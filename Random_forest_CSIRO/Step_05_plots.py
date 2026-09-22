"""
Validation and summary figures.

Reads   data/oof_*.npz, data/cv_metrics*.csv, data/feature_importances.csv,
        output/fpi_<ssp>_<year>.tif, required_data/fpi/fpi_<year>.tif
Writes  plots/scatter_cv.png            out-of-fold predicted vs observed FPI
        plots/cv_by_year.png            temporal-CV skill, year by year
        plots/feature_importance.png    top 25 predictors, soil vs climate
        plots/residual_map.png          mean out-of-fold residual in space
        plots/future_trajectory.png     domain-mean FPI 2035-2099, per SSP
        plots/future_change_maps.png    period mean vs the observed 1985-2014 mean
        plots/future_change_summary.csv

Every scatter is drawn from out-of-fold predictions - each point predicted by a
forest that did not train on it - so none of them is the final model scoring its
own training data. The `groupcv_year` panel is the one to read: it is the only
scheme that asks the question the projection asks.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray as rxr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA_DIR, FPI_DIR, HIST_YEARS, OUTPUT_DIR, PLOTS_DIR, SSPS,
                    nlum_template, regression_metrics)

SCHEMES = ["kfold_random", "blockcv_space", "groupcv_year"]
SCHEME_TITLES = {
    "kfold_random": "random 5-fold (optimistic)",
    "blockcv_space": "spatial block CV (unseen region)",
    "groupcv_year": "year-group CV (unseen year)",
}
PERIODS = ["2035-2064", "2070-2099"]
SSP_COLOURS = dict(zip(SSPS, ["#3B7EA1", "#5B8C5A", "#C77B30", "#B04A4A"]))


def _oof(scheme):
    p = DATA_DIR / f"oof_{scheme}.npz"
    return np.load(p) if p.exists() else None


def scatter_cv():
    have = [(s, _oof(s)) for s in SCHEMES]
    have = [(s, d) for s, d in have if d is not None]
    if not have:
        print("no out-of-fold files - run Step_03 first")
        return

    fig, axes = plt.subplots(1, len(have), figsize=(5.2 * len(have), 5.2), squeeze=False)
    for ax, (name, d) in zip(axes[0], have):
        t, p = d["y_true"], d["y_pred"]
        hi = float(np.nanpercentile(np.concatenate([t, p]), 99.9))
        m = regression_metrics(t, p)
        ax.hexbin(t, p, gridsize=110, bins="log", extent=(0, hi, 0, hi), cmap="viridis")
        ax.plot([0, hi], [0, hi], color="0.85", lw=1)
        ax.set(xlim=(0, hi), ylim=(0, hi), xlabel="observed FPI",
               ylabel="out-of-fold predicted FPI",
               title=f"{SCHEME_TITLES[name]}\n$R^2$={m['r2']:.3f}  "
                     f"RMSE={m['rmse']:.3f}  MAE={m['mae']:.3f}  "
                     f"bias={m['bias']:+.3f}")
        ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "scatter_cv.png", dpi=160)
    plt.close(fig)


def cv_by_year():
    path = DATA_DIR / "cv_metrics_by_year.csv"
    if not path.exists():
        return
    df = pd.read_csv(path).sort_values("year")
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    ax[0].bar(df["year"], df["r2"], color="#3B7EA1", width=0.75)
    ax[0].axhline(0, color="0.6", lw=0.8)
    ax[0].set(ylabel="$R^2$", xlabel="year",
              title="year-group CV: skill for each held-out year")
    ax[1].plot(df["year"], df["obs_mean"], "o-", color="0.3", label="observed")
    ax[1].plot(df["year"], df["pred_mean"], "s--", color="#C77B30",
               label="out-of-fold predicted")
    ax[1].set(ylabel="mean FPI", xlabel="year", title="annual mean, observed vs predicted")
    ax[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "cv_by_year.png", dpi=160)
    plt.close(fig)


def feature_importance():
    path = DATA_DIR / "feature_importances.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    top = df.head(25).iloc[::-1]
    colours = ["#8C6D3F" if k == "soil" else "#3B7EA1" for k in top["kind"]]
    fig, ax = plt.subplots(figsize=(7.5, 8.5))
    ax.barh(top["feature"], top["importance"], color=colours)
    tot = df.groupby("kind")["importance"].sum()
    ax.set(xlabel="impurity-based importance",
           title=f"top 25 predictors  (soil {tot.get('soil', 0):.2f} / "
                 f"climate {tot.get('climate', 0):.2f} of total)")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "feature_importance.png", dpi=160)
    plt.close(fig)


def residual_map():
    d = _oof("groupcv_year")
    if d is None:
        return
    tpl = nlum_template()
    res = d["y_pred"].astype(np.float64) - d["y_true"]
    idx = d["cell_row"].astype(np.int64) * tpl.sizes["x"] + d["cell_col"]
    n = tpl.sizes["y"] * tpl.sizes["x"]
    s = np.bincount(idx, weights=res, minlength=n)
    c = np.bincount(idx, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(c > 0, s / np.maximum(c, 1), np.nan)
    grid = mean.reshape(tpl.sizes["y"], tpl.sizes["x"])

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(grid, cmap="RdBu_r", vmin=-2, vmax=2, interpolation="nearest")
    ax.set(xticks=[], yticks=[],
           title="mean out-of-fold residual, year-group CV\n(predicted - observed FPI)")
    fig.colorbar(im, ax=ax, shrink=0.7, label="FPI")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "residual_map.png", dpi=160)
    plt.close(fig)


def observed_baseline():
    """Mean observed FPI over the 1985-2014 training window."""
    acc, n = None, 0
    for yr in HIST_YEARS:
        v = rxr.open_rasterio(FPI_DIR / f"fpi_{yr}.tif",
                              masked=True).squeeze(drop=True).values
        acc = v.astype(np.float64) if acc is None else acc + v
        n += 1
    return acc / n


def future_trajectory():
    rows = []
    for ssp in SSPS:
        for p in sorted(OUTPUT_DIR.glob(f"fpi_{ssp}_[0-9][0-9][0-9][0-9].tif")):
            v = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
            rows.append({"ssp": ssp, "year": int(p.stem.split("_")[-1]),
                         "mean": float(np.nanmean(v))})
    if not rows:
        print("no yearly predictions yet - run Step_04")
        return
    df = pd.DataFrame(rows).sort_values(["ssp", "year"])
    df.to_csv(OUTPUT_DIR / "domain_mean_fpi_by_year.csv", index=False)

    obs = [{"year": yr,
            "mean": float(np.nanmean(rxr.open_rasterio(
                FPI_DIR / f"fpi_{yr}.tif", masked=True).squeeze(drop=True).values))}
           for yr in HIST_YEARS]
    obs = pd.DataFrame(obs)

    fig, ax = plt.subplots(figsize=(11.5, 4.5))
    ax.plot(obs["year"], obs["mean"], color="0.35", lw=1.5, label="observed 1985-2014")
    for ssp, g in df.groupby("ssp"):
        # CSIRO separates the two windows deliberately; a single line through
        # the 2065-2069 gap would draw a trend across years that do not exist.
        for lo, hi in [(2035, 2064), (2070, 2099)]:
            w = g[(g["year"] >= lo) & (g["year"] <= hi)]
            ax.plot(w["year"], w["mean"], color=SSP_COLOURS[ssp], lw=1.2,
                    label=ssp if lo == 2035 else None)
    ax.set(xlabel="year", ylabel="domain-mean FPI",
           title="projected FPI, Australia-wide mean over land cells")
    ax.legend(frameon=False, ncol=5)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "future_trajectory.png", dpi=160)
    plt.close(fig)


def change_maps():
    paths = {(s, p): OUTPUT_DIR / f"fpi_{s}_{p}_mean.tif" for s in SSPS for p in PERIODS}
    paths = {k: v for k, v in paths.items() if v.exists()}
    if not paths:
        return
    baseline = observed_baseline()

    fig, axes = plt.subplots(len(PERIODS), len(SSPS),
                             figsize=(3.5 * len(SSPS), 3.4 * len(PERIODS)),
                             squeeze=False)
    rows, im = [], None
    for i, period in enumerate(PERIODS):
        for j, ssp in enumerate(SSPS):
            ax = axes[i][j]
            ax.set_xticks([]); ax.set_yticks([])
            if (ssp, period) not in paths:
                ax.axis("off")
                continue
            fut = rxr.open_rasterio(paths[(ssp, period)],
                                    masked=True).squeeze(drop=True).values
            diff = fut - baseline
            im = ax.imshow(diff, cmap="BrBG", vmin=-3, vmax=3, interpolation="nearest")
            ax.set_title(f"{ssp}  {period}", fontsize=9)
            rows.append({"ssp": ssp, "period": period,
                         "future_mean": float(np.nanmean(fut)),
                         "baseline_mean": float(np.nanmean(baseline)),
                         "change": float(np.nanmean(diff)),
                         "pct_change": float(100 * np.nanmean(diff)
                                             / np.nanmean(baseline))})
    if im is not None:
        fig.colorbar(im, ax=axes, shrink=0.6,
                     label="FPI change vs observed 1985-2014 mean")
    fig.savefig(PLOTS_DIR / "future_change_maps.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    df = pd.DataFrame(rows)
    df.to_csv(PLOTS_DIR / "future_change_summary.csv", index=False)
    print(df.round(3).to_string(index=False))


def scatter_future_vs_2022():
    """Projected 2035-2064 mean FPI against observed FPI in 2022, one panel per SSP.

    Read this as a displacement, not a validation. The left-hand axis is a
    30-year mean and the right-hand one is a single observed year, so the cloud
    is necessarily narrower vertically than horizontally: averaging thirty years
    removes interannual variance that 2022 still carries. Points below the 1:1
    line are cells the model puts below their 2022 value, and the useful signal
    is how that displacement varies with scenario and with FPI level, not the
    scatter width.

    2022 is also the last year in the FPI record and a wet La Nina year across
    much of eastern Australia, so it sits above the 1985-2014 norm to begin
    with. The dashed line is that observed 1985-2014 mean against 2022, which
    is the reference the projected offset should be judged against - the gap
    between the two clouds is the projected change, the gap between the dashed
    line and 1:1 is just how unusual 2022 was.
    """
    ref_path = FPI_DIR / "fpi_2022.tif"
    if not ref_path.exists():
        print("fpi_2022.tif not found - skipping the 2022 comparison")
        return
    paths = {s: OUTPUT_DIR / f"fpi_{s}_2035-2064_mean.tif" for s in SSPS}
    paths = {s: p for s, p in paths.items() if p.exists()}
    if not paths:
        print("no 2035-2064 mean rasters yet - run Step_04")
        return

    obs = rxr.open_rasterio(ref_path, masked=True).squeeze(drop=True).values
    baseline = observed_baseline()

    fig, axes = plt.subplots(1, len(paths), figsize=(4.9 * len(paths), 5.2),
                             squeeze=False)
    rows = []
    for ax, (ssp, p) in zip(axes[0], paths.items()):
        fut = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
        ok = np.isfinite(obs) & np.isfinite(fut)
        o, f = obs[ok], fut[ok]
        m = regression_metrics(o, f)
        # Ordinary least squares of projected on observed: the slope says
        # whether the projected change is uniform or concentrated at one end of
        # the productivity range.
        slope, intercept = np.polyfit(o, f, 1)
        hi = float(np.nanpercentile(np.concatenate([o, f]), 99.8))

        ax.hexbin(o, f, gridsize=110, bins="log", extent=(0, hi, 0, hi),
                  cmap="viridis")
        ax.plot([0, hi], [0, hi], color="0.85", lw=1.2)
        xs = np.linspace(0, hi, 50)
        ax.plot(xs, slope * xs + intercept, color="#C77B30", lw=1.4,
                label=f"fit: y = {slope:.3f}x {intercept:+.3f}")

        bok = np.isfinite(obs) & np.isfinite(baseline)
        bs, bi = np.polyfit(obs[bok], baseline[bok], 1)
        ax.plot(xs, bs * xs + bi, color="0.45", lw=1.2, ls="--",
                label="observed 1985-2014 mean vs 2022")

        ax.set(xlim=(0, hi), ylim=(0, hi), xlabel="observed FPI 2022",
               ylabel="projected mean FPI 2035-2064",
               title=f"{ssp}\nmean {f.mean():.2f} vs {o.mean():.2f}  "
                     f"({100 * (f.mean() - o.mean()) / o.mean():+.1f}%)  "
                     f"$R^2$={m['r2']:.3f}")
        ax.set_aspect("equal")
        ax.legend(frameon=False, fontsize=8, loc="upper left")

        rows.append({"ssp": ssp, "n_cells": int(ok.sum()),
                     "fpi_2022_mean": float(o.mean()),
                     "future_2035_2064_mean": float(f.mean()),
                     "change": float(f.mean() - o.mean()),
                     "pct_change": float(100 * (f.mean() - o.mean()) / o.mean()),
                     "slope": float(slope), "intercept": float(intercept),
                     "r2": m["r2"], "pearson_r": m["pearson_r"],
                     "rmse": m["rmse"], "mae": m["mae"]})

    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "scatter_future_vs_fpi2022.png", dpi=160)
    plt.close(fig)

    df = pd.DataFrame(rows)
    df.to_csv(PLOTS_DIR / "future_vs_fpi2022_summary.csv", index=False)
    print(df.round(3).to_string(index=False))

    # The same comparison as a map, since a scatter cannot show where the
    # displacement sits.
    fig, axes = plt.subplots(1, len(paths), figsize=(3.6 * len(paths), 3.8),
                             squeeze=False)
    im = None
    for ax, (ssp, p) in zip(axes[0], paths.items()):
        fut = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
        im = ax.imshow(fut - obs, cmap="BrBG", vmin=-4, vmax=4,
                       interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([]); ax.set_title(ssp, fontsize=9)
    if im is not None:
        fig.colorbar(im, ax=axes, shrink=0.7,
                     label="projected 2035-2064 mean minus observed 2022")
    fig.savefig(PLOTS_DIR / "future_vs_fpi2022_map.png", dpi=160,
                bbox_inches="tight")
    plt.close(fig)


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    scatter_cv()
    cv_by_year()
    feature_importance()
    residual_map()
    future_trajectory()
    change_maps()
    scatter_future_vs_2022()
    print(f"\nplots in {PLOTS_DIR}")


if __name__ == "__main__":
    main()
