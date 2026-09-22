"""
Export the training table to NetCDF.

Reads   data/training_table.npz
Writes  data/X_train.nc, data/y_train.nc          (always)
        data/X_train_gridded.nc, data/y_train_gridded.nc   (--gridded)

Step_02 stores the fitted table as `.npz` because that is what sklearn is handed
and what Step_03 reloads. This step re-expresses the same numbers as NetCDF, in
either of the two shapes a reader might reasonably want.

Table form (default) - what was actually fitted
-----------------------------------------------
    X_train  (sample, feature)   float32, 2,086,920 x 174
    y_train  (sample)            float32

with `year`, `cell_row`, `cell_col`, `lat` and `lon` carried as coordinates on
`sample`, so any row can be traced back to the cell and year it came from. This
is the honest representation: the fit sees a flat table of rows, not a raster.

Gridded form (--gridded) - what a GIS wants
-------------------------------------------
    X_train  (year, feature, y, x)   float32
    y_train  (year, y, x)            float32

on the downsampled grid Step_02 sampled (every 10th NLUM row and column, so
337 x 408 at the default). Cells that were dropped for incomplete soil come back
as NaN, which is why this form is larger than the table it is built from - it
stores the holes. Roughly 2.9 GB before compression against 1.45 GB, hence the
flag rather than doing it by default.

Both forms hold identical numbers; neither is a re-derivation. Nothing here
recomputes a predictor, so the exported file cannot disagree with what the model
was fitted on.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, HIST_YEARS, X_TABLE_PATH, nlum_template

ENCODING = {"zlib": True, "complevel": 4}


def load():
    d = np.load(X_TABLE_PATH, allow_pickle=True)
    return (d["X"], d["y"], d["year"], d["cell_row"], d["cell_col"],
            [str(s) for s in d["feature_names"]], int(d["n_soil"]),
            int(d["downsample"]))


def write_table(X, y, year, cell_row, cell_col, names, n_soil, downsample):
    tpl = nlum_template()
    lat = tpl.y.values[cell_row].astype(np.float32)
    lon = tpl.x.values[cell_col].astype(np.float32)

    kind = np.array(["soil"] * n_soil + ["climate"] * (len(names) - n_soil))
    coords = {
        "sample": np.arange(len(y), dtype=np.int32),
        "feature": np.array(names),
        "year": ("sample", year.astype(np.int16)),
        "cell_row": ("sample", cell_row.astype(np.int32)),
        "cell_col": ("sample", cell_col.astype(np.int32)),
        "lat": ("sample", lat),
        "lon": ("sample", lon),
        "kind": ("feature", kind),
    }
    attrs = {
        "title": "FPI random forest training predictors, 1985-2014",
        "description": "One row per (NLUM cell, year). Soil is static and repeats "
                       "down the 30 rows of a cell; only the climate columns vary "
                       "by year.",
        "n_soil_features": n_soil,
        "n_climate_features": len(names) - n_soil,
        "grid_downsample": downsample,
        "source": "Step_02_build_training_table.py -> data/training_table.npz",
    }

    Xda = xr.DataArray(X, dims=("sample", "feature"), coords=coords,
                       name="X_train", attrs=attrs)
    # y carries only the sample-dimension coordinates: `feature` and the `kind`
    # attached to it describe columns, and xarray rejects a coordinate whose
    # dimension the array does not have.
    sample_coords = {k: v for k, v in coords.items()
                     if k == "sample" or (isinstance(v, tuple) and v[0] == "sample")}
    yda = xr.DataArray(y, dims=("sample",), coords=sample_coords,
                       name="y_train",
                       attrs={"title": "Forest Productivity Index, observed",
                              "long_name": "FPI", "source": attrs["source"]})

    Xda.to_netcdf(DATA_DIR / "X_train.nc", engine="netcdf4",
                  encoding={"X_train": ENCODING})
    yda.to_netcdf(DATA_DIR / "y_train.nc", engine="netcdf4",
                  encoding={"y_train": ENCODING})
    print(f"wrote {DATA_DIR / 'X_train.nc'}  {Xda.shape}")
    print(f"wrote {DATA_DIR / 'y_train.nc'}  {yda.shape}")


def write_gridded(X, y, year, cell_row, cell_col, names, n_soil, downsample):
    tpl = nlum_template()
    rr = np.arange(0, tpl.sizes["y"], downsample)
    cc = np.arange(0, tpl.sizes["x"], downsample)
    ri = {int(v): i for i, v in enumerate(rr)}
    ci = {int(v): i for i, v in enumerate(cc)}
    yi = {int(v): i for i, v in enumerate(HIST_YEARS)}

    ti = np.array([yi[int(v)] for v in year])
    row = np.array([ri[int(v)] for v in cell_row])
    col = np.array([ci[int(v)] for v in cell_col])

    shape = (len(HIST_YEARS), len(names), len(rr), len(cc))
    Xg = np.full(shape, np.nan, dtype=np.float32)
    Xg[ti, :, row, col] = X
    yg = np.full((len(HIST_YEARS), len(rr), len(cc)), np.nan, dtype=np.float32)
    yg[ti, row, col] = y

    coords = {
        "year": np.array(HIST_YEARS, dtype=np.int16),
        "feature": np.array(names),
        "y": tpl.y.values[rr],
        "x": tpl.x.values[cc],
        "kind": ("feature", np.array(["soil"] * n_soil
                                     + ["climate"] * (len(names) - n_soil))),
    }
    attrs = {"crs": "EPSG:4283 (GDA94)",
             "grid": f"NLUM every {downsample}th cell",
             "note": "NaN where soil coverage is incomplete or the cell is ocean",
             "source": "Step_02_build_training_table.py -> data/training_table.npz"}

    Xda = xr.DataArray(Xg, dims=("year", "feature", "y", "x"), coords=coords,
                       name="X_train", attrs=attrs)
    yda = xr.DataArray(yg, dims=("year", "y", "x"),
                       coords={k: coords[k] for k in ("year", "y", "x")},
                       name="y_train", attrs=attrs)

    Xda.to_netcdf(DATA_DIR / "X_train_gridded.nc", engine="netcdf4",
                  encoding={"X_train": ENCODING})
    yda.to_netcdf(DATA_DIR / "y_train_gridded.nc", engine="netcdf4",
                  encoding={"y_train": ENCODING})
    print(f"wrote {DATA_DIR / 'X_train_gridded.nc'}  {Xda.shape}")
    print(f"wrote {DATA_DIR / 'y_train_gridded.nc'}  {yda.shape}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gridded", action="store_true",
                    help="also write the (year, feature, y, x) cube (~2.9 GB)")
    args = ap.parse_args()

    t0 = time.time()
    data = load()
    print(f"X {data[0].shape}  y {data[1].shape}  "
          f"{len(data[5])} features ({data[6]} soil)")

    write_table(*data)
    if args.gridded:
        write_gridded(*data)
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
