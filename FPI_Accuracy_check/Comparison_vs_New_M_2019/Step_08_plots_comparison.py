"""
Step 08 - the comparison figures. One metric per figure, as asked.

Reads   output/*.csv, output/cv/*.tif, ../output_Mprime_rf/mean_of_annual/*_mean.tif,
        Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif
Writes  plots/fig_06_cv_interannual.png        interannual CV, 8 windows + historical
        plots/fig_07_cv_change.png             future CV - historical CV
        plots/fig_08_cv_across_scenarios.png   scenario disagreement
        plots/fig_09_scatter_vs_New_M_2019.png M' against the reference, per window
        plots/fig_10_totals.png                national total biomass
        plots/fig_11_change_by_decile.png      where the change sits in the distribution

Recomputes no metric: the maps come from Step_07's rasters and every number from
its CSVs.

Colour
------
Magnitude (CV, M') is a one-hue blue ramp. Anything centred on a meaningful zero
- a change in CV, a percent change - is a diverging blue/red pair with a neutral
grey midpoint, symmetric about that centre. The four scenarios take a fixed
categorical order (blue, aqua, yellow, red) that clears the CVD and
normal-vision separation checks; aqua and yellow sit below 3:1 on this surface,
so every series is also directly labelled rather than identified by colour alone.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_08_plots_comparison.py
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402
import rasterio                                                # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm   # noqa: E402

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent
OUT_DIR = HERE / "output"
CV_DIR = OUT_DIR / "cv"
PLOT_DIR = HERE / "plots"
MPRIME_ANNUAL = PARENT / "output_Mprime_rf" / "mean_of_annual"
MPRIME_OFMEAN = PARENT / "output_Mprime_rf" / "eq1_of_mean"
ORDER = "eq1_of_mean"        # the method; --order mean_of_annual is the sensitivity


def window_mean_path(ssp, win):
    if ORDER == "eq1_of_mean":
        return MPRIME_OFMEAN / ("maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win))
    return MPRIME_ANNUAL / ("maxAbgMF_%s_%s_mean.tif" % (ssp, win))
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019_NLUM.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
DECIMATE = 4

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8a85"
GRID_C = "#e4e3df"
SSP_C = {"ssp126": "#2a78d6", "ssp245": "#1baf7a",
         "ssp370": "#eda100", "ssp585": "#e34948"}
HIST_C = "#52514e"

SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list("blue_red", [
    "#0d366b", "#256abf", "#86b6ef", "#f0efec", "#ec8a89", "#d03b3b", "#7d1f1f"])

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


def read(path, dec=1):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float32")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
        b = s.bounds
    if dec > 1:
        a = a[::dec, ::dec]
    return a, (b.left, b.right, b.bottom, b.top)


def mask(dec=1):
    with rasterio.open(NLUM_MASK) as t:
        m = t.read(1) == 1
    return m[::dec, ::dec] if dec > 1 else m


def show_map(ax, arr, extent, cmap, norm=None, vmin=None, vmax=None, title=""):
    im = ax.imshow(arr, extent=extent, cmap=cmap, norm=norm, vmin=vmin, vmax=vmax,
                   interpolation="nearest")
    ax.set_title(title, pad=5, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    return im


def label(ssp):
    return ssp.replace("ssp", "SSP")


# --------------------------------------------------------------------------- #
# 6 - interannual CV
# --------------------------------------------------------------------------- #

def fig_cv_interannual():
    m = mask(DECIMATE)
    hist, ext = read(CV_DIR / "cv_interannual_historical_1985-2014.tif", DECIMATE)
    hist = np.where(m, hist, np.nan)

    panels = [("historical 1985-2014", hist)]
    for win in WINDOWS:
        for ssp in SSPS:
            a, _ = read(CV_DIR / ("cv_interannual_%s_%s.tif" % (ssp, win)), DECIMATE)
            panels.append(("%s  %s" % (label(ssp), win), np.where(m, a, np.nan)))

    # A shared scale set by the typical spread, not by the longest tail: one
    # panel's p98 would flatten every panel. The colourbar extends past it.
    vmax = float(np.ceil(np.median([np.nanpercentile(a, 90) for _, a in panels]) / 10) * 10)

    fig, axes = plt.subplots(3, 3, figsize=(12.6, 8.4))
    fig.subplots_adjust(hspace=0.08, wspace=0.02)
    im = None
    for ax, (title, arr) in zip(axes.ravel(), panels):
        im = show_map(ax, arr, ext, SEQ_BLUE, vmin=0, vmax=vmax,
                      title="%s\nmedian %.1f%%" % (title, np.nanmedian(arr)))
    cb = fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015, extend="max")
    cb.set_label("interannual CV of M' (%)", fontsize=9)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=2)

    fig.suptitle("Year-to-year variability of M' within each 30-year window, and "
                 "in the modelled historical period", fontsize=11, color=INK_2)
    dst = PLOT_DIR / "fig_06_cv_interannual.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# 7 - change in interannual CV
# --------------------------------------------------------------------------- #

def fig_cv_change():
    m = mask(DECIMATE)
    hist, ext = read(CV_DIR / "cv_interannual_historical_1985-2014.tif", DECIMATE)
    hist = np.where(m, hist, np.nan)

    fig, axes = plt.subplots(2, 4, figsize=(13.6, 5.9))
    fig.subplots_adjust(hspace=0.06, wspace=0.02)
    im = None
    for r, win in enumerate(WINDOWS):
        for c, ssp in enumerate(SSPS):
            a, _ = read(CV_DIR / ("cv_interannual_%s_%s.tif" % (ssp, win)), DECIMATE)
            d = np.where(m, a, np.nan) - hist
            im = show_map(axes[r, c], d, ext, DIVERGING,
                          norm=TwoSlopeNorm(vmin=-8, vcenter=0, vmax=8),
                          title="%s  %s\nmedian %+.1f pp"
                                % (label(ssp), win, np.nanmedian(d)))
    cb = fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015, extend="both")
    cb.set_label("change in interannual CV (percentage points)", fontsize=9)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=2)

    fig.suptitle("Does M' become more variable from year to year? "
                 "Future CV minus the modelled historical CV", fontsize=11, color=INK_2)
    dst = PLOT_DIR / "fig_07_cv_change.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# 8 - across-scenario CV
# --------------------------------------------------------------------------- #

def fig_cv_scenarios():
    m = mask(DECIMATE)
    cv = pd.read_csv(OUT_DIR / "cv_summary.csv")
    arrs, ext = [], None
    for win in WINDOWS:
        a, ext = read(CV_DIR / ("cv_across_scenarios_%s.tif" % win), DECIMATE)
        arrs.append(np.where(m, a, np.nan))
    vmax = float(np.ceil(max(np.nanpercentile(a, 90) for a in arrs) / 5) * 5)

    # The colourbar goes UNDER the maps, not beside them: to their right sits the
    # bar panel's category labels, and a vertical bar lands on top of them.
    fig = plt.figure(figsize=(13.4, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.05], wspace=0.5)
    map_axes = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1])]
    im = None
    for ax, win, a in zip(map_axes, WINDOWS, arrs):
        im = show_map(ax, a, ext, SEQ_BLUE, vmin=0, vmax=vmax,
                      title="%s\nmedian %.1f%%" % (win, np.nanmedian(a)))
    cb = fig.colorbar(im, ax=map_axes, orientation="horizontal",
                      fraction=0.055, pad=0.04, extend="max")
    cb.set_label("CV of window-mean M' across the four SSPs (%)", fontsize=9)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=2)

    ax = tidy(fig.add_subplot(gs[2]), grid_axis="x")
    inter = cv[cv["kind"] == "interannual"]
    scen = cv[cv["kind"] == "across_scenarios"]
    names = ["interannual\n(historical)", "interannual\n(future, mean of 8)",
             "across scenarios\n2035-2064", "across scenarios\n2070-2099"]
    vals = [float(inter[inter["layer"].str.startswith("historical")]["median"].iloc[0]),
            float(inter[~inter["layer"].str.startswith("historical")]["median"].mean()),
            float(scen[scen["layer"] == "2035-2064"]["median"].iloc[0]),
            float(scen[scen["layer"] == "2070-2099"]["median"].iloc[0])]
    colors = [HIST_C, "#2a78d6", "#6da7ec", "#256abf"]
    y = np.arange(len(names))[::-1]
    ax.barh(y, vals, color=colors, height=0.62)
    for yi, v in zip(y, vals):
        ax.text(v + 0.25, yi, "%.1f%%" % v, va="center", fontsize=9, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("median CV (%)")
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_title("Which uncertainty is larger?", loc="left")

    fig.suptitle("Disagreement between scenarios, against year-to-year variability "
                 "within one scenario", fontsize=11, color=INK_2)
    dst = PLOT_DIR / "fig_08_cv_across_scenarios.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# 9 - M' against New_M_2019
# --------------------------------------------------------------------------- #

def fig_scatter():
    df = pd.read_csv(OUT_DIR / ("comparison_vs_New_M_2019%s.csv"
                                % ("" if ORDER == "eq1_of_mean"
                                   else "_mean_of_annual")))
    df = df[df["ssp"] != "New_M_2019"].set_index(["ssp", "window"])
    base, _ = read(NEW_M, 2)
    m = mask(2)
    base = np.where(m, base, np.nan)

    rng = np.random.default_rng(42)
    fig, axes = plt.subplots(2, 4, figsize=(14.0, 7.0), sharex=True, sharey=True)
    hi = float(np.nanpercentile(base, 99.5))

    for r, win in enumerate(WINDOWS):
        for c, ssp in enumerate(SSPS):
            ax = axes[r, c]
            a, _ = read(window_mean_path(ssp, win), 2)
            a = np.where(m, a, np.nan)
            ok = np.isfinite(a) & np.isfinite(base)
            idx = rng.choice(int(ok.sum()), min(400_000, int(ok.sum())), replace=False)
            x, y = base[ok][idx], a[ok][idx]
            ax.hexbin(x, y, gridsize=70, cmap=SEQ_BLUE, mincnt=1,
                      extent=(0, hi, 0, hi), linewidths=0)
            ax.plot([0, hi], [0, hi], color=INK_MUTED, lw=1.2, ls="--")
            ax.set_xlim(0, hi)
            ax.set_ylim(0, hi)
            row = df.loc[(ssp, win)]
            ax.set_title("%s  %s" % (label(ssp), win), loc="left")
            ax.text(0.04, 0.93,
                    "r %.3f\nslope %.3f\nbias %+.1f\nRMSE %.1f"
                    % (row["pearson_r"], row["slope"], row["bias"], row["rmse"]),
                    transform=ax.transAxes, va="top", fontsize=8.5, color=INK_2,
                    linespacing=1.35)
            tidy(ax)

    for ax in axes[1]:
        ax.set_xlabel("New_M_2019 (t DM ha$^{-1}$)")
    for ax in axes[:, 0]:
        ax.set_ylabel("future M' (t DM ha$^{-1}$)")

    fig.suptitle("Future M' against New_M_2019, cell by cell. Points below the "
                 "dashed 1:1 line are cells that lose biomass", fontsize=11,
                 color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_09_scatter_vs_New_M_2019.png"
    fig.savefig(dst, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# 10 - national totals
# --------------------------------------------------------------------------- #

def fig_totals():
    df = pd.read_csv(OUT_DIR / ("comparison_vs_New_M_2019%s.csv"
                                % ("" if ORDER == "eq1_of_mean"
                                   else "_mean_of_annual")))
    ref = df[df["ssp"] == "New_M_2019"]["total_Mt_DM"].iloc[0]
    d = df[df["ssp"] != "New_M_2019"].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.6))

    x = np.arange(len(WINDOWS))
    w = 0.2
    for i, ssp in enumerate(SSPS):
        vals = [float(d[(d["ssp"] == ssp) & (d["window"] == win)]["total_Mt_DM"].iloc[0])
                for win in WINDOWS]
        pos = x + (i - 1.5) * (w + 0.015)
        ax1.bar(pos, vals, w, color=SSP_C[ssp], label=label(ssp))
        # Label inside the bar: above it the labels run into the baseline rule.
        for p, v in zip(pos, vals):
            ax1.text(p, v - ref * 0.03, label(ssp)[3:], ha="center", va="top",
                     fontsize=8.5, color="white")
    ax1.axhline(ref, color=INK, lw=1.4, ls="--", zorder=3)
    ax1.text(-0.42, ref + ref * 0.015, "New_M_2019  %.0f Mt DM" % ref,
             va="bottom", ha="left", fontsize=9, color=INK)
    ax1.set_xticks(x)
    ax1.set_xticklabels(WINDOWS)
    ax1.set_ylabel("national total above-ground biomass (Mt DM)")
    ax1.set_ylim(0, max(d["total_Mt_DM"].max(), ref) * 1.12)
    ax1.set_title("a  Area-weighted national total", loc="left")
    tidy(ax1, grid_axis="y")

    for ssp in SSPS:
        vals = [float(d[(d["ssp"] == ssp) & (d["window"] == win)]["total_pct_change"].iloc[0])
                for win in WINDOWS]
        ax2.plot(x, vals, "-o", color=SSP_C[ssp], lw=2, ms=6, label=label(ssp))
        ax2.text(x[-1] + 0.04, vals[-1], " " + label(ssp), va="center", fontsize=9,
                 color=INK_2)
    ax2.axhline(0, color=INK_MUTED, lw=1.1)
    ax2.set_xticks(x)
    ax2.set_xticklabels(WINDOWS)
    ax2.set_xlim(-0.25, len(WINDOWS) - 0.45)
    ax2.set_ylabel("change in the national total (%)")
    ax2.set_title("b  Change against New_M_2019", loc="left")
    tidy(ax2, grid_axis="y")

    fig.suptitle("The national carrying capacity implied by each scenario-window",
                 fontsize=11, color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_10_totals.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# 11 - change by baseline decile
# --------------------------------------------------------------------------- #

def fig_decile():
    d = pd.read_csv(OUT_DIR / ("change_by_baseline_decile%s.csv"
                               % ("" if ORDER == "eq1_of_mean"
                                  else "_mean_of_annual")))

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), sharey=True)
    for ax, win in zip(axes, WINDOWS):
        sub = d[d["window"] == win]
        for ssp in SSPS:
            s = sub[sub["ssp"] == ssp].sort_values("decile")
            ax.plot(s["decile"], s["pct_change_median"], "-o", color=SSP_C[ssp],
                    lw=2, ms=5, label=label(ssp))
        ax.axhline(0, color=INK_MUTED, lw=1.1)
        ax.set_xticks(range(1, 11))
        ax.set_xlim(0.6, 10.4)
        ax.set_xlabel("decile of New_M_2019 (1 = lowest biomass)")
        ax.set_title(win, loc="left")
        tidy(ax, grid_axis="y")
    # A legend rather than end-of-line labels: the four lines converge in the
    # top deciles and the labels land on top of one another there.
    axes[0].legend(fontsize=9, loc="lower right", ncol=2)
    axes[0].set_ylabel("median change in M' (%)")

    fig.suptitle("Where the change sits: in relative terms the loss is deepest in "
                 "the low- and mid-biomass deciles, shallowest in the top decile",
                 fontsize=11, color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_11_change_by_decile.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--order", choices=["eq1_of_mean", "mean_of_annual"],
                    default="eq1_of_mean")
    args = ap.parse_args()
    global ORDER
    ORDER = args.order

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = {"6": fig_cv_interannual, "7": fig_cv_change, "8": fig_cv_scenarios,
            "9": fig_scatter, "10": fig_totals, "11": fig_decile}
    for k in (args.only or list(jobs)):
        print("building figure %s ..." % k, flush=True)
        print("  -> %s" % jobs[k]().name)
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
