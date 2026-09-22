"""
Audit every input against the NLUM grid before trusting any of it.

Reads   required_data/fpi/*.tif, required_data/Soil_data/**/*.tif,
        data/monthly_climate/**/*.nc  (a sample)
Writes  data/audit_inputs.csv, data/audit_masks.csv
        data/soil_incomplete_mask.tif   where soil is not complete but FPI is

Three questions, because getting any of them wrong is silent rather than loud:

1. Is every raster on the same grid? Soil is sampled by integer row/column
   index (`values[rows, cols]`), which is fast and exact when the grids match
   and quietly reads the wrong cells when they do not. A raster one pixel off,
   or on a different extent, produces a plausible map with the wrong numbers.
   Note that `soil_N` and `soil_P` are the two directories whose file names
   lack the `_NLUM` suffix the others carry, so they are the ones to look at.

2. Does the climate have gaps over Australia? It is bilinearly interpolated
   from 0.11 deg rather than pre-reprojected, and bilinear propagates a single
   NaN into the four cells around it. The BARRA-R2 domain covers ocean as well
   as land, so this is expected to be clean, but expected is not checked.

3. Is the soil footprint smaller than the FPI footprint? Cells with any NaN
   soil band are dropped from training and left NaN in the projection. If FPI
   exists where soil does not, the projection has holes that the target does
   not, and those holes are invisible in a domain mean.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray as rxr
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BBOX, CLIM_VARS, DATA_DIR, FPI_DIR, HIST_YEARS, SSPS,
                    monthly_path, nlum_template, soil_files)

FPI_YEARS_TO_CHECK = sorted(int(p.stem.split("_")[1]) for p in FPI_DIR.glob("fpi_*.tif"))


def grid_signature(path):
    da = rxr.open_rasterio(path, masked=True).squeeze(drop=True)
    t = da.rio.transform()
    return {
        "file": path.name,
        "dir": path.parent.name,
        "height": da.sizes["y"],
        "width": da.sizes["x"],
        "res_x": round(t.a, 10),
        "res_y": round(t.e, 10),
        "origin_x": round(t.c, 10),
        "origin_y": round(t.f, 10),
        "crs": str(da.rio.crs).split("\n")[0][:40],
        "dtype": str(da.dtype),
        "nodata": da.rio.nodata,
        "finite_pct": round(100 * float(np.isfinite(da.values).mean()), 3),
    }, np.isfinite(da.values)


def main():
    tpl = nlum_template()
    ref = grid_signature(FPI_DIR / f"fpi_{HIST_YEARS[0]}.tif")[0]
    print("reference grid (fpi_1985.tif):")
    for k in ("height", "width", "res_x", "res_y", "origin_x", "origin_y", "crs"):
        print(f"  {k:9s} {ref[k]}")

    rows = []
    soil_mask = np.ones((tpl.sizes["y"], tpl.sizes["x"]), dtype=bool)
    per_band_missing = []

    print(f"\nsoil: {len(soil_files())} rasters")
    for p in soil_files():
        sig, finite = grid_signature(p)
        sig["role"] = "soil"
        rows.append(sig)
        soil_mask &= finite
        per_band_missing.append((p.name, 100 - sig["finite_pct"]))

    print(f"fpi: {len(FPI_YEARS_TO_CHECK)} rasters")
    fpi_masks = {}
    for yr in FPI_YEARS_TO_CHECK:
        sig, finite = grid_signature(FPI_DIR / f"fpi_{yr}.tif")
        sig["role"] = "fpi"
        rows.append(sig)
        if yr in HIST_YEARS or yr == 2022:
            fpi_masks[yr] = finite

    df = pd.DataFrame(rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_DIR / "audit_inputs.csv", index=False)

    key = ["height", "width", "res_x", "res_y", "origin_x", "origin_y"]
    groups = df.groupby(key).size().reset_index(name="n")
    print(f"\ndistinct grids among {len(df)} rasters: {len(groups)}")
    print(groups.to_string(index=False))
    if len(groups) != 1:
        print("\nMISMATCH - the following do not share the reference grid:")
        bad = df[~df[key].eq(pd.Series({k: ref[k] for k in key})).all(axis=1)]
        print(bad[["dir", "file"] + key].to_string(index=False))

    crss = df["crs"].unique()
    print(f"\ndistinct CRS strings: {len(crss)} -> {list(crss)}")

    # ---------------------------------------------------------------- masks
    print("\nsoil completeness vs FPI footprint")
    mrows = []
    for yr, fmask in sorted(fpi_masks.items()):
        both = soil_mask & fmask
        fpi_only = fmask & ~soil_mask
        soil_only = soil_mask & ~fmask
        mrows.append({
            "year": yr,
            "fpi_cells": int(fmask.sum()),
            "soil_complete_cells": int(soil_mask.sum()),
            "both": int(both.sum()),
            "fpi_without_soil": int(fpi_only.sum()),
            "soil_without_fpi": int(soil_only.sum()),
            "pct_fpi_lost": round(100 * fpi_only.sum() / max(fmask.sum(), 1), 3),
        })
    md = pd.DataFrame(mrows)
    md.to_csv(DATA_DIR / "audit_masks.csv", index=False)
    print(md.to_string(index=False))

    worst = sorted(per_band_missing, key=lambda t: -t[1])[:10]
    print("\nsoil bands with the most missing data")
    for name, pct in worst:
        print(f"  {pct:7.3f}%  {name}")

    # Where FPI exists but soil does not - the cells the projection cannot fill.
    ref_year = 2022 if 2022 in fpi_masks else HIST_YEARS[-1]
    gap = (fpi_masks[ref_year] & ~soil_mask).astype(np.float32)
    if gap.sum():
        da = tpl.copy(data=np.where(gap > 0, 1.0, np.nan).astype(np.float32))
        da.attrs["long_name"] = f"fpi_{ref_year}_present_soil_incomplete"
        da.rio.to_raster(DATA_DIR / "soil_incomplete_mask.tif", compress="lzw")
        print(f"\nwrote {DATA_DIR / 'soil_incomplete_mask.tif'} "
              f"({int(gap.sum()):,} cells)")

    # ---------------------------------------------------------------- climate
    print("\nclimate: grid and NaN over the Australian crop")
    crows = []
    samples = [(v, HIST_YEARS[0], None) for v in CLIM_VARS]
    samples += [(v, 2035, "ssp245") for v in CLIM_VARS]
    samples += [("pr", 2099, s) for s in SSPS]
    for var, yr, ssp in samples:
        path = monthly_path(var, yr, ssp)
        if not path.exists():
            crows.append({"var": var, "year": yr, "set": ssp or "historical",
                          "status": "missing"})
            continue
        with xr.open_dataset(path) as ds:
            a = ds[var]
            crows.append({
                "var": var, "year": yr, "set": ssp or "historical",
                "status": "ok", "months": a.sizes["month"],
                "lat": a.sizes["lat"], "lon": a.sizes["lon"],
                "lat_min": round(float(a.lat.min()), 4),
                "lat_max": round(float(a.lat.max()), 4),
                "lon_min": round(float(a.lon.min()), 4),
                "lon_max": round(float(a.lon.max()), 4),
                "nan_pct": round(100 * float(np.isnan(a.values).mean()), 6),
                "min": round(float(np.nanmin(a.values)), 3),
                "max": round(float(np.nanmax(a.values)), 3),
            })
    cd = pd.DataFrame(crows)
    print(cd.to_string(index=False))
    cd.to_csv(DATA_DIR / "audit_climate.csv", index=False)

    # Does the climate crop enclose the NLUM grid, so bilinear never clips?
    with xr.open_dataset(monthly_path("pr", HIST_YEARS[0], None)) as ds:
        lat, lon = ds.lat.values, ds.lon.values
    print(f"\nNLUM y range   {float(tpl.y.min()):.4f} .. {float(tpl.y.max()):.4f}")
    print(f"climate lat    {lat.min():.4f} .. {lat.max():.4f}  "
          f"{'encloses' if lat.min() <= tpl.y.min() and lat.max() >= tpl.y.max() else 'CLIPS'}")
    print(f"NLUM x range   {float(tpl.x.min()):.4f} .. {float(tpl.x.max()):.4f}")
    print(f"climate lon    {lon.min():.4f} .. {lon.max():.4f}  "
          f"{'encloses' if lon.min() <= tpl.x.min() and lon.max() >= tpl.x.max() else 'CLIPS'}")
    print(f"BBOX used      {BBOX}")


if __name__ == "__main__":
    main()
