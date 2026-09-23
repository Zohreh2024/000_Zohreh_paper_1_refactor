"""
Run 2 - the figures.

    fig_01  where the sites are, before and after - the reason for the change
    fig_02  the metrics, with both nulls and the gap
    fig_03  the stability check: how far the gap moves when 8 of 778 sites go

Axes are linear throughout.

Reads   outputs/run02_headline.csv, coverage.csv, reference_table_min004.csv
        ../../outputs/reference_table.csv
Writes  plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_plots.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from matplotlib.patches import Patch                           # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"
SOUTH = -37.0
MATURE = ["verified mature", "likely mature"]

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_005 = "#6b6a66"
C_NEW = "#e34948"
C_004 = "#2a78d6"
C_NULL = "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="both"):
    ax.tick_params(labelsize=9, colors=INK_2, length=2.5, width=0.6)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID_C, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.6)
        ax.spines[sp].set_color("#c9c8c4")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    return ax


def find_parent(start):
    for d in [start] + list(start.parents):
        if (d / "Step_01_build_reference_table.py").exists():
            return d
    raise SystemExit("parent not found")


def fig_coverage():
    """Where the sites are. This is the whole argument for the change."""
    p05 = pd.read_csv(find_parent(HERE) / "outputs" / "reference_table.csv",
                      low_memory=False)
    p04 = pd.read_csv(OUT_DIR / "reference_table_min004.csv", low_memory=False)
    p05 = p05[p05["maturity"].isin(MATURE)]
    p04 = p04[p04["maturity"].isin(MATURE)]
    added = p04[~p04["site"].isin(set(p05["site"]))]

    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.4),
                             gridspec_kw={"width_ratios": (1.5, 1)})
    ax = tidy(axes[0])
    ax.scatter(p05["longitude"], p05["latitude"], s=13, color=C_005,
               alpha=0.65, label="already in at 0.05 ha (%d)" % len(p05),
               zorder=3)
    ax.scatter(added["longitude"], added["latitude"], s=22, color=C_NEW,
               alpha=0.9, edgecolor=SURFACE, linewidth=0.4,
               label="admitted by 0.04 ha (%d)" % len(added), zorder=5)
    ax.axhline(SOUTH, color=INK, lw=1.2, ls="--", zorder=4)
    ax.text(114, SOUTH, " 37°S", va="bottom", fontsize=9, color=INK_2)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("a) Where the new sites are", loc="left")
    ax.legend(fontsize=8.6, frameon=False, loc="lower left")

    ax = tidy(axes[1], grid_axis="x")
    bins = np.arange(-44, -9, 2.0)
    ax.hist(p05["latitude"], bins=bins, orientation="horizontal",
            color=C_005, alpha=0.75, label="0.05 ha", zorder=3)
    ax.hist(p04["latitude"], bins=bins, orientation="horizontal",
            histtype="step", lw=2.2, color=C_004, label="0.04 ha", zorder=4)
    ax.axhline(SOUTH, color=INK, lw=1.2, ls="--", zorder=5)
    ax.set_xlabel("sites")
    ax.set_ylabel("latitude")
    ax.set_title("b) Latitude distribution", loc="left")
    ax.legend(fontsize=8.6, frameon=False)
    ax.text(0.97, 0.03, "south of 37°S: %d → %d"
            % (int((p05["latitude"] < SOUTH).sum()),
               int((p04["latitude"] < SOUTH).sum())),
            transform=ax.transAxes, ha="right", fontsize=9.5, color=INK)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_01_coverage.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_metrics(h):
    d = h.set_index("config")
    order = [c for c in ["floor_005", "floor_004", "floor_004_no_unsw",
                         "floor_004_south"] if c in d.index]
    x = np.arange(len(order))
    w = 0.38

    fig, axes = plt.subplots(2, 1, figsize=(10.0, 7.6), sharex=True)
    ax = tidy(axes[0], grid_axis="y")
    ax.bar(x - w / 2, d.loc[order, "rho"], w, color=C_004,
           label="the runs (median of eight)", zorder=3)
    ax.bar(x + w / 2, d.loc[order, "null_nvis_rho"], w, color=C_NULL,
           label="NVIS-constrained null", zorder=3)
    for xi, a, b in zip(x, d.loc[order, "rho"], d.loc[order, "null_nvis_rho"]):
        ax.annotate("%.3f" % a, (xi - w / 2, a), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8.4,
                    color=INK_2)
        ax.annotate("%.3f" % b, (xi + w / 2, b), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8.4,
                    color=INK_2)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("a) The runs against their own null", loc="left")
    ax.legend(fontsize=8.6, frameon=False)

    ax = tidy(axes[1], grid_axis="y")
    gaps = d.loc[order, "gap_rho_nvis"]
    ax.bar(x, gaps, 0.5, color=[C_005 if c == "floor_005" else C_004
                                for c in order], zorder=3)
    ax.axhline(float(d.loc["floor_005", "gap_rho_nvis"]), color=C_005, lw=1.2,
               ls="--", zorder=4)
    ax.axhline(0, color="#333333", lw=1.0, zorder=5)
    for xi, v, n in zip(x, gaps, d.loc[order, "sites"]):
        ax.annotate("%+.3f\nn = %d" % (v, n), (xi, v),
                    xytext=(0, 5 if v >= 0 else -22),
                    textcoords="offset points", ha="center", fontsize=8.4,
                    color=INK_2)
    ax.set_ylabel("rank correlation above the null", fontsize=9)
    ax.set_title("b) The gap - what survives the null", loc="left")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([c.replace("floor_", "").replace("_", "\n")
                              for c in order], fontsize=8.6)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_metrics.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_stability(h):
    """How far the gap moves when 8 sites of 778 are removed.

    The answer decides whether the change in the gap is a result or noise. If
    dropping one per cent of the sample moves the statistic as far as the
    change being tested does, the change cannot be quoted as an effect.
    """
    d = h.set_index("config")
    if not {"floor_005", "floor_004", "floor_004_no_unsw"} <= set(d.index):
        return None
    base = float(d.loc["floor_005", "gap_rho_nvis"])
    full = float(d.loc["floor_004", "gap_rho_nvis"])
    less = float(d.loc["floor_004_no_unsw", "gap_rho_nvis"])
    effect = full - base
    noise = abs(full - less)

    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    tidy(ax, grid_axis="x")
    ax.barh([1], [effect], 0.5, color=C_004, zorder=3,
            label="the effect being tested: 0.05 ha to 0.04 ha")
    ax.barh([0], [noise], 0.5, color=C_NEW, zorder=3,
            label="removing 8 of 778 sites (University of NSW)")
    for yi, v in ((1, effect), (0, noise)):
        ax.annotate("%+.3f" % v, (v, yi), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9.5,
                    color=INK_2)
    ax.axvline(0, color="#333333", lw=1.0, zorder=5)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["dropping 1% of the sample",
                        "the change itself"], fontsize=9)
    ax.set_xlabel("movement in the gap to the NVIS-constrained null")
    ax.set_title("Is the change larger than the noise?", loc="left")
    ax.legend(fontsize=8.5, frameon=False, loc="lower right")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi * 1.25)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_stability.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(OUT_DIR / "run02_headline.csv")
    for p in (fig_coverage(), fig_metrics(h), fig_stability(h)):
        print("  -> %s" % (p.name if p else "skipped"))
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
