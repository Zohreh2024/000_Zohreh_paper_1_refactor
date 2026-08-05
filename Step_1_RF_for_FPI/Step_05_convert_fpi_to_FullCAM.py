"""
Convert the predicted FPI GeoTIFFs into the NetCDF form FullCAM reads.

    Step_1_RF_for_FPI/output/future_<ssp>_<period>_prediction.tif
        -> Data/Input_for_FullCAM/forestProdIx/<SSP>/forestProdIx_<SSP>_<range>.nc

The target format is taken from the existing files under
N:/Current-Users/ZOHREH-KALAHROUDI/RUN_FULLCAM/forestProdIx/, which
RUN_FullCAM2024.py consumes as:

    xr.open_dataarray(f".../forestProdIx/{SSP}/forestProdIx_{SSP}_{range}.nc",
                      chunks={}).assign_coords(x=..., y=...)

Format requirements this implies, all matched here:

  * NetCDF holding EXACTLY ONE data variable - open_dataarray fails otherwise.
  * Variable name == file stem, e.g. `forestProdIx_SSP126_2020-2040`.
  * dims (y, x) = (3364, 4071), the NLUM grid, so the `assign_coords` in
    RUN_FullCAM2024 lines up. A mismatch there raises rather than misaligns.
  * float64, NaN outside the NLUM mask, uncompressed/contiguous (~104.6 MB).
  * Scalar `band` and `spatial_ref` coords carried over from the GeoTIFF.

Two naming conversions
----------------------
1. SSP is UPPERCASE in FullCAM (`SSP126`), lowercase in ours (`ssp126`).
2. FullCAM's first period is labelled **2020-2040**, while the WorldClim
   scenario data is **2021-2040**. RUN_FullCAM2024's `year_range_map` maps
   simulation year 2030 -> '2020-2040', so the file must carry that label or it
   will not be found. The underlying data is unchanged (still 2021-2040); the
   original filename is recorded in the `source_tif` attribute.
"""

import os
from pathlib import Path

import numpy as np
import rioxarray
import xarray as xr
from tqdm.auto import tqdm

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
PRED_DIR = Path(__file__).resolve().parent / "output"
OUT_ROOT = PROJECT_ROOT / "Data" / "Input_for_FullCAM" / "forestProdIx"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

VARIABLE = "forestProdIx"
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]

# our period label -> the label FullCAM's year_range_map expects
PERIOD_MAP = {
    "2021-2040": "2020-2040",
    "2041-2060": "2041-2060",
    "2061-2080": "2061-2080",
    "2081-2100": "2081-2100",
}

OVERWRITE = True


# --------------------------------------------------------------------------- #
# Convert
# --------------------------------------------------------------------------- #

def convert(src_path, dst_path, var_name):
    """GeoTIFF -> single-variable float64 NetCDF on the NLUM grid."""
    da = rioxarray.open_rasterio(src_path).squeeze()   # band becomes a scalar coord
    try:
        da = da.astype("float64")
        da.name = var_name
        da.attrs = {"AREA_OR_POINT": da.attrs.get("AREA_OR_POINT", "Area")}

        ds = da.to_dataset()
        ds.attrs = {
            "source_tif": src_path.name,
            "reference_grid": NLUM_MASK.name,
            "crs": str(da.rio.crs),
        }

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst_path.with_suffix(".nc.tmp")
        # Uncompressed and contiguous, matching the reference files.
        ds.to_netcdf(
            tmp,
            engine="netcdf4",
            encoding={var_name: {"dtype": "float64", "zlib": False, "_FillValue": np.nan}},
        )
        tmp.replace(dst_path)
        return da.shape, int(np.isfinite(da.values).sum())
    finally:
        da.close()


jobs = []
for ssp in SSPS:
    for our_period, fullcam_period in PERIOD_MAP.items():
        src = PRED_DIR / f"future_{ssp}_{our_period}_prediction.tif"
        var = f"{VARIABLE}_{ssp.upper()}_{fullcam_period}"
        dst = OUT_ROOT / ssp.upper() / f"{var}.nc"
        jobs.append((src, dst, var))

missing = [str(s) for s, _, _ in jobs if not s.exists()]
if missing:
    raise FileNotFoundError("prediction raster(s) not found:\n  " + "\n  ".join(missing))

todo = [j for j in jobs if OVERWRITE or not j[1].exists()]
print(f"{len(jobs)} prediction(s); {len(todo)} to convert -> {OUT_ROOT}\n")

for src, dst, var in tqdm(todo, desc=VARIABLE, unit="file"):
    shape, n_finite = convert(src, dst, var)
    tqdm.write(f"[OK] {dst.parent.name}/{dst.name}  {shape}  finite {n_finite:,}")


# --------------------------------------------------------------------------- #
# Verify - read them back exactly the way RUN_FullCAM2024.py does
# --------------------------------------------------------------------------- #

print("\nverifying (open_dataarray, as RUN_FullCAM2024 does):")

with rioxarray.open_rasterio(NLUM_MASK) as m:
    ref_shape = (m.rio.height, m.rio.width)

problems = []
for _, dst, var in jobs:
    try:
        da = xr.open_dataarray(dst, chunks={})
    except Exception as exc:            # noqa: BLE001 - report and continue
        problems.append(f"{dst.name}: cannot open_dataarray - {exc}")
        continue
    try:
        if da.name != var:
            problems.append(f"{dst.name}: variable is {da.name!r}, expected {var!r}")
        if da.shape != ref_shape:
            problems.append(f"{dst.name}: shape {da.shape}, expected {ref_shape}")
        if da.dtype != np.float64:
            problems.append(f"{dst.name}: dtype {da.dtype}, expected float64")
        if da.dims != ("y", "x"):
            problems.append(f"{dst.name}: dims {da.dims}, expected ('y', 'x')")
    finally:
        da.close()

print(f"  {len(jobs) - len(problems)} of {len(jobs)} files valid")
for p in problems:
    print("   ", p)

n = len(list(OUT_ROOT.rglob("*.nc")))
print(f"\nwrote {n} NetCDF file(s) under {OUT_ROOT}")
print("To use them, point RUN_FullCAM2024.py's forestProdIx path at:")
print(f"  {OUT_ROOT}/{{SSP}}/forestProdIx_{{SSP}}_{{year_range}}.nc")
