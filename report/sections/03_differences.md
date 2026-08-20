---

## 3. The differences that matter

Six differences do real work. The rest is marketing.

### 3.1 Who decides where the data goes

| | GPU | TPU |
|---|---|---|
| On-chip memory | Hardware caches (L1/L2) with residency hints | Software scratchpads (VMEM, CMEM, SMEM) |
| Latency hiding | Dynamic: swap warps on a miss | Static: compiler-placed DMA pipeline |
| Instruction model | SIMT, 32-thread warps, up to 2,048 threads/SM | "Single Instruction 2D Data", 1 thread per core |
| Step-time variance | Meaningful — caches, clocks, scheduler | Very small by construction |
| Irregular workloads | Runs them, at some efficiency | Needs a separate unit (SparseCore) or fails |
| Who you debug | Your kernel, with a profiler | The compiler's schedule, with less visibility |

This single distinction explains most downstream differences, including why TPUs achieve better MACs per watt and why porting an exotic research kernel to a TPU is harder than porting it to AMD.

### 3.2 Array granularity

A GPU Tensor Core instruction operates on a small tile (order 16×8×16) and is re-issued thousands of times by warps, with register reads, scheduling and dispatch amortised over relatively few MACs. A TPU MXU is one 256×256 physical fabric issuing 16,384 MACs per cycle from one instruction. The GPU wins on any matmul that does not fill 256 lanes in the contracting dimension; the TPU wins on the large regular GEMMs that dominate transformer training.

### 3.3 The scale-up domain

![Scale-up domain size and per-chip fabric bandwidth](figures/fig12_scaleup_evolution.png)

This is the number that changed most, and it is the one most often left out of chip-versus-chip comparisons.

| System | Chips in one coherent domain | Per-chip fabric |
|---|---|---|
| HGX H100 / H200 | 8 | 900 GB/s NVLink 4 |
| HGX B200 | 8 | 1.8 TB/s NVLink 5 |
| GB200 / GB300 NVL72 | **72** | 1.8 TB/s NVLink 5 |
| Vera Rubin NVL72 | 72 | **3.6 TB/s NVLink 6** |
| AMD Helios (MI455X) | **72** | 3.6 TB/s UALink-over-Ethernet |
| Trainium3 Gen2 UltraServer | 144 | 2.0 TB/s NeuronLink v4 |
| Huawei CloudMatrix 384 | 384 | 350 GB/s Unified Bus |
| Microsoft Maia 200 | 6,144 | 2.8 TB/s Ethernet + custom transport |
| TPU v7 Ironwood pod | **9,216** | 1.2 TB/s ICI (3D torus + OCS) |
| TPU 8t pod | 9,600 | not published |

(confirmed from vendor documentation; see `data/accelerators.csv`)

Google's advantage here is structural and hard to copy: **nobody else has a reconfigurable topology.** OCS gives topology matching, twisted tori, fault isolation and scheduling flexibility that fixed copper cannot. NVIDIA's answer is raw bandwidth and a flat non-blocking 72-GPU domain; AMD's is the same domain size over open standards; Microsoft, Intel and AMD have all independently chosen Ethernet for scale-up specifically to avoid proprietary lock-in.

Note also what the eighth-generation TPU split tells you about workload divergence. TPU 8t keeps a 3D torus at 9,600 chips because neighbour traffic dominates dense pretraining. TPU 8i abandons it for a high-radix "Boardfly" fabric because all-to-all dominates MoE and reasoning, and Google published the arithmetic: an 8×8×16 torus of 1,024 chips has a 16-hop diameter, where Boardfly reaches the same 1,024 chips in **7 hops**. (confirmed)

### 3.4 Precision

Both families are converging on the same formats, and the interesting differences are in the metadata rather than the element width.

![Number formats and block scaling](figures/fig08_precision.png)

| Format | GPU support | TPU support |
|---|---|---|
| BF16 | Ampere onward | v2 onward (native MXU input, FP32 accumulate) |
| FP8 | Hopper onward (Transformer Engine) | v5p onward |
| FP6 / FP4 | Blackwell onward (MXFP, NVFP4) | **TPU 8t/8i: native FP4 in the MXU** |
| INT8 | all generations | v1 onward; v4 at full rate |
| 3-bit LUT weights | Rubin | not announced |

The measured result that should govern any FP4 planning: with an identical recipe on a 12B model, **NVFP4 held about 1.5% relative loss error against BF16 where OCP MXFP4 reached about 2.5%, and MXFP4 needed 36% more tokens (1.36T vs 1.0T) to match NVFP4's loss.** A 36% token penalty is most of what 4-bit was supposed to buy. The cause is exactly the metadata: 16-element blocks with an E4M3 scale plus a per-tensor FP32 scale preserve more local dynamic range than 32-element blocks with a power-of-two E8M0 scale. (confirmed — NVIDIA, arXiv:2509.25149)

### 3.5 Availability and lock-in

| | GPU (NVIDIA/AMD) | TPU |
|---|---|---|
| Can you buy the silicon? | Yes, from many OEMs | **No** |
| Where can you rent it? | Every hyperscaler, dozens of neoclouds, marketplaces | Google Cloud only |
| Price discovery | Real, and volatile (45× spread on H100) | Google's list price, or a negotiated contract |
| Exit cost if prices rise | Move providers | Renegotiate, or port the model |
| On-prem | Normal | Google Distributed Cloud only |

This is not a footnote. SemiAnalysis's TPU-versus-GPU total-cost model concludes Google's internal TCO per Ironwood chip is roughly 44% below a GB200 server, and that an external GCP customer sees roughly 30–41% lower cost per hour than GB200/GB300. But that first number is a cost-of-goods figure computed by the only company that both designs the chip and runs the datacenter. You are not that company. You rent at a price Google sets, and unlike a GPU you cannot buy the silicon and run it elsewhere. The actionable question is not "is a TPU cheaper than a GPU" but "is this GCP commitment cheaper than my GPU alternative" — a procurement negotiation, not a benchmark. (estimate)

One striking data point on the negotiating value of the *threat*: SemiAnalysis reports that "OpenAI hasn't even deployed TPUs yet and they've already saved ~30% on their entire lab-wide NVIDIA fleet." (estimate)

### 3.6 Software

| | GPU | TPU |
|---|---|---|
| Kernel authoring | CUDA C++, CUTLASS/CuTe, Triton, hand-written PTX | Pallas (Python DSL); otherwise you rely on XLA |
| Distribution | Explicit: NCCL calls, Megatron/DeepSpeed/FSDP configuration | Declarative: annotate arrays, GSPMD inserts collectives |
| Numerics library | TransformerEngine ships with the silicon | XLA built-in |
| Reference training stack | Megatron-LM / NeMo | MaxText (JAX) |
| Orchestration | Multi-controller, one process per device | Pathways single-controller across pods |
| New research techniques | Land here first, usually by months | Follow |
| Failure mode | A slow kernel you can profile | A recompilation or a schedule you cannot see |

The honest summary of the CUDA moat in 2026: it has narrowed to the frontier. For a well-trodden dense or MoE transformer, alternatives work — Gemini is trained entirely on TPUs, Zyphra pretrained ZAYA1 on 1,024 MI300X with ROCm 6.4 and RCCL over AMD Pollara Ethernet, and AMD's MI355X posted 10.18 minutes on MLPerf Llama 2 70B LoRA against NVIDIA's 11.145-minute GB200 result from the prior round. What CUDA still owns is *breadth*: NVIDIA was the only vendor to submit across all seven MLPerf Training v6.0 workloads, and every new numeric format arrives with day-one library support. Triton is the most important counterweight, because kernels written in Triton compile to AMD backends and increasingly to others, so the share of the ecosystem that is hard-locked to CUDA keeps shrinking.
