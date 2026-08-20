"""Data-driven figures. Every number is read from the CSVs in data/."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from theme import (
    ACCENT,
    ACCENT2,
    ACCENT3,
    ACCENT4,
    DATA,
    GPU_C,
    GRID,
    INK,
    MUTED,
    PANEL,
    TPU_C,
    VENDOR,
    WARN,
    apply_style,
    blank_axes,
    box,
    note,
    save,
    titleblock,
)

ACC = pd.read_csv(DATA / "accelerators.csv")
PRICE = pd.read_csv(DATA / "cloud_pricing.csv")
RUNS = pd.read_csv(DATA / "training_runs.csv")
MLPERF = pd.read_csv(DATA / "mlperf_training.csv")
BOM = pd.read_csv(DATA / "bom_costs.csv")
SUPPLY = pd.read_csv(DATA / "supply_chain.csv")
RACKS = pd.read_csv(DATA / "rack_systems.csv")
FAILURES = pd.read_csv(DATA / "llama3_failures.csv")


def spec(short_name: str) -> pd.Series:
    row = ACC[ACC.short_name == short_name]
    if row.empty:
        raise KeyError(short_name)
    return row.iloc[0]


def vcolor(vendor: str) -> str:
    return VENDOR.get(vendor, MUTED)


def thousands(x, _pos):
    if x >= 1000:
        return f"{x/1000:g}k"
    return f"{x:g}"


# --------------------------------------------------------------------------
# 9. Compute throughput timeline
# --------------------------------------------------------------------------
def fig09_compute_timeline():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 6.8))
    titleblock(
        fig,
        "Per-chip throughput, 2017–2026: the gains come as much from narrower numbers as from silicon",
        "Dense rates only. Vendor headline figures that assume 2:1 structured sparsity have been halved.",
        top=0.85,
    )

    picks = [
        "V100", "A100 80GB", "H100", "H200", "B200 NVL72", "B300 NVL72", "Rubin R100",
        "MI250X", "MI300X", "MI355X", "MI455X",
        "Gaudi 2", "Gaudi 3",
        "TPU v2", "TPU v3", "TPU v4", "TPU v5p", "TPU v6e", "TPU v7",
        "Trainium1", "Trainium2", "Trainium3", "Ascend 910C", "Maia 200",
    ]
    df = ACC[ACC.short_name.isin(picks)].copy()

    for ax, col, label in (
        (ax1, "fp16bf16_dense_tflops", "dense BF16/FP16 TFLOP/s"),
        (ax2, "fp8_dense_tflops", "dense FP8 TFLOP/s  (FP4 shown hollow)"),
    ):
        for vendor, grp in df.groupby("vendor"):
            grp = grp.dropna(subset=[col]).sort_values("launch_year")
            if grp.empty:
                continue
            ax.plot(grp.launch_year, grp[col], "-o", color=vcolor(vendor), ms=6, lw=1.8,
                    label=vendor, alpha=0.9)
            for _, r in grp.iterrows():
                ax.annotate(r.short_name, (r.launch_year, r[col]),
                            textcoords="offset points", xytext=(6, 4), fontsize=7.6,
                            color=vcolor(vendor))
        ax.set_yscale("log")
        ax.set_xlabel("launch year")
        ax.set_ylabel(label)
        ax.set_xlim(2016.5, 2027.2)
        ax.yaxis.set_major_formatter(FuncFormatter(thousands))

    # FP4 overlay on the right panel
    fp4 = df.dropna(subset=["fp4_dense_tflops"])
    for _, r in fp4.iterrows():
        ax2.plot(r.launch_year, r.fp4_dense_tflops, "o", mfc="none", ms=9,
                 mec=vcolor(r.vendor), mew=1.6)
        ax2.annotate(f"{r.short_name} FP4", (r.launch_year, r.fp4_dense_tflops),
                     textcoords="offset points", xytext=(6, -11), fontsize=7.4,
                     color=vcolor(r.vendor))

    ax1.set_title("BF16: 20× in nine years", fontsize=11.5)
    ax2.set_title("FP8 and FP4: the real Blackwell/Rubin story", fontsize=11.5)
    ax1.legend(loc="upper left", ncol=2)
    ax1.annotate("V100 has no BF16 path\n(FP16 shown)", (2018, 125),
                 textcoords="offset points", xytext=(14, -34), fontsize=8.0, color=MUTED,
                 arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax2.annotate("Gaudi 3 has no FP8 speedup:\nFP8 rate equals its BF16 rate", (2024, 1835),
                 textcoords="offset points", xytext=(-120, -46), fontsize=8.0,
                 color=VENDOR["Intel"],
                 arrowprops=dict(arrowstyle="-", color=VENDOR["Intel"], lw=0.8))

    save(
        fig,
        "fig09_compute_timeline.png",
        "Sources: vendor datasheets and architecture blogs (see data/accelerators.csv). Rubin's NVFP4 figure is NVIDIA's published 35 PFLOPS "
        "training rate; NVIDIA has not clarified its dense/sparse basis.",
    )


# --------------------------------------------------------------------------
# 10. Memory capacity vs bandwidth
# --------------------------------------------------------------------------
def fig10_memory_scatter():
    fig, ax = plt.subplots(figsize=(13.4, 7.8))
    titleblock(
        fig,
        "HBM capacity vs bandwidth: the axis where AMD and the ASICs actually compete",
        "Bubble area ∝ chip TDP where published. HBM capacity is what decides how much sharding a model needs.",
        top=0.88,
    )
    picks = [
        "V100", "A100 80GB", "H100", "H200", "H20", "GH200", "B200 NVL72", "B300 NVL72",
        "Rubin R100", "MI250X", "MI300X", "MI325X", "MI355X", "MI455X", "Gaudi 2",
        "Gaudi 3", "TPU v4", "TPU v5p", "TPU v6e", "TPU v7", "TPU 8t", "TPU 8i",
        "Trainium2", "Trainium3", "Ascend 910C", "Maia 100", "Maia 200", "MTIA 400",
        "L40S", "RTX 5090",
    ]
    df = ACC[ACC.short_name.isin(picks)].dropna(subset=["memory_gb", "mem_bw_tbs"]).copy()
    for _, r in df.iterrows():
        size = 90 if pd.isna(r.tdp_w) else 60 + r.tdp_w * 0.42
        ax.scatter(r.memory_gb, r.mem_bw_tbs, s=size, color=vcolor(r.vendor), alpha=0.55,
                   edgecolor=vcolor(r.vendor), linewidth=1.4, zorder=3)
        ax.annotate(r.short_name, (r.memory_gb, r.mem_bw_tbs), textcoords="offset points",
                    xytext=(0, 11 + size / 90), fontsize=8.0, color=INK, ha="center")

    for gb, bw, label, colour in [
        (80, 3.35, "", None),
    ]:
        pass

    # iso-lines of bytes per FLOP are not meaningful here; show HBM generations instead
    ax.axhline(3.35, color=GRID, lw=0.8)
    ax.text(500, 3.45, "H100-class bandwidth", fontsize=8.2, color=MUTED, ha="right")
    ax.axhline(8.0, color=GRID, lw=0.8)
    ax.text(500, 8.15, "Blackwell / MI355X / HBM3e ceiling", fontsize=8.2, color=MUTED,
            ha="right")

    ax.set_xscale("log")
    ax.set_xlim(18, 560)
    ax.set_ylim(0, 25)
    ax.set_xlabel("memory per chip (GB, log scale)")
    ax.set_ylabel("memory bandwidth (TB/s)")
    ax.set_xticks([24, 32, 48, 80, 96, 128, 192, 256, 288, 432])
    ax.get_xaxis().set_major_formatter(FuncFormatter(lambda v, p: f"{v:g}"))
    handles = [Line2D([], [], marker="o", ls="", color=vcolor(v), label=v, ms=9, alpha=0.7)
               for v in sorted(df.vendor.unique())]
    ax.legend(handles=handles, loc="upper left", ncol=2, title="vendor", title_fontsize=9)

    note(ax, 22, 23.6,
         "HBM4 arrives on Rubin (288 GB @ 22 TB/s) and MI455X (432 GB @ ~23 TB/s):\n"
         "the first generation where bandwidth roughly triples rather than creeping up.",
         fontsize=9.0)
    save(
        fig,
        "fig10_memory_scatter.png",
        "Cerebras (44 GB of on-wafer SRAM at 21 PB/s) and Groq (0.5 GB at 150 TB/s) are off-scale by construction and omitted.",
    )


# --------------------------------------------------------------------------
# 11. Efficiency: per watt
# --------------------------------------------------------------------------
def fig11_perf_per_watt():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 7.0))
    titleblock(
        fig,
        "Efficiency per watt, where vendors publish enough to compute it",
        "Chip-level TDP only — it excludes CPU, NIC, switch and cooling, which are a third or more of rack power.",
        top=0.86,
    )
    picks = ["V100", "A100 80GB", "H100", "H200", "B200 NVL72", "B300 NVL72", "MI250X",
             "MI300X", "MI325X", "MI355X", "Gaudi 2", "Gaudi 3", "TPU v2", "TPU v3",
             "TPU v7", "Ascend 910C", "Maia 100", "Maia 200", "MTIA 400", "L40S",
             "RTX 5090"]
    df = ACC[ACC.short_name.isin(picks)].dropna(subset=["tdp_w"]).copy()

    d1 = df.dropna(subset=["fp16bf16_dense_tflops"]).copy()
    d1["gf_per_w"] = d1.fp16bf16_dense_tflops * 1000 / d1.tdp_w
    d1 = d1.sort_values("gf_per_w")
    ax1.barh(d1.short_name, d1.gf_per_w, color=[vcolor(v) for v in d1.vendor], alpha=0.85)
    ax1.set_xlabel("dense BF16 GFLOP/s per watt")
    ax1.set_title("Compute per watt", fontsize=11.5)
    for y, (v, n) in enumerate(zip(d1.gf_per_w, d1.short_name)):
        ax1.text(v + 40, y, f"{v:,.0f}", va="center", fontsize=8.2, color=INK)
    ax1.set_xlim(0, d1.gf_per_w.max() * 1.22)

    d2 = df.copy()
    d2["gb_per_w"] = d2.memory_gb / d2.tdp_w
    d2 = d2.sort_values("gb_per_w")
    ax2.barh(d2.short_name, d2.gb_per_w, color=[vcolor(v) for v in d2.vendor], alpha=0.85)
    ax2.set_xlabel("memory GB per watt")
    ax2.set_title("Memory per watt", fontsize=11.5)
    for y, v in enumerate(d2.gb_per_w):
        ax2.text(v + 0.006, y, f"{v:.3f}", va="center", fontsize=8.2, color=INK)
    ax2.set_xlim(0, d2.gb_per_w.max() * 1.22)

    handles = [Line2D([], [], marker="s", ls="", color=vcolor(v), label=v, ms=9)
               for v in sorted(df.vendor.unique())]
    ax1.legend(handles=handles, loc="lower right", ncol=2, fontsize=8.6)
    save(
        fig,
        "fig11_perf_per_watt.png",
        "Google publishes no per-chip TDP after v4; the TPU v7 value of ~1 kW is inferred from \u201cnearly 10 MW\u201d for a 9,216-chip pod and "
        "therefore includes rack overhead, making it a conservative comparison.",
    )


# --------------------------------------------------------------------------
# 12. Scale-up domain evolution
# --------------------------------------------------------------------------
def fig12_scaleup_evolution():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 6.6))
    titleblock(
        fig,
        "The scale-up domain is the number that changed most",
        "Left: how many chips sit inside one coherent high-bandwidth domain. Right: per-chip scale-up bandwidth.",
        top=0.86,
    )
    picks = ["V100", "A100 80GB", "H100", "GH200", "B200 NVL72", "B300 NVL72",
             "Rubin R100", "MI300X", "MI355X", "MI455X", "Gaudi 3", "TPU v3", "TPU v4",
             "TPU v5p", "TPU v7", "TPU 8t", "Trainium2", "Trainium3", "Ascend 910C",
             "Maia 200", "Groq 3"]
    df = ACC[ACC.short_name.isin(picks)].copy()

    d1 = df.dropna(subset=["scaleup_domain_chips"]).sort_values("scaleup_domain_chips")
    ax1.barh(d1.short_name, d1.scaleup_domain_chips,
             color=[vcolor(v) for v in d1.vendor], alpha=0.85)
    ax1.set_xscale("log")
    ax1.set_xlim(1, 30000)
    ax1.set_xlabel("chips in one scale-up domain (log scale)")
    ax1.set_title("Domain size: 8 → 72 → 9,216", fontsize=11.5)
    for y, v in enumerate(d1.scaleup_domain_chips):
        ax1.text(v * 1.15, y, f"{int(v):,}", va="center", fontsize=8.2, color=INK)
    ax1.grid(axis="y", visible=False)

    d2 = df.dropna(subset=["scaleup_bw_gbs"]).sort_values("scaleup_bw_gbs")
    ax2.barh(d2.short_name, d2.scaleup_bw_gbs / 1000.0,
             color=[vcolor(v) for v in d2.vendor], alpha=0.85)
    ax2.set_xlabel("scale-up bandwidth per chip (TB/s, bidirectional)")
    ax2.set_title("Per-chip fabric bandwidth", fontsize=11.5)
    for y, v in enumerate(d2.scaleup_bw_gbs / 1000.0):
        ax2.text(v + 0.05, y, f"{v:.2f}", va="center", fontsize=8.2, color=INK)
    ax2.set_xlim(0, (d2.scaleup_bw_gbs / 1000.0).max() * 1.2)
    ax2.grid(axis="y", visible=False)

    ax1.axvline(8, color=WARN, ls=":", lw=1.2)
    ax1.text(8.6, 0.4, "the 8-GPU wall that\ncapped TP for a decade", fontsize=8.4,
             color=WARN)
    save(
        fig,
        "fig12_scaleup_evolution.png",
        "\u201cScale-up domain\u201d = the set of chips a vendor presents as one coherent, uniformly high-bandwidth pool: NVLink/NVSwitch, TPU ICI, "
        "UALink-over-Ethernet, NeuronLink, Huawei UB.",
    )


# --------------------------------------------------------------------------
# 13. Rack and pod comparison
# --------------------------------------------------------------------------
def fig13_rack_systems():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.8))
    titleblock(
        fig,
        "Rack-scale and pod-scale systems: the unit customers actually buy in 2026",
        "Note the scale difference — a TPU superpod is 128 racks' worth of chips, so per-system totals are not like-for-like.",
        top=0.85,
    )
    keep = ["HGX H100 (8-GPU)", "GB200 NVL72", "GB300 NVL72", "Vera Rubin NVL72",
            "AMD Helios (MI455X)", "Trainium3 Gen2 UltraServer", "Huawei CloudMatrix 384",
            "TPU v7 Ironwood pod"]
    df = RACKS[RACKS.system.isin(keep)].copy()
    short = {
        "HGX H100 (8-GPU)": "HGX H100\n8 GPUs",
        "GB200 NVL72": "GB200\nNVL72",
        "GB300 NVL72": "GB300\nNVL72",
        "Vera Rubin NVL72": "Vera Rubin\nNVL72",
        "AMD Helios (MI455X)": "AMD Helios\n72 MI455X",
        "Trainium3 Gen2 UltraServer": "Trn3 Gen2\n144 chips",
        "Huawei CloudMatrix 384": "CloudMatrix\n384 chips",
        "TPU v7 Ironwood pod": "TPU v7 pod\n9,216 chips",
    }
    df["lbl"] = df.system.map(short)
    df = df.sort_values("fp8_dense_pflops", na_position="first")

    panels = [
        ("fp8_dense_pflops", "dense FP8 PFLOP/s per system", True),
        ("hbm_tb", "HBM capacity per system (TB)", True),
        ("scaleup_bw_tbs", "scale-up fabric bandwidth (TB/s)", True),
    ]
    for ax, (col, label, logscale) in zip(axes, panels):
        d = df.dropna(subset=[col]).copy()
        ax.barh(d.lbl, d[col], color=[vcolor(v) for v in d.vendor], alpha=0.85)
        if logscale:
            ax.set_xscale("log")
        ax.set_xlabel(label)
        for y, v in enumerate(d[col]):
            ax.text(v * 1.12, y, f"{v:,.0f}" if v >= 10 else f"{v:,.1f}", va="center",
                    fontsize=8.4, color=INK)
        ax.set_xlim(right=d[col].max() * 3.2)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=8.4)

    axes[0].set_title("Compute", fontsize=11.5)
    axes[1].set_title("Memory", fontsize=11.5)
    axes[2].set_title("Fabric", fontsize=11.5)
    save(
        fig,
        "fig13_rack_systems.png",
        "CloudMatrix 384 has no FP8 path so it is absent from the compute panel; its 300 PFLOPS BF16 comes at 559 kW versus 132 kW for a "
        "GB200 NVL72.",
    )


# --------------------------------------------------------------------------
# 14. Cloud pricing
# --------------------------------------------------------------------------
def fig14_cloud_prices():
    fig, ax = plt.subplots(figsize=(14.0, 8.4))
    titleblock(
        fig,
        "What an hour of accelerator actually costs, August 2026",
        "Same silicon, radically different prices. Provider tier moves the number more than the chip generation does.",
        top=0.89,
    )
    order = ["H100 SXM", "H200", "B200", "B300", "GB200", "A100 80GB", "MI300X",
             "MI355X", "Trainium1", "Trainium2", "TPU v5e", "TPU v5p", "TPU v6e Trillium",
             "TPU v7 Ironwood"]
    df = PRICE[PRICE.accelerator.isin(order)].copy()
    df["accelerator"] = pd.Categorical(df.accelerator, categories=order, ordered=True)
    df = df.sort_values(["accelerator", "usd_per_chip_hour"])

    tier_style = {
        "on-demand": ("o", ACCENT, 78),
        "community": ("o", ACCENT, 60),
        "marketplace": ("v", ACCENT3, 66),
        "spot": ("v", ACCENT3, 66),
        "capacity-block": ("s", ACCENT2, 62),
        "1yr-commit": ("D", ACCENT4, 52),
        "3yr-commit": ("D", ACCENT4, 52),
        "flex-start": ("P", ACCENT4, 66),
        "enterprise-contract": ("*", WARN, 160),
    }
    ypos = {name: i for i, name in enumerate(order)}
    for _, r in df.iterrows():
        marker, colour, size = tier_style.get(r.tier, ("o", MUTED, 50))
        y = ypos[r.accelerator] + np.random.default_rng(abs(hash(r.provider)) % 999).uniform(-0.22, 0.22)
        ax.scatter(r.usd_per_chip_hour, y, marker=marker, s=size, color=colour,
                   alpha=0.8, zorder=3, edgecolor="white", linewidth=0.5)

    for name, i in ypos.items():
        sub = df[df.accelerator == name]
        if sub.empty:
            continue
        lo, hi = sub.usd_per_chip_hour.min(), sub.usd_per_chip_hour.max()
        ax.plot([lo, hi], [i, i], color=GRID, lw=8, zorder=1, solid_capstyle="round")
        ax.text(hi * 1.06, i, f"{hi/lo:.1f}× spread", va="center", fontsize=8.2,
                color=MUTED)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.set_xscale("log")
    ax.set_xlim(0.2, 95)
    ax.set_xlabel("US$ per chip-hour (log scale)")
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    handles = [Line2D([], [], marker=m, ls="", color=c, ms=8, label=t)
               for t, (m, c, _) in tier_style.items()]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 0.18), ncol=2,
              title="pricing tier", title_fontsize=9, fontsize=9.0)
    save(
        fig,
        "fig14_cloud_prices.png",
        "The star is SemiAnalysis's estimate of Anthropic's negotiated Ironwood rate — 1.60 USD per chip-hour against Google's 12.00 list price. "
        "That 7.5\u00d7 gap is why \u201care TPUs cheaper?\u201d has no answer without knowing which price you would be offered.\n"
        "Sources: vendor rate cards (GCP TPU pricing, AWS Capacity Blocks, CoreWeave, RunPod, Oracle) plus price trackers for marketplace and "
        "spot tiers; see data/cloud_pricing.csv for per-row provenance.",
    )


# --------------------------------------------------------------------------
# 15. Price per PFLOP-hour and per TB/s-hour
# --------------------------------------------------------------------------
def fig15_price_per_flop():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 7.6))
    titleblock(
        fig,
        "Normalising price by what you get: dollars per dense PFLOP-hour and per TB/s-hour",
        "Computed from data/cloud_pricing.csv joined to data/accelerators.csv. Peak FLOPs are an upper bound — real MFU is 30–50%.",
        top=0.86,
    )
    rows = []
    for _, r in PRICE.iterrows():
        try:
            s = spec(r.spec_key)
        except KeyError:
            continue
        fp8 = s.fp8_dense_tflops
        bw = s.mem_bw_tbs
        if pd.isna(fp8) or fp8 == 0:
            continue
        rows.append({
            "label": f"{r.accelerator} · {r.provider}",
            "tier": r.tier,
            "vendor": s.vendor,
            "usd_per_pflop_h": r.usd_per_chip_hour / (fp8 / 1000.0),
            "usd_per_tbs_h": r.usd_per_chip_hour / bw,
            "price": r.usd_per_chip_hour,
        })
    d = pd.DataFrame(rows)
    keep_tiers = ["on-demand", "capacity-block", "3yr-commit", "spot", "marketplace",
                  "enterprise-contract", "community", "flex-start", "1yr-commit"]
    d = d[d.tier.isin(keep_tiers)]

    d1 = d.sort_values("usd_per_pflop_h").drop_duplicates("label").head(24).sort_values("usd_per_pflop_h")
    ax1.barh(d1.label, d1.usd_per_pflop_h, color=[vcolor(v) for v in d1.vendor], alpha=0.85)
    ax1.set_xlabel("US$ per dense FP8 PFLOP-hour")
    ax1.set_title("Cheapest 24 offers by compute", fontsize=11.5)
    for y, v in enumerate(d1.usd_per_pflop_h):
        ax1.text(v + 0.03, y, f"${v:.2f}", va="center", fontsize=8.0, color=INK)
    ax1.set_xlim(0, d1.usd_per_pflop_h.max() * 1.22)
    ax1.tick_params(axis="y", labelsize=8.0)
    ax1.grid(axis="y", visible=False)

    d2 = d.sort_values("usd_per_tbs_h").drop_duplicates("label").head(24).sort_values("usd_per_tbs_h")
    ax2.barh(d2.label, d2.usd_per_tbs_h, color=[vcolor(v) for v in d2.vendor], alpha=0.85)
    ax2.set_xlabel("US$ per TB/s of HBM bandwidth per hour  (the metric that governs decode)")
    ax2.set_title("Cheapest 24 offers by memory bandwidth", fontsize=11.5)
    for y, v in enumerate(d2.usd_per_tbs_h):
        ax2.text(v + 0.01, y, f"${v:.2f}", va="center", fontsize=8.0, color=INK)
    ax2.set_xlim(0, d2.usd_per_tbs_h.max() * 1.22)
    ax2.tick_params(axis="y", labelsize=8.0)
    ax2.grid(axis="y", visible=False)

    save(
        fig,
        "fig15_price_per_flop.png",
        "An H100 on a marketplace beats a B200 on a hyperscaler per FLOP-hour: for buyers below reserved-capacity scale, procurement channel "
        "dominates architecture.",
    )


# --------------------------------------------------------------------------
# 16. Bill of materials
# --------------------------------------------------------------------------
def fig16_bom():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 6.6),
                                   gridspec_kw={"width_ratios": [1.25, 1.0]})
    titleblock(
        fig,
        "Where the money goes: HBM is now the most expensive thing on the package",
        "Analyst-modelled build cost, not disclosed COGS. The lineage is the 2023 Raymond James H100 teardown, extended by Epoch AI and SemiAnalysis.",
        top=0.85,
    )
    d = BOM.copy()
    parts = ["logic_die_usd", "hbm_usd", "packaging_usd", "other_usd"]
    labels = ["logic die", "HBM stacks", "CoWoS packaging", "substrate, test, assembly"]
    colours = [ACCENT, ACCENT2, ACCENT3, MUTED]
    left = np.zeros(len(d))
    for part, label, colour in zip(parts, labels, colours):
        ax1.barh(d.chip, d[part], left=left, color=colour, alpha=0.85, label=label)
        left = left + d[part].values
    for y, (tot, sell) in enumerate(zip(d.total_mfg_usd, d.modeled_sell_usd)):
        ax1.text(tot + 260, y, f"build ${tot:,.0f}   →   sells for ~${sell:,.0f}",
                 va="center", fontsize=8.6, color=INK)
    ax1.set_xlabel("modelled manufacturing cost (US$)")
    ax1.set_xlim(0, 26000)
    ax1.legend(loc="lower right", ncol=2)
    ax1.grid(axis="y", visible=False)
    ax1.set_title("Build cost composition", fontsize=11.5)

    d["hbm_share"] = d.hbm_usd / d.total_mfg_usd * 100
    d["margin"] = (1 - d.total_mfg_usd / d.modeled_sell_usd) * 100
    x = np.arange(len(d))
    ax2.bar(x - 0.2, d.hbm_share, width=0.38, color=ACCENT2, alpha=0.85,
            label="HBM share of build cost (%)")
    ax2.bar(x + 0.2, d.margin, width=0.38, color=ACCENT, alpha=0.85,
            label="implied gross margin (%)")
    for i, (h, m) in enumerate(zip(d.hbm_share, d.margin)):
        ax2.text(i - 0.2, h + 1.2, f"{h:.0f}%", ha="center", fontsize=8.4, color=INK)
        ax2.text(i + 0.2, m + 1.2, f"{m:.0f}%", ha="center", fontsize=8.4, color=INK)
    ax2.set_xticks(x)
    ax2.set_xticklabels(d.chip, rotation=18, ha="right", fontsize=8.6)
    ax2.set_ylabel("percent")
    ax2.set_ylim(0, 100)
    ax2.legend(loc="lower left")
    ax2.set_title("HBM share and implied margin", fontsize=11.5)
    note(ax2, -0.45, 96,
         "NVIDIA's reported corporate gross margin is ~75%: rack-scale products bundle\n"
         "lower-margin CPUs, switches, NICs and cold plates that dilute the per-die figure.",
         fontsize=8.6)
    save(fig, "fig16_bom.png")


# --------------------------------------------------------------------------
# 17. Supply chain: packaging, HBM, wafers
# --------------------------------------------------------------------------
def fig17_supply():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.2))
    titleblock(
        fig,
        "The two chokepoints that decide how many accelerators exist: CoWoS packaging and HBM",
        "Neither is a logic-wafer problem. Advanced packaging capacity and HBM stacks have gated supply since 2023.",
        top=0.80,
    )
    cap = SUPPLY[SUPPLY.category == "cowos_capacity"]
    ax = axes[0]
    ax.bar(cap.year, cap.value / 1000, color=ACCENT, alpha=0.85, width=0.62)
    for _, r in cap.iterrows():
        ax.text(r.year, r.value / 1000 + 4, f"{r.value/1000:.0f}k", ha="center",
                fontsize=8.8, color=INK)
    ax.set_ylabel("TSMC CoWoS capacity (thousand wafers/month)")
    ax.set_title("Packaging capacity nearly doubles yearly", fontsize=11.0)
    ax.set_xticks(cap.year)
    ax.set_ylim(0, 250)
    note(ax, 2023.6, 232,
         "A ~2,500 mm² H100 interposer yields\nabout 16–20 good packages per wafer,\n"
         "so wafers/month converts almost\ndirectly into GPUs/month.", fontsize=8.4)

    ax = axes[1]
    hbm = SUPPLY[SUPPLY.category == "hbm_share"]
    colours = {"SK hynix": ACCENT, "Samsung": ACCENT3, "Micron": ACCENT2}
    wedges, _, autotexts = ax.pie(
        hbm.value, labels=hbm.item, autopct="%1.0f%%", startangle=60, labeldistance=1.12,
        pctdistance=0.78,
        colors=[colours[i] for i in hbm.item],
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9.6, color=INK),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title("Estimated NVIDIA HBM4 allocation, 2026", fontsize=11.0)
    ax.text(0, -1.42,
            "No supplier reports HBM revenue separately,\nso every share figure is an estimate. The only\n"
            "hard datapoint: Micron has disclosed >$1B of\nHBM4 revenue.",
            ha="center", fontsize=8.4, color=MUTED)
    ax.grid(False)

    ax = axes[2]
    price = SUPPLY[SUPPLY.category == "hbm_price"]
    labels = ["HBM3\n8-Hi", "HBM3E\n8-Hi", "HBM4\n12-Hi 36GB"]
    ax.bar(labels, price.value, color=[ACCENT4, ACCENT2, WARN], alpha=0.85, width=0.6)
    for i, v in enumerate(price.value):
        ax.text(i, v + 14, f"${v:,.0f}", ha="center", fontsize=9.4, color=INK,
                fontweight="bold")
    ax.set_ylabel("estimated price per stack (US$)")
    ax.set_ylim(0, 700)
    ax.set_title("HBM price per stack: +55-70% for HBM4", fontsize=11.0)
    note(ax, -0.45, 660,
         "An 8-stack Blackwell carries ~$2,900 of HBM\nagainst ~$850 of logic silicon. This is why the\n"
         "2026 rental-price reversal was blamed on\nmemory, not on GPUs.", fontsize=8.4)

    save(
        fig,
        "fig17_supply.png",
        "Sources: TrendForce CoWoS capacity reporting; supplier earnings disclosures; JPMorgan CoWoS wafer economics. All figures analyst "
        "estimates unless noted.",
    )


# --------------------------------------------------------------------------
# 18. Training compute of real models
# --------------------------------------------------------------------------
def fig18_training_compute():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 6.8),
                                   gridspec_kw={"width_ratios": [1.25, 1.0]})
    titleblock(
        fig,
        "What the hardware is for: training compute of real models, and the 6ND rule that predicts it",
        "Frontier training compute has grown about 5× per year. Post-2024 figures are reconstructions — labs stopped publishing.",
        top=0.86,
    )
    d = RUNS.dropna(subset=["training_flops"]).copy()
    d["flops"] = d.training_flops.astype(float)
    colour = {"confirmed": ACCENT, "estimate": MUTED}
    for conf, grp in d.groupby("confidence"):
        ax1.scatter(grp.year, grp.flops, s=110, color=colour[conf], alpha=0.8,
                    label=f"{conf} figure", zorder=3, edgecolor="white")
    for _, r in d.iterrows():
        ax1.annotate(r.model, (r.year, r.flops), textcoords="offset points",
                     xytext=(8, 5), fontsize=8.2, color=INK)
    years = np.linspace(2019.6, 2025.6, 50)
    ax1.plot(years, 3.14e23 * 5.0 ** (years - 2020), color=WARN, ls="--", lw=1.6,
             label="5× per year (Epoch AI trend)")
    ax1.set_yscale("log")
    ax1.set_xlabel("year")
    ax1.set_ylabel("training compute (FLOP)")
    ax1.set_xlim(2019.5, 2026.4)
    ax1.legend(loc="upper left")
    ax1.set_title("Training compute per model", fontsize=11.5)

    # 6ND validation panel
    v = RUNS.dropna(subset=["params_b", "tokens_t", "training_flops"]).copy()
    v["predicted"] = 6 * v.params_b * 1e9 * v.tokens_t * 1e12
    v.loc[v.model == "DeepSeek-V3", "predicted"] = 6 * 37e9 * 14.8e12
    v["actual"] = v.training_flops.astype(float)
    ax2.scatter(v.predicted, v.actual, s=110, color=ACCENT3, alpha=0.85, zorder=3,
                edgecolor="white")
    for _, r in v.iterrows():
        ax2.annotate(r.model, (r.predicted, r.actual), textcoords="offset points",
                     xytext=(8, -12), fontsize=8.2, color=INK)
    lim = [2e23, 6e25]
    ax2.plot(lim, lim, color=MUTED, ls="--", lw=1.2, label="perfect agreement")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlim(*lim)
    ax2.set_ylim(*lim)
    ax2.set_xlabel("predicted by 6ND  (6 × params × tokens)")
    ax2.set_ylabel("reported training compute")
    ax2.set_title("The 6ND rule, checked against\npublished numbers", fontsize=11.5)
    ax2.legend(loc="upper left")
    note(ax2, 2.6e23, 3.2e25,
         "Llama 3.1 405B: 6 × 405e9 × 15.6e12\n= 3.79e25 vs Meta's stated 3.8e25.\n\n"
         "For MoE, N must be the activated\nparameter count: DeepSeek-V3 uses\n37B of 671B.",
         fontsize=8.6)
    save(
        fig,
        "fig18_training_compute.png",
        "Sources: Kaplan et al. 2020; Hoffmann et al. 2022; Llama 2/3 papers; DeepSeek-V3 technical report; PaLM (JMLR 24:240); Epoch AI.",
    )


# --------------------------------------------------------------------------
# 19. MLPerf scaling
# --------------------------------------------------------------------------
def fig19_mlperf():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 6.8))
    titleblock(
        fig,
        "MLPerf Training: the only audited cross-vendor numbers, and what they hide",
        "Left: time-to-train vs cluster size. Right: scaling efficiency, which is where the interesting engineering lives.",
        top=0.86,
    )

    series = [
        ("Llama 3.1 405B · GB200 NVL72 (v6.0)", "Llama 3.1 405B", "GB200 NVL72", "v6.0", ACCENT2),
        ("Llama 3.1 405B · GB300 NVL72 (v6.0)", "Llama 3.1 405B", "GB300 NVL72", "v6.0", ACCENT3),
        ("DeepSeek-V3 671B · GB300 NVL72 (v6.0)", "DeepSeek-V3 671B", "GB300 NVL72", "v6.0", ACCENT4),
        ("GPT-3 175B · H100 (v4.0)", "GPT-3 175B", "H100 (NVIDIA Eos)", "v4.0", GPU_C),
        ("GPT-3 175B · TPU v5p (v4.1)", "GPT-3 175B", "TPU v5p", "v4.1", TPU_C),
    ]
    for label, bench, plat, rnd, colour in series:
        d = MLPERF[(MLPERF.benchmark == bench) & (MLPERF.platform == plat)]
        d = d.dropna(subset=["chips"]).sort_values("chips")
        if len(d) == 0:
            continue
        ax1.plot(d.chips, d.minutes, "-o", color=colour, lw=1.9, ms=6, label=label)
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("accelerators in the submission")
    ax1.set_ylabel("time to train (minutes)")
    ax1.set_title("Time-to-train scales, but sublinearly", fontsize=11.5)
    ax1.legend(loc="upper right", fontsize=8.6)
    ax1.annotate("11,616 H100s trained GPT-3 3.4× faster than\n6,144 TPU v5p — at ~1.9× the chip count",
                 (6144, 11.77), textcoords="offset points", xytext=(-58, -74),
                 fontsize=8.4, color=TPU_C, ha="left",
                 arrowprops=dict(arrowstyle="-", color=TPU_C, lw=0.8))

    ds = MLPERF[(MLPERF.benchmark == "DeepSeek-V3 671B")].sort_values("chips")
    base_t, base_n = ds.iloc[0].minutes, ds.iloc[0].chips
    eff = base_t / ds.minutes / (ds.chips / base_n) * 100
    ax2.plot(ds.chips, eff, "-o", color=ACCENT4, lw=2.0, ms=8,
             label="DeepSeek-V3 671B MoE on GB300 NVL72 (CoreWeave)")
    for n, e, t in zip(ds.chips, eff, ds.minutes):
        ax2.annotate(f"{int(n):,} GPUs\n{t:.2f} min\n{e:.0f}%", (n, e),
                     textcoords="offset points", xytext=(0, -34), fontsize=8.2,
                     ha="center", color=INK)
    la = MLPERF[(MLPERF.benchmark == "Llama 3.1 405B") & (MLPERF.platform == "GB200 NVL72")
                & (MLPERF["round"] == "v6.0")].sort_values("chips")
    eff2 = la.iloc[0].minutes / la.minutes / (la.chips / la.iloc[0].chips) * 100
    ax2.plot(la.chips, eff2, "-s", color=ACCENT, lw=2.0, ms=7,
             label="Llama 3.1 405B dense on GB200 NVL72 (Azure)")
    ax2.axhline(100, color=MUTED, ls="--", lw=1.0)
    ax2.text(2100, 101.5, "perfect weak scaling", fontsize=8.6, color=MUTED)
    ax2.set_xscale("log")
    ax2.set_xlabel("accelerators")
    ax2.set_ylabel("scaling efficiency vs the smallest submission (%)")
    ax2.set_ylim(50, 112)
    ax2.set_title("MoE scaling degrades faster than dense", fontsize=11.5)
    ax2.legend(loc="lower left", fontsize=8.8)
    note(ax2, 2100, 66,
         "The MoE curve falls off because expert-parallel all-to-all\n"
         "starts crossing Ethernet hops once the job outgrows a\n"
         "handful of NVL72 racks. Dense 405B holds up better\n"
         "because tensor parallelism stays inside the rack.",
         fontsize=8.6)
    save(
        fig,
        "fig19_mlperf.png",
        "Sources: MLCommons MLPerf Training v4.0/v4.1/v5.0/v5.1/v6.0 results; NVIDIA, CoreWeave, Azure, Lambda and AMD submission write-ups. "
        "Efficiency percentages are computed from the published times.",
    )


# --------------------------------------------------------------------------
# 20. Reliability at scale
# --------------------------------------------------------------------------
def fig20_reliability():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.4))
    titleblock(
        fig,
        "Reliability is a first-class hardware property: 419 unexpected interruptions in 54 days",
        "Meta's published failure log for Llama 3.1 405B on 16,384 H100s is the best public dataset on what breaks at scale.",
        top=0.85,
    )

    ax = axes[0]
    grp = FAILURES.groupby("category")["count"].sum().sort_values(ascending=True)
    cols = {"GPU": WARN, "Host": ACCENT2, "Network": ACCENT, "Dependency": ACCENT4,
            "Unknown": MUTED}
    ax.barh(grp.index, grp.values, color=[cols[i] for i in grp.index], alpha=0.85)
    total = grp.sum()
    for y, v in enumerate(grp.values):
        ax.text(v + 4, y, f"{v}  ({v/total*100:.0f}%)", va="center", fontsize=8.8,
                color=INK)
    ax.set_xlabel("unexpected interruptions in 54 days")
    ax.set_xlim(0, 330)
    ax.set_title("GPUs cause 58.7% of stoppages", fontsize=11.0)
    ax.grid(axis="y", visible=False)
    note(ax, 6, 0.15,
         "Includes 6 silent data corruptions —\nthe worst kind, because the job keeps\n"
         "running and poisons the gradients.", fontsize=8.4)

    ax = axes[1]
    n = np.array([1024, 4096, 8192, 16384, 32768, 65536, 100000, 250000, 1000000])
    per_gpu_days = 16384 * 54 / 419
    mtbf_hours = per_gpu_days * 24 / n
    ax.plot(n, mtbf_hours, "-o", color=WARN, lw=2.0, ms=6)
    ax.scatter([16384], [per_gpu_days * 24 / 16384], s=180, facecolor="none",
               edgecolor=ACCENT, linewidth=2.2, zorder=4)
    ax.annotate("Llama 3.1 405B\nmeasured: 3.1 h", (16384, per_gpu_days * 24 / 16384),
                textcoords="offset points", xytext=(-96, 26), fontsize=8.6, color=ACCENT,
                arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.8))
    ax.annotate("100k GPUs → an interruption\nroughly every 30 minutes",
                (100000, per_gpu_days * 24 / 100000), textcoords="offset points",
                xytext=(-142, -46), fontsize=8.6, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("GPUs in one synchronous job")
    ax.set_ylabel("mean time between interruptions (hours)")
    ax.set_title("Job MTBF falls linearly with scale", fontsize=11.0)

    ax = axes[2]
    M = per_gpu_days * 24 * 3600 / 100000  # seconds, 100k-GPU job
    delta = np.linspace(1, 120, 300)
    waste = np.sqrt(2 * delta / M) * 100
    ax.plot(delta, waste, color=ACCENT3, lw=2.2)
    for d_, lbl in [(60, "synchronous write\nto storage: 60 s"),
                    (20, "tuned async: 20 s"),
                    (5, "peer / in-memory\nreplication: 5 s")]:
        w = np.sqrt(2 * d_ / M) * 100
        ax.plot([d_], [w], "o", color=WARN, ms=7)
        ax.annotate(f"{lbl}\n→ {w:.0f}% of the cluster wasted", (d_, w),
                    textcoords="offset points", xytext=(16, 6), fontsize=8.4, color=INK)
    ax.set_xlabel("checkpoint cost δ (seconds)")
    ax.set_ylabel("fraction of cluster time wasted (%)")
    ax.set_title("Young/Daly optimum on a 100k-GPU job\n√(2δ/M)", fontsize=11.0)
    ax.set_xlim(0, 125)
    ax.set_ylim(0, 30)

    save(
        fig,
        "fig20_reliability.png",
        "Failure counts from Llama 3 Herd of Models, Table 5 (arXiv:2407.21783). MTBF and checkpoint-waste curves are derived from those counts "
        "using the Young/Daly formula; they assume Meta's per-GPU failure rate holds at other scales.",
    )


# --------------------------------------------------------------------------
# 21. Memory math: why models must be sharded
# --------------------------------------------------------------------------
def fig21_memory_math():
    fig = plt.figure(figsize=(15.2, 6.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 2.4], hspace=0.55, wspace=0.20)
    titleblock(
        fig,
        "Why one accelerator is never enough: 16 bytes per parameter, before any activations",
        "Mixed-precision Adam keeps BF16 weights and gradients plus FP32 master weights and two FP32 moments.",
        top=0.86,
    )

    axc = fig.add_subplot(gs[0, 0])
    blank_axes(axc, (0, 16), (0, 1))
    axc.set_title("Bytes of state per parameter", fontsize=11.0)
    comps = [("BF16\nweights", 2, ACCENT), ("BF16\ngrads", 2, ACCENT3),
             ("FP32 master\nweights", 4, ACCENT2), ("Adam\nmoment m", 4, ACCENT4),
             ("Adam\nvariance v", 4, MUTED)]
    x = 0.0
    for label, bpp, colour in comps:
        box(axc, x, 0.30, bpp, 0.50, f"{label}\n{bpp} B", face=colour, edge="white",
            color="white", fontsize=7.8, weight="bold", radius=0.004, alpha=0.9)
        x += bpp
    axc.text(8, 0.12, "16 bytes per parameter in total", ha="center", fontsize=9.4,
             color=INK, fontweight="bold")

    ax1 = fig.add_subplot(gs[1, 0])
    models = [("Llama 3 8B", 8), ("Llama 2 70B", 70), ("Llama 3.1 405B", 405),
              ("DeepSeek-V3 671B", 671), ("1.8T MoE (GPT-4 scale)", 1800)]
    names = [m[0] for m in models]
    totals = np.array([m[1] * 16 for m in models], dtype=float)
    ax1.barh(names, totals, color=ACCENT, alpha=0.85, height=0.6)
    for y, t in enumerate(totals):
        ax1.text(t * 1.12, y, f"{t:,.0f} GB  →  {np.ceil(t/80):.0f}× H100  /  "
                              f"{np.ceil(t/192):.0f}× MI300X or TPU v7", va="center",
                 fontsize=8.6, color=INK)
    ax1.set_xscale("log")
    ax1.set_xlim(80, 4_000_000)
    ax1.set_xlabel("optimizer + model state (GB, log scale)")
    ax1.set_title("How many accelerators the state alone requires", fontsize=11.0)
    ax1.grid(axis="y", visible=False)

    ax2 = fig.add_subplot(gs[:, 1])

    kv = [("DeepSeek-V3 (MLA)", 70.272), ("Qwen-2.5 72B (GQA)", 327.680),
          ("Llama 3.1 405B (GQA)", 516.096)]
    ctx = np.array([4096, 32768, 131072])
    width = 0.26
    x = np.arange(len(ctx))
    for i, (name, kb) in enumerate(kv):
        gb = kb * ctx / 1024 / 1024
        ax2.bar(x + (i - 1) * width, gb, width=width, alpha=0.85,
                color=[ACCENT, ACCENT2, WARN][i], label=name)
        for xi, g in zip(x + (i - 1) * width, gb):
            ax2.text(xi, g + 1.2, f"{g:.0f}", ha="center", fontsize=8.2, color=INK)
    ax2.axhline(80, color=GPU_C, ls="--", lw=1.4)
    ax2.text(-0.42, 82, "one H100 = 80 GB", fontsize=8.8, color=GPU_C)
    ax2.axhline(192, color=VENDOR["Google"], ls="--", lw=1.4)
    ax2.text(-0.42, 194, "one TPU v7 / MI300X = 192 GB", fontsize=8.8,
             color=VENDOR["Google"])
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{c//1024}k context" for c in ctx])
    ax2.set_ylabel("KV cache for a single sequence (GB)")
    ax2.set_ylim(0, 230)
    ax2.legend(loc="upper left", fontsize=8.8)
    ax2.set_title("KV cache for one sequence: attention design is memory engineering",
                  fontsize=11.5)

    save(
        fig,
        "fig21_memory_math.png",
        "Sources: ZeRO (arXiv:1910.02054) for the 16-bytes-per-parameter accounting; DeepSeek-V3 hardware paper, Table 1, for per-token KV "
        "cache sizes (verified here as 2 × layers × kv_heads × head_dim × bytes).",
    )


# --------------------------------------------------------------------------
# 22. Estimated 2026 unit volumes
# --------------------------------------------------------------------------
def fig22_shipments():
    fig, ax = plt.subplots(figsize=(13.2, 6.6))
    titleblock(
        fig,
        "Estimated 2026 accelerator volumes: custom silicon is no longer a rounding error",
        "All figures are analyst estimates and disagree between sources by 1.5–2×. Treat as orders of magnitude, not counts.",
        top=0.87,
    )
    d = SUPPLY[(SUPPLY.category == "shipments") & (SUPPLY.year == 2026)].copy()
    vendor_of = {
        "Google TPU v6/v7": "Google", "AWS Trainium2/3": "AWS", "AMD Instinct": "AMD",
        "Intel Gaudi 3": "Intel", "Microsoft Maia": "Microsoft", "Meta MTIA": "Meta",
        "Huawei Ascend 910C": "Huawei",
    }
    d["vendor"] = d.item.map(vendor_of)
    d = d.sort_values("value")
    ax.barh(d.item, d.value / 1e6, color=[vcolor(v) for v in d.vendor], alpha=0.85)
    for y, v in enumerate(d.value / 1e6):
        ax.text(v + 0.03, y, f"{v:.2f}M units", va="center", fontsize=9.0, color=INK)
    ax.set_xlabel("estimated units shipped in 2026 (millions)")
    ax.set_xlim(0, 3.6)
    ax.grid(axis="y", visible=False)
    note(ax, 1.15, 1.3,
         "For scale: Broadcom's confirmed FY2026 guidance is $56B of AI semiconductor revenue (about 180% growth),\n"
         "most of it TPU and custom-ASIC content, against NVIDIA's confirmed $75.2B of data-center revenue in a\n"
         "single quarter. The custom-ASIC business is real, but NVIDIA still captures most of the dollars because\n"
         "it sells the CPU, the switch, the NIC and the rack alongside the accelerator.",
         fontsize=8.8)
    save(
        fig,
        "fig22_shipments.png",
        "Sources: SemiAnalysis, Fubon, DigiTimes, Bank of America and Reuters estimates as compiled in data/supply_chain.csv. NVIDIA and "
        "Broadcom revenue figures are from company filings.",
    )


# --------------------------------------------------------------------------
# 23. Normalised comparison against H100
# --------------------------------------------------------------------------
def fig23_normalised():
    fig, ax = plt.subplots(figsize=(14.4, 7.4))
    titleblock(
        fig,
        "Everything normalised to one H100 SXM",
        "Ratios of published dense specs. A chip can win on memory and lose on compute — which is exactly the AMD and TPU story.",
        top=0.87,
    )
    base = spec("H100")
    picks = ["H200", "B200 NVL72", "B300 NVL72", "Rubin R100", "MI300X", "MI355X",
             "MI455X", "Gaudi 3", "TPU v5p", "TPU v7", "Trainium2", "Trainium3",
             "Ascend 910C", "Maia 200"]
    metrics = [
        ("fp16bf16_dense_tflops", "BF16 compute"),
        ("fp8_dense_tflops", "FP8 compute"),
        ("memory_gb", "memory capacity"),
        ("mem_bw_tbs", "memory bandwidth"),
        ("scaleup_bw_gbs", "scale-up bandwidth"),
        ("scaleup_domain_chips", "scale-up domain"),
    ]
    x = np.arange(len(picks))
    width = 0.13
    for i, (col, label) in enumerate(metrics):
        vals = []
        for name in picks:
            s = spec(name)
            v = s[col]
            b = base[col]
            vals.append(np.nan if pd.isna(v) or pd.isna(b) else v / b)
        ax.bar(x + (i - 2.5) * width, vals, width=width,
               color=[ACCENT, ACCENT3, ACCENT2, ACCENT4, GPU_C, WARN][i], alpha=0.88,
               label=label)
    ax.axhline(1, color=INK, lw=1.2)
    ax.text(-0.55, 1.06, "H100 = 1", fontsize=9.0, color=INK, fontweight="bold")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(picks, rotation=22, ha="right", fontsize=9.2)
    ax.set_ylabel("ratio to H100 SXM (log scale)")
    ax.set_ylim(0.05, 2000)
    ax.legend(ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.09), fontsize=9.0)
    note(ax, -0.5, 1400,
         "Missing bars are unpublished values, not zeros: NVIDIA does not disclose Rubin's TDP, Google discloses no TPU FP16 rate for 8t/8i,\n"
         "and Huawei publishes no FP8 path at all.", fontsize=8.6)
    save(fig, "fig23_normalised.png")


# --------------------------------------------------------------------------
# 24. TPU generations
# --------------------------------------------------------------------------
def fig24_tpu_generations():
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 6.0))
    titleblock(
        fig,
        "Ten years of TPU: compute, memory and pod size",
        "Google's lever has been the pod, not just the chip — v7 puts 9,216 chips and 1.77 PB of HBM into one addressable machine.",
        top=0.85,
    )
    order = ["TPU v2", "TPU v3", "TPU v4", "TPU v5e", "TPU v5p", "TPU v6e", "TPU v7"]
    d = ACC[ACC.short_name.isin(order)].copy()
    d["short_name"] = pd.Categorical(d.short_name, categories=order, ordered=True)
    d = d.sort_values("short_name")

    ax = axes[0]
    ax.bar(d.short_name.astype(str), d.fp16bf16_dense_tflops, color=TPU_C, alpha=0.85,
           width=0.62)
    for i, v in enumerate(d.fp16bf16_dense_tflops):
        ax.text(i, v * 1.06, f"{v:,.0f}", ha="center", fontsize=8.8, color=INK)
    ax.set_yscale("log")
    ax.set_ylabel("dense BF16 TFLOP/s per chip")
    ax.set_title("50× per-chip compute, v2 → v7", fontsize=11.0)
    ax.tick_params(axis="x", rotation=28, labelsize=8.8)
    ax.set_ylim(20, 6000)

    ax = axes[1]
    ax.bar(d.short_name.astype(str), d.memory_gb, color=ACCENT2, alpha=0.85, width=0.62,
           label="HBM per chip (GB)")
    ax2 = ax.twinx()
    ax2.plot(d.short_name.astype(str), d.mem_bw_tbs, "-o", color=WARN, lw=2.0, ms=7,
             label="bandwidth (TB/s)")
    ax2.set_ylabel("memory bandwidth (TB/s)", color=WARN)
    ax2.tick_params(axis="y", colors=WARN)
    ax2.grid(False)
    ax.set_ylabel("HBM capacity per chip (GB)")
    ax.set_title("Memory: the v5e/v6e dip is deliberate\n(cost-optimised inference parts)",
                 fontsize=11.0)
    ax.tick_params(axis="x", rotation=28, labelsize=8.8)
    ax.legend(loc="upper left", fontsize=8.6)
    ax2.legend(loc="lower right", fontsize=8.6)

    ax = axes[2]
    ax.bar(d.short_name.astype(str), d.scaleup_domain_chips, color=ACCENT4, alpha=0.85,
           width=0.62)
    for i, v in enumerate(d.scaleup_domain_chips):
        ax.text(i, v * 1.08, f"{int(v):,}", ha="center", fontsize=8.8, color=INK)
    ax.set_yscale("log")
    ax.set_ylabel("chips in the largest pod / slice")
    ax.set_title("Pod size, and the OCS era from v4 on", fontsize=11.0)
    ax.tick_params(axis="x", rotation=28, labelsize=8.8)
    ax.set_ylim(100, 40000)
    ax.axvspan(1.5, 6.5, color=TPU_C, alpha=0.06)
    ax.text(4.0, 22000, "optically reconfigurable\n3D torus", ha="center", fontsize=8.8,
            color=TPU_C)

    save(
        fig,
        "fig24_tpu_generations.png",
        "Sources: Jouppi et al. ISCA 2021 and ISCA 2023; Google Cloud TPU documentation for v5e, v5p, v6e and TPU7x; Ironwood Hot Chips 2025.",
    )


FIGURES = [
    fig09_compute_timeline,
    fig10_memory_scatter,
    fig11_perf_per_watt,
    fig12_scaleup_evolution,
    fig13_rack_systems,
    fig14_cloud_prices,
    fig15_price_per_flop,
    fig16_bom,
    fig17_supply,
    fig18_training_compute,
    fig19_mlperf,
    fig20_reliability,
    fig21_memory_math,
    fig22_shipments,
    fig23_normalised,
    fig24_tpu_generations,
]


def main():
    apply_style()
    print("Data figures:")
    for fn in FIGURES:
        fn()


if __name__ == "__main__":
    main()
