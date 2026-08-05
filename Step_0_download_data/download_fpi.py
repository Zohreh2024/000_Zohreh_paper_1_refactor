"""
Download the Forest Productivity Index (FPI) v1.0, Sept 2024 release.

Dataset: https://data.gov.au/data/dataset/forest-productivity-index-version-1-0-sept-2024-release
Publisher: DCCEEW, derived from FullCAM / 3-PG. FPI is the Y target for the
random forest in Step_1_RF_for_FPI.

The release is 37 zipped map-sheet tiles covering Australia. Each zip holds 53
yearly FPI GeoTIFFs (1970-2022) at ~1 km on GDA94, plus .tfw/.ovr/.xml
sidecars. Only the .tif files are extracted: georeferencing is embedded in the
GeoTIFF itself (verified - CRS and bounds read correctly with the .tfw removed),
and the .ovr pyramids are regenerable bulk.

    Data/Raw/fpi/<tile>/1970_001.tif .. 2022_001.tif

IMPORTANT: the rasters inside every zip share the same names (1970_001.tif and
so on) with no tile prefix, so each zip MUST extract into its own sub-directory
or the 37 tiles overwrite one another down to a single tile.

Resource URLs are read from the data.gov.au CKAN API rather than hard-coded, so
they stay correct if the portal re-issues resource IDs.

Usage
-----
    python download_fpi.py
    python download_fpi.py --dry-run
    python download_fpi.py --workers 6
    python download_fpi.py --delete-zips
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# Reuse the resumable downloader from the CMIP6 script (its CLI is __main__-guarded).
from download_worldclim_cmip6 import download

DATASET_ID = "forest-productivity-index-version-1-0-sept-2024-release"
CKAN_API = f"https://data.gov.au/data/api/3/action/package_show?id={DATASET_ID}"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Data" / "Raw"
FPI_DIR = RAW_DIR / "fpi"
ZIP_DIR = RAW_DIR / "_fpi_zips"

EXPECTED_YEARS = 53          # 1970-2022 inclusive
N_THREADS = 6


def list_resources():
    """Return [(tile, filename, url), ...] for every zip in the dataset."""
    resp = requests.get(CKAN_API, timeout=(30, 120), headers={"User-Agent": "fpi-downloader/1.0"})
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError("CKAN API returned success=false")

    out = []
    for res in payload["result"]["resources"]:
        if (res.get("format") or "").upper() != "ZIP":
            continue
        name = res["name"]                      # e.g. sk55_fpi_7022.zip
        tile = name.split("_")[0]               # e.g. sk55
        out.append((tile, name, res["url"]))
    return sorted(out)


def fetch_and_extract(tile, name, url, delete_zip=False, position=0):
    """Download one tile's zip and extract its yearly GeoTIFFs."""
    out_dir = FPI_DIR / tile
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(sorted(out_dir.glob("*.tif"))) == EXPECTED_YEARS:
        return f"{tile}: already extracted ({EXPECTED_YEARS} tif)"

    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = ZIP_DIR / name
    status = download(url, zip_path, position=position)

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".tif")]
        for m in members:
            target = out_dir / Path(m).name
            if target.exists():
                continue
            with zf.open(m) as src, open(target, "wb") as dst:
                while chunk := src.read(4 * 1024 * 1024):
                    dst.write(chunk)

    n = len(sorted(out_dir.glob("*.tif")))
    if delete_zip:
        zip_path.unlink(missing_ok=True)
    if n != EXPECTED_YEARS:
        raise IOError(f"{tile}: extracted {n} tif, expected {EXPECTED_YEARS}")
    return f"{tile}: {status}, {n} tif"


def run_one(tile, name, url, delete_zip, position):
    """Never raises, so one bad tile cannot kill the batch."""
    try:
        msg = fetch_and_extract(tile, name, url, delete_zip=delete_zip, position=position)
    except Exception as exc:  # noqa: BLE001 - report and keep going
        tqdm.write(f"[FAIL] {tile}: {exc}")
        return tile, exc
    tqdm.write(f"[OK  ] {msg}")
    return tile, None


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Download the FPI v1.0 (Sept 2024) tiles from data.gov.au.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--workers", type=int, default=N_THREADS, help="concurrent downloads")
    p.add_argument("--delete-zips", action="store_true",
                   help="remove each .zip after a successful extraction")
    p.add_argument("--dry-run", action="store_true",
                   help="list the tiles and what is already present")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    resources = list_resources()
    print(f"{len(resources)} tile(s) listed by the CKAN API")

    if args.dry_run:
        todo = 0
        for tile, name, url in resources:
            have = len(sorted((FPI_DIR / tile).glob("*.tif")))
            done = have == EXPECTED_YEARS
            todo += 0 if done else 1
            print(f"  [{'have' if done else ' get'}] {tile:6s} {have:2d}/{EXPECTED_YEARS} tif  {name}")
        print(f"\nTiles still to fetch: {todo}")
        return 0

    n_threads = max(1, min(args.workers, len(resources)))
    print(f"downloading with {n_threads} threads -> {FPI_DIR}\n")

    outcomes = Parallel(n_jobs=n_threads, backend="threading")(
        delayed(run_one)(tile, name, url, args.delete_zips, i % n_threads)
        for i, (tile, name, url) in enumerate(resources)
    )

    failed = [(t, e) for t, e in outcomes if e is not None]
    print(f"\nDone. ok={len(outcomes) - len(failed)} failed={len(failed)}")
    for t, e in failed:
        print(f"  FAILED {t}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
