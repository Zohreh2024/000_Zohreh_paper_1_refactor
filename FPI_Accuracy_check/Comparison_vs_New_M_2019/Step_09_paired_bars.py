"""
Step 09 - the paired-bar view: two footings per scenario-window, one reference line.

The layout follows the figure supplied as the target: a hatched baseline group on
the left, then one pair of bars per scenario-window, a dashed horizontal
reference line across the whole panel, and the value printed above every bar.

What the two series are here
----------------------------
orange   Eq. (1) M from the projected FPI, `M = (6.011 sqrt(FPI) - 5.291)^2`,
         used as written. This is the ORIGINAL (Eq. 1) footing, and it is not
         the layer FullCAM ships: Eq. (1) overstates `Original_M_2004` by a
         median factor of about 1.46.

navy     M' on the matched footing, `lambda x Original_M_2004 x Eq1(FPI_fut) /
         Eq1(FPI_hist)`, with both sides of the ratio modelled by the random
         forest. This is what this folder's comparison is about.

baseline The same two quantities for 1985-2014: Eq. (1) M from the modelled
         historical FPI, and M' for the historical period - which is
         `New_M_2019` exactly, by construction. Hatched, because they are a
         reference rather than a projection.

line     the median of `New_M_2019` over the same cells.

Read the figure in two directions. Vertically, the gap between the orange and
navy bar of a pair is the footing question - it is a level difference of roughly
1.6x that has nothing to do with climate. Horizontally, the movement of the navy
bars away from the dashed line is the projected change, and it is the only part
of the picture that is a climate signal.

All medians are taken over the NLUM mask, on the same cells, and cached to
`output/paired_bar_medians.csv` so the figure and any text quoting it agree.

Writes  plots/fig_12_paired_bars.png (+ .pdf)
        output/paired_bar_medians.csv

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_09_paired_bars.py
    ... --stat mean          # the same figure on means rather than medians
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
EQ1_M_DIR = ROOT / "Calculation_future_M_CSIRO" / "output"
HIST_EQ1 = PARENT / "output" / "Eq1_M_histRF_mean_of_annual.tif"
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
EQ1_C = "#eb6834"        # categorical slot 2
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
             series="Eq1 M (Eq. 1 footing)", stat=stat,
             value=stat_of(HIST_EQ1, valid, stat),
             source=HIST_EQ1.name),
        dict(group="1985-2014\nbaseline", ssp="baseline", window="1985-2014",
             series="M' (matched footing)", stat=stat,
             value=stat_of(NEW_M, valid, stat), source=NEW_M.name),
    ]
    for win in WINDOWS:
        for ssp in SSPS:
            eq1 = EQ1_M_DIR / ("M_%s_%s_mean.tif" % (ssp, win))
            mp = (MPRIME_OFMEAN / ("maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win))
                  if ORDER == "eq1_of_mean"
                  else MPRIME_ANNUAL / ("maxAbgMF_%s_%s_mean.tif" % (ssp, win)))
            g = "%s\n%s" % (SSP_LABEL[ssp], win)
            if eq1.exists():
                rows.append(dict(group=g, ssp=ssp, window=win,
                                 series="Eq1 M (Eq. 1 footing)", stat=stat,
                                 value=stat_of(eq1, valid, stat), source=eq1.name))
            if mp.exists():
                rows.append(dict(group=g, ssp=ssp, window=win,
                                 series="M' (matched footing)", stat=stat,
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
    series = "M' (matched footing)"
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
               label="New_M_2019 reference, %.2f t DM ha$^{-1}$" % ref)
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

    fig.suptitle("Future M' with every component modelled by the random forest, "
                 "against the historical baseline it is built on",
                 fontsize=10.5, color=INK_2, y=0.99)
    # These percentages are the shift in the median, which is NOT the median of
    # the per-cell changes reported elsewhere (a median is not additive). Both
    # are correct; they answer different questions, so the figure says which.
    fig.text(0.01, 0.015,
             "Percentages are the change in the median M', i.e. median(M') "
             "against median(New_M_2019). The median of the per-cell changes is "
             "a different statistic and is the one tabulated in "
             "comparison_vs_New_M_2019.csv.",
             fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.035, 1, 0.94))
    dst = PLOT_DIR / "fig_13_rf_mprime_bars.png"
    fig.savefig(dst, dpi=200)
    fig.savefig(dst.with_suffix(".pdf"))
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stat", choices=["median", "mean"], default="median")
    ap.add_argument("--mode", choices=["rf_only", "footings", "both"],
                    default="both",
                    help="rf_only: one bar per window, the random forest's M' "
                         "(fig_13). footings: Eq.(1) M beside it (fig_12)")
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

    if args.mode in ("rf_only", "both"):
        print(plot_rf_only(df, ref, args.stat, groups))
    if args.mode == "rf_only":
        return
    x = np.arange(len(groups))
    w = 0.38

    fig, ax = plt.subplots(figsize=(13.2, 5.6))
    for i, (series, color) in enumerate([("Eq1 M (Eq. 1 footing)", EQ1_C),
                                         ("M' (matched footing)", MP_C)]):
        vals = [float(df[(df["group"] == g) & (df["series"] == series)]["value"].iloc[0])
                for g in groups]
        pos = x + (i - 0.5) * (w + 0.02)
        hatch = ["//" if g.startswith("1985") else "" for g in groups]
        bars = ax.bar(pos, vals, w, color=color, label=series, zorder=2)
        for b, h in zip(bars, hatch):
            if h:
                b.set_hatch(h)
                b.set_facecolor(SURFACE)
                b.set_edgecolor(color)
                b.set_linewidth(1.6)
        # A surface-coloured halo: several bars top out within a tonne or two of
        # the reference line, and the label would otherwise sit on it.
        for p, v in zip(pos, vals):
            ax.text(p, v + ref * 0.025, "%.0f" % v, ha="center", va="bottom",
                    fontsize=9.5, fontweight="bold", color=color, zorder=4,
                    path_effects=[pe.withStroke(linewidth=3.2, foreground=SURFACE)])

    ax.axhline(ref, color=REF_C, lw=1.8, ls="--", zorder=1,
               label="New_M_2019 reference, %.2f" % ref)
    ax.axvline(0.5, color=GRID_C, lw=1.4, zorder=0)

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=9)
    ax.set_ylabel("%s M across land cells  (t DM ha$^{-1}$)"
                  % ("median" if args.stat == "median" else "mean"))
    ax.set_ylim(0, max(df["value"]) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, axis="y", lw=0.6, alpha=0.9)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=3, fontsize=9.5)

    fig.suptitle("Two footings, one reference: the vertical gap is the footing, "
                 "the movement away from the dashed line is the climate signal",
                 fontsize=10.5, color=INK_2, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dst = PLOT_DIR / "fig_12_paired_bars.png"
    fig.savefig(dst, dpi=200)
    fig.savefig(dst.with_suffix(".pdf"))
    plt.close(fig)
    print("\n%s\n%s" % (dst, dst.with_suffix(".pdf")))


if __name__ == "__main__":
    main()
