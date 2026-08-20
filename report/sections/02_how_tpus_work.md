---

## 2. How a TPU works

A TPU starts from the observation that transformer training is overwhelmingly matrix multiplication, and asks what you would build if you were allowed to give up generality.

### 2.1 The systolic array

A systolic array is a two-dimensional grid of multiply-accumulate cells wired directly to their neighbours. Google's own description: "TPUs contain thousands of multiply-accumulators that are directly connected to each other to form a large physical matrix." Operands enter at the edges and *pulse* through — each cell takes values from its neighbours, multiplies, accumulates, and passes results onward. Nothing returns to a register file or cache in between.

![Weight-stationary systolic dataflow over four cycles](figures/fig02_systolic_array.png)

The reason this fits matmul is an arithmetic-intensity argument. In an N×N array, an operand entering the edge is reused N times as it propagates, so **arithmetic scales with N² (the cell count) while traffic across the array boundary scales with N**. A 256×256 Ironwood MXU performs **16,384 MACs per cycle** from one instruction. A conventional machine needs an operand fetch and a result writeback per MAC; the systolic array replaces that O(N²) register traffic with O(N) edge traffic plus nearest-neighbour wires, and short local wires are dramatically cheaper in energy than SRAM accesses.

Google TPUs are fundamentally **weight-stationary**: a tile of the weight matrix stays resident while activations stream through. TPU v4 explicitly improved "faster MXU weight loading bandwidth" to cut the changeover cost, and Ironwood exposes the pipeline to the programmer — VMEM is split between the current computation scope and the *next* weight prefetch, tuned with `xla_tpu_scoped_vmem_limit_kib`. (confirmed)

The array width is not free. Google states that Ironwood's MXU "is efficient when the contracting dimension is larger than or equal to a multiple of 256." The move from 128×128 (v2 through v5p) to 256×256 (v6e, v7) raised peak FLOPS and simultaneously raised the granularity you must hit to achieve them — Google notes flash-attention kernels suffer "more underutilization of the MXU" as a result. A matmul with a contracting dimension of 128 wastes half the array.

### 2.2 No caches, anywhere

There is no cache hierarchy on a TPU. Every level of on-chip memory is a software-managed scratchpad with an explicit address space, and XLA decides statically what lives where and when it moves. No prefetcher, no eviction policy, no coherence protocol, no cache tags.

| Scratchpad | Role | Sizes |
|---|---|---|
| **VMEM** | High-bandwidth staging for MXU/VPU; the tile buffer for custom kernels | v3: 32 MiB · v4: 16 MiB per TensorCore (32/chip) · **v7: 64 MiB per TensorCore (128/chip)** · TPU 8i: 384 MB |
| **CMEM** | Chip-level scratchpad shared by both TensorCores, load/store access. New in v4 | v4: **128 MiB** |
| **SMEM / Spmem** | Per-SparseCore-tile buffer for embedding vectors | v3: 5 MiB · v4: 10 MiB (2.5 MiB per tile slice) |
| Register file | | 0.25 MiB, unchanged v3 → v4 |

(confirmed — Jouppi et al. ISCA 2023; Google Cloud Ironwood performance docs)

CMEM was measurably load-bearing rather than decorative. The v4 paper reports RNN1 — small weights, small batches — running **3.3× faster on v4 than v3**, well above the typical 1.5–2.0×, and attributes it specifically to "CMEM bandwidth versus HBM." The v4i paper decomposes its performance-per-watt gain as roughly 1.5× from CMEM, 1.3× from the 16nm→7nm move, and 1.2× from everything else.

**Why determinism is the real product.** Because the compiler knows when every byte arrives, XLA can statically schedule collectives to overlap maximally with compute. Google's Gemini technical report describes exactly this: the GSPMD partitioner partitions the step, and "the MegaScale XLA compiler pass statically schedules appropriate collectives so that they maximally overlap with the computation **with very little variation in step time**." At 4,096-chip synchronous scale the slowest chip sets the pace, so removing variance is worth more than raising the mean.

![Dynamic latency hiding versus static scheduling](figures/fig03_execution_model.png)

The cost is that everything becomes the compiler's problem. Shapes must be static or padded to static buckets. A kernel whose working set overflows VMEM does not degrade gracefully; it gets a different, worse schedule. And when performance is bad you are debugging XLA's choices, which are far less legible than a GPU profiler trace.

### 2.3 SparseCore: the part that is not a systolic array

Embedding lookups — irregular, data-dependent gather/scatter — are what a systolic array is worst at. Rather than compromise the MXU, Google added a separate dataflow processor on the same die.

The economics are remarkable, and Google states them plainly: SparseCores "speed up models that rely on embeddings by **5×–7× yet use only 5% of die area and power**." Each SparseCore tile has a Fetch Unit pulling activations and parameters from HBM into its 2.5 MiB Spmem slice, an scVPU reusing the TensorCore's ALUs, a Flush Unit writing updated parameters back on the backward pass, and five Cross-Channel Units executing embedding primitives across all 16 banks. These units run **CISC-like instructions on variable-length inputs where each instruction's runtime is data-dependent** — deliberately the opposite of the MXU's deterministic pipeline, isolated on its own core so the irregularity cannot infect the main datapath. (confirmed — ISCA 2023)

SparseCores also give the pod a flat, globally addressable memory space — **128 TiB on TPU v4** — which is how an embedding table larger than any chip's HBM gets sharded across a pod and accessed over ICI.

In Ironwood, SparseCore acquired a second job: **collective offloading**. The SparseCores are now "independent threads of control capable of managing data movement over the ICI fabric," so All-Gather and Reduce-Scatter run in parallel with TensorCore compute. Google calls it "the recommended method for asynchronous collectives on TPU7x." (confirmed)

### 2.4 The optically reconfigurable torus

From v4 onward a pod is not hard-wired. Chips are grouped into **4×4×4 cubes of 64 chips** on passive copper, and the cubes are joined through **optical circuit switches** — mechanically steered mirror arrays that make a physical-layer optical circuit between fibre ports. Four consequences follow, and all four are load-bearing.

**Topology on demand.** Gemini's technical report gives the timescale: v4 superpods of 4,096 chips are "each connected to a dedicated optical switch, which can dynamically reconfigure 4×4×4 chip cubes into arbitrary 3D torus topologies in around 10 seconds." A 512-chip slice can be 4×4×32, 4×8×16 or 8×8×8 depending on which parallelism dimensions your model wants, and Google's docs advise matching them.

**Twisted tori.** Because links are switch-mediated, wrap-around edges can shift by X+2 mod 4 instead of connecting same-coordinate chips, converting an asymmetric torus into a symmetric one. Published bisection-bandwidth gains: about **70% for 4×4×8, 8×8×16 and 12×12×24**, about 40% for 4×8×8 and 8×16×16. Measured effect on FSDP MaxText was 1–2 percentage points of MFU. (confirmed)

**Fault tolerance and scheduling availability.** Google calls this ICI resiliency: connections route around OCS and optical faults, which "improves the scheduling availability of TPU slices, with the trade-off of temporary degradation in ICI performance," and it is on by default for slices of one cube or larger. The v4 paper's argument is that with hosts at 99.0–99.9% availability, "in practice it is much easier to schedule a 3K slice than a 4K" one. Gemini Ultra exploited this explicitly: "we decided to retain a small number of cubes per superpod to allow for hot standbys and rolling maintenance."

**Pod-scale memory sharing.** Ironwood's Hot Chips deck frames OCS as a memory technology: 9,216 chips "use optical circuit switches to share memory… directly addressable shared HBM memory capacity of **1.77 PB**."

### 2.5 What this buys, in one number

A TPU v7 chip delivers 2,307 dense BF16 TFLOP/s and 4,614 FP8 TFLOP/s with 192 GiB of HBM3E at 7.38 TB/s, and a 9,216-chip superpod reaches 42.5 FP8 exaFLOPS inside about 10 MW. Google claims 2× the performance per watt of Trillium and roughly 30× that of its 2018 Cloud TPU. (confirmed for specs; the perf/W comparisons are vendor claims with no independent benchmark)

![Ten years of TPU: compute, memory and pod size](figures/fig24_tpu_generations.png)
