"""
Download the BARRA-R2 historical baseline (1985-2014) from CSIRO's Data Access
Portal collection csiro:64206.

Source page: https://data.csiro.au/collection/csiro:64206
    "Application-ready quantile-delta-change (QDC) scaled CMIP6 climate
     projections for Australia (time slices, 11km grid)"
    DOI 10.25919/nc64-tx11, CC-BY 4.0

That collection is 14 TB in total, but only the `BARRA-R2/raw/historical/`
branch is the historical baseline - 270 files, 109 GB, 9 daily variables x
30 years (1985-2014) on the native AUS-11 (~11 km) BARRA-R2 grid. This is the
same observational baseline the QDC change factors in `Data/Raw/rainFall/` were
applied to, so it is the correct historical footing for those projections.

    variable      files      size    meaning
    hurs            30     15.1 GB   mean near-surface relative humidity
    hursmax         30     16.1 GB   maximum near-surface relative humidity
    hursmin         30     16.4 GB   minimum near-surface relative humidity
    pr              30     21.2 GB   precipitation
    rsds            30     12.6 GB   mean downwelling shortwave radiation
    sfcWind         30      9.3 GB   mean near-surface wind speed
    sfcWindmax      30      6.2 GB   maximum near-surface wind speed
    tasmax          30      5.9 GB   maximum near-surface temperature
    tasmin          30      6.5 GB   minimum near-surface temperature

Files land in Data/Raw/CSIRO_historical_data/<variable>/ under the provider's
original file name, e.g.

    Data/Raw/CSIRO_historical_data/pr/pr_day_BARRA-R2_historical_v1_AUS-11_1985.nc

Usage
-----
    python download_CSIRO_historical_data.py --dry-run          # list, download nothing
    python download_CSIRO_historical_data.py --vars pr tasmax tasmin
    python download_CSIRO_historical_data.py --years 1985-1994
    python download_CSIRO_historical_data.py                    # everything (109 GB)
    python download_CSIRO_historical_data.py --refresh-manifest # re-query the DAP API

Why this does not import `download()` from download_worldclim_cmip6.py
----------------------------------------------------------------------
DAP serves file bytes from S3 behind a pre-signed URL, which differs from a
plain static host in two ways that the WorldClim helper cannot accommodate:

  * the signature covers GET only, so a HEAD returns 403 - the expected size
    has to come from the API manifest instead of Content-Length;
  * signatures expire (48 h), so a long download has to re-sign mid-flight by
    re-requesting the per-file endpoint, which 302-redirects to a fresh URL.

Everything else - .part files, Range resume, size verification, retries - keeps
the same shape as the other downloaders in this directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

import requests
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

COLLECTION_ID = 64206
DATA_API = f"https://data.csiro.au/dap/ws/v2/collections/{COLLECTION_ID}/data"

# Only this branch of the collection is the historical baseline; everything else
# is future QDC-scaled projections for one of the 9 CMIP6 models.
HISTORICAL_PREFIX = "BARRA-R2/raw/historical/"

VARIABLES = [
    "hurs",        # mean near-surface relative humidity
    "hursmax",     # maximum near-surface relative humidity
    "hursmin",     # minimum near-surface relative humidity
    "pr",          # precipitation
    "rsds",        # mean downwelling shortwave radiation
    "sfcWind",     # mean near-surface wind speed
    "sfcWindmax",  # maximum near-surface wind speed
    "tasmax",      # maximum near-surface temperature
    "tasmin",      # minimum near-surface temperature
]

YEAR_START, YEAR_END = 1985, 2014  # the QDC baseline period

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "Data" / "Raw" / "CSIRO_historical_data"

# The manifest is ~30 MB of JSON describing all 16,596 files in the collection.
# Cache it beside this script so repeat runs and --dry-run do not re-fetch it.
MANIFEST_CACHE = Path(__file__).resolve().parent / ".dap_64206_manifest.json"

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
TIMEOUT = (30, 300)           # (connect, read) seconds
MAX_RETRIES = 5
N_THREADS = 8                 # joblib threads; override with --workers


# --------------------------------------------------------------------------- #
# HTTP session (one per thread - a Session is not safe to share across threads)
# --------------------------------------------------------------------------- #

_local = threading.local()


def get_session():
    """Return this thread's requests.Session, creating it on first use."""
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "csiro-dap-downloader/1.0"
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=N_THREADS, pool_maxsize=N_THREADS
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _local.session = session
    return session


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #

def fetch_manifest(refresh=False):
    """Return the collection's file list, using the on-disk cache when possible.

    The cached copy keeps the `filename`/`fileSize`/`id` fields valid
    indefinitely; only the embedded pre-signed URLs go stale, and those are
    re-signed per file at download time.
    """
    if MANIFEST_CACHE.exists() and not refresh:
        with open(MANIFEST_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)["file"]

    print(f"Fetching file manifest for collection csiro:{COLLECTION_ID} ...")
    resp = get_session().get(
        DATA_API, headers={"Accept": "application/json"}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    payload = resp.json()

    MANIFEST_CACHE.write_text(json.dumps(payload), encoding="utf-8")
    print(f"  {len(payload['file'])} files in collection "
          f"(cached -> {MANIFEST_CACHE.name})")
    return payload["file"]


def parse_entry(entry):
    """Pull (variable, year) out of a historical file's DAP path.

    Paths look like
        BARRA-R2/raw/historical/v1/day/pr/AUS-11/1985-2014/v20241104/
            pr_day_BARRA-R2_historical_v1_AUS-11_1985.nc
    """
    parts = entry["filename"].split("/")
    variable = parts[5]
    year = int(Path(parts[-1]).stem.rsplit("_", 1)[-1])
    return variable, year


def build_jobs(entries, variables, years, out_root):
    """Return [(entry, destination Path)] for every requested variable-year."""
    wanted_vars, wanted_years = set(variables), set(years)

    jobs = []
    for entry in entries:
        if not entry["filename"].startswith(HISTORICAL_PREFIX):
            continue
        variable, year = parse_entry(entry)
        if variable not in wanted_vars or year not in wanted_years:
            continue
        name = entry["filename"].rsplit("/", 1)[-1]
        jobs.append((entry, out_root / variable / name))

    jobs.sort(key=lambda job: job[1].as_posix())
    return jobs


def signed_url(entry):
    """A currently-valid pre-signed S3 URL for `entry`.

    The manifest ships one, but it expires after 48 h. The per-file endpoint
    302-redirects to a freshly signed URL, and requests follows that for us, so
    re-requesting it is how a long download re-signs mid-flight.
    """
    resp = get_session().get(
        entry["link"]["href"], timeout=TIMEOUT, allow_redirects=False
    )
    if resp.is_redirect or resp.is_permanent_redirect:
        return resp.headers["Location"]
    resp.raise_for_status()
    return entry["presignedLink"]["href"]


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def download(entry, dst, position=0):
    """Download `entry` to `dst`, resuming a previous partial download if present.

    Returns "skipped" or "downloaded", or raises on unrecoverable failure.
    Safe to call from several joblib threads at once - each gets its own session.
    """
    session = get_session()

    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_suffix(dst.suffix + ".part")

    # From the manifest, not a HEAD: the pre-signed signature covers GET only.
    total = int(entry["fileSize"])

    # Already complete?
    if dst.exists():
        if dst.stat().st_size == total:
            return "skipped"
        tqdm.write(f"  size mismatch, re-downloading: {dst.name}")
        dst.unlink()

    url = entry["presignedLink"]["href"]

    for attempt in range(1, MAX_RETRIES + 1):
        done = part.stat().st_size if part.exists() else 0

        if done == total:
            break
        if done > total:
            part.unlink()
            done = 0

        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with session.get(url, headers=headers, stream=True, timeout=TIMEOUT) as resp:
                # 403 here means the pre-signed URL has expired - re-sign and retry.
                if resp.status_code == 403:
                    url = signed_url(entry)
                    continue
                # 200 means the server ignored our Range header -> restart from 0.
                if done and resp.status_code == 200:
                    done = 0
                    part.unlink(missing_ok=True)
                resp.raise_for_status()

                mode = "ab" if done else "wb"
                bar = tqdm(
                    total=total,
                    initial=done,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=dst.name,
                    position=position,
                    leave=False,
                )
                with open(part, mode) as fh, bar:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            fh.write(chunk)
                            bar.update(len(chunk))
        except (requests.RequestException, OSError) as exc:
            if attempt == MAX_RETRIES:
                raise
            tqdm.write(f"  retry {attempt}/{MAX_RETRIES - 1} for {dst.name}: {exc}")
            continue

        if part.stat().st_size == total:
            break

    if part.stat().st_size != total:
        raise IOError(f"{dst.name}: got {part.stat().st_size} bytes, expected {total}")

    part.replace(dst)
    return "downloaded"


def run_one(entry, dst, position):
    """joblib task wrapper: never raises, so one bad file can't kill the batch.

    Returns (status, file name, exception or None).
    """
    try:
        status = download(entry, dst, position=position)
    except Exception as exc:  # noqa: BLE001 - report and keep the batch going
        tqdm.write(f"[FAIL      ] {dst.name}: {exc}")
        return "failed", dst.name, exc
    tqdm.write(f"[{status.upper():10s}] {dst.name}")
    return status, dst.name, None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_years(spec):
    """Expand "1985-1994" or "1985" into a list of years, bounded by the baseline."""
    if "-" in spec:
        first, last = (int(part) for part in spec.split("-", 1))
    else:
        first = last = int(spec)
    if not (YEAR_START <= first <= last <= YEAR_END):
        raise argparse.ArgumentTypeError(
            f"years must fall inside {YEAR_START}-{YEAR_END}, got {spec!r}"
        )
    return list(range(first, last + 1))


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=(
            f"Download the BARRA-R2 historical baseline {YEAR_START}-{YEAR_END} "
            f"from CSIRO DAP collection csiro:{COLLECTION_ID}."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--vars", nargs="+", default=VARIABLES,
                   choices=VARIABLES, metavar="VAR",
                   help="variables to download: " + ", ".join(VARIABLES))
    p.add_argument("--years", type=parse_years,
                   default=list(range(YEAR_START, YEAR_END + 1)),
                   metavar="YYYY[-YYYY]",
                   help=f"year or inclusive range within {YEAR_START}-{YEAR_END}")
    p.add_argument("--out", type=Path, default=OUT_DIR,
                   help="output root; variable sub-directories are created inside")
    p.add_argument("--workers", type=int, default=N_THREADS,
                   help="joblib threads, i.e. concurrent downloads")
    p.add_argument("--refresh-manifest", action="store_true",
                   help="re-query the DAP API instead of using the cached manifest")
    p.add_argument("--dry-run", action="store_true",
                   help="print the files and sizes, download nothing")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    entries = fetch_manifest(refresh=args.refresh_manifest)
    jobs = build_jobs(entries, args.vars, args.years, args.out)
    n_threads = max(1, args.workers)

    if not jobs:
        print("No files matched the requested variables and years.")
        return 1

    total_bytes = sum(int(entry["fileSize"]) for entry, _ in jobs)
    print(f"{len(jobs)} file(s) requested, {total_bytes / 1024 ** 3:.1f} GB "
          f"-> {args.out}")

    if args.dry_run:
        still = 0
        for entry, dst in jobs:
            size = int(entry["fileSize"])
            have = dst.exists() and dst.stat().st_size == size
            still += 0 if have else size
            print(f"  [{'have' if have else ' get'}] {size / 1024 ** 3:6.2f} GB  "
                  f"{dst.relative_to(args.out).as_posix()}")
        print(f"\nStill to download: {still / 1024 ** 3:.1f} GB")
        return 0

    print(f"Downloading with {n_threads} joblib threads\n")

    outcomes = Parallel(n_jobs=n_threads, backend="threading")(
        delayed(run_one)(entry, dst, i % n_threads)
        for i, (entry, dst) in enumerate(jobs)
    )

    results = {"downloaded": [], "skipped": [], "failed": []}
    for status, name, exc in outcomes:
        if status == "failed":
            results["failed"].append((name, exc))
        else:
            results[status].append(name)

    print(
        f"\nDone. downloaded={len(results['downloaded'])} "
        f"skipped={len(results['skipped'])} failed={len(results['failed'])}"
    )
    for name, exc in results["failed"]:
        print(f"  FAILED {name}: {exc}")

    return 1 if results["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
