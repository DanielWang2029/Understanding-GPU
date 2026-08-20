---

## 4. The arithmetic of LLM training on real hardware

This section is the bridge between the specifications and the invoices. Every constant here is checkable, and the worked examples reconcile against published runs.

### 4.1 The 6ND rule

Training FLOPs ≈ **6 × parameters × tokens**. The forward pass costs 2 FLOPs per parameter per token (one multiply, one add); the backward pass costs twice that, because each layer computes both a weight gradient and an input gradient. Kaplan et al. (2020) drop the attention-score term `2·n_layer·n_ctx·d_attn`, which was two orders of magnitude smaller for the models of that era — and is *not* negligible at 128k context, which is precisely why Meta's measured throughput fell from 400 to 380 TFLOP/s per GPU during Llama 3.1's long-context stage.

![Training compute of real models, and the 6ND rule checked against it](figures/fig18_training_compute.png)

**Chinchilla-optimal allocation** is about 20 tokens per parameter. Substituting D = 20N into C = 6ND gives C = 120N², so N_opt = √(C/120). Chinchilla itself: 70B parameters on 1.4T tokens beat the 280B Gopher at equal compute. (confirmed — Hoffmann et al. 2022)

Nobody trains at the Chinchilla point any more, because inference cost scales with N and is paid forever. Llama 3.1 405B used about 38 tokens per parameter; Llama 3.1 8B used roughly 1,875, about 90× "over-trained."

**Worked check on Llama 3.1 405B.** 6 × 405e9 × 15.6e12 = **3.79e25 FLOP** against Meta's stated 3.8e25. Now against GPU-hours: 30.84M H100-hours × 3,600 s × 989.5e12 dense BF16 FLOP/s = 1.10e26 FLOP of peak capacity, so **end-to-end utilisation was 34.6%** while Meta reports 38–43% instantaneous MFU. The ~16% gap is restarts, evaluation, checkpoint stalls and the lower-MFU long-context stage. That reconciliation is the most honest single picture of what a frontier training run looks like. (estimate, from confirmed inputs)

**Worked check on DeepSeek-V3.** Using activated parameters: 6 × 37e9 × 14.8e12 = 3.29e24. DeepSeek's own hardware paper states 250 GFLOPS per token, giving 3.70e24 — the gap is MLA attention and routing that 6ND omits. Against 2.664M H800-hours the run used about 39% of BF16 peak, but its GEMMs ran in FP8, so **19.5% of FP8 peak**. The famous $5.576M figure is therefore evidence of a very sparse model on cheap-per-hour silicon, not of unusual hardware efficiency — and DeepSeek says explicitly it excludes "prior research and ablation experiments." (confirmed inputs, derived ratios)

### 4.2 Memory: why one accelerator is never enough

Mixed-precision Adam costs **16 bytes per parameter**: 2 (BF16 weights) + 2 (BF16 gradients) + 4 (FP32 master weights) + 4 (Adam m) + 4 (Adam v).

![Model state, KV cache and how many accelerators they require](figures/fig21_memory_math.png)

ZeRO/FSDP shards those three categories across the data-parallel degree:

| Stage | What is sharded | Per-GPU bytes | 7.5B model, 64-way |
|---|---|---|---|
| DDP baseline | nothing | 16Ψ | 120 GB |
| ZeRO-1 | optimizer states | 4Ψ + 12Ψ/N | 31.4 GB |
| ZeRO-2 | + gradients | 2Ψ + 14Ψ/N | 16.6 GB |
| ZeRO-3 / FSDP | + parameters | 16Ψ/N | 1.9 GB |

(confirmed — ZeRO, arXiv:1910.02054)

**Activation memory** per transformer layer without recomputation is `s·b·h·(34 + 5·a·s/h)` bytes in BF16. The `5as/h` term is the attention score matrix, quadratic in sequence length — exactly the term FlashAttention removes from HBM.

**KV cache per token** = `2 × n_layer × n_kv_heads × d_head × bytes`. Verifying against Llama 3.1 405B (126 layers, 8 GQA KV heads, head dim 128, BF16): 2 × 126 × 8 × 128 × 2 = **516,096 bytes = 516 KB per token**, matching DeepSeek's published table exactly. At that rate a single 128k-token context needs **66 GB** — most of an H100 — for one sequence. DeepSeek's MLA gets the same job done in 70.3 KB per token, 7.3× less.

The structural problem, as DeepSeek frames it citing the AI-memory-wall literature: **LLM memory demand grows more than 1000% per year while HBM capacity grows less than 50% per year.**

### 4.3 Roofline: the ~300 FLOP/byte wall

Arithmetic intensity is FLOPs per byte moved from HBM. A kernel is compute-bound above the machine's ridge point (peak ÷ bandwidth).

![Roofline for H100, B200, TPU v7 and MI355X](figures/fig07_roofline.png)

| Accelerator | Dense BF16 peak | HBM bandwidth | Ridge point |
|---|---|---|---|
| H100 SXM | 989.5 TFLOP/s | 3.35 TB/s | **295 FLOP/byte** |
| B200 (in GB200) | ~2,500 TFLOP/s | 8.0 TB/s | **~312** |
| TPU v7 Ironwood | 2,307 TFLOP/s | 7.38 TB/s | **~313** |
| MI355X | 2,517 TFLOP/s | 8.0 TB/s | **~315** |
| TPU v6e Trillium | 918 TFLOP/s | 1.638 TB/s | 561 |

The convergence around 300 across four unrelated architectures is not coincidence — it reflects the shared economics of HBM stacks against logic area. Practical consequences:

- A square BF16 GEMM has intensity n/3, so **n ≳ 900** to clear the ridge. Tiny GEMMs — small batch, heavily sharded tensor-parallel slices — waste the machine.
- **Prefill** at 8k context has intensity ~8,192: firmly compute-bound.
- **Decode** has intensity ≈ batch size. To clear 295 on an H100 you need a batch near 300. Below that you pay full HBM traffic for the entire weight matrix to produce one token per sequence. This is why inference economics are a batching and KV-cache problem, and why "decode MFU" of 8–12% at batch 32 is not bad engineering but a roofline ceiling.
- **FP8 does not move the crossover.** It halves the bytes and doubles the peak, so the ridge point doubles too. FP8 raises throughput, it does not make decode compute-bound.

**FlashAttention** is the single most important software change to this picture: it tiles attention so the S×S score matrix never leaves SRAM, cutting HBM accesses by a factor of roughly SRAM-size ÷ head-dim². FlashAttention-3 reaches 740–840 TFLOP/s on an H100 (75–85% of dense BF16 peak) versus about 35% for FA-2, and its FP8 variant hits 1.2–1.3 PFLOP/s with 2.6× lower numerical error than baseline per-tensor FP8 attention. (confirmed)

### 4.4 Parallelism, and why the fabric decides the strategy

![Which parallelism can live on which wire](figures/fig06_parallelism.png)

| Axis | What is split | Communication per step | Where it can live |
|---|---|---|---|
| Data parallel / FSDP | batch (+ state) | one gradient all-reduce; ring moves 2(N−1)/N × bytes | scale-out, even WAN |
| Tensor parallel | individual weight matrices | **4 all-reduces of the full activation per layer** | scale-up only |
| Expert parallel | MoE experts | all-to-all token routing per MoE layer | scale-up, spilling out |
| Pipeline parallel | layers | point-to-point at stage boundaries; bubble = (P−1)/(V·M) | scale-out |
| Context/sequence parallel | sequence | ring or all-gather of K,V | scale-up preferred |

**Worked example — why TP must stay inside NVLink.** Llama 3.1 405B's real configuration: h = 16,384, s = 8,192, microbatch 1, BF16, TP = 8. The activation tensor is 8,192 × 16,384 × 2 = 268 MB. Ring all-reduce puts 2×7/8 × 268 MB = 470 MB on the wire per GPU, four times per layer, so **1.88 GB per GPU per layer per microbatch**. That layer's compute at Meta's measured 400 TFLOP/s takes about 49.5 ms per GPU.

| Fabric | Per-GPU unidirectional | Communication time | As % of compute |
|---|---|---|---|
| NVLink 4 (H100) | 450 GB/s | 4.2 ms | **8.5%** |
| NVLink 5 (GB200 NVL72) | 900 GB/s | 2.1 ms | **4.2%** |
| InfiniBand NDR 400G | 50 GB/s | 37.6 ms | **76%** |

(estimate, derived from confirmed specs)

That last row is the entire argument for rack-scale systems. It is also why DeepSeek capped each token's routing to at most 4 nodes — a model-architecture decision made backwards from the ~3.2:1 ratio between intra-node NVLink and inter-node InfiniBand bandwidth.

**Meta's published parallelism table** is the best public ground truth on how the axes compose:

| GPUs | TP | CP | PP | DP | Seq len | TFLOP/s per GPU | BF16 MFU |
|---|---|---|---|---|---|---|---|
| 8,192 | 8 | 1 | 16 | 64 | 8,192 | 430 | **43%** |
| 16,384 | 8 | 1 | 16 | 128 | 8,192 | 400 | **41%** |
| 16,384 | 8 | 16 | 16 | 8 | 131,072 | 380 | **38%** |

(confirmed — Llama 3 paper, Table 4)

Read the pattern: TP is pinned at 8 (the NVLink domain), PP at 16 (cheap over RoCE), and doubling the GPU count halves the per-replica batch, which shrinks the GEMMs and costs 2 points of MFU. Extending context to 128k consumes 16-way context parallelism taken out of data parallelism and costs 3 more.

**What NVL72 changes.** Megatron Core's TP-communication overlap "requires all devices to be on the same NVLink fabric, which on NVIDIA Hopper systems mean a maximum of 8 GPU servers can be utilized for a single parallelism group. NVIDIA GB200 NVL72 alleviates this limitation." TP can exceed 8, which shrinks pipeline depth and the bubble; MoE all-to-all can be confined to one rack; and in NVL72 there is no intra-tray GPU-to-GPU shortcut at all — all 72 GPUs are equidistant, so the placement heuristics developed for 8-GPU nodes stop applying. (confirmed)

### 4.5 What MFU you should actually expect

| Regime | Typical MFU (dense peak denominator) |
|---|---|
| Dense transformer pretraining, BF16, well tuned | 40–55% |
| MoE pretraining | 25–40% (routing fragments compute; load imbalance) |
| Fine-tuning with adequate batch | 35–50% |
| Inference prefill | 30–50% |
| **Inference decode, batch 32** | **8–12% — and that is well-optimised** |
| Naive eager PyTorch, no fusion | 3–8% |

Published first-party figures: Meta 38–43% (Llama 3.1 405B), Google 46.2% (PaLM), NVIDIA Megatron-LM up to 47%, Databricks over 50% on 64 H100s. (confirmed)

One trap worth naming: **FP8 runs report lower MFU while being faster**, because the FP8 peak is 2× the BF16 peak. Databricks measured a 1.4–1.5× throughput gain from FP8 alongside a *lower* MFU percentage. Any MFU comparison without a stated, common, dense denominator is meaningless.

### 4.6 Reliability is a hardware specification

![Llama 3 failure breakdown, job MTBF versus scale, and checkpoint waste](figures/fig20_reliability.png)

Meta's published failure log for Llama 3.1 405B on 16,384 H100s over 54 days is the best public dataset in existence on what breaks at scale: **466 interruptions, 47 planned and 419 unexpected, of which about 78% were confirmed hardware issues.** Meta states that GPU issues are the largest single category at **58.7% of unexpected interruptions**; tabulating the paper's per-cause counts (148 faulty GPUs, 72 HBM3 failures, 19 SRAM, 17 GPU system processors, 6 thermal-interface or sensor faults, 6 silent data corruptions) gives 268 of 419, or 64% — the difference depends on whether SRAM, thermal and silent-corruption events are attributed to the GPU. Software bugs were third at 54 events. Only **3 of 419** interruptions needed significant human intervention, and Meta still achieved over 90% effective training time. (confirmed — Llama 3 paper, Table 5)

Derived consequences (estimate, assuming Meta's per-GPU rate holds):

- Per-GPU MTBF ≈ 2,112 GPU-days ≈ 5.8 GPU-years counting all causes.
- Job MTBF = per-GPU MTBF ÷ N: **3.1 hours at 16,384 GPUs, about 30 minutes at 100,000, about 3 minutes at a million.**
- Young/Daly optimum: waste ≈ √(2δ/M). On a 100k-GPU job, a 60-second synchronous checkpoint wastes **26% of the cluster**; 5-second peer/in-memory replication wastes 7%.

That arithmetic is why checkpointing engineering outranks kernel micro-optimisation at scale. Meta's Tectonic storage fabric — 240 PB across 7,500 SSD servers, 2 TB/s sustained — exists to absorb "highly bursty checkpoint writes." Google's answer for Gemini was different and more radical: **redundant in-memory copies of model state instead of periodic checkpointing to storage, lifting goodput from 85% to 97%.** Google also notes that at Gemini scale silent data corruption "impact[s] training every week or two."

Two further failure modes worth knowing. First, hardware failures at this scale often present as **hangs, not errors**: Meta notes that NVLink load/store failures "often manifest as stalled load/store operations within CUDA kernels without returning a clear error code," which is why the NCCL flight recorder exists. Second, synchronous training makes the whole cluster one coherent electrical load — tens of thousands of GPUs pausing together for a checkpoint produce "instant fluctuations of power consumption across the data center on the order of tens of megawatts, stretching the limits of the power grid."

TPUs attack the same problem at the topology layer: a failed cube is optically bypassed and a spare swapped in, so the job resumes on a *logically identical* mesh — which matters enormously in a compiler-first stack where the mesh shape is baked into the compiled program.
