#!/usr/bin/env python3
"""Build the entity atlas: entities, relations, and per-source entity recognition.

Reads the datasets this repo already carries and produces
`docs/entity-atlas/data.json`, which powers two views:

  * an entity-relation grid (categories as cards, relations as curves)
  * a source search view (pick entities, get every source that mentions them)

The interesting part is the recognition pass. Every source URL is examined four
ways, and each hit records *how* the entity was found so the UI can show its
working:

  record   the URL was attached to a record whose fields name entities
           (a data center's operator, tenant, country, installed chips)
  domain   the URL's host belongs to an entity we track (nvidia.com -> NVIDIA)
  path     an entity alias appears in the URL path (/gb200-nvl72/)
  context  an entity alias appears in the text that travelled with the URL
           (record name, Epoch observation note, region description)

Sources are deduplicated by normalised URL, so one link cited by three datasets
becomes one source with three provenance entries.

    python3 scripts/build_entity_atlas.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import unicodedata
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAP_JSON = ROOT / "docs" / "compute-map" / "data.json"
DATA = ROOT / "data"
OUT = ROOT / "docs" / "entity-atlas" / "data.json"
AS_OF = "2026-08-20"

# --------------------------------------------------------------------------
# entity types, in the order the grid lays them out
# --------------------------------------------------------------------------
TYPES = {
    "company":   {"label": "Company / operator", "color": "#4fc3ff"},
    "chip":      {"label": "Accelerator",        "color": "#ffb648"},
    "site":      {"label": "Data center",        "color": "#b085ff"},
    "region":    {"label": "Cloud region",       "color": "#3fe0a0"},
    "component": {"label": "Supply chain",       "color": "#ff6fb5"},
    "country":   {"label": "Country",            "color": "#8ea0bd"},
}

# Canonical companies with the aliases that actually appear in our sources and
# records. Aliases are matched case-insensitively on word boundaries.
COMPANIES = {
    "nvidia": ("NVIDIA", ["nvidia", "nvda"], ["nvidia.com", "developer.nvidia.com",
                                              "blogs.nvidia.com", "nvidianews.nvidia.com",
                                              "investor.nvidia.com", "resources.nvidia.com",
                                              "images.nvidia.com", "docs.nvidia.com"]),
    "amd": ("AMD", ["amd", "instinct"], ["amd.com", "rocm.blogs.amd.com", "docs.amd.com"]),
    "intel": ("Intel", ["intel", "gaudi", "habana"], ["intel.com", "newsroom.intel.com",
                                                      "docs.habana.ai"]),
    "google": ("Google", ["google", "google cloud", "gcp", "alphabet", "deepmind"],
               ["google.com", "cloud.google.com", "blog.google", "docs.cloud.google.com",
                "datacenters.google", "sustainability.google", "googlecloudpresscorner.com",
                "discuss.google.dev", "storage.googleapis.com"]),
    "microsoft": ("Microsoft", ["microsoft", "azure", "msft"],
                  ["microsoft.com", "blogs.microsoft.com", "azure.microsoft.com",
                   "prices.azure.com", "techcommunity.microsoft.com", "news.microsoft.com"]),
    "amazon": ("Amazon / AWS", ["amazon", "aws", "amazon web services"],
               ["aws.amazon.com", "aboutamazon.com", "awsdocs-neuron.readthedocs-hosted.com",
                "repost.aws", "press.aboutamazon.com", "instances.vantage.sh"]),
    "meta": ("Meta", ["meta", "facebook", "mtia"],
             ["ai.meta.com", "datacenters.atmeta.com", "about.fb.com", "engineering.fb.com",
              "facebook.com"]),
    "openai": ("OpenAI", ["openai", "stargate"], ["openai.com"]),
    "anthropic": ("Anthropic", ["anthropic", "claude"], ["anthropic.com"]),
    "xai": ("xAI", ["xai", "x.ai", "colossus", "spacexai", "macrohard"], ["x.ai"]),
    "oracle": ("Oracle", ["oracle", "oci"], ["oracle.com", "blogs.oracle.com",
                                             "docs.oracle.com"]),
    "coreweave": ("CoreWeave", ["coreweave"], ["coreweave.com", "docs.coreweave.com",
                                               "wf.coreweave.com"]),
    "crusoe": ("Crusoe", ["crusoe"], ["crusoe.ai", "crusoeenergy.com"]),
    "tsmc": ("TSMC", ["tsmc", "cowos"], ["tsmc.com"]),
    "broadcom": ("Broadcom", ["broadcom", "avgo"], ["broadcom.com", "investors.broadcom.com"]),
    "sk_hynix": ("SK hynix", ["sk hynix", "hynix"], ["skhynix.com"]),
    "samsung": ("Samsung", ["samsung"], ["samsung.com", "news.samsung.com"]),
    "micron": ("Micron", ["micron"], ["micron.com"]),
    "huawei": ("Huawei", ["huawei", "ascend", "cloudmatrix"], ["huawei.com"]),
    "cerebras": ("Cerebras", ["cerebras", "wse"], ["cerebras.ai", "cerebras.net"]),
    "groq": ("Groq", ["groq"], ["groq.com", "groq.humain.ai"]),
    "sambanova": ("SambaNova", ["sambanova"], ["sambanova.ai"]),
    "tenstorrent": ("Tenstorrent", ["tenstorrent"], ["tenstorrent.com", "docs.tenstorrent.com"]),
    "nscale": ("Nscale", ["nscale"], ["nscale.com"]),
    "nebius": ("Nebius", ["nebius"], ["nebius.com", "docs.nebius.com"]),
    "lambda": ("Lambda", ["lambda labs", "lambda ai"], ["lambda.ai", "lambdalabs.com"]),
    "firmus": ("Firmus", ["firmus", "sustainable metal cloud"], ["firmus.co"]),
    "terawulf": ("TeraWulf", ["terawulf", "lake mariner"], ["terawulf.com",
                                                            "investors.terawulf.com"]),
    "cipher": ("Cipher Mining", ["cipher mining", "barber lake"], ["ciphermining.com"]),
    "fluidstack": ("Fluidstack", ["fluidstack"], ["fluidstack.io"]),
    "vantage": ("Vantage Data Centers", ["vantage"], ["vantage-dc.com"]),
    "qts": ("QTS", ["qts"], ["qtsdatacenters.com", "q.com"]),
    "equinix": ("Equinix", ["equinix"], ["equinix.com"]),
    "digital_realty": ("Digital Realty", ["digital realty"], ["digitalrealty.com"]),
    "stack": ("STACK Infrastructure", ["stack infrastructure"], ["stackinfra.com"]),
    "dayone": ("DayOne / GDS", ["dayone", "gds holdings"], ["dayonedc.com"]),
    "ytl": ("YTL", ["ytl"], ["ytl.com"]),
    "g42": ("G42", ["g42", "khazna", "core42"], ["g42.ai", "khaznadatacenters.com"]),
    "humain": ("Humain", ["humain"], ["humain.ai"]),
    "softbank": ("SoftBank", ["softbank", "sb energy"], ["softbank.jp", "sbenergy.com"]),
    "kddi": ("KDDI", ["kddi"], ["kddi.com", "newsroom.kddi.com"]),
    "naver": ("NAVER", ["naver"], ["navercorp.com"]),
    "foxconn": ("Foxconn", ["foxconn", "hon hai"], ["foxconn.com"]),
    "scala": ("Scala Data Centers", ["scala data"], ["scaladatacenters.com"]),
    "cassava": ("Cassava", ["cassava"], ["cassavatechnologies.com"]),
    "bell": ("Bell Canada", ["bell ai fabric", "bell canada"], ["bce.ca", "bell.ca"]),
    "telus": ("Telus", ["telus"], ["telus.com"]),
    "yotta": ("Yotta", ["yotta"], ["yotta.com"]),
    "reliance": ("Reliance", ["reliance industries", "reliance jio"], ["ril.com"]),
    "eurohpc": ("EuroHPC", ["eurohpc", "jupiter", "lumi", "leonardo", "marenostrum"],
                ["eurohpc-ju.europa.eu", "fz-juelich.de"]),
    "mistral": ("Mistral AI", ["mistral"], ["mistral.ai"]),
    "eclairion": ("Eclairion", ["eclairion"], ["eclairion.com"]),
    "vnet": ("VNET", ["vnet", "21vianet"], ["vnet.com"]),
    "alibaba": ("Alibaba", ["alibaba"], ["alibabacloud.com"]),
    "bytedance": ("ByteDance", ["bytedance", "tiktok"], ["bytedance.com"]),
    "tencent": ("Tencent", ["tencent"], ["tencent.com", "cloud.tencent.com"]),
    "epoch": ("Epoch AI", ["epoch ai"], ["epoch.ai"]),
    "mlcommons": ("MLCommons", ["mlcommons", "mlperf"], ["mlcommons.org"]),
    "semianalysis": ("SemiAnalysis", ["semianalysis"], ["semianalysis.com",
                                                        "newsletter.semianalysis.com"]),
    "trendforce": ("TrendForce", ["trendforce"], ["trendforce.com"]),
    "peeringdb": ("PeeringDB", ["peeringdb"], ["peeringdb.com"]),
}

COMPONENTS = {
    "hbm3e": ("HBM3E", ["hbm3e", "hbm3"]),
    "hbm4": ("HBM4", ["hbm4"]),
    "cowos": ("CoWoS packaging", ["cowos", "advanced packaging", "interposer"]),
    "nvlink": ("NVLink / NVSwitch", ["nvlink", "nvswitch", "nvl72"]),
    "infiniband": ("InfiniBand", ["infiniband", "quantum-x", "quantum x800"]),
    "ethernet_ai": ("AI Ethernet", ["spectrum-x", "ultra ethernet", "ualink", "roce"]),
    "liquid_cooling": ("Liquid cooling", ["liquid cool", "direct-to-chip", "immersion cool"]),
    "gas_turbine": ("On-site generation", ["gas turbine", "microgrid", "fuel cell",
                                           "on-site gas"]),
    "grid": ("Grid interconnect", ["interconnect queue", "substation", "transformer",
                                   "ercot", "oncor", "tva", "saskpower"]),
    "optical": ("Optical switching", ["optical circuit switch", "ocs", "co-packaged optics"]),
}

# publishers that are media/registry rather than an entity we model
PUBLISHER_LABELS = {
    "datacenterdynamics.com": "DataCenterDynamics",
    "datacenterfrontier.com": "Data Center Frontier",
    "datacenterknowledge.com": "Data Center Knowledge",
    "datacenters.com": "DataCenters.com",
    "datacentermap.com": "Data Center Map",
    "baxtel.com": "Baxtel",
    "ocolo.io": "oColo",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "wsj.com": "Wall Street Journal",
    "ft.com": "Financial Times",
    "nytimes.com": "New York Times",
    "theinformation.com": "The Information",
    "tomshardware.com": "Tom's Hardware",
    "theregister.com": "The Register",
    "arxiv.org": "arXiv",
    "sec.gov": "SEC EDGAR",
    "comptroller.texas.gov": "Texas Comptroller",
    "tdlr.texas.gov": "Texas TDLR",
    "chipsandcheese.com": "Chips and Cheese",
    "servethehome.com": "ServeTheHome",
    "hpcwire.com": "HPCwire",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "businesswire.com": "Business Wire",
    "prnewswire.com": "PR Newswire",
    "globenewswire.com": "GlobeNewswire",
}

# File lockers, archives and social hosts: the domain says nothing about which
# company the document is about, so they must not produce a `domain` hit.
GENERIC_HOSTS = {
    "drive.google.com": "Google Drive (scan)",
    "docs.google.com": "Google Docs (scan)",
    "storage.googleapis.com": "Google Storage (file)",
    "web.archive.org": "Internet Archive",
    "archive.org": "Internet Archive",
    "x.com": "X / Twitter",
    "twitter.com": "X / Twitter",
    "youtube.com": "YouTube",
    "linkedin.com": "LinkedIn",
    "scribd.com": "Scribd",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "wikipedia.org": "Wikipedia",
    "baidu.com": "Baidu",
    "baike.baidu.com": "Baidu Baike",
}

KIND_BY_DOMAIN_HINT = [
    (("sec.gov", "investors.", "investor."), "filing"),
    (("arxiv.org", "jmlr.org", "dl.acm.org", "doi.org", "proceedings."), "paper"),
    (("peeringdb.com", "datacenters.com", "datacentermap.com", "baxtel.com", "ocolo.io",
      "databank.com"), "registry"),
    ((".gov", "europa.eu", "eurohpc"), "government"),
    (("prices.azure.com", "instances.vantage.sh", "cloud.google.com/tpu/pricing"), "pricing"),
    (("epoch.ai",), "dataset"),
]
VENDOR_DOMAIN_KINDS = "vendor"
MEDIA_KIND = "news"


MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


# Aliases that would fire on almost any page and are never evidence by
# themselves. "meta" appears in meta-descriptions, "oci" in unrelated paths.
STOP_ALIASES = {"meta", "oci", "gcp", "aws", "amd", "arm", "hbm", "dc", "ai",
                "gds holdings", "x.ai", "q.com"}


def norm(text: str | None) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


TITLE_JUNK = re.compile(r"\.(html?|php|aspx?|pdf|csv|json|xml)$", re.I)
ACRONYMS = {"ai", "gpu", "tpu", "hbm", "cowos", "nvl72", "mw", "gw", "us", "uk", "uae",
            "hpc", "llm", "sec", "eu", "b200", "b300", "h100", "h200", "gb200", "gb300",
            "mi300x", "mi355x", "trn1", "trn2", "iso", "pue", "ercot", "tva", "qts"}


def title_from_url(url: str) -> str:
    """A readable headline from the URL itself. Sources in our datasets are bare
    links, so this is what a search result can honestly show."""
    path = re.sub(r"^https://[^/]+", "", url).strip("/")
    if not path:
        return ""
    parts = [p for p in path.split("/") if p]
    # walk back to the last segment that looks like prose rather than an id
    for seg in reversed(parts):
        seg = TITLE_JUNK.sub("", seg)
        words = [w for w in re.split(r"[-_+]", seg) if w]
        alpha = [w for w in words if re.search(r"[a-z]{3}", w, re.I)]
        if len(alpha) >= 3 or (len(alpha) >= 2 and len(seg) > 14):
            out = []
            for w in words:
                lw = w.lower()
                if lw in ACRONYMS:
                    out.append(lw.upper())
                elif re.fullmatch(r"\d{4,}", w):
                    continue
                else:
                    out.append(w.capitalize() if w.islower() else w)
            text = " ".join(out).strip()
            if len(text) > 4:
                return text[:120]
    return ""


def display_name(name: str) -> str:
    """dataCenterView holds some records in caps ("ORACLE DATA CENTER"); title
    them for display while leaving acronyms and part numbers alone."""
    if not name or not name.isupper() or len(name) < 5:
        return name
    keep = {"DC", "AI", "US", "UK", "TPU", "GPU", "HPC", "IT", "NVL72", "LLC", "INC"}
    return " ".join(w if (w in keep or any(c.isdigit() for c in w)) else w.capitalize()
                    for w in name.split())


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return re.sub(r"^www\.", "", m.group(1).lower()) if m else ""


def canonical_url(url: str) -> str:
    u = (url or "").strip().rstrip("/.,)")
    u = re.sub(r"^http://", "https://", u)
    u = re.sub(r"^https://www\.", "https://", u)
    u = re.sub(r"[?#].*$", "", u)
    return u


def num(v, default=None):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# entity registry
# --------------------------------------------------------------------------
class Registry:
    def __init__(self):
        self.entities: dict[str, dict] = {}
        self.alias_index: list[tuple[str, str]] = []   # (alias, entity id), long first
        self.domain_index: dict[str, str] = {}
        self.alias_map: dict[str, str] = {}
        self.max_ngram = 1
        self._cache: dict[str, list] = {}

    def add(self, eid, name, etype, aliases=(), domains=(), **extra):
        e = self.entities.get(eid)
        if not e:
            e = {"id": eid, "name": name, "type": etype, "aliases": set(),
                 "domains": set(), "sources": set(), "relations": [], "metrics": [],
                 "summary": "", "weight": 0.0}
            self.entities[eid] = e
        e.update({k: v for k, v in extra.items() if v not in (None, "", [])})
        e["aliases"].update({norm(a) for a in [name, *aliases] if a})
        e["domains"].update(d.lower() for d in domains)
        return e

    def finalise_index(self):
        """Index aliases by word count so matching is a dictionary lookup over
        the text's n-grams rather than a regex scan over ~900 aliases."""
        self.alias_map = {}
        self.max_ngram = 1
        for e in self.entities.values():
            for a in e["aliases"]:
                if len(a) < 3 or a in STOP_ALIASES:
                    continue
                n = len(a.split())
                self.max_ngram = max(self.max_ngram, n)
                # first writer wins, but a longer alias for the same entity is fine
                self.alias_map.setdefault(a, e["id"])
            for d in e["domains"]:
                self.domain_index[d] = e["id"]
        self.max_ngram = min(self.max_ngram, 5)
        self.alias_index = sorted(self.alias_map.items(), key=lambda kv: -len(kv[0]))
        self._cache = {}

    def match_text(self, text: str) -> list[tuple[str, str]]:
        """Return (entity id, matched span) for aliases found in text. Longer
        aliases win, and each entity is reported once."""
        t = norm(text)
        if not t:
            return []
        cached = self._cache.get(t)
        if cached is not None:
            return cached
        tokens = re.findall(r"[a-z0-9.]+", t)
        hits, seen, consumed = [], set(), set()
        for n in range(self.max_ngram, 0, -1):
            for i in range(len(tokens) - n + 1):
                if any((i + k) in consumed for k in range(n)):
                    continue
                gram = " ".join(tokens[i:i + n])
                eid = self.alias_map.get(gram)
                if eid and eid not in seen:
                    hits.append((eid, gram))
                    seen.add(eid)
                    consumed.update(range(i, i + n))
        if len(self._cache) < 60000:
            self._cache[t] = hits
        return hits

    def match_host(self, host: str) -> str | None:
        if not host:
            return None
        if host in self.domain_index:
            return self.domain_index[host]
        for d, eid in self.domain_index.items():
            if host == d or host.endswith("." + d):
                return eid
        return None


REG = Registry()


# --------------------------------------------------------------------------
# load our datasets
# --------------------------------------------------------------------------
def load():
    map_data = json.loads(MAP_JSON.read_text())
    accel = list(csv.DictReader((DATA / "accelerators.csv").open()))
    pricing = list(csv.DictReader((DATA / "cloud_pricing.csv").open()))
    supply = list(csv.DictReader((DATA / "supply_chain.csv").open()))
    racks = list(csv.DictReader((DATA / "rack_systems.csv").open()))
    mlperf = list(csv.DictReader((DATA / "mlperf_training.csv").open()))
    runs = list(csv.DictReader((DATA / "training_runs.csv").open()))
    regions = list(csv.DictReader((DATA / "compute_map" / "accelerator_regions.csv").open()))
    return map_data, accel, pricing, supply, racks, mlperf, runs, regions


def register_entities(map_data, accel, pricing, supply, racks, regions):
    # --- companies ---
    for eid, (name, aliases, domains) in COMPANIES.items():
        REG.add(eid, name, "company", aliases, domains)

    # --- components ---
    for eid, (name, aliases) in COMPONENTS.items():
        REG.add(eid, name, "component", aliases)

    # --- accelerators ---
    vendor_ids = {"NVIDIA": "nvidia", "AMD": "amd", "Intel": "intel", "Google": "google",
                  "AWS": "amazon", "Meta": "meta", "Microsoft": "microsoft",
                  "Huawei": "huawei", "Cerebras": "cerebras", "Groq": "groq",
                  "SambaNova": "sambanova", "Tenstorrent": "tenstorrent"}
    for a in accel:
        eid = "chip:" + slug(a["short_name"])
        aliases = [a["short_name"], a["name"]]
        # tolerate the ways the same part gets written
        base = a["short_name"]
        if base.startswith("TPU "):
            aliases += [base.replace("TPU ", "tpu"), base.replace("TPU ", "")]
        aliases = [x for x in aliases if x]
        e = REG.add(eid, a["short_name"], "chip", aliases,
                    summary=(a.get("notes") or "").strip(),
                    metrics=[m for m in [
                        ["Vendor", a["vendor"]],
                        ["Launch", a.get("launch") or ""],
                        ["Memory", f"{a['memory_gb']} GB {a['memory_type']}"
                         if a.get("memory_gb") else ""],
                        ["Dense BF16", f"{num(a.get('fp16bf16_dense_tflops'), 0):,.0f} TFLOP/s"
                         if num(a.get("fp16bf16_dense_tflops")) else ""],
                        ["Dense FP8", f"{num(a.get('fp8_dense_tflops'), 0):,.0f} TFLOP/s"
                         if num(a.get("fp8_dense_tflops")) else ""],
                        ["Scale-up domain", f"{num(a.get('scaleup_domain_chips'), 0):,.0f} chips"
                         if num(a.get("scaleup_domain_chips")) else ""],
                    ] if m[1]])
        e["vendor"] = a["vendor"]
        e["weight"] = 3.0
        v = vendor_ids.get(a["vendor"])
        if v:
            add_relation(v, eid, "designs", 1.0, "data/accelerators.csv")

    REG.finalise_index()   # companies + components + chips are the matcher vocabulary

    # --- sites and countries ---
    for s in map_data["sites"]:
        if s["layer"] == "cloud_region":
            continue
        eid = "site:" + s["id"]
        aliases = [s["name"], *s.get("aka", [])]
        power = s.get("power_mw_planned") or s.get("power_mw") or 0
        e = REG.add(eid, s["name"], "site", aliases,
                    summary=(s.get("notes") or "")[:280],
                    metrics=[m for m in [
                        ["Operator", s.get("operator") or ""],
                        ["Tenant", s.get("tenant") or ""],
                        ["Status", (s.get("status") or "").replace("_", " ")],
                        ["Power now", f"{s['power_mw']:,.0f} MW" if s.get("power_mw") else ""],
                        ["Power planned", f"{s['power_mw_planned']:,.0f} MW"
                         if s.get("power_mw_planned") else ""],
                        ["H100e installed", f"{s['h100e']:,.0f}" if s.get("h100e") else ""],
                        ["Location", ", ".join(filter(None, [s.get("city"), s.get("admin1"),
                                                             s.get("country")]))],
                    ] if m[1]])
        e["weight"] = 1.0 + min(6.0, power / 250.0)
        e["status"] = s.get("status")
        e["map_id"] = s["id"]
        e["country"] = s.get("country")

        if s.get("country"):
            cid = "country:" + slug(s["country"])
            REG.add(cid, s["country"], "country", [s["country"]])
            REG.entities[cid]["weight"] = REG.entities[cid].get("weight", 0) + 0.5
            add_relation(eid, cid, "located in", 1.0, "compute map")

        for field, verb in (("operator", "operates"), ("tenant", "tenant of")):
            raw = s.get(field) or ""
            for company in match_company_string(raw):
                add_relation(company, eid, verb, 1.0, "compute map")
        for fam in (s.get("chip_families") or {}):
            for chip in chips_for_family_at_site(s, fam):
                add_relation(eid, chip, "deploys", 1.0, "Epoch chip table")

    # --- cloud regions ---
    for r in regions:
        eid = "region:" + slug(f"{r['provider']}-{r['region_id']}")
        e = REG.add(eid, f"{r['provider']} {r['region_id']}", "region",
                    [r["region_id"], f"{r['provider']} {r['region_id']}"],
                    summary=r.get("detail") or "",
                    metrics=[["Provider", r["provider"]], ["Location", f"{r['city']}, {r['country']}"],
                             ["Accelerators", r["accelerators"]]])
        e["weight"] = 2.0
        for company in match_company_string(r["provider"]):
            add_relation(company, eid, "operates region", 1.0, "provider documentation")
        cid = "country:" + slug(r["country"])
        REG.add(cid, r["country"], "country", [r["country"]])
        add_relation(eid, cid, "located in", 1.0, "provider documentation")
        for chip in REG.match_text(r["detail"]):
            if REG.entities[chip[0]]["type"] == "chip":
                add_relation(chip[0], eid, "rentable in", 1.0, "provider documentation")

    # --- supply chain relations from our own datasets ---
    for row in supply:
        if row["category"] == "hbm_share":
            for company in match_company_string(row["item"]):
                target = "hbm4" if row["year"] == "2026" else "hbm3e"
                add_relation(company, target, "supplies", 2.0, "data/supply_chain.csv")
    for row in csv.DictReader((DATA / "bom_costs.csv").open()):
        for eid, _ in REG.match_text(row["chip"]):
            if REG.entities[eid]["type"] == "chip":
                add_relation(eid, "hbm3e", "consumes", 1.5, "data/bom_costs.csv")
                add_relation(eid, "cowos", "consumes", 1.5, "data/bom_costs.csv")
    for r in racks:
        for eid, _ in REG.match_text(r["chip_type"]):
            if REG.entities[eid]["type"] == "chip":
                add_relation(eid, "nvlink" if "NVL" in r["system"] else "ethernet_ai",
                             "fabric", 1.0, "data/rack_systems.csv")
    for p in pricing:
        for company in match_company_string(p["provider"]):
            for eid, _ in REG.match_text(p["spec_key"]):
                if REG.entities[eid]["type"] == "chip":
                    add_relation(company, eid, "rents out", 1.0, "data/cloud_pricing.csv")


RELATIONS: dict[tuple[str, str, str], dict] = {}


def add_relation(a: str, b: str, verb: str, weight: float, evidence: str):
    if not a or not b or a == b:
        return
    key = (a, b, verb)
    rel = RELATIONS.get(key)
    if not rel:
        rel = {"a": a, "b": b, "verb": verb, "weight": 0.0, "evidence": set()}
        RELATIONS[key] = rel
    rel["weight"] += weight
    rel["evidence"].add(evidence)


COMPANY_STRING_CACHE: dict[str, list[str]] = {}


def match_company_string(raw: str) -> list[str]:
    """Map an operator/tenant string such as 'Microsoft Azure' or
    'Cipher Mining + Fluidstack' onto canonical company entities."""
    if not raw:
        return []
    if raw in COMPANY_STRING_CACHE:
        return COMPANY_STRING_CACHE[raw]
    hits = [eid for eid, _ in REG.match_text(raw)
            if REG.entities[eid]["type"] == "company"]
    COMPANY_STRING_CACHE[raw] = hits
    return hits


CHIP_BY_FAMILY_CACHE: dict[str, list[str]] = {}


def chips_for_family_at_site(site: dict, family: str) -> list[str]:
    """A site's chip_families are aggregated ('Google TPU'); the underlying
    chips list gives the actual parts, so map those onto chip entities."""
    out = []
    for chip_name in list(site.get("chips") or {}) + list(site.get("chips_planned") or {}):
        for eid, _ in REG.match_text(chip_name):
            if REG.entities[eid]["type"] == "chip":
                out.append(eid)
    return sorted(set(out))


# --------------------------------------------------------------------------
# source collection + recognition
# --------------------------------------------------------------------------
SOURCES: dict[str, dict] = {}


def classify(url: str, host: str, publisher_entity: str | None) -> str:
    low = url.lower()
    for hints, kind in KIND_BY_DOMAIN_HINT:
        if any(h in low for h in hints):
            return kind
    if publisher_entity:
        return VENDOR_DOMAIN_KINDS
    return MEDIA_KIND


def add_source(url: str, *, dataset: str, context: str = "", record: dict | None = None,
               record_entities: list[str] | None = None, title: str = "", date: str = ""):
    cu = canonical_url(url)
    if not cu.startswith("https://"):
        return None
    host = host_of(cu)
    src = SOURCES.get(cu)
    if not src:
        pub_eid = None if host in GENERIC_HOSTS else REG.match_host(host)
        src = {
            "id": "src-%06d" % (len(SOURCES) + 1),
            "url": cu,
            "host": host,
            "publisher": (GENERIC_HOSTS.get(host) or PUBLISHER_LABELS.get(host)
                          or (REG.entities[pub_eid]["name"] if pub_eid else host)),
            "publisher_entity": pub_eid,
            "kind": classify(cu, host, pub_eid),
            "title": title_from_url(cu),
            "attached_to": [],
            "date": date,
            "datasets": set(),
            "contexts": [],
            "records": [],
            "recognition": {},     # entity id -> {methods: {method: span}, score}
        }
        SOURCES[cu] = src
    src["datasets"].add(dataset)
    if title and title not in src["attached_to"]:
        src["attached_to"].append(title)
    if not src["title"]:
        src["title"] = title
    if date and not src["date"]:
        src["date"] = date
    if context and context not in src["contexts"]:
        src["contexts"].append(context[:400])
    if record:
        keep = {k: v for k, v in record.items() if v not in (None, "", [])}
        if keep not in src["records"]:
            src["records"].append(keep)

    def note(eid: str, method: str, span: str, score: float):
        rec = src["recognition"].setdefault(eid, {"methods": {}, "score": 0.0})
        if method not in rec["methods"]:
            rec["methods"][method] = span
            rec["score"] += score

    # 1) publisher domain
    if src["publisher_entity"]:
        note(src["publisher_entity"], "domain", host, 1.0)
    # 2) URL path aliases
    path = re.sub(r"^https://[^/]+", "", cu)
    if path:
        readable = re.sub(r"[-_/]+", " ", path)
        for eid, span in REG.match_text(readable):
            note(eid, "path", span, 0.9)
    # 3) entities named by the attached record
    for eid in (record_entities or []):
        if eid in REG.entities:
            note(eid, "record", REG.entities[eid]["name"], 1.2)
    # 4) aliases in the travelling text
    for text in filter(None, [title, context]):
        for eid, span in REG.match_text(text):
            note(eid, "context", span, 0.7)
    return src


REGION_BY_NAME: dict[str, str] = {}


def collect_sources(map_data, accel, pricing, regions, mlperf, runs):
    for e in REG.entities.values():
        if e["type"] == "region":
            REGION_BY_NAME[norm(e["name"])] = e["id"]
    # --- from the compute map: sites and regions carry real source URLs ---
    by_map_id = {s["id"]: s for s in map_data["sites"]}
    for s in map_data["sites"]:
        is_region = s["layer"] == "cloud_region"
        ent_id = REGION_BY_NAME.get(norm(s["name"])) if is_region else "site:" + s["id"]
        entities = []
        if ent_id and ent_id in REG.entities:
            entities.append(ent_id)
        entities += match_company_string(s.get("operator") or "")
        entities += match_company_string(s.get("tenant") or "")
        if s.get("country"):
            cid = "country:" + slug(s["country"])
            if cid in REG.entities:
                entities.append(cid)
        entities += chips_for_family_at_site(s, "")
        context = " · ".join(filter(None, [
            s["name"], s.get("operator"), s.get("tenant"), s.get("chip_detail"),
            ", ".join(filter(None, [s.get("city"), s.get("admin1"), s.get("country")])),
            (s.get("notes") or "")[:200],
        ]))
        record = {"dataset record": s["name"], "operator": s.get("operator"),
                  "tenant": s.get("tenant"), "status": s.get("status"),
                  "power_mw_planned": s.get("power_mw_planned"),
                  "country": s.get("country")}
        for src in s["sources"]:
            add_source(src["url"], dataset=src["dataset"], context=context,
                       record=record, record_entities=entities, title=s["name"])

    # --- our own derived datasets are sources too ---
    internal = [
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/accelerators.csv",
         "data/accelerators.csv", "dataset",
         "Per-accelerator specification table: 49 chips from 12 vendors with dense throughput, "
         "memory, fabric and pricing.",
         [e["id"] for e in REG.entities.values() if e["type"] == "chip"]),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/cloud_pricing.csv",
         "data/cloud_pricing.csv", "pricing",
         "59 cloud offers across 12 providers and 9 pricing tiers, per chip-hour.",
         sorted({c for p in pricing for c in match_company_string(p["provider"])})),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/supply_chain.csv",
         "data/supply_chain.csv", "dataset",
         "CoWoS capacity, HBM share and pricing, unit-shipment estimates and rack power.",
         ["cowos", "hbm3e", "hbm4", "tsmc", "sk_hynix", "samsung", "micron"]),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/mlperf_training.csv",
         "data/mlperf_training.csv", "dataset",
         "MLPerf Training v4.0 through v6.0 results by benchmark, platform and scale.",
         ["mlcommons"] + sorted({e for m in mlperf for e, _ in REG.match_text(m["platform"])
                                 if REG.entities[e]["type"] == "chip"})),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/bom_costs.csv",
         "data/bom_costs.csv", "dataset",
         "Modelled bill of materials for six accelerators: die, HBM, packaging, assembly.",
         ["hbm3e", "cowos", "tsmc"]),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/training_runs.csv",
         "data/training_runs.csv", "dataset",
         "Published training compute for 14 real models with hardware and chip-hours.",
         sorted({e for r in runs for e, _ in REG.match_text(r["hardware"] + " " + r["org"])})),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/rack_systems.csv",
         "data/rack_systems.csv", "dataset",
         "13 rack- and pod-scale systems with compute, memory, fabric and power.",
         ["nvlink", "ethernet_ai"]),
        ("https://github.com/DanielWang2029/Understanding-GPU/blob/main/report/report.md",
         "report/report.md", "report",
         "The 21,500-word accelerator field guide this atlas sits alongside.",
         []),
    ]
    for url, dataset, kind, summary, ents in internal:
        src = add_source(url, dataset=dataset, context=summary, title=dataset,
                         record_entities=ents)
        if src:
            src["kind"] = kind
            src["publisher"] = "Understanding-GPU repository"

    # --- Epoch chip-quantity notes carry their own URLs and rich context ---
    chip_csv = DATA / "sources" / "epoch_ai" / "data_center_chip_quantities.csv"
    if chip_csv.exists():
        for row in csv.DictReader(chip_csv.open()):
            note = row.get("Notes") or ""
            urls = re.findall(r"https?://[^\s)\]]+", note)
            if not urls:
                continue
            ents = []
            for eid, _ in REG.match_text(f"{row['Data center']} {row['Chip type']} "
                                         f"{row.get('Owner','')} {row.get('User','')}"):
                ents.append(eid)
            plain = MD_LINK.sub(r"\1", note)[:300]
            ctx = (f"{row['Chip type']} at {row['Data center']} "
                   f"({row['Date'][:10]}): {plain}")
            for u in urls:
                add_source(u, dataset="Epoch AI chip table", context=ctx,
                           record_entities=ents, title=f"{row['Chip type']} at {row['Data center']}",
                           date=row["Date"][:10])


# --------------------------------------------------------------------------
# assemble output
# --------------------------------------------------------------------------
def main() -> int:
    print("Loading datasets...")
    map_data, accel, pricing, supply, racks, mlperf, runs, regions = load()

    print("Registering entities...")
    register_entities(map_data, accel, pricing, supply, racks, regions)
    REG.finalise_index()
    print(f"  {len(REG.entities)} entities, {len(REG.alias_index)} aliases")

    print("Collecting sources and running entity recognition...")
    collect_sources(map_data, accel, pricing, regions, mlperf, runs)
    print(f"  {len(SOURCES)} unique sources")

    # attach sources to entities, and derive co-mention relations
    co = defaultdict(float)
    for src in SOURCES.values():
        ents = sorted(src["recognition"])
        for eid in ents:
            if eid in REG.entities:
                REG.entities[eid]["sources"].add(src["id"])
        strong = [e for e in ents if src["recognition"][e]["score"] >= 1.0]
        for i, a in enumerate(strong):
            for b in strong[i + 1:]:
                if REG.entities.get(a, {}).get("type") != REG.entities.get(b, {}).get("type"):
                    co[(a, b)] += 1
    for (a, b), n in co.items():
        if n >= 3:
            add_relation(a, b, "co-cited", min(4.0, n / 3), f"{int(n)} shared sources")

    # One comparable 1-10 scale. Base size comes from the entity's own scale
    # (site power, country site count), the rest from how often sources mention
    # it, so the grid reflects both magnitude and evidence.
    site_counts = defaultdict(int)
    for e in REG.entities.values():
        if e["type"] == "site" and e.get("country"):
            site_counts["country:" + slug(e["country"])] += 1
    for e in REG.entities.values():
        base = {"company": 2.0, "chip": 2.5, "region": 2.0, "component": 2.0}.get(e["type"], 0.0)
        if e["type"] == "site":
            base = 1.0 + min(5.0, e.get("weight", 0.0))
        elif e["type"] == "country":
            base = 1.0 + min(4.0, site_counts.get(e["id"], 0) / 8.0)
        evidence = min(5.0, len(e["sources"]) / 12.0)
        e["weight"] = round(max(1.0, min(10.0, base + evidence)), 2)

    # relation lists per entity
    rel_out = []
    for (a, b, verb), rel in RELATIONS.items():
        if a not in REG.entities or b not in REG.entities:
            continue
        rid = len(rel_out)
        rel_out.append({"a": a, "b": b, "verb": verb, "weight": round(rel["weight"], 2),
                        "evidence": sorted(rel["evidence"])[:4]})
        REG.entities[a]["relations"].append(rid)
        REG.entities[b]["relations"].append(rid)

    entities = []
    for e in sorted(REG.entities.values(), key=lambda x: (-x["weight"], x["name"])):
        if not e["sources"] and not e["relations"]:
            continue
        entities.append({
            "id": e["id"],
            # only dataCenterView site records shout; vendor and part names are
            # legitimately upper case (NVIDIA, B200 HGX, TPU v7)
            "name": display_name(e["name"]) if e["type"] == "site" else e["name"],
            "type": e["type"],
            "weight": e["weight"],
            "summary": e.get("summary", ""),
            "metrics": e.get("metrics", [])[:6],
            "aliases": sorted(a for a in e["aliases"] if a != norm(e["name"]))[:6],
            "sources": sorted(e["sources"]),
            "relations": sorted(set(e["relations"])),
            "vendor": e.get("vendor", ""),
            "status": e.get("status", ""),
            "country": e.get("country", ""),
            "map_id": e.get("map_id", ""),
        })

    sources = []
    for src in sorted(SOURCES.values(), key=lambda s: (-len(s["recognition"]), s["url"])):
        rec = []
        for eid, info in sorted(src["recognition"].items(),
                                key=lambda kv: -kv[1]["score"]):
            if eid not in REG.entities:
                continue
            rec.append({"entity": eid, "score": round(info["score"], 2),
                        "methods": [{"method": m, "span": sp}
                                    for m, sp in info["methods"].items()]})
        sources.append({
            "id": src["id"], "url": src["url"], "host": src["host"],
            "publisher": src["publisher"], "kind": src["kind"],
            "title": src["title"], "attached_to": src["attached_to"][:4],
            "date": src["date"],
            "datasets": sorted(src["datasets"]),
            "contexts": src["contexts"][:3],
            "records": src["records"][:3],
            "entities": rec,
        })

    payload = {
        "generated_at": AS_OF,
        "types": TYPES,
        "entities": entities,
        "relations": rel_out,
        "sources": sources,
        "methods": {
            "record": "Named by a field of the dataset record the link was attached to "
                      "(operator, tenant, country, installed chips).",
            "domain": "The link's host belongs to this entity.",
            "path": "An alias for this entity appears in the URL path.",
            "context": "An alias appears in the text that travelled with the link — "
                       "record name, Epoch observation note, or region description.",
        },
        "stats": {
            "entities": len(entities),
            "relations": len(rel_out),
            "sources": len(sources),
            "recognitions": sum(len(s["entities"]) for s in sources),
            "by_type": {t: sum(1 for e in entities if e["type"] == t) for t in TYPES},
            "by_kind": {k: sum(1 for s in sources if s["kind"] == k)
                        for k in sorted({s["kind"] for s in sources})},
            "by_dataset": {d: sum(1 for s in sources if d in s["datasets"])
                           for d in sorted({d for s in sources for d in s["datasets"]})},
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))

    st = payload["stats"]
    print(f"\n  entities {st['entities']}  relations {st['relations']}  "
          f"sources {st['sources']}  recognitions {st['recognitions']}")
    print("  by type:", st["by_type"])
    print("  by kind:", st["by_kind"])
    print(f"\nwrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
