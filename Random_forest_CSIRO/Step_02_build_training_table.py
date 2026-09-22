"""
Build the pooled 1985-2014 training table: one row per (cell, year).

Reads   data/monthly_climate/historical/*, required_data/Soil_data/*,
        required_data/fpi/fpi_<year>.tif
Writes  data/training_table.npz  (X, y, year, cell_row, cell_col, feature_names)

Design
------
Step_01_RF_for_FPI fitted one climatological map: 1970-2000 mean FPI against a
1970-2000 climate normal, so every cell contributed exactly one row and the
model only ever saw spatial variation. That model cannot answer "what is FPI in
2043", because nothing in its training data distinguishes one year from another.

Here each of the 30 historical years is a separate sample of the same cell, so
the fit sees the interannual signal directly: cells that were dry in 1994 and
wet in 2010 appear twice with different climate and different FPI. Soil repeats
unchanged down the 30 rows of a cell, which is exactly the assumption the future
prediction makes when it holds soil constant.

`cell_row`/`cell_col` are kept alongside so Step_03 can split by *cell block*
and Step_05 can map residuals; a plain random split would put 1994 and 1995 of
the same cell on opposite sides of the split, and those two rows share all 83
soil values and most of their climate.

Sampling
--------
The full grid is 13.7 M cells, half of them ocean, and 30 years of it is far
more than a random forest needs. `--downsample 10` takes every 10th row and
column, ~69 k valid cells, ~2.1 M rows - enough that the limiting factor is the
signal, not the sample. Climate is interpolated straight onto those cells'
coordinates rather than onto the full grid first (see `climate_features_at`).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rioxarray as rxr
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA_DIR, FPI_DIR, HIST_YEARS, X_TABLE_PATH,
                    climate_features_at, feature_names, nlum_template,
                    soil_feature_names, soil_files)

DOWNSAMPLE = 10
N_JOBS = 15          # one worker per two years; each holds ~1 GB of climate


def load_soil(rows, cols):
    """The 83 static soil bands, sampled at the given cell indices.

    `masked=True` matters: AWC and several other layers carry -9999 as nodata
    rather than NaN, and an unmasked read would feed -9999 to the forest as if
    it were an available water capacity.
    """
    paths = soil_files()
    out = np.empty((len(paths), len(rows)), dtype=np.float32)
    for i, p in enumerate(paths):
        da = rxr.open_rasterio(p, masked=True).squeeze(drop=True)
        out[i] = da.values[rows, cols].astype(np.float32)
    return out


def year_rows(year, lat, lon):
    """The 91 climate features for one historical year at the sampled cells."""
    clim = climate_features_at(year, None, lat, lon, pointwise=True)
    fpi = rxr.open_rasterio(FPI_DIR / f"fpi_{year}.tif", masked=True).squeeze(drop=True)
    return clim, fpi


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--downsample", type=int, default=DOWNSAMPLE)
    ap.add_argument("--jobs", type=int, default=N_JOBS)
    args = ap.parse_args()

    t0 = time.time()
    tpl = nlum_template()
    ny, nx = tpl.sizes["y"], tpl.sizes["x"]
    y_axis = tpl.y.values
    x_axis = tpl.x.values

    rr = np.arange(0, ny, args.downsample)
    cc = np.arange(0, nx, args.downsample)
    grid_r, grid_c = np.meshgrid(rr, cc, indexing="ij")
    rows, cols = grid_r.ravel(), grid_c.ravel()
    print(f"grid {ny} x {nx}, every {args.downsample}th cell -> {rows.size:,} candidates")

    # Keep only cells where all 83 soil bands are finite. Climate is defined
    # everywhere inside the bounding box, so soil alone sets the land mask; FPI
    # is masked per year, since its footprint moves slightly year to year.
    soil = load_soil(rows, cols)
    soil_ok = np.isfinite(soil).all(axis=0)
    rows, cols, soil = rows[soil_ok], cols[soil_ok], soil[:, soil_ok]
    print(f"cells with complete soil: {rows.size:,} "
          f"({100 * soil_ok.mean():.1f}% of candidates)")

    lat = y_axis[rows]
    lon = x_axis[cols]

    results = Parallel(n_jobs=args.jobs, backend="loky", verbose=5)(
        delayed(year_rows)(yr, lat, lon) for yr in HIST_YEARS
    )

    X_parts, y_parts, yr_parts, r_parts, c_parts = [], [], [], [], []
    for yr, (clim, fpi) in zip(HIST_YEARS, results):
        target = fpi.values[rows, cols].astype(np.float32)
        ok = np.isfinite(target) & np.isfinite(clim).all(axis=0)
        n_drop = int((~ok).sum())
        X_parts.append(np.vstack([soil[:, ok], clim[:, ok]]).T)
        y_parts.append(target[ok])
        yr_parts.append(np.full(int(ok.sum()), yr, dtype=np.int16))
        r_parts.append(rows[ok].astype(np.int32))
        c_parts.append(cols[ok].astype(np.int32))
        print(f"  {yr}: {int(ok.sum()):,} rows  (dropped {n_drop:,} for missing FPI)"
              f"  FPI {target[ok].min():.2f}..{target[ok].max():.2f}")

    X = np.concatenate(X_parts).astype(np.float32)
    y = np.concatenate(y_parts).astype(np.float32)
    year = np.concatenate(yr_parts)
    cell_row = np.concatenate(r_parts)
    cell_col = np.concatenate(c_parts)

    names = feature_names()
    if X.shape[1] != len(names):
        raise AssertionError(f"{X.shape[1]} columns but {len(names)} feature names")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        X_TABLE_PATH, X=X, y=y, year=year, cell_row=cell_row, cell_col=cell_col,
        feature_names=np.array(names), downsample=args.downsample,
        n_soil=len(soil_feature_names()),
    )

    print(f"\nX {X.shape}  y {y.shape}  {X.nbytes / 1e9:.2f} GB in memory")
    print(f"{len(names)} features: {len(soil_feature_names())} soil + "
          f"{len(names) - len(soil_feature_names())} climate")
    print(f"wrote {X_TABLE_PATH}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
