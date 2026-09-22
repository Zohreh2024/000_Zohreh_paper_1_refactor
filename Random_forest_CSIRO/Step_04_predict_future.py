"""
Predict FPI for every future year, on the full NLUM grid.

Reads   data/random_forest_model.pkl, data/monthly_climate/<ssp>/*,
        required_data/Soil_data/*
Writes  output/fpi_<ssp>_<year>.tif          240 rasters, 4 SSPs x 60 years
        output/fpi_<ssp>_<period>_mean.tif   the two window means, per SSP
        output/prediction_summary.csv

240 predictions of 6.9 M land cells against a 64-tree forest, so the loop is
arranged around not repeating anything it does not have to:

- Soil is read once. It is 83 bands and, by the stated assumption, identical in
  every future year of every scenario - the only thing that moves between the
  240 predictions is the 91 climate columns.
- The land mask comes from soil alone (every cell where all 83 bands are
  finite). Climate is defined everywhere inside the bounding box, so it adds no
  masking of its own, and the historical FPI footprint is deliberately not used:
  masking future predictions to where FPI happened to be observed in 1985-2014
  would bake an observational footprint into a projection.
- Only land cells are assembled and predicted. The full grid is 13.7 M cells and
  half of it is ocean; predicting there would double the cost to produce NaN.
  sklearn also refuses outright - RandomForestRegressor.predict raises on NaN
  input rather than propagating it.

Prediction is a fresh process per year (loky) rather than threads, and each
worker holds its own copy of the model and the soil block, ~7 GB. Keep --jobs
modest.
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray as rxr
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FUTURE_YEARS, MODEL_PATH, OUTPUT_DIR, SSPS,
                    climate_features_at, feature_names, nlum_template,
                    soil_files)

N_JOBS = 6
PERIODS = {"2035-2064": range(2035, 2065), "2070-2099": range(2070, 2100)}

_CACHE = {}


def land_and_soil():
    """(rows, cols, soil) for every NLUM cell with complete soil, cached per process."""
    if "soil" in _CACHE:
        return _CACHE["soil"]

    paths = soil_files()
    tpl = nlum_template()
    ny, nx = tpl.sizes["y"], tpl.sizes["x"]

    mask = np.ones((ny, nx), dtype=bool)
    bands = []
    for p in paths:
        v = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values.astype(np.float32)
        mask &= np.isfinite(v)
        bands.append(v)

    rows, cols = np.nonzero(mask)
    soil = np.empty((len(paths), rows.size), dtype=np.float32)
    for i, v in enumerate(bands):
        soil[i] = v[rows, cols]
    del bands

    _CACHE["soil"] = (rows, cols, soil)
    return _CACHE["soil"]


def load_model():
    if "model" not in _CACHE:
        with open(MODEL_PATH, "rb") as f:
            blob = pickle.load(f)
        if list(blob["feature_names"]) != feature_names():
            raise AssertionError(
                "the saved model's feature order does not match common.feature_names(); "
                "refit with Step_03 before predicting"
            )
        _CACHE["model"] = blob["model"]
    return _CACHE["model"]


def predict_one(ssp, year, n_jobs, overwrite):
    out_path = OUTPUT_DIR / f"fpi_{ssp}_{year}.tif"
    if out_path.exists() and not overwrite:
        return {"ssp": ssp, "year": year, "status": "skip"}

    t0 = time.time()
    rows, cols, soil = land_and_soil()
    model = load_model()
    model.n_jobs = n_jobs

    tpl = nlum_template()
    lat = tpl.y.values[rows]
    lon = tpl.x.values[cols]

    clim = climate_features_at(year, ssp, lat, lon, pointwise=True)
    X = np.vstack([soil, clim]).T
    del clim

    pred = model.predict(X).astype(np.float32)
    del X

    grid = np.full((tpl.sizes["y"], tpl.sizes["x"]), np.nan, dtype=np.float32)
    grid[rows, cols] = pred

    da = tpl.copy(data=grid)
    da.attrs["long_name"] = f"FPI_prediction_{ssp}_{year}"
    da.rio.to_raster(out_path, compress="lzw")

    return {
        "ssp": ssp, "year": year, "status": "ok", "n_cells": int(rows.size),
        "min": float(pred.min()), "max": float(pred.max()),
        "mean": float(pred.mean()), "seconds": round(time.time() - t0, 1),
    }


def period_means():
    """Average the yearly rasters into the two CSIRO windows, per SSP."""
    tpl = nlum_template()
    made = []
    for ssp in SSPS:
        for name, yrs in PERIODS.items():
            paths = [OUTPUT_DIR / f"fpi_{ssp}_{y}.tif" for y in yrs]
            paths = [p for p in paths if p.exists()]
            if not paths:
                continue
            acc = np.zeros((tpl.sizes["y"], tpl.sizes["x"]), dtype=np.float64)
            for p in paths:
                acc += rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
            da = tpl.copy(data=(acc / len(paths)).astype(np.float32))
            da.attrs["long_name"] = f"FPI_mean_{ssp}_{name}"
            out = OUTPUT_DIR / f"fpi_{ssp}_{name}_mean.tif"
            da.rio.to_raster(out, compress="lzw")
            made.append(f"{out.name}  ({len(paths)} years)")
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=N_JOBS)
    ap.add_argument("--model-jobs", type=int, default=8,
                    help="threads inside each worker's RandomForest.predict")
    ap.add_argument("--ssp", nargs="*", default=SSPS)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--periods-only", action="store_true")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.periods_only:
        jobs = [(s, y) for s in args.ssp for y in FUTURE_YEARS]
        print(f"{len(jobs)} scenario-years, {args.jobs} processes "
              f"x {args.model_jobs} predict threads")
        t0 = time.time()
        results = Parallel(n_jobs=args.jobs, backend="loky", verbose=5)(
            delayed(predict_one)(s, y, args.model_jobs, args.overwrite) for s, y in jobs
        )
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_DIR / "prediction_summary.csv", index=False)
        done = df[df["status"] == "ok"]
        print(f"\n{len(done)} predicted, {len(df) - len(done)} skipped, "
              f"{time.time() - t0:.0f}s")
        if len(done):
            print(done.groupby("ssp")[["min", "mean", "max"]].mean().round(3).to_string())

    for line in period_means():
        print("period mean:", line)
    print(f"\noutputs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
