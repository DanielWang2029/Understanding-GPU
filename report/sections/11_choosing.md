---

## 11. Choosing hardware

A decision procedure, in the order the questions actually bind.

### 11.1 Start with the constraint, not the chip

**1. Does your model fit, and how much sharding does that force?** Model state is 16 bytes per parameter. Add activations and KV cache. If ZeRO-1 data parallelism alone fits, take it — Zyphra's ZAYA1 shows that high-capacity HBM buys away entire parallelism axes, and every axis you avoid is a class of bugs and a source of communication you do not pay for. This is the strongest argument for MI300X/MI355X/MI455X and for TPU v7 over an 80 GB H100.

**2. How large a scale-up domain does your parallelism need?** If tensor parallelism above 8 or MoE expert parallelism is on the critical path, an 8-GPU HGX node will cost you dearly and a 72-chip NVL72/Helios or a TPU pod will not. The worked example in §4.4 is the whole argument: the same tensor-parallel all-reduce is 8.5% of layer time on NVLink 4 and 76% on 400G InfiniBand.

**3. Is your workload prefill/training-shaped or decode-shaped?** Training and prefill are compute-bound above ~300 FLOP/byte; decode is memory-bandwidth-bound below batch ~300 and will not be rescued by more FLOPS. Price decode capacity in dollars per TB/s-hour, not dollars per PFLOP-hour.

**4. What is your software risk tolerance?** If you write custom fused kernels for novel architectures, CUDA remains the only place where everything lands first. If you run mainstream dense or MoE transformers with PyTorch, vLLM or JAX, the alternatives work today.

**5. What price can you actually get?** This is the question most analyses skip, and it usually dominates. See §10.3.

### 11.2 A rough mapping

| Situation | Reasonable choice | Reasoning |
|---|---|---|
| Frontier pretraining, thousands of chips, need the best software | GB300 NVL72 → Vera Rubin NVL72 | Largest audited results, 72-chip domain, NVFP4 recipes, breadth of tooling |
| Frontier pretraining, willing to co-design and commit for years | TPU v7 / 8t pods, or Trainium3 | Best TCO *if* you can negotiate; determinism and OCS fault tolerance at 9k+ chips |
| Large-scale inference serving, cost per token dominates | TPU 8i, MTIA 400, Maia 200, MI355X | Memory capacity and bandwidth per dollar; low kernel diversity makes non-CUDA viable |
| MoE training, hundreds to low thousands of chips | GB300/GB200 NVL72 | All-to-all inside one rack; see the CoreWeave scaling ladder in §9.3 |
| Fine-tuning and mid-size training on rented capacity | H100/H200 from a neocloud or marketplace | Cheapest dollars per PFLOP-hour anywhere; H200's 141 GB removes a sharding tier |
| Memory-hungry inference, single node | MI355X (288 GB) or MI300X (192 GB) | Fits models that need 2–3 H100s on one GPU; ROCm is fine for vLLM/SGLang |
| Latency-critical serving, tokens/sec/user is the product | Cerebras CS-4, Groq/NVIDIA LPX | SRAM-only bandwidth; not the cheapest per token above ~8 concurrent requests |
| Cost-constrained enterprise inference, air-cooled racks | Gaudi 3, Intel Crescent Island, L40S | Published prices, no liquid cooling, no HBM supply exposure |
| Research on a workstation | RTX 5090 (32 GB, FP4) or RTX PRO 6000 (96 GB) | No NVLink means single-GPU work only |
| Learning the stack, minimal budget | Tenstorrent Blackhole p150a at $1,399 | Open RISC-V stack; accept the software gap and 512 GB/s |
| Inside China | Ascend 910C now, 950DT when it ships | Export controls make this the only supply that reliably arrives |

### 11.3 Five mistakes this report exists to prevent

**Comparing sparse to dense.** Vendor headline TFLOPS are usually 2:1 sparse. Halve them. Meta has confirmed publicly that sparsity is not used in its production models because of quality loss; assume the same everywhere unless proven otherwise.

**Comparing peak FLOPS at all.** Well-tuned dense pretraining is 40–50% MFU; decode at batch 32 is capped near 11%. A 2× peak advantage frequently delivers 1.2× in production, and sometimes nothing at all if the bottleneck is bandwidth or the fabric.

**Comparing chips when the product is a rack.** A GB200 NVL72 is not nine HGX nodes; the 72-GPU coherent domain changes which parallelism strategies are viable. Conversely, a TPU superpod is 9,216 chips, so pod-level totals are not comparable to a rack.

**Treating a vendor's TCO advantage as your TCO advantage.** SemiAnalysis's 44% figure for Ironwood is Google's internal cost of goods. You rent at a price Google sets and cannot take the silicon elsewhere. Convert every TCO claim into a quote before believing it.

**Assuming benchmark leadership transfers.** MLPerf has no perf/$ or perf/W metric, submitters choose their scale, rounds are six months apart, and Ironwood has never been submitted. The most-discussed matchup of 2026 — Ironwood versus Blackwell Ultra — has zero audited data behind it.

### 11.4 What to watch next

- **HBM4 supply and pricing.** It is the reason rental prices rose in H1 2026. If 2027 capacity lands on schedule, that reverses; if not, GPU prices keep climbing even as packaging capacity improves.
- **Whether FP4 training becomes standard.** NVFP4 has produced a 10T-token, 12B-parameter run within ~1.5% of FP8 loss. If that holds at frontier scale, effective compute per rack roughly doubles again without new silicon — and the MXFP4-versus-NVFP4 token penalty becomes a real competitive asymmetry.
- **Whether Google sells TPUs externally.** Morgan Stanley's 5M-unit 2027 forecast and persistent Meta reports point that way. It would be the single biggest structural change to the market since Hopper. Currently a rumor.
- **Scale-up domain inflation.** 72 today, 144 on Trainium3, 1,152–9,600 on TPU 8i/8t, 6,144 on Maia 200. If NVIDIA's 576-GPU NVLink ceiling gets used, tensor and expert parallelism get much cheaper and the parallelism playbook changes again.
- **Ethernet versus proprietary fabric for scale-up.** AMD (UALink-over-Ethernet), Intel (RoCE on-die), Microsoft (Ethernet plus a custom transport) and Meta have all chosen Ethernet. CoreWeave's MLPerf record on Spectrum-X shows it works at 8,192 GPUs.
- **Power, not silicon.** Growth in training compute comes 1.69× per year from more chips and 1.53× from longer runs against only 1.41× from faster chips. Gigawatt campuses, transformer lead times and grid interconnection queues are the real 2027 constraint.
