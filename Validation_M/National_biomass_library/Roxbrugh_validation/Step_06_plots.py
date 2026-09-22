"""
Step 06 - the figures.

Roxburgh's own figures, redrawn on our layers and our sample, plus two that his
paper does not need and this one does: the walk over sample decisions, and the
plot-size artefact that drives it.

    fig_01a..c  observed against predicted, one file per layer    (his Fig. 4)
    fig_02a     model efficiency by layer, with intervals         (his Table 4)
    fig_02b     Lin's concordance by layer, with intervals        (his Table 4)
    fig_03      frequency distributions against the observations  (his Fig. 6b)
    fig_04a     mean biomass by state, Forest                     (his Fig. 8)
    fig_04b     mean biomass by state, Woodland                   (his Fig. 8)
    fig_05      spatial autocorrelation of the residual           (his Sec. 2.4)
    fig_06      what each sample decision does to the agreement
    fig_07      reported biomass against plot size

Axes are LINEAR everywhere. Roxburgh draws Figs. 3 and 4 on log10 axes and
computes the statistics on untransformed data; we keep his statistics and drop
his axes, because a log axis straightens a relationship that the reader should
see as it is. Where a quantity spans orders of magnitude the axis stops just
above the bulk of the data and the few points beyond are clipped, with the count
stated on the panel.

Reads   outputs/*.csv
Writes  plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_06_plots.py
"""

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
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID_C = "#e4e3df"
C_OBS = "#52514e"
C_ORIG = "#eda100"
C_REV = "#2a78d6"
C_FUT = "#eb6834"
C_OK = "#1baf7a"
C_BAD = "#e34948"

# Roxburgh et al. (2019) Table 4, his own scores for the two layers he scored.
ROX = {"M_original_2004": dict(EF=0.14, LCC=0.25, ME=-35.3, RMSE=239.1),
       "M_revised_Roxburgh": dict(EF=0.40, LCC=0.62, ME=-8.0, RMSE=200.7)}

NICE = {
    "M_original_2004": "Original M (FullCAM before 2019)",
    "M_revised_Roxburgh": "Revised_M_Roxburgh (New_M_2019)",
    "M_eq1_rf_hist": "Eq. (1) on modelled historical FPI",
}


def nice(layer):
    if layer in NICE:
        return NICE[layer]
    if layer.startswith("M_future_"):
        ssp, win = layer[len("M_future_"):].split("_")
        return "Future M, %s %s" % (ssp.upper(), win)
    return layer


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


def fig_scatter(d, stats, layer, panel):
    """Observed against predicted, Roxburgh's Fig. 4 on linear axes."""
    obs = d["agb"].to_numpy(float)
    pred = d[layer].to_numpy(float)
    g = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[g], pred[g]
    hi = float(np.percentile(np.concatenate([obs, pred]), 98))
    clipped = int(((obs > hi) | (pred > hi)).sum())

    fig, ax = plt.subplots(figsize=(6.4, 5.8))
    tidy(ax)
    hb = ax.hexbin(obs, pred, gridsize=55, cmap="Blues", mincnt=1,
                   extent=(0, hi, 0, hi), linewidths=0)
    counts = hb.get_array()
    if len(counts[counts > 0]):
        hb.set_clim(0, float(np.percentile(counts[counts > 0], 98)))
    cb = fig.colorbar(hb, ax=ax, fraction=0.045, pad=0.02)
    cb.set_label("records per cell", fontsize=9, color=INK_2)
    cb.ax.tick_params(labelsize=8, colors=INK_2)

    ax.plot([0, hi], [0, hi], color="#333333", lw=1.1, ls="--", zorder=4)
    ax.set(xlim=(0, hi), ylim=(0, hi))
    ax.set_xlabel("observed above-ground biomass (t DM ha$^{-1}$)")
    ax.set_ylabel("modelled maximum biomass (t DM ha$^{-1}$)")
    ax.set_title("%s) %s" % (panel, nice(layer)), loc="left")

    r = stats.set_index("layer").loc[layer]
    txt = ("n = %s\nME    %+.1f t DM ha$^{-1}$\nRMSE  %.1f\nEF    %.2f\n"
           "LCC   %.2f" % (format(int(r["n"]), ","), r["ME"], r["RMSE"],
                           r["EF"], r["LCC"]))
    if layer in ROX:
        txt += ("\n\nRoxburgh's own:\nEF %.2f, LCC %.2f"
                % (ROX[layer]["EF"], ROX[layer]["LCC"]))
    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left",
            fontsize=8.6, color=INK_2, family="monospace",
            bbox=dict(boxstyle="round,pad=0.45", fc=SURFACE, ec="#d8d7d3",
                      lw=0.7))
    if clipped:
        ax.text(0.98, 0.02, "%d records beyond the axis" % clipped,
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
                color=INK_2)
    dst = PLOT_DIR / ("fig_01%s_observed_vs_%s.png" % (panel, layer))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_stat_bars(stats, stat, panel, title):
    d = stats.copy()
    d["label"] = [nice(c) for c in d["layer"]]
    y = np.arange(len(d))[::-1]
    lo = d[stat + "_lo"].to_numpy()
    hi = d[stat + "_hi"].to_numpy()
    mid = d[stat].to_numpy()

    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    tidy(ax, grid_axis="x")
    colours = [C_OK if v > 0 else C_BAD for v in mid]
    ax.barh(y, mid, color=colours, height=0.62, zorder=3)
    ax.errorbar(mid, y, xerr=[mid - lo, hi - mid], fmt="none", ecolor=INK_2,
                elinewidth=1.1, capsize=3, zorder=4)
    ax.axvline(0, color="#333333", lw=1.0, zorder=5)

    for layer, yi in zip(d["layer"], y):
        if layer in ROX:
            ax.scatter([ROX[layer][stat]], [yi], marker="D", s=46,
                       color="#0b0b0b", zorder=6,
                       label="Roxburgh's published value"
                       if layer == "M_revised_Roxburgh" else None)

    ax.set_yticks(y)
    ax.set_yticklabels(d["label"], fontsize=8.8)
    ax.set_xlabel({"EF": "model efficiency (1 is perfect, 0 is no better "
                         "than the mean of the observations)",
                   "LCC": "Lin's concordance correlation coefficient "
                          "(agreement with the 1:1 line)"}[stat])
    ax.set_title("%s) %s" % (panel, title), loc="left")
    ax.legend(fontsize=8.5, frameon=False, loc="upper right",
              bbox_to_anchor=(1.0, -0.12))
    dst = PLOT_DIR / ("fig_02%s_%s_by_layer.png" % (panel, stat.lower()))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_distributions(d, ks):
    shown = ["M_original_2004", "M_revised_Roxburgh",
             "M_future_ssp585_2070-2099"]
    shown = [c for c in shown if c in d.columns]
    hi = float(np.percentile(d["agb"], 97))
    bins = np.linspace(0, hi, 46)

    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    tidy(ax, grid_axis="y")
    ax.hist(np.clip(d["agb"], 0, hi), bins=bins, density=True, color=C_OBS,
            alpha=0.35, label="observed biomass", zorder=2)
    for c, col in zip(shown, [C_ORIG, C_REV, C_FUT]):
        ax.hist(np.clip(d[c], 0, hi), bins=bins, density=True, histtype="step",
                lw=2.0, color=col, label=nice(c), zorder=3)

    ax.set_xlabel("above-ground biomass (t DM ha$^{-1}$)")
    ax.set_ylabel("relative frequency")
    ax.set_title("Distribution of modelled maximum biomass against the "
                 "observations", loc="left")
    ax.legend(fontsize=8.8, frameon=False)
    k = ks.set_index("layer")
    note = "  ".join("%s D = %.2f" % (nice(c).split(" (")[0], k.loc[c, "ks_statistic"])
                     for c in shown if c in k.index)
    ax.text(0.99, 0.55, "Kolmogorov-Smirnov\n" + note.replace("  ", "\n"),
            transform=ax.transAxes, ha="right", va="top", fontsize=8.2,
            color=INK_2, bbox=dict(boxstyle="round,pad=0.4", fc=SURFACE,
                                   ec="#d8d7d3", lw=0.7))
    dst = PLOT_DIR / "fig_03_distributions.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_state_means(ms, cls, panel):
    d = ms[(ms["veg_class"] == cls) & (ms["state"] != "ALL")].copy()
    d = d.sort_values("n", ascending=False)
    if d.empty:
        return None
    series = [("observed", "observed biomass", C_OBS),
              ("M_original_2004", "Original M", C_ORIG),
              ("M_revised_Roxburgh", "Revised_M_Roxburgh", C_REV),
              ("M_future_ssp585_2070-2099", "Future M, SSP585 2070-2099", C_FUT)]
    series = [s for s in series if s[0] in d.columns]
    x = np.arange(len(d))
    w = 0.8 / len(series)

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    tidy(ax, grid_axis="y")
    for k, (col, lab, colour) in enumerate(series):
        ax.bar(x + k * w - 0.4 + w / 2, d[col], w * 0.9, color=colour,
               label=lab, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(["%s\nn = %d" % (s, n)
                        for s, n in zip(d["state"], d["n"])], fontsize=8.8)
    ax.set_ylabel("mean above-ground biomass (t DM ha$^{-1}$)")
    ax.set_title("%s) Mean biomass by state, %s sites" % (panel, cls),
                 loc="left")
    ax.legend(fontsize=8.5, frameon=False, ncol=2)
    dst = PLOT_DIR / ("fig_04%s_state_means_%s.png" % (panel, cls.lower()))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_correlogram(cg):
    d = cg.copy()
    mid = np.sqrt(d["lo_km"].clip(lower=0.5) * d["hi_km"])
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    tidy(ax)
    ax.plot(mid, d["correlation"], "-o", color=C_REV, lw=2.0, ms=7,
            markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=4)
    ax.axhline(0.2, color=C_BAD, lw=1.2, ls="--", zorder=3)
    ax.text(mid.iloc[-1], 0.2, " Roxburgh's 0.2 threshold", va="bottom",
            ha="right", fontsize=8.5, color=C_BAD)
    ax.axhline(0, color="#333333", lw=1.0, zorder=3)
    ax.set_xscale("log")      # distance only; the correlation axis is linear
    ax.set_xlabel("separation between plots (km)")
    ax.set_ylabel("correlation of the residual, observed minus modelled")
    ax.set_title("How far apart two plots must be before their errors are "
                 "independent", loc="left")
    dst = PLOT_DIR / "fig_05_spatial_autocorrelation.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_sensitivity(ss, layer="M_revised_Roxburgh"):
    d = ss[ss["layer"] == layer].copy()
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(9.8, 6.0))
    tidy(ax, grid_axis="x")
    colours = [C_OK if v > 0.2 else C_BAD for v in d["spearman_rho"]]
    ax.barh(y, d["spearman_rho"], color=colours, height=0.62, zorder=3)
    ax.axvline(0, color="#333333", lw=1.0, zorder=5)
    for yi, v, n in zip(y, d["spearman_rho"], d["n"]):
        ax.text(v + (0.012 if v >= 0 else -0.012), yi, "%+.2f  (n = %s)"
                % (v, format(int(n), ",")), va="center",
                ha="left" if v >= 0 else "right", fontsize=8.2, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels(d["variant"], fontsize=8.5)
    ax.set_xlabel("Spearman rank correlation between observed biomass and "
                  "Revised_M_Roxburgh")
    ax.set_title("What each sample decision does to the agreement", loc="left")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 0.12, hi + 0.16)
    dst = PLOT_DIR / "fig_06_sample_sensitivity.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_plot_size(d):
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    tidy(ax)
    bands = [(0, 0.05), (0.05, 0.15), (0.15, 0.3), (0.3, 0.45), (0.45, 1e3)]
    labels = ["up to\n0.05 ha", "0.05 to\n0.15 ha", "0.15 to\n0.3 ha",
              "0.3 to\n0.45 ha", "above\n0.45 ha"]
    med, n = [], []
    for lo, hi in bands:
        s = d[(d["area_ha"] > lo) & (d["area_ha"] <= hi)]
        med.append(float(s["agb"].median()) if len(s) else np.nan)
        n.append(len(s))
    x = np.arange(len(bands))
    ax.bar(x, med, 0.6, color=C_BAD, zorder=3)
    for xi, v, ni in zip(x, med, n):
        ax.annotate("%.0f\nn = %s" % (v, format(ni, ",")), (xi, v),
                    xytext=(0, 4), textcoords="offset points", ha="center",
                    fontsize=8.5, color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.8)
    ax.set_ylabel("median reported biomass (t DM ha$^{-1}$)")
    ax.set_title("Reported biomass per hectare against the size of the plot "
                 "it was measured in", loc="left")
    dst = PLOT_DIR / "fig_07_plot_size.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default="records.csv")
    args = ap.parse_args()

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    suf = args.records[len("records"):-len(".csv")]
    d = pd.read_csv(OUT_DIR / args.records, low_memory=False)
    stats = pd.read_csv(OUT_DIR / ("fit_statistics%s.csv" % suf))
    ks = pd.read_csv(OUT_DIR / ("ks_tests%s.csv" % suf))
    ms = pd.read_csv(OUT_DIR / ("means_by_state_class%s.csv" % suf))
    cg = pd.read_csv(OUT_DIR / ("spatial_autocorrelation%s.csv" % suf))
    ss = pd.read_csv(OUT_DIR / "sample_sensitivity.csv")

    made = []
    for panel, layer in zip("abc", ["M_original_2004", "M_revised_Roxburgh",
                                    "M_future_ssp585_2070-2099"]):
        if layer in d.columns:
            made.append(fig_scatter(d, stats, layer, panel))
    made.append(fig_stat_bars(stats, "EF", "a",
                              "Model efficiency of every layer"))
    made.append(fig_stat_bars(stats, "LCC", "b",
                              "Lin's concordance of every layer"))
    made.append(fig_distributions(d, ks))
    for panel, cls in zip("ab", ["Forest", "Woodland"]):
        made.append(fig_state_means(ms, cls, panel))
    made.append(fig_correlogram(cg))
    made.append(fig_sensitivity(ss))
    made.append(fig_plot_size(d))

    for p in made:
        print("  -> %s" % (p.name if p else "skipped"))
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
