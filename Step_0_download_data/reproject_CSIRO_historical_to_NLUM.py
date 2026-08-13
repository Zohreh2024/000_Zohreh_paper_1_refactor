"""
Aggregate the daily BARRA-R2 historical baseline to monthly, match it to the
NLUM grid, fill gaps, and mask to NLUM's valid cells.

Per raw file (one variable, one year):
    1. clip      - subset lat/lon to the NLUM bounding box (+ buffer) while the
                   file is still lazy, so only ~1/6 of the domain is ever read
    2. aggregate - 365/366 daily steps -> 12 monthly bands (see AGGREGATION)
    3. match     - rio.reproject_match onto the NLUM template: WGS 84 -> GDA94,
                   0.11 deg -> 0.01 deg, snapped to NLUM's exact grid
    4. fill      - NaN cells take the value of the nearest valid cell
    5. mask      - cells outside the NLUM mask (mask == 0) are set to NaN

Data/Raw/CSIRO_historical_data/<var>/<var>_day_..._<year>.nc
    -> Data/Processed/CSIRO_historical_data/<var>/<var>_mon_..._<year>.tif

`day` becomes `mon` in the output name so nothing downstream mistakes these for
the daily source. Steps 3-5 and the 12-band monthly layout are identical to
`reproject_match_NLUM.py`, whose helpers this imports, so these variables land on
exactly the same footing as tmin/tmax/prec/bioc.

Units
-----
Output units follow ANUClimate v2-0 monthly
(https://thredds.nci.org.au/thredds/catalog/gh70/ANUClimate/v2-0/stable/month)
for the four variables ANUClimate also carries, so these land on the same
footing as FullCAM's historical inputs. `rsds` is the only conversion; see
AGGREGATION/SCALE/UNITS below. The units are written into each GeoTIFF as a
dataset tag and a per-band tag, because the nine variables do not share one.

Why monthly
-----------
NLUM is 3364 x 4071, so one float32 band is 52 MB. Keeping the daily step would
turn 109 GB of source into ~5.1 TB of output; monthly gives ~169 GB and matches
both FullCAM's time step and every other variable in Data/Processed.

Usage
-----
    python reproject_CSIRO_historical_to_NLUM.py --dry-run
    python reproject_CSIRO_historical_to_NLUM.py --vars pr tasmax tasmin
    python reproject_CSIRO_historical_to_NLUM.py --workers 6
    python reproject_CSIRO_historical_to_NLUM.py --overwrite

Runs through joblib with the loky backend, not threading: netCDF4-python
serialises every HDF5 call behind a module-global lock, so threads would take
turns inside the library instead of overlapping I/O. Windows spawns rather than
forks, so the driver sits behind `if __name__ == "__main__"` and each worker
loads the NLUM template lazily rather than at import time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
import rioxarray  # noqa: F401 - registers the .rio accessor on xarray objects
import xarray as xr
from joblib import Parallel, delayed
from rasterio.enums import Resampling

# Importing this also applies its PROJ_LIB fix for the PostGIS proj.db on PATH.
from reproject_match_NLUM import (
    CLIP_BUFFER_DEG,
    PROCESSED_DIR,
    RAW_DIR,
    fill,
    load_template,
    write_gtiff,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

VARIABLE_DIR = "CSIRO_historical_data"
SRC_DIR = RAW_DIR / VARIABLE_DIR
DST_DIR = PROCESSED_DIR / VARIABLE_DIR

# How each variable collapses from daily to monthly, and what it comes out as.
#
# Units follow ANUClimate v2-0 monthly wherever ANUClimate has the variable, so
# these sit on the same footing as FullCAM's own historical inputs:
#
#     BARRA-R2      ANUClimate    ANUClimate units    this pipeline
#     pr            rain          mm month-1          sum of mm d-1  -> mm month-1
#     tasmax        tmax          degree Celsius      mean, already degC
#     tasmin        tmin          degree Celsius      mean, already degC
#     rsds          srad          MJ m-2 day-1        mean W m-2 x 0.0864
#
# `pr` is a rate in mm d-1, so summing the daily values over a month gives the
# monthly total in mm - the quantity ANUClimate's rain carries and what
# Data/Processed/prec holds for WorldClim.
#
# `rsds` is the only real unit change: 1 W m-2 sustained for a day is
# 86400 J m-2 = 0.0864 MJ m-2, so the monthly mean of the daily-mean flux times
# 0.0864 is ANUClimate's "monthly total solar radiation" expressed, as it is
# there, as a mean daily total in MJ m-2 day-1.
#
# ANUClimate has no relative humidity or wind speed product (its vp/vpd are
# vapour pressure in hPa, a different variable), so hurs*/sfcWind* are left in
# their source units, unscaled. Everything except pr is a state variable, so the
# month's mean is the meaningful summary; for hursmax/hursmin/sfcWindmax that is
# the mean of the daily extreme, the standard monthly form of those fields - NOT
# the monthly extreme.
AGGREGATION = {
    "hurs": "mean",        # mean near-surface relative humidity
    "hursmax": "mean",     # mean of daily maximum relative humidity
    "hursmin": "mean",     # mean of daily minimum relative humidity
    "pr": "sum",           # monthly total precipitation
    "rsds": "mean",        # mean downwelling shortwave radiation
    "sfcWind": "mean",     # mean near-surface wind speed
    "sfcWindmax": "mean",  # mean of daily maximum wind speed
    "tasmax": "mean",      # mean of daily maximum temperature
    "tasmin": "mean",      # mean of daily minimum temperature
}

# Multiplier applied after aggregation, and the resulting units. A scale of 1.0
# means the source units already match what ANUClimate would use, or that
# ANUClimate has no counterpart and the source units stand.
SCALE = {"rsds": 86400 / 1e6}

UNITS = {
    "hurs": "%",
    "hursmax": "%",
    "hursmin": "%",
    "pr": "mm month-1",
    "rsds": "MJ m-2 day-1",
    "sfcWind": "m s-1",
    "sfcWindmax": "m s-1",
    "tasmax": "degree Celsius",
    "tasmin": "degree Celsius",
}

VARIABLES = sorted(AGGREGATION)

# BARRA-R2 ships plain CF lat/lon in degrees_north/degrees_east with no grid
# mapping variable, i.e. an unqualified geographic CRS. Declaring WGS 84 and
# letting reproject_match convert to NLUM's GDA94 is the same path the WorldClim
# rasters take, so the two products stay consistent.
SRC_CRS = "EPSG:4326"

RESAMPLING = Resampling.bilinear

N_WORKERS = 6  # loky processes; each holds one year of one variable


# --------------------------------------------------------------------------- #
# Per-file processing
# --------------------------------------------------------------------------- #

def dst_for(src_path):
    """Output path for a raw file: <var>_day_..._<year>.nc -> <var>_mon_...tif."""
    variable = src_path.parent.name
    name = src_path.stem.replace(f"{variable}_day_", f"{variable}_mon_", 1)
    return DST_DIR / variable / f"{name}.tif"


def monthly_bands(src_path, variable, template):
    """Read one year, clip to the NLUM box, and collapse it to 12 monthly bands.

    Returns a (12, lat, lon) DataArray still on the source 0.11 deg grid, with
    the source CRS attached and latitude descending so it is north-up like the
    template.
    """
    west, south, east, north = template.rio.bounds()
    buffer_deg = CLIP_BUFFER_DEG

    ds = xr.open_dataset(src_path)
    try:
        # Source latitude ascends and longitude runs past 180 (the AUS-11 domain
        # reaches 207.39E), so slice in the source's own order and orientation.
        sub = ds[variable].sel(
            lat=slice(south - buffer_deg, north + buffer_deg),
            lon=slice(west - buffer_deg, east + buffer_deg),
        )

        # groupby, not resample: this environment's pandas rejects the `base`
        # kwarg xarray's resample passes. One file is exactly one calendar year,
        # so grouping on the month is equivalent and gives bands in month order.
        grouped = sub.groupby("time.month")
        monthly = grouped.sum() if AGGREGATION[variable] == "sum" else grouped.mean()
        monthly = monthly.load()
    finally:
        ds.close()

    if monthly.sizes["month"] != 12:
        raise ValueError(f"{src_path.name}: got {monthly.sizes['month']} months, want 12")

    # Scale to the ANUClimate unit before reprojecting, so the tif never holds
    # values in one unit while its metadata claims another.
    if variable in SCALE:
        monthly = monthly * SCALE[variable]

    monthly = monthly.sortby("lat", ascending=False)
    monthly = monthly.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    return monthly.rio.write_crs(SRC_CRS)


def reproject_months(monthly, template):
    """Reproject all 12 monthly bands onto the template grid, one at a time."""
    out = np.empty(
        (12, template.rio.height, template.rio.width), dtype="float32"
    )
    for i in range(12):
        band = monthly.isel(month=i)
        out[i] = band.rio.reproject_match(template, resampling=RESAMPLING).values
    return out


def process(src_path, overwrite=False):
    """Aggregate, reproject, fill and write one raw file. Never raises.

    Returns (status, output name, message). Loads the NLUM template inside the
    worker so loky's spawned processes do not each pay for it at import.
    """
    dst = dst_for(src_path)
    if dst.exists() and not overwrite:
        return "skipped", dst.name, ""

    try:
        variable = src_path.parent.name
        template, valid = load_template()

        monthly = monthly_bands(src_path, variable, template)
        matched = reproject_months(monthly, template)
        filled = fill(matched, valid)
        write_gtiff(
            filled, dst, template,
            [f"{variable}_{m:02d}" for m in range(1, 13)],
        )

        # Stamp the units on the file itself. Band descriptions alone say which
        # month a band is, not what it is measured in, and these nine variables
        # do not share a unit.
        with rasterio.open(dst, "r+") as ds:
            ds.update_tags(
                units=UNITS[variable],
                variable=variable,
                aggregation=AGGREGATION[variable],
                source=src_path.name,
            )
            for band in range(1, 13):
                ds.update_tags(band, units=UNITS[variable])

        # Should be impossible; say so loudly rather than write a silent hole.
        nan_in_mask = int(np.isnan(filled[:, valid]).sum())
        if filled.shape[1:] != valid.shape or nan_in_mask:
            return "warned", dst.name, (
                f"shape {filled.shape[1:]} vs NLUM {valid.shape}, "
                f"nan in mask {nan_in_mask:,}"
            )
    except Exception as exc:  # noqa: BLE001 - report and keep the batch going
        return "failed", dst.name, str(exc)

    return "processed", dst.name, ""


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def todo(variables, overwrite):
    """Raw files still needing processing, as a flat sorted list."""
    files = []
    for variable in variables:
        found = sorted((SRC_DIR / variable).glob(f"{variable}_day_*.nc"))
        pending = found if overwrite else [
            f for f in found if not dst_for(f).exists()
        ]
        print(f"{variable:<11} {len(pending):>3} of {len(found):>3} file(s) to process")
        files += pending
    return files


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Aggregate the BARRA-R2 historical baseline to monthly and "
                    "match it to the NLUM grid.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--vars", nargs="+", default=VARIABLES,
                   choices=VARIABLES, metavar="VAR",
                   help="variables to process: " + ", ".join(VARIABLES))
    p.add_argument("--workers", type=int, default=N_WORKERS,
                   help="loky processes")
    p.add_argument("--overwrite", action="store_true",
                   help="reprocess files that already have an output")
    p.add_argument("--dry-run", action="store_true",
                   help="list what would be processed, write nothing")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    files = todo(args.vars, args.overwrite)
    if not files:
        print("\nNothing to do.")
        return 0

    print(f"\n{len(files)} file(s) -> {DST_DIR}")

    if args.dry_run:
        for src in files:
            print(f"  {src.parent.name}/{src.name}  ->  {dst_for(src).name} "
                  f"[{AGGREGATION[src.parent.name]}]")
        return 0

    n_workers = max(1, args.workers)
    print(f"Processing with {n_workers} loky process(es)\n")

    outcomes = Parallel(n_jobs=n_workers, backend="loky", verbose=10)(
        delayed(process)(src, args.overwrite) for src in files
    )

    counts = {}
    for status, name, message in outcomes:
        counts[status] = counts.get(status, 0) + 1
        if status in ("failed", "warned"):
            print(f"[{status.upper()}] {name}: {message}")

    print("\nDone. " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
