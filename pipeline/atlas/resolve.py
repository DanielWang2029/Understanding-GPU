"""Stage 4 — resolution: decide which mentions are the same entity.

Every record arrives with a `subject_hint` — a raw name as its source wrote it.
Resolution turns that string into a canonical entity id, applying these rules in
order and logging which one fired:

  R1 given        the adapter already knew the canonical id (curated facts).
  R2 seeded       the name matches a seeded company or component alias.
  R3 identity     the name matches a canonical site or region from the identity
                  source, including the names that source already merged. Sites
                  are deduplicated once, in scripts/build_compute_map.py, by
                  explicit identity rule, coordinate proximity and name-token
                  overlap; this stage consumes those decisions rather than
                  re-deriving them.
  R4 alias        the normalised name equals an existing entity's name or alias
                  of the same type.
  R5 designator   a candidate is rejected when both names carry facility codes
                  and the codes differ: "Equinix DA11" is not "Equinix DA2",
                  however similar the strings look.
  R6 new          nothing matched, so a provisional entity is created and
                  flagged, because a silent merge is worse than a duplicate you
                  can see.

Every fold is written to `data/registry/resolution_log.json` so a surprising
merge can be traced to the rule that caused it.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from . import schema, seeds
from .recognize import Recognizer, norm

DESIGNATOR = re.compile(r"\b([a-z]{2,4}[-\s]?\d{1,3}[a-z]?)\b")
GENERIC_TOKENS = {"data", "center", "centre", "campus", "site", "facility", "phase",
                  "building", "dc", "the", "of", "and", "at", "ai", "cloud", "project"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")


def designators(name: str) -> set[str]:
    return {d.replace(" ", "").replace("-", "") for d in DESIGNATOR.findall(norm(name))}


def display_name(name: str) -> str:
    """Some pipeline records shout ("ORACLE DATA CENTER"); title them while
    leaving acronyms and part numbers alone."""
    if not name or not name.isupper() or len(name) < 5:
        return name
    keep = {"DC", "AI", "US", "UK", "TPU", "GPU", "HPC", "IT", "NVL72", "LLC", "INC"}
    return " ".join(w if (w in keep or any(c.isdigit() for c in w)) else w.capitalize()
                    for w in name.split())


class EntityStore:
    def __init__(self):
        self.entities: dict[str, dict] = {}
        self.recognizer = Recognizer()
        self.by_name: dict[tuple[str, str], str] = {}   # (type, normalised name) -> id
        self.log: list[dict] = []

    # ------------------------------------------------------------------ create
    def add(self, entity_id: str, etype: str, name: str, aliases=(), domains=(),
            summary: str = "", provisional: bool = False) -> dict:
        e = self.entities.get(entity_id)
        if not e:
            e = {"id": entity_id, "type": etype, "name": name, "aliases": set(),
                 "domains": set(), "summary": summary, "provisional": provisional,
                 "params": schema.blank_params(etype), "provenance": {}, "conflicts": {},
                 "sources": set(), "records": [], "documents": set(),
                 "relations": [], "merged_from": set(), "weight": 1.0,
                 "updated": "", "map_id": ""}
            self.entities[entity_id] = e
        if summary and not e["summary"]:
            e["summary"] = summary
        for a in [name, *aliases]:
            if a and norm(a):
                e["aliases"].add(norm(a))
                self.by_name.setdefault((etype, norm(a)), entity_id)
        e["domains"].update(d.lower() for d in domains)
        self.recognizer.add_entity(entity_id, etype, [name, *aliases], domains)
        return e

    # ----------------------------------------------------------------- resolve
    def resolve(self, hint: str, etype: str, *, given: str = "",
                record_id: str = "") -> str | None:
        if given:
            self._note(record_id, given, hint, "R1 given")
            return given if given in self.entities else None
        if not hint or not etype:
            return None
        key = (etype, norm(hint))
        hit = self.by_name.get(key)
        if hit:
            self._note(record_id, hit, hint, "R4 alias"
                       if norm(hit.split(":", 1)[-1]) != norm(hint) else "R2 seeded")
            return hit
        # type-scoped alias lookup over the full index (handles "Microsoft Azure"
        # style strings where the entity name is a substring)
        matches = self.recognizer.match_text(hint, etype)
        for eid, span in matches:
            cand = self.entities[eid]
            if self._designator_clash(hint, cand):
                self._note(record_id, eid, hint, "R5 designator (rejected)")
                continue
            # a one-token alias inside a much longer facility name is not identity
            if etype in ("datacenter", "cloud_region") and len(norm(hint).split()) > 2 \
                    and len(span.split()) < 2:
                continue
            self._note(record_id, eid, hint, "R4 alias")
            cand["merged_from"].add(hint)
            cand["aliases"].add(norm(hint))
            self.by_name.setdefault(key, eid)
            return eid
        return None

    def resolve_or_create(self, hint: str, etype: str, *, record_id: str = "") -> str | None:
        eid = self.resolve(hint, etype, record_id=record_id)
        if eid:
            return eid
        if not hint or etype not in schema.ENTITY_TYPES:
            return None
        new_id = f"{etype}:{slug(hint)[:60]}"
        if not slug(hint):
            return None
        self.add(new_id, etype, display_name(hint), provisional=True)
        self._note(record_id, new_id, hint, "R6 new")
        return new_id

    def _designator_clash(self, hint: str, candidate: dict) -> bool:
        a = designators(hint)
        b = set().union(*(designators(x) for x in candidate["aliases"])) if candidate["aliases"] else set()
        return bool(a and b and not (a & b))

    def _note(self, record_id: str, entity_id: str, hint: str, rule: str):
        if len(self.log) < 20000:
            self.log.append({"record": record_id, "entity": entity_id,
                             "hint": hint[:120], "rule": rule})


# ---------------------------------------------------------------------------
# seeding and discovery
# ---------------------------------------------------------------------------
def seed(store: EntityStore) -> None:
    for eid, name, aliases, domains in seeds.company_seeds():
        e = store.add(eid, "company", name, aliases, domains)
        e["params"]["category"] = seeds.COMPANY_CATEGORY.get(eid)
        if domains:
            e["params"]["website"] = domains[0]
    for eid, name, aliases in seeds.component_seeds():
        store.add(eid, "component", name, aliases)


def discover(store: EntityStore, records: list[dict], catalog: dict) -> None:
    """Create entities for everything the records talk about.

    Order matters: accelerators and the identity source go first so that later
    records resolve against a populated index instead of minting duplicates.
    """
    # 1. accelerators, from the specification table
    for r in records:
        if r["kind"] != "chip_spec" or r["source"] != "accelerators":
            continue
        short = r["subject_hint"]
        full = r["claims"].get("full_name")
        aliases = [short, full]
        if short.startswith("TPU "):
            aliases += [short.replace("TPU ", "tpu"), short.replace("TPU ", "")]
        store.add(f"accelerator:{slug(short)}", "accelerator", short,
                  [a for a in aliases if a], summary=r.get("context", ""))

    # 2. canonical data centers and cloud regions, from the identity source.
    # Two distinct facilities can share a name — there are two unrelated
    # "Goodnight" sites in the Texas panhandle, one Google and one Crusoe — so a
    # colliding slug is disambiguated by operator rather than silently merged.
    identity = [r for r in records if r["source"] == "compute_map"]
    slug_counts = Counter(f"{r['subject_type']}:{slug(r['claims'].get('canonical_name') or r['subject_hint'])[:60]}"
                          for r in identity)
    for r in identity:
        etype = r["subject_type"]
        name = r["claims"].get("canonical_name") or r["subject_hint"]
        aliases = list(r["claims"].get("aliases") or [])
        merged = list(r["claims"].get("merged_from") or [])
        eid = f"{etype}:{slug(name)[:60]}"
        if slug_counts[eid] > 1:
            qualifier = slug(r["claims"].get("operator") or "") or \
                        (r["claims"].get("map_id") or "").rsplit("-", 1)[-1]
            eid = f"{eid}-{qualifier[:24]}"
        e = store.add(eid, etype, display_name(name), [name, *aliases, *merged])
        e["map_id"] = r["claims"].get("map_id") or ""
        e["merged_from"].update(m for m in merged if norm(m) != norm(name))
        # the identity record knows its own entity; assigning it here stops a
        # same-named neighbour from claiming it through the alias index
        r["subject"] = eid
        store.log.append({"record": r["id"], "entity": eid, "hint": name,
                          "rule": "R3 identity"})

    # 2b. curated accelerator aliases: other tables write the same silicon
    # differently, and each mapping is a judgement recorded with its reason
    for alias, (target, reason) in seeds.ACCELERATOR_ALIASES.items():
        if target in store.entities:
            store.entities[target]["aliases"].add(alias)
            store.by_name.setdefault(("accelerator", alias), target)
            store.recognizer.add_entity(target, "accelerator", [alias])
            store.log.append({"record": "", "entity": target, "hint": alias,
                              "rule": f"R2 seeded (curated alias: {reason})"})

    # 3. countries, wherever they are claimed
    for r in records:
        c = r["claims"].get("country")
        if isinstance(c, str) and c.strip():
            store.add(f"country:{slug(c)}", "country", c.strip(), [c.strip()])

    # 4. remaining subjects: sites and regions no identity source knew about
    for r in records:
        if r.get("subject"):      # an adapter that already knows the id wins
            continue
        etype = r.get("subject_type")
        if etype in ("datacenter", "cloud_region") and r["source"] != "compute_map":
            r["subject"] = store.resolve_or_create(r["subject_hint"], etype,
                                                   record_id=r["id"]) or ""
        elif etype == "component" and r["subject_hint"]:
            r["subject"] = store.resolve(r["subject_hint"], "component",
                                         record_id=r["id"]) or ""


def attach(store: EntityStore, records: list[dict]) -> None:
    """Run recognition over every record and file the results on both sides."""
    from .recognize import Recognizer  # noqa: F401  (documented dependency)
    for r in records:
        hits = store.recognizer.recognise(r)
        r["entities"] = [{"entity": h["entity"], "score": h["score"],
                          "methods": h["methods"]} for h in hits]
        for h in hits:
            e = store.entities.get(h["entity"])
            if not e:
                continue
            e["sources"].add(r["source"])
            if len(e["records"]) < 4000:
                e["records"].append(r["id"])
            e["documents"].update(r.get("documents") or [])
            if r.get("date") and r["date"] > (e["updated"] or ""):
                e["updated"] = r["date"]


def counts(store: EntityStore) -> dict:
    out = defaultdict(int)
    for e in store.entities.values():
        out[e["type"]] += 1
        if e["provisional"]:
            out[e["type"] + "_provisional"] += 1
    return dict(out)
