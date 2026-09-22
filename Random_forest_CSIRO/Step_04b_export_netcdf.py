"""
Re-express the projected FPI rasters as NetCDF cubes.

Reads   output/fpi_<ssp>_<year>.tif, output/fpi_<ssp>_<period>_mean.tif
Writes  output/netcdf/fpi_<ssp>_<period>.nc      8 files, 30 years each
        output/netcdf/fpi_all_period_means.nc    the 8 window means in one file

One file per scenario per window, holding

    fpi       (year, lat, lon)   the 30 individual years
    fpi_mean  (lat, lon)         that window's mean

which follows the project's existing `<var>_<SSP>_<period>.nc` convention and,
more importantly, keeps the two windows in separate files. CSIRO separated
2035-2064 from 2070-2099 deliberately so that users would not join them - the
five intervening years are not in the delivered dataset - and a single cube with
a 60-long year axis invites exactly the interpolation across that gap that the
data does not support.

The GeoTIFFs remain the primary output; nothing is recomputed here, so the cubes
cannot disagree with them. `lat` descends, matching the rasters' row order and
the NLUM grid, rather than being flipped to ascending: flipping would silently
disagree with every other raster in the project.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rioxarray as rxr
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUTPUT_DIR, SSPS, nlum_template

NC_DIR = OUTPUT_DIR / "netcdf"
PERIODS = {"2035-2064": list(range(2035, 2065)),
           "2070-2099": list(range(2070, 2100))}

ENCODING = {"zlib": True, "complevel": 4, "dtype": "float32",
            "_FillValue": np.float32(np.nan)}


def base_attrs():
    return {
        "title": "Projected Forest Productivity Index from a random forest on "
                 "CSIRO BARRA-R2 / QDC-CMIP6 climate",
        "source": "Step_04_predict_future.py",
        "model": "RandomForestRegressor, 64 trees, trained on 1985-2014 "
                 "(30 years x 69,564 cells)",
        "predictors": "83 static soil bands (held constant into the future) + "
                      "91 annual climate features",
        "climate_forcing": "ACCESS-CM2 r4i1p1f1, quantile-delta change applied "
                           "multiplicatively to observed BARRA-R2 1985-2014",
        "grid": "NLUM 3364 x 4071, 0.01 degree, GDA94",
        "units": "1 (dimensionless index)",
        "caveat": "A random forest cannot extrapolate beyond its training "
                  "envelope; late-century high-forcing years are conservative "
                  "by construction.",
    }


def build(ssp, period, years, tpl):
    paths = [(y, OUTPUT_DIR / f"fpi_{ssp}_{y}.tif") for y in years]
    have = [(y, p) for y, p in paths if p.exists()]
    if not have:
        return None
    if len(have) != len(years):
        print(f"  {ssp} {period}: only {len(have)} of {len(years)} years present")

    cube = np.empty((len(have), tpl.sizes["y"], tpl.sizes["x"]), dtype=np.float32)
    for i, (_, p) in enumerate(have):
        cube[i] = rxr.open_rasterio(p, masked=True).squeeze(drop=True).values

    coords = {"year": np.array([y for y, _ in have], dtype=np.int16),
              "lat": tpl.y.values, "lon": tpl.x.values}
    ds = xr.Dataset(
        {"fpi": (("year", "lat", "lon"), cube)},
        coords=coords,
        attrs={**base_attrs(), "scenario": ssp, "period": period,
               "n_years": len(have)},
    )

    mean_path = OUTPUT_DIR / f"fpi_{ssp}_{period}_mean.tif"
    if mean_path.exists():
        ds["fpi_mean"] = (("lat", "lon"),
                          rxr.open_rasterio(mean_path, masked=True)
                          .squeeze(drop=True).values.astype(np.float32))
    else:
        ds["fpi_mean"] = (("lat", "lon"), np.nanmean(cube, axis=0))

    ds["fpi"].attrs = {"long_name": "Forest Productivity Index, projected",
                       "units": "1"}
    ds["fpi_mean"].attrs = {"long_name": f"FPI mean over {period}", "units": "1"}
    ds["lat"].attrs = {"units": "degrees_north", "standard_name": "latitude"}
    ds["lon"].attrs = {"units": "degrees_east", "standard_name": "longitude"}
    return ds


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ssp", nargs="*", default=SSPS)
    args = ap.parse_args()

    NC_DIR.mkdir(parents=True, exist_ok=True)
    tpl = nlum_template()
    t0 = time.time()

    means = {}
    for ssp in args.ssp:
        for period, years in PERIODS.items():
            ds = build(ssp, period, years, tpl)
            if ds is None:
                print(f"  {ssp} {period}: no rasters, skipped")
                continue
            # Write the CRS the way rioxarray does, so QGIS and friends read the
            # cube as georeferenced rather than as a bare array.
            ds = ds.rio.write_crs(tpl.rio.crs).rio.write_transform(tpl.rio.transform())
            out = NC_DIR / f"fpi_{ssp}_{period}.nc"
            ds.to_netcdf(out, engine="netcdf4",
                         encoding={"fpi": ENCODING, "fpi_mean": ENCODING})
            print(f"wrote {out.name:34s} fpi {tuple(ds.fpi.shape)}  "
                  f"{out.stat().st_size / 1e6:7.0f} MB")
            means[(ssp, period)] = ds["fpi_mean"].values
            ds.close()

    if means:
        keys = list(means)
        stacked = np.stack([means[k] for k in keys])
        ds = xr.Dataset(
            {"fpi_mean": (("scenario_period", "lat", "lon"), stacked)},
            coords={"scenario_period": np.array([f"{s}_{p}" for s, p in keys]),
                    "lat": tpl.y.values, "lon": tpl.x.values},
            attrs={**base_attrs(),
                   "note": "the eight window means in one file, for convenience"},
        )
        ds = ds.rio.write_crs(tpl.rio.crs)
        out = NC_DIR / "fpi_all_period_means.nc"
        ds.to_netcdf(out, engine="netcdf4", encoding={"fpi_mean": ENCODING})
        print(f"wrote {out.name:34s} {tuple(ds.fpi_mean.shape)}  "
              f"{out.stat().st_size / 1e6:7.0f} MB")

    print(f"\n{time.time() - t0:.0f}s -> {NC_DIR}")


if __name__ == "__main__":
    main()
