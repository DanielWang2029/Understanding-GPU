"""Shared plotting style, vendor palette and small drawing helpers."""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIGDIR = ROOT / "report" / "figures"

INK = "#16202a"
MUTED = "#5b6b7a"
GRID = "#d7dee5"
PANEL = "#f4f7f9"
CANVAS = "#ffffff"

VENDOR = {
    "NVIDIA": "#76b900",
    "AMD": "#e2231a",
    "Google": "#1a73e8",
    "AWS": "#ff9900",
    "Intel": "#0068b5",
    "Huawei": "#cf0a2c",
    "Meta": "#0866ff",
    "Microsoft": "#7a4fd6",
    "Cerebras": "#f05a28",
    "Groq": "#e2508a",
    "SambaNova": "#00a3a1",
    "Tenstorrent": "#7c68ee",
}

# Semantic colours reused across figures.
ACCENT = "#1a73e8"
ACCENT2 = "#e8710a"
ACCENT3 = "#12805c"
ACCENT4 = "#8430ce"
WARN = "#c5221f"

GPU_C = "#76b900"
TPU_C = "#1a73e8"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": CANVAS,
            "axes.facecolor": CANVAS,
            "savefig.facecolor": CANVAS,
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlepad": 12,
            "axes.labelsize": 11,
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 0.9,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.frameon": False,
            "legend.fontsize": 9.5,
            "figure.dpi": 130,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.28,
        }
    )


def save(fig, name: str, caption: str | None = None) -> pathlib.Path:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    if caption:
        fig.text(
            0.5,
            -0.012,
            caption,
            ha="center",
            va="top",
            fontsize=8.6,
            color=MUTED,
            wrap=True,
        )
    path = FIGDIR / name
    fig.savefig(path)
    plt.close(fig)
    print(f"  wrote {path.relative_to(ROOT)}")
    return path


def titleblock(fig, title: str, subtitle: str = "", top: float = 0.87) -> None:
    """Figure title + subtitle with guaranteed clearance above the axes."""
    fig.subplots_adjust(top=top)
    fig.suptitle(title, fontsize=15, fontweight="bold", color=INK, y=0.995)
    if subtitle:
        fig.text(0.5, top + (0.995 - top) * 0.36, subtitle, ha="center", fontsize=10.2,
                 color=MUTED)


def box(
    ax,
    x,
    y,
    w,
    h,
    label,
    face=PANEL,
    edge=MUTED,
    fontsize=9,
    weight="normal",
    color=INK,
    radius=0.02,
    lw=1.0,
    alpha=1.0,
    zorder=2,
    va="center",
    ls="-",
):
    """Rounded labelled rectangle in axes data coordinates."""
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
        alpha=alpha,
        zorder=zorder,
        linestyle=ls,
    )
    ax.add_patch(patch)
    if label:
        ax.text(
            x + w / 2,
            y + h / 2 if va == "center" else y + h - 0.02,
            label,
            ha="center",
            va=va,
            fontsize=fontsize,
            fontweight=weight,
            color=color,
            zorder=zorder + 1,
            linespacing=1.35,
        )
    return patch


def arrow(ax, xy_from, xy_to, color=MUTED, lw=1.3, style="-|>", ls="-", zorder=3, rad=0.0):
    ax.annotate(
        "",
        xy=xy_to,
        xytext=xy_from,
        zorder=zorder,
        arrowprops=dict(
            arrowstyle=style,
            color=color,
            linewidth=lw,
            linestyle=ls,
            shrinkA=0,
            shrinkB=0,
            connectionstyle=f"arc3,rad={rad}",
        ),
    )


def blank_axes(ax, xlim=(0, 1), ylim=(0, 1)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return ax


def note(ax, x, y, text, fontsize=8.6, color=MUTED, ha="left", va="top", weight="normal"):
    ax.text(
        x,
        y,
        text,
        fontsize=fontsize,
        color=color,
        ha=ha,
        va=va,
        weight=weight,
        linespacing=1.45,
    )
