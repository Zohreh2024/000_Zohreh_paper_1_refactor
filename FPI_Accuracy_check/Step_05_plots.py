"""
Step 05 - the report figures.

Reads the CSVs the earlier steps wrote and the rasters they produced; recomputes
no metric, so a figure cannot disagree with the pipeline. The one number
computed here is Option B's change against `New_M_2019`, which no earlier step
wrote; it is cached to `output/optionB_pct_change.csv` so the report and the
figure read the same value.

Writes  plots/fig_01_accuracy.png
        plots/fig_02_hist_fpi_maps.png
        plots/fig_03_denominator.png
        plots/fig_04_mprime_change.png
        plots/fig_05_mprime_change_maps.png
        output/optionB_pct_change.csv

Colour, deliberately
--------------------
Magnitude (FPI, M') is a one-hue blue ramp, light to dark. Anything centred on a
meaningful zero - a difference, a ratio against 1, a percent change - is a
diverging blue/red pair with a neutral grey midpoint, symmetric about that
centre, so "no change" reads as nothing and the two directions are never
confusable. Series colours are a fixed categorical order, assigned by entity and
never by rank: blue is always the observed denominator, orange always the
modelled one, across every panel of every figure.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_05_plots.py
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
ROOT = HERE.parent
OUT_DIR = HERE / "output"
PLOT_DIR = HERE / "plots"
MPRIME_DIR = HERE / "output_Mprime_rf"
OPTION_B = ROOT / "Option_B_matched_footing" / "output_Mprime"
OBS_FPI_DIR = ROOT / "Random_forest_CSIRO" / "required_data" / "fpi"
LAMBDA = ROOT / "Step_02_published_lambda" / "output" / "lambda_published.tif"
ORIGINAL_M = ROOT / "Step_02_published_lambda" / "output" / "original_M_2004.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
DECIMATE = 4                     # every 4th row/col for the map panels
PER_YEAR_POINTS = 60_000         # cells drawn per year for the hexbin

# --- palette --------------------------------------------------------------- #
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8a85"
OBS_C = "#2a78d6"                # categorical slot 1 - observed denominator
MOD_C = "#eb6834"                # categorical slot 2 - modelled denominator
GRID_C = "#e4e3df"

SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list("blue_red", [
    "#0d366b", "#256abf", "#86b6ef", "#f0efec", "#ec8a89", "#d03b3b", "#7d1f1f"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2,
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
    ax.set_title(title, pad=6)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    return im


# --------------------------------------------------------------------------- #
# Figure 1 - accuracy
# --------------------------------------------------------------------------- #

def fig_accuracy(sample_years):
    """Modelled against observed FPI, and accuracy year by year.

    Every one of the 30 years is plotted, subsampled to keep the hexbin
    tractable. An earlier version drew five hand-picked years under a title
    carrying the pooled 30-year statistics, so the caption and the cloud
    described different samples; they now describe the same one.
    """
    by_year = pd.read_csv(OUT_DIR / "accuracy_by_year.csv")
    oof = pd.read_csv(OUT_DIR / "oof_accuracy_by_year.csv")
    summary = pd.read_csv(OUT_DIR / "accuracy_summary.csv").set_index("scheme")

    rng = np.random.default_rng(42)
    obs, mod = [], []
    for y in sample_years:        # all 30 historical years
        o, _ = read(OBS_FPI_DIR / ("fpi_%d.tif" % y))
        m, _ = read(OUT_DIR / ("fpi_rf_%d.tif" % y))
        ok = np.isfinite(o) & np.isfinite(m)
        idx = rng.choice(int(ok.sum()), PER_YEAR_POINTS, replace=False)
        obs.append(o[ok][idx])
        mod.append(m[ok][idx])
    obs, mod = np.concatenate(obs), np.concatenate(mod)

    # Two standalone figures rather than one two-panel figure: they are read
    # separately and each is easier to place on its own.
    fig1, ax1 = plt.subplots(figsize=(6.2, 4.8))
    fig2, ax2 = plt.subplots(figsize=(6.2, 4.8))

    hi = float(np.percentile(np.concatenate([obs, mod]), 99.5))
    ax1.hexbin(obs, mod, gridsize=80, cmap=SEQ_BLUE, mincnt=1,
               extent=(0, hi, 0, hi), linewidths=0)
    ax1.plot([0, hi], [0, hi], color=INK_MUTED, lw=1.4, ls="--", zorder=3)
    ax1.text(hi * 0.80, hi * 0.72, "1:1", color=INK_MUTED, ha="left", va="top",
             fontsize=9)
    ax1.set_xlim(0, hi)
    ax1.set_ylim(0, hi)
    ax1.set_xlabel("observed FPI, DCCEEW 1 km layer (dimensionless)")
    ax1.set_ylabel("modelled FPI, random forest (dimensionless)")
    ins = summary.loc["in_sample_full_grid"]
    ax1.set_title("a) Modelled against observed FPI, %d-%d"
                  % (min(sample_years), max(sample_years)), loc="left")
    tidy(ax1)

    ax2.plot(by_year["year"], by_year["r2"], "-o", color=OBS_C, lw=2, ms=4.5,
             label="in sample")
    ax2.plot(oof["year"], oof["r2"], "-s", color=MOD_C, lw=2, ms=4.5,
             label="out of fold")
    ax2.set_ylim(0.88, 1.0)
    ax2.set_xlabel("year")
    ax2.set_ylabel("R$^2$ of modelled against observed FPI")
    ax2.set_title("b) Accuracy by year", loc="left")
    ax2.legend(loc="lower left", fontsize=9)
    tidy(ax2, grid_axis="y")

    out = []
    for fig, ax, name in [(fig1, ax1, "fig_01a_modelled_vs_observed"),
                          (fig2, ax2, "fig_01b_accuracy_by_year")]:
        fig.tight_layout()
        dst = PLOT_DIR / (name + ".png")
        fig.savefig(dst, dpi=200)
        plt.close(fig)
        out.append(dst)
    return out[0]


# --------------------------------------------------------------------------- #
# Figure 2 - the historical FPI maps
# --------------------------------------------------------------------------- #

def fig_hist_maps():
    obs, ext = read(OUT_DIR / "fpi_obs_1985-2014_mean.tif", DECIMATE)
    mod, _ = read(OUT_DIR / "fpi_rf_1985-2014_mean_masked.tif", DECIMATE)
    m = mask(DECIMATE)
    obs = np.where(m, obs, np.nan)
    mod = np.where(m, mod, np.nan)
    diff = mod - obs

    hi = float(np.nanpercentile(obs, 99))
    lim = float(np.nanpercentile(np.abs(diff), 99))

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.6))
    im0 = show_map(axes[0], obs, ext, SEQ_BLUE, vmin=0, vmax=hi,
                   title="a) Observed mean FPI")
    im1 = show_map(axes[1], mod, ext, SEQ_BLUE, vmin=0, vmax=hi,
                   title="b) Modelled mean FPI")
    im2 = show_map(axes[2], diff, ext, DIVERGING,
                   norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim),
                   title="c) Modelled minus observed")

    for im, ax, lab in [(im0, axes[0], "FPI"), (im1, axes[1], "FPI"),
                        (im2, axes[2], "FPI difference")]:
        cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
        cb.set_label(lab, fontsize=8.5)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=8, length=2)

    med = float(np.nanmedian(diff))
    fig.suptitle("Mean Forest Productivity Index, 1985-2014",
                 fontsize=11, y=1.0, color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_hist_fpi_maps.png"
    fig.savefig(dst, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #
# Figure 3 - the denominator
# --------------------------------------------------------------------------- #

def fig_denominator():
    """Three standalone figures about the historical denominator of M′.

    Separate files rather than one three-panel figure: the titles have to say
    what each quantity is, and at that length they collide in one row.
    """
    comp = pd.read_csv(OUT_DIR / "hist_M_denominator_comparison.csv")

    def med(label):
        row = comp[comp["comparison"].str.startswith(label)]
        return float(row["median"].iloc[0])

    rf, ext = read(OUT_DIR / "Eq1_M_histRF_mean_of_annual.tif", DECIMATE)
    ob, _ = read(OUT_DIR / "Eq1_M_histOBS_mean_of_annual.tif", DECIMATE)
    rf_m, _ = read(OUT_DIR / "Eq1_M_histRF_eq1_of_mean.tif", DECIMATE)
    ob_m, _ = read(OUT_DIR / "Eq1_M_histOBS_eq1_of_mean.tif", DECIMATE)
    m = mask(DECIMATE)

    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(m & (ob > 0), rf / ob, np.nan)
        r_annual = ratio[np.isfinite(ratio)]
        r_ofmean = (rf_m / ob_m)[m & np.isfinite(rf_m) & np.isfinite(ob_m) & (ob_m > 0)]
        jensen = (rf / rf_m)[m & np.isfinite(rf) & np.isfinite(rf_m) & (rf_m > 0)]

    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    im = show_map(ax, ratio, ext, DIVERGING,
                  norm=TwoSlopeNorm(vmin=0.8, vcenter=1.0, vmax=1.2),
                  title="a) Historical M: modelled FPI $\div$ observed FPI")
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03, extend="both")
    cb.set_label("ratio", fontsize=8.5)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=2)
    fig.tight_layout()
    a_path = PLOT_DIR / "fig_03a_denominator_map.png"
    fig.savefig(a_path, dpi=190, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    bins = np.linspace(0.6, 1.4, 90)
    ax.hist(r_annual, bins=bins, color=MOD_C, alpha=0.85,
            label="per-year order: mean$_y$[Eq1(FPI$_y$)]")
    ax.hist(r_ofmean, bins=bins, histtype="step", lw=2, color=OBS_C,
            label="mean-FPI order: Eq1(mean$_y$ FPI$_y$)")
    ax.axvline(1.0, color=INK_MUTED, lw=1.2, ls="--")
    ax.set_xlabel("Eq1(FPI modelled) / Eq1(FPI observed), 1985-2014")
    ax.set_ylabel("number of 1 km cells")
    ax.set_yticklabels([])
    ax.set_title("b) Distribution of that ratio", loc="left")
    ax.legend(fontsize=9, loc="upper left")
    tidy(ax, grid_axis="y")
    fig.tight_layout()
    b_path = PLOT_DIR / "fig_03b_denominator_ratio.png"
    fig.savefig(b_path, dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    ax.hist(jensen, bins=np.linspace(1.0, 1.4, 90), color=MOD_C, alpha=0.85)
    ax.axvline(1.0, color=INK_MUTED, lw=1.2, ls="--")
    ax.axvline(med("RF: mean_of_annual"), color=INK, lw=1.4)
    ax.text(med("RF: mean_of_annual") + 0.008, ax.get_ylim()[1] * 0.88,
            "median %.4f" % med("RF: mean_of_annual"), fontsize=9, color=INK)
    ax.set_xlabel("mean$_y$[Eq1(FPI$_y$)] / Eq1(mean$_y$ FPI$_y$), same 30 modelled layers")
    ax.set_ylabel("number of 1 km cells")
    ax.set_yticklabels([])
    ax.set_title("c) Averaging-order ratio, same layers", loc="left")
    tidy(ax, grid_axis="y")
    fig.tight_layout()
    c_path = PLOT_DIR / "fig_03c_averaging_order.png"
    fig.savefig(c_path, dpi=190)
    plt.close(fig)
    return a_path


# --------------------------------------------------------------------------- #
# Figure 4 - what it does to M'
# --------------------------------------------------------------------------- #

def option_b_change(valid, force=False):
    """Option B's median change against New_M_2019, per layer. Cached."""
    dst = OUT_DIR / "optionB_pct_change.csv"
    if dst.exists() and not force:
        return pd.read_csv(dst)

    lam, _ = read(LAMBDA)
    orig, _ = read(ORIGINAL_M)
    base = lam.astype("float64") * orig.astype("float64")

    rows = []
    for ssp in SSPS:
        for win in WINDOWS:
            for order, stem in [("mean_of_annual", "maxAbgMF_%s_%s_mean.tif" % (ssp, win)),
                                ("eq1_of_mean", "maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win))]:
                p = OPTION_B / stem
                if not p.exists():
                    continue
                a, _ = read(p)
                ok = valid & np.isfinite(a) & np.isfinite(base) & (base > 0)
                pct = 100 * (a[ok].astype("float64") - base[ok]) / base[ok]
                rows.append(dict(ssp=ssp, window=win, averaging_order=order,
                                 layer=stem,
                                 pct_change_vs_New_M_2019_median=float(np.median(pct))))
    df = pd.DataFrame(rows)
    df.to_csv(dst, index=False)
    return df


def fig_mprime_change(valid):
    mod = pd.read_csv(OUT_DIR / "Mprime_modelled_vs_observed_denominator.csv")
    obs = option_b_change(valid)

    key = ["ssp", "window", "averaging_order"]
    df = obs.merge(mod, on=key, suffixes=("_obs", "_mod"))
    df["label"] = df["ssp"].str.replace("ssp", "SSP") + "\n" + df["window"]

    figs = [plt.subplots(figsize=(7.4, 4.9)) for _ in range(2)]
    axes = [a for _, a in figs]
    titles = {
        "eq1_of_mean": "a) M′ = New_M_2019 x Eq1(mean FPI$_{future}$) $\div$ Eq1(mean FPI$_{1985-2014}$)",
        "mean_of_annual": "b) M′ = New_M_2019 x mean$_y$[Eq1(FPI$_y$)] $\div$ mean$_y$[Eq1(FPI$_y$, hist)]",
    }
    for ax, order in zip(axes, ["eq1_of_mean", "mean_of_annual"]):
        d = df[df["averaging_order"] == order].sort_values(["window", "ssp"])
        x = np.arange(len(d))
        w = 0.38
        ax.bar(x - w / 2 - 0.01, d["pct_change_vs_New_M_2019_median_obs"], w,
               color=OBS_C, label="observed historical FPI (DCCEEW download)")
        ax.bar(x + w / 2 + 0.01, d["pct_change_vs_New_M_2019_median_mod"], w,
               color=MOD_C, label="modelled historical FPI (random forest)")
        ax.axhline(0, color=INK_MUTED, lw=1.1)
        ax.set_xticks(x)
        ax.set_xticklabels(d["label"], fontsize=8.5)
        ax.set_title(titles[order], loc="left")
        tidy(ax, grid_axis="y")
        for xi, v in zip(x + w / 2 + 0.01, d["pct_change_vs_New_M_2019_median_mod"]):
            ax.text(xi, v - 0.9, "%.0f" % v, ha="center", va="top",
                    fontsize=8, color=INK_2)

    lo = min(df["pct_change_vs_New_M_2019_median_mod"].min(),
             df["pct_change_vs_New_M_2019_median_obs"].min())
    hi = max(2.5, df["pct_change_vs_New_M_2019_median_obs"].max() + 1)
    out = []
    for (fig, ax), name in zip(figs, ["fig_04a_mprime_change_method",
                                      "fig_04b_mprime_change_sensitivity"]):
        ax.set_ylim(lo - 4.5, hi)
        ax.set_ylabel("median change in M′ against New_M_2019 (%)")
        ax.legend(loc="lower left", fontsize=9)
        fig.suptitle("Change in future M′ against New_M_2019",
                     fontsize=11, color=INK_2, y=1.0)
        fig.tight_layout()
        dst = PLOT_DIR / (name + ".png")
        fig.savefig(dst, dpi=200, bbox_inches="tight")
        plt.close(fig)
        out.append(dst)
    return out[0]


# --------------------------------------------------------------------------- #
# Figure 5 - where the change is
# --------------------------------------------------------------------------- #

def fig_change_maps():
    lam, ext = read(LAMBDA, DECIMATE)
    orig, _ = read(ORIGINAL_M, DECIMATE)
    m = mask(DECIMATE)
    base = np.where(m, lam.astype("float64") * orig.astype("float64"), np.nan)

    fig, axes = plt.subplots(2, 4, figsize=(13.6, 5.9))
    fig.subplots_adjust(hspace=0.06, wspace=0.02)
    im = None
    for r, win in enumerate(WINDOWS):
        for c, ssp in enumerate(SSPS):
            p = MPRIME_DIR / "mean_of_annual" / ("maxAbgMF_%s_%s_mean.tif" % (ssp, win))
            ax = axes[r, c]
            if not p.exists():
                ax.axis("off")
                continue
            a, _ = read(p, DECIMATE)
            with np.errstate(invalid="ignore", divide="ignore"):
                pct = np.where(np.isfinite(base) & (base > 0),
                               100 * (a - base) / base, np.nan)
            im = show_map(ax, pct, ext, DIVERGING,
                          norm=TwoSlopeNorm(vmin=-60, vcenter=0, vmax=60),
                          title="%s  %s" % (ssp.replace("ssp", "SSP"), win))

    if im is not None:
        cb = fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015, extend="both")
        cb.set_label("change in M' against New_M_2019 (%)", fontsize=9)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=8, length=2)

    fig.suptitle("Change in M' against New_M_2019, per cell",
                 fontsize=11, color=INK_2)
    dst = PLOT_DIR / "fig_05_mprime_change_maps.png"
    fig.savefig(dst, dpi=190, bbox_inches="tight")
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None,
                    help="figure numbers to build, e.g. --only 1 4")
    ap.add_argument("--force", action="store_true",
                    help="recompute Option B's change instead of using the cache")
    args = ap.parse_args()

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    valid = mask()

    if args.force:
        option_b_change(valid, force=True)

    jobs = {
        "1": lambda: fig_accuracy(list(range(1985, 2015))),
        "2": fig_hist_maps,
        "3": fig_denominator,
        "4": lambda: fig_mprime_change(valid),
        "5": fig_change_maps,
    }
    wanted = args.only or list(jobs)
    for k in wanted:
        print("building figure %s ..." % k, flush=True)
        print("  -> %s" % jobs[k]().name)

    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
