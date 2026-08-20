---

## 6. AMD, Intel and Huawei

### 6.1 AMD Instinct

<!-- TABLE:amd -->

AMD's strategy is legible from the table: **compete on memory, match on low precision, and give away nothing on openness.** MI300X shipped 192 GB when H100 had 80; MI355X shipped 288 GB at 8 TB/s in the same window as B200's 180–192 GB; MI455X ships 432 GB of HBM4 against Rubin's 288 GB. AMD's own Helios claim against Vera Rubin NVL72 is 15% more peak FP4, **50% more HBM capacity**, 6% more HBM bandwidth and 50% more scale-out bandwidth. The capacity claim is the structurally defensible one.

Three things to know beyond the specifications.

**MI300X and MI325X have identical compute.** MI325X is purely a memory upgrade (192 → 256 GB, 5.3 → 6.0 TB/s) bought with 250 W. Same pattern as H100 → H200.

**CDNA 4 deprioritised FP64** just as Blackwell Ultra did: 163.4 → 78.6 TFLOP/s. The HPC-and-AI dual-purpose era is over on both sides.

**Helios is an open-standards rack.** 72 MI455X in an OCP Open Rack Wide, 18 EPYC Venice CPUs, 31 TB of HBM4, 260 TB/s of scale-up over **UALink-over-Ethernet** with single-hop all-to-all, 43 TB/s of scale-out over Ultra Ethernet, in production and shipping late Q3 2026. AMD's bet is that open fabrics plus more memory beat a mature proprietary stack for inference-dominated workloads, where kernel diversity is lower than in research training.

**The MI455X bandwidth number is genuinely disputed.** AMD's newsroom says 1.7 PB/s per Helios rack (23.3 TB/s per GPU, which matches a physical derivation from 12 HBM4 stacks × 2,048-bit at ~7.6 GT/s); Supermicro's datasheet says 1.4 PB/s (19.6 TB/s). Both sets are internally self-consistent, so this is two specifications rather than a typo — likely a peak-theoretical versus conservative-binned figure. AMD also labels none of the MI455X throughput figures dense or sparse while benchmarking them against NVIDIA's dense NVFP4. (estimate; flagged)

**Where ROCm actually stands in 2026.** Solved: upstream PyTorch works out of the box, vLLM and SGLang treat Instinct as first-class, Hugging Face models load, and Triton has a real AMD backend — which matters more than it sounds, because it gives a portable path for a large fraction of the ecosystem's hand-written kernels. Still friction: custom CUDA kernels need porting, RCCL multi-node collective tuning is much less well-trodden than NCCL's, new techniques (novel attention variants, quantisation schemes, MoE kernels) land on CUDA first by months, and profiling and debugging tooling is thinner.

The evidence that training on AMD is now real rather than theoretical:

- **Zyphra's ZAYA1**, the first large-scale MoE foundation model pretrained end-to-end on AMD hardware, networking and software: 128 nodes × 8 MI300X = **1,024 GPUs**, 8× Pensando Pollara 400 Gbps NICs per node, over 750 aggregate BF16 PFLOP/s measured, ROCm 6.4, Apache 2.0 weights. Critically, MI300X's 192 GB let Zyphra pretrain "primarily using a simpler parallelism strategy, namely data-parallelism with the ZeRO-1 distributed optimizer," avoiding expert and tensor sharding entirely. That is the underrated argument for high-capacity HBM: it buys *simplicity*, and every parallelism axis you avoid is a class of bugs you do not debug. The paper also contributes the first published RCCL-over-Pollara collective microbenchmarks at that scale. (confirmed)
- **MLPerf Training v5.1**, audited, 8-GPU FP8 Llama 2 70B LoRA:

<!-- TABLE:mlperf_amd -->

MI355X at 10.18 minutes against NVIDIA's 11.145-minute GB200 result is close to parity — but note the rounds differ by six months of NVIDIA software optimisation, and in v6.0 AMD did not submit to the two new MoE benchmarks, so no full-suite like-for-like comparison exists. Nine OEM partners submitted on Instinct in v5.1, the broadest AMD ecosystem participation so far. (confirmed)

### 6.2 Intel

<!-- TABLE:intel_huawei -->

Gaudi 3's genuine differentiator is that **scale-up and scale-out both run on the same on-die Ethernet NICs**: 24 × 200 Gb/s RoCE v2 giving 1,200 GB/s per accelerator, with an 8-OAM node fully peer-to-peer and **no switch inside the node**. Intel's pitch was explicitly about avoiding "risky investments in locked, proprietary technologies such as NVLink, NVSwitch, and InfiniBand," and it claims 33% more I/O per accelerator than H100.

The unusual fact about Intel is price transparency: it is the only vendor that ever published accelerator list prices — **$125,000 for an 8-card Gaudi 3 baseboard including networking** (≈$15,625 per accelerator) and $65,000 for Gaudi 2, positioned at two-thirds and one-third of "comparable competitive platforms." Any comparison against an HGX system should add InfiniBand or Ethernet NIC cost to the NVIDIA side, since Gaudi's fabric is on-die. (confirmed)

The architectural catch: **Gaudi 3's FP8 rate equals its BF16 rate** at 1,835 TFLOP/s. There is no 2× FP8 speedup — Gaudi 2 had one. For FP8-heavy inference that is roughly half an H100's dense FP8 throughput, while being competitive on BF16 and ahead on memory.

**Falcon Shores was cancelled as a product** in January 2025 — "an internal test chip only, without bringing it to market" — with a revealing stated reason: "it's not enough to just deliver the silicon… what customers really want is that full-scale rack solution." Intel also missed its $500M Gaudi 3 revenue target, citing software. What replaced it is a deliberate retreat from the frontier: **Crescent Island** (announced October 2025, sampling H2 2026) uses **160 GB of LPDDR5X rather than HBM** and is air-cooled, sidestepping HBM supply competition entirely at the cost of bandwidth far below any HBM part. It is a "tokens-as-a-service" inference capacity play. **Jaguar Shores** is the announced rack-scale answer, with no published specifications or date. (confirmed)

### 6.3 Huawei

Ascend 910C is a dual-die DaVinci part on SMIC 7nm: 780 dense BF16 TFLOP/s, 128 GB HBM2e at 3.2 TB/s, roughly 600 W, and — the single biggest handicap — **no native FP8 or FP4 path**, arriving only with the Ascend 950 generation. Every low-precision throughput multiplier the rest of the industry is monetising is unavailable.

Provenance warning: Huawei publishes no 910C datasheet. The canonical figures trace to Huawei's own CloudMatrix paper, **arXiv:2506.12708 version 1** — version 2 deleted the sentence giving the chip's throughput and version 3 renamed the part, so citations must be pinned to v1. (estimate)

**CloudMatrix 384** is the system that matters, and it is an honest statement of the strategy: 384 Ascend 910C delivering about 300 BF16 PFLOP/s and 49.2 TB of HBM — roughly 1.9× the compute and 3.6× the memory of a GB200 NVL72 — at **559 kW against 132 kW**. Per-chip efficiency is roughly a third of NVIDIA's. It is a brute-force answer to export controls: win at system level by spending the input China has (power) to compensate for the one it does not (leading-edge silicon and HBM).

The 2026 roadmap is aggressive and constrained by the same two things. **Ascend 950PR** (Q1 2026, ~1 PFLOPS FP8, 128 GB HiBL 1.0 at 1.6 TB/s) and **950DT** (Q4 2026, ~2 PFLOPS FP4, 144 GB HiZQ 2.0 at 4 TB/s) finally add FP8/FP4 and MXFP formats, with UB 2.0 cutting single-hop latency from 2 µs to 200 ns. The **Atlas 950 SuperPod** targets 8,192 chips, 8 EFLOPS FP8, and 16 PB/s of all-optical interconnect. A widely-reported 96 GB variant of the 950DT is read as a direct response to domestic HBM constraints. Production capacity is the binding limit: roughly 200,000 Ascend 910-series chips in 2025 against a 2026 target near 600,000, versus Chinese demand estimated at 1.0–1.5 million advanced AI chips. (estimate)
