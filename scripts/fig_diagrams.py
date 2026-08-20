"""Conceptual architecture diagrams: how GPUs and TPUs actually work.

Every diagram is drawn from primitives so it can be regenerated and edited.
Numbers annotated on the diagrams come from data/accelerators.csv and the
vendor documents cited in report/report.md.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from theme import (
    ACCENT,
    ACCENT2,
    ACCENT3,
    ACCENT4,
    GPU_C,
    GRID,
    INK,
    MUTED,
    PANEL,
    TPU_C,
    WARN,
    apply_style,
    arrow,
    blank_axes,
    box,
    note,
    save,
    titleblock,
)

SRC_1 = ("Sources: NVIDIA Hopper/Blackwell architecture whitepapers; Google Cloud TPU architecture docs; "
         "Jouppi et al. ISCA 2023; Ironwood Hot Chips 2025 deck.")


# --------------------------------------------------------------------------
# 1. GPU vs TPU chip block diagram
# --------------------------------------------------------------------------
def fig01_gpu_vs_tpu_block():
    fig, ax = plt.subplots(figsize=(15.4, 9.6))
    blank_axes(ax, (0, 100), (0, 100))
    titleblock(
        fig,
        "One chip, two philosophies: GPU streaming multiprocessors vs TPU systolic arrays",
        "Left: NVIDIA H100-class Hopper GPU.   Right: Google TPU v7 (Ironwood)-class chip.   Boxes are functional units, not drawn to scale.",
        top=0.93,
    )

    # ============================ GPU ============================
    L = 1.0
    box(ax, L, 2, 47, 96, "", face="#fbfdf7", edge=GPU_C, lw=1.8, radius=0.010)
    ax.text(L + 23.5, 94.6, "GPU die  —  general-purpose parallel processor",
            ha="center", fontsize=12.4, fontweight="bold", color=GPU_C)

    box(ax, L + 2, 76.0, 43, 16.0, "", face="#ffffff", edge=GRID, radius=0.006)
    ax.text(L + 3.4, 89.8, "132 Streaming Multiprocessors", fontsize=9.8,
            fontweight="bold", color=INK)
    for r in range(3):
        for c in range(11):
            box(ax, L + 3.4 + c * 3.72, 78.0 + r * 3.4, 3.0, 2.8, "SM",
                face="#eef6e0", edge=GPU_C, fontsize=5.8, lw=0.6, radius=0.003)
    ax.text(L + 44.0, 77.0, "hardware scheduler places blocks on any free SM",
            fontsize=8.0, color=MUTED, style="italic", ha="right")

    box(ax, L + 2, 57.5, 43, 16.5, "", face="#ffffff", edge=GPU_C, ls="--", radius=0.006)
    ax.text(L + 3.4, 71.6, "inside one SM  (×4 processing blocks)", fontsize=9.8,
            fontweight="bold", color=INK)
    for i in range(2):
        y = 65.8 - i * 4.3
        box(ax, L + 3.4, y, 17.5, 3.7, "warp scheduler + 32 FP32 lanes",
            face="#eef6e0", edge=GPU_C, fontsize=7.4, lw=0.6, radius=0.003)
        box(ax, L + 21.6, y, 9.5, 3.7, "Tensor Core", face="#dcecc2", edge=GPU_C,
            fontsize=7.6, lw=0.6, radius=0.003)
    box(ax, L + 32.0, 61.5, 12.4, 8.0, "256 KB\nregister file", face=PANEL, edge=MUTED,
        fontsize=8.0, lw=0.7, radius=0.005)
    box(ax, L + 3.4, 58.4, 41.0, 2.7, "256 KB L1 / shared   +   TMA async copy engine",
        face="#f0f4e6", edge=MUTED, fontsize=8.2, lw=0.6, radius=0.003)

    box(ax, L + 2, 50.4, 43, 5.2, "L2 cache: 50 MB (H100) → 126 MB (B200)",
        face="#e8f0d8", edge=GPU_C, fontsize=10.2, weight="bold")
    ax.text(L + 23.5, 51.5, "hardware-managed, partitioned crossbar", ha="center",
            fontsize=8.2, color=MUTED, style="italic")
    box(ax, L + 2, 41.5, 43, 6.4, "HBM3  80 GB  @  3.35 TB/s", face="#dceac0",
        edge=GPU_C, fontsize=11.0, weight="bold")
    ax.text(L + 23.5, 42.7, "H100 SXM5;  B200: 180–186 GB HBM3e @ 7.7–8.0 TB/s",
            ha="center", fontsize=8.4, color=INK)
    box(ax, L + 2, 34.4, 20.8, 5.4, "NVLink 4: 900 GB/s per GPU\n→ 8-GPU scale-up domain",
        face="#ffffff", edge=ACCENT, fontsize=8.6)
    box(ax, L + 24.2, 34.4, 20.8, 5.4, "PCIe Gen5 128 GB/s to host\nIB / Ethernet for scale-out",
        face="#ffffff", edge=MUTED, fontsize=8.6)

    note(ax, L + 2.6, 31.0,
         "How work gets scheduled\n"
         "•  32-thread warps; the hardware hides memory latency by switching warps\n"
         "•  Caches decide what stays on chip, so occupancy is a negotiation\n"
         "•  Any kernel shape runs: irregular, dynamic, data-dependent code included\n"
         "•  Price of generality: control logic, cache tags and scheduling silicon\n"
         "    replicated in all 132 SMs, plus run-to-run timing variance",
         fontsize=9.0)

    # ============================ TPU ============================
    R = 52.0
    box(ax, R, 2, 47, 96, "", face="#f7fafe", edge=TPU_C, lw=1.8, radius=0.010)
    ax.text(R + 23.5, 94.6, "TPU chip  —  domain-specific matrix engine",
            ha="center", fontsize=12.4, fontweight="bold", color=TPU_C)

    box(ax, R + 2, 62.0, 43, 30.0, "", face="#ffffff", edge=TPU_C, radius=0.006)
    ax.text(R + 3.4, 89.8, "TensorCore   (2 per chip on v4, v5p and v7)", fontsize=9.8,
            fontweight="bold", color=INK)

    box(ax, R + 3.4, 71.0, 25.0, 16.5, "", face="#eaf1fd", edge=TPU_C, lw=0.9, radius=0.004)
    ax.text(R + 15.9, 85.4, "MXU: 256 × 256 systolic array", ha="center", fontsize=8.4,
            fontweight="bold", color=INK)
    for i in range(5):
        for j in range(11):
            box(ax, R + 4.9 + j * 2.1, 72.6 + i * 2.3, 1.7, 1.8, "",
                face="#c9dcfa", edge="#8fb4ef", lw=0.4, radius=0.001)
    ax.text(R + 15.9, 71.5, "16,384 MACs/cycle from one instruction", ha="center",
            fontsize=7.2, color=MUTED, style="italic")
    box(ax, R + 29.6, 71.0, 14.2, 16.5, "VPU\n128 lanes\n× 16 ALUs\n\nsoftmax,\nlayernorm,\nelementwise",
        face="#eaf1fd", edge=TPU_C, fontsize=8.0, lw=0.9)
    box(ax, R + 3.4, 63.2, 40.4, 6.0, "VMEM: 64 MiB software-managed scratchpad",
        face="#dce8fb", edge=TPU_C, fontsize=9.6, weight="bold")
    ax.text(R + 23.6, 64.4, "split between the current tile and the next weight prefetch",
            ha="center", fontsize=7.9, color=INK)

    box(ax, R + 2, 54.6, 43, 5.4, "4 × SparseCore", face="#e3ecfb", edge=TPU_C,
        fontsize=10.2, weight="bold")
    ax.text(R + 23.5, 55.7, "embedding gather/scatter + collective offload over ICI",
            ha="center", fontsize=8.4, color=INK)
    box(ax, R + 2, 48.6, 43, 5.2, "no L1 · no L2 · no cache tags", face="#ffffff",
        edge=WARN, fontsize=10.4, weight="bold", color=WARN, ls="--")
    ax.text(R + 23.5, 49.7, "XLA statically places every byte at compile time", ha="center",
            fontsize=8.4, color=WARN, style="italic")

    box(ax, R + 2, 41.5, 43, 6.4, "HBM3E  192 GiB  @  7.38 TB/s", face="#cfe0fa",
        edge=TPU_C, fontsize=11.0, weight="bold")
    ax.text(R + 23.5, 42.7, "TPU v7: 8 stacks across 2 compute dies", ha="center",
            fontsize=8.4, color=INK)
    box(ax, R + 2, 34.4, 43, 5.4,
        "ICI 1.2 TB/s per chip  →  9,216-chip 3D torus, optically circuit-switched,\n1.77 PB of directly addressable HBM per pod",
        face="#ffffff", edge=TPU_C, fontsize=8.6)

    note(ax, R + 2.6, 31.0,
         "How work gets scheduled\n"
         "•  One instruction stream drives a 2D operand fabric — Google's own\n"
         "    classification is \u201cSingle Instruction 2D Data\u201d, 1 thread per core\n"
         "•  No warps, no divergence, no cache misses: the compiler owns movement\n"
         "•  Near-deterministic step time is what makes 9,216-chip synchronous\n"
         "    training practical\n"
         "•  Price of specialisation: static shapes, and matmuls must fill 256 lanes",
         fontsize=9.0)

    save(fig, "fig01_gpu_vs_tpu_block.png", SRC_1)


# --------------------------------------------------------------------------
# 2. Systolic array dataflow
# --------------------------------------------------------------------------
def fig02_systolic_array():
    fig, axes = plt.subplots(1, 4, figsize=(15.4, 5.1))
    titleblock(
        fig,
        "Weight-stationary systolic dataflow: why a 256×256 array beats a register file for matmul",
        "A 4×4 slice of an MXU computing Y = A·W. Weights stay resident; activations pulse in from the left; partial sums accumulate downward.",
        top=0.82,
    )
    n = 4
    for t, ax in enumerate(axes):
        blank_axes(ax, (-1.35, n + 0.5), (-1.6, n + 0.7))
        ax.set_title(f"cycle t = {t}", fontsize=11, color=INK)
        for i in range(n):
            for j in range(n):
                active = (i + j) == t
                box(ax, j, n - 1 - i, 0.9, 0.9, f"w{i}{j}",
                    face="#1a73e8" if active else "#eaf1fd", edge=TPU_C,
                    color="white" if active else INK, fontsize=8.4,
                    weight="bold" if active else "normal", radius=0.06,
                    lw=1.1 if active else 0.7)
        for i in range(n):
            idx = t - i
            if 0 <= idx < n:
                ax.text(-0.80, n - 0.55 - i, f"a{idx}", fontsize=8.8, color=ACCENT2,
                        ha="center", va="center", fontweight="bold")
                arrow(ax, (-0.48, n - 0.55 - i), (-0.06, n - 0.55 - i), color=ACCENT2, lw=1.1)
        for j in range(min(t + 1, n)):
            arrow(ax, (j + 0.45, -0.08), (j + 0.45, -0.68), color=ACCENT3, lw=1.1)
        ax.text(n / 2 - 0.4, -1.15, "partial sums → accumulator", ha="center",
                fontsize=8.0, color=ACCENT3)

    fig.text(
        0.5,
        -0.13,
        "The wavefront (dark cells) is what \u201csystolic\u201d means: each activation is consumed by one cell, then handed to its neighbour, so one operand\n"
        "entering the edge is reused N times inside the array. Arithmetic scales with N\u00b2 (the number of cells) while edge traffic scales with N — the\n"
        "opposite of a register-file machine, where every multiply-accumulate needs its own operand fetch and result writeback. On Ironwood a single\n"
        "256\u00d7256 MXU issues 16,384 MACs per cycle from one instruction. The trade: a matmul whose contracting dimension is not a multiple of 256\n"
        "leaves part of the array idle, which is why flash-attention kernels underutilise the newer wide MXUs.",
        ha="center",
        fontsize=8.9,
        color=INK,
        linespacing=1.6,
    )
    save(fig, "fig02_systolic_array.png")


# --------------------------------------------------------------------------
# 3. Execution model: SIMT latency hiding vs static compiler schedule
# --------------------------------------------------------------------------
def fig03_execution_model():
    fig = plt.figure(figsize=(15.4, 7.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[2.4, 1.0], hspace=0.55, wspace=0.10)
    titleblock(
        fig,
        "Dynamic latency hiding vs static scheduling",
        "The same matmul-plus-memory workload: as the GPU runs it (left), and as the TPU compiler schedules it (right).",
        top=0.86,
    )

    axg = fig.add_subplot(gs[0, 0])
    blank_axes(axg, (-6.0, 20), (-1.4, 6.5))
    axg.set_title("GPU: four warps interleaved by the hardware scheduler",
                  fontsize=11.5, color=GPU_C)
    rng = np.random.default_rng(7)
    for w in range(4):
        y = 5 - w * 1.25
        axg.text(-0.35, y + 0.28, f"warp {w}", fontsize=8.6, color=MUTED, ha="right",
                 va="center")
        x = 0.2 + w * 0.6
        while x < 19:
            comp = rng.uniform(0.8, 1.7)
            box(axg, x, y, comp, 0.56, "", face="#dcecc2", edge=GPU_C, lw=0.6, radius=0.05)
            x += comp
            stall = rng.uniform(1.0, 3.2)
            box(axg, x, y, stall, 0.56, "", face="#f2f5ec", edge=GRID, lw=0.6, radius=0.05,
                ls="--")
            x += stall
    box(axg, 0.2, 0.15, 3.0, 0.52, "compute", face="#dcecc2", edge=GPU_C, fontsize=8.2)
    box(axg, 3.6, 0.15, 4.6, 0.52, "stall on memory", face="#f2f5ec", edge=GRID,
        fontsize=8.2, ls="--")
    note(axg, -6.0, -0.35,
         "Cache hit or miss is decided at run time, so per-warp stalls vary. The scheduler swaps in\n"
         "another warp to keep the SM busy — generality bought with jitter.", fontsize=8.4)

    axt = fig.add_subplot(gs[0, 1])
    blank_axes(axt, (-6.5, 20), (-1.4, 6.5))
    axt.set_title("TPU: one compiler-scheduled pipeline, nothing decided at run time",
                  fontsize=11.5, color=TPU_C)
    lanes = [
        ("DMA in (HBM→VMEM)", "#cfe0fa"),
        ("MXU matmul", "#1a73e8"),
        ("VPU softmax / norm", "#9dbff6"),
        ("DMA out + ICI collective", "#dce8fb"),
    ]
    for i, (name, colour) in enumerate(lanes):
        y = 5 - i * 1.25
        axt.text(-0.35, y + 0.28, name, fontsize=8.2, color=MUTED, ha="right", va="center")
        for k in range(6):
            box(axt, 0.2 + k * 3.15 + i * 0.16, y, 2.85, 0.56, "",
                face=colour, edge=TPU_C, lw=0.6, radius=0.05)
    note(axt, -6.5, -0.35,
         "Every tile movement is placed at compile time by XLA. Nothing waits on a cache, nothing is\n"
         "rescheduled, and the four stages overlap by construction. Shapes must be static.",
         fontsize=8.4)

    axh = fig.add_subplot(gs[1, :])
    axh.set_title("Consequence at cluster scale: the distribution of per-step times",
                  fontsize=10.8)
    x = np.linspace(0.86, 1.32, 600)
    gpu = np.exp(-((x - 1.045) ** 2) / (2 * 0.048 ** 2)) + 0.35 * np.exp(-((x - 1.17) ** 2) / (2 * 0.055 ** 2))
    tpu = np.exp(-((x - 1.0) ** 2) / (2 * 0.011 ** 2))
    axh.fill_between(x, gpu / gpu.max(), color=GPU_C, alpha=0.30,
                     label="GPU cluster: cache, clock and scheduler jitter, plus stragglers")
    axh.fill_between(x, tpu / tpu.max(), color=TPU_C, alpha=0.35,
                     label="TPU pod: static schedule — \u201cvery little variation in step time\u201d (Gemini report)")
    axh.set_xlabel("step time, normalised to the fastest rank")
    axh.set_xlim(0.86, 1.32)
    axh.set_ylim(0, 1.5)
    axh.set_yticks([])
    axh.legend(loc="upper right", fontsize=9.0)
    axh.text(0.875, 0.62,
             "In synchronous training the slowest rank sets\nthe pace, so cutting variance is worth more\nthan cutting the mean.",
             fontsize=8.6, color=INK, va="top")
    save(
        fig,
        "fig03_execution_model.png",
        "The bottom panel illustrates the mechanism described in Google's Gemini technical report and NVIDIA's CUDA scheduling documentation; "
        "the curves are schematic, not measurements.",
    )


# --------------------------------------------------------------------------
# 4. Memory hierarchy comparison
# --------------------------------------------------------------------------
def fig04_memory_hierarchy():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.6))
    titleblock(
        fig,
        "Where the bytes live: hardware caches, software scratchpads, and SRAM-only",
        "Capacity per chip on a log scale, bandwidth as annotated. Every serious non-GPU design has concluded that the compiler should place data explicitly.",
        top=0.85,
    )

    stacks = [
        ("GPU — hardware caches", GPU_C, [
            ("Registers  256 KB per SM", 33, "33 MB total on H100; ~20 TB/s aggregate"),
            ("L1 / shared  256 KB per SM", 33, "up to 228 KB usable as shared memory"),
            ("L2 cache  50 MB → 126 MB", 126, "hardware-managed, partitioned crossbar"),
            ("HBM3 / HBM3e  80–192 GB", 192_000, "3.35 → 8.0 TB/s"),
        ]),
        ("TPU — compiler scratchpads", TPU_C, [
            ("Register file  0.25 MiB", 0.25, "per TensorCore, unchanged v3 → v4"),
            ("VMEM  32 MiB (v4) → 128 MiB (v7)", 128, "explicitly tiled by XLA"),
            ("CMEM 128 MiB + SparseCore SMEM", 138, "load/store scratchpad, no tags"),
            ("HBM2 / HBM3E  32–192 GiB", 192_000, "1.2 → 7.38 TB/s"),
        ]),
        ("SRAM-only designs", ACCENT2, [
            ("Groq LPU v1  230 MB", 230, "80 TB/s, no DRAM at all"),
            ("Maia 200  272 MB / TPU 8i  384 MB", 384, "fully software-managed"),
            ("Groq 3 LPU  512 MB", 512, "150 TB/s"),
            ("Cerebras WSE-3  44 GB on wafer", 44_000, "21 PB/s"),
        ]),
    ]

    for ax, (title, colour, levels) in zip(axes, stacks):
        ax.set_title(title, fontsize=12, color=colour)
        ax.set_xscale("log")
        ax.set_xlim(0.1, 5_000_000)
        ax.set_ylim(-0.55, len(levels) - 0.25)
        ax.set_yticks([])
        ax.set_xlabel("capacity per chip (MB, log scale)")
        for i, (label, mb, bw) in enumerate(levels):
            y = len(levels) - 1 - i
            ax.barh(y, mb, height=0.46, color=colour, alpha=0.20 + 0.18 * i, edgecolor=colour)
            ax.text(0.14, y + 0.32, label, fontsize=8.8, color=INK, va="center", ha="left")
            ax.text(0.14, y - 0.14, bw, fontsize=8.0, color=MUTED, va="center", ha="left",
                    style="italic")
        ax.grid(axis="y", visible=False)

    fig.text(
        0.5,
        -0.07,
        "The GPU spends silicon on tags, coherence and replacement policy so that any access pattern works. The TPU spends the same silicon on more\n"
        "MACs and hands the placement problem to XLA. Groq and Cerebras take it to the limit and delete DRAM entirely, which buys enormous bandwidth\n"
        "per byte and forces you to shard a 70B model across hundreds of chips.",
        ha="center", fontsize=8.9, color=INK, linespacing=1.6,
    )
    save(fig, "fig04_memory_hierarchy.png")


# --------------------------------------------------------------------------
# 5. Interconnect topologies
# --------------------------------------------------------------------------
def fig05_topology():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.6))
    titleblock(
        fig,
        "Scale-up fabrics: 8-GPU node, 72-GPU rack, and an optically switched 3D torus",
        "The size of the coherent high-bandwidth domain decides which parallelism strategies are affordable at all.",
        top=0.85,
    )

    # --- HGX 8-GPU ---
    ax = axes[0]
    blank_axes(ax, (0, 10), (0, 10))
    ax.set_title("HGX H100 / B200\n8 GPUs, NVSwitch on the baseboard", fontsize=10.8,
                 color=GPU_C)
    box(ax, 0.5, 6.4, 9.0, 1.1, "4 × NVSwitch", face="#e8f0d8", edge=GPU_C,
        fontsize=9.6, weight="bold")
    for i in range(8):
        x = 0.5 + i * 1.14
        box(ax, x, 3.4, 0.95, 1.7, f"GPU\n{i}", face="#dcecc2", edge=GPU_C, fontsize=7.6)
        arrow(ax, (x + 0.475, 5.1), (x + 0.475, 6.4), color=GPU_C, lw=1.0)
    note(ax, 0.5, 2.9,
         "•  NVLink 4: 900 GB/s per GPU\n    (NVLink 5 on Blackwell: 1.8 TB/s)\n"
         "•  Tensor parallelism must stay inside\n    these 8 GPUs\n"
         "•  Above 8 GPUs you cross InfiniBand or\n    Ethernet at ~50 GB/s per GPU —\n    roughly 18× less bandwidth",
         fontsize=8.6)

    # --- NVL72 ---
    ax = axes[1]
    blank_axes(ax, (0, 10), (0, 10))
    ax.set_title("GB200 / GB300 NVL72\n72 GPUs, switches moved into the rack",
                 fontsize=10.8, color=GPU_C)
    box(ax, 4.05, 3.0, 1.9, 6.4, "9 NVLink\nswitch\ntrays\n\n18\nNVSwitch\nASICs\n\n130 TB/s\nall-to-all",
        face="#e8f0d8", edge=GPU_C, fontsize=8.0, weight="bold")
    for side, x0 in ((0, 0.4), (1, 6.5)):
        for r in range(9):
            y = 8.6 - r * 0.67
            box(ax, x0, y, 3.1, 0.52, "4 GPU + 2 Grace", face="#dcecc2", edge=GPU_C,
                fontsize=6.6, lw=0.6, radius=0.03)
            arrow(ax, (x0 + 3.1, y + 0.26) if side == 0 else (x0, y + 0.26),
                  (4.05, y + 0.26) if side == 0 else (5.95, y + 0.26),
                  color=GPU_C, lw=0.7)
    ax.text(5.0, 2.55, "18 compute trays", ha="center", fontsize=8.2, color=MUTED,
            style="italic")
    note(ax, 0.4, 2.2,
         "•  18 NVLink 5 ports per GPU — exactly one\n    to each NVSwitch ASIC\n"
         "•  Non-blocking and flat: no GPU pair is\n    closer than any other\n"
         "•  TP can exceed 8, and MoE all-to-all fits\n    inside a single rack\n"
         "•  132–140 kW, liquid cooled, ~1.4 t",
         fontsize=8.6)

    # --- TPU torus + OCS ---
    ax = axes[2]
    blank_axes(ax, (0, 10), (0, 10))
    ax.set_title("TPU v4 / v5p / v7 pod\n4×4×4 cubes wired by optical circuit switches",
                 fontsize=10.8, color=TPU_C)

    def cube(ox, oy, s=0.52, colour=TPU_C):
        pts = {}
        for i in range(3):
            for j in range(3):
                for k in range(2):
                    pts[(i, j, k)] = (ox + j * s + k * s * 0.55,
                                      oy + (2 - i) * s + k * s * 0.42)
        for (i, j, k), (x, y) in pts.items():
            ax.add_patch(plt.Circle((x, y), 0.075, color=colour, alpha=0.35 + 0.3 * k,
                                    zorder=4))
        for (i, j, k), (x, y) in pts.items():
            for di, dj, dk in ((0, 1, 0), (1, 0, 0), (0, 0, 1)):
                nb = (i + di, j + dj, k + dk)
                if nb in pts:
                    x2, y2 = pts[nb]
                    ax.plot([x, x2], [y, y2], color=colour, lw=0.7, alpha=0.55, zorder=3)

    for ox, oy in ((0.45, 7.0), (3.0, 7.0), (0.45, 4.6), (3.0, 4.6)):
        cube(ox, oy)
    box(ax, 5.9, 4.4, 3.6, 4.6, "Optical Circuit\nSwitch\n\nre-wires cubes\nin ~10 s\n\n"
        "any 3D torus\nshape, twisted\ntori, or a route\naround a dead\ncube",
        face="#e3ecfb", edge=TPU_C, fontsize=8.2, weight="bold")
    for oy in (7.6, 5.2):
        arrow(ax, (4.9, oy), (5.85, oy), color=TPU_C, lw=1.0)
    note(ax, 0.45, 4.0,
         "•  64 chips per cube on copper; cubes joined\n    optically\n"
         "•  v7 pod = 144 cubes = 9,216 chips =\n    1.77 PB of shared HBM\n"
         "•  Nearest-neighbour collectives need no\n    switch hop at all\n"
         "•  Failed cube → OCS swaps in a spare and\n    the logical shape is unchanged",
         fontsize=8.6)

    save(
        fig,
        "fig05_topology.png",
        "Sources: NVIDIA GB200 NVL72 reference architecture; Jouppi et al. ISCA 2023; Google Cloud \u201cInside the Ironwood TPU codesigned AI stack\u201d.",
    )


# --------------------------------------------------------------------------
# 6. Parallelism mapped onto the hardware hierarchy
# --------------------------------------------------------------------------
def fig06_parallelism():
    fig, ax = plt.subplots(figsize=(15.0, 7.8))
    blank_axes(ax, (0, 100), (0, 57))
    titleblock(
        fig,
        "Which parallelism can live on which wire",
        "Each band is a level of the hardware hierarchy. A parallelism axis is only affordable where its communication fits the available bandwidth.",
        top=0.88,
    )

    bands = [
        (39.0, "Across datacenters", "WAN, asynchronous — used for the outermost data-parallel replica only",
         "#f0eef7", [("Data parallel / FSDP", "#5b6b7a",
                      "one gradient all-reduce per step;\n2(N−1)/N × bytes, independent of N")]),
        (26.5, "Scale-out fabric", "InfiniBand XDR / Spectrum-X Ethernet / TPU DCN  —  50–100 GB/s per chip",
         "#fde8cf", [("Pipeline parallel (PP)", ACCENT2,
                      "point-to-point activations at stage\nboundaries; bubble = (P−1)/(V·M)"),
                     ("Context / sequence parallel", ACCENT3,
                      "ring or all-gather of K,V across\nthe sequence dimension")]),
        (14.0, "Scale-up domain", "NVLink 0.9–3.6 TB/s per GPU  •  TPU ICI 1.2 TB/s  •  domain = 8 → 72 → 9,216 chips",
         "#cfe0fa", [("Tensor parallel (TP)", ACCENT,
                      "4 all-reduces of the full activation\ntensor per transformer layer"),
                     ("Expert parallel (EP)", ACCENT4,
                      "all-to-all token routing in every\nMoE layer — the hungriest collective")]),
        (1.5, "Inside one chip", "HBM 3.35–22 TB/s  •  SRAM scratchpads at 10–150 TB/s",
         "#dcecc2", [("Microbatching, recomputation, FlashAttention tiling", "#4a6b2a",
                      "trade FLOPs for bytes so the kernel\nstays above the roofline ridge")]),
    ]

    for y, name, detail, colour, axes_list in bands:
        box(ax, 1.5, y, 97, 11.0, "", face=colour, edge=MUTED, lw=0.8, radius=0.006)
        ax.text(3.2, y + 7.9, name, fontsize=11.0, fontweight="bold", color=INK)
        ax.text(3.2, y + 4.6, detail, fontsize=8.6, color=MUTED)
        n = len(axes_list)
        for i, (label, colour2, note_txt) in enumerate(axes_list):
            w = 26.0 if n == 2 else 40.0
            x = 44.0 + i * 27.5 if n == 2 else 56.0
            box(ax, x, y + 1.2, w, 8.6, "", face=colour2, edge=colour2, alpha=0.20,
                radius=0.006)
            ax.text(x + w / 2, y + 7.7, label, ha="center", fontsize=9.4,
                    fontweight="bold", color=colour2)
            ax.text(x + w / 2, y + 3.9, note_txt, ha="center", fontsize=8.2, color=INK,
                    linespacing=1.4)

    ax.text(50, 54.0,
            "Llama 3.1 405B on 16,384 H100s:  TP=8 (pinned to the NVLink domain), CP=1, PP=16, DP=128  →  41% BF16 MFU\n"
            "DeepSeek-V3:  each token routed to at most 4 nodes, a limit chosen to match the 3.2:1 NVLink-to-InfiniBand bandwidth ratio",
            ha="center", fontsize=9.6, color=INK, fontweight="bold", linespacing=1.7)

    save(
        fig,
        "fig06_parallelism.png",
        "Sources: Megatron-LM (arXiv:1909.08053); ZeRO (arXiv:1910.02054); Llama 3 Herd of Models (arXiv:2407.21783); "
        "DeepSeek-V3 hardware paper (arXiv:2505.09343).",
    )


# --------------------------------------------------------------------------
# 7. Roofline
# --------------------------------------------------------------------------
def fig07_roofline():
    fig, ax = plt.subplots(figsize=(12.8, 7.4))
    machines = [
        ("H100 SXM  (989 TFLOP/s, 3.35 TB/s)", 989.5, 3.35, GPU_C, "-"),
        ("B200 in GB200  (2500, 8.0)", 2500.0, 8.00, "#4a7c00", "--"),
        ("TPU v7 Ironwood  (2307, 7.38)", 2307.0, 7.38, TPU_C, "-"),
        ("MI355X  (2517, 8.0)", 2516.6, 8.00, "#e2231a", ":"),
    ]
    I = np.logspace(-0.3, 4.2, 700)
    for name, peak, bw, colour, ls in machines:
        bw_flops = bw * 1000.0
        ax.plot(I, np.minimum(peak, I * bw_flops), color=colour, lw=2.1, ls=ls, label=name)
        ridge = peak / bw_flops
        ax.plot([ridge], [peak], "o", color=colour, ms=6)
        ax.annotate(f"ridge {ridge:.0f}", (ridge, peak), textcoords="offset points",
                    xytext=(9, -13), fontsize=8.6, color=colour, fontweight="bold")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("arithmetic intensity  (FLOP per byte moved from HBM)")
    ax.set_ylabel("achievable throughput  (dense TFLOP/s, BF16)")
    ax.set_title("Roofline: three unrelated architectures converge on ~300 FLOP per byte")
    ax.set_xlim(0.5, 16000)
    ax.set_ylim(1, 7000)

    for x, label, colour in [
        (1.0, "decode, batch 1", WARN),
        (32.0, "decode, batch 32", WARN),
        (295.0, "decode, batch ≈300", ACCENT2),
        (341.0, "square GEMM n=1024", ACCENT3),
        (8192.0, "prefill, 8k context", ACCENT4),
    ]:
        ax.axvline(x, color=colour, lw=0.9, ls=":", alpha=0.85)
        ax.text(x * 1.07, 1.35, label, rotation=90, fontsize=8.6, color=colour, va="bottom")

    ax.fill_between([0.5, 295], 1, 7000, color=WARN, alpha=0.045)
    ax.text(6.0, 3600, "memory-bandwidth-bound\nevery token of inference decode lives here",
            fontsize=9.8, color=WARN, ha="center", fontweight="bold")
    ax.text(2600, 26, "compute-bound\ntraining GEMMs and prefill", fontsize=9.8,
            color=ACCENT3, ha="center", fontweight="bold")
    ax.legend(loc="lower right", title="peak / HBM bandwidth", title_fontsize=9)

    save(
        fig,
        "fig07_roofline.png",
        "Ridge point = dense peak ÷ HBM bandwidth. Decode intensity ≈ 2·batch / bytes-per-element, so an H100 needs a batch near 300 before its "
        "tensor cores stop waiting on memory. FP8 does not move the crossover: it halves the bytes and doubles the peak.",
    )


# --------------------------------------------------------------------------
# 8. Precision formats and block scaling
# --------------------------------------------------------------------------
def fig08_precision():
    fig = plt.figure(figsize=(15.4, 7.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.10)
    titleblock(
        fig,
        "Number formats: what got thrown away, and what the scale factor puts back",
        "Left: bit layouts. Right: the two competing 4-bit block formats, and the measured cost of getting the metadata wrong.",
        top=0.86,
    )

    ax = fig.add_subplot(gs[0, 0])
    formats = [
        ("FP32", 1, 8, 23, "master weights, accumulation"),
        ("TF32", 1, 8, 10, "Ampere+ drop-in for FP32 GEMM"),
        ("BF16", 1, 8, 7, "the default training format"),
        ("FP16", 1, 5, 10, "needs loss scaling"),
        ("FP8 E4M3", 1, 4, 3, "forward activations, weights"),
        ("FP8 E5M2", 1, 5, 2, "gradients: range over precision"),
        ("FP6 E3M2", 1, 3, 2, "Blackwell inference"),
        ("FP4 E2M1", 1, 2, 1, "Blackwell / CDNA4 tensor cores"),
    ]
    blank_axes(ax, (-11.0, 46), (-1.1, len(formats) - 0.2))
    ax.set_title("Bit layout: sign, exponent, mantissa", fontsize=11.5)
    for i, (name, s, e, m, use) in enumerate(formats):
        y = len(formats) - 1 - i
        ax.text(-0.7, y + 0.22, name, fontsize=9.6, ha="right", va="center",
                fontweight="bold", color=INK)
        box(ax, 0, y, s, 0.46, "", face="#c9d3dc", edge=MUTED, radius=0.01)
        box(ax, s, y, e, 0.46, f"E{e}" if e < 6 else f"exponent {e}", face="#f6c8a8",
            edge=ACCENT2, fontsize=7.4, radius=0.01)
        box(ax, s + e, y, m, 0.46, f"M{m}" if m < 6 else f"mantissa {m}", face="#bcd7f7",
            edge=ACCENT, fontsize=7.4, radius=0.01)
        ax.text(s + e + m + 1.0, y + 0.22, use, fontsize=8.4, color=MUTED, va="center")
    note(ax, -11.0, -0.30,
         "BF16 keeps FP32's 8 exponent bits and spends the mantissa instead. Training tolerates\n"
         "low precision far better than it tolerates overflow or underflow, which is why BF16 needs\n"
         "no loss scaling and displaced FP16 as the default format.",
         fontsize=8.6)

    ax2 = fig.add_subplot(gs[0, 1])
    blank_axes(ax2, (0, 10), (0, 10))
    ax2.set_title("MXFP4 (OCP standard) vs NVFP4 (NVIDIA)", fontsize=11.5)

    box(ax2, 0.2, 6.9, 9.6, 2.9, "", face="#fdf4ea", edge=ACCENT2)
    ax2.text(0.5, 9.35, "MXFP4", fontsize=10.4, fontweight="bold", color=ACCENT2)
    ax2.text(1.6, 9.35, "32 elements share one E8M0 power-of-two scale", fontsize=9.0,
             color=INK, va="center")
    for k in range(32):
        box(ax2, 0.5 + k * 0.28, 8.05, 0.23, 0.55, "", face="#f6c8a8", edge=ACCENT2,
            lw=0.4, radius=0.01)
    box(ax2, 0.5, 7.20, 2.1, 0.60, "E8M0 scale", face="#e8a877", edge=ACCENT2, fontsize=7.8)
    ax2.text(2.9, 7.50, "4.25 bits/element  ·  one outlier can crush 31 neighbours",
             fontsize=8.4, color=INK, va="center")

    box(ax2, 0.2, 3.1, 9.6, 3.4, "", face="#eef4fd", edge=ACCENT)
    ax2.text(0.5, 6.05, "NVFP4", fontsize=10.4, fontweight="bold", color=ACCENT)
    ax2.text(1.6, 6.05, "16 elements share an E4M3 scale, plus a per-tensor FP32 scale",
             fontsize=9.0, color=INK, va="center")
    for k in range(16):
        box(ax2, 0.5 + k * 0.28, 4.85, 0.23, 0.55, "", face="#bcd7f7", edge=ACCENT,
            lw=0.4, radius=0.01)
    box(ax2, 0.5, 4.00, 2.1, 0.60, "E4M3 scale", face="#8fb4ef", edge=ACCENT, fontsize=7.8)
    box(ax2, 2.8, 4.00, 2.7, 0.60, "FP32 tensor scale", face="#c9dcfa", edge=ACCENT,
        fontsize=7.8)
    ax2.text(5.8, 4.30, "4.5 bits/element", fontsize=8.4, color=INK, va="center")
    ax2.text(0.5, 3.45, "a smaller block narrows the range each scale must cover; a floating-point scale keeps mantissa bits",
             fontsize=8.0, color=MUTED)

    box(ax2, 0.2, 0.3, 9.6, 2.4, "", face="#ffffff", edge=WARN)
    ax2.text(5.0, 2.30, "Measured, same recipe, 12B model, 10T tokens", ha="center",
             fontsize=9.2, fontweight="bold", color=WARN)
    ax2.text(5.0, 1.35,
             "NVFP4 held ~1.5% relative loss error against BF16 where MXFP4 reached ~2.5%.\n"
             "MXFP4 needed 1.36T tokens to match NVFP4 at 1.0T — a 36% token penalty, which is\n"
             "most of what FP4 was supposed to buy. \u201c4-bit\u201d is not one thing: the scaling\n"
             "metadata decides whether the format is usable.",
             ha="center", fontsize=8.6, color=INK, va="center", linespacing=1.55)

    save(
        fig,
        "fig08_precision.png",
        "Sources: OCP Microscaling Formats v1.0; NVIDIA \u201cPretraining LLMs with NVFP4\u201d (arXiv:2509.25149); NVIDIA Blackwell and Rubin "
        "architecture blogs.",
    )


DIAGRAMS = [
    fig01_gpu_vs_tpu_block,
    fig02_systolic_array,
    fig03_execution_model,
    fig04_memory_hierarchy,
    fig05_topology,
    fig06_parallelism,
    fig07_roofline,
    fig08_precision,
]


def main():
    apply_style()
    print("Architecture diagrams:")
    for fn in DIAGRAMS:
        fn()


if __name__ == "__main__":
    main()
