---

## 5. The NVIDIA lineup

### The catalogue at a glance

Sections 5 through 8 go vendor by vendor. This is the index: every accelerator in this report, who built it, what it was built for, and — the part most comparisons omit — whether you can actually obtain one.

<!-- TABLE:index -->

Four availability models are worth separating, because they determine whether a specification is actionable for you at all. **Purchasable merchant silicon** (NVIDIA, AMD, Intel, Tenstorrent) has real price discovery and you can run it anywhere. **Cloud-only silicon** (TPU, Trainium, Inferentia) is rentable from exactly one provider, so its price is that provider's decision rather than a market's. **First-party silicon** (MTIA, Maia 100) is not for sale at all and exists purely to reduce its owner's costs — though Microsoft has said Maia 200 will eventually be leasable. **System-only silicon** (Cerebras, Groq/LPX, SambaNova) is sold as a rack or consumed as an API, and per-chip specifications are close to meaningless for it.

One caveat the table cannot express: Huawei Ascend is "purchasable" only inside China. Huawei is on the US Entity List, so no Western provider rents Ascend capacity and no dollar-per-hour price exists for it.

![Per-chip throughput 2017-2026](figures/fig09_compute_timeline.png)

### 5.1 Datacenter training and inference parts

<!-- TABLE:nvidia_training -->

Notes on individual parts, in the order they matter.

**V100 (2017–18).** The chip that made deep learning a datacenter category: first-generation Tensor Cores, 125 dense FP16 TFLOP/s, no BF16 path, no sparsity, no MIG. GPT-3 was trained on V100s. It is included here as the baseline against which everything else is a multiple.

**A100 (2020).** The generation that set the modern template: TF32 and BF16 tensor cores, 2:4 structured sparsity, MIG partitioning, 40 MB of L2 (nearly 7× V100), and NVLink 3 at 600 GB/s. Still widely rented at 0.68–2.70 USD/hour and still the cheapest way to get 80 GB of HBM.

**H100 (2022).** The workhorse of the LLM era, and the part every comparison is calibrated against. 989.5 dense BF16 TFLOP/s, 1,979 dense FP8, 80 GB HBM3 at 3.35 TB/s, 900 GB/s NVLink, 700 W. Its real contribution was the first-generation Transformer Engine plus TMA and thread-block clusters, which together made FP8 transformer training practical.

**H200 (2024).** Identical compute to H100 with 141 GB of HBM3e at 4.8 TB/s. NVIDIA measured up to 47% faster than H100 on its MLPerf debut — pure memory-bound uplift, and a clean demonstration that on inference-heavy work the memory system is the product.

**H20 (2024).** The export-compliant China SKU, and the most instructive artefact of the policy environment: compute cut roughly 7× below H100 (148 dense BF16 TFLOP/s) while *memory* went up to 96 GB at 4.0 TB/s. Bandwidth-bound decode barely notices; training does. NVIDIA publishes no datasheet, so every H20 figure here is secondary. NVIDIA took a **$4.5B charge** in Q1 FY26 when H20 licensing was imposed. (confirmed)

**GH200 (2023–24).** A 72-core Grace CPU and an H100 on one module, joined by 900 GB/s coherent NVLink-C2C, with up to 480 GB of CPU LPDDR5X the GPU can address directly. 624 GB of total fast memory per module. The architectural point outlived the product: coherent CPU-GPU memory is now standard on GB200, GB300 and Vera Rubin.

**B200 and GB200 NVL72 (2024–25).** NVIDIA's first chiplet datacenter GPU: two reticle-limited dies joined by a 10 TB/s NV-HBI link and presented to software as one GPU, 208B transistors, 126 MB of partitioned L2. Second-generation Transformer Engine with FP6, FP4 and microscaling. The important number is not the 2,500 dense BF16 TFLOP/s but the **72-GPU NVLink domain** with 130 TB/s of all-to-all bandwidth in a 132 kW rack.

**B300 / GB300 NVL72 (H2 2025).** Blackwell Ultra: 1.5× FP4 (15,000 dense TFLOP/s), 279 GB of 12-Hi HBM3e, PCIe Gen6, 800 Gb/s ConnectX-8 per GPU, up to 1,400 W. Two deliberate regressions tell you what NVIDIA thinks the market is: **FP64 cut 30× (40 → 1.3 TFLOP/s)** and INT8 cut roughly 30×. Traditional double-precision HPC gets nothing from this part. In MLPerf v6.0 it delivered up to 1.6× GB200 at equal GPU count.

**Rubin / Vera Rubin NVL72 (2026).** In full production as of 31 May 2026, shipping to OpenAI, CoreWeave, Google Cloud, Azure, Meta and Dell. 336B transistors, 224 SMs, 896 Tensor Cores, **288 GB of HBM4 at 22 TB/s** (2.8× Blackwell), NVLink 6 at 3.6 TB/s per GPU, 260 TB/s per rack, 88 custom Olympus Arm cores in the Vera CPU. Third-generation Transformer Engine adds 3-bit LUT weights, activation sparsity in attention, 2×/4× faster softmax, and tile-level dependent kernel launch. NVIDIA has not published Rubin's TDP or price. Two naming traps: the shipping product is **NVL72** (72 packages), not the "NVL144" die-count label; and the NVFP4 pair "50 PFLOPS inference / 35 PFLOPS training" is not a clean 2× relationship, so do not assume the usual dense/sparse mapping.

**Rubin CPX: cancelled.** Announced September 2025 as a GDDR7 prefill accelerator, absent from GTC 2026, and explicitly removed from the roadmap. NVIDIA VP Ian Buck: "It's still a good idea, but in order to dedicate our focus on optimizing the decode with LPU this year, we'll be thinking about CPX more in the next generation." Its replacement is the **Groq 3 LPU in NVIDIA LPX racks** — 256 SRAM-only chips per rack paired with an adjacent Vera Rubin NVL72, the first product of NVIDIA's $20B Groq licensing deal. Any circulating "NVL144 CPX" figures describe a product that does not exist. (confirmed)

### 5.2 Inference and prosumer parts

<!-- TABLE:nvidia_inference -->

The L40S and L4 matter because they show what NVIDIA builds when HBM is not on the menu: GDDR6, no NVLink, no MIG, strong video engines, and 72 W in the L4's case. The RTX 5090 is the interesting one for individuals — 32 GB of GDDR7 at 1.79 TB/s and native FP4 for $1,999 — but with no NVLink it cannot participate in tensor parallelism, which caps it at single-GPU work. The RTX PRO 6000 Blackwell (96 GB GDDR7, MIG, confidential computing) launched at $8,565 and was listed at $13,250 by August 2026, a 55% increase NVIDIA attributes to the GDDR7 shortage. (confirmed)

### 5.3 Rack-scale systems

![Rack and pod scale systems compared](figures/fig13_rack_systems.png)

<!-- TABLE:racks -->

Read this table with the chip counts in view: a TPU v7 superpod is 9,216 chips, roughly 128 NVL72 racks' worth, so its totals are not a like-for-like comparison with a single rack. What *is* comparable is the per-rack progression — GB200 → GB300 → Vera Rubin roughly triples FP4 throughput and quadruples fabric bandwidth in about eighteen months — and the fact that AMD's Helios matches NVIDIA's 72-chip domain while carrying 50% more HBM.
