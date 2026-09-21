"""
Step 02 - Dataframe 2, the future table (and its historical twin).

One row per future grid cell, carrying the same columns as the reference table:
X, Y and the same 174 FPI predictors, under each scenario-window, plus the M'
projected for that cell.

    X, Y | 83 soil | 91 climate (window mean) | M' | FPI

Nine sets are built: the eight scenario-windows and one historical set on the
same cells. The historical set does three jobs - it supplies the mean and
standard deviation that put both tables in one comparable space, it is the
sample the PCA is fitted on, and it is the control run in Step_03 (matching a
site to a *present-day* analogue, where the answer is already known).

The grid is subsampled every `--downsample` cells (default 10, the same rate the
random forest's training table used), giving ~69,500 land cells. That is ample
for an analogue search: the question is whether a climate exists somewhere in
the future domain, not to enumerate every cell that has it, and a full-resolution
search would multiply the cost a hundredfold to return neighbours a few hundred
metres apart.

Soil is static by assumption, so the same 83 columns appear in the historical
and in every future set - as they do in the projection itself.

Reads   Random_forest_CSIRO/required_data/Soil_data/*.tif
        Random_forest_CSIRO/data/monthly_climate/<historical|ssp>/*
        FPI_Accuracy_check/output_Mprime_rf/mean_of_annual/maxAbgMF_<ssp>_<win>_mean.tif
        FPI_Accuracy_check/output/fpi_rf_1985-2014_mean.tif
        Random_forest_CSIRO/output/fpi_<ssp>_<window>_mean.tif
        Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif
Writes  outputs/tables/future_table_<ssp>_<window>.npz     8
        outputs/tables/historical_table.npz
        outputs/tables/<set>_slim.csv      X, Y, M', FPI + the 7 annual climate
                                           means, for reading by eye

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_build_future_table.py --jobs 6
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402
import rioxarray as rxr                                        # noqa: E402
from joblib import Parallel, delayed                           # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RF_DIR = ROOT / "Random_forest_CSIRO"
sys.path.insert(0, str(RF_DIR))

from common import (CLIM_VARS, HIST_YEARS, climate_features_at,       # noqa: E402
                    feature_names, nlum_template, soil_feature_names,
                    soil_files)

OUT_DIR = HERE / "outputs" / "tables"
FPI_ACC = ROOT / "FPI_Accuracy_check"
# The method is Eq.(1) of the window-mean FPI (Roxburgh et al. 2019, Sec. 2,
# p. 265: one FPI per location in, one M out). `mean_of_annual` is the
# sensitivity and holds the annual rasters.
MPRIME_OFMEAN = FPI_ACC / "output_Mprime_rf" / "eq1_of_mean"
MPRIME_ANNUAL = FPI_ACC / "output_Mprime_rf" / "mean_of_annual"
FPI_FUT_DIR = RF_DIR / "output"
FPI_HIST = FPI_ACC / "output" / "fpi_rf_1985-2014_mean.tif"
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019_NLUM.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = {"2035-2064": list(range(2035, 2065)),
           "2070-2099": list(range(2070, 2100))}


def land_cells(downsample):
    """Subsampled cells with complete soil - the same rule the projection uses."""
    tpl = nlum_template()
    ny, nx = tpl.sizes["y"], tpl.sizes["x"]
    rr = np.arange(0, ny, downsample)
    cc = np.arange(0, nx, downsample)
    gr, gc = np.meshgrid(rr, cc, indexing="ij")
    rows, cols = gr.ravel(), gc.ravel()

    paths = soil_files()
    soil = np.empty((len(paths), rows.size), dtype=np.float32)
    for i, p in enumerate(paths):
        v = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values
        soil[i] = v[rows, cols]
    ok = np.isfinite(soil).all(axis=0)

    with rasterio.open(NLUM_MASK) as s:
        mask = s.read(1) == 1
    ok &= mask[rows, cols]

    rows, cols, soil = rows[ok], cols[ok], soil[:, ok]
    lat = tpl.y.values[rows]
    lon = tpl.x.values[cols]
    print("grid: every %dth cell, %s land cells with complete soil"
          % (downsample, format(rows.size, ",")))
    return rows, cols, lat, lon, soil


def read_at(path, rows, cols):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
    return a[rows, cols].astype("float32")


def window_climate(years, ssp, lat, lon, jobs):
    """The 91 climate features averaged over a window, at the given points.

    Processes, not threads: netCDF4 serialises every HDF5 call behind one
    module-global lock, so threads take turns inside the library instead of
    overlapping I/O.
    """
    def one(yr):
        return climate_features_at(yr, ssp, lat, lon, pointwise=True).astype("float64")

    parts = Parallel(n_jobs=jobs, backend="loky", verbose=0)(
        delayed(one)(yr) for yr in years)
    acc = parts[0]
    for p in parts[1:]:
        acc = acc + p
    return (acc / len(years)).astype("float32")


def slim_frame(lat, lon, clim, names, extra):
    """X, Y, the annual climate means and whatever else, for reading by eye."""
    idx = {n: i for i, n in enumerate(names)}
    out = {"x": lon.astype("float32"), "y": lat.astype("float32")}
    out.update(extra)
    for var in CLIM_VARS:
        out["%s_ann" % var] = clim[idx["%s_ann" % var]]
    return pd.DataFrame(out)


def build(name, years, ssp, rows, cols, lat, lon, soil, jobs, overwrite,
          order="eq1_of_mean"):
    dst = OUT_DIR / ("%s.npz" % name)
    if dst.exists() and not overwrite:
        print("  %s exists, kept" % dst.name)
        return

    t0 = time.time()
    clim = window_climate(years, ssp, lat, lon, jobs)
    X = np.vstack([soil, clim]).T.astype("float32")

    if ssp is None:
        mprime = read_at(NEW_M, rows, cols)
        fpi = read_at(FPI_HIST, rows, cols)
    else:
        win = "%d-%d" % (years[0], years[-1])
        mprime = read_at(
            (MPRIME_OFMEAN / ("maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win)))
            if order == "eq1_of_mean"
            else (MPRIME_ANNUAL / ("maxAbgMF_%s_%s_mean.tif" % (ssp, win))),
            rows, cols)
        fpi = read_at(FPI_FUT_DIR / ("fpi_%s_%s_mean.tif" % (ssp, win)), rows, cols)

    np.savez_compressed(
        dst, X=X, rows=rows.astype("int32"), cols=cols.astype("int32"),
        x=lon.astype("float32"), y=lat.astype("float32"),
        mprime=mprime, fpi=fpi,
        feature_names=np.array(feature_names(), dtype=object),
        years=np.array(years), ssp=str(ssp))

    slim = slim_frame(lat, lon, clim, feature_names()[len(soil_feature_names()):],
                      {"mprime": mprime, "fpi": fpi})
    slim.to_csv(OUT_DIR / ("%s_slim.csv" % name), index=False)

    print("  %s: %s cells, M' median %.2f, FPI median %.3f, %.0fs"
          % (name, format(X.shape[0], ","), float(np.nanmedian(mprime)),
             float(np.nanmedian(fpi)), time.time() - t0), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--downsample", type=int, default=10)
    ap.add_argument("--order", choices=["eq1_of_mean", "mean_of_annual"],
                    default="eq1_of_mean",
                    help="which averaging order of M' to store (default: the "
                         "method)")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, cols, lat, lon, soil = land_cells(args.downsample)

    print("historical 1985-2014")
    build("historical_table", HIST_YEARS, None, rows, cols, lat, lon, soil,
          args.jobs, args.overwrite, args.order)

    for win, years in WINDOWS.items():
        for ssp in SSPS:
            print("%s %s" % (ssp, win))
            build("future_table_%s_%s" % (ssp, win), years, ssp,
                  rows, cols, lat, lon, soil, args.jobs, args.overwrite,
                  args.order)

    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
