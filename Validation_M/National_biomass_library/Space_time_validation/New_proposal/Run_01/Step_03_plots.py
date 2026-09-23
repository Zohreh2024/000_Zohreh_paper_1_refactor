"""
Run 1 - the figures.

    fig_01  why Run 1 exists: the two maturity classes side by side, on the
            quantities that separate them
    fig_02  Run 1 against Run 0, per scenario-window, with both nulls drawn in
    fig_03  the gap to each null - what the gain is worth once the null moves
            with the sample

Axes are linear throughout.

Reads   outputs/gate_by_maturity.csv, run01_vs_run00.csv, both_nulls.csv
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
from matplotlib.ticker import FuncFormatter                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"

SURFACE = "#fcfcfb"
INK, INK_2, GRID_C = "#0b0b0b", "#52514e", "#e4e3df"
C_RUN0 = "#6b6a66"
C_RUN1 = "#2a78d6"
C_LIKELY = "#eb6834"
C_VERIF = "#2a78d6"
C_NULL_N = "#eda100"
C_NULL_U = "#1baf7a"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
FUTURE = ["%s_%s" % (a, w) for w in WINDOWS for a in SSPS]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="y"):
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


def fig_gate(gate):
    """The two classes, on the four quantities that separate them.

    Each panel is on its own scale because the quantities are unrelated; the
    point is the pattern across panels, not the heights within one.
    """
    d = gate[gate["maturity"].isin(["verified mature", "likely mature"])]
    d = d.set_index("maturity").reindex(["verified mature", "likely mature"])
    panels = [
        ("median_ratio", "median M' / observed AGB", "the result"),
        ("spearman_rho", "Spearman rank correlation", "the result"),
        ("agb_per_basal_area",
         "observed AGB per m$^2$/ha of live basal area", "the cause"),
        ("plot_area_ha", "median plot area (ha)", "the cause"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(14.2, 4.4))
    for ax, (col, lab, kind) in zip(axes, panels):
        tidy(ax)
        v = d[col].to_numpy(float)
        ax.bar([0, 1], v, 0.55, color=[C_VERIF, C_LIKELY], zorder=3)
        for xi, val in zip([0, 1], v):
            ax.annotate("%.2f" % val, (xi, val), xytext=(0, 4),
                        textcoords="offset points", ha="center", fontsize=9.5,
                        color=INK_2)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["verified\nmature\nn = %d" % d.loc["verified mature", "n"],
                            "likely\nmature\nn = %d" % d.loc["likely mature", "n"]],
                           fontsize=8.6)
        ax.set_ylabel(lab, fontsize=9)
        ax.set_title("%s" % kind, loc="left", fontsize=10, color=INK_2)
        ax.set_ylim(0, max(v) * 1.28)
    fig.suptitle("Why Run 1 exists: the two maturity classes carry almost the "
                 "same biomass and behave completely differently",
                 x=0.06, ha="left", fontsize=12)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_01_why_run1.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_by_window(cmp, nulls):
    d = cmp[cmp["is_future"]].set_index("run").reindex(
        [r for r in FUTURE if r in set(cmp["run"])])
    x = np.arange(len(d))
    n = nulls.set_index(["run", "null"])

    fig, axes = plt.subplots(2, 1, figsize=(10.6, 8.0), sharex=True)
    for ax, (c0, c1, lab) in zip(axes, [
            ("ratio_run0", "ratio_run1",
             "median M' / observed AGB, analogue-found sites"),
            ("rho_run0", "rho_run1", "Spearman rank correlation")]):
        tidy(ax)
        ax.plot(x, d[c0], "-o", color=C_RUN0, lw=2.0, ms=7,
                markeredgecolor=SURFACE, markeredgewidth=1.1,
                label="Run 0, mature (600 sites)", zorder=5)
        ax.plot(x, d[c1], "-o", color=C_RUN1, lw=2.2, ms=8,
                markeredgecolor=SURFACE, markeredgewidth=1.2,
                label="Run 1, verified only (327 sites)", zorder=6)
        key = "median_ratio" if "ratio" in c0 else "spearman_rho"
        for run, colour, ls in (("Run 0", C_RUN0, ":"), ("Run 1", C_RUN1, ":")):
            for nm, style in (("NVIS-constrained", "-."),
                              ("unconstrained", ":")):
                if (run, nm) in n.index:
                    ax.axhline(n.loc[(run, nm), key], color=colour, lw=1.1,
                               ls=style, alpha=0.75, zorder=2)
        ax.set_ylabel(lab, fontsize=9)
    axes[0].legend(fontsize=8.8, frameon=False, loc="upper right")
    axes[0].set_title("Run 1 against Run 0, per scenario-window, with both "
                      "nulls drawn in", loc="left")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(
        ["%s\n%s\nn %d / %d" % (r.split("_")[0].upper(), r.split("_")[1],
                                d.loc[r, "n_run0"], d.loc[r, "n_run1"])
         for r in d.index], fontsize=8)
    axes[-1].text(0.995, -0.22, "dash-dot: NVIS-constrained null   dotted: "
                  "unconstrained null   grey Run 0, blue Run 1",
                  transform=axes[-1].transAxes, ha="right", fontsize=8,
                  color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_run1_vs_run0.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_gap(cmp, nulls):
    """What the gain is worth once the null is allowed to move with the sample.

    A null drawn from the same 327 sites is easier to beat for the same reason
    the runs are: the sample is cleaner. So the honest measure of what Run 1
    buys is not the change in the runs, it is the change in the GAP between the
    runs and their own null.
    """
    f = cmp[cmp["is_future"]]
    n = nulls.set_index(["run", "null"])
    runs = {"Run 0": float(f["rho_run0"].median()),
            "Run 1": float(f["rho_run1"].median())}
    labels, vals, colours = [], [], []
    for nm, colour in (("NVIS-constrained", C_NULL_N),
                       ("unconstrained", C_NULL_U)):
        for run in ("Run 0", "Run 1"):
            if (run, nm) not in n.index:
                continue
            labels.append("%s\nvs the %s null" % (run, nm))
            vals.append(runs[run] - float(n.loc[(run, nm), "spearman_rho"]))
            colours.append(colour if run == "Run 0" else colour)
    x = np.arange(len(vals))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    tidy(ax)
    ax.bar(x, vals, 0.55, color=colours, zorder=3,
           edgecolor=[C_RUN1 if "Run 1" in l else C_RUN0 for l in labels],
           linewidth=2.0)
    for xi, v in zip(x, vals):
        ax.annotate("%+.3f" % v, (xi, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=9.5,
                    color=INK_2)
    ax.axhline(0, color="#333333", lw=1.0, zorder=5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.6)
    ax.set_ylabel("rank correlation of the runs minus that of their own null",
                  fontsize=9)
    ax.set_title("What Run 1 actually buys, once the null moves with the "
                 "sample", loc="left")
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_gap_to_nulls.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    gate = pd.read_csv(OUT_DIR / "gate_by_maturity.csv")
    cmp = pd.read_csv(OUT_DIR / "run01_vs_run00.csv")
    nulls = pd.read_csv(OUT_DIR / "both_nulls.csv")

    for p in (fig_gate(gate), fig_by_window(cmp, nulls), fig_gap(cmp, nulls)):
        print("  -> %s" % p.name)
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
