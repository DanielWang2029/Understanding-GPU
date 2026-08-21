# The data pipeline: sources, records, entities

Everything the Entity Atlas and the compute map display comes from one pipeline
with three layers and one direction of travel:

```
 SOURCE                RECORD                        ENTITY
 where data            one dated observation          a resolved thing whose typed
 comes from      →     extracted from a source   →    parameters are filled from
 (15 catalogued)       (3,606, each with claims)      records (843, with provenance)
```

The point of the arrangement is that adding, changing or removing data is a local
edit. A new data source is a catalog entry plus an adapter function; nothing else
in the pipeline changes. A new entity parameter is a line in a schema table. A
correction to how two names get merged is a rule, applied once, logged.

Build it with:

```bash
python3 -m pipeline.atlas.build
```

It takes under a second and writes both the registry and the UI bundles.

---

## 1. What lives where

| Path | Contents |
| --- | --- |
| `pipeline/atlas/schema.py` | The contract: every field of every layer, and the default parameter set of each entity type. |
| `pipeline/atlas/catalog.py` | The source catalog, hand-maintained. One entry per data source, plus curated entity facts. |
| `pipeline/atlas/adapters.py` | One function per source: its native shape → records. |
| `pipeline/atlas/recognize.py` | The alias index and the four recognition channels. |
| `pipeline/atlas/resolve.py` | Which mentions are the same entity, and the rules that decide. |
| `pipeline/atlas/fill.py` | How a record becomes a filled entity parameter. |
| `pipeline/atlas/relate.py` | Relations, derived from filled parameters. |
| `pipeline/atlas/validate.py` | The gates a build must pass, and parameter coverage. |
| `pipeline/atlas/documents.py` | The evidence layer: individual cited URLs. |
| `pipeline/atlas/build.py` | Runs the stages in order and emits everything. |
| `data/registry/sources.json` | The catalog with measured statistics and sample record ids. |
| `data/registry/records.json` | Every record, with its recognition results. |
| `data/registry/entities.json` | Every entity, with filled parameters, provenance and conflicts. |
| `data/registry/resolution_log.json` | Which rule folded which name into which entity. |
| `docs/entity-atlas/data.json` | UI bundle: entities, relations, documents. |
| `docs/entity-atlas/sources.json` | UI bundle: the Data sources tab, with example records. |

---

## 2. Layer 1 — sources

A **source** is an origin of data: a pipeline, a published dataset, a set of
documents, an API, a registry, or one of our own derived tables. There are 15,
declared in `catalog.py`. This is the only file you edit to add one.

### Default parameters of a source

Every source carries all of these. The first group is identity and access, the
second is what it is good for, the third is judgement, and the last is measured
by the builder rather than written by hand.

| Parameter | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable slug. Every record names it. |
| `name` | yes | Human name. |
| `publisher` | yes | Who publishes it. |
| `kind` | yes | `pipeline`, `dataset`, `document-set`, `api`, `derived` or `registry`. |
| `url` | yes | Landing page or file. |
| `adapter` | yes | The function in `adapters.py` that ingests it. |
| `access` | | `download`, `api`, `zip`, `repo`, `manual`, `derived`. |
| `format` | | `csv`, `json`, `zip`, `html`, `markdown`, `mixed`. |
| `local_path` | | Where the snapshot lives in this repository. |
| `licence` | | Licence or terms. |
| `attribution` | | The citation string to reproduce. |
| `retrieved` | | ISO date of the snapshot. |
| `cadence` | | `static`, `ad-hoc`, `monthly`, `quarterly`, `continuous`. |
| `scope` | | One line: geography, topic, period. |
| `record_kinds` | yes | Which record kinds it may produce. Validation enforces this. |
| `entity_types` | | Which entity types it can create or describe. |
| `fills` | yes | Dotted paths it can populate, e.g. `datacenter.power_mw`. May be empty for evidence-only sources. |
| `trust` | yes | 0-1, the tie-breaker when two sources claim the same parameter. |
| `confidence_default` | | Confidence stamped on records that lack their own. |
| `caveats` | | What it is known to get wrong or omit. |
| `sample` | measured | Record ids the UI shows as example data. |
| `stats` | measured | `{records, documents, entities, record_kinds{}}`. |

### The trust scale

`trust` is a judgement about who is in a position to know, not about whether we
like the number:

| Trust | Who | Sources here |
| --- | --- | --- |
| 0.95 | The party itself, in a document of record | `mlperf` |
| 0.80 | A provider's own API or docs about its own service | `provider_docs` |
| 0.70 | A research dataset or document set with a stated method | `curated_global`, `training_runs` |
| 0.60 | Our own derived tables: transparent, but second-hand | `accelerators`, `cloud_pricing`, `rack_systems`, `compute_map` |
| 0.45-0.55 | Modelled estimates over inference | `epoch_*`, `datacenterview`, `supply_chain`, `bom_costs` |
| 0.30 | Aggregators with no stated method | none currently |

### The 15 sources

| Source | Kind | Trust | Records | Produces |
| --- | --- | --- | --- | --- |
| `epoch_timelines` | dataset | 0.45 | 980 | site_capacity, site_compute |
| `datacenterview` | pipeline | 0.55 | 890 | site_profile, citation |
| `compute_map` | derived | 0.60 | 719 | site_profile, geo_profile |
| `epoch_datacenters` | dataset | 0.45 | 249 | site_profile, site_capacity, site_compute |
| `curated_global` | document-set | 0.70 | 244 | site_profile, site_capacity, site_compute |
| `epoch_chips` | dataset | 0.45 | 225 | chip_inventory |
| `cloud_pricing` | derived | 0.60 | 59 | chip_price |
| `provider_docs` | api | 0.80 | 53 | region_availability |
| `accelerators` | derived | 0.60 | 49 | chip_spec |
| `curated_manual` | derived | 0.65 | 45 | citation |
| `supply_chain` | derived | 0.45 | 32 | supply_metric |
| `mlperf` | derived | 0.95 | 29 | benchmark_result |
| `training_runs` | derived | 0.70 | 14 | training_run |
| `rack_systems` | derived | 0.60 | 12 | supply_metric |
| `bom_costs` | derived | 0.45 | 6 | cost_model |

Two sources deserve a note on their role:

- **`compute_map`** is the *identity source*. Data-center deduplication —
  coordinate proximity, identity rules, name-token overlap, facility-code guards
  — is solved once in `scripts/build_compute_map.py`. The registry consumes those
  decisions instead of re-deriving them, so the map and the atlas can never
  disagree about what counts as one site.
- **`curated_manual`** holds attributes no dataset here carries: a company's
  founding year, chief executive, headquarters and ticker, and a component's
  category, role and constraint. These are the only values in the registry with
  no document behind them, and they are labelled as such.

---

## 3. Layer 2 — records

A **record** is one dated observation about one subject, expressed as claims.
Records are the only way a value reaches an entity. They are never edited by
hand: they are what an adapter produced from a source.

### Default parameters of a record

| Parameter | Required | Meaning |
| --- | --- | --- |
| `id` | yes | `<source>-<kind>-<n>`, stable across builds for stable input. |
| `source` | yes | The source id it came from. |
| `kind` | yes | One of the record kinds below. |
| `claims` | yes | `{field: value}` payload. Field names match entity parameters where the record is about an entity attribute. |
| `confidence` | yes | `confirmed`, `estimate` or `rumor`. |
| `entities` | yes | Every entity recognised in it, with method and matched span. |
| `date` | key present | The date the observation refers to; empty when undated. |
| `subject` | key present | The entity it is primarily about, once resolved. |
| `subject_hint` | | The raw subject name before resolution, kept for auditing. |
| `subject_type` | | Which entity type the subject should be. |
| `retrieved` | | When the source snapshot was taken. |
| `units` | | `{field: unit}` for numeric claims. |
| `documents` | | URLs evidencing the record. |
| `context` | | Text that travelled with it, capped at 400 characters. |
| `raw_ref` | | Pointer back into the source: file plus row or key. |

### Record kinds

| Kind | Count | Meaning |
| --- | --- | --- |
| `site_profile` | 1,352 | Identity, location, operator and status of a data center. |
| `site_compute` | 667 | Installed or planned accelerators and H100-equivalents at a site. |
| `site_capacity` | 628 | Power capacity at a date, current or planned. |
| `citation` | 445 | A document offered as evidence, with no numeric payload of its own. |
| `chip_inventory` | 225 | A count of one chip type at one site on one date. |
| `chip_price` | 59 | A rental or purchase price. |
| `region_availability` | 53 | Which accelerators a cloud region offers. |
| `chip_spec` | 49 | Specification of an accelerator part. |
| `supply_metric` | 44 | A supply-chain quantity: capacity, share, price, shipments. |
| `geo_profile` | 35 | Geography of a place: ISO code, continent. |
| `benchmark_result` | 29 | A time-to-train or throughput result. |
| `training_run` | 14 | Compute, hardware and duration of a published training run. |
| `cost_model` | 6 | A modelled bill of materials. |

### Confidence

`confirmed` (468 records) means the party in a position to know said it: a vendor
datasheet, a filing, an official price list, a benchmark body, a peer-reviewed
paper. `estimate` (3,124) means a named analyst or model, or arithmetic derived
here from confirmed inputs. `rumor` (14) means a single-source channel check.

The distribution is itself a finding: most of what is publicly knowable about AI
data centers is modelled, not disclosed.

---

## 4. Layer 3 — entities

An **entity** is a resolved thing. Its type determines the set of default
parameters it carries, and it carries *all* of them — `null` where nothing has
filled it, because "nobody has published this" is information worth showing.

### Common fields

| Field | Meaning |
| --- | --- |
| `id` | `<type>:<slug>`. |
| `type` | `company`, `accelerator`, `datacenter`, `cloud_region`, `component`, `country`. |
| `name`, `aliases` | Canonical name, and every spelling it is recognised by. |
| `params` | The typed default parameter set, every key present. |
| `provenance` | `{param: {source, record, confidence, as_of, unit, note}}`. |
| `conflicts` | `{param: [{value, source, confidence, as_of}]}` where sources disagreed. |
| `params_extra` | Claims no default parameter covers, kept rather than dropped. |
| `sources`, `records`, `documents` | What mentions it. |
| `relations` | Indices into the relations array. |
| `merged_from` | Names folded into it by resolution. |
| `provisional` | True when it was created by rule R6 and nothing has confirmed it. |
| `weight` | 1-10 display weight: own scale plus evidence volume. |
| `updated` | The latest observation date across its records. |

### How a parameter gets filled

Every parameter declares how it is obtained:

- **`record`** — a source claimed it. Candidates are records whose subject is this
  entity and whose claims contain the parameter name. The winner is chosen by
  source trust, then confidence rank, then observation recency.
- **`derived`** — the pipeline computes it from the resolved graph (how many sites
  a company operates, how many chips of a part are deployed). Derivations are
  pure functions of other layers.
- **`manual`** — curated in `catalog.MANUAL_FACTS`, which reaches the fill stage
  as records from `curated_manual`, so it goes through the same precedence
  machinery and is auditable the same way.

Two refinements matter for time series. Several sources publish rows dated years
ahead, so a parameter describing the present ignores future-dated candidates
(`power_mw`, `h100e`, `capex_usd_b`, `accelerators_installed`), and a parameter
describing full build takes the *peak* of the series rather than whatever row
sorts last (`power_mw_planned`, `h100e_planned`, `accelerators_planned`). Without
this, summing site power across a country double-counts a 2030 projection as if
it were energised today.

### company

Coverage: 61 entities, 53.8% of parameters filled.

| Parameter | Unit | Fill | Meaning |
| --- | --- | --- | --- |
| `role` | | record | What it does in this market. |
| `category` | | record | vendor, operator, colocation, neocloud, hyperscaler, lab, supplier, foundry, research. |
| `founded` | year | manual | Year founded. |
| `ceo` | | manual | Chief executive. |
| `headquarters` | | manual | City, country of head office. |
| `country` | | manual | Country of incorporation. |
| `ticker` | | manual | Listed ticker, if public. |
| `website` | | record | Primary domain. |
| `sites_operated` | count | derived | Data centers it operates in the registry. |
| `sites_tenanted` | count | derived | Data centers where it is tenant or end user. |
| `power_mw_operated` | MW | derived | Planned power across sites it operates. |
| `accelerators_designed` | count | derived | Accelerator parts it designs. |

### accelerator

Coverage: 49 entities, 73.9%.

| Parameter | Unit | Fill | Meaning |
| --- | --- | --- | --- |
| `vendor`, `family`, `role` | | record | Designer, architecture family, training/inference. |
| `launch` | | record | Launch quarter or year. |
| `process` | | record | Fabrication node. |
| `memory_gb`, `memory_type` | GB | record | On-package memory and its technology. |
| `memory_bw_tbs` | TB/s | record | Memory bandwidth. |
| `dense_bf16_tflops` | TFLOP/s | record | Dense BF16/FP16 throughput. |
| `dense_fp8_tflops` | TFLOP/s | record | Dense FP8 throughput. |
| `dense_fp4_tflops` | TFLOP/s | record | Dense FP4 throughput. |
| `tdp_w` | W | record | Board or module power. |
| `scaleup_bw_gbs` | GB/s | record | Scale-up fabric bandwidth per chip. |
| `scaleup_domain` | chips | record | Chips in one coherent domain. |
| `unit_price_usd` | USD | record | Street or list price per chip. |
| `cheapest_rental_usd_hr` | USD/hr | derived | Lowest observed rental rate, with the provider and tier in the note. |
| `deployed_units` | chips | derived | Units counted across sites in the registry. |
| `sites_deployed` | count | derived | Sites known to run it. |

### datacenter

Coverage: 635 entities, 60.4%.

| Parameter | Unit | Fill | Meaning |
| --- | --- | --- | --- |
| `operator` | | record | Company running the facility. |
| `tenant` | | record | Tenant or end user of the capacity. |
| `status` | | record | operating, expanding, under_construction, planned, announced, cancelled. |
| `country`, `region`, `city` | | record | Where it is. |
| `lat`, `lon` | deg | record | Coordinates. |
| `coord_precision` | | record | site, street, city, county, state, country — how much the coordinates mean. |
| `power_mw` | MW | record | Energised IT power. |
| `power_mw_planned` | MW | record | IT power at full build. |
| `accelerators_installed` | chips | record | `{chip: units}` counted on site. |
| `accelerators_planned` | chips | record | `{chip: units}` planned. |
| `h100e` | chips | record | H100-equivalents installed. |
| `h100e_planned` | chips | record | H100-equivalents at full build. |
| `first_operational` | year | record | Year the site first carried load. |
| `capex_usd_b` | USD bn | record | Modelled or announced capital cost. |
| `category` | | record | hyperscaler, neocloud, wholesale_colo, retail_colo, developer, enterprise, frontier, other. |

### cloud_region

Coverage: 53 entities, 100%.

`provider`, `region_id`, `label`, `city`, `country`, `lat`, `lon`,
`accelerators`, `detail`, `status`. A region is a metro, not a building:
providers publish where a SKU can be provisioned, never how many chips are
installed.

### component

Coverage: 10 entities, 60%.

`category` (memory, packaging, fabric, power, cooling, optics), `role`,
`suppliers` (derived from supply-share records), `consumed_by` (derived from
cost-model and rack records), `unit_price_usd`, `constraint` — why it gates
supply, if it does.

### country

Coverage: 35 entities, 67.2%.

`iso3` and `continent` come from the identity source; `sites`, `power_mw`,
`power_mw_planned`, `h100e`, `cloud_regions` and `accelerator_families` are
derived by aggregating the country's resolved sites and regions.

---

## 5. The entity recognition pipeline

Recognition answers "which entities does this record talk about". It runs over
every record from every source in exactly the same way — this is the part that
used to be re-implemented per dataset, and no longer is.

### Four channels

| Channel | Score | Evidence |
| --- | --- | --- |
| `field` | 1.2 | A claim field names the entity: operator, tenant, provider, vendor, owner, user, country, chip type, platform, hardware. The strongest signal, because the source filed the claim against that value. |
| `domain` | 1.0 | An evidencing document's host belongs to the entity. |
| `path` | 0.9 | An alias appears in a document's URL path. |
| `text` | 0.7 | An alias appears in free text attached to the record — a title, an observation note, a region description. |

Scores add across channels, and a hit is kept at 0.7 or above, so a single weak
text match survives but is visibly weaker than a field match. Each hit keeps the
method and the matched span, which is what the atlas shows in its "how it was
recognised" table. The result: 8,242 entity references across 3,606 records,
and 8,581 entity parameters filled with a named source behind each one.

Two guards keep the channels honest. Aliases that fire on almost any page are
never evidence by themselves (`meta`, `aws`, `ai`, `data`, `center`, and others in
`STOP_ALIASES`). Hosts that carry no entity information — file lockers, archives,
social posts, Wikipedia — cannot produce a `domain` hit, though they can still be
cited.

Matching itself is an n-gram dictionary lookup rather than a scan over a thousand
regexes: aliases are indexed by word count, the text is tokenised, and the
longest alias wins with each entity reported once. That is what keeps a full
build under a second.

### Resolution: deciding two names are one entity

Recognition finds mentions; resolution decides identity. Six rules, applied in
order, each logged to `data/registry/resolution_log.json` with the record and the
name that triggered it.

| Rule | Fired | What it does |
| --- | --- | --- |
| **R1 given** | — | The adapter already knew the canonical id (curated facts). |
| **R2 seeded** | 86 + 20 curated aliases | The name matches a seeded company or component alias, or a curated accelerator alias. |
| **R3 identity** | 719 | The name matches a canonical site or region from the identity source, including names that source already merged. |
| **R4 alias** | 2,306 | The normalised name equals an existing entity's name or alias *of the same type*. |
| **R5 designator** | guard | Rejects a candidate when both names carry facility codes and the codes differ: `Equinix DA11` is not `Equinix DA2`. |
| **R6 new** | 5 | Nothing matched, so a provisional entity is created and flagged. |

Three principles are worth stating because they are easy to get wrong:

1. **A visible duplicate beats a silent merge.** R6 creates a flagged provisional
   entity rather than guessing. Five exist today, all data centers that appear in
   Epoch's chip table under a name no other source uses.
2. **Identical names are not identical things.** There are two unrelated
   "Goodnight" sites in the Texas panhandle, one Google and one Crusoe, five
   kilometres apart. Site identity is keyed on the identity source's stable id,
   and a colliding slug is disambiguated by operator.
3. **Aliasing across SKUs is a judgement, so it is written down.** Twenty
   accelerator aliases each carry their reason — `gb200 nvl72` is the rack form
   of the same silicon as `B200 NVL72`; `mi350x` is the air-cooled SKU of the
   MI355X die. Names that are genuinely different parts are left unmapped rather
   than merged.

Geographic deduplication of data centers is *not* repeated here. It happens once,
in `scripts/build_compute_map.py`, using explicit identity rules, coordinate
proximity with a facility-code guard, and name-token overlap that strips metro and
generic words. The registry treats the result as the identity source.

### Relations

Relations are never authored; each is a function of a filled parameter, so every
edge can name the source and record behind it. `accelerator.vendor` becomes
*designs*, `datacenter.operator` becomes *operates*, `datacenter.country` becomes
*located in*, and so on. Priced offers, supply shares, cost models, training runs
and benchmark submissions add their own verbs. Co-citation adds an edge where two
entities of different types are recognised in three or more shared documents.

Today: 683 *located in*, 663 *co-cited*, 260 *operates*, 172 *tenant of*, 113
*deploys*, 80 *rentable in*, 46 *operates region*, 37 *designs*, 22 *rents out*,
12 *consumes*, 7 *trained on*, 6 *submitted result*, 3 *supplies*.

---

## 6. Validation

`validate.py` runs on every build. **Errors fail the build**: a missing required
field, an unknown record kind, a source claiming to fill a parameter that does not
exist, an entity missing one of its type's default parameters or carrying one that
is not declared, provenance naming a source or record that does not exist,
provenance attached to an empty parameter, a relation index out of range.

**Warnings** are printed and counted, because some of them describe the data
rather than the code — a site nobody has published power for is a fact about the
world. Conflicts are not warnings: 269 parameters currently have a competing value
from another source, and that is the system working.

The build also prints **parameter coverage** per type: the share of each type's
default parameters that carry a value. This is the number to watch when adding a
source; it should go up.

---

## 7. How to change things

**Add a data source.** Append an entry to `CATALOG` in `catalog.py`, then write
`ingest_<name>(source)` in `adapters.py` returning records whose claim keys match
entity parameter names. Run the build: validation will tell you if the catalog
promises something the adapter does not deliver. The Data sources tab picks it up
with no UI change.

**Remove a data source.** Delete its catalog entry. Its records, and any parameter
it filled, disappear on the next build; another source's claim takes over
wherever one exists, and coverage shows what was lost.

**Add an entity parameter.** Add it to the type's table in `schema.ENTITY_PARAMS`
with a description, unit and fill mode. Every entity of that type gains the key
immediately, empty until a source fills it. If a source already claims it, add
the path to that source's `fills`.

**Add an entity type.** Add it to `ENTITY_TYPES`, give it a parameter table, teach
`resolve.discover` how to create it, and add a UI type mapping in `build.py`.

**Correct a bad merge.** Look up the name in `resolution_log.json` to find the
rule that fired. A wrong site merge belongs in
`data/compute_map/identity_rules.csv`; a wrong accelerator alias belongs in
`seeds.ACCELERATOR_ALIASES`; a bad company alias belongs in `seeds.COMPANIES` or
`recognize.STOP_ALIASES`.

**Add a curated fact.** Put it in `catalog.MANUAL_FACTS` keyed by entity id. It
becomes a record from `curated_manual` and is labelled in the UI as having no
document behind it.

---

## 8. What this deliberately does not do

- It does not invent values. A parameter with no record stays `null` and the atlas
  says "nothing published for" it.
- It does not reconcile disagreements silently. When sources conflict, the winner
  is chosen by trust and the losers are kept in `conflicts` and shown in the UI.
- It does not promote an estimate to a fact. Confidence travels from the record to
  the parameter's provenance and is displayed next to the value.
- It does not merge on similarity alone. Every merge is a rule with a name, and
  every rule application is logged.
