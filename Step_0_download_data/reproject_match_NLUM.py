"""
Clip WorldClim global rasters to Australia, match them to the NLUM grid,
fill gaps, and mask to NLUM's valid cells.

Per raster, for every band:
    1. clip   - windowed read of the NLUM bounding box (+ buffer) out of the
                global 43200 x 21600 source, so we never load the whole world
    2. match  - rio.reproject_match onto the NLUM template: WGS 84 -> GDA94,
                0.008333 deg -> 0.01 deg, snapped to NLUM's exact grid
    3. fill   - NaN cells take the value of the nearest valid cell
    4. mask   - cells outside the NLUM mask (mask == 0) are set to NaN

Data/Raw/<variable>/<name>.tif  ->  Data/Processed/<variable>/<name>.tif

Follows tools/raster.py from
https://github.com/JinzhuWANG/LUTO_2.0_input_data_Scripts
with two deliberate differences, both driven by the actual data:
  * WorldClim rasters carry 12 monthly bands (19 for bioc), not 1. Every band
    is processed; the reference's `.sel(band=1)` would drop the rest.
  * The reference's `fill_with_nearest(to_fill=0)` treats 0 as a gap. For
    temperature 0 degC is a real value, so only NaN is filled here.
"""

import os
from pathlib import Path

import numpy as np
import rasterio
import rioxarray
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy.ndimage import distance_transform_edt
from tqdm.auto import tqdm

# A PostgreSQL/PostGIS proj.db on PATH shadows the conda one and makes GDAL emit
# "PROJ: proj_identify ... lacks DATABASE.LAYOUT.VERSION" errors. Point PROJ at
# this environment's own database.
_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
RAW_DIR = PROJECT_ROOT / "Data" / "Raw"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

RESAMPLING = Resampling.bilinear   # continuous data; use nearest for categorical

# Skip rasters that already have an output, so a re-run only picks up what is
# new - e.g. files that failed the first download and arrived later. Set False to
# reprocess everything from scratch.
SKIP_EXISTING = True


def todo(variable):
    """Raw rasters for `variable` that still need processing.

    Downloads still in flight are named *.tif.part, so the *.tif glob only ever
    sees rasters that finished downloading.
    """
    files = sorted((RAW_DIR / variable).glob("*.tif"))
    if SKIP_EXISTING:
        files = [f for f in files if not (PROCESSED_DIR / variable / f.name).exists()]
    print(f"{variable}: {len(files)} raster(s) to process")
    return files

# Degrees of slack around the NLUM bounds when clipping the global source. Gives
# the resampler and the nearest-neighbour fill real data just outside the
# template instead of edge-of-array NaN.
CLIP_BUFFER_DEG = 0.5

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


# --------------------------------------------------------------------------- #
# Raster helpers
# --------------------------------------------------------------------------- #

def fill_with_nearest(arr):
    """Replace NaN cells with the value of the nearest non-NaN cell.

    Only NaN counts as a gap - unlike the reference implementation, zero is left
    alone, because 0 degC / 0 mm are meaningful values in this data.
    """
    gaps = np.isnan(arr)
    if not gaps.any():
        return arr
    if gaps.all():
        raise ValueError("band is entirely NaN - nothing to fill from")
    idx = distance_transform_edt(gaps, return_distances=False, return_indices=True)
    return arr[tuple(idx)]


def clip(src_path, template, buffer_deg=CLIP_BUFFER_DEG):
    """Cut the template's bounding box (+ buffer) out of a global raster.

    Opened lazily and chunked per band, so this is a windowed read - the global
    43200 x 21600 array is never materialised. The buffer gives the resampler and
    the nearest-neighbour fill real data just outside the template instead of
    edge-of-array NaN.

    Returns a DataArray that still carries its band dimension.
    """
    west, south, east, north = template.rio.bounds()
    raw = rioxarray.open_rasterio(src_path, masked=True, chunks={"band": 1})
    return raw.rio.clip_box(
        west - buffer_deg,
        south - buffer_deg,
        east + buffer_deg,
        north + buffer_deg,
    )


def reproject_match(clipped, template, resampling=RESAMPLING, desc=""):
    """Reproject every band of `clipped` onto the template grid.

    Handles CRS (WGS 84 -> GDA94), resolution (0.008333 -> 0.01 deg) and grid
    alignment in one step. Bands are done one at a time to keep peak memory to a
    single band rather than all 12.

    Returns a (band, y, x) float32 array on the template's exact grid.
    """
    n_bands = clipped.sizes["band"]
    out = np.empty((n_bands, template.rio.height, template.rio.width), dtype="float32")
    for i in tqdm(range(n_bands), desc=desc, unit="band", leave=False):
        band = clipped.isel(band=i).load()
        out[i] = band.rio.reproject_match(template, resampling=resampling).values
    return out


def fill(arr, valid):
    """Fill each band's NaN gaps from the nearest valid cell, then apply the mask.

    Order matters: fill first so coastal cells that the source leaves NaN pick up
    a real value, then blank everything outside the NLUM mask.
    """
    out = np.empty_like(arr)
    for i, band in enumerate(arr):
        out[i] = np.where(valid, fill_with_nearest(band), np.nan)
    return out


def write_gtiff(arr, dst_path, template, descriptions=()):
    """Write a (band, y, x) array as a GeoTIFF on the template's grid."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a .tmp first so an interrupted run never leaves a half-written tif.
    tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
    with rasterio.open(
        tmp_path,
        "w",
        height=template.rio.height,
        width=template.rio.width,
        count=arr.shape[0],
        crs=template.rio.crs,
        transform=template.rio.transform(),
        **CREATION_OPTS,
    ) as dst:
        dst.write(arr)
        for i, description in enumerate(descriptions, start=1):
            if description:
                dst.set_band_description(i, description)
    tmp_path.replace(dst_path)
    return dst_path


def band_descriptions(src_path):
    """The source's per-band names, e.g. ('wc2.1_30s_tmin_01', ...)."""
    with rasterio.open(src_path) as src:
        return src.descriptions


def stream_match(src_path, template, resampling):
    """Reproject straight onto the NLUM grid without loading the source.

    The clip + rioxarray path above materialises the clipped extent in memory,
    which is fine for WorldClim (~80 MB a band) but not for the soil grids:
    soil_N is 40800 x 49200 at ~90 m, so one band over the NLUM box is ~7.9 GB.
    Here GDAL reads only the source windows it needs and writes directly into the
    destination array - measured peak RSS 0.21 GB for soil_N.

    No separate clip step is needed: the destination defines the extent, so
    anything outside the NLUM box is never read. src_nodata is honoured, so
    soil_P's -9999 becomes NaN before resampling rather than being averaged in.

    Returns a (band, y, x) float32 array on the template's exact grid.
    """
    with rasterio.open(src_path) as src:
        out = np.full(
            (src.count, template.rio.height, template.rio.width),
            np.nan, dtype="float32",
        )
        for i in range(src.count):
            reproject(
                source=rasterio.band(src, i + 1),
                destination=out[i],
                src_nodata=src.nodata,
                dst_transform=template.rio.transform(),
                dst_crs=template.rio.crs,
                dst_nodata=np.nan,
                resampling=resampling,
                num_threads=4,
            )
    return out


# --------------------------------------------------------------------------- #
# Load the NLUM template and its valid-cell mask
# --------------------------------------------------------------------------- #

template = rioxarray.open_rasterio(NLUM_MASK).sel(band=1, drop=True)
valid = template.values == 1

print(f"template : {template.rio.height} x {template.rio.width}")
print(f"valid    : {valid.sum():,} of {valid.size:,} cells")


# --------------------------------------------------------------------------- #
# tmin - monthly minimum temperature, 12 bands, degC
# --------------------------------------------------------------------------- #

for src in tqdm(todo("tmin"), desc="tmin", unit="file"):
    dst = PROCESSED_DIR / "tmin" / src.name
    clipped = clip(src, template)
    matched = reproject_match(clipped, template, desc=src.name)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))
    clipped.close()

    # Stay quiet on success; only speak up if the grid drifted off NLUM or the
    # fill left a hole inside the mask. Both should be impossible.
    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )


# --------------------------------------------------------------------------- #
# tmax - monthly maximum temperature, 12 bands, degC
# --------------------------------------------------------------------------- #

for src in tqdm(todo("tmax"), desc="tmax", unit="file"):
    dst = PROCESSED_DIR / "tmax" / src.name
    clipped = clip(src, template)
    matched = reproject_match(clipped, template, desc=src.name)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))
    clipped.close()

    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )


# --------------------------------------------------------------------------- #
# prec - monthly precipitation, 12 bands, mm
#
# Unlike the other three, the source is int16 with nodata -32768. masked=True in
# clip() converts that sentinel to NaN and promotes to float32 before any
# resampling, so -32768 never gets averaged into coastal cells. Verified: a
# clipped band holds 10,745,592 nodata cells, all NaN after masking, leaving a
# real range of 1-896 mm.
# --------------------------------------------------------------------------- #

for src in tqdm(todo("prec"), desc="prec", unit="file"):
    dst = PROCESSED_DIR / "prec" / src.name
    clipped = clip(src, template)
    matched = reproject_match(clipped, template, desc=src.name)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))
    clipped.close()

    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )


# --------------------------------------------------------------------------- #
# bioc - 19 bioclimatic variables, 19 bands, mixed units
#
# BIO1-11 are temperature (degC), BIO12-19 precipitation (mm) and ratios. All are
# continuous, so bilinear is fine across the set, but the bands are NOT
# interchangeable - check units before comparing bands downstream.
# --------------------------------------------------------------------------- #

for src in tqdm(todo("bioc"), desc="bioc", unit="file"):
    dst = PROCESSED_DIR / "bioc" / src.name
    clipped = clip(src, template)
    matched = reproject_match(clipped, template, desc=src.name)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))
    clipped.close()

    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )


# --------------------------------------------------------------------------- #
# hist_* - WorldClim 2.1 historical climate, 1970-2000
#
# These are what the FPI random forest TRAINS on, while the future scenarios
# above are what it predicts on, so both must be processed identically -
# same clip, same bilinear resampling, same fill, same mask. Anything else puts
# training and prediction on different footings.
#
# Layout differs from the CMIP6 products: historical ships one single-band
# raster per month (or per bioclim variable), not one multi-band file per
# scenario. Band count is therefore 1 and the loop body is unchanged; only the
# number of files differs (19 for bio, 12 each for prec/tmax/tmin).
#
# Note the variable code: historical bioclim is `bio`, CMIP6 bioclim is `bioc`.
# --------------------------------------------------------------------------- #

for variable in ["hist_bio", "hist_prec", "hist_tmax", "hist_tmin"]:
    for src in tqdm(todo(variable), desc=variable, unit="file"):
        dst = PROCESSED_DIR / variable / src.name
        clipped = clip(src, template)
        matched = reproject_match(clipped, template, desc=src.name)
        filled = fill(matched, valid)
        write_gtiff(filled, dst, template, band_descriptions(src))
        clipped.close()

        nan_in_mask = np.isnan(filled[:, valid]).sum()
        if filled.shape[1:] != valid.shape or nan_in_mask:
            print(
                f"[WARN] {dst.name}\n"
                f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
                f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
                f"       nan in mask  {nan_in_mask:,}\n"
                f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
            )


# --------------------------------------------------------------------------- #
# soil_N - total soil nitrogen, 6 depth slices, 1 band each, % w/w
#
# WGS 84 at ~90 m (40800 x 49200), so 12x finer than NLUM in each direction.
# Resampled with AVERAGE, not bilinear: each output cell aggregates all ~144
# source cells it covers instead of point-sampling one of them. Uses
# stream_match() because a single band over the NLUM box would be ~7.9 GB.
#
# The source starts at 112.9996E while NLUM reaches 112.925E, so the far west
# edge has no source data - fill() closes that gap from the nearest valid cell.
# --------------------------------------------------------------------------- #

for src in tqdm(todo("soil_N"), desc="soil_N", unit="file"):
    dst = PROCESSED_DIR / "soil_N" / src.name
    matched = stream_match(src, template, Resampling.average)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))

    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )


# --------------------------------------------------------------------------- #
# soil_P - soil phosphorus, 6 depth slices, 1 band each, % w/w
#
# Already GDA94 at 0.01 deg, so this is a half-cell grid shift rather than a real
# reprojection - bilinear blends the neighbours. nodata is -9999 (not NaN);
# stream_match() passes it as src_nodata so it becomes NaN before resampling
# instead of being blended into valid cells.
# --------------------------------------------------------------------------- #

for src in tqdm(todo("soil_P"), desc="soil_P", unit="file"):
    dst = PROCESSED_DIR / "soil_P" / src.name
    matched = stream_match(src, template, Resampling.bilinear)
    filled = fill(matched, valid)
    write_gtiff(filled, dst, template, band_descriptions(src))

    nan_in_mask = np.isnan(filled[:, valid]).sum()
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(
            f"[WARN] {dst.name}\n"
            f"       shape        {filled.shape[1:]} vs NLUM {valid.shape}\n"
            f"       valid cells  {valid.sum():,} of {valid.size:,} per band\n"
            f"       nan in mask  {nan_in_mask:,}\n"
            f"       nan total    {np.isnan(filled).sum():,} of {filled.size:,}"
        )
