---

## 8. The other ASICs

<a id="8-the-other-asics"></a>

<!-- TABLE:other_asics -->

### 8.1 AWS Trainium — the largest non-NVIDIA training fleet

AWS is unusually explicit about dense versus sparse, which makes its numbers easy to trust. Trainium2: 8 NeuronCore-v3, **1,299 dense FP8 TFLOP/s** (2,563 sparse), 96 GiB HBM at 2.9 TB/s, 224 MiB of SBUF on-chip SRAM, NeuronLink-v3 at 1.28 TB/s, and a **64-chip UltraServer** memory pool. Trainium3 (GA December 2025) is AWS's first 3 nm chip: **2,517 dense MXFP8 TFLOP/s**, 144 GB HBM3e at 4.9 TB/s, NeuronLink-v4 at 2 TB/s, and a **144-chip scale-up domain** built as 36 servers × 4 chips behind a two-level NeuronSwitch — "optimized for… Mixture of Experts models and autoregressive inference serving."

Confirmed by Amazon: the chips business is now at a **>$25B revenue run rate**; Anthropic has committed to **up to 5 GW** of current and future Trainium and runs Claude on **over one million Trainium2 chips**; **OpenAI has committed to 2 GW** of Trainium capacity from 2027; Trn3 UltraServers deliver up to 4.4× the compute of Trn2 and **>5× the output tokens per megawatt**.

**Project Rainier** is the physical expression: an $11B, 1,200-acre campus in New Carlisle, Indiana, operational from late October 2025 with roughly **500,000 Trainium2 chips** in 7 of 30 planned buildings, sized for eventual 2.2 GW. AWS calls it "the world's largest cluster of non-NVIDIA AI chips." Be careful with chip counts in circulation: ~500k at New Carlisle, >1M in Anthropic's company-wide fleet, and ~1.4M Trainium2 deployed across all AWS customers are three different numbers. (confirmed / estimate as noted)

Pricing: only Trn1 has a full public on-demand rate card ($1.34 per chip-hour). For Trn2, the citable AWS-published rate is **Capacity Blocks at $2.235 per chip-hour**; third-party trackers showing ~$0.54 per Trainium2 chip-hour are almost certainly spot and should not be planned against. Trainium3 has no published public price at all. (confirmed / flagged)

For calibration at published rates: Trainium2 is about **$1.72 per dense FP8 PFLOP-hour** versus Ironwood at $2.60 on-demand or $1.17 on a 3-year commit.

### 8.2 Meta MTIA — internal-only, and the most candid roadmap

MTIA is not for sale and not rentable, but Meta publishes unusually detailed specifications and, more valuable, unusually honest caveats. MTIA v2: TSMC N5, 421 mm², 8×8 PE grid at 1.35 GHz, **354 dense INT8 / 177 dense BF16 TFLOP/s**, 256 MB of on-chip SRAM at 2.7 TB/s, and **128 GB of LPDDR5 at only 204.8 GB/s** — entirely appropriate for ranking and recommendation, where the bottleneck is embedding capacity and random access rather than sequential bandwidth, and the reason its perf/W (7.8 TOPS/W) beats an H100's (5.65).

Meta's admission about sparsity is the single most useful sentence any vendor has published on the subject: 2:4 sparsity is in the hardware, but "our production experience indicates that exploiting sparsity is challenging due to potential quality loss in our recommendation models… **this feature is not yet widely used in production**."

The March 2026 roadmap is four generations on a roughly six-month cadence, enabled by modular chiplets sharing one chassis, rack and network: **MTIA 300** (in production, 1.2 PFLOPS FP8, 216 GB @ 6.1 TB/s, 800 W), **MTIA 400** (deploying 2026, 6 PFLOPS FP8 / 12 PFLOPS MX4, 288 GB @ 9.2 TB/s, 1,200 W, **72 devices in one scale-up domain**), then 450 and 500 in 2027. Meta inverts the industry's usual logic explicitly: "Mainstream chips are typically built for the most demanding workload — large-scale GenAI pre-training — and then applied, often less cost-effectively, to other workloads… **We take the opposite approach**: MTIA 450 and 500 are optimized first for GenAI inference." Everything is built on PyTorch, vLLM, Triton and OCP standards.

Flag: the published MTIA 450/500 FP8 figures (7 and 10 PFLOPS) do not reconcile with Meta's own claim of a 25× compute increase from MTIA 300 to 500 (which would be 30 PFLOPS), while the bandwidth claim of 4.5× checks out exactly. Treat those two compute numbers as unresolved.

### 8.3 Microsoft Maia

Maia 100 (2024) was a supply-strategy statement as much as a chip: TSMC N5, ~820 mm², **3 POPS at 6-bit / 1.5 POPS at 9-bit / 0.8 POPS BF16**, ~500 MB of L1/L2 scratchpad, and deliberately **HBM2E rather than HBM3** — as ServeTheHome put it, "Microsoft is not competing with NVIDIA and AMD for leading-edge HBM supply." It never went beyond internal Azure OpenAI workloads.

**Maia 200** (announced 26 January 2026, in production in US Central) is a serious part: TSMC 3 nm, >140B transistors, **10.1 PFLOPS FP4 / 5.07 PFLOPS FP8 / 1.27 PFLOPS BF16**, 216 GB HBM3e at ~7 TB/s, **272 MB of fully software-managed SRAM**, 2.8 TB/s of scale-up bandwidth over an integrated on-die NIC, and a scale-up domain of **up to 6,144 accelerators** over two-tier Ethernet with a custom AI Transport Layer. Microsoft's framing — "compilers and runtimes can place working sets explicitly to keep attention and GEMM kernels close to compute" — is a description of a TPU-style scratchpad hierarchy, not a cache. It serves GPT-5.2 among other models, targets synthetic data generation and reinforcement learning pipelines as well as inference, and Microsoft has said it "will be made available for lease to a broader customer base in the future." No public price. (confirmed)

### 8.4 Cerebras — wafer-scale

WSE-3: **46,225 mm² of silicon (a full 21.5 × 21.5 cm wafer), 4 trillion transistors, 900,000 cores, 44 GB of on-wafer SRAM at 21 PB/s, no HBM at all, ~23 kW per CS-3 system.** Yield is handled by designing for defects — redundant cores and routing, fail-in-place.

Two caveats matter more than any spec. First, **the headline "125 PFLOPS" is sparse FP16**, and Cerebras's sparsity is unstructured, so it cannot be compared to a dense GPU number; Cerebras publishes no dense equivalent. Second, the August 2026 **CS-4 is not new silicon**: the WSE-3 Turbo carries the same 4T transistors, 900k cores, 44 GB SRAM and 5 nm node, and doubles throughput by roughly doubling the clock (~1.4 → ~2.8 GHz) on the back of a redesigned power path that moved conversion "100 times closer to the processors." Both compute and power roughly doubled, so **perf/W is at best slightly improved**; what genuinely improved is per-rack throughput and memory bandwidth per user, which is what determines tokens/sec/user on decode. A CS-4 rack is 3 wafers, 750 sparse-FP16 PFLOPS, 129.6 PB/s of memory bandwidth, 125–140 kW, shipping Q3 2026. (confirmed / estimate as noted)

Cerebras is not the cheapest per token — several GPU providers undercut it, and above roughly 8 concurrent requests a rented H100 running vLLM with continuous batching produces more tokens per dollar. The value case is latency: ~3,000 tokens/sec on GPT-OSS-120B, ~1,800 on Llama 3.3 70B.

### 8.5 Groq — now part of NVIDIA

Important framing: **Groq's inference silicon is no longer an independent alternative.** In December 2025 NVIDIA licensed the LPU technology for **$20 billion**, the largest deal in its history, including acqui-hiring founder Jonathan Ross, and at GTC 2026 the result shipped as the **NVIDIA Groq 3 LPU**. Jensen Huang compared the integration to Mellanox.

The architecture remains the purest expression of compiler-scheduled determinism in shipping silicon, and it is directly relevant to the TPU comparison:

- **No DRAM whatsoever.** Weights live in SRAM: 230 MB at 80 TB/s on v1, 512 MB at 150 TB/s on Groq 3. Groq's framing: on-chip SRAM has "memory bandwidth upwards of 80 terabytes/second, while GPU off-chip HBM clocks in at about eight." The cost is capacity — serving Llama 2 70B took roughly **576 LPUs** on v1 silicon.
- **Compiler-first, literally:** "We didn't touch chip design until the compiler's architecture was designed."
- **Plesiosynchronous chip-to-chip links** that cancel clock drift so hundreds of LPUs behave as one logical core — determinism extended past the die boundary, which even TPUs do not attempt.

An LPX rack is 256 LPUs, 128 GB of aggregate SRAM, 40 PB/s of aggregate bandwidth, 315 PFLOPS FP8, shipping H2 2026 as the decode partner to a Vera Rubin NVL72. (confirmed)

### 8.6 SambaNova and Tenstorrent

**SambaNova SN40L** is the only shipping accelerator with a tightly coupled **three-tier memory system**: 520 MiB of on-chip PMU SRAM, 64 GiB of HBM at 1.8 TB/s, and up to 1.5 TiB of pluggable DDR at >200 GB/s, with a DDR→HBM load rate above 1 TB/s. The design target is *model switching*, not raw throughput — hundreds of models resident in DDR, swapped into HBM in microseconds, aimed at composition-of-experts and agentic serving. Its dataflow execution model fuses operations into a single kernel call so data never returns to memory between stages; the ISSCC/arXiv paper reports 2×–13× speedups on 8 sockets against an unfused baseline. A 16-socket rack is 10.2 BF16 PFLOPS and runs DeepSeek R1 671B. (confirmed)

**Tenstorrent** is the only vendor here that publishes hardware list prices and sells retail: **Blackhole p150a at $1,399** for 120 Tensix cores, 180 MB of SRAM, 32 GB of GDDR6 at 512 GB/s, 664 TFLOPS BLOCKFP8, 300 W, four QSFP-DD 800G ports for direct card-to-card meshing, and a fully open-source RISC-V stack. A 32-chip Galaxy rack is 23 PFLOPS BLOCKFP8 from $110,000. Note a spec revision: Tenstorrent previously published 140 cores and 774 TFLOPS; after a February 2026 firmware update the official figures are **120 cores and 664 TFLOPS**, and many third-party pages still carry the old numbers. The counterweight is decisive for most buyers: GDDR6 at 512 GB/s is 6–15× below any HBM part, there is no cloud marketplace offering Tenstorrent capacity, and the software maturity gap is larger than AMD's. (confirmed)

### 8.7 What the field looks like after twelve months of consolidation

The non-NVIDIA field narrowed sharply. Intel cancelled Falcon Shores and retreated to LPDDR5X inference parts. NVIDIA bought Groq's technology and used it to displace its own Rubin CPX. Cerebras shipped a clock bump rather than new silicon. Meanwhile the hyperscalers went the other way: Google split its eighth generation into two purpose-built chips, Meta announced four generations in two years, Microsoft shipped Maia 200 on 3 nm, and AWS shipped 3 nm Trainium3.

**The viable non-NVIDIA path has narrowed to vertically integrated hyperscaler silicon plus AMD, and Huawei inside China.** Merchant challengers without a captive workload have not found a durable position.

![Estimated 2026 accelerator volumes](figures/fig22_shipments.png)
