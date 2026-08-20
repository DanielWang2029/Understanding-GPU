---

## 12. Appendix: methodology, conflicts and unknowns

### 12.1 How this report was built

```
data/                        seven CSVs, every row carrying a confidence label
  accelerators.csv           58 accelerators: specs, TDP, fabric, price
  cloud_pricing.csv          61 offers across 14 providers and 9 pricing tiers
  rack_systems.csv           13 rack- and pod-scale systems
  mlperf_training.csv        MLPerf Training v4.0 through v6.0 results
  training_runs.csv          published training compute for 14 real models
  bom_costs.csv              modelled bill of materials for 6 chips
  supply_chain.csv           CoWoS capacity, HBM share and price, volumes, rack power
  llama3_failures.csv        Meta's 419-interruption failure log

scripts/
  theme.py                   shared style, vendor palette, drawing helpers
  fig_diagrams.py            8 architecture diagrams drawn from primitives
  fig_data.py                16 plots computed from the CSVs
  tables.py                  markdown tables generated from the CSVs
  build_site.py              assembles report.md and the HTML site

report/report.md             the single-file report
report/figures/              24 generated PNGs
docs/index.html              the HTML version
```

Reproduce everything with `python3 scripts/build_site.py --figures`.

Where the report states a derived number — job MTBF, checkpoint waste, dollars per PFLOP-hour, the tensor-parallel communication example — it is computed in code from labelled inputs, and the inputs are cited. Nothing is interpolated silently: unpublished values are blank in the CSVs and render as em-dashes in the tables.

### 12.2 Conflicting numbers you will encounter

These are the disagreements most likely to bite anyone doing capacity or cost math.

| Item | The conflict | What this report uses |
|---|---|---|
| H100 SXM bandwidth | Hopper whitepaper says 3.0 TB/s and marks it "not finalized"; product page says 3.35 | **3.35 TB/s** |
| B200 memory | 192 GB (keynote, raw HBM) vs 186 GB (GB200 datasheet) vs 180 GB (HGX datasheet) | 186 / 180 GB, with 192 noted |
| B300 memory | 288 GB (keynote) vs 279 / 270 GB (Oct 2025 datasheet, corroborated by Lambda's MLPerf entry) | **279 GB** |
| Blackwell Ultra INT8 | 330 TOPS sparse where B200 lists 10 POPS — a ~30× cut, internally consistent but unexplained | as published, flagged |
| Blackwell Ultra FP64 | 1.3 TFLOP/s vs B200's 40 — a deliberate 30× cut | as published |
| B200 SM count and L2 | NVIDIA publishes neither; 148 SMs and 126 MB are Chips and Cheese measurements | measured values, labelled |
| Rubin NVFP4 | "50 PFLOPS inference / 35 PFLOPS training" is not a 2× relationship and NVIDIA has not explained the basis | as published, flagged |
| Rubin naming | "NVL144" (die count) vs shipping "NVL72" (package count) | **NVL72** |
| Rubin fabric | 260 TB/s in-rack NVLink vs 28.8 TB/s rack-to-rack scale-out, frequently conflated | both, labelled separately |
| MI455X bandwidth | 23.3 TB/s per GPU / 1.7 PB/s per rack (AMD) vs 19.6 / 1.4 (Supermicro) | 23.3, with 19.6 noted |
| MI355X platform FP8 | AMD's platform table lists 80.5 PFLOPS where 8 × 5.03 = 40.3 | per-GPU figures |
| GH200 HBM3e | 144 GB / 4.9 TB/s (NVIDIA) vs 141 / 4.8 (secondary, likely conflated with H200) | **144 GB / 4.9 TB/s** |
| TPU v2 peak | 46 BF16 TFLOP/s (ISCA 2021) vs 45 or 43 in marketing | **46** |
| TPU v4 power | Paper: 121 W min / 170 mean / 192 max, idle 90; Cloud docs list 90 as minimum | paper values |
| GB300 NVL72 price | $3.7–4.0M (Loop Capital) vs $6.0–6.5M (Tom's Hardware supply chain) | $3.7M, flagged |
| TPU 2026 volume | 2.7M (SemiAnalysis, Aug 2026, revised down) to 4.6M (BofA) | **2.7M**, flagged |
| Ascend 910C specs | Huawei's own paper v1 gives throughput; v2 deleted it and v3 renamed the part | v1, pinned |
| MTIA 450/500 compute | Published FP8 figures contradict Meta's own 25× scaling claim | unresolved, flagged |
| TPU 8i pod compute | Reported 331.8 EFLOPS does not reconcile with chip count or the stated multiple | unresolved, flagged |
| Cerebras "125 PFLOPS" | Sparse FP16 with unstructured sparsity; no dense equivalent published | not compared to dense |
| MFU expectations | Lambda's own whitepaper says 35–45%; a third party reads Lambda's benchmarks as 60–68% | **35–50%** for dense pretraining |
| Colossus GPU count | 200,000 (x.ai) vs ~230,000 itemised vs ">220,000" (Anthropic lease) vs 276k H100-equivalents (Epoch) | all cited, by convention |

### 12.3 Things nobody has published

Stated explicitly, because their absence shapes every comparison:

- **B200/B300 official SM, CUDA core and Tensor Core counts.** NVIDIA stopped publishing these for datacenter parts.
- **B300 L2 size and die size. Rubin's CUDA core count, die size, L2 size, TDP and price.** Rubin's process node comes only from third parties.
- **Per-chip TDP, clock speed and process node for every TPU after v4.** Google's ~1 kW Ironwood figure here is inferred from pod power.
- **Any Ironwood MLPerf result.** None exists.
- **Trainium3 public pricing.** Capacity Blocks and enterprise agreements only.
- **AMD's dense-versus-sparse labelling for MI455X**, and its process node.
- **H20's SM count, transistor count and die configuration.** No NVIDIA datasheet exists.
- **Per-part cost of goods from any vendor.** Every BOM figure in §10.1 is modelled.
- **HBM revenue by supplier.** No share figure is verifiable.
- **Gemini 1.5/2.5/3 training compute; Nemotron total FLOPs.** Not disclosed.
- **The percentage of step time spent in communication at frontier scale.** No lab publishes it; §4.4's figures are derived.

### 12.4 Primary sources

**Architecture.** NVIDIA Volta, Ampere, Hopper, Ada and RTX Blackwell architecture whitepapers; NVIDIA Blackwell, Blackwell Ultra and GH200 datasheets; NVIDIA Rubin architecture blog; Chips and Cheese B200 microarchitectural analysis; Jouppi et al., *In-Datacenter Performance Analysis of a TPU* (ISCA 2017), *Ten Lessons From Three Generations Shaped Google's TPUv4i* (ISCA 2021), and *TPU v4: An Optically Reconfigurable Supercomputer* (ISCA 2023); Google Cloud TPU architecture documentation; Ironwood Hot Chips 2025 deck; Google Cloud eighth-generation TPU deep dive; AMD MI350/MI355X product briefs and Helios launch materials; Intel Gaudi 3 whitepaper and Hot Chips 2024 deck; AWS Neuron architecture documentation; Meta MTIA ISCA 2025 paper; Microsoft Maia 100 Hot Chips 2024 deck and Maia 200 announcement; Cerebras WSE-3 datasheet; Groq LPU documentation; SambaNova SN40L ISSCC 2025 paper; Tenstorrent Blackhole specifications.

**LLM systems.** Kaplan et al. 2020 (arXiv:2001.08361); Hoffmann et al. 2022 (arXiv:2203.15556); Rajbhandari et al., ZeRO (arXiv:1910.02054); Shoeybi et al., Megatron-LM (arXiv:1909.08053); Narayanan et al. 2021 (arXiv:2104.04473); Korthikanti et al. 2022 (arXiv:2205.05198); Dao et al., FlashAttention (arXiv:2205.14135) and FlashAttention-3 (arXiv:2407.08608); Grattafiori et al., *The Llama 3 Herd of Models* (arXiv:2407.21783); DeepSeek-V3 technical report (arXiv:2412.19437) and hardware paper (arXiv:2505.09343); Anthony et al., ZAYA1 (arXiv:2511.17127); NVIDIA, *Pretraining LLMs with NVFP4* (arXiv:2509.25149); OCP Microscaling Formats v1.0; Gemini technical reports (arXiv:2312.11805, arXiv:2403.05530); PaLM (JMLR 24:240); Apple Intelligence Foundation Language Models.

**Benchmarks and market data.** MLCommons MLPerf Training v4.0, v4.1, v5.0, v5.1 and v6.0 result sets and submitter write-ups; Google Cloud TPU pricing page; AWS EC2 Capacity Blocks pricing; CoreWeave, RunPod and Oracle price lists; NVIDIA, Broadcom, Marvell, Micron and Amazon earnings materials; TrendForce CoWoS reporting; Epoch AI training-compute datasets and datacenter directory; SemiAnalysis TPU and TCO analyses; BIS rule text and the January 2026 presidential proclamation.

### 12.5 Correcting this report

The datasets are the interface. To change a number, edit the CSV row — the confidence column is required — and re-run `python3 scripts/build_site.py --figures`. Every table and figure that depends on it updates, so the prose and the plots cannot drift apart. Where a value is disputed, the convention used here is to record the better-sourced value in the CSV and note the conflict in §12.2 rather than silently averaging.
