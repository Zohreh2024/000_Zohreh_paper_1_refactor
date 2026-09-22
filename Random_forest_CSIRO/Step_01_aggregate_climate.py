"""
Collapse the daily CSIRO NetCDFs to 12 monthly aggregates per variable-year.

Reads   required_data/CSIRO_{historical,future}_data/<var>[/<ssp>]/*.nc
Writes  data/monthly_climate/<historical|ssp>/<var>/<var>_<set>_<year>_monthly.nc

1,890 daily files, ~1.5 TB, are the whole cost of this pipeline; everything
downstream reads the ~6 MB monthly files this step leaves behind. It is
resumable - a variable-year whose output already exists and opens cleanly is
skipped - so an interrupted run just continues.

Two things the daily files force:

- Crop to Australia first. The AUS-11 domain runs to lon 207 and lat 13, and
  more than four fifths of it is ocean and neighbouring continents that the
  NLUM grid never touches. Cropping cuts each year from 646 x 1082 to about
  323 x 386 before any reduction runs.
- Use processes, not threads. netCDF4-python serialises every HDF5 call behind
  a module-global lock, so threads take turns inside the library and overlap no
  I/O at all (29 MB/s serial, 36 MB/s on 6 threads, 116 MB/s on 6 processes on
  this share). Windows spawns rather than forks, so the driver sits behind
  `if __name__ == "__main__"` or every worker re-runs the module.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import xarray as xr
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BBOX, CLIM_VARS, MONTHLY_DIR, climate_jobs, monthly_path,
                    raw_climate_file)

N_JOBS = 24


def already_done(path, var):
    if not path.exists():
        return False
    try:
        with xr.open_dataset(path) as ds:
            return ds[var].sizes.get("month") == 12
    except Exception:
        return False


def aggregate_one(var, year, ssp):
    """Daily -> 12 monthly values for one variable-year. Returns a status line."""
    out_path = monthly_path(var, year, ssp)
    label = f"{var:8s} {ssp or 'historical':11s} {year}"

    if already_done(out_path, var):
        return f"{label}  skip (exists)"

    t0 = time.time()
    src = raw_climate_file(var, year, ssp)
    how = CLIM_VARS[var]

    with xr.open_dataset(src) as ds:
        da = ds[var].sel(**BBOX)
        if da.sizes["lat"] == 0 or da.sizes["lon"] == 0:
            raise ValueError(f"{src.name}: bounding box selected nothing")
        # `time.month` groups the calendar year directly. resample("1MS") would
        # do the same but reindexes on timestamps, and the historical and QDC
        # files stamp their days differently (12:00 vs 00:00), which would then
        # show up as different month coordinates between the two sets.
        grouped = da.groupby("time.month")
        monthly = grouped.sum("time") if how == "sum" else grouped.mean("time")

    monthly = monthly.astype(np.float32).transpose("month", "lat", "lon")
    monthly.name = var
    monthly.attrs = {
        "long_name": f"monthly {'total' if how == 'sum' else 'mean'} {var}",
        "aggregation": how,
        "source_file": src.name,
        "n_days": int(da.sizes["time"]),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".nc.tmp")
    monthly.to_netcdf(
        tmp, engine="netcdf4",
        encoding={var: {"zlib": True, "complevel": 4}},
    )
    tmp.replace(out_path)

    return (f"{label}  {da.sizes['time']:3d} days -> "
            f"{monthly.shape}  {time.time() - t0:6.1f}s")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=N_JOBS)
    ap.add_argument("--vars", nargs="*", default=None,
                    help="restrict to these climate variables")
    ap.add_argument("--set", nargs="*", default=None,
                    help="restrict to 'historical' and/or ssp names")
    args = ap.parse_args()

    jobs = climate_jobs()
    if args.vars:
        jobs = [j for j in jobs if j[0] in args.vars]
    if args.set:
        jobs = [j for j in jobs if (j[2] or "historical") in args.set]

    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(jobs)} variable-years, {args.jobs} processes")

    t0 = time.time()
    lines = Parallel(n_jobs=args.jobs, backend="loky", verbose=5)(
        delayed(aggregate_one)(*j) for j in jobs
    )
    for line in lines:
        print(line)

    n_skip = sum("skip" in l for l in lines)
    print(f"\n{len(lines) - n_skip} written, {n_skip} already present, "
          f"{time.time() - t0:.0f}s total -> {MONTHLY_DIR}")


if __name__ == "__main__":
    main()
