---

## 7. Google TPU, generation by generation

<!-- TABLE:tpu -->

Google publishes no clock speed, process node or per-chip TDP for anything after v4, so those columns are blank rather than guessed. The ~1 kW figure used for Ironwood elsewhere in this report is inferred from "nearly 10 MW" for a 9,216-chip pod and therefore includes rack overhead.

### 7.1 What each generation was actually for

**v1 (2015), inference only.** A 256×256 systolic array at 700 MHz: 65,536 8-bit MACs × 0.7 GHz ≈ 92 TOPS, exactly Google's published figure. 28 nm, 75 W, 8 GB of DDR3.

**v2 (2017), the first trainable TPU.** Google shrank the array to 128×128 — a deliberate trade favouring utilisation on narrower matrices — added HBM and ICI links, and made a 256-chip pod.

**v3 (2018).** Two MXUs per TensorCore, 32 GB HBM, liquid cooling, 1,024-chip pods.

**v4 (2020, GA 2022).** The most important generation architecturally: 7 nm, **128 MiB of CMEM**, 4 SparseCores, and the first **optically reconfigurable 3D torus** at 4,096 chips per pod (1.1 EFLOPS BF16). The die is *smaller* than v3's despite twice the matrix multipliers. PaLM 540B was trained on 6,144 v4 chips; Gemini Ultra used "a large fleet of TPUv4 accelerators… across multiple datacenters"; Apple trained AFM-server on 8,192 v4 chips.

**v5e (2023), cost-optimised.** One TensorCore, 16 GB, 256-chip pods, air-cooled, and the cheapest TPU on the rate card at $1.20/chip-hour ($0.54 on a 3-year commit).

**v5p (2023), the training flagship of its era.** Megacore (two TensorCores presented as one logical core over a unified memory space), 95 GB HBM at 2.765 TB/s, 3D torus, single slices to 6,144 chips and **multislice to 18,432**.

**v6e Trillium (2024).** First 256×256 MXU, 918 dense BF16 TFLOP/s, back to 256-chip pods. Google's claim is 1.8× better performance per dollar than v5p (45% lower cost to train), with 99% weak-scaling efficiency across 8 Trillium-256 slices over multislice versus 94% for v5p within a single ICI domain. (confirmed as a vendor claim; the perf/$ number is unauditable within MLPerf)

**v7 Ironwood (2025, GA 2026).** The first dual-compute-die TPU: **2,307 dense BF16 / 4,614 FP8 TFLOP/s, 192 GiB HBM3E at 7.38 TB/s, 128 MiB VMEM, 4th-gen SparseCore with collective offloading, 1.2 TB/s ICI, 9,216-chip superpods at 42.5 FP8 EFLOPS with 1.77 PB of directly addressable shared HBM in nearly 10 MW.** Google claims 2× the perf/W of Trillium and about 30× its 2018 Cloud TPU. **No Ironwood MLPerf submission exists** — the most recent TPU training submission is Trillium in v5.0, June 2025 — so every Ironwood-versus-Blackwell training comparison in circulation is spec-sheet arithmetic. (confirmed for specs; flagged for comparisons)

**Eighth generation (announced April 2026): the split.** Google stopped building one chip for both jobs.

| | TPU 8t (training) | TPU 8i (inference) |
|---|---|---|
| Topology | 3D torus | **Boardfly** high-radix, Dragonfly-inspired |
| Pod | **9,600 chips** | 1,152 chips |
| HBM | 216 GB @ 6.53 TB/s | **288 GB @ 8.6 TB/s** |
| On-chip SRAM | 128 MB | **384 MB** (3× Ironwood) |
| Peak FP4 | **12.6 PFLOP/s** | 10.1 PFLOP/s |
| Specialised units | SparseCore + LLM Decoder Engine | **Collectives Acceleration Engine** replaces SparseCore |
| Claimed vs Ironwood | 2.7× perf/$ training, up to 2× perf/W | 80% better perf/$ inference |

(confirmed from Google's announcement and technical deep dive; the claimed multiples are vendor figures)

The reasoning Google published is the clearest statement anywhere of why topology follows workload: dense pretraining is neighbour-dominated, so 8t keeps the torus; MoE and reasoning are all-to-all-dominated, so 8i abandons it. Google shows the arithmetic — a 1,024-chip 8×8×16 torus has a 16-hop diameter, Boardfly reaches the same 1,024 chips in **7 hops**, a 56% reduction. 8t also adds **native FP4 in the MXU**, a more balanced VPU so quantisation and normalisation overlap better with matmul, and **TPUDirect RDMA and Storage** moving data between HBM and NICs or Lustre without transiting host DRAM. Both are hosted on Arm Axion CPUs, which Google says "removed the host bottleneck caused by data preparation latency." The Virgo fabric links over 134,000 8t chips with up to 47 Pb/s of non-blocking bisection, and Google states JAX plus Pathways can "scale to more than 1 million TPU chips in a single training cluster."

One caveat: secondary reporting of "331.8 exaFLOPS FP8 per 8i pod" does not reconcile — 1,152 chips × ~5 PFLOPS ≈ 5.8 EFLOPS, and 6.74 × Ironwood's 42.5 would be 286 EFLOPS, not 331.8. The 8t figure does reconcile cleanly (9,600 × 12.6 PFLOPS = 121 EFLOPS = 2.84 × Ironwood). Treat the 8i pod aggregate as unverified. (flagged)

### 7.2 Pricing — the one authoritative accelerator price list in the industry

TPUs are GCP-only: you cannot buy one, no third party resells them, and the only on-prem path is Google Distributed Cloud. In exchange, Google publishes real prices.

| Generation | On-demand | Flex-start (queued) | 1-year commit | 3-year commit |
|---|---|---|---|---|
| **v7 Ironwood** (us-central1) | **$12.00** | $6.00 | $8.40 | **$5.40** |
| v6e Trillium (us-east1/5) | $2.70 | $1.35 | $1.89 | $1.22 |
| v5p (us-east5) | $4.20 | $2.10 | $2.94 | $1.89 |
| v5e (us-central1) | $1.20 | $0.60 | $0.84 | $0.54 |
| v4 pod (us-central2) | $3.22 | — | $2.03 | $1.45 |

(confirmed — `cloud.google.com/tpu/pricing`, retrieved 20 August 2026)

Two structural features worth extracting. The **3-year commitment is a flat 55% discount** and the 1-year a flat 30%, across every generation. And **flex-start is a 50% discount with no commitment at all** — for Ironwood that is $6.00, cheaper than the 1-year commit. If your workload tolerates queuing, flex-start is the best rate available without signing anything. Note also that the console bills in VM-hours, not chip-hours: a 4-chip v4 host shows as $12.88/hour.

Spot pricing is not published as a table; Google says only that spot prices "can change up to once every 30 days."

Against that list price, SemiAnalysis estimates Anthropic pays about **$1.60 per Ironwood chip-hour** — 7.5× below list — and characterises the list as "car-salesman" pricing: "No major customers of TPUs is paying anywhere close to that much." (estimate)

### 7.3 Who trains on TPUs

- **PaLM 540B**: 6,144 v4 chips across two pods, 3,072 per pod on 768 hosts, model+data parallelism within a pod and pure data parallelism across pods. (confirmed)
- **Gemini**: "We trained Gemini models using TPUv5e and TPUv4… Training Gemini Ultra used a large fleet of TPUv4 accelerators owned by Google across multiple datacenters." Gemini 1.5 used multiple 4,096-chip v4 pods across datacenters. (confirmed)
- **Apple**: AFM-server on 8,192 TPU v4; AFM-on-device on 2,048 TPU v5p. Notable mainly as evidence that a company with no Google Cloud dependency chose TPUs on merit. (confirmed)
- **Anthropic**: up to **one million TPUs** and "well over a gigawatt of compute capacity online in 2026" (October 2025), expanded in April 2026 with Google and Broadcom to multiple further gigawatts from 2027 — roughly 3.5 GW per a Broadcom SEC filing. Google Cloud's CEO attributed the choice to TPU "price-performance and efficiency." (confirmed announcement; the 3.5 GW figure is filing-derived)

The Gemini infrastructure detail worth stealing: instead of periodic checkpointing to cluster storage, Google used **redundant in-memory copies of model state** and recovered from an intact replica, lifting goodput from 85% to 97%.
