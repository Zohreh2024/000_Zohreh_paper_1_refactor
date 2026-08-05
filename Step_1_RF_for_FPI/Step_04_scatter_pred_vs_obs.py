"""
Scatter each SSP's 2021-2040 predicted FPI against observed mean FPI 2020-2022.

Samples N_POINTS random NLUM-valid cells and plots one panel per scenario:

    x = mean of Data/Processed/fpi/fpi_{2020,2021,2022}.tif   (observed)
    y = Step_1_RF_for_FPI/output/future_<ssp>_2021-2040_prediction.tif

The SAME cells are used in every panel, so the four scenarios are directly
comparable rather than each being a different random draw.

Read this as a sanity check, not a validation
---------------------------------------------
The prediction is FPI under the *2021-2040 mean climate*; the observation is a
3-year mean. Averaging 2020-2022 damps single-year weather relative to using
2022 alone, but does not remove the mismatch: all three were La Nina years, so
the observed mean (~4.7) still sits above the 1970-2000 climatological mean of
4.28. Points below the 1:1 line remain expected and are not by themselves model
error. Compare panels with each other rather than against the 1:1 line.

Output: plots/scatter_pred_vs_obs_2020_2022.png  (+ .csv of the sampled points)
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")           # no display on this machine

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

STEP_DIR = Path(__file__).resolve().parent
PRED_DIR = STEP_DIR / "output"      # Step_03's prediction rasters
PLOTS_DIR = STEP_DIR / "plots"      # figures produced by this and later steps

OBS_YEARS = [2020, 2021, 2022]      # averaged to damp single-year weather
OBS_LABEL = f"{OBS_YEARS[0]}-{OBS_YEARS[-1]}"
OBS_COL = f"observed_{OBS_YEARS[0]}_{OBS_YEARS[-1]}"
PERIOD = "2021-2040"
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]

N_POINTS = 1_000
RANDOM_STATE = 42

# From the validated reference palette (light surface). One series colour: the
# panel title carries scenario identity, so colour is not encoding anything and
# the all-pairs CVD cap on 4+ categorical hues never applies.
SERIES = "#2a78d6"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Sample the same random cells from every raster
# --------------------------------------------------------------------------- #

with rasterio.open(NLUM_MASK) as s:
    valid = s.read(1) == 1

obs_stack = []
for year in OBS_YEARS:
    p = PROCESSED_DIR / "fpi" / f"fpi_{year}.tif"
    if not p.exists():
        raise FileNotFoundError(f"observed FPI raster not found: {p}")
    with rasterio.open(p) as s:
        a = s.read(1)
    obs_stack.append(a)
    print(f"observed {year}: mean {np.nanmean(a):.3f}")

# All cells are either finite in every year or NaN in every year (same mask), so
# a plain mean is safe here - no need for nanmean and its empty-slice warning.
obs = np.mean(np.stack(obs_stack), axis=0)
print(f"observed {OBS_LABEL} mean: {np.nanmean(obs):.3f}")

pred = {}
missing = []
for ssp in SSPS:
    p = PRED_DIR / f"future_{ssp}_{PERIOD}_prediction.tif"
    if not p.exists():
        missing.append(p.name)
        continue
    with rasterio.open(p) as s:
        pred[ssp] = s.read(1)

if missing:
    raise FileNotFoundError(
        "prediction raster(s) not found - has Step_03 finished?\n  "
        + "\n  ".join(missing)
    )

# Only sample cells that are valid in the mask AND finite in every raster, so
# each panel plots the identical set of points.
usable = valid & np.isfinite(obs)
for a in pred.values():
    usable &= np.isfinite(a)

rows, cols = np.nonzero(usable)
print(f"usable cells: {rows.size:,} of {valid.sum():,} NLUM-valid")

rng = np.random.default_rng(RANDOM_STATE)
pick = rng.choice(rows.size, size=min(N_POINTS, rows.size), replace=False)
r, c = rows[pick], cols[pick]
print(f"sampled      : {r.size:,} points (seed {RANDOM_STATE})")

sample = pd.DataFrame({"row": r, "col": c, OBS_COL: obs[r, c]})
for ssp in SSPS:
    sample[ssp] = pred[ssp][r, c]


# --------------------------------------------------------------------------- #
# Plot - 2x2 small multiples, shared scales
# --------------------------------------------------------------------------- #

lo = float(min(sample[OBS_COL].min(), *(sample[s].min() for s in SSPS)))
hi = float(max(sample[OBS_COL].max(), *(sample[s].max() for s in SSPS)))
pad = 0.04 * (hi - lo)
lim = (lo - pad, hi + pad)

fig, axes = plt.subplots(2, 2, figsize=(9.6, 9.6), sharex=True, sharey=True)
fig.patch.set_facecolor(SURFACE)

for ax, ssp in zip(axes.ravel(), SSPS):
    x = sample[OBS_COL].values
    y = sample[ssp].values

    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # 1:1 reference, recessive - it is context, not a series
    ax.plot(lim, lim, color=AXIS, linewidth=1.2, linestyle="--", zorder=1)

    ax.scatter(x, y, s=26, c=SERIES, alpha=0.5, linewidths=0.5,
               edgecolors=SURFACE, zorder=2)

    # Fit statistics, not a label on every point
    resid = y - x
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    bias = float(np.mean(resid))
    r_pearson = float(np.corrcoef(x, y)[0, 1])
    ax.text(0.04, 0.96,
            f"r = {r_pearson:.3f}\nRMSE = {rmse:.2f}\nbias = {bias:+.2f}",
            transform=ax.transAxes, va="top", ha="left",
            fontsize=9, color=INK_SECONDARY, linespacing=1.5)

    ax.set_title(ssp, fontsize=12, color=INK, pad=8, loc="left")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.tick_params(colors=MUTED, labelsize=9)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)

for ax in axes[-1]:
    ax.set_xlabel("Observed FPI, mean 2020-2022", fontsize=10, color=INK_SECONDARY)
for ax in axes[:, 0]:
    ax.set_ylabel(f"Predicted FPI, {PERIOD} mean climate", fontsize=10, color=INK_SECONDARY)

fig.suptitle(f"Predicted FPI ({PERIOD}) vs observed mean FPI (2020-2022)",
             fontsize=14, color=INK, x=0.5, y=0.975)
fig.text(0.5, 0.945,
         f"{len(sample):,} random NLUM cells, identical in every panel  ·  dashed line is 1:1",
         ha="center", fontsize=9.5, color=MUTED)
fig.text(0.5, 0.015,
         f"A {PERIOD} mean-climate prediction is not expected to match a 3-year observed mean; "
         f"{OBS_LABEL} were all La Nina years. Compare panels with each other, not against the 1:1 line.",
         ha="center", fontsize=8.5, color=MUTED, style="italic", wrap=True)

fig.tight_layout(rect=[0, 0.035, 1, 0.935])

png = PLOTS_DIR / "scatter_pred_vs_obs_2020_2022.png"
fig.savefig(png, dpi=160, facecolor=SURFACE)
sample.to_csv(PLOTS_DIR / "scatter_pred_vs_obs_2020_2022.csv", index=False)

print(f"\nwrote {png}")
print(f"wrote {PLOTS_DIR / 'scatter_pred_vs_obs_2020_2022.csv'}")

print(f"\n{'scenario':10s} {'r':>7s} {'RMSE':>7s} {'bias':>7s} {'mean pred':>10s}")
print(f"{'observed':10s} {'':>7s} {'':>7s} {'':>7s} {sample[OBS_COL].mean():10.3f}")
for ssp in SSPS:
    d = sample[ssp] - sample[OBS_COL]
    print(f"{ssp:10s} {np.corrcoef(sample[OBS_COL], sample[ssp])[0,1]:7.3f} "
          f"{np.sqrt((d**2).mean()):7.3f} {d.mean():+7.3f} {sample[ssp].mean():10.3f}")
