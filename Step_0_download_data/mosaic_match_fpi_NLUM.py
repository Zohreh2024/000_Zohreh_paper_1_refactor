"""
Mosaic the 37 FPI map-sheet tiles per year, then match the result to NLUM.

Per year (1970-2022):
    1. mosaic  - merge the 37 tiles into one continental raster
    2. match   - reproject/snap onto the NLUM grid
    3. fill    - NaN cells take the value of the nearest valid cell
    4. mask    - cells outside the NLUM mask are set to NaN

    Data/Raw/fpi/<tile>/<year>_001.tif  ->  Data/Processed/fpi/fpi_<year>.tif

and finally an average over AVG_YEARS -> Data/Processed/fpi/fpi_avg_<a>_<b>.tif,
which is the Y target for Step_1_RF_for_FPI.

Why the tiles still need reprojecting
-------------------------------------
They are already GDA94 at 0.01 deg - the same CRS and resolution as NLUM - but
their origin is offset by half a cell (e.g. tile sk55 starts at 143.81E, which
is 3088.5 NLUM cells from 112.925E). So this is a grid snap, not a true
reprojection, and bilinear blends the two straddling cells. Same situation as
soil_P in reproject_match_NLUM.py.

Tile nodata is -3.4e38 (float32 -FLT_MAX), passed as src_nodata so it becomes
NaN before resampling rather than being blended into valid cells.
"""

import os
from pathlib import Path

import numpy as np
import rasterio
import rioxarray
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.warp import reproject
from scipy.ndimage import distance_transform_edt
from tqdm.auto import tqdm

# A PostgreSQL/PostGIS proj.db on PATH shadows the conda one and makes GDAL emit
# "PROJ: proj_identify ... lacks DATABASE.LAYOUT.VERSION" errors.
_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
FPI_RAW_DIR = PROJECT_ROOT / "Data" / "Raw" / "fpi"
FPI_OUT_DIR = PROJECT_ROOT / "Data" / "Processed" / "fpi"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

YEARS = range(1970, 2023)          # 53 yearly rasters per tile
RESAMPLING = Resampling.bilinear   # continuous index, half-cell grid snap

# The average written at the end. 1970-2000 matches the WorldClim historical
# baseline the model trains on, and reproduces the 31-band legacy fpi_multiband.
AVG_YEARS = (1970, 2000)

SKIP_EXISTING = True

CREATION_OPTS = dict(
    driver="GTiff",
    dtype="float32",
    nodata=np.nan,
    compress="LZW",
    tiled=True,
    blockxsize=256,
    blockysize=256,
    BIGTIFF="IF_SAFER",
)

FPI_OUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def fill_with_nearest(arr):
    """Replace NaN cells with the value of the nearest non-NaN cell."""
    gaps = np.isnan(arr)
    if not gaps.any():
        return arr
    if gaps.all():
        raise ValueError("band is entirely NaN - nothing to fill from")
    idx = distance_transform_edt(gaps, return_distances=False, return_indices=True)
    return arr[tuple(idx)]


def mosaic_year(year):
    """Merge every tile's raster for `year` into one continental array.

    Returns (array, transform, crs, nodata). Australia at 0.01 deg is only about
    4200 x 3400 cells, so the mosaic fits comfortably in memory.
    """
    tiles = sorted(FPI_RAW_DIR.glob(f"*/{year}_*.tif"))
    if not tiles:
        raise FileNotFoundError(f"no tiles found for {year} under {FPI_RAW_DIR}")

    srcs = [rasterio.open(t) for t in tiles]
    try:
        # np.float32() is load-bearing. The tiles' nodata is -3.4028230607370965e+38,
        # which arrives from rasterio as a Python float (float64), and
        # np.can_cast(that, 'float32') is False under numpy's same-kind rule. merge()
        # then warns "Ignoring nodata value" and returns an array of ALL ZEROS -
        # every tile silently discarded. Casting to float32 first makes the check
        # pass and the merge behave. See the guard below.
        nodata = np.float32(srcs[0].nodata)
        arr, transform = merge(srcs, nodata=nodata)
        return arr[0], transform, srcs[0].crs, nodata, len(tiles)
    finally:
        for s in srcs:
            s.close()


def match_to_nlum(arr, transform, crs, nodata, template, resampling=RESAMPLING):
    """Reproject a mosaic onto the NLUM grid."""
    out = np.full((template.rio.height, template.rio.width), np.nan, dtype="float32")
    reproject(
        source=arr,
        destination=out,
        src_transform=transform,
        src_crs=crs,
        src_nodata=nodata,
        dst_transform=template.rio.transform(),
        dst_crs=template.rio.crs,
        dst_nodata=np.nan,
        resampling=resampling,
        num_threads=4,
    )
    return out


def write_gtiff(arr, dst_path, template, description=None):
    """Write a 2D array as a single-band GeoTIFF on the template's grid."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
    with rasterio.open(
        tmp_path,
        "w",
        height=template.rio.height,
        width=template.rio.width,
        count=1,
        crs=template.rio.crs,
        transform=template.rio.transform(),
        **CREATION_OPTS,
    ) as dst:
        dst.write(arr[np.newaxis, :, :])
        if description:
            dst.set_band_description(1, description)
    tmp_path.replace(dst_path)
    return dst_path


# --------------------------------------------------------------------------- #
# Load the NLUM template and its valid-cell mask
# --------------------------------------------------------------------------- #

template = rioxarray.open_rasterio(NLUM_MASK).sel(band=1, drop=True)
valid = template.values == 1

print(f"template : {template.rio.height} x {template.rio.width}")
print(f"valid    : {valid.sum():,} of {valid.size:,} cells")
print(f"tiles    : {len(sorted(FPI_RAW_DIR.glob('*/')))} directories under Data/Raw/fpi\n")


# --------------------------------------------------------------------------- #
# fpi - yearly mosaics matched to NLUM
# --------------------------------------------------------------------------- #

todo = [y for y in YEARS
        if not (SKIP_EXISTING and (FPI_OUT_DIR / f"fpi_{y}.tif").exists())]
print(f"{len(todo)} of {len(list(YEARS))} year(s) to process")

for year in tqdm(todo, desc="fpi", unit="year"):
    dst = FPI_OUT_DIR / f"fpi_{year}.tif"

    arr, transform, crs, nodata, n_tiles = mosaic_year(year)

    # Guard against a silently empty mosaic - see the np.float32 note in
    # mosaic_year(). A mosaic with no real cells means the merge dropped
    # everything, and the fill step downstream would happily turn that into a
    # plausible-looking constant raster.
    real = (arr != nodata) & np.isfinite(arr)
    if real.sum() == 0:
        raise ValueError(f"{year}: mosaic contains no real data - merge dropped every tile")

    matched = match_to_nlum(arr, transform, crs, nodata, template)
    filled = np.where(valid, fill_with_nearest(matched), np.nan)
    write_gtiff(filled, dst, template, description=f"FPI_{year}")

    nan_in_mask = np.isnan(filled[valid]).sum()
    if filled.shape != valid.shape or nan_in_mask or n_tiles != 37:
        print(
            f"[WARN] {dst.name}\n"
            f"       tiles merged {n_tiles} (expected 37)\n"
            f"       shape        {filled.shape} vs NLUM {valid.shape}\n"
            f"       nan in mask  {nan_in_mask:,} of {valid.sum():,}"
        )


# --------------------------------------------------------------------------- #
# Average over AVG_YEARS - the Y target for the random forest
# --------------------------------------------------------------------------- #

a, b = AVG_YEARS
avg_path = FPI_OUT_DIR / f"fpi_avg_{a}_{b}.tif"

stack = []
for year in range(a, b + 1):
    with rasterio.open(FPI_OUT_DIR / f"fpi_{year}.tif") as s:
        stack.append(s.read(1))

avg = np.nanmean(np.stack(stack), axis=0).astype("float32")
write_gtiff(avg, avg_path, template, description=f"FPI_mean_{a}_{b}")

v = avg[valid]
print(f"\n{avg_path.name}: {b - a + 1} years averaged")
print(f"  range {np.nanmin(v):.3f} .. {np.nanmax(v):.3f}  mean {np.nanmean(v):.3f}")
print(f"  nan in mask {np.isnan(v).sum():,} of {valid.sum():,}")
