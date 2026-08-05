"""
Predict future FPI for every ACCESS-CM2 scenario x period.

Adapted from Refactor_JZ/Step_03_prediction.py. The future climate now comes
straight from this project's Data/Processed, which is already NLUM-matched, so
no reprojection happens here.

For each (ssp, period) the 55 future climate bands are combined with the 12
static soil bands taken from X_data.nc, giving the same 67-band predictor stack
and the same band order the model was trained on:

    Soil_N_1..6, Soil_P_1..6, Bio_1..19, Precip_1..12, Tmax_1..12, Tmin_1..12

Reads  data/X_data.nc, data/random_forest_model.pkl, Data/Processed/*
Writes output/future_<ssp>_<period>_prediction.tif

Two fixes relative to the original
----------------------------------
1. Prediction is run only on cells where every predictor is finite. sklearn
   1.3.0 raises "Input X contains NaN" from RandomForestRegressor.predict, and
   ~6.7 M of the 13.7 M cells per band are NaN outside the NLUM mask, so
   predicting on the full grid fails outright. Masked cells are written as NaN.
2. compress='lzp' was not a valid GDAL creation option; it is 'lzw'.
"""

import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray as rxr
import xarray as xr

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"

STEP_DIR = Path(__file__).resolve().parent
DATA_DIR = STEP_DIR / "data"
OUTPUT_DIR = STEP_DIR / "output"

X_PATH = DATA_DIR / "X_data.nc"
MODEL_PATH = DATA_DIR / "random_forest_model.pkl"

# Future climate variables: Data/Processed sub-directory -> (band count, X prefix)
FUTURE_VARS = {
    "bioc": (19, "Bio"),
    "prec": (12, "Precip"),
    "tmax": (12, "Tmax"),
    "tmin": (12, "Tmin"),
}

# Write the assembled 55-band future stacks to NetCDF as well (~700 MB each,
# ~11 GB for all 16). Off by default - the prediction loop does not need them.
SAVE_FUTURE_NC = False

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Index the future rasters
# --------------------------------------------------------------------------- #

re_type = re.compile(r"30s_(.*)_ACCESS")
re_ssp = re.compile(r"CM2_(.*)_\d{4}")
re_year = re.compile(r"(\d{4}-\d{4})")

records = []
for var in FUTURE_VARS:
    for fp in sorted((PROCESSED_DIR / var).glob("*.tif")):
        records.append({
            "file_path": fp,
            "type": re_type.findall(fp.name)[0],
            "ssp": re_ssp.findall(fp.name)[0],
            "year": re_year.findall(fp.name)[0],
        })

TIF_info_df = pd.DataFrame(records)
print(f"{len(TIF_info_df)} future rasters across "
      f"{TIF_info_df.groupby(['ssp', 'year']).ngroups} scenario x period combinations")


# --------------------------------------------------------------------------- #
# Static predictors and model
# --------------------------------------------------------------------------- #

ds_all = xr.open_dataset(X_PATH)["data"]

soil_bands = [b for b in ds_all.band.values if "Soil" in b]
ds_soil = ds_all.sel(band=soil_bands)
ds_not_soil = ds_all.sel(band=~ds_all.band.isin(soil_bands))

print(f"soil bands   : {len(soil_bands)}")
print(f"climate bands: {ds_not_soil.band.size}")

with open(MODEL_PATH, "rb") as m:
    model = pickle.load(m)

# Georeferencing template for the output rasters. Selecting band 1 leaves the
# array 2D but keeps the source's long_name attribute, which still lists all
# 12/19 source band names - rioxarray then refuses to write with
# "Number of names in the 'long_name' attribute does not equal the number of
# bands". Drop it and name the single output band instead.
TIFF_ref = rxr.open_rasterio(TIF_info_df.iloc[0]["file_path"]).sel(band=1).astype(np.float32)
TIFF_ref.attrs.pop("long_name", None)
TIFF_ref.attrs["long_name"] = "FPI_prediction"


# --------------------------------------------------------------------------- #
# Predict, one scenario x period at a time
# --------------------------------------------------------------------------- #

for (ssp, year), df in TIF_info_df.groupby(["ssp", "year"]):
    # Start from NaN so a variable missing for this group stays NaN rather than
    # silently becoming zero (the original seeded with np.zeros).
    ds = xr.DataArray(
        np.full(ds_not_soil.shape, np.nan, dtype="float32"),
        coords={"band": ds_not_soil.band, "y": ds_not_soil.y, "x": ds_not_soil.x},
        name="data",
    )

    for _, row in df.iterrows():
        n_bands, prefix = FUTURE_VARS[row["type"]]
        band_names = [f"{prefix}_{i}" for i in range(1, n_bands + 1)]
        ds.loc[{"band": band_names}] = rxr.open_rasterio(row["file_path"]).squeeze().values

    if SAVE_FUTURE_NC:
        ds.to_netcdf(
            DATA_DIR / f"future_{ssp}_{year}.nc",
            encoding={ds.name: {"zlib": True, "complevel": 4}},
            engine="netcdf4",
        )

    # Soil first, then climate - matches the training band order.
    ds_cat = xr.concat([ds_soil, ds], dim="band")
    ds_2D = ds_cat.stack(cell=("y", "x")).reset_index("cell").transpose("cell", "band")

    X = ds_2D.values
    finite = np.isfinite(X).all(axis=1)

    pred_1D = np.full(X.shape[0], np.nan, dtype="float32")
    pred_1D[finite] = model.predict(X[finite])
    pred_2D = pred_1D.reshape(ds.sizes["y"], ds.sizes["x"])

    out_path = OUTPUT_DIR / f"future_{ssp}_{year}_prediction.tif"
    pred_xr = TIFF_ref.copy()
    pred_xr.data = pred_2D
    pred_xr.rio.to_raster(out_path, compress="lzw")

    v = pred_2D[np.isfinite(pred_2D)]
    print(f"{ssp} {year}: predicted {finite.sum():,} of {X.shape[0]:,} cells  "
          f"range {v.min():.3f}..{v.max():.3f}  mean {v.mean():.3f}  -> {out_path.name}")

print(f"\nwrote {len(list(OUTPUT_DIR.glob('*_prediction.tif')))} prediction rasters to {OUTPUT_DIR}")
