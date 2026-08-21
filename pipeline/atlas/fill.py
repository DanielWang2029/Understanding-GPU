"""Stage 5 — filling: give every entity its typed default parameters.

Each entity type declares a default parameter set in `schema.ENTITY_PARAMS`, and
every entity carries every key of its type — None where nothing filled it,
because "nobody has said" is information worth showing.

A parameter is filled one of three ways, declared per parameter as `fill`:

  record    a source claimed it. Candidates come from records whose subject is
            this entity and whose `claims` contain the parameter name. The winner
            is chosen by, in order: source trust, confidence rank, observation
            recency, then value magnitude as a last-resort tie-break. Losing
            candidates that disagree are kept in `conflicts`.
  derived   the pipeline computes it from the resolved graph — how many sites a
            company operates, how many chips of a part are deployed. Derivations
            live in `DERIVERS` below and are pure functions of other layers.
  manual    curated in `catalog.MANUAL_FACTS`, which reaches this stage as
            records from the `curated_manual` source, so it goes through the same
            precedence machinery and is auditable the same way.

Whatever fills a parameter, `entity["provenance"][param]` records the source,
the record, the confidence and the as-of date. Extra parameters are welcome: a
claim whose key is not in the type's default set is kept in `params_extra`
rather than dropped, so a new field can be added to a source before the schema
catches up.
"""

from __future__ import annotations

import time
from collections import defaultdict

from . import schema

CONFIDENCE_RANK = {"confirmed": 3, "estimate": 2, "rumor": 1}

NOW = time.strftime("%Y-%m-%d")

# Several sources publish a time series that runs into the future: Epoch's build
# timelines carry rows dated years ahead. A parameter describing the present must
# not be filled from a projection, and a parameter describing full build should
# take the peak of the series rather than whatever row happens to sort last.
#
#   asof  candidates dated after today are ignored; the most recent one wins
#   peak  the largest value across the whole series wins, whatever its date
TIME_RULE = {
    "power_mw": "asof", "h100e": "asof", "capex_usd_b": "asof",
    "accelerators_installed": "asof",
    "power_mw_planned": "peak", "h100e_planned": "peak",
    "accelerators_planned": "peak",
}

# For a peak parameter, the present-tense claim it may also read.
PEAK_ALSO = {"power_mw_planned": "power_mw", "h100e_planned": "h100e"}

# Parameters where the claim key differs from the parameter name, or where the
# value needs assembling from several claims.
ALIASED_CLAIMS = {
    "accelerator": {"unit_price_usd": ("unit_price_usd",)},
    "cloud_region": {"accelerators": ("accelerators",)},
}


def _rank(record: dict, source_trust: dict) -> tuple:
    return (source_trust.get(record["source"], 0.3),
            CONFIDENCE_RANK.get(record["confidence"], 1),
            record.get("date") or "",
            1 if record["claims"] else 0)


def fill_from_records(store, records: list[dict], catalog: dict) -> None:
    trust = {sid: s.get("trust") or 0.3 for sid, s in catalog.items()}
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("subject"):
            by_subject[r["subject"]].append(r)

    for entity in store.entities.values():
        spec = schema.ENTITY_PARAMS[entity["type"]]
        recs = sorted(by_subject.get(entity["id"], []),
                      key=lambda r: _rank(r, trust), reverse=True)
        extra: dict[str, dict] = {}

        for param, meta in spec.items():
            if meta.get("fill") == "derived":
                continue
            rule = TIME_RULE.get(param)
            # a peak parameter also reads the present-tense claim, because a
            # timeline row dated 2027 stating 900 MW *is* the plan for full build
            keys = [param] + ([PEAK_ALSO[param]] if rule == "peak"
                              and param in PEAK_ALSO else [])
            candidates = [(r, k) for r in recs for k in keys
                          if r["claims"].get(k) not in (None, "", [], {})]
            if rule == "asof":
                candidates = [(r, k) for r, k in candidates
                              if not r["date"] or r["date"] <= NOW]
            if not candidates:
                continue
            if rule == "peak":
                numeric = [(r, k) for r, k in candidates
                           if isinstance(r["claims"][k], (int, float))]
                if numeric:
                    candidates = [max(numeric, key=lambda rk: rk[0]["claims"][rk[1]])]
            winner, key = candidates[0]
            value = winner["claims"][key]
            entity["params"][param] = value
            entity["provenance"][param] = {
                "source": winner["source"], "record": winner["id"],
                "confidence": winner["confidence"],
                "as_of": winner.get("date") or winner.get("retrieved") or "",
                "unit": meta.get("unit") or winner.get("units", {}).get(key, ""),
                **({"note": f"peak of the {key} series"} if key != param else {}),
            }
            disagreeing = []
            for other, other_key in candidates[1:]:
                v = other["claims"][other_key]
                if _differs(v, value) and len(disagreeing) < 4:
                    disagreeing.append({"value": v, "source": other["source"],
                                        "confidence": other["confidence"],
                                        "as_of": other.get("date") or ""})
            if disagreeing:
                entity["conflicts"][param] = disagreeing

        # claims that no default parameter covers: keep, do not drop
        for r in recs[:60]:
            for key, value in r["claims"].items():
                if key in spec or key in ("aliases", "merged_from", "canonical_name",
                                          "full_name", "chip_detail"):
                    continue
                if key not in extra and value not in (None, "", [], {}):
                    extra[key] = {"value": value, "source": r["source"],
                                  "record": r["id"]}
        if extra:
            entity["params_extra"] = dict(list(extra.items())[:14])


def _differs(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if b == 0:
            return a != 0
        return abs(a - b) / max(abs(b), 1e-9) > 0.1
    return str(a).strip().lower() != str(b).strip().lower()


# ---------------------------------------------------------------------------
# inventories: several records per entity, aggregated rather than picked
# ---------------------------------------------------------------------------
def fill_inventories(store, records: list[dict]) -> None:
    """`accelerators_installed` is a mapping, so it is built from every chip
    inventory record for the site, keeping the latest count per chip type."""
    latest: dict[str, dict[str, tuple[str, float, str]]] = defaultdict(dict)
    planned: dict[str, dict[str, tuple[str, float, str]]] = defaultdict(dict)
    for r in records:
        if r["kind"] != "chip_inventory" or not r.get("subject"):
            continue
        chip, units = r["claims"].get("chip"), r["claims"].get("units")
        if not chip or not units:
            continue
        # a count dated in the future is a plan, not an inventory
        bucket = latest if (not r.get("date") or r["date"] <= NOW) else planned
        prev = bucket[r["subject"]].get(chip)
        if not prev or (r.get("date") or "") >= prev[0]:
            bucket[r["subject"]][chip] = (r.get("date") or "", units, r["id"])

    for param, bucket in (("accelerators_installed", latest),
                          ("accelerators_planned", planned)):
        for site_id, chips in bucket.items():
            e = store.entities.get(site_id)
            if not e or e["type"] != "datacenter":
                continue
            e["params"][param] = {chip: units for chip, (_, units, _) in sorted(chips.items())}
            e["provenance"][param] = {
                "source": "epoch_chips",
                "record": next(iter(chips.values()))[2],
                "confidence": "estimate",
                "as_of": max(d for d, _, _ in chips.values()),
                "unit": "chips",
            }

    # cheapest observed rental per accelerator
    best: dict[str, tuple[float, dict]] = {}
    for r in records:
        if r["kind"] != "chip_price" or not r.get("subject"):
            continue
        price = r["claims"].get("usd_per_chip_hour")
        if not price:
            continue
        cur = best.get(r["subject"])
        if not cur or price < cur[0]:
            best[r["subject"]] = (price, r)
    for chip_id, (price, r) in best.items():
        e = store.entities.get(chip_id)
        if not e or e["type"] != "accelerator":
            continue
        e["params"]["cheapest_rental_usd_hr"] = price
        e["provenance"]["cheapest_rental_usd_hr"] = {
            "source": r["source"], "record": r["id"], "confidence": r["confidence"],
            "as_of": r.get("date") or "", "unit": "USD/hr",
            "note": f"{r['claims'].get('provider')} {r['claims'].get('tier')}",
        }


# ---------------------------------------------------------------------------
# derived parameters: pure functions of the resolved graph
# ---------------------------------------------------------------------------
def fill_derived(store, records: list[dict]) -> None:
    ents = store.entities
    sites = [e for e in ents.values() if e["type"] == "datacenter"]
    chips = [e for e in ents.values() if e["type"] == "accelerator"]
    regions = [e for e in ents.values() if e["type"] == "cloud_region"]

    def note(entity, param, value, basis):
        if value in (None, 0, [], {}):
            return
        entity["params"][param] = value
        entity["provenance"][param] = {"source": "derived", "record": "",
                                       "confidence": "estimate", "as_of": "",
                                       "unit": schema.param_spec(entity["type"], param)
                                                     .get("unit", ""),
                                       "note": basis}

    # company ← sites, power, accelerators designed
    operated, tenanted, power = defaultdict(int), defaultdict(int), defaultdict(float)
    for s in sites:
        for param, bucket in (("operator", operated), ("tenant", tenanted)):
            raw = s["params"].get(param)
            if not isinstance(raw, str):
                continue
            for eid, _ in store.recognizer.match_text(raw, "company"):
                bucket[eid] += 1
                if param == "operator":
                    power[eid] += (s["params"].get("power_mw_planned")
                                   or s["params"].get("power_mw") or 0)
    designed = defaultdict(int)
    for c in chips:
        vendor = c["params"].get("vendor")
        for eid, _ in store.recognizer.match_text(vendor or "", "company"):
            designed[eid] += 1
    for eid, e in ents.items():
        if e["type"] != "company":
            continue
        note(e, "sites_operated", operated.get(eid), "counted across resolved sites")
        note(e, "sites_tenanted", tenanted.get(eid), "counted across resolved sites")
        note(e, "power_mw_operated", round(power.get(eid, 0), 1),
             "sum of planned power at sites it operates")
        note(e, "accelerators_designed", designed.get(eid), "counted in the spec table")

    # accelerator ← deployed units and sites
    units, site_count = defaultdict(float), defaultdict(int)
    for s in sites:
        for chip, n in (s["params"].get("accelerators_installed") or {}).items():
            for eid, _ in store.recognizer.match_text(chip, "accelerator"):
                if isinstance(n, (int, float)):
                    units[eid] += n
                site_count[eid] += 1
    for eid, e in ents.items():
        if e["type"] != "accelerator":
            continue
        note(e, "deployed_units", round(units.get(eid, 0)) or None,
             "sum of per-site chip counts")
        note(e, "sites_deployed", site_count.get(eid), "sites with a count for this part")

    # country ← its sites and regions
    agg = defaultdict(lambda: {"sites": 0, "power": 0.0, "planned": 0.0,
                               "h100e": 0.0, "regions": 0, "families": set()})
    for s in sites:
        country = s["params"].get("country")
        if not isinstance(country, str):
            continue
        cid = f"country:{_slug(country)}"
        a = agg[cid]
        a["sites"] += 1
        a["power"] += s["params"].get("power_mw") or 0
        a["planned"] += s["params"].get("power_mw_planned") or s["params"].get("power_mw") or 0
        a["h100e"] += s["params"].get("h100e") or 0
        for chip in (s["params"].get("accelerators_installed") or {}):
            a["families"].add(str(chip).split()[0])
    for r in regions:
        country = r["params"].get("country")
        if isinstance(country, str):
            agg[f"country:{_slug(country)}"]["regions"] += 1
    for cid, a in agg.items():
        e = ents.get(cid)
        if not e:
            continue
        note(e, "sites", a["sites"], "resolved sites in this country")
        note(e, "power_mw", round(a["power"], 1), "sum of energised power")
        note(e, "power_mw_planned", round(a["planned"], 1), "sum of power at full build")
        note(e, "h100e", round(a["h100e"]), "sum of H100-equivalents")
        note(e, "cloud_regions", a["regions"], "cloud regions in this country")
        note(e, "accelerator_families", sorted(a["families"])[:8], "chip types seen on site")

    # component ← suppliers and consumers, from the relation evidence
    suppliers, consumers = defaultdict(set), defaultdict(set)
    for r in records:
        if r["kind"] == "supply_metric" and r["claims"].get("category") == "hbm_share":
            # a share of HBM shipments is a share of the whole product line, so it
            # names the supplier of both generations shipping in that year
            for eid, _ in store.recognizer.match_text(r["claims"].get("item") or "", "company"):
                for target in ("component:hbm3e", "component:hbm4"):
                    suppliers[target].add(ents[eid]["name"])
        if r["kind"] == "cost_model" and r.get("subject"):
            name = ents.get(r["subject"], {}).get("name")
            if name:
                consumers["component:hbm3e"].add(name)
                consumers["component:cowos"].add(name)
        if r["kind"] == "supply_metric" and r["claims"].get("system"):
            fabric = ("component:nvlink" if "NVL" in str(r["claims"]["system"])
                      else "component:ethernet_ai")
            for eid, _ in store.recognizer.match_text(
                    r["claims"].get("chip_type") or "", "accelerator"):
                consumers[fabric].add(ents[eid]["name"])
    for cid, names in suppliers.items():
        if cid in ents:
            note(ents[cid], "suppliers", sorted(names), "named in supply-share records")
    for cid, names in consumers.items():
        if cid in ents:
            note(ents[cid], "consumed_by", sorted(names)[:12],
                 "named in cost-model and rack records")


def _slug(text: str) -> str:
    from .resolve import slug
    return slug(text)


def weigh(store) -> None:
    """One comparable 1-10 display weight: the entity's own scale plus how much
    evidence stands behind it."""
    for e in store.entities.values():
        p = e["params"]
        if e["type"] == "datacenter":
            base = 1.0 + min(5.0, (p.get("power_mw_planned") or p.get("power_mw") or 0) / 250.0)
        elif e["type"] == "country":
            base = 1.0 + min(4.0, (p.get("sites") or 0) / 8.0)
        else:
            base = {"company": 2.0, "accelerator": 2.5, "cloud_region": 2.0,
                    "component": 2.0}.get(e["type"], 1.0)
        evidence = min(5.0, len(e["documents"]) / 12.0 + len(e["records"]) / 60.0)
        e["weight"] = round(max(1.0, min(10.0, base + evidence)), 2)
