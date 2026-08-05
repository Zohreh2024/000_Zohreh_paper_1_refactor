"""
Download WorldClim 2.1 CMIP6 downscaled future climate data (30 arc-seconds)
for the ACCESS-CM2 GCM.

Source page: https://www.worldclim.org/data/cmip6/cmip6_clim30s.html
Files are served from: https://geodata.ucdavis.edu/cmip6/30s/

Files land in Data/Raw/<variable>/ using the original WorldClim file name, e.g.
    Data/Raw/bioc/wc2.1_30s_bioc_ACCESS-CM2_ssp245_2021-2040.tif
    Data/Raw/tmin/wc2.1_30s_tmin_ACCESS-CM2_ssp245_2021-2040.tif

Downloads are resumable: partial files are written to <name>.tif.part and
continued with an HTTP Range request. A file already present at the full remote
size is skipped.

Usage
-----
    python download_worldclim_cmip6.py                     # everything (~660 GB)
    python download_worldclim_cmip6.py --vars bioc         # bioclim only
    python download_worldclim_cmip6.py --ssps ssp245 ssp585 --periods 2021-2040
    python download_worldclim_cmip6.py --dry-run           # list what would download
    python download_worldclim_cmip6.py --workers 4         # fewer concurrent downloads

Downloads run through joblib with the threading backend (12 threads by default);
the work is network-bound, so threads sidestep the GIL while sharing one process.
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

import requests
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

BASE_URL = "https://geodata.ucdavis.edu/cmip6/30s"
GCM = "ACCESS-CM2"

# WorldClim variable codes. Each is also its sub-directory name under Data/Raw.
VARIABLES = [
    "tmin",  # monthly minimum temperature
    "tmax",  # monthly maximum temperature
    "prec",  # monthly precipitation
    "bioc",  # 19 bioclimatic variables
]

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
PERIODS = ["2021-2040", "2041-2060", "2061-2080", "2081-2100"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Data" / "Raw"

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
TIMEOUT = (30, 300)           # (connect, read) seconds
MAX_RETRIES = 5
N_THREADS = 12                # joblib threads; override with --workers


# --------------------------------------------------------------------------- #
# HTTP session (one per thread - a Session is not safe to share across threads)
# --------------------------------------------------------------------------- #

_local = threading.local()


def get_session():
    """Return this thread's requests.Session, creating it on first use."""
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "worldclim-downloader/1.0"
        # Size the connection pool for the whole thread fleet.
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=N_THREADS, pool_maxsize=N_THREADS
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _local.session = session
    return session


# --------------------------------------------------------------------------- #
# Job construction
# --------------------------------------------------------------------------- #

def build_jobs(variables, ssps, periods, out_root):
    """Return a list of (url, destination Path) for every requested combination."""
    jobs = []
    for ssp in ssps:
        for period in periods:
            for var in variables:
                fname = f"wc2.1_30s_{var}_{GCM}_{ssp}_{period}.tif"
                url = f"{BASE_URL}/{GCM}/{ssp}/{fname}"
                dst = out_root / var / fname
                jobs.append((url, dst))
    return jobs


def remote_size(url):
    """Content-Length of the remote file, or None if the server won't say."""
    resp = get_session().head(url, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    size = resp.headers.get("Content-Length")
    return int(size) if size is not None else None


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def download(url, dst, position=0):
    """Download `url` to `dst`, resuming a previous partial download if present.

    Returns one of "skipped", "downloaded", or raises on unrecoverable failure.
    Safe to call from several joblib threads at once - each gets its own session.
    """
    session = get_session()

    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_suffix(dst.suffix + ".part")

    total = remote_size(url)

    # Already complete?
    if dst.exists():
        if total is None or dst.stat().st_size == total:
            return "skipped"
        # Size mismatch: previous download was truncated, start over.
        tqdm.write(f"  size mismatch, re-downloading: {dst.name}")
        dst.unlink()

    for attempt in range(1, MAX_RETRIES + 1):
        done = part.stat().st_size if part.exists() else 0

        if total is not None and done == total:
            break
        if total is not None and done > total:
            part.unlink()
            done = 0

        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with session.get(url, headers=headers, stream=True, timeout=TIMEOUT) as resp:
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

        if total is None or part.stat().st_size == total:
            break

    if total is not None and part.stat().st_size != total:
        raise IOError(
            f"{dst.name}: got {part.stat().st_size} bytes, expected {total}"
        )

    part.replace(dst)
    return "downloaded"


def run_one(url, dst, position):
    """joblib task wrapper: never raises, so one bad file can't kill the batch.

    Returns (status, file name, exception or None).
    """
    try:
        status = download(url, dst, position=position)
    except Exception as exc:  # noqa: BLE001 - report and keep the batch going
        tqdm.write(f"[FAIL      ] {dst.name}: {exc}")
        return "failed", dst.name, exc
    tqdm.write(f"[{status.upper():10s}] {dst.name}")
    return status, dst.name, None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=f"Download WorldClim 2.1 CMIP6 30s data for {GCM}.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--vars", nargs="+", default=VARIABLES,
                   choices=VARIABLES, metavar="VAR",
                   help="variables to download: " + ", ".join(VARIABLES))
    p.add_argument("--ssps", nargs="+", default=SSPS, choices=SSPS, metavar="SSP",
                   help="scenarios: " + ", ".join(SSPS))
    p.add_argument("--periods", nargs="+", default=PERIODS, choices=PERIODS,
                   metavar="PERIOD", help="periods: " + ", ".join(PERIODS))
    p.add_argument("--out", type=Path, default=RAW_DIR,
                   help="output root; variable sub-directories are created inside")
    p.add_argument("--workers", type=int, default=N_THREADS,
                   help="joblib threads, i.e. concurrent downloads")
    p.add_argument("--dry-run", action="store_true",
                   help="print the URLs and sizes, download nothing")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    jobs = build_jobs(args.vars, args.ssps, args.periods, args.out)
    n_threads = max(1, args.workers)

    print(f"{len(jobs)} file(s) requested -> {args.out}")

    if args.dry_run:
        grand_total = 0
        for url, dst in jobs:
            try:
                size = remote_size(url)
            except requests.RequestException as exc:
                print(f"  [ERROR] {url}  ({exc})")
                continue
            have = dst.exists() and size is not None and dst.stat().st_size == size
            grand_total += 0 if have else (size or 0)
            gb = size / 1024 ** 3 if size else float("nan")
            print(f"  [{'have' if have else ' get'}] {gb:8.2f} GB  {url}")
        print(f"\nStill to download: {grand_total / 1024 ** 3:.1f} GB")
        return 0

    print(f"Downloading with {n_threads} joblib threads\n")

    outcomes = Parallel(n_jobs=n_threads, backend="threading")(
        delayed(run_one)(url, dst, i % n_threads)
        for i, (url, dst) in enumerate(jobs)
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
