"""The contract for the three registry layers.

    source  →  record  →  entity

Every JSON the pipeline emits conforms to what is declared here, and
`validate.py` enforces it. Adding a field means adding it here first; the
builders and the UI read the declarations rather than hard-coding key names.

Layer 1  SOURCE  an origin of data: a pipeline, a dataset, a document set, an
                 API, or one of our own derived tables. Catalogued by hand in
                 `catalog.py`, emitted to `data/registry/sources.json`.
Layer 2  RECORD  one dated observation extracted from a source, expressed as
                 claims about one subject entity. Emitted to
                 `data/registry/records.json`.
Layer 3  ENTITY  a resolved thing — company, accelerator, data center, cloud
                 region, supply-chain component, country — whose typed default
                 parameters are filled from records, each with its own
                 provenance. Emitted to `data/registry/entities.json`.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# shared vocabularies
# ---------------------------------------------------------------------------
CONFIDENCE = ("confirmed", "estimate", "rumor")
"""confirmed = the party in a position to know said it (vendor datasheet, filing,
earnings call, official price list, peer-reviewed paper, benchmark body).
estimate  = a named analyst or model, or arithmetic derived here from confirmed
            inputs. rumor = single-source channel check or anonymous report."""

ACCESS = ("download", "api", "zip", "repo", "manual", "derived")
FORMATS = ("csv", "json", "zip", "html", "markdown", "mixed")
CADENCE = ("static", "ad-hoc", "monthly", "quarterly", "continuous")

SOURCE_KINDS = {
    "pipeline": "An ingestion system with its own provenance model, ingested as a whole.",
    "dataset": "A published, downloadable dataset with a licence.",
    "document-set": "A set of individual documents (news, filings, vendor pages) cited per claim.",
    "api": "A queryable endpoint read at build time or snapshotted.",
    "derived": "A table produced by this repository from other sources.",
    "registry": "A directory or listing service used to enumerate facilities.",
}

RECORD_KINDS = {
    "site_profile": "Identity, location, operator and status of a data center.",
    "site_capacity": "Power capacity of a site at a date, current or planned.",
    "site_compute": "Installed or planned accelerator counts and H100-equivalents at a site.",
    "chip_spec": "Specification of an accelerator part.",
    "chip_price": "A rental or purchase price for an accelerator.",
    "chip_inventory": "A count of one chip type at one site on one date.",
    "region_availability": "Which accelerators a cloud region offers.",
    "benchmark_result": "A time-to-train or throughput result.",
    "training_run": "Compute, hardware and duration of a published model training run.",
    "supply_metric": "A supply-chain quantity: capacity, share, price, shipments.",
    "cost_model": "A modelled bill of materials or cost breakdown.",
    "reliability": "Observed failure or interruption counts.",
    "geo_profile": "Geography of a place: ISO code, continent, containing country.",
    "citation": "A document cited as evidence, carrying no numeric payload of its own.",
}

ENTITY_TYPES = ("company", "accelerator", "datacenter", "cloud_region",
                "component", "country")

# ---------------------------------------------------------------------------
# Layer 1 — SOURCE
# ---------------------------------------------------------------------------
SOURCE_FIELDS = {
    # identity
    "id":            "Stable slug, referenced by every record. Required.",
    "name":          "Human name of the source. Required.",
    "publisher":     "Who publishes it. Required.",
    "kind":          f"One of {tuple(SOURCE_KINDS)}. Required.",
    # access
    "url":           "Landing page or file URL. Required.",
    "access":        f"How it is obtained: {ACCESS}.",
    "format":        f"Wire format: {FORMATS}.",
    "local_path":    "Path in this repo holding the snapshot, if any.",
    "adapter":       "Name of the adapter function that ingests it. Required.",
    # licence and freshness
    "licence":       "Licence or terms of use.",
    "attribution":   "The citation string to reproduce when using it.",
    "retrieved":     "ISO date this snapshot was taken.",
    "cadence":       f"How often upstream changes: {CADENCE}.",
    # what it is good for
    "scope":         "One line on coverage: geography, topic, period.",
    "record_kinds":  f"Record kinds it can produce, from {tuple(RECORD_KINDS)}. Required.",
    "entity_types":  f"Entity types it can create or describe, from {ENTITY_TYPES}.",
    "fills":         "Dotted paths this source can populate, e.g. "
                     "'datacenter.power_mw'. Drives the fill step's precedence "
                     "and the UI's 'fills' column. Required.",
    # judgement
    "trust":         "0-1. Tie-breaker when two sources claim the same field. "
                     "Primary/vendor/filing high, analyst model mid, aggregator low. Required.",
    "confidence_default": f"Confidence stamped on records lacking their own: {CONFIDENCE}.",
    "caveats":       "What this source is known to get wrong or omit.",
    # measured at build time (never hand-written)
    "sample":        "Ids of representative records, filled by the builder.",
    "stats":         "{records, documents, entities, record_kinds{}} filled by the builder.",
}
SOURCE_REQUIRED = ("id", "name", "publisher", "kind", "url", "adapter",
                   "record_kinds", "fills", "trust")

# ---------------------------------------------------------------------------
# Layer 2 — RECORD
# ---------------------------------------------------------------------------
RECORD_FIELDS = {
    "id":          "Stable id: '<source>-<kind>-<n>'. Required.",
    "source":      "Source id this came from. Required.",
    "kind":        f"One of {tuple(RECORD_KINDS)}. Required.",
    "date":        "ISO date the observation refers to (as-of), '' if undated. Required key.",
    "retrieved":   "ISO date the source snapshot was taken.",
    "subject":     "Entity id this record is primarily about, once resolved. Required key.",
    "subject_hint": "Raw name of the subject before resolution, kept for auditing.",
    "entities":    "All entity ids recognised in this record, with method and span. Required.",
    "claims":      "{field: value} payload. Field names match entity parameters "
                   "where the record is about an entity attribute. Required.",
    "units":       "{field: unit} for numeric claims.",
    "confidence":  f"One of {CONFIDENCE}. Required.",
    "documents":   "URLs evidencing this record.",
    "context":     "Short text that travelled with the record, for auditing.",
    "raw_ref":     "Pointer back into the source: file plus row or key.",
}
RECORD_REQUIRED = ("id", "source", "kind", "claims", "confidence", "entities")

# ---------------------------------------------------------------------------
# Layer 3 — ENTITY
# ---------------------------------------------------------------------------
ENTITY_COMMON = {
    "id":         "Stable id: '<type>:<slug>'. Required.",
    "type":       f"One of {ENTITY_TYPES}. Required.",
    "name":       "Canonical display name. Required.",
    "aliases":    "Other names and spellings this entity is recognised by. Required.",
    "summary":    "One or two sentences.",
    "params":     "The typed default parameter set below, every key present. Required.",
    "provenance": "{param: {source, record, confidence, as_of}} for filled params. Required.",
    "conflicts":  "{param: [{value, source, confidence}]} where sources disagreed.",
    "sources":    "Source ids that mention it.",
    "records":    "Record ids that mention it.",
    "documents":  "Document URLs that mention it.",
    "relations":  "Indices into the relations array.",
    "merged_from": "Ids or names folded into this entity by the resolve step.",
    "weight":     "1-10 display weight: own scale plus evidence volume.",
    "updated":    "Latest observation date across its records.",
}
ENTITY_COMMON_REQUIRED = ("id", "type", "name", "aliases", "params", "provenance")

# Per-type default parameters. Every entity of a type carries every key, with
# None where nothing has filled it — absence is information, so it is explicit
# rather than missing. `unit` documents numerics; `fill` says how the value is
# obtained: "record" (claimed by a source), "derived" (computed by the pipeline)
# or "manual" (curated in the catalog).
ENTITY_PARAMS: dict[str, dict[str, dict]] = {
    "company": {
        "role":          {"desc": "What it does in this market", "fill": "record"},
        "category":      {"desc": "vendor | operator | colocation | neocloud | "
                                  "hyperscaler | lab | supplier | foundry | research",
                          "fill": "record"},
        "founded":       {"desc": "Year founded", "unit": "year", "fill": "manual"},
        "ceo":           {"desc": "Chief executive", "fill": "manual"},
        "headquarters":  {"desc": "City, country of head office", "fill": "manual"},
        "country":       {"desc": "Country of incorporation", "fill": "manual"},
        "ticker":        {"desc": "Listed ticker, if public", "fill": "manual"},
        "website":       {"desc": "Primary domain", "fill": "record"},
        "sites_operated": {"desc": "Data centers it operates in the registry",
                           "unit": "count", "fill": "derived"},
        "sites_tenanted": {"desc": "Data centers where it is tenant or end user",
                           "unit": "count", "fill": "derived"},
        "power_mw_operated": {"desc": "Planned power across sites it operates",
                              "unit": "MW", "fill": "derived"},
        "accelerators_designed": {"desc": "Accelerator parts it designs",
                                  "unit": "count", "fill": "derived"},
    },
    "accelerator": {
        "vendor":        {"desc": "Designer", "fill": "record"},
        "family":        {"desc": "Architecture family", "fill": "record"},
        "role":          {"desc": "training | inference | both | dev", "fill": "record"},
        "launch":        {"desc": "Launch quarter or year", "fill": "record"},
        "process":       {"desc": "Fabrication node", "fill": "record"},
        "memory_gb":     {"desc": "On-package memory", "unit": "GB", "fill": "record"},
        "memory_type":   {"desc": "Memory technology", "fill": "record"},
        "memory_bw_tbs": {"desc": "Memory bandwidth", "unit": "TB/s", "fill": "record"},
        "dense_bf16_tflops": {"desc": "Dense BF16/FP16 throughput", "unit": "TFLOP/s",
                              "fill": "record"},
        "dense_fp8_tflops":  {"desc": "Dense FP8 throughput", "unit": "TFLOP/s",
                              "fill": "record"},
        "dense_fp4_tflops":  {"desc": "Dense FP4 throughput", "unit": "TFLOP/s",
                              "fill": "record"},
        "tdp_w":         {"desc": "Board or module power", "unit": "W", "fill": "record"},
        "scaleup_bw_gbs": {"desc": "Scale-up fabric bandwidth per chip", "unit": "GB/s",
                           "fill": "record"},
        "scaleup_domain": {"desc": "Chips in one coherent domain", "unit": "chips",
                           "fill": "record"},
        "unit_price_usd": {"desc": "Street or list price per chip", "unit": "USD",
                           "fill": "record"},
        "cheapest_rental_usd_hr": {"desc": "Lowest observed rental rate", "unit": "USD/hr",
                                   "fill": "derived"},
        "deployed_units":  {"desc": "Units counted across sites in the registry",
                            "unit": "chips", "fill": "derived"},
        "sites_deployed":  {"desc": "Sites known to run it", "unit": "count",
                            "fill": "derived"},
    },
    "datacenter": {
        "operator":      {"desc": "Company running the facility", "fill": "record"},
        "tenant":        {"desc": "Tenant or end user of the capacity", "fill": "record"},
        "status":        {"desc": "operating | expanding | under_construction | "
                                  "planned | announced | cancelled", "fill": "record"},
        "country":       {"desc": "Country", "fill": "record"},
        "region":        {"desc": "State, province or admin area", "fill": "record"},
        "city":          {"desc": "City or locality", "fill": "record"},
        "lat":           {"desc": "Latitude", "unit": "deg", "fill": "record"},
        "lon":           {"desc": "Longitude", "unit": "deg", "fill": "record"},
        "coord_precision": {"desc": "site | street | city | county | state | country",
                            "fill": "record"},
        "power_mw":      {"desc": "Energised IT power", "unit": "MW", "fill": "record"},
        "power_mw_planned": {"desc": "IT power at full build", "unit": "MW", "fill": "record"},
        "accelerators_installed": {"desc": "{chip: units} counted on site",
                                   "fill": "record"},
        "accelerators_planned":   {"desc": "{chip: units} planned", "fill": "record"},
        "h100e":         {"desc": "H100-equivalents installed", "unit": "chips",
                          "fill": "record"},
        "h100e_planned": {"desc": "H100-equivalents at full build", "unit": "chips",
                          "fill": "record"},
        "first_operational": {"desc": "Year the site first carried load", "unit": "year",
                              "fill": "record"},
        "capex_usd_b":   {"desc": "Modelled or announced capital cost",
                          "unit": "USD billions", "fill": "record"},
        "category":      {"desc": "hyperscaler | neocloud | wholesale_colo | "
                                  "retail_colo | developer | enterprise | frontier | other",
                          "fill": "record"},
    },
    "cloud_region": {
        "provider":      {"desc": "Cloud provider", "fill": "record"},
        "region_id":     {"desc": "Provider's region identifier", "fill": "record"},
        "label":         {"desc": "Provider's own location label", "fill": "record"},
        "city":          {"desc": "Physical metro", "fill": "record"},
        "country":       {"desc": "Country", "fill": "record"},
        "lat":           {"desc": "Latitude", "unit": "deg", "fill": "record"},
        "lon":           {"desc": "Longitude", "unit": "deg", "fill": "record"},
        "accelerators":  {"desc": "Accelerator families provisionable here", "fill": "record"},
        "detail":        {"desc": "Which generations and SKUs", "fill": "record"},
        "status":        {"desc": "operating | announced", "fill": "record"},
    },
    "component": {
        "category":      {"desc": "memory | packaging | fabric | power | cooling | optics",
                          "fill": "manual"},
        "role":          {"desc": "What it does in the stack", "fill": "manual"},
        "suppliers":     {"desc": "Companies supplying it", "fill": "derived"},
        "consumed_by":   {"desc": "Accelerators or systems that consume it",
                          "fill": "derived"},
        "unit_price_usd": {"desc": "Representative unit price", "unit": "USD",
                           "fill": "record"},
        "constraint":    {"desc": "Why it gates supply, if it does", "fill": "manual"},
    },
    "country": {
        "iso3":          {"desc": "ISO 3166-1 alpha-3", "fill": "record"},
        "continent":     {"desc": "Continent", "fill": "record"},
        "sites":         {"desc": "Data centers in the registry", "unit": "count",
                          "fill": "derived"},
        "power_mw":      {"desc": "Energised IT power across sites", "unit": "MW",
                          "fill": "derived"},
        "power_mw_planned": {"desc": "IT power at full build", "unit": "MW",
                             "fill": "derived"},
        "h100e":         {"desc": "H100-equivalents installed", "unit": "chips",
                          "fill": "derived"},
        "cloud_regions": {"desc": "Cloud regions in the country", "unit": "count",
                          "fill": "derived"},
        "accelerator_families": {"desc": "Accelerator families present", "fill": "derived"},
    },
}

# Relations are derived, never authored.
RELATION_FIELDS = {
    "a": "Subject entity id.",
    "b": "Object entity id.",
    "verb": "Relation type, e.g. designs, operates, deploys, located_in.",
    "weight": "Evidence weight.",
    "sources": "Source ids evidencing it.",
    "records": "Record ids evidencing it (capped).",
}

RECOGNITION_METHODS = {
    "field": "The value came from a named field of the record — operator, tenant, "
             "country, chip type. The strongest signal: the source filed the claim "
             "against that value.",
    "domain": "The evidencing document's host belongs to the entity.",
    "path": "An alias appears in the document's URL path.",
    "text": "An alias appears in free text attached to the record — a title, an "
            "observation note, a region description.",
}
METHOD_SCORE = {"field": 1.2, "domain": 1.0, "path": 0.9, "text": 0.7}
RECOGNITION_MIN_SCORE = 0.7


def blank_params(entity_type: str) -> dict:
    """Every default parameter present, None until something fills it."""
    return {name: None for name in ENTITY_PARAMS[entity_type]}


def param_spec(entity_type: str, name: str) -> dict:
    return ENTITY_PARAMS.get(entity_type, {}).get(name, {})


def default_source() -> dict:
    return {k: None for k in SOURCE_FIELDS}


def default_record() -> dict:
    return {"id": "", "source": "", "kind": "", "date": "", "retrieved": "",
            "subject": "", "subject_hint": "", "entities": [], "claims": {},
            "units": {}, "confidence": "estimate", "documents": [], "context": "",
            "raw_ref": ""}
