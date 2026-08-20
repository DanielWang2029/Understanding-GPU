#!/usr/bin/env python3
"""Build the interactive global compute map dataset.

Ingests four independent sources, resolves them into one canonical set of
sites, and emits `docs/compute-map/data.json` with continent, country and site
roll-ups.

Sources
  1. dataCenterView  — `datecenterview-main.zip` in the repo root: 490 US data
     centers with status, capacity and 1,115 source URLs (the uploaded project).
  2. Epoch AI        — `data/sources/epoch_ai/*.csv` (CC-BY): 83 frontier AI
     data centers with modelled power, H100-equivalents, per-chip-type unit
     counts and forward-dated build timelines (the "planned" numbers).
  3. Curated global  — `data/compute_map/curated_sites.csv`: 95 sites outside
     Epoch's coverage, mostly non-US, each with sources.
  4. Cloud regions   — `data/compute_map/accelerator_regions.csv`: where TPU,
     Trainium and GPU SKUs can actually be rented, region by region.

Deduplication: sites are merged when they describe the same physical campus.
Rules are (a) explicit pairs in `identity_rules.csv`, (b) geographic proximity
plus operator or name agreement, (c) identical normalised name in the same
admin area for records with no coordinates. Explicit `never` rules win over
everything, because several genuinely distinct buildings sit a few hundred
metres apart.

    python3 scripts/build_compute_map.py
"""

from __future__ import annotations

import csv
import json
import math
import pathlib
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DCV_ZIP = ROOT / "datecenterview-main.zip"
EPOCH_DIR = ROOT / "data" / "sources" / "epoch_ai"
MAP_DIR = ROOT / "data" / "compute_map"
GEOCACHE = ROOT / "data" / "sources" / "geocode_cache.json"
ISO_CSV = ROOT / "data" / "sources" / "iso3166_country_regions.csv"
OUT = ROOT / "docs" / "compute-map" / "data.json"

AS_OF = "2026-08-20"

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
STOPWORDS = {
    "data", "center", "centre", "centers", "centres", "campus", "dc", "site",
    "facility", "the", "of", "at", "and", "phase", "building", "expansion",
    "project", "inc", "llc", "ltd", "corp", "co", "cloud", "ai", "north",
    "south", "east", "west",
}
OPERATOR_ALIASES = {
    "spacexai": "xai", "x ai": "xai", "space xai": "xai",
    "google cloud": "google", "google llc": "google", "alphabet": "google",
    "amazon web services": "amazon", "aws": "amazon",
    "microsoft corporation": "microsoft", "msft": "microsoft",
    "meta platforms": "meta", "facebook": "meta",
    "crusoe energy": "crusoe", "coreweave inc": "coreweave",
    "qts realty trust": "qts", "qts data centers": "qts",
    "oracle corporation": "oracle", "oracle cloud": "oracle",
    "terawulf": "terawulf", "ai xpv platform": "terawulf",
    "gds": "dayone", "gds holdings": "dayone",
}


def norm_text(value: str | None) -> str:
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


METRO_TOKENS = {
    "san", "jose", "los", "angeles", "silicon", "valley", "santa", "clara",
    "dallas", "fort", "worth", "plano", "austin", "houston", "antonio",
    "phoenix", "mesa", "goodyear", "atlanta", "chicago", "denver", "columbus",
    "richmond", "sterling", "ashburn", "manassas", "reston", "memphis",
    "seattle", "portland", "boston", "york", "jersey", "miami", "vegas",
    "sacramento", "diego", "francisco", "oakland", "tulsa", "omaha", "abilene",
    "kansas", "city", "county", "township", "metro", "park", "plaza", "street",
    "blvd", "road", "drive", "avenue", "st", "dr", "ave", "rd", "one", "two",
}
DESIGNATOR = re.compile(r"^[a-z]{0,5}\d{1,6}[a-z]?$")


def name_tokens(name: str, geo: str = "") -> set[str]:
    geo_tokens = set(norm_text(geo).split()) | METRO_TOKENS
    return {t for t in norm_text(name).split()
            if t and t not in STOPWORDS and t not in geo_tokens
            and not DESIGNATOR.match(t)}


def designators(name: str) -> set[str]:
    """Facility codes such as SV3, LA1, RIC5, VA4, DA11, NVA02, or a street
    number. Two records that carry different codes are different buildings."""
    return {t for t in norm_text(name).split() if DESIGNATOR.match(t) and t not in {"1", "2"}} | \
           {t for t in norm_text(name).split() if t in {"1", "2", "3", "4", "5"}}


def norm_operator(value: str | None) -> str:
    s = norm_text(re.sub(r"#\w+", "", value or ""))
    return OPERATOR_ALIASES.get(s, s)


def num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = p2 - p1
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


STATUS_ORDER = ["cancelled", "announced", "planned", "under_construction",
                "expanding", "operating"]


def norm_status(raw: str | None) -> str:
    s = norm_text(raw)
    if not s:
        return "unknown"
    if "cancel" in s:
        return "cancelled"
    if "announce" in s:
        return "announced"
    if "plan" in s or "proposed" in s:
        return "planned"
    if "construction" in s or s == "under construction":
        return "under_construction"
    if "expand" in s:
        return "expanding"
    if "operat" in s or "live" in s or "online" in s or s == "reported":
        return "operating"
    return "unknown"


def better_status(a: str, b: str) -> str:
    """Keep the most-built status: a campus that is operating and expanding is
    operating."""
    ia = STATUS_ORDER.index(a) if a in STATUS_ORDER else -1
    ib = STATUS_ORDER.index(b) if b in STATUS_ORDER else -1
    return a if ia >= ib else b


PRECISION_RANK = {"site": 6, "building": 6, "exact": 6, "street": 5, "facility": 5,
                  "suburb": 4, "district": 4, "locality": 4, "city": 3, "town": 3,
                  "municipality": 3, "county": 2, "state": 1, "region": 1,
                  "country": 0, "none": -1, "unknown": -1, "": -1}


def precision_rank(p: str | None) -> int:
    return PRECISION_RANK.get((p or "").lower(), -1)


# Chip families keep the map legible: the question users ask is "GPU or TPU?"
def chip_family(chip: str) -> str:
    c = norm_text(chip)
    if not c:
        return "Other"
    if "tpu" in c:
        return "Google TPU"
    if "trainium" in c or "inferentia" in c:
        return "AWS Trainium"
    if "ascend" in c:
        return "Huawei Ascend"
    if "mi3" in c or "mi2" in c or "mi4" in c or "instinct" in c:
        return "AMD Instinct"
    if "wse" in c or "cerebras" in c:
        return "Cerebras WSE"
    if "lpu" in c or "groq" in c:
        return "Groq LPU"
    if "gaudi" in c:
        return "Intel Gaudi"
    if "max" in c and "gpu" in c:
        return "Intel GPU"
    if "ai100" in c or "qualcomm" in c:
        return "Qualcomm AI100"
    if any(k in c for k in ("h100", "h200", "h20", "a100", "b200", "b300", "gb200",
                            "gb300", "rubin", "v100", "l40", "l4", "rtx", "nvidia",
                            "grace", "gh200", "blackwell")):
        return "NVIDIA GPU"
    return "Other"


# --------------------------------------------------------------------------
# country / continent metadata
# --------------------------------------------------------------------------
MANUAL_CONTINENT = {
    "Taiwan, Province of China": "Asia",
    "Taiwan": "Asia",
}


def load_country_meta() -> dict:
    """ISO 3166 name -> {iso3, iso_num, continent}. Splits the ISO 'Americas'
    region into North and South America, which is what people mean by
    continent."""
    meta = {}
    for row in csv.DictReader(ISO_CSV.open()):
        region = row["region"]
        sub = row["sub-region"]
        inter = row["intermediate-region"]
        if region == "Americas":
            continent = "South America" if (inter == "South America" or
                                            sub == "Latin America and the Caribbean" and
                                            inter == "South America") else "North America"
        elif region:
            continent = region
        elif row["name"] == "Antarctica":
            continent = "Antarctica"
        else:
            # ISO leaves the region blank for a couple of entries (Taiwan).
            continent = MANUAL_CONTINENT.get(row["name"], "Unknown")
        meta[row["name"]] = {
            "iso3": row["alpha-3"],
            "iso_num": row["country-code"],
            "continent": continent,
        }
    # Names as they appear in our sources -> ISO 3166 official names.
    aliases = {
        "United States": "United States of America",
        "USA": "United States of America",
        "South Korea": "Korea, Republic of",
        "Korea": "Korea, Republic of",
        "Taiwan": "Taiwan, Province of China",
        "Hong Kong SAR": "Hong Kong",
        "United Arab Emirates": "United Arab Emirates",
        "United Kingdom": "United Kingdom of Great Britain and Northern Ireland",
        "Russia": "Russian Federation",
        "Vietnam": "Viet Nam",
        "Netherlands": "Netherlands, Kingdom of the",
        "Turkey": "Türkiye",
        "Czechia": "Czechia",
        "Iran": "Iran, Islamic Republic of",
        "Bolivia": "Bolivia, Plurinational State of",
        "Venezuela": "Venezuela, Bolivarian Republic of",
        "Tanzania": "Tanzania, United Republic of",
        "Moldova": "Moldova, Republic of",
        "Syria": "Syrian Arab Republic",
        "Laos": "Lao People's Democratic Republic",
        "Brunei": "Brunei Darussalam",
        "Cape Verde": "Cabo Verde",
        "Ivory Coast": "Côte d'Ivoire",
        "DR Congo": "Congo, Democratic Republic of the",
    }
    out = dict(meta)
    for src, official in aliases.items():
        if official in meta:
            out[src] = meta[official]
    # South America fix-up: the ISO file's intermediate-region is blank for a few.
    for name in ("Brazil", "Chile", "Argentina", "Colombia", "Peru", "Uruguay",
                 "Paraguay", "Bolivia, Plurinational State of", "Ecuador",
                 "Venezuela, Bolivarian Republic of", "Guyana", "Suriname",
                 "Falkland Islands (Malvinas)", "French Guiana", "Bolivia",
                 "Venezuela"):
        if name in out:
            out[name] = {**out[name], "continent": "South America"}
    return out


COUNTRY_META = load_country_meta()

US_STATE_CENTROIDS = {
    "AL": (32.79, -86.83), "AK": (63.35, -152.84), "AZ": (34.29, -111.66),
    "AR": (34.90, -92.44), "CA": (37.18, -119.47), "CO": (38.997, -105.55),
    "CT": (41.62, -72.73), "DE": (38.99, -75.51), "FL": (28.63, -82.44),
    "GA": (32.64, -83.44), "HI": (20.29, -156.37), "ID": (44.35, -114.61),
    "IL": (40.04, -89.20), "IN": (39.91, -86.28), "IA": (42.07, -93.50),
    "KS": (38.49, -98.38), "KY": (37.53, -85.30), "LA": (31.07, -92.00),
    "ME": (45.37, -69.24), "MD": (39.04, -76.79), "MA": (42.26, -71.81),
    "MI": (44.35, -85.41), "MN": (46.28, -94.31), "MS": (32.74, -89.68),
    "MO": (38.36, -92.48), "MT": (47.05, -109.63), "NE": (41.53, -99.81),
    "NV": (39.33, -116.63), "NH": (43.68, -71.58), "NJ": (40.19, -74.67),
    "NM": (34.42, -106.11), "NY": (42.95, -75.53), "NC": (35.54, -79.36),
    "ND": (47.45, -100.47), "OH": (40.29, -82.79), "OK": (35.59, -97.49),
    "OR": (43.94, -120.56), "PA": (40.87, -77.80), "RI": (41.68, -71.56),
    "SC": (33.92, -80.90), "SD": (44.44, -100.23), "TN": (35.86, -86.35),
    "TX": (31.40, -99.32), "UT": (39.31, -111.67), "VT": (44.07, -72.67),
    "VA": (37.52, -78.85), "WA": (47.38, -120.45), "WV": (38.64, -80.62),
    "WI": (44.62, -89.99), "WY": (42.99, -107.55), "DC": (38.90, -77.02),
}


# --------------------------------------------------------------------------
# source loaders — each returns a list of raw records in a common shape
# --------------------------------------------------------------------------
def blank_record(**kw):
    rec = {
        "dataset": "", "dataset_id": "", "name": "", "operator": "", "tenant": "",
        "city": "", "admin1": "", "country": "", "lat": None, "lon": None,
        "coord_precision": "none", "status": "unknown", "year": None,
        "power_mw": None, "power_mw_planned": None, "h100e": None,
        "h100e_planned": None, "capex_usd_b": None, "chips": {}, "chips_planned": {},
        "accelerators": [], "chip_detail": "", "category": "", "confidence": "",
        "notes": "", "sources": [], "layer": "site",
    }
    rec.update(kw)
    return rec


def load_dcv() -> list[dict]:
    if not DCV_ZIP.exists():
        print(f"  ! {DCV_ZIP.name} not found; skipping dataCenterView")
        return []
    with zipfile.ZipFile(DCV_ZIP) as zf:
        member = next(n for n in zf.namelist() if n.endswith("/data.json")
                      or n.endswith("data.json"))
        payload = json.loads(zf.read(member).decode())
    out = []
    for r in payload["datasets"]["data_center"]:
        state = (r.get("state") or "").strip()
        lat, lon = num(r.get("lat")), num(r.get("lng"))
        precision = (r.get("geo_precision") or "none").lower()
        if lat is None and state in US_STATE_CENTROIDS:
            lat, lon = US_STATE_CENTROIDS[state]
            precision = "state"
        status = norm_status(r.get("status"))
        capacity = num(r.get("capacity_mw"))
        # dataCenterView's capacity_mw is the site's nameplate capacity, which is
        # only energised where the site is actually operating. Attributing it to
        # "operating" power for a site under construction overstates today.
        power_now = capacity if status in ("operating", "expanding") else None
        capex = num(r.get("cap_ex"))
        out.append(blank_record(
            dataset="dataCenterView",
            dataset_id=r["id"],
            name=r.get("project_name") or r["id"],
            operator=r.get("operator") or r.get("developer") or "",
            tenant=r.get("tenant") or r.get("end_user") or "",
            city=(r.get("county") or ""),
            admin1=state,
            country="United States",
            lat=lat, lon=lon, coord_precision=precision,
            status=status,
            year=num(r.get("operating_year")),
            power_mw=power_now,
            power_mw_planned=capacity,
            capex_usd_b=(capex / 1e9) if capex and capex > 1e6 else capex,
            category=r.get("developer_category") or "",
            confidence=f"pipeline confidence {r.get('confidence')}" if r.get("confidence") else "",
            notes=f"review status: {r.get('review_status')}" if r.get("review_status") else "",
            sources=[s for s in (r.get("sources") or []) if s.startswith("http")],
        ))
    return out


def load_epoch() -> list[dict]:
    sites = list(csv.DictReader((EPOCH_DIR / "data_centers.csv").open()))
    timelines = list(csv.DictReader((EPOCH_DIR / "data_center_timelines.csv").open()))
    chips = list(csv.DictReader((EPOCH_DIR / "data_center_chip_quantities.csv").open()))
    geo = json.loads(GEOCACHE.read_text()) if GEOCACHE.exists() else {}
    overrides = {r["site_name"]: r for r in
                 csv.DictReader((MAP_DIR / "epoch_coord_overrides.csv").open())}
    aliases = {norm_text(r["chip_table_name"]): r for r in
               csv.DictReader((MAP_DIR / "chip_table_aliases.csv").open())}

    # timelines: split into "as of now" and "peak planned"
    now_power, peak_power, now_h1, peak_h1, status_now, peak_date = {}, {}, {}, {}, {}, {}
    latest_note = {}
    for t in timelines:
        site = t["Data center"]
        date = t["Date"][:10]
        p = num(t.get("IT power (MW)")) or 0.0
        h = num(t.get("H100 equivalents")) or 0.0
        if date <= AS_OF:
            if p >= now_power.get(site, 0):
                now_power[site] = p
            if h >= now_h1.get(site, 0):
                now_h1[site] = h
            if date >= status_now.get(site, ("", ""))[0]:
                status_now[site] = (date, t.get("Construction status", ""))
                latest_note[site] = (date, t.get("Construction status", ""))
        peak_power[site] = max(peak_power.get(site, 0.0), p)
        peak_h1[site] = max(peak_h1.get(site, 0.0), h)
        if p > 0 or h > 0:
            peak_date[site] = max(peak_date.get(site, ""), date)

    # chip quantities: latest record per (site, chip type) now vs planned
    chips_now, chips_planned, chip_sources = defaultdict(dict), defaultdict(dict), defaultdict(set)
    dropped_chip_rows = []
    for c in chips:
        raw_site = c["Data center"]
        alias = aliases.get(norm_text(raw_site))
        target = raw_site
        if alias:
            if alias["action"] == "drop":
                dropped_chip_rows.append(raw_site)
                continue
            if alias["action"] in ("merge_into", "attach_to"):
                target = alias["target"]
        date = c["Date"][:10]
        chip = c["Chip type"]
        units = num(c.get("Number of Units")) or 0.0
        bucket = chips_now if date <= AS_OF else chips_planned
        prev = bucket[target].get(chip)
        if prev is None or date >= prev[0]:
            bucket[target][chip] = (date, units)
        note = (c.get("Notes") or "")
        for url in re.findall(r"https?://[^\s)\]]+", note):
            chip_sources[target].add(url.rstrip(".,"))

    out = []
    for s in sites:
        name = s["Name"].strip()
        lat = lon = None
        precision, coord_src = "none", ""
        if name in overrides:
            o = overrides[name]
            lat, lon = num(o["lat"]), num(o["lon"])
            precision, coord_src = o["coord_precision"], o["source"]
        elif name in geo and geo[name].get("lat") is not None:
            g = geo[name]
            lat, lon = g["lat"], g["lon"]
            precision = g["precision"]
            coord_src = g.get("source", "OpenStreetMap Nominatim")
        urls = re.findall(r"https?://[^\s)\]]+", s.get("Selected Sources") or "")
        urls = [u.rstrip(".,)") for u in urls]
        urls += sorted(chip_sources.get(name, ()))
        chip_now = {k: v[1] for k, v in chips_now.get(name, {}).items() if v[1] > 0}
        chip_plan = {k: v[1] for k, v in chips_planned.get(name, {}).items() if v[1] > 0}
        # Epoch's "Construction status" column is a free-text observation note
        # (e.g. "the proposed expansion was achieved in time"), so keyword
        # matching mislabels operating sites. Derive status from the numbers,
        # which is what the figures actually support, and keep the prose as an
        # observation note.
        cur_p = now_power.get(name, 0) or 0
        peak_p = peak_power.get(name, 0) or 0
        cur_h = now_h1.get(name, 0) or 0
        if cur_p > 0 or cur_h > 0:
            status = "expanding" if peak_p > cur_p * 1.05 else "operating"
        elif peak_p > 0 or (peak_h1.get(name, 0) or 0) > 0:
            status = "under_construction"
        else:
            status = "announced"
        note = (latest_note.get(name, ("", ""))[1] or "").strip()
        note = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", note)
        observation = (f"Epoch observation {latest_note[name][0]}: {note[:260]}"
                       if note else "")
        out.append(blank_record(
            dataset="Epoch AI",
            dataset_id=name,
            name=name,
            operator=re.sub(r"#\w+", "", s.get("Owner") or "").strip(" ,"),
            tenant=re.sub(r"#\w+", "", s.get("Users") or "").strip(" ,"),
            city=(s.get("Address") or "").split(",")[-3].strip() if (s.get("Address") or "").count(",") >= 2 else "",
            admin1="",
            country=s.get("Country") or "",
            lat=lat, lon=lon, coord_precision=precision,
            status=status,
            power_mw=now_power.get(name) or num(s.get("Current power (MW)")),
            power_mw_planned=peak_power.get(name),
            h100e=now_h1.get(name) or num(s.get("Current H100 equivalents")),
            h100e_planned=peak_h1.get(name),
            capex_usd_b=num(s.get("Current total capital cost (2025 USD billions)")),
            chips=chip_now, chips_planned=chip_plan,
            accelerators=sorted({chip_family(c) for c in
                                 (list(chip_now) + list(chip_plan) +
                                  (s.get("All chip types") or "").split(","))
                                 if c.strip()}),
            chip_detail="; ".join(f"{k}: {int(v):,}" for k, v in
                                  sorted(chip_now.items(), key=lambda kv: -kv[1])),
            category="frontier",
            confidence="Epoch AI model output (power, chips and capex are estimates)",
            notes="; ".join(filter(None, [
                f"peak planned build date {peak_date.get(name)}" if peak_date.get(name) else "",
                observation])),
            sources=urls + ["https://epoch.ai/data/ai-data-centers"],
        ))
    if dropped_chip_rows:
        print(f"  dropped {len(set(dropped_chip_rows))} chip-table record(s) per alias rules: "
              f"{sorted(set(dropped_chip_rows))}")
    # chip-table-only names routed to curated sites are handled by the curated
    # loader reading the same alias file.
    return out, chips_now, chips_planned, chip_sources, aliases


def load_curated(chips_now, chips_planned, chip_sources, aliases) -> list[dict]:
    attach = {}
    for norm_name, rule in aliases.items():
        if rule["action"] == "attach_to":
            attach[rule["target"]] = rule
    out = []
    for r in csv.DictReader((MAP_DIR / "curated_sites.csv").open()):
        chips = {}
        chips_plan = {}
        extra_sources = []
        rule = attach.get(r["id"])
        if rule:
            key = rule["chip_table_name"]
            # chip tables are keyed by their own display name
            for src_key in (key, norm_text(key)):
                if src_key in chips_now:
                    chips = {k: v[1] for k, v in chips_now[src_key].items() if v[1] > 0}
                if src_key in chips_planned:
                    chips_plan = {k: v[1] for k, v in chips_planned[src_key].items() if v[1] > 0}
                extra_sources += sorted(chip_sources.get(src_key, ()))
        accel = [a.strip() for a in (r["accelerators"] or "").split("|") if a.strip()]
        accel += [chip_family(c) for c in list(chips) + list(chips_plan)]
        out.append(blank_record(
            dataset="curated",
            dataset_id=r["id"],
            name=r["name"],
            operator=r["operator"], tenant=r["tenant"],
            city=r["city"], admin1=r["admin1"], country=r["country"],
            lat=num(r["lat"]), lon=num(r["lon"]),
            coord_precision=r["coord_precision"],
            status=norm_status(r["status"]), year=num(r["year"]),
            power_mw=num(r["power_mw_current"]),
            power_mw_planned=num(r["power_mw_planned"]) or num(r["power_mw_current"]),
            h100e=num(r["h100e_current"]), h100e_planned=num(r["h100e_planned"]),
            capex_usd_b=num(r["capex_usd_b"]),
            chips=chips, chips_planned=chips_plan,
            accelerators=sorted(set(accel)),
            chip_detail=r["chip_detail"],
            category=r["category"], confidence=r["confidence"], notes=r["notes"],
            sources=[s for s in r["sources"].split("|") if s.startswith("http")] + extra_sources,
        ))
    return out


def load_regions() -> list[dict]:
    out = []
    for r in csv.DictReader((MAP_DIR / "accelerator_regions.csv").open()):
        out.append(blank_record(
            dataset="cloud region",
            dataset_id=f"{r['provider']}:{r['region_id']}",
            name=f"{r['provider']} {r['region_id']}",
            operator=r["provider"], tenant="",
            city=r["city"], admin1="", country=r["country"],
            lat=num(r["lat"]), lon=num(r["lon"]),
            coord_precision=r["coord_precision"],
            status=norm_status(r["status"]),
            accelerators=[a.strip() for a in r["accelerators"].split("|") if a.strip()],
            chip_detail=r["detail"],
            category="cloud_region",
            confidence="provider documentation",
            notes=f"region {r['region_id']} ({r['label']})",
            sources=[s for s in r["sources"].split("|") if s.startswith("http")],
            layer="cloud_region",
        ))
    return out


# --------------------------------------------------------------------------
# deduplication
# --------------------------------------------------------------------------
class Union:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def dedupe(records: list[dict]) -> tuple[list[list[int]], list[dict]]:
    rules = list(csv.DictReader((MAP_DIR / "identity_rules.csv").open()))
    force = [(norm_text(r["name_a"]), norm_text(r["name_b"]), r["reason"])
             for r in rules if r["rule"] == "merge"]
    never = {frozenset((norm_text(r["name_a"]), norm_text(r["name_b"])))
             for r in rules if r["rule"] == "never"}

    by_norm = defaultdict(list)
    for i, r in enumerate(records):
        by_norm[norm_text(r["name"])].append(i)

    uf = Union(len(records))
    log = []

    def blocked(i, j) -> bool:
        return frozenset((norm_text(records[i]["name"]),
                          norm_text(records[j]["name"]))) in never

    # (a) explicit merges
    for a, b, reason in force:
        for i in by_norm.get(a, []):
            for j in by_norm.get(b, []):
                uf.union(i, j)
                log.append({"kind": "explicit", "a": records[i]["name"],
                            "b": records[j]["name"], "reason": reason})

    # (b) geographic proximity + name/operator agreement
    geo = [i for i, r in enumerate(records)
           if r["lat"] is not None and r["layer"] == "site"
           and precision_rank(r["coord_precision"]) >= 2]
    cell = defaultdict(list)
    for i in geo:
        r = records[i]
        cell[(round(r["lat"] * 4), round(r["lon"] * 4))].append(i)
    for (cy, cx), members in list(cell.items()):
        neigh = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                neigh += cell.get((cy + dy, cx + dx), [])
        for i in members:
            for j in neigh:
                if j <= i or blocked(i, j):
                    continue
                a, b = records[i], records[j]
                d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
                if d > 3.0:
                    continue
                da, db = designators(a["name"]), designators(b["name"])
                if da != db:
                    # e.g. CoreSite SV3 vs SV9, Equinix DA1 vs DA11 vs DA, H5
                    # Virginia 4030 vs 4040: one campus, different buildings.
                    # Codes must match exactly, since brand prefixes such as
                    # "h5" are themselves code-shaped and would otherwise let
                    # different buildings pass.
                    continue
                geo = " ".join(filter(None, [a["city"], a["admin1"], b["city"], b["admin1"]]))
                ta, tb = name_tokens(a["name"], geo), name_tokens(b["name"], geo)
                overlap = len(ta & tb) / max(1, min(len(ta), len(tb))) if ta and tb else 0
                op_a, op_b = norm_operator(a["operator"]), norm_operator(b["operator"])
                same_op = bool(op_a) and op_a == op_b
                one_unknown_op = not op_a or not op_b
                if same_op and d <= 1.0:
                    reason = f"{d*1000:.0f} m apart, same operator"
                elif same_op and overlap >= 0.5:
                    reason = f"{d:.1f} km apart, same operator, {overlap:.0%} name overlap"
                elif overlap >= 0.6 and (same_op or one_unknown_op) and d <= 1.0:
                    reason = f"{d*1000:.0f} m apart with {overlap:.0%} name overlap"
                else:
                    continue
                uf.union(i, j)
                log.append({"kind": "proximity", "a": a["name"], "b": b["name"],
                            "reason": reason})

    # (b2) same facility, coarse coordinate. dataCenterView often places a site
    # tens of km from the campus, so proximity alone misses obvious duplicates
    # such as "xAI Colossus 2" (dcv) and "Colossus 2" (Epoch), 18 km apart.
    # Two escape hatches, both requiring operator agreement:
    #   - identical facility code (Microsoft SAT14 == Microsoft SAT14)
    #   - a shared distinctive token that is neither operator nor place name
    def operator_tokens(rec):
        return set(norm_operator(rec["operator"]).split()) | set(
            norm_text(rec["operator"]).split())

    # A token is only "distinctive" if it identifies one campus. Programme and
    # brand words ("stargate" spans seven sites, "aws" dozens) show up in many
    # names, so measure document frequency and drop the common ones instead of
    # maintaining a hand-written stoplist.
    token_df = defaultdict(int)
    for r in records:
        for t in name_tokens(r["name"]):
            token_df[t] += 1
    common = {t for t, n in token_df.items() if n >= 4}

    located = [i for i, r in enumerate(records)
               if r["lat"] is not None and r["layer"] == "site"]
    for ai, i in enumerate(located):
        a = records[i]
        for j in located[ai + 1:]:
            b = records[j]
            if a["dataset"] == b["dataset"] or blocked(i, j):
                continue
            if uf.find(i) == uf.find(j):
                continue
            da, db = designators(a["name"]), designators(b["name"])
            if da != db:
                continue
            op_a, op_b = norm_operator(a["operator"]), norm_operator(b["operator"])
            same_op = bool(op_a) and op_a == op_b
            one_unknown_op = not op_a or not op_b
            d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            drop = operator_tokens(a) | operator_tokens(b)
            geo = " ".join(filter(None, [a["city"], a["admin1"], b["city"], b["admin1"]]))
            ta = name_tokens(a["name"], geo) - drop - common
            tb = name_tokens(b["name"], geo) - drop - common
            distinctive = len(ta & tb) / max(1, min(len(ta), len(tb))) if ta and tb else 0
            if same_op and da and d <= 400:
                reason = f"same operator and facility code {sorted(da)} ({d:.0f} km apart in the two sources)"
            elif d <= 40 and distinctive >= 0.5 and (same_op or one_unknown_op):
                reason = (f"{d:.0f} km apart, shared distinctive name "
                          f"{sorted(ta & tb)} across two datasets")
            else:
                continue
            uf.union(i, j)
            log.append({"kind": "cross-dataset", "a": a["name"], "b": b["name"],
                        "reason": reason})

    # (c) identical name + admin area for records without usable coordinates
    keyed = defaultdict(list)
    for i, r in enumerate(records):
        if r["layer"] != "site":
            continue
        key = (norm_text(r["name"]), r["country"], r["admin1"])
        if norm_text(r["name"]):
            keyed[key].append(i)
    for key, members in keyed.items():
        for j in members[1:]:
            da, db = designators(records[members[0]]["name"]), designators(records[j]["name"])
            if da != db:
                continue
            if not blocked(members[0], j):
                uf.union(members[0], j)
                log.append({"kind": "same-name", "a": records[members[0]]["name"],
                            "b": records[j]["name"],
                            "reason": f"identical name in {key[2] or key[1]}"})

    groups = defaultdict(list)
    for i in range(len(records)):
        groups[uf.find(i)].append(i)
    return list(groups.values()), log


# --------------------------------------------------------------------------
# merging a group into a canonical site
# --------------------------------------------------------------------------
DATASET_TRUST = {"Epoch AI": 3, "curated": 2, "dataCenterView": 1, "cloud region": 0}


def site_tier(lead, members, power_planned, chips, families) -> str:
    """How significant is this site for an AI-compute map? Lets the UI hide the
    long tail of small retail colocation without discarding it."""
    if lead["layer"] == "cloud_region":
        return "cloud_region"
    if chips or any(m["dataset"] == "Epoch AI" for m in members):
        return "frontier"
    if (power_planned or 0) >= 100:
        return "frontier"
    if (power_planned or 0) >= 20:
        return "large"
    return "small"


def merge_group(records: list[dict], idxs: list[int]) -> dict:
    members = [records[i] for i in idxs]
    members.sort(key=lambda r: (-DATASET_TRUST.get(r["dataset"], 0),
                                -precision_rank(r["coord_precision"]),
                                -(r["power_mw"] or 0)))
    lead = members[0]

    best_coord = max(members, key=lambda r: (precision_rank(r["coord_precision"]),
                                             r["lat"] is not None))
    status = "unknown"
    for m in members:
        status = better_status(status, m["status"])

    def pick_max(field):
        vals = [m[field] for m in members if m[field] is not None]
        return max(vals) if vals else None

    chips, chips_planned = defaultdict(float), defaultdict(float)
    for m in members:
        for k, v in m["chips"].items():
            chips[k] = max(chips[k], v)
        for k, v in m["chips_planned"].items():
            chips_planned[k] = max(chips_planned[k], v)

    families = defaultdict(float)
    for k, v in chips.items():
        families[chip_family(k)] += v
    families_planned = defaultdict(float)
    for k, v in chips_planned.items():
        families_planned[chip_family(k)] += v

    accel = sorted({a for m in members for a in m["accelerators"] if a})
    sources, seen = [], set()
    for m in members:
        for u in m["sources"]:
            u = u.strip()
            if u and u not in seen:
                seen.add(u)
                sources.append({"url": u, "dataset": m["dataset"]})

    power = pick_max("power_mw")
    power_planned = pick_max("power_mw_planned")
    if power_planned is not None and power is not None:
        power_planned = max(power_planned, power)

    country = lead["country"] or next((m["country"] for m in members if m["country"]), "")
    meta = COUNTRY_META.get(country, {})
    return {
        "id": f"site-{lead['dataset'][:3].lower()}-{abs(hash(lead['dataset_id'])) % 10**9}",
        "name": lead["name"],
        "aka": sorted({m["name"] for m in members if m["name"] != lead["name"]}),
        "operator": lead["operator"] or next((m["operator"] for m in members if m["operator"]), ""),
        "tenant": lead["tenant"] or next((m["tenant"] for m in members if m["tenant"]), ""),
        "city": lead["city"] or next((m["city"] for m in members if m["city"]), ""),
        "admin1": lead["admin1"] or next((m["admin1"] for m in members if m["admin1"]), ""),
        "country": country,
        "continent": meta.get("continent", "Unknown"),
        "iso3": meta.get("iso3", ""),
        "lat": best_coord["lat"], "lon": best_coord["lon"],
        "coord_precision": best_coord["coord_precision"],
        "status": status,
        "year": pick_max("year"),
        "power_mw": power,
        "power_mw_planned": power_planned,
        "h100e": pick_max("h100e"),
        "h100e_planned": pick_max("h100e_planned"),
        "capex_usd_b": pick_max("capex_usd_b"),
        "chips": {k: round(v) for k, v in sorted(chips.items(), key=lambda kv: -kv[1])},
        "chips_planned": {k: round(v) for k, v in
                          sorted(chips_planned.items(), key=lambda kv: -kv[1])},
        "chip_families": {k: round(v) for k, v in
                          sorted(families.items(), key=lambda kv: -kv[1])},
        "chip_families_planned": {k: round(v) for k, v in
                                  sorted(families_planned.items(), key=lambda kv: -kv[1])},
        "accelerators": accel,
        "chip_detail": next((m["chip_detail"] for m in members if m["chip_detail"]), ""),
        "category": lead["category"] or next((m["category"] for m in members if m["category"]), ""),
        "confidence": "; ".join(dict.fromkeys(m["confidence"] for m in members if m["confidence"])),
        "notes": "; ".join(dict.fromkeys(m["notes"] for m in members if m["notes"]))[:400],
        "layer": lead["layer"],
        "tier": site_tier(lead, members, power_planned, chips, families),
        "datasets": sorted({m["dataset"] for m in members}),
        "records": [{"dataset": m["dataset"], "id": m["dataset_id"], "name": m["name"],
                     "operator": m["operator"], "status": m["status"],
                     "power_mw": m["power_mw"], "sources": len(m["sources"])}
                    for m in members],
        "sources": sources,
    }


# --------------------------------------------------------------------------
# roll-ups
# --------------------------------------------------------------------------
def zero_agg():
    return {"sites": 0, "sites_located": 0, "power_mw": 0.0, "power_mw_planned": 0.0,
            "h100e": 0.0, "h100e_planned": 0.0, "capex_usd_b": 0.0,
            "chip_families": defaultdict(float), "chip_families_planned": defaultdict(float),
            "status": defaultdict(int), "accelerators": defaultdict(int),
            "cloud_regions": 0, "operators": defaultdict(float)}


def add_site(agg, s):
    if s["layer"] == "cloud_region":
        agg["cloud_regions"] += 1
        for a in s["accelerators"]:
            agg["accelerators"][a] += 1
        return
    agg["sites"] += 1
    if s["lat"] is not None:
        agg["sites_located"] += 1
    agg["power_mw"] += s["power_mw"] or 0
    agg["power_mw_planned"] += s["power_mw_planned"] or s["power_mw"] or 0
    agg["h100e"] += s["h100e"] or 0
    agg["h100e_planned"] += max(s["h100e_planned"] or 0, s["h100e"] or 0)
    agg["capex_usd_b"] += s["capex_usd_b"] or 0
    agg["status"][s["status"]] += 1
    for k, v in s["chip_families"].items():
        agg["chip_families"][k] += v
    for k, v in s["chip_families_planned"].items():
        agg["chip_families_planned"][k] += max(v, s["chip_families"].get(k, 0))
    for a in s["accelerators"]:
        agg["accelerators"][a] += 1
    if s["operator"]:
        agg["operators"][s["operator"]] += (s["power_mw_planned"] or s["power_mw"] or 0)


def finish(agg):
    out = dict(agg)
    for key in ("chip_families", "chip_families_planned", "status", "accelerators"):
        out[key] = {k: (round(v) if isinstance(v, float) else v)
                    for k, v in sorted(agg[key].items(), key=lambda kv: -kv[1])}
    out["operators"] = [{"name": k, "power_mw": round(v)} for k, v in
                        sorted(agg["operators"].items(), key=lambda kv: -kv[1])[:8]]
    for key in ("power_mw", "power_mw_planned", "h100e", "h100e_planned", "capex_usd_b"):
        out[key] = round(agg[key], 1)
    return out


def main() -> int:
    print("Loading sources:")
    dcv = load_dcv()
    print(f"  dataCenterView: {len(dcv)} records")
    epoch, chips_now, chips_planned, chip_sources, aliases = load_epoch()
    print(f"  Epoch AI:       {len(epoch)} records")
    curated = load_curated(chips_now, chips_planned, chip_sources, aliases)
    print(f"  curated:        {len(curated)} records")
    regions = load_regions()
    print(f"  cloud regions:  {len(regions)} records")

    records = dcv + epoch + curated + regions
    print(f"\nDeduplicating {len(records)} records...")
    groups, log = dedupe(records)
    sites = [merge_group(records, g) for g in groups]
    merged = [s for s in sites if len(s["records"]) > 1]
    print(f"  {len(groups)} canonical entries; {len(merged)} formed by merging "
          f"{sum(len(s['records']) for s in merged)} records")
    for entry in log[:14]:
        print(f"    [{entry['kind']}] {entry['a']} + {entry['b']} — {entry['reason']}")
    if len(log) > 14:
        print(f"    ... and {len(log)-14} more merges")

    # roll-ups
    countries, continents, world = {}, {}, zero_agg()
    for s in sites:
        cont = s["continent"] or "Unknown"
        key = s["country"] or "Unknown"
        countries.setdefault(key, {"name": key, "iso3": s["iso3"], "continent": cont,
                                   "agg": zero_agg()})
        continents.setdefault(cont, {"name": cont, "agg": zero_agg()})
        add_site(countries[key]["agg"], s)
        add_site(continents[cont]["agg"], s)
        add_site(world, s)

    def centroid(items):
        pts = [(s["lat"], s["lon"], (s["power_mw_planned"] or s["power_mw"] or 1))
               for s in items if s["lat"] is not None]
        if not pts:
            return None, None
        tw = sum(p[2] for p in pts) or 1
        return (sum(p[0] * p[2] for p in pts) / tw, sum(p[1] * p[2] for p in pts) / tw)

    for key, c in countries.items():
        members = [s for s in sites if (s["country"] or "Unknown") == key]
        lat, lon = centroid(members)
        c.update({"lat": lat, "lon": lon, **finish(c.pop("agg"))})
    for key, c in continents.items():
        members = [s for s in sites if (s["continent"] or "Unknown") == key]
        lat, lon = centroid(members)
        c.update({"lat": lat, "lon": lon, **finish(c.pop("agg")),
                  "countries": sorted([k for k, v in countries.items()
                                       if v["continent"] == key])})

    # every country in ISO 3166 keyed by the numeric code used as the feature id
    # in world-atlas topojson, so the map can shade and zoom to any country
    country_index = {}
    for name, meta in COUNTRY_META.items():
        code = meta["iso_num"]
        if code and code not in country_index:
            country_index[code] = {"iso3": meta["iso3"], "name": name,
                                   "continent": meta["continent"]}
    # prefer the short source-facing names where we have data for them
    for c in countries.values():
        for code, entry in country_index.items():
            if entry["iso3"] == c["iso3"]:
                entry["name"] = c["name"]

    payload = {
        "generated_at": AS_OF,
        "country_index": country_index,
        "as_of": AS_OF,
        "world": finish(world),
        "continents": [continents[k] for k in sorted(continents)],
        "countries": [countries[k] for k in sorted(countries)],
        "sites": sorted(sites, key=lambda s: -(s["power_mw_planned"] or s["power_mw"] or 0)),
        "merge_log": log,
        "sources": {
            "dataCenterView": {
                "records": len(dcv),
                "note": "Uploaded dataCenterView project (datecenterview-main.zip): US data centers "
                        "with field-level provenance from its Postgres system of record.",
            },
            "Epoch AI": {
                "records": len(epoch),
                "licence": "CC-BY 4.0",
                "citation": "Epoch AI, 'AI Data Centers'. Published online at epoch.ai.",
                "url": "https://epoch.ai/data/ai-data-centers",
                "note": "Power, chip counts, H100-equivalents and capex are Epoch model outputs, "
                        "not company disclosures.",
            },
            "curated": {
                "records": len(curated),
                "note": "Hand-assembled from company announcements, government publications and "
                        "trade press for sites outside Epoch's coverage. Each row carries its own "
                        "source URLs and a confidence label.",
            },
            "cloud regions": {
                "records": len(regions),
                "note": "Where TPU, Trainium and GPU SKUs can actually be provisioned, from "
                        "provider documentation and pricing APIs. Region markers carry no capacity "
                        "so they never double-count campus figures.",
            },
            "geocoding": {
                "note": "Epoch publishes addresses but no coordinates. Addresses were geocoded with "
                        "OpenStreetMap Nominatim (ODbL) and cached; 31 sites use Epoch's own map "
                        "polygon centroids where the geocoder was too coarse.",
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"\nRoll-up:")
    print(f"  world: {world['sites']} sites, {finish(world)['power_mw']:,.0f} MW operating, "
          f"{finish(world)['power_mw_planned']:,.0f} MW planned")
    for c in payload["continents"]:
        print(f"    {c['name']:<15} {c['sites']:>4} sites  {c['power_mw']:>9,.0f} MW now  "
              f"{c['power_mw_planned']:>9,.0f} MW planned  {c['cloud_regions']:>3} regions  "
              f"{len(c['countries']):>2} countries")
    print(f"\nwrote {OUT.relative_to(ROOT)} ({kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
