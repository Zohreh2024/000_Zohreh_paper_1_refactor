"""
Step 09 - the headline bar chart: median M' by scenario-window.

A hatched baseline bar on the left, then one bar per scenario-window, a dashed
reference line across the panel at the median of Revised_M_Roxburgh, and the
value above every bar with the percent change inside it.

The comparison the figure invites is horizontal: each bar against the hatched
baseline and the dashed reference, both of which are Revised_M_Roxburgh.

Writes  plots/fig_13_rf_mprime_bars.png (+ .pdf)
        output/paired_bar_medians.csv

Run
---
    conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_09_paired_bars.py
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
import matplotlib.patheffects as pe                            # noqa: E402
import matplotlib.pyplot as plt                                # noqa: E402
import rasterio                                                # noqa: E402

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent
OUT_DIR = HERE / "output"
PLOT_DIR = HERE / "plots"
MPRIME_ANNUAL = PARENT / "output_Mprime_rf" / "mean_of_annual"
MPRIME_OFMEAN = PARENT / "output_Mprime_rf" / "eq1_of_mean"
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019_NLUM.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

ORDER = "eq1_of_mean"        # the method: Eq.(1) of the window-mean FPI
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
SSP_LABEL = {"ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5",
             "ssp370": "SSP3-7.0", "ssp585": "SSP5-8.5"}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID_C = "#e4e3df"
MP_C = "#1b3a5c"         # deep navy, >= 3:1 on this surface
REF_C = "#2f3a45"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": GRID_C, "grid.color": GRID_C,
    "font.size": 10, "axes.titlesize": 11, "legend.frameon": False,
})


def mask():
    with rasterio.open(NLUM_MASK) as t:
        return t.read(1) == 1


def stat_of(path, valid, stat):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
    v = a[valid & np.isfinite(a)]
    return float(np.median(v)) if stat == "median" else float(v.mean())


def gather(valid, stat, force):
    dst = OUT_DIR / "paired_bar_medians.csv"
    if dst.exists() and not force:
        df = pd.read_csv(dst)
        if df["stat"].iloc[0] == stat:
            return df

    rows = [
        dict(group="1985-2014\nbaseline", ssp="baseline", window="1985-2014",
             series="M'", stat=stat,
             value=stat_of(NEW_M, valid, stat), source=NEW_M.name),
    ]
    for win in WINDOWS:
        for ssp in SSPS:
            mp = (MPRIME_OFMEAN / ("maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win))
                  if ORDER == "eq1_of_mean"
                  else MPRIME_ANNUAL / ("maxAbgMF_%s_%s_mean.tif" % (ssp, win)))
            g = "%s\n%s" % (SSP_LABEL[ssp], win)
            if mp.exists():
                rows.append(dict(group=g, ssp=ssp, window=win,
                                 series="M'", stat=stat,
                                 value=stat_of(mp, valid, stat), source=mp.name))
            print("  %s %s done" % (ssp, win), flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(dst, index=False)
    return df


def plot_rf_only(df, ref, stat, groups):
    """One bar per scenario-window: the new M', every component from the forest.

    No second series. The comparison the figure invites is horizontal - each
    bar against the hatched baseline and the dashed reference, both of which are
    New_M_2019 - so the percent change is printed inside the bar rather than
    left to the reader's arithmetic.
    """
    series = "M'"
    vals = [float(df[(df["group"] == g) & (df["series"] == series)]["value"].iloc[0])
            for g in groups]

    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(12.6, 5.4))

    bars = ax.bar(x, vals, 0.62, color=MP_C, zorder=2,
                  label="M' from the random forest (both sides of the ratio)")
    bars[0].set_facecolor(SURFACE)
    bars[0].set_edgecolor(MP_C)
    bars[0].set_linewidth(1.6)
    bars[0].set_hatch("//")

    for xi, v in zip(x, vals):
        ax.text(xi, v + ref * 0.022, "%.1f" % v, ha="center", va="bottom",
                fontsize=10.5, fontweight="bold", color=MP_C, zorder=4,
                path_effects=[pe.withStroke(linewidth=3.2, foreground=SURFACE)])
    for xi, v in list(zip(x, vals))[1:]:
        ax.text(xi, v - ref * 0.045, "%+.0f%%" % (100 * (v - ref) / ref),
                ha="center", va="top", fontsize=9, color="white", zorder=4)

    ax.axhline(ref, color=REF_C, lw=1.8, ls="--", zorder=1,
               label="Revised_M_Roxburgh reference, %.2f t DM ha$^{-1}$" % ref)
    ax.axvline(0.5, color=GRID_C, lw=1.4, zorder=0)

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=9)
    ax.set_ylabel("%s M' across land cells  (t DM ha$^{-1}$)"
                  % ("median" if stat == "median" else "mean"))
    ax.set_ylim(0, max(vals) * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, axis="y", lw=0.6, alpha=0.9)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, fontsize=9.5)

    fig.suptitle("Median future M' against the 1985-2014 baseline",
                 fontsize=11, color=INK_2, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dst = PLOT_DIR / "fig_13_rf_mprime_bars.png"
    fig.savefig(dst, dpi=200)
    fig.savefig(dst.with_suffix(".pdf"))
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stat", choices=["median", "mean"], default="median")
    ap.add_argument("--order", choices=["eq1_of_mean", "mean_of_annual"],
                    default="eq1_of_mean")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    global ORDER
    ORDER = args.order

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    valid = mask()

    df = gather(valid, args.stat, args.force)
    ref = float(df[(df["ssp"] == "baseline") &
                   (df["series"].str.startswith("M'"))]["value"].iloc[0])

    groups = ["1985-2014\nbaseline"] + ["%s\n%s" % (SSP_LABEL[s], w)
                                        for w in WINDOWS for s in SSPS]

    print(plot_rf_only(df, ref, args.stat, groups))


if __name__ == "__main__":
    main()
