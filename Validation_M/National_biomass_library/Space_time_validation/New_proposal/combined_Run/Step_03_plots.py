"""
Combined run, step 3 - the figures.

    fig_01  the ladder: what each ingredient adds, and what the nulls do
    fig_02  coverage, before and after
    fig_03  what the ceiling removes

Reads   outputs/combined_headline.csv, reference_table_combined.csv,
        provider_effects.csv, ceiling_calibration.csv
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
SOUTH = -37.0
MATURE = ["verified mature", "likely mature"]

SURFACE, INK, INK2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_RUN, C_NULL, C_GAP = "#2a78d6", "#eda100", "#1baf7a"
C_OLD, C_NEW = "#6b6a66", "#e34948"

LABEL = {
    "run0": "Run 0\nas published",
    "run3_rebuilt": "+ biomass\nrebuilt",
    "combined_no_area": "+ floor retired\n+ ceiling",
    "combined_no_ceiling": "+ 0.04 ha\n(no ceiling)",
    "combined": "all four\ncombined",
}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="y"):
    ax.tick_params(labelsize=9, colors=INK2, length=2.5, width=0.6)
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


def find_up(start, name):
    for d in [start] + list(start.parents):
        if (d / name).exists():
            return d
    raise SystemExit("not found")


def fig_ladder(h):
    d = h.set_index("config")
    order = [c for c in LABEL if c in d.index]
    x = np.arange(len(order))
    w = 0.27

    fig, axes = plt.subplots(2, 1, figsize=(10.6, 8.4), sharex=True)
    ax = tidy(axes[0])
    ax.plot(x, d.loc[order, "gate_rho"], "-o", color=C_RUN, lw=2.4, ms=10,
            markeredgecolor=SURFACE, markeredgewidth=1.3, zorder=5)
    for xi, v, n in zip(x, d.loc[order, "gate_rho"], d.loc[order, "sites"]):
        ax.annotate("%.3f\nn = %d" % (v, n), (xi, v), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=9,
                    color=INK2)
    ax.axhline(float(d.loc["run0", "gate_rho"]), color=C_OLD, lw=1.2, ls="--",
               zorder=3)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("a) The present-day gate: M' against observed biomass at the "
                 "site's own cell", loc="left")
    ax.set_ylim(0, 1.0)

    ax = tidy(axes[1])
    ax.bar(x - w, d.loc[order, "rho"], w, color=C_RUN,
           label="the eight future runs", zorder=3)
    ax.bar(x, d.loc[order, "null_nvis_rho"], w, color=C_NULL,
           label="their NVIS-constrained null", zorder=3)
    ax.bar(x + w, d.loc[order, "gap_rho_nvis"], w, color=C_GAP,
           label="the gap between them", zorder=3)
    ax.axhline(float(d.loc["run0", "gap_rho_nvis"]), color=C_OLD, lw=1.2,
               ls="--", zorder=4)
    for xi, v in zip(x, d.loc[order, "gap_rho_nvis"]):
        ax.annotate("%+.3f" % v, (xi + w, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8.6,
                    color=INK2)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("b) The future runs, their null, and the gap that survives it",
                 loc="left")
    ax.legend(fontsize=8.6, frameon=False, ncol=3)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([LABEL[c] for c in order], fontsize=8.8)
    axes[-1].text(0.995, -0.20, "dashed lines: Run 0",
                  transform=axes[-1].transAxes, ha="right", fontsize=8,
                  color=INK2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_01_ladder.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_coverage():
    stv = find_up(HERE, "Step_03_match_and_validate.py")
    old = pd.read_csv(stv / "outputs" / "reference_table.csv", low_memory=False)
    old = old[old["maturity"].isin(MATURE)]
    new = pd.read_csv(OUT_DIR / "reference_table_combined.csv",
                      low_memory=False)
    added = new[~new["site"].isin(set(old["site"]))]

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4),
                             gridspec_kw={"width_ratios": (1.5, 1)})
    ax = tidy(axes[0], grid_axis="both")
    ax.scatter(old["longitude"], old["latitude"], s=13, color=C_OLD,
               alpha=0.6, label="Run 0 (%d sites)" % len(old), zorder=3)
    ax.scatter(added["longitude"], added["latitude"], s=22, color=C_NEW,
               alpha=0.9, edgecolor=SURFACE, linewidth=0.4,
               label="added by the combined recipe (%d)" % len(added),
               zorder=5)
    ax.axhline(SOUTH, color=INK, lw=1.2, ls="--", zorder=4)
    ax.text(114, SOUTH, " 37°S", va="bottom", fontsize=9, color=INK2)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("a) Where the sample grew", loc="left")
    ax.legend(fontsize=8.6, frameon=False, loc="lower left")

    ax = tidy(axes[1], grid_axis="x")
    bins = np.arange(-44, -9, 2.0)
    ax.hist(old["latitude"], bins=bins, orientation="horizontal", color=C_OLD,
            alpha=0.75, label="Run 0", zorder=3)
    ax.hist(new["latitude"], bins=bins, orientation="horizontal",
            histtype="step", lw=2.2, color=C_RUN, label="combined", zorder=4)
    ax.axhline(SOUTH, color=INK, lw=1.2, ls="--", zorder=5)
    ax.set_xlabel("sites")
    ax.set_ylabel("latitude")
    ax.set_title("b) Latitude distribution", loc="left")
    ax.legend(fontsize=8.6, frameon=False)
    ax.text(0.97, 0.03, "south of 37°S: %d → %d"
            % (int((old["latitude"] < SOUTH).sum()),
               int((new["latitude"] < SOUTH).sum())),
            transform=ax.transAxes, ha="right", fontsize=9.5, color=INK)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_coverage.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_ceiling():
    new = pd.read_csv(OUT_DIR / "reference_table_combined.csv",
                      low_memory=False)
    cal = pd.read_csv(OUT_DIR / "ceiling_calibration.csv").iloc[0]
    prov = pd.read_csv(OUT_DIR / "provider_effects.csv")
    prov = prov[prov["sites"] >= 10].sort_values("ratio_median",
                                                 ascending=False).head(10)

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0))
    ax = tidy(axes[0])
    hi = float(np.nanpercentile(new["agb_per_ba"], 99)) * 1.2
    for cl, colour in (("verified mature", C_RUN),
                       ("likely mature", "#7fb3f0")):
        v = new.loc[new["maturity"] == cl, "agb_per_ba"].dropna()
        ax.hist(v[v <= hi], bins=40, histtype="step", lw=2.0, color=colour,
                label="%s (%d)" % (cl, len(v)), zorder=4)
    ax.axvline(cal["ceiling"], color=C_NEW, lw=1.6, ls="--", zorder=5)
    ax.text(cal["ceiling"], ax.get_ylim()[1] * 0.92,
            "  ceiling %.1f\n  (95th percentile of\n  verified mature)"
            % cal["ceiling"], fontsize=8.6, color=C_NEW, va="top")
    ax.set_xlabel("rebuilt AGB per m$^2$/ha of live basal area")
    ax.set_ylabel("sites")
    ax.set_title("a) Where the ceiling sits", loc="left")
    ax.legend(fontsize=8.6, frameon=False, loc="upper right")

    ax = tidy(axes[1], grid_axis="x")
    y = np.arange(len(prov))[::-1]
    ax.barh(y, prov["ratio_median"], 0.6, color=C_RUN, zorder=3)
    ax.axvline(cal["ceiling"], color=C_NEW, lw=1.6, ls="--", zorder=5)
    for yi, r in zip(y, prov.itertuples()):
        ax.text(r.ratio_median + 0.6, yi, "%.0f%% kept  (n=%d)"
                % (r.pct_kept, r.sites), va="center", fontsize=8.2,
                color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels([s[:32] for s in prov["source"]], fontsize=8.2)
    ax.set_xlabel("median rebuilt AGB per m$^2$/ha of basal area")
    ax.set_title("b) By provider, against the ceiling", loc="left")
    lo, hi2 = ax.get_xlim()
    ax.set_xlim(0, hi2 * 1.35)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_ceiling.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(OUT_DIR / "combined_headline.csv")
    for p in (fig_ladder(h), fig_coverage(), fig_ceiling()):
        print("  -> %s" % p.name)
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
