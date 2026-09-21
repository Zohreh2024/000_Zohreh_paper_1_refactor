"""
Step 04 - the figures for the space-for-time validation.

Reads   outputs/reference_table.csv, outputs/matches.csv,
        outputs/metrics_by_run.csv, outputs/metrics_by_maturity.csv
Writes  plots/fig_01_reference_sites.png
        plots/fig_02_present_day_gate.png
        plots/fig_03_match_quality.png
        plots/fig_04_obs_vs_matched.png
        plots/fig_05_ratio_by_run.png
        plots/fig_06_displacement.png

Recomputes no metric; every number comes from Step_03's CSVs.

Colour: magnitude on a one-hue blue ramp, anything centred on a meaningful value
(a ratio against 1) on a diverging blue/red pair with a neutral grey midpoint.
All axes are linear. Biomass spans three orders of magnitude, so axis limits are
set just above the bulk of the data (a high percentile) and the handful of sites
beyond are clipped - the shape of the data is shown as it is, rather than
straightened by a transform.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_04_plots.py
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402
from matplotlib.colors import LinearSegmentedColormap          # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells"]
CONTROL_LABEL = {"same_cell_present_day": "the site's own cell, today",
                 "historical_analogue": "present-day analogue",
                 "random_cells": "random cells (null)"}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8a85"
GRID_C = "#e4e3df"
C_MATURE = "#2a78d6"
C_LIKELY = "#eb6834"
C_CONTROL = "#52514e"
C_FUT = "#1b3a5c"

SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])

SUFFIX = ""          # set from --suffix; keeps the two variants side by side


def out_path(name):
    """fig_05_ratio_by_run.png -> fig_05_ratio_by_run_nvis.png"""
    return PLOT_DIR / ("%s%s.png" % (name, SUFFIX))


plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": GRID_C, "grid.color": GRID_C,
    "font.size": 9.5, "axes.titlesize": 10.5, "legend.frameon": False,
})


def tidy(ax, grid_axis=None):
    ax.spines[["top", "right"]].set_visible(False)
    if grid_axis:
        ax.grid(True, axis=grid_axis, lw=0.6, alpha=0.9)
        ax.set_axisbelow(True)
    return ax


def square(ax, lo=0.0, hi=1200.0):
    """Linear axes, equal on both, with the 1:1 line.

    Biomass spans three orders of magnitude, so the low end is dense and the
    few very large sites sit alone in the corner. That is what the data looks
    like; the axis limit is set just above the bulk (see `hi`) so the dense
    part stays readable, and sites beyond it are clipped rather than hidden
    behind a transform.
    """
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    # Few, round ticks: with eight panels side by side the default locator puts
    # a label at each panel edge and neighbouring labels run into one another.
    ticks = [t for t in (0, 400, 800, 1200, 1600, 2000) if lo <= t <= hi]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.plot([lo, hi], [lo, hi], color=INK_MUTED, lw=1.2, ls="--", zorder=1)
    return ax


def label_run(run):
    if run in CONTROL_LABEL:
        return CONTROL_LABEL[run]
    ssp, win = run.rsplit("_", 1)
    return "%s %s" % (ssp.replace("ssp", "SSP"), win)


# --------------------------------------------------------------------------- #

def fig_sites(ref):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.8),
                                   gridspec_kw={"width_ratios": [1.15, 1]})
    for mat, c in [("verified mature", C_MATURE), ("likely mature", C_LIKELY)]:
        d = ref[ref["maturity"] == mat]
        if d.empty:
            continue
        ax1.scatter(d["longitude"], d["latitude"], s=np.clip(d["agb"] / 6, 4, 90),
                    color=c, alpha=0.55, lw=0.3, edgecolor="white",
                    label="%s (n=%d)" % (mat, len(d)))
    ax1.set_xlabel("longitude")
    ax1.set_ylabel("latitude")
    ax1.set_title("a) Reference sites", loc="left")
    ax1.legend(fontsize=9, loc="lower left")
    ax1.set_aspect(1 / np.cos(np.deg2rad(30)))
    tidy(ax1)

    bins = np.linspace(0, float(np.nanpercentile(ref["agb"], 99)), 40)
    for mat, c in [("verified mature", C_MATURE), ("likely mature", C_LIKELY)]:
        d = ref[ref["maturity"] == mat]
        if not d.empty:
            ax2.hist(d["agb"], bins=bins, color=c, alpha=0.7, label=mat)
    ax2.set_xlabel("observed above-ground biomass (Mg ha$^{-1}$)")
    ax2.set_ylabel("sites")
    ax2.set_title("b) Observed biomass distribution", loc="left")
    ax2.legend(fontsize=9)
    tidy(ax2, grid_axis="y")

    fig.tight_layout()
    dst = out_path("fig_01_reference_sites")
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def fig_gate(matches, runs):
    d = matches[matches["run"] == "same_cell_present_day"]
    m = runs[(runs["run"] == "same_cell_present_day") &
             (runs["stratum"] == "all matched")].iloc[0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.9))
    for mat, c in [("verified mature", C_MATURE), ("likely mature", C_LIKELY)]:
        s = d[d["maturity"] == mat]
        ax1.scatter(s["agb"], s["M_matched"], s=16, color=c, alpha=0.5,
                    lw=0.3, edgecolor="white", label=mat)
    square(ax1)
    ax1.set_xlabel("observed AGB (Mg ha$^{-1}$)")
    ax1.set_ylabel("M' at the same cell, today (t DM ha$^{-1}$)")
    ax1.set_title("a) M' at the site's own cell against observed AGB",
                  loc="left")
    ax1.text(0.03, 0.97,
             "n = %d sites\nmedian ratio = %.2f\nSpearman rho = %.2f\n"
             "within 2x = %.0f%%\nRMSE = %.0f Mg/ha"
             % (int(m["n"]), m["median_ratio"], m["spearman_rho"],
                m["pct_within_2x"], m["rmse"]),
             transform=ax1.transAxes, va="top", fontsize=8.5, color=INK_2,
             linespacing=1.5)
    ax1.legend(fontsize=9, loc="lower right")
    tidy(ax1)

    ratio = (d["M_matched"] / d["agb"]).replace([np.inf, -np.inf], np.nan).dropna()
    # The ratio has a very long right tail (a few sites carry almost no
    # biomass), so the axis stops at the 95th percentile or 6, whichever is
    # smaller; the count beyond it is stated rather than drawn.
    hi_r = min(float(np.nanpercentile(ratio, 95)), 6.0)
    beyond = int((ratio > hi_r).sum())
    ax2.hist(ratio[ratio <= hi_r], bins=np.linspace(0, hi_r, 45),
             color=C_FUT, alpha=0.85)
    ax2.set_xlim(0, hi_r)
    ax2.axvline(1, color=INK_MUTED, lw=1.4, ls="--")
    ax2.axvline(float(np.median(ratio)), color=C_LIKELY, lw=1.8)
    ax2.set_xlabel("M' $\\div$ observed AGB")
    ax2.set_ylabel("sites")
    ax2.set_title("b) Distribution of M' / observed AGB", loc="left")
    ax2.text(0.97, 0.97,
             "median %.2f%s%d site(s) beyond %.1f not shown"
             % (float(np.median(ratio)), "\n", beyond, hi_r),
             transform=ax2.transAxes, va="top", ha="right", fontsize=9,
             color=INK_2, linespacing=1.5)
    tidy(ax2, grid_axis="y")

    fig.tight_layout()
    dst = out_path("fig_02_present_day_gate")
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def fig_match_quality(matches, na):
    fut = matches[~matches["run"].isin(CONTROLS)]
    hist = matches[matches["run"] == "historical_analogue"]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4))

    ax = tidy(axes[0], grid_axis="y")
    bins = np.linspace(0, np.nanpercentile(fut["match_distance"], 99), 45)
    ax.hist(hist["match_distance"].dropna(), bins=bins, color=C_CONTROL,
            alpha=0.55, label="present-day analogue")
    ax.hist(fut["match_distance"].dropna(), bins=bins, color=C_FUT, alpha=0.7,
            label="future analogues (8 runs)")
    ax.set_xlabel("distance in predictor space")
    ax.set_ylabel("sites")
    ax.set_title("a) Distance to the analogue in predictor space",
                 loc="left")
    ax.legend(fontsize=9)

    ax = tidy(axes[1], grid_axis="x")
    d = na[~na["run"].isin(["same_cell_present_day"])].copy()
    d["label"] = d["run"].map(label_run)
    y = np.arange(len(d))[::-1]
    ax.barh(y, d["pct"], color=[C_CONTROL if r in CONTROLS else C_FUT
                                for r in d["run"]], height=0.65)
    for yi, v in zip(y, d["pct"]):
        ax.text(v + 0.4, yi, "%.1f%%" % v, va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels(d["label"], fontsize=8.5)
    ax.set_xlabel("sites with no close analogue (%)")
    ax.set_title("b) Sites with no close analogue", loc="left")

    ax = tidy(axes[2], grid_axis="y")
    ax.hist(fut["displacement_km"].dropna(), bins=45, color=C_FUT, alpha=0.85)
    ax.set_xlabel("distance from site to its analogue (km)")
    ax.set_ylabel("matches")
    ax.set_title("c) Distance to the analogue on the ground", loc="left")
    ax.text(0.97, 0.97, "median %.0f km"
            % np.nanmedian(fut["displacement_km"]),
            transform=ax.transAxes, va="top", ha="right", fontsize=9,
            color=INK_2)

    fig.tight_layout()
    dst = out_path("fig_03_match_quality")
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def fig_obs_vs_matched(matches, runs):
    fig, axes = plt.subplots(2, 4, figsize=(14.0, 7.2), sharex=True, sharey=True)
    r = runs[runs["stratum"] == "analogue found"].set_index("run")
    for i, win in enumerate(WINDOWS):
        for j, ssp in enumerate(SSPS):
            run = "%s_%s" % (ssp, win)
            ax = axes[i, j]
            d = matches[(matches["run"] == run) & (~matches["no_analogue"])]
            if d.empty:
                ax.axis("off")
                continue
            for mat, c in [("verified mature", C_MATURE), ("likely mature", C_LIKELY)]:
                s = d[d["maturity"] == mat]
                ax.scatter(s["agb"], s["M_matched"], s=13, color=c, alpha=0.45,
                           lw=0.25, edgecolor="white", label=mat)
            square(ax)
            row = r.loc[run] if run in r.index else None
            if row is not None:
                ax.text(0.04, 0.96,
                        "n = %d\nratio = %.2f\nrho = %.2f\nwithin 2x = %.0f%%"
                        % (int(row["n"]), row["median_ratio"],
                           row["spearman_rho"], row["pct_within_2x"]),
                        transform=ax.transAxes, va="top", fontsize=8,
                        color=INK_2, linespacing=1.45)
            ax.set_title("%s %s" % (ssp.replace("ssp", "SSP"), win), loc="left")
            tidy(ax)
    axes[0, 0].legend(fontsize=8.5, loc="upper right", markerscale=1.8)
    for ax in axes[1]:
        ax.set_xlabel("observed AGB (Mg ha$^{-1}$)")
    for ax in axes[:, 0]:
        ax.set_ylabel("M' at the analogue cell")

    fig.suptitle("Observed AGB against M' at the matched future cell",
                 fontsize=11, color=INK_2)
    fig.tight_layout()
    dst = out_path("fig_04_obs_vs_matched")
    fig.savefig(dst, dpi=180)
    plt.close(fig)
    return dst


def fig_ratio_by_run(runs):
    d = runs[runs["stratum"] == "analogue found"].copy()
    order = CONTROLS + ["%s_%s" % (s, w) for w in WINDOWS for s in SSPS]
    d["order"] = d["run"].apply(lambda r: order.index(r) if r in order else 99)
    d = d.sort_values("order")
    d["label"] = d["run"].map(label_run)

    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(10.6, 5.6))
    colors = [C_CONTROL if r in CONTROLS else C_FUT for r in d["run"]]
    ax.errorbar(d["median_ratio"], y,
                xerr=[d["median_ratio"] - d["median_ratio_lo"],
                      d["median_ratio_hi"] - d["median_ratio"]],
                fmt="none", ecolor=INK_MUTED, lw=1.4, capsize=3, zorder=1)
    ax.scatter(d["median_ratio"], y, s=70, color=colors, zorder=2,
               lw=0.6, edgecolor="white")
    for yi, v, n in zip(y, d["median_ratio"], d["n"]):
        ax.text(v, yi + 0.28, "%.2f" % v, ha="center", fontsize=8.5, color=INK_2)
    ax.axvline(1, color=INK_MUTED, lw=1.4, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(d["label"], fontsize=9)
    ax.set_xlabel("median M' $\\div$ observed AGB   (95% bootstrap interval)")
    ax.set_title("Median M' / observed AGB by run", loc="left")
    tidy(ax, grid_axis="x")
    fig.tight_layout()
    dst = out_path("fig_05_ratio_by_run")
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def fig_displacement(matches, run="ssp585_2070-2099"):
    d = matches[(matches["run"] == run) & (~matches["no_analogue"])]
    if d.empty:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.2),
                                   gridspec_kw={"width_ratios": [1.1, 1]})

    for _, r in d.iterrows():
        ax1.annotate("", xy=(r["match_x"], r["match_y"]),
                     xytext=(r["x"], r["y"]),
                     arrowprops=dict(arrowstyle="->", color=C_FUT, lw=0.5,
                                     alpha=0.35))
    ax1.scatter(d["x"], d["y"], s=10, color=C_LIKELY, zorder=3, lw=0,
                label="NBL site")
    ax1.set_xlabel("longitude")
    ax1.set_ylabel("latitude")
    ax1.set_aspect(1 / np.cos(np.deg2rad(30)))
    ax1.set_title("a) Site to matched cell, %s" % label_run(run),
                  loc="left")
    ax1.legend(fontsize=9, loc="lower left")
    tidy(ax1)

    sc = ax2.scatter(d["displacement_km"], d["M_matched"] / d["agb"],
                     c=d["match_distance"], cmap=SEQ_BLUE, s=18, lw=0.2,
                     edgecolor="white")
    ax2.axhline(1, color=INK_MUTED, lw=1.2, ls="--")
    ax2.set_ylim(0, float(np.nanpercentile(d["M_matched"] / d["agb"], 98)))
    ax2.set_xlabel("distance to the analogue (km)")
    ax2.set_ylabel("M' $\\div$ observed AGB")
    ax2.set_title("b) Agreement against distance to the analogue",
                  loc="left")
    rho_d = stats.spearmanr(d["displacement_km"],
                            d["M_matched"] / d["agb"]).correlation
    ax2.text(0.97, 0.97, "Spearman rho = %+.2f" % rho_d,
             transform=ax2.transAxes, va="top", ha="right", fontsize=9,
             color=INK_2)
    cb = fig.colorbar(sc, ax=ax2, fraction=0.045, pad=0.02)
    cb.set_label("distance in predictor space", fontsize=8.5)
    cb.outline.set_visible(False)
    tidy(ax2, grid_axis="y")

    fig.tight_layout()
    dst = out_path("fig_06_displacement")
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suffix", default="", help="'_climate_only' for that variant")
    args = ap.parse_args()

    global SUFFIX
    SUFFIX = args.suffix
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(OUT_DIR / "reference_table.csv", low_memory=False)
    matches = pd.read_csv(OUT_DIR / ("matches%s.csv" % args.suffix))
    runs = pd.read_csv(OUT_DIR / ("metrics_by_run%s.csv" % args.suffix))
    na = pd.read_csv(OUT_DIR / ("no_analogue_summary%s.csv" % args.suffix))

    ref = ref[ref["site"].isin(matches["site"].unique())]

    for fn, arg in [(fig_sites, (ref,)), (fig_gate, (matches, runs)),
                    (fig_match_quality, (matches, na)),
                    (fig_obs_vs_matched, (matches, runs)),
                    (fig_ratio_by_run, (runs,)),
                    (fig_displacement, (matches,))]:
        out = fn(*arg)
        print("  -> %s" % (out.name if out else "skipped"))

    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
