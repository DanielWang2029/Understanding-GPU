# Entity Atlas

Three views over one registry, in a single page:

* **Entity grid** — an entity-relation map. Categories are cards, entities are chips,
  and selecting one draws its relations as curves across the grid. The right rail shows
  the entity's typed parameters with the source that filled each one.
* **Data sources** — every catalogued data source, line by line. Opening one shows what
  it fills, what it should not be trusted for, and real example records it produced with
  the entities each was labelled with.
* **Document search** — a search box for entities. Pick as many as you like and every
  cited document whose recognised entities match is listed; each one opens its own page
  showing exactly how it was linked to those entities.

The vocabulary is the registry's: a **source** is where data comes from (15 of them), a
**document** is one cited URL inside a source (1,327), and an **entity** is a resolved
thing whose parameters were filled from **records** (3,606). The full design is in
[../DATA-PIPELINE.md](../DATA-PIPELINE.md).

Open `docs/entity-atlas/index.html`, or serve the folder:

```bash
python3 -m http.server -d docs 8901
# → http://localhost:8901/entity-atlas/index.html
```

No build step and no dependencies — the page loads `data.json` and `sources.json`.

## What it is built from

`python3 -m pipeline.atlas.build` reads the sources catalogued in
`pipeline/atlas/catalog.py` and emits the registry under `data/registry/` plus the two
UI bundles here. The sources:

| Input | Contributes |
|---|---|
| `docs/compute-map/data.json` | the identity layer: 631 data centers and 53 cloud regions with the merge decisions already made, plus their coordinates and cited URLs |
| `references/datecenterview-main.zip` | 490 US data-center records with field-level provenance, and 400 news citations |
| `data/sources/epoch_ai/*.csv` | 83 frontier sites, 492 dated build observations and 225 per-site chip counts |
| `data/compute_map/curated_sites.csv` | 95 sites in 31 countries that Epoch does not cover, each with its own sources |
| `data/compute_map/accelerator_regions.csv` | 53 cloud regions and the accelerators each can provision |
| `data/accelerators.csv` | 49 accelerators with vendor, launch, memory, throughput and scale-up domain |
| `data/cloud_pricing.csv` | which providers rent which accelerator |
| `data/supply_chain.csv`, `data/bom_costs.csv`, `data/rack_systems.csv` | HBM, CoWoS, NVLink and Ethernet relations |
| `data/mlperf_training.csv`, `data/training_runs.csv` | benchmark and training-run context |
| `data/sources/epoch_ai/data_center_chip_quantities.csv` | Epoch's per-chip observation notes, which carry their own links |

The result: **843 entities in 6 types, 2,104 relations, 1,327 documents, 8,242 entity
recognitions and 8,581 entity parameters filled with a named source behind each.**

## How entity recognition works

Every source URL is examined four ways. Each hit records *which* method found it and
*what* it matched, so a source's page can show its working rather than a bare list of
tags.

| Method | What it means |
|---|---|
| `field` | Named by a claim field of the record — operator, tenant, country, chip type, vendor. The strongest signal, because the source filed the claim against that value. |
| `domain` | An evidencing document's host belongs to an entity we track (`nvidia.com` → NVIDIA, `investors.terawulf.com` → TeraWulf). |
| `path` | An entity alias appears in a document's URL path (`/gb200-nvl72/`, `/stargate-abilene/`). |
| `text` | An alias appears in the text that travelled with the record — its subject name, an Epoch observation note, or a cloud region description. |

Matching runs over an alias dictionary built from the data itself: canonical company
names plus the spellings that actually occur (`SpaceXAI`, `Colossus`, `Macrohard` → xAI),
every accelerator's short and long name, all site names including the `aka` names
produced by the compute map's deduplication, and every country. Aliases are matched on
n-gram boundaries with the longest alias winning, so `TPU v6e` beats `TPU`.

Two deliberate guards keep the output honest:

* **Generic hosts carry no domain evidence.** `drive.google.com`, `web.archive.org`,
  `x.com` and similar are labelled as what they are (a scan, an archive, a post) and
  never produce a `domain` hit, because the host says nothing about which company the
  document concerns.
* **Aliases that would fire everywhere are excluded** — bare `meta`, `aws`, `ai`, `hbm`
  and similar are never evidence on their own.

## Relations

Relations are derived, not hand-drawn. Each carries a weight and the dataset that
evidences it:

`designs` (vendor → accelerator) · `operates` and `tenant of` (company → data center) ·
`deploys` (data center → accelerator) · `located in` (data center or region → country) ·
`rentable in` (accelerator → cloud region) · `operates region` · `rents out`
(provider → accelerator, from the pricing table) · `supplies` and `consumes`
(HBM and CoWoS) · `trained on` · `submitted result` · and `co-cited`, which
appears when two entities of different types are recognised together in at least three
documents. Co-citation links are hidden by default — the checkbox in the grid toolbar
turns them on.

## Reading the interface

**Grid tab.** Click a chip to select it: curves fan out to its related entities,
everything unrelated dims, the left rail becomes a "Connected to …" list grouped by
relation verb, and the right rail shows the entity — its metrics, the aliases it is
recognised by, its relations, and the sources that mention it. A card header's
`show all` expands that category to its full membership. Cards can be filtered with
the box at the top left, and hidden entirely by clicking a legend row.

**Data sources tab.** The left list is every source, ordered by how much of the registry
it accounts for, with a trust bar under each. Opening one shows its licence, snapshot
date, adapter, trust and default confidence, the record kinds it produces, the entity
parameters it fills, its known limits, and example records rendered exactly as the
pipeline stored them — including which entities each record was labelled with and by
which channel.

**Document search tab.** Type to get entity suggestions with their document counts, press Enter or
click to add a chip, and repeat for as many entities as you want. `Any of` widens,
`All of` narrows to sources that mention every selected entity. Kind pills filter to
news, vendor documents, filings, registries, government records, datasets and pricing
pages. Clicking a result opens its page: the recognition table, the data sources that
cite it, the context that travelled with the link, what the citing records claimed, and
other documents that share at least two entities with it.

All three tabs stay in one page and every state is linkable: `#grid/company:nvidia`,
`#sources/epoch_datacenters`, `#search/company:anthropic,accelerator:tpu-v7?all`,
`#doc/doc-000123`.

## Caveats

* **Titles are derived from the URL.** These datasets store bare links, not headlines,
  so the title you see is a humanised URL slug. The source page says so explicitly.
* **Recognition is dictionary matching, not a language model.** It is precise about
  entities we know and silent about entities we do not. A source can be about a company
  that never enters this atlas.
* **`field` hits inherit the ingesting source's judgement.** If dataCenterView filed a
  link against the wrong campus, the recognition follows it. The document page shows the
  claims that cited it, so that judgement is visible rather than hidden.
* **Registry links dominate by count.** 499 of the 1,327 documents are directory entries
  (PeeringDB and similar) attached to colocation records. They are down-weighted in
  relevance ranking but not removed, because they are what the underlying source cites.
* **Most of this data is modelled.** 3,124 of 3,606 records are estimates rather than
  disclosures. Confidence travels from the record to the parameter and is shown beside
  the value.

## Rebuilding

```bash
python3 scripts/build_compute_map.py     # the identity layer: sites and their sources
python3 -m pipeline.atlas.build          # sources, records, entities, relations, documents
```

The build prints per-source record counts, resolution rule counts and parameter coverage
per entity type, and fails on a schema violation, so a bad alias or a mis-declared source
shows up immediately.
