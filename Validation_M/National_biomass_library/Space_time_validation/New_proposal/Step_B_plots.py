"""
Step B - the figures.

    fig_01  what each single change does to the rank correlation
    fig_02  the same for the median ratio
    fig_03  both nulls beside the runs, every configuration
    fig_04  the no-analogue share, which decides whether a delta means anything
    fig_05  per scenario-window, baseline against the two changes that matter

Axes are linear throughout. Every panel separates the changes whose sample
stayed comparable from those that also moved the no-analogue share, because a
metric computed on a different set of surviving sites is not a like-for-like
comparison and its delta cannot be attributed to the change alone.

Reads   outputs/ofat_summary.csv, ofat_deltas.csv
Writes  plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_B_plots.py
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

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID_C = "#e4e3df"
C_OK = "#2a78d6"          # sample comparable
C_CONF = "#b9b8b4"        # sample also changed
C_POS = "#1baf7a"
C_NEG = "#e34948"
C_NULL_N = "#eda100"
C_NULL_U = "#eb6834"

CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells_nvis", "random_cells_unconstrained"]
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]

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


def label_of(rid, changed):
    return "%s\n%s" % (rid.split("_", 1)[1].replace("_", " "), changed)


def fig_delta(d, col, name, xlabel, title):
    """One change per bar, ordered by size, coloured by whether it is readable."""
    d = d.sort_values(col)
    y = np.arange(len(d))
    colours = [C_OK if ok else C_CONF for ok in d["sample_comparable"]]

    fig, ax = plt.subplots(figsize=(9.8, 5.6))
    tidy(ax, grid_axis="x")
    ax.barh(y, d[col], color=colours, height=0.62, zorder=3)
    ax.axvline(0, color="#333333", lw=1.1, zorder=5)
    for yi, v, ok, na in zip(y, d[col], d["sample_comparable"],
                             d["d_pct_no_analogue"]):
        txt = "%+.3f" % v
        if not ok:
            txt += "   (no-analogue %+.0f pp)" % na
        ax.text(v + (0.004 if v >= 0 else -0.004), yi, txt, va="center",
                ha="left" if v >= 0 else "right", fontsize=8.3, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels([label_of(a, b) for a, b in zip(d["run_id"],
                                                       d["changed"])],
                       fontsize=8.4)
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 0.30 * (hi - lo), hi + 0.24 * (hi - lo))
    ax.legend([Patch(facecolor=C_OK), Patch(facecolor=C_CONF)],
              ["sample stayed comparable - the change did this",
               "sample also changed - not attributable to the change"],
              fontsize=8.4, frameon=False, ncol=2, loc="upper right",
              bbox_to_anchor=(1.0, -0.13))
    dst = PLOT_DIR / name
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_nulls(s):
    """Both nulls against the runs, for every configuration.

    The two nulls answer different questions and neither alone is the answer.
    Against the unconstrained null the analogue search looks decisive, and that
    is what shows the method has skill. Against the null drawn under the same
    NVIS constraint the gap is small, and that is what says how much of the
    skill is the vegetation constraint rather than the climate matching.
    """
    runs = sorted(s["run_id"].unique())
    x = np.arange(len(runs))
    fut = s[~s["run"].isin(CONTROLS)].groupby("run_id")
    med = fut["median_ratio"].median().reindex(runs)
    rho = fut["spearman_rho"].median().reindex(runs)

    def ctl(name, col):
        return s[s["run"] == name].set_index("run_id")[col].reindex(runs)

    fig, axes = plt.subplots(2, 1, figsize=(10.4, 8.0), sharex=True)
    for ax, (vals, nn, nu, hist, lab) in zip(axes, [
            (med, ctl("random_cells_nvis", "median_ratio"),
             ctl("random_cells_unconstrained", "median_ratio"),
             ctl("historical_analogue", "median_ratio"),
             "median ratio, M' at the analogue over observed biomass"),
            (rho, ctl("random_cells_nvis", "spearman_rho"),
             ctl("random_cells_unconstrained", "spearman_rho"),
             ctl("historical_analogue", "spearman_rho"),
             "Spearman rank correlation")]):
        tidy(ax, grid_axis="y")
        ax.plot(x, vals, "-o", color=C_OK, lw=2.2, ms=8,
                markeredgecolor=SURFACE, markeredgewidth=1.2,
                label="future runs (median of the eight)", zorder=5)
        ax.plot(x, hist, "--s", color=INK_2, lw=1.6, ms=6,
                label="present-day analogue (the method's own error)", zorder=4)
        ax.plot(x, nn, "-^", color=C_NULL_N, lw=1.8, ms=7,
                label="null: random cells, NVIS-constrained", zorder=4)
        ax.plot(x, nu, "-v", color=C_NULL_U, lw=1.8, ms=7,
                label="null: random cells, unconstrained", zorder=4)
        ax.set_ylabel(lab, fontsize=9)
    axes[0].legend(fontsize=8.4, frameon=False, ncol=2, loc="upper left")
    axes[0].set_title("Every configuration against both nulls", loc="left")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([r.split("_", 1)[1].replace("_", "\n")
                              for r in runs], fontsize=8.2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_both_nulls.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_no_analogue(s):
    runs = sorted(s["run_id"].unique())
    fut = s[~s["run"].isin(CONTROLS)].groupby("run_id")
    med = fut["pct_no_analogue"].median().reindex(runs)
    nmin = fut["n_analogue_found"].min().reindex(runs)
    x = np.arange(len(runs))
    base = float(med.get("run00_baseline", np.nan))

    fig, ax = plt.subplots(figsize=(10.0, 5.0))
    tidy(ax, grid_axis="y")
    colours = [C_NEG if abs(v - base) >= 10 else C_OK for v in med]
    ax.bar(x, med, 0.6, color=colours, zorder=3)
    if np.isfinite(base):
        ax.axhline(base, color=INK_2, lw=1.2, ls="--", zorder=4)
        ax.text(len(runs) - 0.4, base, " Run 0", va="bottom", ha="right",
                fontsize=8.5, color=INK_2)
    for xi, v, nm in zip(x, med, nmin):
        ax.annotate("%.0f%%\nmin n = %d" % (v, nm), (xi, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8,
                    color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels([r.split("_", 1)[1].replace("_", "\n") for r in runs],
                       fontsize=8.2)
    ax.set_ylabel("sites with no analogue, median over the eight "
                  "scenario-windows (%)", fontsize=9)
    ax.set_title("Which changes also change the sample, and so cannot be read "
                 "at face value", loc="left")
    ax.legend([Patch(facecolor=C_OK), Patch(facecolor=C_NEG)],
              ["within 10 points of Run 0", "10 points or more from Run 0"],
              fontsize=8.4, frameon=False, ncol=2, loc="upper right",
              bbox_to_anchor=(1.0, -0.14))
    dst = PLOT_DIR / "fig_04_no_analogue_share.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_by_window(s, show=("run00_baseline", "run01_verified_only",
                           "run09_noqc")):
    """The scenario-windows themselves, for the changes that actually moved."""
    order = ["%s_%s" % (a, w) for w in WINDOWS for a in SSPS]
    have = [r for r in show if r in set(s["run_id"])]
    x = np.arange(len(order))
    colours = [C_OK, C_POS, C_NEG]

    fig, axes = plt.subplots(2, 1, figsize=(10.6, 7.6), sharex=True)
    for ax, col, lab in zip(axes,
                            ["median_ratio", "spearman_rho"],
                            ["median ratio (analogue-found sites)",
                             "Spearman rank correlation"]):
        tidy(ax, grid_axis="y")
        for rid, colour in zip(have, colours):
            d = s[(s["run_id"] == rid)].set_index("run").reindex(order)
            ax.plot(x, d[col], "-o", color=colour, lw=2.0, ms=7,
                    markeredgecolor=SURFACE, markeredgewidth=1.1,
                    label=rid.split("_", 1)[1].replace("_", " "), zorder=4)
        ax.set_ylabel(lab, fontsize=9)
    axes[0].legend(fontsize=8.5, frameon=False, ncol=3, loc="upper left")
    axes[0].set_title("Per scenario-window, for the changes that moved the "
                      "result", loc="left")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([o.replace("_", "\n").upper() for o in order],
                             fontsize=8.2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_05_by_scenario_window.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    s = pd.read_csv(OUT_DIR / "ofat_summary.csv")
    d = pd.read_csv(OUT_DIR / "ofat_deltas.csv")

    made = [
        fig_delta(d, "d_rho_future", "fig_01_delta_rho.png",
                  "change in Spearman rho against Run 0",
                  "What each single change does to the rank correlation"),
        fig_delta(d, "d_ratio_future", "fig_02_delta_ratio.png",
                  "change in the median ratio against Run 0",
                  "What each single change does to the median ratio"),
        fig_nulls(s),
        fig_no_analogue(s),
        fig_by_window(s),
    ]
    for p in made:
        print("  -> %s" % p.name)
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
