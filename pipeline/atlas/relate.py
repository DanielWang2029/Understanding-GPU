"""Stage 6 — relations: derive the graph from filled parameters.

Relations are never authored. Each one is a function of a parameter that some
source filled, so every edge can name the source and record behind it. Adding a
relation type means adding a rule here, not editing data.
"""

from __future__ import annotations

from collections import defaultdict

RULES = [
    # (subject type, parameter, object type, verb, direction)
    ("accelerator", "vendor", "company", "designs", "object_first"),
    ("datacenter", "operator", "company", "operates", "object_first"),
    ("datacenter", "tenant", "company", "tenant of", "object_first"),
    ("datacenter", "country", "country", "located in", "subject_first"),
    ("cloud_region", "provider", "company", "operates region", "object_first"),
    ("cloud_region", "country", "country", "located in", "subject_first"),
]


class Relations:
    def __init__(self):
        self.edges: dict[tuple, dict] = {}

    def add(self, a: str, b: str, verb: str, weight: float, evidence: str,
            record: str = ""):
        if not a or not b or a == b:
            return
        key = (a, b, verb)
        edge = self.edges.get(key)
        if not edge:
            edge = {"a": a, "b": b, "verb": verb, "weight": 0.0,
                    "sources": set(), "records": []}
            self.edges[key] = edge
        edge["weight"] += weight
        edge["sources"].add(evidence)
        if record and len(edge["records"]) < 6:
            edge["records"].append(record)


def derive(store, records: list[dict]) -> Relations:
    rel = Relations()
    ents = store.entities

    for entity in ents.values():
        for etype, param, target_type, verb, direction in RULES:
            if entity["type"] != etype:
                continue
            raw = entity["params"].get(param)
            if not isinstance(raw, str) or not raw.strip():
                continue
            prov = entity["provenance"].get(param, {})
            for eid, _ in store.recognizer.match_text(raw, target_type):
                a, b = ((eid, entity["id"]) if direction == "object_first"
                        else (entity["id"], eid))
                rel.add(a, b, verb, 1.0, prov.get("source", "derived"),
                        prov.get("record", ""))

        # a site deploys the parts counted on it
        if entity["type"] == "datacenter":
            for chip in (entity["params"].get("accelerators_installed") or {}):
                for eid, _ in store.recognizer.match_text(str(chip), "accelerator"):
                    rel.add(entity["id"], eid, "deploys", 1.0, "epoch_chips")

        # a region rents out what it can provision
        if entity["type"] == "cloud_region":
            text = " ".join(str(x) for x in [entity["params"].get("detail") or "",
                                             *(entity["params"].get("accelerators") or [])])
            for eid, _ in store.recognizer.match_text(text, "accelerator"):
                rel.add(eid, entity["id"], "rentable in", 1.0, "provider_docs")

    # priced offers: provider rents out the part
    for r in records:
        if r["kind"] == "chip_price" and r.get("subject"):
            for eid, _ in store.recognizer.match_text(
                    r["claims"].get("provider") or "", "company"):
                rel.add(eid, r["subject"], "rents out", 1.0, r["source"], r["id"])
        if r["kind"] == "supply_metric" and r["claims"].get("category") == "hbm_share":
            target = "component:hbm4" if str(r.get("date")) >= "2026" else "component:hbm3e"
            for eid, _ in store.recognizer.match_text(
                    r["claims"].get("item") or "", "company"):
                rel.add(eid, target, "supplies", 2.0, r["source"], r["id"])
        if r["kind"] == "cost_model" and r.get("subject"):
            for comp in ("component:hbm3e", "component:cowos"):
                rel.add(r["subject"], comp, "consumes", 1.5, r["source"], r["id"])
        if r["kind"] == "training_run":
            org, hw = r["claims"].get("org") or "", r["claims"].get("hardware") or ""
            for c, _ in store.recognizer.match_text(org, "company"):
                for chip, _ in store.recognizer.match_text(hw, "accelerator"):
                    rel.add(c, chip, "trained on", 1.0, r["source"], r["id"])
        if r["kind"] == "benchmark_result":
            for c, _ in store.recognizer.match_text(r["claims"].get("vendor") or "", "company"):
                if r.get("subject"):
                    rel.add(c, r["subject"], "submitted result", 0.5, r["source"], r["id"])

    # co-citation: two entities of different types recognised in the same
    # document often enough to be worth an edge
    doc_entities = defaultdict(set)
    for r in records:
        for url in r.get("documents") or []:
            for hit in r.get("entities") or []:
                if hit["score"] >= 1.0:
                    doc_entities[url].add(hit["entity"])
    co = defaultdict(int)
    for url, group in doc_entities.items():
        members = sorted(group)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if ents.get(a, {}).get("type") != ents.get(b, {}).get("type"):
                    co[(a, b)] += 1
    for (a, b), n in co.items():
        if n >= 3:
            rel.add(a, b, "co-cited", min(4.0, n / 3), f"{n} shared documents")
    return rel


def index(store, rel: Relations) -> list[dict]:
    out = []
    for (a, b, verb), edge in rel.edges.items():
        if a not in store.entities or b not in store.entities:
            continue
        rid = len(out)
        out.append({"a": a, "b": b, "verb": verb, "weight": round(edge["weight"], 2),
                    "sources": sorted(edge["sources"])[:4],
                    "records": edge["records"][:4]})
        store.entities[a]["relations"].append(rid)
        store.entities[b]["relations"].append(rid)
    return out
