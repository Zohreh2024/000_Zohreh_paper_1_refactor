"""
Download WorldClim 2.1 historical climate (1970-2000) at 30 arc-seconds.

Source page: https://www.worldclim.org/data/worldclim21.html
Files served from: https://geodata.ucdavis.edu/climate/worldclim/2_1/base/

These are the *historical* counterparts to the CMIP6 future scenarios fetched by
download_worldclim_cmip6.py, and they are what the FPI random forest trains on.
Unlike the CMIP6 files (one multi-band .tif per scenario x period), each variable
ships as a .zip of single-band GeoTIFFs - 12 monthly rasters for prec/tmax/tmin
and 19 bioclimatic rasters for bio.

Note the variable code differs between the two products: historical bioclim is
`bio`, CMIP6 bioclim is `bioc`. Historical output therefore goes to its own
directories so it never collides with the future data:

    Data/Raw/hist_bio/    wc2.1_30s_bio_1.tif  .. wc2.1_30s_bio_19.tif
    Data/Raw/hist_prec/   wc2.1_30s_prec_01.tif .. _12.tif
    Data/Raw/hist_tmax/   wc2.1_30s_tmax_01.tif .. _12.tif
    Data/Raw/hist_tmin/   wc2.1_30s_tmin_01.tif .. _12.tif

Downloads are resumable and skip-if-present (the logic is reused from
download_worldclim_cmip6.py). Extraction is skipped when the expected number of
GeoTIFFs is already on disk.

Usage
-----
    python download_worldclim_historical.py
    python download_worldclim_historical.py --vars bio prec
    python download_worldclim_historical.py --dry-run
    python download_worldclim_historical.py --delete-zips
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# Reuse the resumable downloader and per-thread sessions from the CMIP6 script.
# That module guards its CLI behind __main__, so importing it runs nothing.
from download_worldclim_cmip6 import download, remote_size

BASE_URL = "https://geodata.ucdavis.edu/climate/worldclim/2_1/base"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Data" / "Raw"
ZIP_DIR = RAW_DIR / "_worldclim_zips"

# variable code -> (destination sub-directory, expected number of GeoTIFFs)
HIST_VARS = {
    "bio": ("hist_bio", 19),   # 19 bioclimatic variables
    "prec": ("hist_prec", 12),  # monthly precipitation
    "tmax": ("hist_tmax", 12),  # monthly maximum temperature
    "tmin": ("hist_tmin", 12),  # monthly minimum temperature
}

N_THREADS = 4


def zip_url(var):
    return f"{BASE_URL}/wc2.1_30s_{var}.zip"


def fetch_and_extract(var, delete_zip=False, position=0):
    """Download one variable's zip and extract its GeoTIFFs. Returns a status."""
    sub, expected = HIST_VARS[var]
    out_dir = RAW_DIR / sub
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(out_dir.glob("*.tif"))
    if len(existing) == expected:
        return f"{var}: already extracted ({expected} tif)"

    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = ZIP_DIR / f"wc2.1_30s_{var}.zip"
    status = download(zip_url(var), zip_path, position=position)

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".tif")]
        for m in tqdm(members, desc=f"unzip {var}", unit="tif", leave=False):
            # Flatten any internal folders - keep the provider's file name only.
            target = out_dir / Path(m).name
            if target.exists():
                continue
            with zf.open(m) as src, open(target, "wb") as dst:
                while chunk := src.read(8 * 1024 * 1024):
                    dst.write(chunk)

    n = len(sorted(out_dir.glob("*.tif")))
    if delete_zip:
        zip_path.unlink(missing_ok=True)
    if n != expected:
        raise IOError(f"{var}: extracted {n} tif, expected {expected}")
    return f"{var}: {status}, extracted {n} tif"


def run_one(var, delete_zip, position):
    """Never raises, so one bad variable cannot kill the batch."""
    try:
        msg = fetch_and_extract(var, delete_zip=delete_zip, position=position)
    except Exception as exc:  # noqa: BLE001 - report and keep going
        tqdm.write(f"[FAIL] {var}: {exc}")
        return var, exc
    tqdm.write(f"[OK  ] {msg}")
    return var, None


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Download WorldClim 2.1 historical 30s climate.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--vars", nargs="+", default=list(HIST_VARS), choices=list(HIST_VARS),
                   metavar="VAR", help="variables: " + ", ".join(HIST_VARS))
    p.add_argument("--workers", type=int, default=N_THREADS, help="concurrent downloads")
    p.add_argument("--delete-zips", action="store_true",
                   help="remove each .zip after a successful extraction")
    p.add_argument("--dry-run", action="store_true",
                   help="print URLs, sizes and what is already present")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.dry_run:
        total = 0
        for var in args.vars:
            sub, expected = HIST_VARS[var]
            have = len(sorted((RAW_DIR / sub).glob("*.tif")))
            try:
                size = remote_size(zip_url(var))
            except requests.RequestException as exc:
                print(f"  [ERROR] {zip_url(var)} ({exc})")
                continue
            done = have == expected
            total += 0 if done else (size or 0)
            print(f"  [{'have' if done else ' get'}] {size / 1024**3:6.2f} GB  "
                  f"{zip_url(var)}  -> Data/Raw/{sub} ({have}/{expected} tif)")
        print(f"\nStill to download: {total / 1024**3:.1f} GB")
        return 0

    n_threads = max(1, min(args.workers, len(args.vars)))
    print(f"{len(args.vars)} variable(s) with {n_threads} threads -> {RAW_DIR}\n")

    outcomes = Parallel(n_jobs=n_threads, backend="threading")(
        delayed(run_one)(var, args.delete_zips, i % n_threads)
        for i, var in enumerate(args.vars)
    )

    failed = [(v, e) for v, e in outcomes if e is not None]
    print(f"\nDone. ok={len(outcomes) - len(failed)} failed={len(failed)}")
    for v, e in failed:
        print(f"  FAILED {v}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
