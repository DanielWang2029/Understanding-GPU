---

## 9. Head to head

### 9.1 Everything relative to one H100

![Normalised comparison against H100](figures/fig23_normalised.png)

The pattern in that figure is the single most useful thing to internalise: **no current accelerator wins on every axis, and the axes are not equally important for your workload.**

| If your bottleneck is… | The winner is… | Because |
|---|---|---|
| Dense training FLOPs per chip | Rubin R100, then MI455X | 4.0 / 5.0 dense BF16 PFLOP/s |
| Low-precision training throughput | Rubin R100 | 17.5 dense FP8 PFLOP/s, 3rd-gen Transformer Engine, NVFP4 recipes |
| Memory capacity per chip | MI455X (432 GB), then TPU 8i (288 GB) | fewer shards, simpler parallelism |
| Memory bandwidth per chip | MI455X (~23 TB/s), Rubin (22 TB/s) | HBM4 roughly triples bandwidth |
| Tensor-parallel headroom | TPU pods (9,216), then NVL72 / Helios (72) | scale-up domain size |
| Determinism at scale | TPU | static schedule, OCS fault isolation |
| Cost per token served | depends entirely on contract | see §10 |
| Software risk | NVIDIA | breadth, day-one format support |

### 9.2 Efficiency

![Compute and memory per watt](figures/fig11_perf_per_watt.png)

Chip-level perf/W favours the specialised parts, and the ordering is stable across metrics: TPU and Maia-class ASICs lead on memory per watt, Blackwell leads on compute per watt among GPUs, and Huawei's 910C trails badly because it lacks low-precision paths and rides an older node.

Three caveats keep this honest. First, chip TDP excludes CPU, NIC, switch and cooling, which are a third or more of rack power. Second, Google publishes no per-chip TDP after v4, so Ironwood's ~1 kW is inferred from pod power and *includes* overhead, making its position conservative. Third, all published perf/W comparisons across vendors are vendor claims — Google's "2× Trillium and 2.8× H100", Amazon's "2.1× Trainium2", NVIDIA's Rubin figures — and **no independent third-party benchmark comparing Ironwood against NVIDIA hardware existed as of August 2026.**

### 9.3 What the audited benchmarks say

![MLPerf time-to-train and scaling efficiency](figures/fig19_mlperf.png)

MLPerf Training v6.0 (June 2026), 24 organisations, 95 unique systems, 13 accelerators, 60% multi-node:

<!-- TABLE:mlperf_v6 -->

The round added two MoE benchmarks — DeepSeek-V3 671B and GPT-OSS 20B — and MLCommons was explicit about why the DeepSeek-V3 benchmark mandates a global batch size of at least 15,360: to prevent "'hero runs' on tiny batch sizes that don't reflect production-scale MoE training." A benchmark body defending against a known gaming vector is a sign of a maturing suite.

The most useful single result is CoreWeave's DeepSeek-V3 scaling ladder, because it is one workload on one platform at three scales: 2,048 GPUs in 5.54 min, 4,096 in 3.09 min (**89.6% scaling efficiency**), 8,192 in 2.02 min (**68.6%**). Near-linear to 4k, clearly sublinear beyond — which is what you expect once expert-parallel all-to-all starts crossing Spectrum-X hops rather than staying inside NVL72 racks. Azure's dense Llama 3.1 405B curve holds up better (83% at 8,192 GPUs against a 40-rack baseline) because tensor parallelism stays inside the rack.

**Eight ways these numbers mislead**, worth stating because they are all common:

1. "Fastest on every benchmark" is partly a coverage claim. NVIDIA was the only vendor submitting to all seven v6.0 workloads; AMD skipped both MoE benchmarks.
2. Time-to-train at maximum scale measures the cluster, not the chip. 3.44 min on 11,616 H100s versus 11.77 min on 6,144 TPU v5p is ~1.8× per chip, not 3.4×.
3. **There is no perf-per-dollar or perf-per-watt metric in the closed division.** Every cost-efficiency claim — Google's Trillium perf/$, AMD's tokens-per-dollar — is unauditable within MLPerf.
4. Cross-round comparisons are not like-for-like: AMD's v5.1 MI355X result against NVIDIA's v5.0 GB200 result spans six months of NVIDIA software work.
5. Submitters choose their scale, and small-scale entries are cherry-picked.
6. The benchmark models lag production. GPT-3 175B was the LLM pretraining benchmark until v5.1, five years after the model.
7. Preview and RDI tiers are not products. Check the tier before quoting.
8. Vendor blog numbers are not MLPerf numbers. Zyphra's ">750 PFLOPs" is footnoted as an internal measurement of "a set of subsequent MLPs in BFLOAT16," not a training workload — an honest disclosure that gets dropped when the number is repeated.

And the biggest gap of all: **no TPU has been submitted since Trillium in v5.0 (June 2025).** Google submitted to v6.0 on NVIDIA hardware, focusing on DeepSeek-V3. So the two most-discussed accelerators of 2026, Ironwood and Blackwell Ultra, have never met in an audited benchmark.

### 9.4 Real training runs, for calibration

<!-- TABLE:training_runs -->

Two observations. First, disclosure has collapsed: everything after 2024 is a reconstruction from hardware counts and durations, so the visible frontier is a record of *publicised successful runs*, not of compute spent. Second, Epoch AI's decomposition of the 4–5×-per-year growth in training compute is the least intuitive and most important fact here: the median annual factors are **hardware quantity 1.69×, training duration 1.53×, per-chip throughput 1.41×.** Most compute growth comes from buying more chips and running longer, not from faster chips. That is why datacenter power, packaging capacity and cluster reliability — not FLOPS per die — are the binding constraints in 2026.
