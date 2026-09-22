"""
Observed historical mean FPI against the projected future window means.

Reads   required_data/fpi/fpi_<year>.tif           observed annual FPI
        output/fpi_<ssp>_<window>_mean.tif         the 8 projected window means
Writes  plots/scatter_hist_vs_future.png           4 SSP x 2 window hexbin panels
        plots/hist_vs_future_summary.csv           R2, RMSE, MAE per panel
        plots/hist_vs_future_map.png               the same difference in space

The x axis is the observed mean over `--hist-start`..`--hist-end` (default
1990-2022) and the y axis is the projected 30-year window mean, cell by cell on
the NLUM grid. Both sides are multi-decade means, so unlike
`scatter_future_vs_fpi2022` neither carries a single year's weather and the
scatter width is a real spatial disagreement rather than interannual noise.

R2 here is 1 - SSE/SST about the observed mean, i.e. the projection scored as if
it were predicting the historical map. It is a measure of displacement from the
baseline, not of model skill - the model is not trying to reproduce 1990-2022,
and a projected decline necessarily costs R2. Pearson r, reported alongside, is
the part that says whether the spatial pattern is preserved.
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray as rxr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FPI_DIR, OUTPUT_DIR, PLOTS_DIR, SSPS, regression_metrics

PERIODS = ["2035-2064", "2070-2099"]


def observed_mean(years):
    """Mean observed FPI over `years`, NaN where any year is NaN."""
    acc, n = None, 0
    for yr in years:
        p = FPI_DIR / f"fpi_{yr}.tif"
        if not p.exists():
            raise FileNotFoundError(p)
        v = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values.astype(np.float64)
        acc = v if acc is None else acc + v
        n += 1
    print(f"observed baseline: {n} years, {years[0]}-{years[-1]}")
    return acc / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist-start", type=int, default=1990)
    ap.add_argument("--hist-end", type=int, default=2022)
    args = ap.parse_args()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    years = list(range(args.hist_start, args.hist_end + 1))
    label = f"{args.hist_start}-{args.hist_end}"
    obs = observed_mean(years)

    paths = {(s, p): OUTPUT_DIR / f"fpi_{s}_{p}_mean.tif"
             for s in SSPS for p in PERIODS}
    missing = [k for k, v in paths.items() if not v.exists()]
    if missing:
        print(f"missing window means: {missing}")
    paths = {k: v for k, v in paths.items() if v.exists()}
    if not paths:
        sys.exit("no window-mean rasters found - run Step_04 first")

    fig, axes = plt.subplots(len(PERIODS), len(SSPS),
                             figsize=(4.6 * len(SSPS), 4.9 * len(PERIODS)),
                             squeeze=False)
    rows = []
    for i, period in enumerate(PERIODS):
        for j, ssp in enumerate(SSPS):
            ax = axes[i][j]
            if (ssp, period) not in paths:
                ax.axis("off")
                continue
            fut = rxr.open_rasterio(paths[(ssp, period)],
                                    masked=True).squeeze(drop=True).values
            ok = np.isfinite(obs) & np.isfinite(fut)
            o, f = obs[ok], fut[ok]
            m = regression_metrics(o, f)
            slope, intercept = np.polyfit(o, f, 1)
            hi = float(np.nanpercentile(np.concatenate([o, f]), 99.8))

            ax.hexbin(o, f, gridsize=110, bins="log", extent=(0, hi, 0, hi),
                      cmap="viridis")
            ax.plot([0, hi], [0, hi], color="0.85", lw=1.2, label="1:1")
            xs = np.linspace(0, hi, 50)
            ax.plot(xs, slope * xs + intercept, color="#C77B30", lw=1.4,
                    label=f"fit: y = {slope:.3f}x {intercept:+.3f}")
            ax.set(xlim=(0, hi), ylim=(0, hi),
                   xlabel=f"observed mean FPI {label}",
                   ylabel=f"projected mean FPI {period}",
                   title=f"{ssp}  {period}")
            ax.set_aspect("equal")
            ax.legend(frameon=False, fontsize=8, loc="upper left")
            # The stats go inside the axes, not into the title. With
            # `set_aspect("equal")` the axes shrink to a square inside their
            # cell, so a multi-line title floats far above its own panel and
            # collides with the row below.
            ax.text(0.97, 0.03,
                    f"$R^2$ = {m['r2']:.3f}\nRMSE = {m['rmse']:.3f}\n"
                    f"MAE = {m['mae']:.3f}\nr = {m['pearson_r']:.3f}\n"
                    f"bias = {m['bias']:+.3f} "
                    f"({100 * m['bias'] / m['obs_mean']:+.1f}%)",
                    transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.35", fc="white",
                              ec="0.75", alpha=0.85))

            rows.append({"ssp": ssp, "period": period,
                         "hist_window": label, "n_cells": int(ok.sum()),
                         "hist_mean": m["obs_mean"], "future_mean": m["pred_mean"],
                         "change": m["bias"],
                         "pct_change": 100 * m["bias"] / m["obs_mean"],
                         "r2": m["r2"], "pearson_r": m["pearson_r"],
                         "rmse": m["rmse"], "mae": m["mae"],
                         "slope": float(slope), "intercept": float(intercept)})

    fig.tight_layout(h_pad=2.5, w_pad=1.5)
    fig.savefig(PLOTS_DIR / "scatter_hist_vs_future.png", dpi=160)
    plt.close(fig)

    df = pd.DataFrame(rows)
    df.to_csv(PLOTS_DIR / "hist_vs_future_summary.csv", index=False)
    print(df.round(3).to_string(index=False))

    # The scatter cannot show where the displacement sits.
    fig, axes = plt.subplots(len(PERIODS), len(SSPS),
                             figsize=(3.5 * len(SSPS), 3.4 * len(PERIODS)),
                             squeeze=False)
    im = None
    for i, period in enumerate(PERIODS):
        for j, ssp in enumerate(SSPS):
            ax = axes[i][j]
            ax.set_xticks([]); ax.set_yticks([])
            if (ssp, period) not in paths:
                ax.axis("off")
                continue
            fut = rxr.open_rasterio(paths[(ssp, period)],
                                    masked=True).squeeze(drop=True).values
            im = ax.imshow(fut - obs, cmap="BrBG", vmin=-4, vmax=4,
                           interpolation="nearest")
            ax.set_title(f"{ssp}  {period}", fontsize=9)
    if im is not None:
        fig.colorbar(im, ax=axes, shrink=0.6,
                     label=f"projected mean minus observed {label} mean")
    fig.savefig(PLOTS_DIR / "hist_vs_future_map.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"\nplots in {PLOTS_DIR}")


if __name__ == "__main__":
    main()
