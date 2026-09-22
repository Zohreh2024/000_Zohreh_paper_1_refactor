"""
Step 06 - the figures.

The subject of this folder is the EIGHT FUTURE M' layers. Original M and
Revised_M_Roxburgh appear only as controls: they are the two layers Roxburgh
scored himself, so reproducing his ordering on them is what proves the protocol
was transplanted correctly before it is applied to anything new. The figures are
laid out to say that - two small control panels, and every other figure carrying
all eight future layers.

    fig_01a/b   CONTROL: observed against predicted for the two layers
                Roxburgh scored, with his own values printed  (his Fig. 4)
    fig_02      the eight future layers, same panel, same axes (his Fig. 4)
    fig_03a/b   model efficiency and Lin's concordance, every layer (his Table 4)
    fig_04      lambda = M / O per layer, his Eq. (2) - the quantity his whole
                method is built on
    fig_05      frequency distributions, observed against all eight (his Fig. 6b)
    fig_06a/b   mean biomass by state, Forest and Woodland, with all eight
                future layers shown against the observed and the anchor
                (his Fig. 8)
    fig_07      spatial autocorrelation of the residual            (his Sec. 2.4)
    fig_08      what each sample decision does to the agreement
    fig_09      reported biomass against plot size

Axes are LINEAR everywhere. Roxburgh draws Figs. 3 and 4 on log10 axes and
computes the statistics on untransformed data; we keep his statistics and drop
his axes, because a log axis straightens a relationship that the reader should
see as it is. Where a quantity spans orders of magnitude the axis stops just
above the bulk of the data and the few points beyond are clipped, with the count
stated on the panel. fig_04 is the one exception and says so on its own axis:
lambda spans four orders of magnitude and is shown as quantiles, not as a cloud.

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

# One colour per scenario, kept for every figure so a reader learns it once.
SSP_COLOUR = {"ssp126": "#2a78d6", "ssp245": "#1baf7a",
              "ssp370": "#eda100", "ssp585": "#e34948"}
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]

CONTROLS = ["M_original_2004", "M_revised_Roxburgh"]
ANCHOR = "M_revised_Roxburgh"
# Eq. (1) on the modelled historical FPI is neither: it is the
# alternative historical footing, kept for reference.
OTHER = ["M_eq1_rf_hist"]
C_CTL = "#b9b8b4"
C_OTHER = "#8fa9c4"

# Roxburgh et al. (2019) Table 4, his own scores for the two layers he scored.
ROX = {"M_original_2004": dict(EF=0.14, LCC=0.25, ME=-35.3, RMSE=239.1),
       "M_revised_Roxburgh": dict(EF=0.40, LCC=0.62, ME=-8.0, RMSE=200.7)}

NICE = {
    "M_original_2004": "Original M (FullCAM before 2019)",
    "M_revised_Roxburgh": "Revised_M_Roxburgh (New_M_2019)",
    "M_eq1_rf_hist": "Eq. (1) on modelled historical FPI",
}


def layer_colour(layer):
    if layer in CONTROLS:
        return C_CTL
    if layer in OTHER:
        return C_OTHER
    return C_FUT


def future_layers(columns):
    """The eight future layers, in scenario then window order."""
    out = []
    for w in WINDOWS:
        for s in SSPS:
            c = "M_future_%s_%s" % (s, w)
            if c in columns:
                out.append(c)
    return out


def nice(layer):
    if layer in NICE:
        return NICE[layer]
    if layer.startswith("M_future_"):
        ssp, win = layer[len("M_future_"):].split("_")
        return "%s %s" % (ssp.upper(), win)
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


def hex_panel(ax, obs, pred, hi):
    hb = ax.hexbin(obs, pred, gridsize=45, cmap="Blues", mincnt=1,
                   extent=(0, hi, 0, hi), linewidths=0)
    counts = np.asarray(hb.get_array())
    pos = counts[counts > 0]
    if len(pos):
        hb.set_clim(0, float(np.percentile(pos, 98)))
    ax.plot([0, hi], [0, hi], color="#333333", lw=1.0, ls="--", zorder=4)
    ax.set(xlim=(0, hi), ylim=(0, hi))
    return hb


# --------------------------------------------------------------------------- #
# The controls
# --------------------------------------------------------------------------- #

def fig_control(d, stats, layer, panel):
    """Roxburgh's Fig. 4 for a layer he scored himself, on linear axes."""
    obs = d["agb"].to_numpy(float)
    pred = d[layer].to_numpy(float)
    g = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[g], pred[g]
    hi = float(np.percentile(np.concatenate([obs, pred]), 98))
    clipped = int(((obs > hi) | (pred > hi)).sum())

    fig, ax = plt.subplots(figsize=(6.4, 5.8))
    tidy(ax)
    hb = hex_panel(ax, obs, pred, hi)
    cb = fig.colorbar(hb, ax=ax, fraction=0.045, pad=0.02)
    cb.set_label("records per cell", fontsize=9, color=INK_2)
    cb.ax.tick_params(labelsize=8, colors=INK_2)

    ax.set_xlabel("observed above-ground biomass (t DM ha$^{-1}$)")
    ax.set_ylabel("modelled maximum biomass (t DM ha$^{-1}$)")
    ax.set_title("%s) Control: %s" % (panel, nice(layer)), loc="left")

    r = stats.set_index("layer").loc[layer]
    txt = ("n = %s\nME    %+.1f t DM ha$^{-1}$\nRMSE  %.1f\nEF    %.2f\n"
           "LCC   %.2f" % (format(int(r["n"]), ","), r["ME"], r["RMSE"],
                           r["EF"], r["LCC"]))
    if layer in ROX:
        txt += ("\n\nRoxburgh's own, on his\n5,739 records:\nEF %.2f, LCC %.2f"
                % (ROX[layer]["EF"], ROX[layer]["LCC"]))
    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left",
            fontsize=8.6, color=INK_2, family="monospace",
            bbox=dict(boxstyle="round,pad=0.45", fc=SURFACE, ec="#d8d7d3",
                      lw=0.7))
    if clipped:
        ax.text(0.98, 0.02, "%d records beyond the axis" % clipped,
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
                color=INK_2)
    dst = PLOT_DIR / ("fig_01%s_control_%s.png" % (panel, layer))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# The subject: all eight future layers
# --------------------------------------------------------------------------- #

def fig_future_scatter(d, stats):
    """The eight future layers on one set of shared axes.

    Eight separate files would show eight near-identical clouds and invite the
    reader to compare them by flipping pages. They belong on one grid, on the
    same axes, where the comparison is immediate - and where the fact that they
    are near-identical is itself the result.
    """
    layers = future_layers(d.columns)
    if not layers:
        return None
    obs_all = d["agb"].to_numpy(float)
    hi = float(np.percentile(
        np.concatenate([obs_all] + [d[c].to_numpy(float) for c in layers]), 98))

    S = stats.set_index("layer")
    fig, axes = plt.subplots(2, 4, figsize=(15.2, 7.8), sharex=True,
                             sharey=True)
    hb = None
    for ax, layer in zip(axes.ravel(), layers):
        tidy(ax)
        obs = d["agb"].to_numpy(float)
        pred = d[layer].to_numpy(float)
        g = np.isfinite(obs) & np.isfinite(pred)
        hb = hex_panel(ax, obs[g], pred[g], hi)
        ssp = layer[len("M_future_"):].split("_")[0]
        ax.set_title(nice(layer), loc="left", fontsize=10.5,
                     color=SSP_COLOUR.get(ssp, INK))
        r = S.loc[layer]
        ax.text(0.04, 0.96, "ME %+.0f\nEF %.2f\nLCC %.2f"
                % (r["ME"], r["EF"], r["LCC"]),
                transform=ax.transAxes, va="top", ha="left", fontsize=8.4,
                color=INK_2, family="monospace",
                bbox=dict(boxstyle="round,pad=0.35", fc=SURFACE, ec="#d8d7d3",
                          lw=0.6))
    for ax in axes[-1]:
        ax.set_xlabel("observed biomass (t DM ha$^{-1}$)")
    for ax in axes[:, 0]:
        ax.set_ylabel("projected maximum biomass (t DM ha$^{-1}$)")
    if hb is not None:
        cb = fig.colorbar(hb, ax=axes, fraction=0.018, pad=0.012)
        cb.set_label("records per cell", fontsize=9, color=INK_2)
        cb.ax.tick_params(labelsize=8, colors=INK_2)
    fig.suptitle("The eight future M layers against observed biomass, on "
                 "shared axes", x=0.09, ha="left", fontsize=12.5)
    dst = PLOT_DIR / "fig_02_future_scatter_all.png"
    fig.savefig(dst, dpi=190)
    plt.close(fig)
    return dst


def fig_stat_bars(stats, stat, panel, title):
    d = stats.copy()
    d["label"] = [nice(c) for c in d["layer"]]
    y = np.arange(len(d))[::-1]
    lo = d[stat + "_lo"].to_numpy()
    hi = d[stat + "_hi"].to_numpy()
    mid = d[stat].to_numpy()
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    tidy(ax, grid_axis="x")
    colours = [layer_colour(c) for c in d["layer"]]
    ax.barh(y, mid, color=colours, height=0.62, zorder=3)
    ax.errorbar(mid, y, xerr=[mid - lo, hi - mid], fmt="none", ecolor=INK_2,
                elinewidth=1.1, capsize=3, zorder=4)
    ax.axvline(0, color="#333333", lw=1.0, zorder=5)

    for layer, yi in zip(d["layer"], y):
        if layer in ROX:
            ax.scatter([ROX[layer][stat]], [yi], marker="D", s=46,
                       color="#0b0b0b", zorder=6,
                       label="Roxburgh's published value"
                       if layer == ANCHOR else None)

    ax.set_yticks(y)
    ax.set_yticklabels(d["label"], fontsize=8.8)
    ax.set_xlabel({"EF": "model efficiency (1 is perfect, 0 is no better "
                         "than the mean of the observations)",
                   "LCC": "Lin's concordance correlation coefficient "
                          "(agreement with the 1:1 line)"}[stat])
    ax.set_title("%s) %s" % (panel, title), loc="left")
    handles, labels = ax.get_legend_handles_labels()
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=C_FUT), Patch(facecolor=C_CTL),
               Patch(facecolor=C_OTHER)] + handles
    labels = ["future M (the subject)", "present-day control",
              "Eq. (1) footing, for reference"] + labels
    ax.legend(handles, labels, fontsize=8.5, frameon=False, ncol=4,
              loc="upper right", bbox_to_anchor=(1.0, -0.13))
    dst = PLOT_DIR / ("fig_03%s_%s_all_layers.png" % (panel, stat.lower()))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_lambda(lam):
    """Roxburgh's Eq. (2), lambda = M / O, per layer.

    His entire method is a model of this ratio, so its distribution is the most
    direct statement any of these layers makes about the observations: lambda
    above 1 means the layer sits above the measured biomass, which is the
    direction a MAXIMUM should err in, and lambda below 1 means it sits under a
    stand that has already been measured carrying more.

    Shown as quantiles rather than a cloud. Lambda spans four orders of
    magnitude here - a plot measured at 0.3 t DM/ha under a cell modelled at 300
    gives 1000 - so a scatter would be unreadable and a log axis would hide the
    asymmetry. The bar is the interquartile range, the marker the median, the
    thin line the 5th to 95th percentile, and the axis is clipped with the p95
    printed where it falls outside.
    """
    d = lam.copy()
    d["label"] = [nice(c) for c in d["layer"]]
    y = np.arange(len(d))[::-1]
    is_ctl = d["layer"].isin(CONTROLS).to_numpy()
    hi = float(np.nanpercentile(d["p75"], 100)) * 1.6

    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    tidy(ax, grid_axis="x")
    for yi, (_, r) in zip(y, d.iterrows()):
        colour = layer_colour(r["layer"])
        ax.plot([r["p05"], min(r["p95"], hi)], [yi, yi], color=colour, lw=1.4,
                alpha=0.75, zorder=3)
        ax.barh(yi, r["p75"] - r["p25"], left=r["p25"], height=0.5,
                color=colour, zorder=4)
        ax.plot([r["median"]], [yi], marker="o", ms=7, color=SURFACE,
                markeredgecolor="#0b0b0b", markeredgewidth=1.6, zorder=6)
        if r["p95"] > hi:
            ax.annotate("p95 %.0f" % r["p95"], (hi, yi), xytext=(-4, 0),
                        textcoords="offset points", ha="right", va="center",
                        fontsize=7.6, color=INK_2)
        ax.annotate("%.2f" % r["median"], (r["median"], yi), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=7.8,
                    color=INK_2)

    ax.axvline(1.0, color="#333333", lw=1.2, ls="--", zorder=5)
    ax.annotate("lambda = 1" + '\\n' + "the layer equals" + '\\n' + "the measured biomass",
                (1.0, -0.9), xytext=(6, 0), textcoords="offset points",
                fontsize=8.2, color=INK_2, va="center", ha="left",
                annotation_clip=False)
    ax.set_xlim(0, hi)
    ax.set_yticks(y)
    ax.set_yticklabels(d["label"], fontsize=8.8)
    ax.set_xlabel("lambda = modelled maximum / observed biomass  "
                  "(Roxburgh Eq. 2)")
    ax.set_title("The ratio Roxburgh's method is built on, per layer", loc="left")
    from matplotlib.patches import Patch
    ax.legend([Patch(facecolor=C_FUT), Patch(facecolor=C_CTL),
               Patch(facecolor=C_OTHER)],
              ["future M (the subject)", "present-day control",
               "Eq. (1) footing, for reference"],
              fontsize=8.5, frameon=False, ncol=3, loc="upper right",
              bbox_to_anchor=(1.0, -0.16))
    dst = PLOT_DIR / "fig_04_lambda_by_layer.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_distributions(d, ks):
    layers = future_layers(d.columns)
    hi = float(np.percentile(d["agb"], 97))
    bins = np.linspace(0, hi, 46)

    fig, ax = plt.subplots(figsize=(10.2, 5.4))
    tidy(ax, grid_axis="y")
    ax.hist(np.clip(d["agb"], 0, hi), bins=bins, density=True, color=C_OBS,
            alpha=0.32, label="observed biomass", zorder=2)
    if ANCHOR in d.columns:
        ax.hist(np.clip(d[ANCHOR], 0, hi), bins=bins, density=True,
                histtype="step", lw=2.4, color="#6b6a66",
                label="Revised_M_Roxburgh (the anchor)", zorder=3)
    for c in layers:
        ssp, win = c[len("M_future_"):].split("_")
        ax.hist(np.clip(d[c], 0, hi), bins=bins, density=True, histtype="step",
                lw=1.7, color=SSP_COLOUR[ssp],
                ls="-" if win == WINDOWS[0] else "--",
                label="%s %s" % (ssp.upper(), win), zorder=4)

    ax.set_xlabel("above-ground biomass (t DM ha$^{-1}$)")
    ax.set_ylabel("relative frequency")
    ax.set_title("Distribution of every future M layer against the "
                 "observations", loc="left")
    ax.legend(fontsize=8.2, frameon=False, ncol=2)
    k = ks.set_index("layer")
    lo_ks = min(k.loc[c, "ks_statistic"] for c in layers)
    hi_ks = max(k.loc[c, "ks_statistic"] for c in layers)
    ax.text(0.99, 0.62, "Kolmogorov-Smirnov against\nthe observations:\n"
            "future layers D = %.2f to %.2f\nanchor D = %.2f"
            % (lo_ks, hi_ks, k.loc[ANCHOR, "ks_statistic"]),
            transform=ax.transAxes, ha="right", va="top", fontsize=8.2,
            color=INK_2, bbox=dict(boxstyle="round,pad=0.4", fc=SURFACE,
                                   ec="#d8d7d3", lw=0.7))
    dst = PLOT_DIR / "fig_05_distributions_future.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_state_means(ms, cls, panel):
    """Roxburgh's Fig. 8, with all eight future layers rather than a sample.

    Observed and the anchor are bars, because they are the two reference
    quantities. The eight future layers are points over the anchor's bar, so
    their spread against it is read vertically without eight more bars per
    state.
    """
    d = ms[(ms["veg_class"] == cls) & (ms["state"] != "ALL")].copy()
    d = d.sort_values("n", ascending=False)
    if d.empty:
        return None
    layers = future_layers(d.columns)
    x = np.arange(len(d))
    w = 0.34

    fig, ax = plt.subplots(figsize=(10.2, 5.4))
    tidy(ax, grid_axis="y")
    ax.bar(x - w / 2, d["observed"], w * 0.92, color=C_OBS,
           label="observed biomass", zorder=3)
    if ANCHOR in d.columns:
        ax.bar(x + w / 2, d[ANCHOR], w * 0.92, color="#b9b8b4",
               label="Revised_M_Roxburgh (the anchor)", zorder=3)

    seen = set()
    for c in layers:
        ssp, win = c[len("M_future_"):].split("_")
        lab = ssp.upper() if ssp not in seen else None
        seen.add(ssp)
        ax.scatter(x + w / 2, d[c], s=26, color=SSP_COLOUR[ssp],
                   marker="o" if win == WINDOWS[0] else "^",
                   edgecolor=SURFACE, linewidth=0.8, zorder=6, label=lab)

    ax.set_xticks(x)
    ax.set_xticklabels(["%s\nn = %d" % (s, n)
                        for s, n in zip(d["state"], d["n"])], fontsize=8.8)
    ax.set_ylabel("mean above-ground biomass (t DM ha$^{-1}$)")
    ax.set_title("%s) Mean biomass by state, %s sites - observed, the anchor, "
                 "and all eight future layers" % (panel, cls), loc="left")
    ax.legend(fontsize=8.2, frameon=False, ncol=3, loc="upper left")
    ax.text(0.995, -0.16, "circles 2035-2064, triangles 2070-2099",
            transform=ax.transAxes, ha="right", fontsize=8, color=INK_2)
    dst = PLOT_DIR / ("fig_06%s_state_means_%s.png" % (panel, cls.lower()))
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# Why the test cannot resolve any of it
# --------------------------------------------------------------------------- #

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
    dst = PLOT_DIR / "fig_07_spatial_autocorrelation.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_sensitivity(ss, layer=ANCHOR):
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
    dst = PLOT_DIR / "fig_08_sample_sensitivity.png"
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
    dst = PLOT_DIR / "fig_09_plot_size.png"
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
    lam = pd.read_csv(OUT_DIR / ("lambda_summary%s.csv" % suf))

    made = [fig_control(d, stats, CONTROLS[0], "a"),
            fig_control(d, stats, CONTROLS[1], "b"),
            fig_future_scatter(d, stats),
            fig_stat_bars(stats, "EF", "a", "Model efficiency of every layer"),
            fig_stat_bars(stats, "LCC", "b",
                          "Lin's concordance of every layer"),
            fig_lambda(lam),
            fig_distributions(d, ks)]
    for panel, cls in zip("ab", ["Forest", "Woodland"]):
        made.append(fig_state_means(ms, cls, panel))
    made += [fig_correlogram(cg), fig_sensitivity(ss), fig_plot_size(d)]

    for p in made:
        print("  -> %s" % (p.name if p else "skipped"))
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
