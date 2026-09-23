"""
Run 2 - the comparison, and the figures.

Why the gap to the null is the only fair axis here
--------------------------------------------------
Raising the plot-area floor does two things at once. It removes the
per-hectare inflation, which is the point - but it also lowers the observed
biomass of whatever survives, because the surviving plots are larger and larger
plots report less biomass per hectare. Median observed AGB falls from 112 Mg/ha
with no floor to 43 at 0.50 ha.

Any ratio of M' to observed biomass therefore rises as the floor rises, for
every M' including a randomly chosen one. The constrained null's own ratio goes
from 0.445 to 1.255 across this sweep. So a ratio approaching 1 is not by itself
evidence of anything, and the comparison has to be against the null that moved
with it.

The same is true of the rank correlation, though less dramatically, so both are
reported as a GAP: the run minus its own null, under both nulls.

    outputs/area_floor_comparison.csv    every configuration, both nulls, gaps
    plots/fig_01_ratio_and_rho.png       the sweep, with both nulls drawn in
    plots/fig_02_gap_to_null.png         the decision figure
    plots/fig_03_tradeoff.png            sites retained against skill gained

Reads   outputs/area_floor_summary.csv
Writes  outputs/area_floor_comparison.csv
        plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_compare.py
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

CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells_nvis", "random_cells_unconstrained"]
FLOORS = ["area_010", "area_020", "area_025", "area_030", "area_040",
          "area_050"]
REFS = ["mature_nofloor", "verified_nofloor"]
BOTH = ["area_025_mature"]

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_AREA = "#2a78d6"
C_RUN0 = "#6b6a66"
C_RUN1 = "#eb6834"
C_BOTH = "#9b59b6"
C_NULL_N = "#eda100"
C_NULL_U = "#1baf7a"

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


def build(s):
    rows = []
    for cfg, g in s.groupby("config", sort=False):
        fut = g[~g["run"].isin(CONTROLS)]
        d = g.set_index("run")

        def ctl(name, col):
            return float(d.loc[name, col]) if name in d.index else np.nan

        r = float(fut["median_ratio"].median())
        rho = float(fut["spearman_rho"].median())
        rows.append(dict(
            config=cfg,
            min_area_ha=float(g["min_area_ha"].iloc[0]),
            maturity=g["maturity"].iloc[0],
            n_sites=int(g["n_sites"].max()),
            median_plot_ha=float(g["median_plot_ha"].iloc[0]),
            median_agb_per_ba=float(g["median_agb_per_ba"].iloc[0]),
            pct_no_analogue=float(fut["pct_no_analogue"].median()),
            ratio=r, rho=rho,
            null_nvis_ratio=ctl("random_cells_nvis", "median_ratio"),
            null_nvis_rho=ctl("random_cells_nvis", "spearman_rho"),
            null_free_ratio=ctl("random_cells_unconstrained", "median_ratio"),
            null_free_rho=ctl("random_cells_unconstrained", "spearman_rho"),
            gate_ratio=ctl("same_cell_present_day", "median_ratio"),
            gate_rho=ctl("same_cell_present_day", "spearman_rho")))
    d = pd.DataFrame(rows)
    d["gap_rho_nvis"] = d["rho"] - d["null_nvis_rho"]
    d["gap_rho_free"] = d["rho"] - d["null_free_rho"]
    d["gap_ratio_nvis"] = d["ratio"] - d["null_nvis_ratio"]
    return d


def fig_sweep(d):
    f = d[d["config"].isin(FLOORS)].sort_values("min_area_ha")
    x = f["min_area_ha"].to_numpy()
    ref = d.set_index("config")

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.0))
    for ax, (col, nn, nu, lab, one) in zip(axes, [
            ("ratio", "null_nvis_ratio", "null_free_ratio",
             "median M' / observed AGB", True),
            ("rho", "null_nvis_rho", "null_free_rho",
             "Spearman rank correlation", False)]):
        tidy(ax)
        ax.plot(x, f[col], "-o", color=C_AREA, lw=2.4, ms=8,
                markeredgecolor=SURFACE, markeredgewidth=1.2,
                label="plot-area floor, every maturity class", zorder=6)
        ax.plot(x, f[nn], "-^", color=C_NULL_N, lw=1.8, ms=7,
                label="its NVIS-constrained null", zorder=4)
        ax.plot(x, f[nu], "-v", color=C_NULL_U, lw=1.8, ms=7,
                label="its unconstrained null", zorder=4)
        for cfg, colour, mark, name in (
                ("mature_nofloor", C_RUN0, "s", "Run 0: mature, no floor"),
                ("verified_nofloor", C_RUN1, "D", "Run 1: verified only"),
                ("area_025_mature", C_BOTH, "P", "both filters together")):
            if cfg in ref.index:
                ax.axhline(ref.loc[cfg, col], color=colour, lw=1.3, ls="--",
                           alpha=0.9, zorder=3, label=name)
        if one:
            ax.axhline(1.0, color=INK, lw=1.1, ls=":", zorder=2)
            ax.text(x.max(), 1.0, " M' = observed", va="bottom", ha="right",
                    fontsize=8.4, color=INK_2)
        ax.set_xlabel("plot-area floor (ha)")
        ax.set_ylabel(lab, fontsize=9)
    axes[0].legend(fontsize=8.2, frameon=False, loc="upper left")
    axes[0].set_title("a) The ratio rises past 1 - but so does its null",
                      loc="left")
    axes[1].set_title("b) The rank correlation", loc="left")
    fig.tight_layout()
    dst = PLOT_DIR / "fig_01_ratio_and_rho.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_gap(d):
    """The decision figure: skill above the null, which is what survives."""
    order = REFS + FLOORS + BOTH
    d = d.set_index("config").reindex([c for c in order if c in set(d.config)])
    x = np.arange(len(d))
    colours = []
    for c in d.index:
        colours.append(C_RUN0 if c == "mature_nofloor" else
                       C_RUN1 if c == "verified_nofloor" else
                       C_BOTH if c in BOTH else C_AREA)

    fig, ax = plt.subplots(figsize=(10.6, 5.4))
    tidy(ax)
    ax.bar(x, d["gap_rho_nvis"], 0.58, color=colours, zorder=3)
    ax.axhline(0, color="#333333", lw=1.1, zorder=5)
    base = float(d.loc["mature_nofloor", "gap_rho_nvis"]) \
        if "mature_nofloor" in d.index else np.nan
    if np.isfinite(base):
        ax.axhline(base, color=C_RUN0, lw=1.2, ls="--", zorder=4)
    for xi, v, n in zip(x, d["gap_rho_nvis"], d["n_sites"]):
        ax.annotate("%+.3f\nn = %d" % (v, n), (xi, v),
                    xytext=(0, 5 if v >= 0 else -22),
                    textcoords="offset points", ha="center", fontsize=8.4,
                    color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in d.index], fontsize=8.3)
    ax.set_ylabel("rank correlation above the NVIS-constrained null", fontsize=9)
    ax.set_title("Skill above the null - the only axis the area floor does not "
                 "inflate", loc="left")
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo - 0.03, hi + 0.03)
    dst = PLOT_DIR / "fig_02_gap_to_null.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_tradeoff(d):
    """Sites kept against skill gained - the choice, on one axis each."""
    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    tidy(ax, grid_axis="both")
    for _, r in d.iterrows():
        c = r["config"]
        colour = (C_RUN0 if c == "mature_nofloor" else
                  C_RUN1 if c == "verified_nofloor" else
                  C_BOTH if c in BOTH else C_AREA)
        ax.scatter(r["n_sites"], r["gap_rho_nvis"], s=130, color=colour,
                   edgecolor=SURFACE, linewidth=1.4, zorder=5)
        ax.annotate(c.replace("_nofloor", "").replace("area_", "≥0.")
                    .replace("0.010", "10 ha"),
                    (r["n_sites"], r["gap_rho_nvis"]), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=8.2,
                    color=INK_2)
    ax.axhline(0, color="#333333", lw=1.0, zorder=3)
    ax.set_xlabel("sites retained")
    ax.set_ylabel("rank correlation above the NVIS-constrained null", fontsize=9)
    ax.set_title("What each filter costs in sites and returns in skill",
                 loc="left")
    ax.text(0.99, 0.03, "up and to the right is better",
            transform=ax.transAxes, ha="right", fontsize=8.5, color=INK_2)
    dst = PLOT_DIR / "fig_03_tradeoff.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    s = pd.read_csv(OUT_DIR / "area_floor_summary.csv")
    d = build(s)
    d.to_csv(OUT_DIR / "area_floor_comparison.csv", index=False)

    cols = ["config", "n_sites", "median_plot_ha", "median_agb_per_ba",
            "ratio", "null_nvis_ratio", "rho", "null_nvis_rho",
            "gap_rho_nvis", "gap_rho_free", "pct_no_analogue"]
    print(d[cols].to_string(index=False, float_format=lambda v: "%.3f" % v))

    best = d.loc[d["gap_rho_nvis"].idxmax()]
    print("\nlargest gap to the constrained null: %s, %d sites, gap %+.3f"
          % (best["config"], best["n_sites"], best["gap_rho_nvis"]))

    for p in (fig_sweep(d), fig_gap(d), fig_tradeoff(d)):
        print("  -> %s" % p.name)
    print("\ntables and figures in %s" % OUT_DIR.parent)


if __name__ == "__main__":
    main()
