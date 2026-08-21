# Understanding-GPU

Two things live here:

**1. A field guide to AI accelerators** — how GPUs and TPUs work, why they are built differently, what every current accelerator's specifications actually are, what they cost, who can get them, and how they compare.

**→ Read the report: [`report/report.md`](report/report.md)** (about 21,500 words, 24 figures, 13 data-generated tables)
**→ HTML version: [`docs/index.html`](docs/index.html)** — open locally, or serve with `python3 -m http.server -d docs`

**2. An interactive global compute map** — where that hardware physically is, operating and planned, drilling from continent to country to individual data center with sources attached to every site.

**→ Open the map: [`docs/compute-map/index.html`](docs/compute-map/index.html)** ([how it works](docs/compute-map/README.md))

**3. An entity atlas** — the entity-relation grid behind both, a catalogue of every data source with real example records, and a search over every cited document showing how each one was recognised as being about which companies, accelerators and data centers.

**→ Open the atlas: [`docs/entity-atlas/index.html`](docs/entity-atlas/index.html)** ([how it works](docs/entity-atlas/README.md))

**4. A standardised data pipeline** — 15 catalogued sources produce 3,606 dated records, which fill the typed parameters of 843 entities, each parameter naming the record and source behind it. Adding, changing or removing a data source is a catalog entry plus an adapter function.

**→ Read the design: [`docs/DATA-PIPELINE.md`](docs/DATA-PIPELINE.md)**

Everything is generated from the datasets in [`data/`](data/), so any number can be traced, corrected and re-plotted.

## What is in the report

| Part | Contents |
|---|---|
| 1–3 | How a GPU works (SMs, warps, caches, TMA, NVLink), how a TPU works (systolic arrays, scratchpads, SparseCore, optical circuit switches), and the six differences that actually matter |
| 4 | The arithmetic of LLM training on real hardware: the 6ND rule, memory accounting, roofline and the ~300 FLOP/byte wall, parallelism versus fabric bandwidth, MFU expectations, reliability at scale |
| 5–8 | Per-accelerator catalogue: NVIDIA V100 → Rubin, AMD MI250X → MI455X, Intel Gaudi, Huawei Ascend, Google TPU v2 → 8t/8i, AWS Trainium, Meta MTIA, Microsoft Maia, Cerebras, Groq, SambaNova, Tenstorrent |
| 9 | Head to head: normalised comparisons, efficiency per watt, what MLPerf Training v6.0 says and eight ways it misleads |
| 10 | Supply and price: bill-of-materials estimates, CoWoS and HBM chokepoints, cloud rental pricing across 14 providers, TCO models, export controls |
| 11–12 | A decision procedure for choosing hardware, then methodology, conflicting numbers and explicit unknowns |

## What is on the map

| Level | Grouping | Click to |
|---|---|---|
| World | Continent bubbles | Zoom to a continent |
| Continent | Country bubbles | Zoom to a country |
| Country | Individual data centers and cloud regions | Open a site's capacity, chips, provenance and sources |

631 physical sites and 53 cloud regions, covering both **currently available** and **planned** capacity, built from four sources: the uploaded **dataCenterView** project (490 US sites, 1,115 source URLs), **Epoch AI**'s frontier data-center dataset (83 sites with modelled power, chip counts and forward timelines, CC-BY), **95 curated non-US sites** across 31 countries, and **53 cloud regions** documenting where TPU, Trainium and GPU SKUs can actually be rented. Records describing the same campus are merged into one site — `xAI Colossus 2` and `Colossus 2`, or the five records behind `OpenAI Stargate Abilene` — with the merge reason and every contributing source shown in the panel. See [`docs/compute-map/README.md`](docs/compute-map/README.md) for the deduplication rules and the coverage caveats.

## What is in the entity atlas

| View | Contents |
|---|---|
| Entity grid | 834 entities in 6 types (company, accelerator, data center, cloud region, supply chain, country) and 1,850 derived relations; select any entity to draw its relations across the grid |
| Source search | 1,255 unique source URLs with 4,619 entity recognitions; pick any number of entities and every matching source is listed, each opening its own page |

Each source page shows **how** it was linked to each entity — `record` (a field of the dataset record it was filed against), `domain` (the host belongs to that entity), `path` (an alias in the URL), or `context` (an alias in the text that travelled with the link) — together with the matched span, the datasets that cite it, and the records it was attached to.

## Repository layout

```
data/                        report datasets (specs, pricing, benchmarks, BOM, supply chain)
data/compute_map/            map datasets (curated sites, cloud regions, identity rules)
data/sources/epoch_ai/       Epoch AI AI-Data-Centers CSVs (CC-BY 4.0)
scripts/theme.py             shared plotting style, vendor palette, drawing helpers
scripts/fig_diagrams.py      8 architecture diagrams drawn from primitives
scripts/fig_data.py          16 plots computed from the CSVs
scripts/tables.py            markdown tables generated from the CSVs
scripts/build_site.py        assembles report/report.md and docs/index.html
scripts/geocode_sites.py     geocodes Epoch addresses into a committed cache
scripts/build_compute_map.py normalises, dedupes and rolls up the map dataset
pipeline/atlas/              the source -> record -> entity pipeline (schema, catalog,
                             adapters, recognition, resolution, filling, validation)
data/registry/               sources.json, records.json, entities.json, resolution_log.json
report/sections/             the report source, one markdown file per section
report/report.md             the assembled single-file report
report/figures/              24 generated PNGs
docs/index.html              the report as an HTML site
docs/compute-map/            the interactive map (D3 + topojson vendored locally)
docs/entity-atlas/           the entity grid, data-source catalogue and document search
docs/DATA-PIPELINE.md        how sources, records and entities are defined and built
references/                  the uploaded dataCenterView project and UI reference
```

## Reproducing

```bash
pip install -r requirements.txt
python3 scripts/build_site.py --figures      # regenerate every figure, then the report and site
python3 scripts/build_site.py                # rebuild the report and site only
python3 scripts/tables.py                    # print the generated tables
python3 scripts/build_compute_map.py         # rebuild the map dataset from all four sources
python3 -m pipeline.atlas.build               # rebuild the registry and the atlas bundles
python3 -m http.server -d docs 8901          # serve the report and the map
```

## Conventions the report follows

- **Dense FLOPS only.** Vendor headline figures that assume 2:1 structured sparsity have been halved. Meta has publicly confirmed that sparsity is not used in its production models because of quality loss.
- **Every claim is labelled** `confirmed` (vendor datasheet, filing, earnings call, official price list, peer-reviewed paper, MLCommons result), `estimate` (named analyst, or derived here from confirmed inputs), or `rumor` (single-source channel check).
- **Unpublished values stay blank.** They render as em-dashes rather than being interpolated. Section 12.3 lists what nobody has published.
- **Conflicting figures are recorded, not averaged.** Section 12.2 tabulates 20 disagreements you will encounter in the literature, with the value used here.

To correct a number, edit the CSV row (the confidence column is required) and re-run the build. Every table and figure that depends on it updates, so the prose and the plots cannot drift apart.
