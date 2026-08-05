"""
Download FullCAM's revised site potential (M), clip / reproject / fill it onto
the NLUM grid, and derive lambda against the original M.

Source: "Site potential (M) and FPI average versions 2.0", part of the Emissions
Reduction Fund environmental data on data.gov.au
  https://data.gov.au/data/dataset/emissions-reduction-fund-environmental-data
      /resource/1e3af98e-967a-4908-882f-2d217b0d0e5a

M (Maximum Above Ground Biomass) is FullCAM's site-potential layer.

The download is a 405.6 MB zip containing NESTED zips plus metadata PDFs. Only
New_M_2019 is taken; the FPIavg layer that ships alongside it is not used here,
because the FPI average this project needs is built from the yearly FPI rasters
in Data/Processed/fpi (see the lambda section below).

    Site potential and FPI version 2_0/
        New_M_2019.zip        375.5 MB -> New_M_2019.tif    (864 MB)
        *.pdf                            metadata, kept

    Data/Raw/maxAbgM_v2/New_M_2019.tif
        -> Data/Processed/maxAbgM_v2/New_M_2019.tif

Resampling: New_M_2019 is WGS 84 at 0.0025 deg - 4x finer than NLUM in each
direction, so one output cell covers ~16 source cells. Resampled with AVERAGE,
which aggregates all of them, rather than bilinear, which would point-sample.
Read via a streaming reproject: the full raster is 13900 x 16292 (226 M cells,
~906 MB as float32) and never needs to be in memory at once.

It carries a float32 -FLT_MAX-style nodata, passed as src_nodata so it becomes
NaN before resampling instead of being averaged into valid cells.

Lambda
------
    lambda = revised M / original M

where "original M" is FullCAM's site potential derived from the *historical*
FPI average over 1970-2002, via the FPI -> M relationship

    M = (6.011 * sqrt(FPI) - 5.291) ** 2

Both are reproduced from the legacy scripts:
  N:/Current-Users/ZOHREH-KALAHROUDI/M_FPI_P90/M_calculation_fpi90P.py  (formula)
  N:/Current-Users/ZOHREH-KALAHROUDI/Original_M/FPI_avg_1979-2002.py    (window;
      despite the filename it uses start_year=1970, end_year=2002)
  N:/Current-Users/ZOHREH-KALAHROUDI/Original_M/Original_M_calculation.py (ratio)

Watch the shape of that formula: it is a parabola in sqrt(FPI) with its root at
FPI = (5.291/6.011)^2 = 0.7748. M is only monotonic in FPI *above* that value -
below it, squaring makes M rise again as FPI falls, which is not physical. The
script reports how many cells fall below the root, and M near zero there is also
what makes the lambda division unstable, so both are guarded and counted.
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import rioxarray
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy.ndimage import distance_transform_edt
from tqdm.auto import tqdm

# Reuse the resumable downloader (its CLI is __main__-guarded, so importing runs nothing).
from download_worldclim_cmip6 import download

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Data" / "Raw"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

ZIP_DIR = RAW_DIR / "_maxabgm_zips"
ZIP_NAME = "site-potential-and-fpi-version-2_0.zip"
ZIP_URL = (
    "https://data.gov.au/data/dataset/b46c29a4-cc80-4bde-b538-51013dea4dcb"
    "/resource/1e3af98e-967a-4908-882f-2d217b0d0e5a/download/"
    + ZIP_NAME
)

# inner zip -> (raw sub-directory, tif name, resampling)
LAYERS = {
    "New_M_2019.zip": ("maxAbgM_v2", "New_M_2019.tif", Resampling.average),
}

CLIP_BUFFER_DEG = 0.5
SKIP_EXISTING = True

# --- lambda ---------------------------------------------------------------- #
FPI_DIR = PROCESSED_DIR / "fpi"
FPI_AVG_YEARS = (1970, 2002)        # window used for the ORIGINAL M
M_A, M_B = 6.011, 5.291             # M = (M_A * sqrt(FPI) - M_B) ** 2
M_ROOT = (M_B / M_A) ** 2           # 0.7748 - below this M stops being monotonic

OUT_M_DIR = PROCESSED_DIR / "maxAbgM_v2"
FPI_AVG_PATH = FPI_DIR / f"fpi_avg_{FPI_AVG_YEARS[0]}_{FPI_AVG_YEARS[1]}.tif"
ORIGINAL_M_PATH = OUT_M_DIR / f"original_M_{FPI_AVG_YEARS[0]}_{FPI_AVG_YEARS[1]}.tif"
LAMBDA_PATH = OUT_M_DIR / f"lambda_{FPI_AVG_YEARS[0]}_{FPI_AVG_YEARS[1]}.tif"

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


def stream_match(src_path, template, resampling):
    """Reproject onto the NLUM grid without loading the source raster.

    GDAL reads only the windows it needs and writes straight into the
    destination, so the 226 M-cell M layer never lands in memory. The
    destination defines the extent, so no separate clip step is needed.
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


def write_gtiff(arr, dst_path, template, descriptions=()):
    """Write a (band, y, x) array as a GeoTIFF on the template's grid."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
    with rasterio.open(
        tmp_path, "w",
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


def fetch_and_extract():
    """Download the outer zip and unpack both layers into Data/Raw."""
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    outer = ZIP_DIR / ZIP_NAME

    need = [
        sub for sub, tif, _ in LAYERS.values()
        if not (RAW_DIR / sub / tif).exists()
    ]
    if not need:
        print("both source rasters already extracted")
        return

    status = download(ZIP_URL, outer)
    print(f"outer zip: {status}")

    with zipfile.ZipFile(outer) as zf:
        # Keep the metadata PDFs beside the rasters - they document the layers.
        for member in zf.namelist():
            name = Path(member).name
            if name.lower().endswith(".pdf"):
                target = ZIP_DIR / name
                if not target.exists():
                    with zf.open(member) as s, open(target, "wb") as d:
                        d.write(s.read())

        for member in zf.namelist():
            name = Path(member).name
            if name not in LAYERS:
                continue
            sub, tif, _ = LAYERS[name]
            out_dir = RAW_DIR / sub
            out_dir.mkdir(parents=True, exist_ok=True)
            if (out_dir / tif).exists():
                continue

            inner_path = ZIP_DIR / name
            if not inner_path.exists():
                with zf.open(member) as s, open(inner_path, "wb") as d:
                    while chunk := s.read(8 * 1024 * 1024):
                        d.write(chunk)

            # The .tif carries its own georeferencing; .tfw/.ovr/.xml are extra.
            with zipfile.ZipFile(inner_path) as inner:
                for m in inner.namelist():
                    if Path(m).name == tif:
                        with inner.open(m) as s, open(out_dir / tif, "wb") as d:
                            while chunk := s.read(8 * 1024 * 1024):
                                d.write(chunk)
            print(f"extracted {sub}/{tif} "
                  f"({(out_dir / tif).stat().st_size / 1024**2:.1f} MB)")


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

fetch_and_extract()


# --------------------------------------------------------------------------- #
# Clip / reproject / fill / mask onto NLUM
# --------------------------------------------------------------------------- #

template = rioxarray.open_rasterio(NLUM_MASK).sel(band=1, drop=True)
valid = template.values == 1

print(f"\ntemplate : {template.rio.height} x {template.rio.width}")
print(f"valid    : {valid.sum():,} of {valid.size:,} cells\n")

for zip_name, (sub, tif, resampling) in LAYERS.items():
    src = RAW_DIR / sub / tif
    dst = PROCESSED_DIR / sub / tif

    if SKIP_EXISTING and dst.exists():
        print(f"[SKIP] {sub}/{tif}")
        continue
    if not src.exists():
        print(f"[MISS] {src} - download step did not produce it", file=sys.stderr)
        continue

    with rasterio.open(src) as s:
        print(f"{sub}/{tif}: {(s.height, s.width)} @ {s.res[0]:.4g} deg, "
              f"{resampling.name} -> NLUM")

    matched = stream_match(src, template, resampling)
    filled = np.empty_like(matched)
    for i, band in enumerate(matched):
        filled[i] = np.where(valid, fill_with_nearest(band), np.nan)
    write_gtiff(filled, dst, template, descriptions=(Path(tif).stem,))

    v = filled[0][valid]
    nan_in_mask = int(np.isnan(v).sum())
    print(f"  -> {dst.relative_to(PROCESSED_DIR)}  "
          f"range {np.nanmin(v):.3f}..{np.nanmax(v):.3f}  mean {np.nanmean(v):.3f}  "
          f"nan in mask {nan_in_mask:,}")
    if filled.shape[1:] != valid.shape or nan_in_mask:
        print(f"  [WARN] shape {filled.shape[1:]} vs NLUM {valid.shape}, "
              f"nan in mask {nan_in_mask:,}")


# --------------------------------------------------------------------------- #
# Original M from the historical FPI average, 1970-2002
# --------------------------------------------------------------------------- #

def fpi_to_m(fpi):
    """FullCAM's FPI -> site potential relationship.

    M = (6.011 * sqrt(FPI) - 5.291) ** 2

    Only monotonic above FPI = M_ROOT (0.7748); below it the squaring turns M
    back upward as FPI falls. Callers should check how many cells sit below.
    """
    return (M_A * np.sqrt(fpi) - M_B) ** 2


a, b = FPI_AVG_YEARS
years = list(range(a, b + 1))
missing_years = [y for y in years if not (FPI_DIR / f"fpi_{y}.tif").exists()]
if missing_years:
    raise FileNotFoundError(
        f"missing yearly FPI raster(s) for {missing_years} - run "
        "Step_0/mosaic_match_fpi_NLUM.py first"
    )

print(f"\naveraging FPI over {a}-{b} ({len(years)} years)")
stack = []
for y in years:
    with rasterio.open(FPI_DIR / f"fpi_{y}.tif") as s:
        stack.append(s.read(1))
fpi_avg = np.mean(np.stack(stack), axis=0).astype("float32")
del stack

write_gtiff(fpi_avg[np.newaxis, :, :], FPI_AVG_PATH, template,
            descriptions=(f"FPI_mean_{a}_{b}",))
fv = fpi_avg[valid]
print(f"  fpi_avg {a}-{b}: range {np.nanmin(fv):.3f}..{np.nanmax(fv):.3f}  "
      f"mean {np.nanmean(fv):.3f}  -> {FPI_AVG_PATH.name}")

# The parabola's root: below it the FPI -> M mapping is not monotonic.
n_below_root = int((fv < M_ROOT).sum())
print(f"  cells below the M-formula root (FPI < {M_ROOT:.4f}): {n_below_root:,}"
      f"  ({100 * n_below_root / fv.size:.4f}%)")
if n_below_root:
    print("  [WARN] M is not monotonic in FPI for those cells - "
          "M rises again as FPI falls, and M is near zero there, which also "
          "destabilises the lambda division below.")

original_M = np.where(valid, fpi_to_m(fpi_avg), np.nan).astype("float32")
write_gtiff(original_M[np.newaxis, :, :], ORIGINAL_M_PATH, template,
            descriptions=(f"original_M_{a}_{b}",))
ov = original_M[valid]
print(f"  original M : range {np.nanmin(ov):.3f}..{np.nanmax(ov):.3f}  "
      f"mean {np.nanmean(ov):.3f}  -> {ORIGINAL_M_PATH.name}")


# --------------------------------------------------------------------------- #
# lambda = revised M / original M
# --------------------------------------------------------------------------- #

revised_path = PROCESSED_DIR / "maxAbgM_v2" / "New_M_2019.tif"
with rasterio.open(revised_path) as s:
    revised_M = s.read(1)

# Guard the division the way Original_M_calculation.py does: an adaptive
# near-zero floor on the denominator, so cells where original M collapses to ~0
# (FPI near the parabola's root) do not produce absurd ratios.
den_abs = np.abs(ov[np.isfinite(ov)])
nonzero = den_abs[den_abs > 0]
p1 = float(np.percentile(nonzero, 1))
thr = max(1e-6, p1 * 0.1)
print(f"\nlambda: near-zero floor on original M -> p1={p1:.6g}, thr={thr:.6g}")

usable = valid & np.isfinite(revised_M) & np.isfinite(original_M) & (np.abs(original_M) >= thr)
n_dropped = int(valid.sum() - usable.sum())
print(f"  cells used   : {int(usable.sum()):,} of {int(valid.sum()):,}"
      f"  (dropped {n_dropped:,})")

lam = np.full(revised_M.shape, np.nan, dtype="float32")
with np.errstate(divide="ignore", invalid="ignore"):
    lam[usable] = revised_M[usable] / original_M[usable]
lam[~np.isfinite(lam)] = np.nan

write_gtiff(lam[np.newaxis, :, :], LAMBDA_PATH, template,
            descriptions=(f"lambda_revisedM_over_originalM_{a}_{b}",))

lv = lam[np.isfinite(lam)]
print(f"  lambda       : range {lv.min():.4f}..{lv.max():.4f}  "
      f"mean {lv.mean():.4f}  median {np.median(lv):.4f}")
for q in (1, 5, 25, 50, 75, 95, 99):
    print(f"    p{q:<3} {np.percentile(lv, q):10.4f}")
print(f"  -> {LAMBDA_PATH}")
