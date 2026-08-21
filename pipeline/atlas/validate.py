"""Stage 7 — validation: the gates a build must pass.

Errors fail the build. Warnings are printed and counted, because some of them
describe the data rather than the code: a data center nobody has published power
for is a fact about the world, not a bug.
"""

from __future__ import annotations

from collections import Counter

from . import schema


def check_sources(catalog: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    seen = set()
    for s in catalog:
        where = s.get("id") or "<unnamed>"
        for field in schema.SOURCE_REQUIRED:
            # `fills` may legitimately be empty: MLPerf and the training-run table
            # are evidence, not attributes. The key must still be declared.
            if field not in s or (not s.get(field) and field != "fills"):
                errors.append(f"source {where}: missing required field '{field}'")
        if where in seen:
            errors.append(f"source {where}: duplicate id")
        seen.add(where)
        if s.get("kind") not in schema.SOURCE_KINDS:
            errors.append(f"source {where}: unknown kind '{s.get('kind')}'")
        for k in s.get("record_kinds") or []:
            if k not in schema.RECORD_KINDS:
                errors.append(f"source {where}: unknown record kind '{k}'")
        for path in s.get("fills") or []:
            etype, _, param = path.partition(".")
            if etype not in schema.ENTITY_PARAMS:
                errors.append(f"source {where}: fills unknown entity type '{etype}'")
            elif param not in schema.ENTITY_PARAMS[etype]:
                errors.append(f"source {where}: fills unknown parameter '{path}'")
        if not isinstance(s.get("trust"), (int, float)) or not 0 <= s["trust"] <= 1:
            errors.append(f"source {where}: trust must be between 0 and 1")
        if not s.get("caveats"):
            warnings.append(f"source {where}: no caveats recorded")
        if not s.get("stats", {}).get("records"):
            warnings.append(f"source {where}: produced no records")
    return errors, warnings


def check_records(records: list[dict], catalog: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    ids = set()
    unresolved = 0
    for r in records:
        where = r.get("id") or "<unnamed>"
        for field in schema.RECORD_REQUIRED:
            if field not in r:
                errors.append(f"record {where}: missing '{field}'")
        if where in ids:
            errors.append(f"record {where}: duplicate id")
        ids.add(where)
        if r.get("source") not in catalog:
            errors.append(f"record {where}: unknown source '{r.get('source')}'")
        if r.get("kind") not in schema.RECORD_KINDS:
            errors.append(f"record {where}: unknown kind '{r.get('kind')}'")
        if r.get("confidence") not in schema.CONFIDENCE:
            errors.append(f"record {where}: bad confidence '{r.get('confidence')}'")
        declared = catalog.get(r.get("source"), {}).get("record_kinds") or []
        if declared and r.get("kind") not in declared:
            errors.append(f"record {where}: kind '{r['kind']}' not declared by its source")
        if not r.get("subject") and r.get("subject_type"):
            unresolved += 1
    if unresolved:
        warnings.append(f"{unresolved} records have a typed subject that did not resolve")
    return errors, warnings


def check_entities(entities: list[dict], relations: list[dict],
                   record_ids: set[str], catalog: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    ids = set()
    empty = Counter()
    for e in entities:
        where = e.get("id") or "<unnamed>"
        for field in schema.ENTITY_COMMON_REQUIRED:
            if field not in e:
                errors.append(f"entity {where}: missing '{field}'")
        if where in ids:
            errors.append(f"entity {where}: duplicate id")
        ids.add(where)
        if e.get("type") not in schema.ENTITY_PARAMS:
            errors.append(f"entity {where}: unknown type '{e.get('type')}'")
            continue
        expected = set(schema.ENTITY_PARAMS[e["type"]])
        got = set(e.get("params") or {})
        if expected - got:
            errors.append(f"entity {where}: default parameters missing "
                          f"{sorted(expected - got)}")
        if got - expected:
            errors.append(f"entity {where}: undeclared parameters {sorted(got - expected)}")
        for param, prov in (e.get("provenance") or {}).items():
            if param not in expected:
                errors.append(f"entity {where}: provenance for unknown parameter '{param}'")
            src = prov.get("source")
            if src and src != "derived" and src not in catalog:
                errors.append(f"entity {where}: provenance names unknown source '{src}'")
            rec = prov.get("record")
            if rec and rec not in record_ids:
                errors.append(f"entity {where}: provenance names unknown record '{rec}'")
            if e["params"].get(param) is None:
                errors.append(f"entity {where}: provenance for empty parameter '{param}'")
        filled = sum(1 for v in e["params"].values() if v not in (None, "", [], {}))
        if not filled:
            empty[e["type"]] += 1
        for rid in e.get("relations") or []:
            if not 0 <= rid < len(relations):
                errors.append(f"entity {where}: relation index {rid} out of range")
    for etype, n in empty.items():
        warnings.append(f"{n} {etype} entities have no filled parameters")
    return errors, warnings


def coverage(entities: list[dict]) -> dict:
    """Share of each type's default parameters that carry a value. This is the
    number to watch when adding a source: it should go up."""
    out = {}
    for etype, spec in schema.ENTITY_PARAMS.items():
        group = [e for e in entities if e["type"] == etype]
        if not group:
            continue
        per_param = {}
        for param in spec:
            n = sum(1 for e in group
                    if e["params"].get(param) not in (None, "", [], {}))
            per_param[param] = round(100 * n / len(group), 1)
        out[etype] = {"entities": len(group),
                      "mean_filled_pct": round(sum(per_param.values()) / len(per_param), 1),
                      "by_param": per_param}
    return out


def report(errors: list[str], warnings: list[str], *, strict: bool = True) -> None:
    for w in warnings[:20]:
        print(f"  warning: {w}")
    if len(warnings) > 20:
        print(f"  ... and {len(warnings) - 20} more warnings")
    for e in errors[:40]:
        print(f"  ERROR: {e}")
    if errors and strict:
        raise SystemExit(f"validation failed with {len(errors)} error(s)")
