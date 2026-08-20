# Understanding-GPU

A technical and commercial field guide to the hardware that trains and serves large language models: how GPUs and TPUs work, why they are built differently, what every current accelerator's specifications actually are, what they cost, who can get them, and how they compare.

**→ Read the report: [`report/report.md`](report/report.md)** (about 20,000 words, 24 figures, 12 data-generated tables)
**→ HTML version: [`docs/index.html`](docs/index.html)** — open locally, or serve with `python3 -m http.server -d docs`

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

## Repository layout

```
data/                  7 CSVs — specs, pricing, benchmarks, BOM, supply chain, failures
scripts/theme.py       shared plotting style, vendor palette, drawing helpers
scripts/fig_diagrams.py  8 architecture diagrams drawn from primitives
scripts/fig_data.py    16 plots computed from the CSVs
scripts/tables.py      markdown tables generated from the CSVs
scripts/build_site.py  assembles report/report.md and docs/index.html
report/sections/       the report source, one markdown file per section
report/report.md       the assembled single-file report
report/figures/        24 generated PNGs
docs/index.html        HTML version with sidebar navigation
```

## Reproducing

```bash
pip install -r requirements.txt
python3 scripts/build_site.py --figures   # regenerate every figure, then the report and site
python3 scripts/build_site.py             # rebuild the report and site only
python3 scripts/tables.py                 # print the generated tables
```

## Conventions the report follows

- **Dense FLOPS only.** Vendor headline figures that assume 2:1 structured sparsity have been halved. Meta has publicly confirmed that sparsity is not used in its production models because of quality loss.
- **Every claim is labelled** `confirmed` (vendor datasheet, filing, earnings call, official price list, peer-reviewed paper, MLCommons result), `estimate` (named analyst, or derived here from confirmed inputs), or `rumor` (single-source channel check).
- **Unpublished values stay blank.** They render as em-dashes rather than being interpolated. Section 12.3 lists what nobody has published.
- **Conflicting figures are recorded, not averaged.** Section 12.2 tabulates 20 disagreements you will encounter in the literature, with the value used here.

To correct a number, edit the CSV row (the confidence column is required) and re-run the build. Every table and figure that depends on it updates, so the prose and the plots cannot drift apart.
