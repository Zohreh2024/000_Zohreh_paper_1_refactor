"""
Divide each CSIRO future climatology by its historical counterpart.

    Data/Processed/CSIRO_avg/FUTURE/CSIRO_<var>_<ssp>_monthly_avg_<window>_NLUM.tif
      /  Data/Processed/CSIRO_avg/HISTORICAL/CSIRO_<var>_monthly_avg_1985-2014_NLUM.tif
      -> Data/Processed/CSIRO_Delta/<var>_<ssp>_delta_<window>_over_1985-2014.tif (+ .nc)

8 variables x 4 scenarios x 2 windows = 64 outputs, each as GeoTIFF and NetCDF.
The division is per cell and per band, so band k of the output is
    future month k / historical month k
a dimensionless change factor: 1.0 means no change, 1.2 means 20% higher.

Windows
-------
    mid   2035-2064
    late  2070-2099
both divided by the single historical reference, 1985-2014.

Grid, band layout, mask and CRS are inherited from the inputs unchanged - both
sides are already on the NLUM grid, so this is pure arithmetic with no
resampling.

A ratio is the right form for seven of the eight variables
----------------------------------------------------------
`pr`, `rsds`, `hurs`, `hursmax`, `hursmin` and `sfcWind` are non-negative
quantities on a ratio scale, where "20% wetter" is meaningful and the factor is
exactly what a delta-change application needs.

**Temperature is different, and the output for `tasmax`/`tasmin` should be read
with care.** degC is an *interval* scale: its zero is arbitrary, so a quotient
carries no physical meaning. A cell whose historical January mean is -0.2 degC
and whose future mean is +1.8 degC yields a ratio of -9.0, and cells near the
zero crossing diverge without bound. The ratio is still computed here because it
was asked for, and the divergence is quantified in the run report so its extent
is visible, but the meaningful change signal for temperature is the additive
difference (future - historical, in degC), not this. Pass --additive to write
that instead.

Division guards
---------------
Cells whose historical value is zero have no defined ratio and are written as
NaN, counted and reported. Values are not clipped: an extreme ratio is
information about the denominator, and silently capping it would hide exactly
the temperature problem described above.

Usage
-----
    python calculate_CSIRO_delta.py --dry-run
    python calculate_CSIRO_delta.py --vars pr --ssps ssp245
    python calculate_CSIRO_delta.py --additive --vars tasmax tasmin
    python calculate_CSIRO_delta.py --workers 8
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import rioxarray
import xarray as xr
from joblib import Parallel, delayed

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AVG = PROJECT_ROOT / "Data" / "Processed" / "CSIRO_avg"
HIST_DIR = AVG / "HISTORICAL"
FUT_DIR = AVG / "FUTURE"
OUT_DIR = PROJECT_ROOT / "Data" / "Processed" / "CSIRO_Delta"
# Additive differences are a different quantity from the ratios, so they
# get their own folder rather than sitting beside them.
OUT_DIR_ADDITIVE = PROJECT_ROOT / "Data" / "Processed" / "CSIRO_Delta_additive"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
REFERENCE = "1985-2014"
WINDOWS = {"2035-2064": "mid", "2070-2099": "late"}

# Temperature is on an interval scale; a quotient of degC is not physical.
INTERVAL_SCALE = {"tasmax", "tasmin"}

MONTH_NAME = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CREATION_OPTS = dict(
    driver="GTiff", dtype="float32", nodata=np.nan, compress="LZW",
    tiled=True, blockxsize=256, blockysize=256, BIGTIFF="IF_SAFER",
)

RENAME_RETRIES, RENAME_BACKOFF = 8, 1.0
N_WORKERS = 8


def variables():
    """Variables that have both a historical file and at least one future file."""
    hist = {p.stem.split("_")[1] for p in HIST_DIR.glob("CSIRO_*_monthly_avg_*.tif")}
    fut = {p.stem.split("_")[1] for p in FUT_DIR.glob("CSIRO_*_monthly_avg_*.tif")}
    return sorted(hist & fut)


def hist_path(var):
    return HIST_DIR / f"CSIRO_{var}_monthly_avg_{REFERENCE}_NLUM.tif"


def fut_path(var, ssp, window):
    return FUT_DIR / f"CSIRO_{var}_{ssp}_monthly_avg_{window}_NLUM.tif"


def out_stem(var, ssp, window, additive):
    kind = "diff" if additive else "delta"
    return f"{var}_{ssp}_{kind}_{window}_over_{REFERENCE}"


def rename_with_retry(tmp, dst):
    for attempt in range(1, RENAME_RETRIES + 1):
        try:
            tmp.replace(dst)
            return
        except OSError:
            if attempt == RENAME_RETRIES:
                raise
            time.sleep(RENAME_BACKOFF * attempt)


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #

def combine(future, historical, additive):
    """future / historical, or future - historical.

    For the ratio, cells whose denominator is exactly zero become NaN rather
    than inf: a ratio against nothing is undefined, and inf would poison every
    downstream statistic. Nothing is clipped - an extreme ratio is a real fact
    about the denominator and hiding it would defeat the purpose of looking.
    """
    if additive:
        return (future - historical).astype("float32"), 0

    out = np.full_like(future, np.nan, dtype="float32")
    ok = historical != 0
    np.divide(future, historical, out=out, where=ok)
    undefined = int((~ok & np.isfinite(historical)).sum())
    return out, undefined


def write_outputs(arr, stem, var, ssp, window, additive, template, src_units,
                  out_dir):
    """Write the (12, y, x) result as GeoTIFF and NetCDF."""
    out_dir.mkdir(parents=True, exist_ok=True)
    units = src_units if additive else "1"
    kind = ("difference, future minus historical" if additive
            else "ratio, future divided by historical")

    tags = dict(
        units=units, variable=var, scenario=ssp, window=window,
        window_label=WINDOWS.get(window, ""), reference=REFERENCE,
        quantity=kind, model="ACCESS-CM2",
        numerator=fut_path(var, ssp, window).name,
        denominator=hist_path(var).name,
        grid="NLUM_2010-11_mask.tif, 3364 x 4071, 0.01 deg, GDA94",
    )
    if var in INTERVAL_SCALE and not additive:
        tags["warning"] = (
            "degC is an interval scale, so this ratio has no physical meaning; "
            "use the additive difference for temperature")

    tif = out_dir / f"{stem}.tif"
    tmp = tif.with_suffix(".tif.tmp")
    with rasterio.open(tmp, "w", height=template.rio.height,
                       width=template.rio.width, count=12,
                       crs=template.rio.crs, transform=template.rio.transform(),
                       **CREATION_OPTS) as dst:
        dst.write(arr)
        for i, mon in enumerate(MONTH_NAME, start=1):
            dst.set_band_description(i, f"{var}_{i:02d}_{mon}")
            dst.update_tags(i, units=units)
        dst.update_tags(**tags)
    rename_with_retry(tmp, tif)

    da = xr.DataArray(
        arr, dims=("band", "lat", "lon"),
        coords={"band": np.arange(1, 13, dtype="int16"),
                "lat": template.y.values.astype("float64"),
                "lon": template.x.values.astype("float64")},
        name=var)
    da.attrs = {"units": units, "long_name": f"{var} {kind}",
                "cell_methods": "per calendar month"}
    da.lat.attrs = {"standard_name": "latitude", "units": "degrees_north"}
    da.lon.attrs = {"standard_name": "longitude", "units": "degrees_east"}
    ds = da.to_dataset()
    ds.attrs = {"title": f"{var} {ssp} {kind}, {window} over {REFERENCE}", **tags}
    ds = ds.rio.write_crs(template.rio.crs)

    nc = out_dir / f"{stem}.nc"
    tmpn = nc.with_suffix(".nc.tmp")
    ds.to_netcdf(tmpn, encoding={var: {"zlib": True, "complevel": 4,
                                       "dtype": "float32",
                                       "_FillValue": np.float32(np.nan)}})
    ds.close()
    rename_with_retry(tmpn, nc)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def process(var, ssps, additive, overwrite, out_dir):
    log = [f"=== {var} ({'difference' if additive else 'ratio'}) ==="]
    made = 0

    hp = hist_path(var)
    if not hp.exists():
        return log + [f"  SKIP - no historical file {hp.name}"], 0

    template = rioxarray.open_rasterio(NLUM_MASK).sel(band=1, drop=True)
    valid = template.values == 1

    with rasterio.open(hp) as ds:
        hist = ds.read()
        src_units = ds.tags().get("units", "")

    for ssp in ssps:
        for window in WINDOWS:
            fp = fut_path(var, ssp, window)
            if not fp.exists():
                log.append(f"  {ssp} {window}: SKIP - missing {fp.name}")
                continue
            stem = out_stem(var, ssp, window, additive)
            if (out_dir / f"{stem}.tif").exists() and not overwrite:
                continue

            with rasterio.open(fp) as ds:
                fut = ds.read()
            if fut.shape != hist.shape:
                log.append(f"  {ssp} {window}: SKIP - shape {fut.shape} vs "
                           f"historical {hist.shape}")
                continue

            arr, undefined = combine(fut, hist, additive)
            arr = np.where(valid, arr, np.nan).astype("float32")
            write_outputs(arr, stem, var, ssp, window, additive, template,
                          src_units, out_dir)
            made += 1

            v = arr[:, valid]
            finite = np.isfinite(v)
            extreme = int((np.abs(v[finite]) > 10).sum()) if not additive else 0
            note = (f"  {ssp} {WINDOWS[window]:<4} {window}: "
                    f"{np.nanmin(v):8.3f}..{np.nanmax(v):9.3f}  "
                    f"median {np.nanmedian(v):6.3f}")
            if undefined:
                note += f"  undefined(hist=0) {undefined:,}"
            if extreme:
                note += f"  |ratio|>10 {extreme:,} ({100 * extreme / finite.sum():.2f}%)"
            log.append(note)

    return log, made


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Future / historical change factors from the CSIRO "
                    "climatologies.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--vars", nargs="+", default=None, metavar="VAR",
                   help="default: every variable present in both folders")
    p.add_argument("--ssps", nargs="+", default=SSPS, choices=SSPS, metavar="SSP")
    p.add_argument("--additive", action="store_true",
                   help="write future - historical instead of the ratio; the "
                        "physically meaningful form for temperature")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="output folder; defaults to CSIRO_Delta for ratios "
                        "and CSIRO_Delta_additive for --additive")
    p.add_argument("--workers", type=int, default=N_WORKERS)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    vars_ = args.vars or variables()
    # Passed to every worker explicitly: loky spawns fresh processes that
    # re-import this module, so a mutated global would not reach them.
    out_dir = args.out_dir or (OUT_DIR_ADDITIVE if args.additive else OUT_DIR)
    kind = "difference (future - historical)" if args.additive \
        else "ratio (future / historical)"

    print(f"numerator  : {FUT_DIR}")
    print(f"denominator: {HIST_DIR}  ({REFERENCE})")
    print(f"output     : {out_dir}")
    print(f"quantity   : {kind}")
    print(f"variables  : {', '.join(vars_)}")
    print(f"windows    : " + ", ".join(f"{w} ({l})" for w, l in WINDOWS.items()))
    print(f"outputs    : {len(vars_)} x {len(args.ssps)} x {len(WINDOWS)} = "
          f"{len(vars_) * len(args.ssps) * len(WINDOWS)} (each .tif and .nc)\n")

    if not args.additive:
        temp = [v for v in vars_ if v in INTERVAL_SCALE]
        if temp:
            print(f"NOTE: {', '.join(temp)} are in degC, an interval scale, so a "
                  "ratio has no\n      physical meaning for them. Written as "
                  "asked; use --additive for the\n      meaningful form.\n")

    if args.dry_run:
        for v in vars_:
            for s in args.ssps:
                for w in WINDOWS:
                    print(f"  {out_stem(v, s, w, args.additive)}")
        return 0

    results = Parallel(n_jobs=max(1, args.workers), backend="loky", verbose=5)(
        delayed(process)(v, args.ssps, args.additive, args.overwrite, out_dir)
        for v in vars_)

    total = 0
    for log, made in results:
        print("\n".join(log))
        total += made
    print(f"\nDone. {total} file pair(s) written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
