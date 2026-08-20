"""Markdown tables generated from the CSVs, injected into the report.

The report sections contain placeholders of the form

    <!-- TABLE:name -->

which build_site.py replaces with the output of the matching function here.
Generating tables from data keeps the prose and the figures consistent and
removes a whole class of transcription errors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from theme import DATA

ACC = pd.read_csv(DATA / "accelerators.csv")
for _c in ("street_price_usd", "memory_gb", "mem_bw_tbs", "fp16bf16_dense_tflops",
           "fp8_dense_tflops", "fp4_dense_tflops", "fp64_tflops", "tdp_w",
           "scaleup_bw_gbs", "scaleup_domain_chips", "onchip_sram_mb", "transistors_b"):
    ACC[_c] = pd.to_numeric(ACC[_c], errors="coerce")
PRICE = pd.read_csv(DATA / "cloud_pricing.csv")
RACKS = pd.read_csv(DATA / "rack_systems.csv")
MLPERF = pd.read_csv(DATA / "mlperf_training.csv")
RUNS = pd.read_csv(DATA / "training_runs.csv")


def _fmt(v, unit="", nd=0, dash="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return dash
    if isinstance(v, str):
        return v
    if nd == 0:
        return f"{v:,.0f}{unit}"
    return f"{v:,.{nd}f}{unit}"


def _money(v):
    if pd.isna(v):
        return "—"
    return f"${v:,.0f}"


def _table(header: list[str], rows: list[list[str]], align: str | None = None) -> str:
    sep = ["---"] * len(header) if align is None else list(align)
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _spec_rows(names: list[str], price=True) -> tuple[list[str], list[list[str]]]:
    header = ["Accelerator", "Launch", "Process", "Memory", "BW (TB/s)",
              "BF16 dense", "FP8 dense", "FP4 dense", "TDP", "Scale-up", "Domain"]
    if price:
        header.append("Unit price")
    rows = []
    for n in names:
        r = ACC[ACC.short_name == n]
        if r.empty:
            continue
        r = r.iloc[0]
        if pd.isna(r.memory_gb):
            mem = "—"
        elif r.memory_gb < 1:
            mem = f"{r.memory_gb*1000:,.0f} MB {r.memory_type}"
        else:
            mem = f"{r.memory_gb:,.0f} GB {r.memory_type}"
        row = [
            f"**{r['name']}**",
            str(r.launch),
            _fmt(r.process, dash="not published"),
            mem,
            _fmt(r.mem_bw_tbs, nd=2),
            _fmt(r.fp16bf16_dense_tflops, " TF"),
            _fmt(r.fp8_dense_tflops, " TF"),
            _fmt(r.fp4_dense_tflops, " TF"),
            _fmt(r.tdp_w, " W"),
            _fmt(r.scaleup_bw_gbs, " GB/s"),
            _fmt(r.scaleup_domain_chips),
        ]
        if price:
            p = _money(r.street_price_usd)
            if p != "—":
                p += f" ({r.price_confidence})"
            elif isinstance(r.price_confidence, str):
                p = r.price_confidence
            row.append(p)
        rows.append(row)
    return header, rows


AVAILABILITY = {
    "list": "purchasable, list price published",
    "estimate": "purchasable, price by quote",
    "unknown": "purchasable, price undisclosed",
    "cloud-only": "rentable from one cloud only",
    "internal": "not for sale (first-party use)",
    "system-only": "sold as a system, price on application",
    "eol": "end of life, secondary market",
}


def table_index():
    header = ["Accelerator", "Vendor", "Launch", "Built for", "How you get it"]
    rows = []
    d = ACC.copy()
    d["vendor_order"] = d.vendor.map(
        {"NVIDIA": 0, "AMD": 1, "Intel": 2, "Google": 3, "AWS": 4, "Meta": 5,
         "Microsoft": 6, "Huawei": 7, "Cerebras": 8, "Groq": 9, "SambaNova": 10,
         "Tenstorrent": 11}
    ).fillna(99)
    d = d.sort_values(["vendor_order", "launch_year", "short_name"])
    for _, r in d.iterrows():
        avail = AVAILABILITY.get(str(r.price_confidence), "—")
        rows.append([
            f"**{r.short_name}**",
            str(r.vendor),
            str(r.launch),
            str(r.role).replace("+", " + "),
            avail,
        ])
    return _table(header, rows)


def table_nvidia_training():
    names = ["V100", "A100 40GB", "A100 80GB", "H100", "H100 PCIe", "H200", "H20",
             "GH200", "B100", "B200 HGX", "B200 NVL72", "B300 NVL72", "Rubin R100"]
    return _table(*_spec_rows(names))


def table_nvidia_inference():
    names = ["L40S", "L4", "RTX 4090", "RTX 5090"]
    return _table(*_spec_rows(names))


def table_amd():
    names = ["MI250X", "MI300X", "MI325X", "MI355X", "MI455X"]
    return _table(*_spec_rows(names))


def table_intel_huawei():
    names = ["Gaudi 2", "Gaudi 3", "Ascend 910B", "Ascend 910C"]
    return _table(*_spec_rows(names))


def table_tpu():
    names = ["TPU v2", "TPU v3", "TPU v4", "TPU v5e", "TPU v5p", "TPU v6e", "TPU v7",
             "TPU 8t", "TPU 8i"]
    header, rows = _spec_rows(names, price=False)
    return _table(header, rows)


def table_other_asics():
    names = ["Trainium1", "Trainium2", "Trainium3", "Inferentia2", "MTIA v2", "MTIA 300",
             "MTIA 400", "Maia 100", "Maia 200", "WSE-3", "Groq LPU", "Groq 3", "SN40L",
             "Blackhole p150a"]
    return _table(*_spec_rows(names))


def table_racks():
    header = ["System", "Chips", "BF16 PFLOP/s", "FP8 PFLOP/s", "FP4 PFLOP/s", "HBM",
              "HBM BW", "Scale-up BW", "Power", "Price"]
    rows = []
    for _, r in RACKS.iterrows():
        rows.append([
            f"**{r.system}**",
            _fmt(r.chips),
            _fmt(r.bf16_dense_pflops, nd=1),
            _fmt(r.fp8_dense_pflops, nd=1),
            _fmt(r.fp4_dense_pflops, nd=1),
            _fmt(r.hbm_tb, " TB", nd=1),
            _fmt(r.hbm_bw_tbs, " TB/s"),
            _fmt(r.scaleup_bw_tbs, " TB/s"),
            _fmt(r.power_kw, " kW"),
            _money(r.price_usd),
        ])
    return _table(header, rows)


def table_cloud_prices():
    header = ["Accelerator", "Cheapest observed", "Typical neocloud on-demand",
              "Hyperscaler on-demand", "Committed / reserved", "Spread"]
    order = ["H100 SXM", "H200", "B200", "B300", "GB200", "A100 80GB", "MI300X",
             "MI355X", "Trainium1", "Trainium2", "TPU v5e", "TPU v5p",
             "TPU v6e Trillium", "TPU v7 Ironwood"]
    rows = []
    for acc in order:
        d = PRICE[PRICE.accelerator == acc]
        if d.empty:
            continue
        lo = d.usd_per_chip_hour.min()
        hi = d.usd_per_chip_hour.max()
        neo = d[d.provider_type == "neocloud"]
        hyp = d[(d.provider_type == "hyperscaler") & (d.tier == "on-demand")]
        com = d[d.tier.isin(["3yr-commit", "1yr-commit", "capacity-block", "flex-start",
                             "enterprise-contract"])]
        rows.append([
            f"**{acc}**",
            f"${lo:,.2f}",
            f"${neo.usd_per_chip_hour.median():,.2f}" if not neo.empty else "—",
            f"${hyp.usd_per_chip_hour.median():,.2f}" if not hyp.empty else "—",
            f"${com.usd_per_chip_hour.min():,.2f}" if not com.empty else "—",
            f"{hi/lo:,.1f}×",
        ])
    return _table(header, rows)


def table_price_per_flop():
    rows_out = []
    for _, r in PRICE.iterrows():
        s = ACC[ACC.short_name == r.spec_key]
        if s.empty:
            continue
        s = s.iloc[0]
        if pd.isna(s.fp8_dense_tflops) or pd.isna(s.mem_bw_tbs):
            continue
        rows_out.append({
            "offer": f"{r.accelerator} · {r.provider} ({r.tier})",
            "usd_h": r.usd_per_chip_hour,
            "pflop": r.usd_per_chip_hour / (s.fp8_dense_tflops / 1000.0),
            "bw": r.usd_per_chip_hour / s.mem_bw_tbs,
        })
    d = pd.DataFrame(rows_out).sort_values("pflop").head(15)
    header = ["Offer", "$/chip-hour", "$ per dense FP8 PFLOP-hour", "$ per TB/s-hour"]
    rows = [[r.offer, f"${r.usd_h:,.2f}", f"${r.pflop:,.2f}", f"${r.bw:,.2f}"]
            for _, r in d.iterrows()]
    return _table(header, rows)


def table_mlperf_v6():
    d = MLPERF[MLPERF["round"] == "v6.0"].sort_values(["benchmark", "chips"])
    header = ["Benchmark", "Platform", "Accelerators", "Time to train"]
    rows = [[r.benchmark, r.platform, _fmt(r.chips), f"{r.minutes:.2f} min"]
            for _, r in d.iterrows()]
    return _table(header, rows)


def table_mlperf_amd():
    d = MLPERF[(MLPERF.vendor == "AMD") | ((MLPERF.chips == 8) & (MLPERF["round"].isin(["v5.0", "v5.1"])))]
    d = d.sort_values(["benchmark", "minutes"])
    header = ["Round", "Benchmark", "Platform", "Accelerators", "Time to train"]
    rows = [[r["round"], r.benchmark, r.platform, _fmt(r.chips), f"{r.minutes:.2f} min"]
            for _, r in d.iterrows()]
    return _table(header, rows)


def table_training_runs():
    d = RUNS.copy()
    header = ["Model", "Params (B)", "Active (B)", "Tokens (T)", "Training FLOP",
              "Hardware", "Chips", "Chip-hours (M)", "MFU", "Confidence"]
    rows = []
    for _, r in d.iterrows():
        rows.append([
            f"**{r.model}**",
            _fmt(r.params_b),
            _fmt(r.active_params_b),
            _fmt(r.tokens_t, nd=2),
            f"{r.training_flops:.2e}".replace("e+", "e") if not pd.isna(r.training_flops) else "—",
            str(r.hardware),
            _fmt(r.chip_count),
            _fmt(r.chip_hours_m, nd=2),
            f"{r.mfu:.0%}" if not pd.isna(r.mfu) else "—",
            str(r.confidence),
        ])
    return _table(header, rows)


TABLES = {
    "index": table_index,
    "nvidia_training": table_nvidia_training,
    "nvidia_inference": table_nvidia_inference,
    "amd": table_amd,
    "intel_huawei": table_intel_huawei,
    "tpu": table_tpu,
    "other_asics": table_other_asics,
    "racks": table_racks,
    "cloud_prices": table_cloud_prices,
    "price_per_flop": table_price_per_flop,
    "mlperf_v6": table_mlperf_v6,
    "mlperf_amd": table_mlperf_amd,
    "training_runs": table_training_runs,
}


def render(name: str) -> str:
    if name not in TABLES:
        raise KeyError(f"unknown table '{name}' (have: {sorted(TABLES)})")
    return TABLES[name]()


if __name__ == "__main__":
    for key in TABLES:
        print(f"\n### {key}\n")
        print(render(key))
