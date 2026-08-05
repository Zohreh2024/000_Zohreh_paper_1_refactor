"""
Build the X (predictor) and Y (target) stacks for the FPI random forest.

Adapted from
  N:/Current-Users/ZOHREH-KALAHROUDI/Random Forest/final_rf/Refactor_JZ
to read from this project's Data/Processed, which is already clipped,
reprojected, gap-filled and masked to the NLUM grid (3364 x 4071, GDA94).

X band order is unchanged from the original so an existing model stays valid:

    Soil_N_1..6    Data/Processed/soil_N   (6 depth slices, 1 band each)
    Soil_P_1..6    Data/Processed/soil_P   (6 depth slices, 1 band each)
    Bio_1..19      historical bioclim      (19 files, 1 band each)
    Precip_1..12   historical monthly
    Tmax_1..12     historical monthly
    Tmin_1..12     historical monthly
                                            -> 67 bands total

Everything now comes from Data/Processed - historical climate and the FPI target
included - so training and prediction inputs went through exactly the same
clip / reproject / fill / mask path (Step_0/reproject_match_NLUM.py and
Step_0/mosaic_match_fpi_NLUM.py).

This replaces the legacy random_forest_final_input directory, whose historical
climate was stored as uint8: temperatures quantised to whole degrees and
precipitation saturated at 255 mm, while the future rasters the model predicts
on are float32 reaching ~850 mm. Training and prediction were on different
footings; they are not any more.
"""

from pathlib import Path

import rioxarray as rxr
import xarray as xr

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"
DATA_DIR = Path(__file__).resolve().parent / "data"

SOIL_N_DIR = PROCESSED_DIR / "soil_N"
SOIL_P_DIR = PROCESSED_DIR / "soil_P"

# Historical climate: WorldClim 2.1 1970-2000, one single-band raster per
# bioclim variable / month.
HIST_DIRS = {
    "bio": PROCESSED_DIR / "hist_bio",
    "prec": PROCESSED_DIR / "hist_prec",
    "tmax": PROCESSED_DIR / "hist_tmax",
    "tmin": PROCESSED_DIR / "hist_tmin",
}

# Y target: mean FPI over the same 1970-2000 window as the climate baseline.
Y_FPI_PATH = PROCESSED_DIR / "fpi" / "fpi_avg_1970_2000.tif"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def stack_single_band(paths, prefix):
    """Concatenate single-band rasters into one DataArray with named bands.

    `paths` must already be in the intended band order - it is used as given.
    """
    paths = list(paths)
    if not paths:
        raise FileNotFoundError(f"no rasters found for {prefix}")
    das = [rxr.open_rasterio(p).squeeze() for p in paths]
    out = xr.concat(das, dim="band").squeeze()
    return out.assign_coords(band=[f"{prefix}_{i + 1}" for i in range(out.band.size)])


def hist_climate_paths(var, count):
    """Historical climate files for `var`, ordered 1..count by their index.

    Ordering numerically is essential: Data/Processed/hist_bio sorts lexically as
    bio_1, bio_10, bio_11, ... bio_8, bio_9, which would silently scramble the
    19 bioclim bands. bio is named _1..._19, the monthly sets _01..._12, so both
    spellings are tried.
    """
    folder = HIST_DIRS[var]
    ordered = []
    for i in range(1, count + 1):
        hits = sorted(folder.glob(f"*_{i}.tif")) or sorted(folder.glob(f"*_{i:02d}.tif"))
        if len(hits) != 1:
            raise FileNotFoundError(
                f"expected exactly 1 file for {var} index {i} in {folder}, got {len(hits)}"
            )
        ordered.append(hits[0])
    return ordered


# --------------------------------------------------------------------------- #
# Build X
# --------------------------------------------------------------------------- #

soil_N = stack_single_band(sorted(SOIL_N_DIR.glob("*.tif")), "Soil_N")
soil_P = stack_single_band(sorted(SOIL_P_DIR.glob("*.tif")), "Soil_P")

climate_bio = stack_single_band(hist_climate_paths("bio", 19), "Bio")
climate_prec = stack_single_band(hist_climate_paths("prec", 12), "Precip")
climate_tmax = stack_single_band(hist_climate_paths("tmax", 12), "Tmax")
climate_tmin = stack_single_band(hist_climate_paths("tmin", 12), "Tmin")

X_ds = xr.concat(
    [soil_N, soil_P, climate_bio, climate_prec, climate_tmax, climate_tmin],
    dim="band",
)

Y_ds = rxr.open_rasterio(Y_FPI_PATH).squeeze()

print(f"X: {X_ds.shape}  bands {X_ds.band.size}")
print(f"   {list(X_ds.band.values)}")
print(f"Y: {Y_ds.shape}")


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #

X_ds.name = "data"
Y_ds.name = "data"

X_ds.to_netcdf(
    DATA_DIR / "X_data.nc",
    encoding={X_ds.name: {"zlib": True, "complevel": 4}},
    engine="netcdf4",
)
Y_ds.to_netcdf(
    DATA_DIR / "Y_data.nc",
    encoding={Y_ds.name: {"zlib": True, "complevel": 4}},
    engine="netcdf4",
)

print(f"\nwrote {DATA_DIR / 'X_data.nc'}")
print(f"wrote {DATA_DIR / 'Y_data.nc'}")
