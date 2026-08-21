"""The build: run every stage in order and emit the registry plus the UI bundles.

    python3 -m pipeline.atlas.build

Stages, in order, each one a module:

    1 catalog    declare the sources                       catalog.py
    2 ingest     source → records                          adapters.py
    3 recognise  records → entity references                recognize.py
    4 resolve    mentions → canonical entities              resolve.py
    5 fill       records → typed default parameters         fill.py
    6 relate     parameters → relations                     relate.py
    7 validate   gates on all three layers                  validate.py
    8 emit       registry JSON + UI bundles                 here

Outputs:
    data/registry/sources.json          the catalog, with measured stats and samples
    data/registry/records.json          every record, with its recognition results
    data/registry/entities.json         every entity, with filled parameters
    data/registry/resolution_log.json   which rule folded which name into which id
    docs/entity-atlas/data.json         UI bundle: entities, relations, documents
    docs/entity-atlas/sources.json      UI bundle: the Data sources tab
"""

from __future__ import annotations

import json
import pathlib
import time
from collections import Counter, defaultdict

from . import adapters, catalog, documents, fill, relate, resolve, schema, validate

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
UI = ROOT / "docs" / "entity-atlas"
GENERATED = time.strftime("%Y-%m-%d")

# The UI's type keys predate the registry's; the registry names the thing, the UI
# names the tile. Mapping here keeps both readable.
UI_TYPE = {"company": "company", "accelerator": "chip", "datacenter": "site",
           "cloud_region": "region", "component": "component", "country": "country"}
UI_TYPES = {
    "company":   {"label": "Company / operator", "color": "#4fc3ff"},
    "chip":      {"label": "Accelerator",        "color": "#ffb648"},
    "site":      {"label": "Data center",        "color": "#b085ff"},
    "region":    {"label": "Cloud region",       "color": "#3fe0a0"},
    "component": {"label": "Supply chain",       "color": "#ff6fb5"},
    "country":   {"label": "Country",            "color": "#8ea0bd"},
}


def write(path: pathlib.Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:,.0f} KB)")


def main() -> int:
    t0 = time.time()
    sources = catalog.catalog()
    by_id = {s["id"]: s for s in sources}

    # ---------------------------------------------------------------- 2 ingest
    print(f"Ingesting {len(sources)} sources...")
    records: list[dict] = []
    for source in sources:
        rows = adapters.run(source)
        records.extend(rows)
        kinds = Counter(r["kind"] for r in rows)
        source["stats"] = {"records": len(rows), "documents": 0, "entities": 0,
                           "record_kinds": dict(kinds)}
        print(f"  {source['id']:<22} {len(rows):>5} records  {dict(kinds)}")

    # -------------------------------------------------- 4 resolve (needs index)
    print("Resolving entities...")
    store = resolve.EntityStore()
    resolve.seed(store)
    resolve.discover(store, records, by_id)
    for r in records:
        if r.get("subject"):
            continue
        etype = r.get("subject_type")
        if not etype:
            continue
        r["subject"] = store.resolve(r["subject_hint"], etype, record_id=r["id"]) or ""
    print(f"  {len(store.entities)} entities: {resolve.counts(store)}")

    # ------------------------------------------------------------- 3 recognise
    print("Running recognition over every record...")
    resolve.attach(store, records)
    hits = sum(len(r["entities"]) for r in records)
    print(f"  {hits:,} entity references across {len(records):,} records")

    # ------------------------------------------------------------------ 5 fill
    print("Filling default parameters...")
    fill.fill_from_records(store, records, by_id)
    fill.fill_inventories(store, records)
    fill.fill_derived(store, records)
    fill.weigh(store)

    # ---------------------------------------------------------------- 6 relate
    print("Deriving relations...")
    rel = relate.derive(store, records)
    relations = relate.index(store, rel)
    print(f"  {len(relations):,} relations")

    # documents (evidence layer, needed by the UI and by source stats)
    print("Collecting documents...")
    docs = documents.collect(records, store, by_id)
    print(f"  {len(docs):,} unique documents")

    # ---------------------------------------------------- source stats+samples
    docs_by_source = defaultdict(set)
    for d in docs:
        for sid in d["sources"]:
            docs_by_source[sid].add(d["url"])
    ents_by_source = defaultdict(set)
    for r in records:
        for hit in r["entities"]:
            ents_by_source[r["source"]].add(hit["entity"])
    for source in sources:
        sid = source["id"]
        source["stats"].update({
            "documents": len(docs_by_source[sid]),
            "entities": len(ents_by_source[sid]),
        })
        source["sample"] = pick_samples(records, sid)

    # -------------------------------------------------------------- 7 validate
    print("Validating...")
    entities_out = [emit_entity(e, store) for e in
                    sorted(store.entities.values(), key=lambda e: (-e["weight"], e["name"]))]
    record_ids = {r["id"] for r in records}
    errors, warnings = [], []
    for check in (validate.check_sources(sources),
                  validate.check_records(records, by_id),
                  validate.check_entities(entities_out, relations, record_ids, by_id)):
        errors += check[0]
        warnings += check[1]
    validate.report(errors, warnings)
    cover = validate.coverage(entities_out)
    for etype, c in cover.items():
        print(f"  {etype:<13} {c['entities']:>4} entities, "
              f"{c['mean_filled_pct']:>5}% of default parameters filled")

    # ------------------------------------------------------------------ 8 emit
    print("Emitting registry...")
    write(REGISTRY / "sources.json", {
        "generated_at": GENERATED,
        "schema": {"fields": schema.SOURCE_FIELDS, "required": list(schema.SOURCE_REQUIRED),
                   "kinds": schema.SOURCE_KINDS},
        "sources": sources,
    })
    write(REGISTRY / "records.json", {
        "generated_at": GENERATED,
        "schema": {"fields": schema.RECORD_FIELDS, "required": list(schema.RECORD_REQUIRED),
                   "kinds": schema.RECORD_KINDS},
        "count": len(records),
        "records": records,
    })
    write(REGISTRY / "entities.json", {
        "generated_at": GENERATED,
        "schema": {"common": schema.ENTITY_COMMON, "params": schema.ENTITY_PARAMS,
                   "types": list(schema.ENTITY_TYPES)},
        "coverage": cover,
        "count": len(entities_out),
        "entities": entities_out,
        "relations": relations,
    })
    write(REGISTRY / "resolution_log.json", {
        "generated_at": GENERATED,
        "rules": {
            "R1 given": "the adapter supplied a canonical id",
            "R2 seeded": "matched a seeded company or component alias",
            "R3 identity": "matched a canonical site from the identity source",
            "R4 alias": "matched an existing entity name or alias of the same type",
            "R5 designator": "rejected: facility codes differ",
            "R6 new": "no match, provisional entity created",
        },
        "counts": dict(Counter(x["rule"] for x in store.log)),
        "log": store.log[:6000],
    })

    # UI bundles
    print("Emitting UI bundles...")
    write(UI / "data.json", ui_bundle(entities_out, relations, docs, cover))
    write(UI / "sources.json", ui_sources(sources, records, store, docs))

    print(f"\ndone in {time.time() - t0:.1f}s  "
          f"{len(sources)} sources · {len(records):,} records · "
          f"{len(entities_out):,} entities · {len(relations):,} relations · "
          f"{len(docs):,} documents")
    return 0


def pick_samples(records: list[dict], source_id: str, per_kind: int = 2) -> list[str]:
    """Two records per kind, preferring ones with the most claims: the UI shows
    these as the source's real example data."""
    by_kind = defaultdict(list)
    for r in records:
        if r["source"] == source_id:
            by_kind[r["kind"]].append(r)
    out = []
    for kind, group in by_kind.items():
        group.sort(key=lambda r: (-len(r["claims"]), -len(r.get("documents") or [])))
        out += [r["id"] for r in group[:per_kind]]
    return out


def emit_entity(e: dict, store) -> dict:
    return {
        "id": e["id"],
        "type": e["type"],
        "name": e["name"],
        "aliases": sorted(a for a in e["aliases"] if a != e["name"].lower())[:8],
        "summary": e["summary"][:400],
        "params": e["params"],
        "params_extra": e.get("params_extra", {}),
        "provenance": e["provenance"],
        "conflicts": e["conflicts"],
        "sources": sorted(e["sources"]),
        "records": e["records"][:40],
        "record_count": len(e["records"]),
        "documents": sorted(e["documents"])[:40],
        "document_count": len(e["documents"]),
        "relations": sorted(set(e["relations"])),
        "merged_from": sorted(e["merged_from"])[:12],
        "provisional": e["provisional"],
        "map_id": e.get("map_id", ""),
        "weight": e["weight"],
        "updated": e["updated"],
    }


def ui_bundle(entities: list[dict], relations: list[dict], docs: list[dict],
              cover: dict) -> dict:
    """The atlas reads this. Registry types are mapped onto the UI's tile types,
    and entity parameters travel through so the detail panel can show them."""
    ui_entities = []
    for e in entities:
        if not e["sources"] and not e["relations"]:
            continue
        ui_entities.append({
            "id": e["id"], "type": UI_TYPE[e["type"]], "kind": e["type"],
            "name": e["name"], "weight": e["weight"], "summary": e["summary"],
            "aliases": e["aliases"][:6],
            "params": {k: v for k, v in e["params"].items() if v not in (None, "", [], {})},
            "provenance": e["provenance"],
            "conflicts": e["conflicts"],
            "metrics": headline_metrics(e),
            "documents": e["documents"],
            "document_count": e["document_count"],
            "record_count": e["record_count"],
            "relations": e["relations"],
            "sources": e["sources"],
            "merged_from": e["merged_from"],
            "provisional": e["provisional"],
            "map_id": e.get("map_id", ""),
            "country": e["params"].get("country") or "",
            "status": e["params"].get("status") or "",
            "vendor": e["params"].get("vendor") or "",
        })
    keep = {e["id"] for e in ui_entities}
    doc_out = []
    for d in docs:
        doc_out.append({**d, "entities": [x for x in d["entities"] if x["entity"] in keep]})

    by_type = Counter(e["type"] for e in ui_entities)
    return {
        "generated_at": GENERATED,
        "types": UI_TYPES,
        "entities": ui_entities,
        "relations": relations,
        "documents": doc_out,
        "methods": schema.RECOGNITION_METHODS,
        "param_spec": {UI_TYPE[t]: spec for t, spec in schema.ENTITY_PARAMS.items()},
        "stats": {
            "entities": len(ui_entities),
            "relations": len(relations),
            "documents": len(doc_out),
            "recognitions": sum(len(d["entities"]) for d in doc_out),
            "by_type": dict(by_type),
            "by_kind": dict(Counter(d["kind"] for d in doc_out)),
            "by_source": dict(Counter(s for d in doc_out for s in d["sources"])),
            "coverage": {UI_TYPE[t]: c["mean_filled_pct"] for t, c in cover.items()},
        },
    }


def headline_metrics(e: dict) -> list[list[str]]:
    """Up to six parameters worth showing on a tile, formatted."""
    order = {
        "company": ["category", "founded", "ceo", "headquarters", "sites_operated",
                    "power_mw_operated"],
        "accelerator": ["vendor", "launch", "memory_gb", "dense_bf16_tflops",
                        "dense_fp8_tflops", "scaleup_domain"],
        "datacenter": ["operator", "tenant", "status", "power_mw", "power_mw_planned",
                       "h100e"],
        "cloud_region": ["provider", "city", "country", "accelerators", "status"],
        "component": ["category", "suppliers", "unit_price_usd", "constraint"],
        "country": ["sites", "power_mw", "power_mw_planned", "h100e", "cloud_regions"],
    }[e["type"]]
    out = []
    for param in order:
        value = e["params"].get(param)
        if value in (None, "", [], {}):
            continue
        spec = schema.param_spec(e["type"], param)
        label = param.replace("_", " ").replace("mw", "MW").replace("h100e", "H100e")
        out.append([label[:1].upper() + label[1:], format_value(value, spec.get("unit"))])
    return out[:6]


def format_value(value, unit: str | None) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:4])
    if isinstance(value, dict):
        return ", ".join(f"{k} {v:,.0f}" if isinstance(v, (int, float)) else str(k)
                         for k, v in list(value.items())[:3])
    if isinstance(value, float):
        # modelled figures arrive with false precision (275795.85649 H100e)
        value = int(round(value)) if abs(value) >= 100 else round(value, 2)
    if isinstance(value, (int, float)):
        text = f"{value:,}" if abs(value) >= 1000 else f"{value:g}"
        return f"{text} {unit}" if unit and unit != "year" else text
    return str(value)


def ui_sources(sources: list[dict], records: list[dict], store, docs: list[dict]) -> dict:
    """The Data sources tab: the catalog plus, per source, its sample records
    resolved into displayable rows and its top documents and entities."""
    by_id = {r["id"]: r for r in records}
    docs_by_source = defaultdict(list)
    for d in docs:
        for sid in d["sources"]:
            docs_by_source[sid].append(d)
    ent_counter = defaultdict(Counter)
    for r in records:
        for hit in r["entities"]:
            ent_counter[r["source"]][hit["entity"]] += 1

    out = []
    for s in sources:
        sid = s["id"]
        samples = []
        for rid in s.get("sample") or []:
            r = by_id.get(rid)
            if not r:
                continue
            samples.append({
                "id": r["id"], "kind": r["kind"], "date": r["date"],
                "subject": r.get("subject") or "",
                "subject_name": store.entities.get(r.get("subject") or "", {}).get(
                    "name", r.get("subject_hint") or ""),
                "confidence": r["confidence"],
                "claims": [[k, format_value(v, r.get("units", {}).get(k))]
                           for k, v in list(r["claims"].items())[:12]],
                "units": r.get("units", {}),
                "entities": [{"entity": h["entity"],
                              "name": store.entities.get(h["entity"], {}).get("name", ""),
                              "score": h["score"],
                              "methods": h["methods"]} for h in r["entities"][:6]],
                "documents": (r.get("documents") or [])[:3],
                "context": r.get("context", "")[:280],
                "raw_ref": r.get("raw_ref", ""),
            })
        top_entities = [{"entity": eid,
                         "name": store.entities.get(eid, {}).get("name", eid),
                         "type": UI_TYPE.get(store.entities.get(eid, {}).get("type", ""), ""),
                         "records": n}
                        for eid, n in ent_counter[sid].most_common(12)]
        out.append({**{k: v for k, v in s.items() if k != "sample"},
                    "samples": samples,
                    "top_entities": top_entities,
                    "top_documents": [{"url": d["url"], "publisher": d["publisher"],
                                       "title": d["title"], "kind": d["kind"]}
                                      for d in docs_by_source[sid][:6]]})
    return {
        "generated_at": GENERATED,
        "schema": {"fields": schema.SOURCE_FIELDS, "required": list(schema.SOURCE_REQUIRED),
                   "kinds": schema.SOURCE_KINDS, "record_kinds": schema.RECORD_KINDS,
                   "confidence": list(schema.CONFIDENCE)},
        "stats": {
            "sources": len(out),
            "records": len(records),
            "documents": len(docs),
            "by_kind": dict(Counter(s["kind"] for s in out)),
            "by_record_kind": dict(Counter(r["kind"] for r in records)),
            "by_confidence": dict(Counter(r["confidence"] for r in records)),
        },
        "sources": out,
    }


if __name__ == "__main__":
    raise SystemExit(main())
