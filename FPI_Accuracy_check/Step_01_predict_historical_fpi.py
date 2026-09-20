"""
Step 01 - model the 30 historical years with the same random forest that made
the projections, on the full NLUM grid.

Why this exists
---------------
The M' ratio currently mixes two sources:

    Eq1(FPI_future, random forest)  /  Eq1(FPI_historical, DCCEEW download)

Any bias in the forest sits in the numerator only, so it does not cancel and is
read downstream as climate change. With both sides modelled by the same fitted
model the bias cancels, which is the rule already applied to temperature and
rainfall (every delta is CSIRO-minus-CSIRO, never CSIRO-minus-ANUClimate).

No retraining, no refitting, no new features. This is
`Random_forest_CSIRO/Step_04_predict_future.py` with `ssp=None`, i.e. the same
model, the same soil block, the same land mask and the same
`common.climate_features_at` regrid, pointed at the BARRA-R2 historical monthly
climate in `Random_forest_CSIRO/data/monthly_climate/historical/`.

In-sample, and deliberately so
------------------------------
These 30 years are the model's training years, so `fpi_rf_<year>.tif` is an
in-sample fit, not an accuracy claim. That is the correct layer for the *ratio*:
the numerator and denominator must come from one model. The accuracy number to
quote is the out-of-fold `groupcv_year` score, which Step_02 reports alongside.

Writes  output/fpi_rf_<year>.tif            30 rasters, 1985-2014
        output/fpi_rf_1985-2014_mean.tif    the 30-year mean
        output/prediction_summary_hist.csv

Run
---
    conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" ^
        python Step_01_predict_historical_fpi.py --jobs 6
"""

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rioxarray as rxr                                        # noqa: E402
from joblib import Parallel, delayed                           # noqa: E402

HERE = Path(__file__).resolve().parent
RF_DIR = HERE.parent / "Random_forest_CSIRO"
sys.path.insert(0, str(RF_DIR))

from common import (HIST_YEARS, MODEL_PATH, climate_features_at,     # noqa: E402
                    feature_names, nlum_template, soil_files)

OUT_DIR = HERE / "output"
N_JOBS = 6

_CACHE = {}


def land_and_soil():
    """(rows, cols, soil) for every NLUM cell with complete soil.

    Identical to Step_04's, including the point that the land mask comes from
    soil alone and never from the observed FPI footprint - the modelled and the
    projected layers must be masked the same way or the ratio has holes on one
    side only.
    """
    if "soil" in _CACHE:
        return _CACHE["soil"]

    paths = soil_files()
    tpl = nlum_template()
    mask = np.ones((tpl.sizes["y"], tpl.sizes["x"]), dtype=bool)
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
                "the saved model's feature order does not match "
                "common.feature_names(); a wrong order gives plausible numbers "
                "with no error raised"
            )
        _CACHE["model"] = blob["model"]
    return _CACHE["model"]


def predict_one(year, n_jobs, overwrite):
    out_path = OUT_DIR / f"fpi_rf_{year}.tif"
    if out_path.exists() and not overwrite:
        return {"year": year, "status": "skip"}

    t0 = time.time()
    rows, cols, soil = land_and_soil()
    model = load_model()
    model.n_jobs = n_jobs

    tpl = nlum_template()
    clim = climate_features_at(year, None, tpl.y.values[rows], tpl.x.values[cols],
                               pointwise=True)
    X = np.vstack([soil, clim]).T
    del clim

    pred = model.predict(X).astype(np.float32)
    del X

    grid = np.full((tpl.sizes["y"], tpl.sizes["x"]), np.nan, dtype=np.float32)
    grid[rows, cols] = pred

    da = tpl.copy(data=grid)
    da.attrs["long_name"] = f"FPI_modelled_historical_{year}"
    da.rio.to_raster(out_path, compress="lzw")

    return {"year": year, "status": "ok", "n_cells": int(rows.size),
            "min": float(pred.min()), "max": float(pred.max()),
            "mean": float(pred.mean()), "seconds": round(time.time() - t0, 1)}


def mean_raster():
    tpl = nlum_template()
    paths = [OUT_DIR / f"fpi_rf_{y}.tif" for y in HIST_YEARS]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None
    acc = np.zeros((tpl.sizes["y"], tpl.sizes["x"]), dtype=np.float64)
    for p in paths:
        acc += rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
    da = tpl.copy(data=(acc / len(paths)).astype(np.float32))
    da.attrs["long_name"] = "FPI_modelled_historical_mean_1985-2014"
    out = OUT_DIR / "fpi_rf_1985-2014_mean.tif"
    da.rio.to_raster(out, compress="lzw")
    return out, len(paths)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=N_JOBS)
    ap.add_argument("--model-jobs", type=int, default=8)
    ap.add_argument("--years", type=int, nargs="*", default=HIST_YEARS)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--mean-only", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.mean_only:
        print(f"{len(args.years)} historical years, {args.jobs} processes "
              f"x {args.model_jobs} predict threads")
        t0 = time.time()
        results = Parallel(n_jobs=args.jobs, backend="loky", verbose=5)(
            delayed(predict_one)(y, args.model_jobs, args.overwrite)
            for y in args.years
        )
        df = pd.DataFrame(results)
        df.to_csv(OUT_DIR / "prediction_summary_hist.csv", index=False)
        done = df[df["status"] == "ok"]
        print(f"\n{len(done)} predicted, {len(df) - len(done)} skipped, "
              f"{time.time() - t0:.0f}s")
        if len(done):
            print(done[["year", "min", "mean", "max", "seconds"]].to_string(index=False))

    made = mean_raster()
    if made:
        print(f"\nmean raster: {made[0].name}  ({made[1]} years)")
    print(f"outputs in {OUT_DIR}")


if __name__ == "__main__":
    main()
