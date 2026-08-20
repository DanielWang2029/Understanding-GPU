# Global AI Compute Map

An interactive 2D world map of AI compute — data centers, GPUs and TPUs, both
operating and planned — that drills from continent to country to individual
site, with every site's sources attached.

Open `docs/compute-map/index.html` directly, or serve the folder:

```bash
python3 -m http.server -d docs 8901
# → http://localhost:8901/compute-map/index.html
```

Everything is vendored (D3, topojson-client, the world-atlas TopoJSON), so it
runs with no network access and no build step.

## How to use it

| Action | Result |
|---|---|
| Click a continent bubble | Zooms to that continent, regroups by country |
| Click a country bubble (or a shaded country) | Zooms to the country, shows individual data centers |
| Click a site marker | Opens its detail panel: capacity, chips, provenance, sources |
| `Zoom out` button, breadcrumb, `Esc`, or double-click the map | Goes up one level |
| `Reset to world` or `Home` | Back to the world view |
| Scroll / drag | Free zoom and pan at any level |

Markers are **coloured by dominant accelerator**, **outlined by status** (solid
for operating, dashed for under construction, hollow for planned), and **sized
by whichever metric you select** — planned MW, operating MW, installed
H100-equivalents, planned H100-equivalents, chip count, or site count.

Diamond markers are **cloud regions** — places where TPU, Trainium or GPU SKUs
can actually be rented. They carry no capacity figures, so they never
double-count the physical campuses.

Filters cover status, accelerator family, and four size tiers. The long tail of
smaller colocation sites is hidden by default; the `Smaller & colocation` chip
brings it back.

## Where the data comes from

| Source | Records | What it contributes |
|---|---|---|
| **dataCenterView** (`datecenterview-main.zip`, the uploaded project) | 490 | US data centers with status, capacity and 1,115 source URLs from its verification pipeline |
| **Epoch AI** — [AI Data Centers](https://epoch.ai/data/ai-data-centers), CC-BY 4.0 | 83 | Frontier AI sites worldwide with modelled power, per-chip-type unit counts, H100-equivalents, capex, and forward-dated build timelines (the "planned" numbers) |
| **Curated global sites** (`data/compute_map/curated_sites.csv`) | 95 | Sites outside Epoch's coverage across 31 countries — EuroHPC systems, Nscale/Nebius/Mistral, Humain, Stargate UAE, SoftBank/KDDI/ABCI, NAVER, Foxconn, Yotta, Reliance, Huawei, Firmus, Bell AI Fabric, Scala, Cassava and more, each with its own sources and confidence label |
| **Cloud region docs** (`data/compute_map/accelerator_regions.csv`) | 53 | Google TPU zones, AWS Trainium regions, Azure GB200/H200 regions, CoreWeave and OCI, from provider documentation and pricing APIs |

Epoch publishes addresses but no coordinates, so `scripts/geocode_sites.py`
geocodes them through OpenStreetMap Nominatim into a committed cache. Where the
geocoder was too coarse — 11 sites landed on a country centroid — the site uses
Epoch's own map polygon centroid, recorded with a reason in
`data/compute_map/epoch_coord_overrides.csv`.

## Deduplication: identifying one campus across many sources

The same physical campus routinely appears several times: `xAI Colossus 2` and
`Colossus 2`, `Abilene campus` and `OpenAI Stargate Abilene` and
`Stargate I (Abilene)`, `Anthropic Lake Mariner` and `Fluidstack Lake Mariner`
and `Core42 Lake Mariner`. Four rules resolve them, and every merge is logged in
`data.json` under `merge_log` and shown in the site's detail panel.

1. **Explicit rules** — `data/compute_map/identity_rules.csv` lists both `merge`
   pairs and `never` pairs with a written reason. The `never` rules win over
   everything, because genuinely distinct buildings often sit a few hundred
   metres apart (QTS and Meta at Eagle Mountain, Microsoft Goodyear and Stream
   Phoenix, Stargate Abilene and the adjacent Crusoe expansion).
2. **Proximity plus agreement** — within 3 km with the same operator, or with a
   strong name overlap once city, state and street words are stripped.
3. **Facility codes** — records are never merged unless their facility codes
   match exactly. `CoreSite SV3` and `SV9`, `Equinix DA1` and `DA11`, `H5
   Virginia 4030` and `4040` are separate buildings on one campus. Conversely a
   matching code plus a matching operator merges records even when the two
   sources disagree about the coordinate by hundreds of kilometres
   (`Microsoft San Antonio (SAT14)` vs `Microsoft SAT14`, 223 km apart).
4. **Distinctive names, measured not guessed** — a shared name token merges
   records only if that token is rare in the corpus. Token document frequency
   does this automatically: `hyperion` and `midlothian` identify one campus,
   while `stargate` spans seven sites and `aws` dozens, so they carry no weight.

Merged sites keep the **union of all sources** tagged by dataset, the list of
contributing records, and the maximum rather than the sum of each capacity
figure — so merging can never inflate a total.

## Caveats worth reading before quoting a number

- **Epoch's power, chip and capex figures are model outputs**, inferred from
  satellite imagery, permits and utility filings — not company disclosures. The
  detail panel says so on every Epoch-sourced site.
- **Coverage is uneven and visibly US-skewed.** Epoch prioritises US sites, and
  dataCenterView is US-only, so the European and Asian totals here are floors,
  not measurements. Independent estimates put the US at roughly 70–75% of
  installed AI compute; this dataset shows more than that because of source
  coverage, not because the world is emptier than it is.
- **China is the weakest data in the set.** Four Chinese sites are tracked in
  detail against an IEA estimate that China is ~25% of global data-center
  electricity. Chinese site-level reporting in Western sources is thin.
- **Announced capacity with no disclosed location** — Korea's 260,000-GPU
  programme, the EU's seven AI gigafactories, the AMD–Cisco–Humain joint
  venture, AWS's promised Asian and European Trainium capacity — is deliberately
  absent rather than pinned to a guessed coordinate.
- **Coordinate precision is carried per site** (`site`, `street`, `city`,
  `county`, `state`) and shown in the detail panel. A city-level pin can be
  several kilometres from the building.
- **`status` is derived from capacity figures**, not from prose. Epoch's
  "Construction status" column is a free-text observation note; keyword matching
  on it mislabelled operating sites as planned.

## Rebuilding

```bash
python3 scripts/geocode_sites.py        # optional: refresh the geocode cache
python3 scripts/build_compute_map.py    # rebuild docs/compute-map/data.json
```

The build prints its merge decisions and the continent roll-up, so a bad merge
is visible immediately. To correct a site, edit the relevant CSV in
`data/compute_map/` — adding a `merge` or `never` row to `identity_rules.csv` is
usually the right fix — and re-run.
