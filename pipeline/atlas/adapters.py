"""Source adapters: raw source → records.

One function per catalog entry, named in the catalog's `adapter` field. An
adapter's only job is to turn its source's native shape into records whose
`claims` use entity parameter names from `schema.ENTITY_PARAMS`. Adapters do no
entity resolution and no merging — `recognize.py` and `resolve.py` own that, so
that adding a source never means reimplementing identity logic.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import zipfile

from . import schema

ROOT = pathlib.Path(__file__).resolve().parents[2]
MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
URL_RE = re.compile(r"https?://[^\s)\]\"<>]+")


def num(v, default=None):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def urls_in(text: str) -> list[str]:
    return [u.rstrip(".,);") for u in URL_RE.findall(text or "")]


class Emitter:
    """Hands out record ids and stamps the source defaults onto every record."""

    def __init__(self, source: dict):
        self.source = source
        self.n = 0
        self.records: list[dict] = []

    def add(self, kind: str, *, subject_hint: str, subject_type: str,
            claims: dict, date: str = "", confidence: str | None = None,
            documents: list[str] | None = None, context: str = "",
            units: dict | None = None, raw_ref: str = "", subject_id: str = ""):
        assert kind in schema.RECORD_KINDS, f"unknown record kind {kind}"
        claims = {k: v for k, v in claims.items() if v not in (None, "", {}, [])}
        if not claims and kind != "citation":
            return None
        self.n += 1
        rec = schema.default_record()
        rec.update({
            "id": f"{self.source['id']}-{kind}-{self.n:05d}",
            "source": self.source["id"],
            "kind": kind,
            "date": date or "",
            "retrieved": self.source.get("retrieved") or "",
            "subject": subject_id,
            "subject_hint": subject_hint or "",
            "subject_type": subject_type,
            "claims": claims,
            "units": units or {},
            "confidence": confidence or self.source.get("confidence_default") or "estimate",
            "documents": [u for u in (documents or []) if u.startswith("http")],
            "context": (context or "")[:400],
            "raw_ref": raw_ref,
        })
        self.records.append(rec)
        return rec


# ---------------------------------------------------------------------------
# pipelines
# ---------------------------------------------------------------------------
def ingest_datacenterview(source: dict) -> list[dict]:
    em = Emitter(source)
    path = ROOT / source["local_path"]
    if not path.exists():
        return []
    with zipfile.ZipFile(path) as zf:
        member = next(n for n in zf.namelist() if n.endswith("data.json"))
        payload = json.loads(zf.read(member).decode())

    for row in payload["datasets"]["data_center"]:
        name = clean(row.get("project_name")) or row["id"]
        status = clean(row.get("status"))
        capacity = num(row.get("capacity_mw"))
        operating = (status or "").lower().startswith("operat")
        capex = num(row.get("cap_ex"))
        claims = {
            "operator": clean(row.get("operator")) or clean(row.get("developer")),
            "tenant": clean(row.get("tenant")) or clean(row.get("end_user")),
            "status": status,
            "city": clean(row.get("county")),
            "region": clean(row.get("state")),
            "country": "United States",
            "lat": num(row.get("lat")),
            "lon": num(row.get("lng")),
            "coord_precision": clean(row.get("geo_precision")),
            # nameplate capacity is only energised where the site is operating
            "power_mw": capacity if operating else None,
            "power_mw_planned": capacity,
            "first_operational": num(row.get("operating_year")),
            "category": clean(row.get("developer_category")),
            # cap_ex arrives in dollars
            "capex_usd_b": (capex / 1e9) if capex and capex > 1e6 else capex,
        }
        em.add("site_profile", subject_hint=name, subject_type="datacenter",
               claims=claims,
               units={"power_mw": "MW", "power_mw_planned": "MW",
                      "capex_usd_b": "USD billions"},
               date=clean(row.get("last_verified")) or "",
               confidence="estimate" if row.get("review_status") == "needs_review"
                          else "confirmed",
               documents=[u for u in (row.get("sources") or []) if str(u).startswith("http")],
               context=f"review status {row.get('review_status')}; pipeline confidence "
                       f"{row.get('confidence')}",
               raw_ref=f"datasets.data_center[{row['id']}]")

    # the news feed is a document set about the same entities
    for item in payload["datasets"].get("news", [])[:400]:
        title = clean(item.get("title")) or clean(item.get("headline")) or ""
        url = clean(item.get("url")) or ""
        if not url.startswith("http"):
            continue
        em.add("citation", subject_hint=title[:120], subject_type="",
               claims={"headline": title},
               date=clean(item.get("published_at")) or clean(item.get("date")) or "",
               documents=[url], context=clean(item.get("summary")) or "",
               raw_ref="datasets.news")
    return em.records


# ---------------------------------------------------------------------------
# Epoch AI
# ---------------------------------------------------------------------------
def ingest_epoch_sites(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        name = clean(row["Name"])
        owner = re.sub(r"#\w+", "", row.get("Owner") or "").strip(" ,")
        users = re.sub(r"#\w+", "", row.get("Users") or "").strip(" ,")
        chips = [c.strip() for c in (row.get("Current chip types") or "").split(",") if c.strip()]
        docs = [u for _, u in MD_LINK.findall(row.get("Selected Sources") or "")]
        docs += urls_in(row.get("Selected Sources") or "")
        em.add("site_profile", subject_hint=name, subject_type="datacenter",
               claims={"operator": owner or None, "tenant": users or None,
                       "country": clean(row.get("Country")), "category": "frontier"},
               documents=docs, context=clean(row.get("Address")) or "",
               raw_ref=f"data_centers.csv[{name}]")
        em.add("site_capacity", subject_hint=name, subject_type="datacenter",
               claims={"power_mw": num(row.get("Current power (MW)")),
                       "capex_usd_b": num(row.get("Current total capital cost (2025 USD billions)"))},
               units={"power_mw": "MW", "capex_usd_b": "USD billions"},
               documents=docs, raw_ref=f"data_centers.csv[{name}]")
        em.add("site_compute", subject_hint=name, subject_type="datacenter",
               claims={"h100e": num(row.get("Current H100 equivalents")),
                       "accelerators_installed": {c: None for c in chips} or None},
               units={"h100e": "chips"}, documents=docs,
               context="chip types listed without counts in this table",
               raw_ref=f"data_centers.csv[{name}]")
    return em.records


def ingest_epoch_timelines(source: dict) -> list[dict]:
    em = Emitter(source)
    rows = list(csv.DictReader((ROOT / source["local_path"]).open()))
    for row in rows:
        name = clean(row["Data center"])
        date = (row.get("Date") or "")[:10]
        note = MD_LINK.sub(r"\1", row.get("Construction status") or "")
        em.add("site_capacity", subject_hint=name, subject_type="datacenter",
               claims={"power_mw": num(row.get("IT power (MW)")),
                       "capex_usd_b": num(row.get("Total capital cost (2025 USD billions)"))},
               units={"power_mw": "MW", "capex_usd_b": "USD billions"},
               date=date, context=note[:300],
               documents=urls_in(row.get("Construction status") or ""),
               raw_ref=f"data_center_timelines.csv[{name}@{date}]")
        em.add("site_compute", subject_hint=name, subject_type="datacenter",
               claims={"h100e": num(row.get("H100 equivalents"))},
               units={"h100e": "chips"}, date=date,
               raw_ref=f"data_center_timelines.csv[{name}@{date}]")
    return em.records


def ingest_epoch_chips(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        site = clean(row["Data center"])
        chip = clean(row["Chip type"])
        units = num(row.get("Number of Units"))
        if not (site and chip and units):
            continue
        note = row.get("Notes") or ""
        em.add("chip_inventory", subject_hint=site, subject_type="datacenter",
               claims={"chip": chip, "units": units,
                       "owner": re.sub(r"#\w+", "", row.get("Owner") or "").strip(" ,") or None,
                       "user": re.sub(r"#\w+", "", row.get("User") or "").strip(" ,") or None},
               units={"units": "chips"}, date=(row.get("Date") or "")[:10],
               documents=[u for _, u in MD_LINK.findall(note)] + urls_in(note),
               context=MD_LINK.sub(r"\1", note)[:300],
               raw_ref=f"data_center_chip_quantities.csv[{row.get('Handle', '')[:60]}]")
    return em.records


# ---------------------------------------------------------------------------
# curated document sets
# ---------------------------------------------------------------------------
def ingest_curated_sites(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        docs = [u for u in (row.get("sources") or "").split("|") if u.startswith("http")]
        accel = [a.strip() for a in (row.get("accelerators") or "").split("|") if a.strip()]
        conf = clean(row.get("confidence")) or "estimate"
        conf = conf if conf in schema.CONFIDENCE else "estimate"
        em.add("site_profile", subject_hint=clean(row["name"]), subject_type="datacenter",
               claims={"operator": clean(row.get("operator")),
                       "tenant": clean(row.get("tenant")),
                       "status": clean(row.get("status")),
                       "city": clean(row.get("city")),
                       "region": clean(row.get("admin1")),
                       "country": clean(row.get("country")),
                       "lat": num(row.get("lat")), "lon": num(row.get("lon")),
                       "coord_precision": clean(row.get("coord_precision")),
                       "category": clean(row.get("category")),
                       "first_operational": num(row.get("year"))},
               confidence=conf, documents=docs,
               context=clean(row.get("notes")) or "",
               raw_ref=f"curated_sites.csv[{row['id']}]")
        em.add("site_capacity", subject_hint=clean(row["name"]), subject_type="datacenter",
               claims={"power_mw": num(row.get("power_mw_current")),
                       "power_mw_planned": num(row.get("power_mw_planned")),
                       "capex_usd_b": num(row.get("capex_usd_b"))},
               units={"power_mw": "MW", "power_mw_planned": "MW",
                      "capex_usd_b": "USD billions"},
               confidence=conf, documents=docs,
               raw_ref=f"curated_sites.csv[{row['id']}]")
        if accel or row.get("chip_detail"):
            em.add("site_compute", subject_hint=clean(row["name"]), subject_type="datacenter",
                   claims={"accelerator_families": accel or None,
                           "chip_detail": clean(row.get("chip_detail")),
                           "h100e": num(row.get("h100e_current")),
                           "h100e_planned": num(row.get("h100e_planned"))},
                   units={"h100e": "chips"}, confidence=conf, documents=docs,
                   raw_ref=f"curated_sites.csv[{row['id']}]")
    return em.records


def ingest_regions(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        name = f"{row['provider']} {row['region_id']}"
        em.add("region_availability", subject_hint=name, subject_type="cloud_region",
               claims={"provider": clean(row["provider"]),
                       "region_id": clean(row["region_id"]),
                       "label": clean(row.get("label")),
                       "city": clean(row.get("city")),
                       "country": clean(row.get("country")),
                       "lat": num(row.get("lat")), "lon": num(row.get("lon")),
                       "accelerators": [a.strip() for a in
                                        (row.get("accelerators") or "").split("|") if a.strip()],
                       "detail": clean(row.get("detail")),
                       "status": clean(row.get("status"))},
               documents=[u for u in (row.get("sources") or "").split("|")
                          if u.startswith("http")],
               context=clean(row.get("detail")) or "",
               raw_ref=f"accelerator_regions.csv[{row['provider']}:{row['region_id']}]")
    return em.records


# ---------------------------------------------------------------------------
# derived tables
# ---------------------------------------------------------------------------
def ingest_accelerators(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        em.add("chip_spec", subject_hint=clean(row["short_name"]), subject_type="accelerator",
               claims={"vendor": clean(row.get("vendor")),
                       "family": clean(row.get("family")),
                       "role": clean(row.get("role")),
                       "launch": clean(row.get("launch")),
                       "process": clean(row.get("process")),
                       "memory_gb": num(row.get("memory_gb")),
                       "memory_type": clean(row.get("memory_type")),
                       "memory_bw_tbs": num(row.get("mem_bw_tbs")),
                       "dense_bf16_tflops": num(row.get("fp16bf16_dense_tflops")),
                       "dense_fp8_tflops": num(row.get("fp8_dense_tflops")),
                       "dense_fp4_tflops": num(row.get("fp4_dense_tflops")),
                       "tdp_w": num(row.get("tdp_w")),
                       "scaleup_bw_gbs": num(row.get("scaleup_bw_gbs")),
                       "scaleup_domain": num(row.get("scaleup_domain_chips")),
                       "unit_price_usd": num(row.get("street_price_usd")),
                       "full_name": clean(row.get("name"))},
               units={"memory_gb": "GB", "memory_bw_tbs": "TB/s",
                      "dense_bf16_tflops": "TFLOP/s", "dense_fp8_tflops": "TFLOP/s",
                      "dense_fp4_tflops": "TFLOP/s", "tdp_w": "W",
                      "scaleup_bw_gbs": "GB/s", "scaleup_domain": "chips",
                      "unit_price_usd": "USD"},
               confidence="confirmed" if clean(row.get("price_confidence")) in
                          (None, "list", "confirmed") else "estimate",
               context=clean(row.get("notes")) or "",
               raw_ref=f"accelerators.csv[{row['short_name']}]")
    return em.records


def ingest_pricing(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        conf = clean(row.get("confidence")) or "estimate"
        em.add("chip_price", subject_hint=clean(row.get("spec_key")),
               subject_type="accelerator",
               claims={"provider": clean(row.get("provider")),
                       "tier": clean(row.get("tier")),
                       "usd_per_chip_hour": num(row.get("usd_per_chip_hour")),
                       "accelerator_label": clean(row.get("accelerator"))},
               units={"usd_per_chip_hour": "USD/hr"},
               date=clean(row.get("as_of")) or "",
               confidence=conf if conf in schema.CONFIDENCE else "estimate",
               context=clean(row.get("note")) or "",
               raw_ref=f"cloud_pricing.csv[{row.get('provider')}:{row.get('accelerator')}:{row.get('tier')}]")
    return em.records


def ingest_supply(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        conf = clean(row.get("confidence")) or "estimate"
        em.add("supply_metric", subject_hint=clean(row.get("item")), subject_type="",
               claims={"category": clean(row.get("category")),
                       "item": clean(row.get("item")),
                       "value": num(row.get("value")),
                       "unit": clean(row.get("unit"))},
               units={"value": clean(row.get("unit")) or ""},
               date=clean(row.get("year")) or "",
               confidence=conf if conf in schema.CONFIDENCE else "estimate",
               context=clean(row.get("note")) or "",
               raw_ref=f"supply_chain.csv[{row.get('category')}:{row.get('item')}:{row.get('year')}]")
    return em.records


def ingest_bom(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        em.add("cost_model", subject_hint=clean(row["chip"]), subject_type="accelerator",
               claims={"logic_die_usd": num(row.get("logic_die_usd")),
                       "hbm_usd": num(row.get("hbm_usd")),
                       "packaging_usd": num(row.get("packaging_usd")),
                       "other_usd": num(row.get("other_usd")),
                       "total_mfg_usd": num(row.get("total_mfg_usd")),
                       "modelled_sell_usd": num(row.get("modelled_sell_usd"))},
               units={k: "USD" for k in ("logic_die_usd", "hbm_usd", "packaging_usd",
                                         "other_usd", "total_mfg_usd", "modelled_sell_usd")},
               context=clean(row.get("note")) or "",
               raw_ref=f"bom_costs.csv[{row['chip']}]")
    return em.records


def ingest_mlperf(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        em.add("benchmark_result", subject_hint=clean(row.get("platform")),
               subject_type="accelerator",
               claims={"round": clean(row.get("round")),
                       "benchmark": clean(row.get("benchmark")),
                       "platform": clean(row.get("platform")),
                       "vendor": clean(row.get("vendor")),
                       "chips": num(row.get("chips")),
                       "minutes": num(row.get("minutes"))},
               units={"chips": "accelerators", "minutes": "minutes"},
               date=clean(row.get("round_date")) or "",
               confidence="confirmed",
               context=clean(row.get("note")) or "",
               raw_ref=f"mlperf_training.csv[{row.get('round')}:{row.get('benchmark')}:{row.get('platform')}]")
    return em.records


def ingest_racks(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        em.add("supply_metric", subject_hint=clean(row["system"]), subject_type="",
               claims={"system": clean(row["system"]),
                       "vendor": clean(row.get("vendor")),
                       "chip_type": clean(row.get("chip_type")),
                       "chips": num(row.get("chips")),
                       "hbm_tb": num(row.get("hbm_tb")),
                       "scaleup_bw_tbs": num(row.get("scaleup_bw_tbs")),
                       "power_kw": num(row.get("power_kw")),
                       "price_usd": num(row.get("price_usd"))},
               units={"chips": "accelerators", "hbm_tb": "TB",
                      "scaleup_bw_tbs": "TB/s", "power_kw": "kW", "price_usd": "USD"},
               confidence=clean(row.get("confidence")) if clean(row.get("confidence"))
                          in schema.CONFIDENCE else "estimate",
               context=clean(row.get("note")) or "",
               raw_ref=f"rack_systems.csv[{row['system']}]")
    return em.records


def ingest_runs(source: dict) -> list[dict]:
    em = Emitter(source)
    for row in csv.DictReader((ROOT / source["local_path"]).open()):
        em.add("training_run", subject_hint=clean(row.get("hardware")),
               subject_type="accelerator",
               claims={"model": clean(row.get("model")), "org": clean(row.get("org")),
                       "params_b": num(row.get("params_b")),
                       "tokens_t": num(row.get("tokens_t")),
                       "training_flops": clean(row.get("training_flops")),
                       "hardware": clean(row.get("hardware")),
                       "chip_count": num(row.get("chip_count")),
                       "chip_hours_m": num(row.get("chip_hours_m")),
                       "mfu": num(row.get("mfu"))},
               units={"params_b": "billions", "tokens_t": "trillions",
                      "chip_hours_m": "million chip-hours"},
               date=clean(row.get("year")) or "",
               confidence=clean(row.get("confidence")) if clean(row.get("confidence"))
                          in schema.CONFIDENCE else "estimate",
               context=clean(row.get("note")) or "",
               raw_ref=f"training_runs.csv[{row.get('model')}]")
    return em.records


def ingest_compute_map_identity(source: dict) -> list[dict]:
    """The identity prior: canonical sites with the merge decisions already made
    by scripts/build_compute_map.py, so geographic dedup is solved once."""
    em = Emitter(source)
    payload = json.loads((ROOT / source["local_path"]).read_text())

    # the map resolves country geography once; carry it as its own records so
    # country entities get their ISO code and continent from a source, not a guess
    for country in payload.get("countries", []):
        em.add("geo_profile", subject_hint=country["name"], subject_type="country",
               claims={"iso3": country.get("iso3"),
                       "continent": country.get("continent"),
                       "country": country["name"]},
               context=f"{country.get('sites', 0)} sites in the map",
               raw_ref=f"compute-map/data.json[countries.{country.get('iso3')}]")

    for site in payload["sites"]:
        is_region = site["layer"] == "cloud_region"
        em.add("site_profile",
               subject_hint=site["name"],
               subject_type="cloud_region" if is_region else "datacenter",
               claims={"canonical_name": site["name"],
                       "map_id": site["id"],
                       "operator": site.get("operator"),
                       "aliases": site.get("aka") or None,
                       "lat": site.get("lat"), "lon": site.get("lon"),
                       "coord_precision": site.get("coord_precision"),
                       "country": site.get("country"),
                       "continent": site.get("continent"),
                       # some upstream records put a street address in the city
                       # field; an address is not a locality, so it travels as
                       # context instead of pretending to be one
                       "city": (site.get("city")
                                if not str(site.get("city") or "")[:1].isdigit() else None),
                       "address": (site.get("city")
                                   if str(site.get("city") or "")[:1].isdigit() else None),
                       "region": site.get("admin1"),
                       "merged_from": [r["name"] for r in site.get("records", [])] or None},
               documents=[s["url"] for s in site.get("sources", [])],
               context=f"merged from {len(site.get('records', []))} source record(s)",
               raw_ref=f"compute-map/data.json[{site['id']}]")
    return em.records


def ingest_manual_facts(source: dict) -> list[dict]:
    """Curated attributes that no ingested dataset here carries. The subject is
    already a canonical entity id, so these records skip resolution."""
    from .catalog import MANUAL_FACTS
    em = Emitter(source)
    for entity_id, facts in MANUAL_FACTS.items():
        etype = entity_id.split(":", 1)[0]
        etype = {"company": "company", "component": "component"}.get(etype, etype)
        em.add("citation", subject_hint=entity_id.split(":", 1)[1],
               subject_type=etype, subject_id=entity_id, claims=dict(facts),
               context="hand-entered attribute", raw_ref="catalog.MANUAL_FACTS")
    return em.records


ADAPTERS = {name: fn for name, fn in list(globals().items()) if name.startswith("ingest_")}


def run(source: dict) -> list[dict]:
    fn = ADAPTERS.get(source["adapter"])
    if not fn:
        raise KeyError(f"no adapter named {source['adapter']}")
    return fn(source)
