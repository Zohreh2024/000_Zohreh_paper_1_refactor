"""
Step 2 - build a fire-history mask on the NLUM grid.

## Why this step exists at all

The original pipeline had no fire handling, and that is the defect most likely
to invalidate its result. GEDI's record starts 2019-04-18. The 2019-20 fires
burned roughly seven million hectares from late 2019, straight through
vic_gippsland, nsw_southeast and nsw_north_seqld - three of the six target
regions, all of them tall forest.

A footprint acquired after a fire measures a burnt canopy. In high-FPI tall
forest that depresses biomass for reasons having nothing to do with M', which
could manufacture, amplify or conceal exactly the negative correlation the
pipeline was built to test. Without a fire flag the experiment cannot
distinguish "M' ranks tall forest backwards" from "this forest burnt".

## What is produced

MODIS MCD64A1 v061 gives, per 500 m pixel per month, the day of year on which
that pixel burned. This step reduces it to one raster per year on the NLUM
grid:

    fire/burn_year_<YYYY>.tif    1 where the cell burned that year, else 0

plus a single summary raster

    fire/last_burn_year.tif      the most recent burn year, 0 if never

Resampling is NEAREST throughout. Burn dates are categorical-ish and a burnt
cell next to an unburnt one must not average into something in between.

## How the flags are used later

Step 4 flags a footprint when its cell burned between (acquisition date minus
--recovery-years) and the acquisition date. Ten years is the default: biomass
in wet eucalypt forest does not return in one. Black Summer is also flagged
separately, because it is the case most likely to be questioned.

## Why HDF4 goes through zoenv's gdal_translate

MCD64A1 ships as HDF4, and the GDAL bundled with JinzhuLuto's rasterio has no
HDF4 driver - every granule fails with RasterioIOError. JinzhuLuto must not be
modified, so each granule is converted to a temporary GeoTIFF by the
gdal_translate.exe of the existing zoenv environment (GDAL 3.6.2, HDF4 built
in), called as a subprocess. zoenv is only executed, never changed. The
GeoTIFF is read here and deleted.

## Start year

The default start is 2009, not 2010. Black Saturday (Feb 2009) burned inside
vic_central, and with the 10-year recovery window a footprint acquired in 2019
needs fire history back to 2009.

Requires the same free Earthdata login as GEDI. Usage:

    python Step_02_build_fire_mask.py --check
    python Step_02_build_fire_mask.py --regions vic_central tasmania
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import common as C

HERE = Path(__file__).resolve().parent
FIRE = HERE / "fire"
CACHE = HERE / "modis_granules"
OUT = HERE / "outputs"

ZOENV = Path(r"C:\ProgramData\Anaconda3\envs\zoenv")
GDAL_TRANSLATE = ZOENV / "Library" / "bin" / "gdal_translate.exe"

# Stop rather than write an all-unburnt mask if conversion is broken.
MAX_CONSECUTIVE_READ_FAILURES = 5


def make_session(user, pw):
    import requests

    class EarthdataSession(requests.Session):
        """Keep Authorization across the URS redirect. NASA's own recipe."""

        def rebuild_auth(self, prepared_request, response):
            headers = prepared_request.headers
            if "Authorization" in headers:
                orig = requests.utils.urlparse(response.request.url).hostname
                redir = requests.utils.urlparse(prepared_request.url).hostname
                if (orig != redir and redir != "urs.earthdata.nasa.gov"
                        and orig != "urs.earthdata.nasa.gov"):
                    del headers["Authorization"]

    s = EarthdataSession()
    s.auth = (user, pw)
    s.headers.update(C.UA)
    return s


def granule_urls(concept_id, bbox, start, end, page_size=2000, suffix=".hdf"):
    """Every granule URL ending in `suffix` intersecting a box and time range.

    Also used by Step 3 for GEDI (.h5)."""
    import json
    import urllib.parse
    import urllib.request
    q = {"collection_concept_id": concept_id,
         "bounding_box": ",".join(str(x) for x in bbox),
         "temporal": "%sT00:00:00Z,%sT23:59:59Z" % (start, end),
         "page_size": page_size}
    url = C.CMR + "granules.json?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=C.UA)
    with urllib.request.urlopen(req, timeout=120, context=C._CTX) as r:
        d = json.load(r)
    urls = []
    for e in d["feed"]["entry"]:
        for lk in e.get("links", []):
            h = lk.get("href", "")
            if h.startswith("http") and h.lower().endswith(suffix):
                urls.append(h)
                break
    return sorted(set(urls))


def fetch(session, url, dest):
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    r = session.get(url, stream=True, timeout=180, allow_redirects=True)
    ctype = (r.headers.get("Content-Type") or "").lower()
    if r.status_code in (401, 403) or "html" in ctype:
        print("     auth refused for %s" % dest.name)
        return False
    if r.status_code != 200:
        print("     HTTP %d for %s" % (r.status_code, dest.name))
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write to .part and rename on completion, so an interrupted download is
    # never mistaken for a complete file by the exists() check above.
    part = dest.with_name(dest.name + ".part")
    expected = int(r.headers.get("Content-Length") or 0)
    with open(part, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
    if expected and part.stat().st_size != expected:
        print("     truncated %s (%d of %d bytes)"
              % (dest.name, part.stat().st_size, expected))
        part.unlink()
        return False
    part.replace(dest)
    return True


def burn_year_from_granule(path):
    """Read the Burn Date layer and return (year, lons, lats) of burnt pixels.

    MCD64A1 is a sinusoidal-grid HDF-EOS file. Burn Date is day-of-year, with
    0 meaning unburnt and negative values meaning unmapped.
    """
    import rasterio
    from rasterio.warp import transform as warp_transform

    sub = ('HDF4_EOS:EOS_GRID:"%s":MOD_Grid_Monthly_500m_DB_BA:"Burn Date"'
           % path)
    tif = path.with_suffix(".burndate.tif")
    env = dict(os.environ)
    env["PATH"] = str(ZOENV / "Library" / "bin") + os.pathsep + env["PATH"]
    env["GDAL_DATA"] = str(ZOENV / "Library" / "share" / "gdal")
    env["PROJ_LIB"] = env["PROJ_DATA"] = str(ZOENV / "Library" / "share" / "proj")
    res = subprocess.run([str(GDAL_TRANSLATE), "-q", sub, str(tif)],
                         env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("gdal_translate: %s" % res.stderr.strip()[:200])
    try:
        with rasterio.open(tif) as s:
            a = s.read(1)
            src_crs, src_t = s.crs, s.transform
    finally:
        try:
            tif.unlink()
        except OSError:
            pass
    burnt = a > 0
    if not burnt.any():
        return None
    rows, cols = np.nonzero(burnt)
    xs = src_t.c + (cols + 0.5) * src_t.a
    ys = src_t.f + (rows + 0.5) * src_t.e
    lon, lat = warp_transform(src_crs, "EPSG:4283", xs.tolist(), ys.tolist())
    year = int(path.name.split(".")[1][1:5])
    return year, np.asarray(lon), np.asarray(lat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", nargs="+", default=list(C.REGIONS),
                    choices=list(C.REGIONS))
    ap.add_argument("--start", default="2009-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--check", action="store_true",
                    help="verify credentials and granule counts, download "
                         "nothing")
    ap.add_argument("--keep-granules", action="store_true")
    args = ap.parse_args()

    FIRE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    fire_col = C.resolve_collection(short_name=C.MODIS_BURN_SHORT)
    print("MODIS burned area: %s v%s  (%s)"
          % (fire_col.get("short_name"), fire_col.get("version_id"),
             fire_col.get("id")))

    user, pw, src = C.earthdata_credentials()
    if not user:
        C.explain_no_credentials()
        if args.check:
            print("\n(granule counts still shown below - CMR search is open)")
            for reg in args.regions:
                n = C.granule_count(fire_col["id"], C.REGIONS[reg],
                                    (args.start[:10], args.end[:10]))
                print("  %-17s %4d MCD64A1 granules" % (reg, n))
        sys.exit(2)
    print("credentials via %s" % src)

    if not args.check and not GDAL_TRANSLATE.exists():
        sys.exit("HDF4 converter not found: %s" % GDAL_TRANSLATE)

    session = make_session(user, pw)
    transform, h, w = C.nlum_grid()
    years = list(range(int(args.start[:4]), int(args.end[:4]) + 1))
    stack = {y: np.zeros((h, w), dtype="uint8") for y in years}

    # Regions share MODIS tiles (the two NSW boxes overlap almost entirely),
    # and a granule covers its whole tile, so each is processed only once.
    done = set()
    failures = 0
    for reg in args.regions:
        bbox = C.REGIONS[reg]
        urls = granule_urls(fire_col["id"], bbox, args.start, args.end)
        new = [u for u in urls if u not in done]
        print("\n=== %s: %d granules, %d not already processed ==="
              % (reg, len(urls), len(new)))
        if args.check:
            continue
        for i, u in enumerate(new, 1):
            done.add(u)
            dest = CACHE / u.rsplit("/", 1)[-1]
            if not fetch(session, u, dest):
                continue
            try:
                got = burn_year_from_granule(dest)
                failures = 0
            except Exception as exc:
                print("     read failed %s (%s: %s)"
                      % (dest.name, type(exc).__name__, exc))
                got = None
                failures += 1
                if failures >= MAX_CONSECUTIVE_READ_FAILURES:
                    sys.exit("%d consecutive read failures - stopping before "
                             "writing an empty fire mask" % failures)
            if got:
                year, lon, lat = got
                if year in stack:
                    idx = C.cell_index(lon, lat, transform, (h, w))
                    ok = idx["inside"]
                    stack[year][idx["row"][ok], idx["col"][ok]] = 1
            if not args.keep_granules:
                try:
                    dest.unlink()
                except OSError:
                    pass
            if i % 25 == 0:
                print("     %d/%d" % (i, len(new)))

    if args.check:
        print("\ncheck complete - nothing downloaded")
        return

    import rasterio
    prof = dict(rasterio.open(C.NLUM_MASK).profile)
    prof.update(dtype="uint8", count=1, nodata=0, compress="lzw",
                tiled=True, blockxsize=256, blockysize=256)
    last = np.zeros((h, w), dtype="uint16")
    written = 0
    for y in years:
        if not stack[y].any():
            continue
        with rasterio.open(FIRE / ("burn_year_%d.tif" % y), "w", **prof) as d:
            d.write(stack[y], 1)
            d.update_tags(product="MCD64A1.061", year=str(y),
                          note="1 = burnt that year, NLUM grid, nearest")
        last = np.where(stack[y] == 1, y, last)
        written += 1
        print("  burn_year_%d.tif  %d cells" % (y, int(stack[y].sum())))

    p2 = dict(prof)
    p2.update(dtype="uint16")
    with rasterio.open(FIRE / "last_burn_year.tif", "w", **p2) as d:
        d.write(last, 1)
        d.update_tags(product="MCD64A1.061",
                      note="most recent burn year, 0 = never burnt in record")
    print("\n%d annual rasters + last_burn_year.tif in %s" % (written, FIRE))


if __name__ == "__main__":
    main()
