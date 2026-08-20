---

## 1. How a GPU works

![GPU and TPU chip block diagrams side by side](figures/fig01_gpu_vs_tpu_block.png)

A datacenter GPU is a lattice of near-identical compute tiles wrapped in a memory system designed to keep them fed despite unpredictable access patterns. On an H100 there are 132 **streaming multiprocessors** (SMs); on a B200 there are 148 enabled across two dies; on Rubin, 224. Everything else — caches, schedulers, interconnect — exists to supply them.

### 1.1 Inside an SM

An SM is divided into four processing blocks, each with its own warp scheduler, dispatch unit, L0 instruction cache and slice of the register file. Per SM on Hopper: **128 FP32 lanes, 64 INT32, 64 FP64, four fourth-generation Tensor Cores, a 256 KB register file, and 256 KB of combined L1/shared memory** of which up to 228 KB can be configured as programmer-managed shared memory. (confirmed — Hopper whitepaper)

The execution model has been stable since Volta and is worth stating precisely, because it explains both the GPU's flexibility and its inefficiency: **32 threads per warp, up to 64 warps and 2,048 threads resident per SM, 32 thread blocks per SM, 65,536 32-bit registers per SM, 255 registers per thread.** Volta added independent thread scheduling, giving each thread its own program counter so divergent branches can interleave rather than serialise.

What changed generation to generation is not the model but the ratios and the units bolted on:

| | Volta V100 | Ampere A100 | Hopper H100 | Blackwell B200 |
|---|---|---|---|---|
| FP32 lanes per SM | 64 | 64 | **128** | 128 |
| Tensor Cores per SM | 8 (1st gen) | 4 (3rd gen) | 4 (4th gen) | 4 (5th gen) |
| Register file per SM | 256 KB | 256 KB | 256 KB | 256 KB |
| L1 + shared per SM | 128 KB | **192 KB** | **256 KB** | 256 KB |
| Max shared memory | 96 KB | 164 KB | 228 KB | not published |
| L2 total | 6 MB | **40 MB** | **50 MB** | **126 MB** (measured) |
| New numeric formats | FP16 tensor | TF32, BF16, 2:4 sparsity | **FP8 (E4M3/E5M2)** | **FP6, FP4, microscaling** |

(confirmed for Volta through Hopper from NVIDIA whitepapers; B200 L2 and SM count are independent measurements by Chips and Cheese — NVIDIA has stopped publishing SM and cache counts for datacenter Blackwell)

Note the ratio that got worse: registers per FP32 lane halved from 1,024 on A100 to 512 on H100, because the lanes doubled and the register file did not. This is one reason kernel authors moved from register-blocked GEMMs to shared-memory-and-TMA pipelines.

### 1.2 The three Hopper additions that made FP8 transformer training work

**Tensor Memory Accelerator (TMA).** A hardware unit that performs asynchronous multi-dimensional bulk copies between global and shared memory from a tensor descriptor. **A single thread** issues a copy of up to the full shared-memory capacity; the unit generates addresses and handles out-of-bounds behaviour while every other thread keeps computing. Synchronisation runs through shared-memory asynchronous transaction barriers rather than spinning. (confirmed)

Rubin extends this with **inline descriptor updates**: a kernel keeps one descriptor for tensors sharing a layout and overrides the base pointer and stride inside the TMA instruction itself. That is a direct attack on MoE inference, where hundreds of expert weight matrices share a layout but live at different addresses. (confirmed — NVIDIA Rubin architecture blog)

**Thread block clusters and distributed shared memory.** Hopper inserted a level between grid and thread block. A cluster co-schedules up to 16 blocks on SMs within one GPC, and **distributed shared memory** makes their shared-memory windows mutually addressable, so an SM can load, store and perform atomics directly on a neighbour's shared memory instead of round-tripping through global memory. (confirmed)

**The Transformer Engine.** First generation (Hopper): FP8 in two flavours — E4M3 forward, E5M2 for gradients — with per-tensor dynamic scaling driven by a tracked history of absolute-maximum values. Second generation (Blackwell): FP6 and FP4, and a move from per-tensor to **block (microscaling) formats**. Third generation (Rubin): a 3-bit lookup-table weight format for the B matrix, plus activation sparsity applied inside attention, where the intermediate scores are 2:4-compressed on the way out of Tensor Memory so softmax and the second GEMM operate on non-zeros while the output stays dense. (confirmed)

### 1.3 The cache hierarchy is the point of difference

L2 went 6 MB (V100) → 40 MB (A100) → 50 MB (H100) → 126 MB (B200). On B200 the L2 is partitioned, almost certainly one partition per die, with about 150 ns latency to the local partition and a cross-die penalty only slightly worse than A100's cross-partition penalty. A single B200 L2 partition holds more than an H100's entire L2. (estimate — measured by Chips and Cheese)

This is the architectural fork in the road. The GPU spends transistors on tags, coherence, replacement policy and residency controls so that **any** access pattern eventually performs acceptably. That is why a GPU runs a novel attention variant, a data-dependent MoE router, a graph neural network and a physics kernel with the same silicon. It is also why a GPU has more silicon per delivered MAC than a systolic machine, and why its step times vary.

![Memory hierarchies compared: caches, scratchpads, and SRAM-only](figures/fig04_memory_hierarchy.png)

### 1.4 Scaling out: NVLink, NVSwitch and the 8-GPU wall

A GPU alone cannot hold a frontier model, so the interconnect is part of the architecture, not an accessory.

| NVLink generation | GPUs | Per-GPU bidirectional bandwidth |
|---|---|---|
| NVLink 2 | V100 | 300 GB/s (6 links) |
| NVLink 3 | A100 | 600 GB/s (12 links) |
| NVLink 4 | H100, H200, GH200 | 900 GB/s (18 links) |
| NVLink 5 | B100, B200, B300 | **1,800 GB/s** (18 × 100 GB/s) |
| NVLink 6 | Rubin | **3,600 GB/s** |

(confirmed — NVIDIA datasheets and the GB200 NVL72 technical blog)

Separately, **NVLink-C2C** connects a Grace CPU to its GPU coherently at 900 GB/s on GH200 (1.3 pJ/bit, over 5× more energy-efficient per bit than PCIe Gen5), rising to 1,800 GB/s on Vera Rubin. That is what lets a GPU issue loads and stores against 480 GB of CPU LPDDR5X as if it were a slower tier of its own memory.

For a decade the practical consequence was the **8-GPU wall**: NVSwitch lived on the server baseboard, so the coherent domain was one node. Tensor parallelism, which all-reduces the full activation tensor four times per transformer layer, had to fit inside it. Above 8 GPUs you were on InfiniBand at roughly 50 GB/s per GPU — about 18× less bandwidth.

**GB200 NVL72 moved the switches into the rack** and broke that wall. 72 GPUs, 36 Grace CPUs, 18 compute trays, 9 switch trays holding 18 NVSwitch ASICs. Each GPU has exactly 18 NVLink 5 ports, one to each ASIC, over a copper backplane: fully connected, non-blocking, no topology-dependent hot spots, 130 TB/s of aggregate all-to-all bandwidth. The switch also does in-network reduction (SHARP), cutting both latency and bytes on the wire for all-reduce. (confirmed)

![Scale-up fabrics: HGX, NVL72 and a TPU torus](figures/fig05_topology.png)

NVIDIA quantifies the payoff bluntly: "every 2× of scale-up in NVLink bandwidth can lead to 1.3–1.4× of rack-level AI performance improvement." Vera Rubin NVL72 keeps 72 packages and doubles the fabric to 260 TB/s.

Scale-out has moved in parallel: Quantum-X800 InfiniBand at 800 Gb/s per port with 144-port switches (115.2 Tb/s), the first use of 200 Gb/s-per-lane SerDes, SHARPv4 with 14.4 TFLOPS of in-network compute, and co-packaged-optics variants that cut insertion loss from about 22 dB to 4 dB. Notably, the fastest MLPerf v6.0 result at 8,192 GPUs ran on **Spectrum-X Ethernet**, not InfiniBand — evidence that Ethernet is now viable at frontier scale. (confirmed)
