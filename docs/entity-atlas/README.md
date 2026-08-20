# Entity Atlas

Two views over the same dataset, in one page:

* **Entity grid** — an entity-relation map. Categories are cards, entities are chips,
  and selecting one draws its relations as curves across the grid.
* **Source search** — a search box for entities. Pick as many as you like and every
  source whose recognised entities match is listed; each one opens its own page
  showing exactly how it was linked to those entities.

Open `docs/entity-atlas/index.html`, or serve the folder:

```bash
python3 -m http.server -d docs 8901
# → http://localhost:8901/entity-atlas/index.html
```

No build step and no dependencies — the page loads one `data.json`.

## What it is built from

`scripts/build_entity_atlas.py` reads the datasets this repository already carries
and emits `docs/entity-atlas/data.json`:

| Input | Contributes |
|---|---|
| `docs/compute-map/data.json` | 631 data centers and 53 cloud regions with their operators, tenants, installed chips, countries and **1,255 unique source URLs** |
| `data/accelerators.csv` | 49 accelerators with vendor, launch, memory, throughput and scale-up domain |
| `data/cloud_pricing.csv` | which providers rent which accelerator |
| `data/supply_chain.csv`, `data/bom_costs.csv`, `data/rack_systems.csv` | HBM, CoWoS, NVLink and Ethernet relations |
| `data/mlperf_training.csv`, `data/training_runs.csv` | benchmark and training-run context |
| `data/sources/epoch_ai/data_center_chip_quantities.csv` | Epoch's per-chip observation notes, which carry their own links |

The result: **834 entities in 6 types, 1,850 relations, 1,255 sources and 4,619
entity recognitions.**

## How entity recognition works

Every source URL is examined four ways. Each hit records *which* method found it and
*what* it matched, so a source's page can show its working rather than a bare list of
tags.

| Method | What it means |
|---|---|
| `record` | Named by a field of the dataset record the link was attached to — operator, tenant, country, installed chips. The strongest signal, because the link was filed against that record by the ingesting pipeline. |
| `domain` | The link's host belongs to an entity we track (`nvidia.com` → NVIDIA, `investors.terawulf.com` → TeraWulf). |
| `path` | An entity alias appears in the URL path (`/gb200-nvl72/`, `/stargate-abilene/`). |
| `context` | An alias appears in the text that travelled with the link — the record's name, an Epoch observation note, or a cloud region description. |

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
(HBM and CoWoS) · `fabric` (accelerator → NVLink or Ethernet) · and `co-cited`, which
appears when two entities of different types are recognised together in at least three
sources. Co-citation links are hidden by default — the checkbox in the grid toolbar
turns them on.

## Reading the interface

**Grid tab.** Click a chip to select it: curves fan out to its related entities,
everything unrelated dims, the left rail becomes a "Connected to …" list grouped by
relation verb, and the right rail shows the entity — its metrics, the aliases it is
recognised by, its relations, and the sources that mention it. A card header's
`show all` expands that category to its full membership. Cards can be filtered with
the box at the top left, and hidden entirely by clicking a legend row.

**Search tab.** Type to get entity suggestions with their source counts, press Enter or
click to add a chip, and repeat for as many entities as you want. `Any of` widens,
`All of` narrows to sources that mention every selected entity. Kind pills filter to
news, vendor documents, filings, registries, government records, datasets and pricing
pages. Clicking a result opens its page: the recognition table, the datasets that cite
it, the context that travelled with the link, the records it was attached to, and other
sources that share at least two entities with it.

Both tabs stay in one page and every state is linkable: `#grid/nvidia`,
`#search/anthropic,chip:tpu-v7?all`, `#source/src-000123`.

## Caveats

* **Titles are derived from the URL.** These datasets store bare links, not headlines,
  so the title you see is a humanised URL slug. The source page says so explicitly.
* **Recognition is dictionary matching, not a language model.** It is precise about
  entities we know and silent about entities we do not. A source can be about a company
  that never enters this atlas.
* **`record` hits inherit the ingesting pipeline's judgement.** If dataCenterView filed
  a link against the wrong campus, the recognition follows it. The source page shows the
  attached record so that judgement is visible rather than hidden.
* **Registry links dominate by count.** 498 of the 1,255 sources are directory entries
  (PeeringDB and similar) attached to colocation records. They are down-weighted in
  relevance ranking but not removed, because they are what the underlying dataset cites.

## Rebuilding

```bash
python3 scripts/build_compute_map.py     # sites and their sources
python3 scripts/build_entity_atlas.py    # entities, relations, recognition
```

The build prints entity, relation and source counts plus the breakdown by type, kind
and dataset, so a bad alias shows up as an implausible count immediately.
