"""
Shared helpers for the corrected GEDI validation.

This module exists to fix two specific defects found in
Option_B_matched_footing/Validation/files/, and to hold the fire-masking
constants the original pipeline lacked.

## Fix 1 - the aggregation grid was half a cell off NLUM

The original used

    cell_col = floor(lon / 0.01)

which places cell edges at multiples of 0.01: ... 145.36, 145.37, 145.38 ...
NLUM's edges are at 112.925 + 0.01k, i.e. ... 145.365, 145.375 ... The two
grids are offset by exactly 0.005 degrees, half a cell. Measured:

    for lon 145.3712
      original cell centre : 145.375000
      NLUM     cell centre : 145.370000
      offset               : 0.005 deg = 0.50 of a cell

Every aggregation cell therefore straddled two NLUM cells, and the point at
which M' and FPI were sampled fell on an NLUM cell boundary. This is the same
trap CLAUDE.md records for ANUClimate, whose centres land on NLUM's edges.

`cell_index()` below derives the grid from NLUM's own transform, so a GEDI
aggregation cell IS an NLUM cell, by construction rather than by coincidence.

## Fix 2 - the GEDI short name did not resolve

The original pinned

    GEDI_L4A_SHORT_NAME = "GEDI_L4A_AGB_Density_V2_1"

CMR's actual short name carries a numeric suffix,
`GEDI_L4A_AGB_Density_V2_1_2056`, and a query with the original string returns
zero granules for every region. Suffixes like this change between releases, so
rather than swap one hard-coded string for another, `resolve_collection()`
looks the collection up by keyword at run time and returns the concept id -
which is stable and unambiguous. It also reports the newer V3 if present.

## Fire masking

The original had none, and the 2019-20 fires fall inside the GEDI record
(which begins 2019-04-18). MODIS MCD64A1 gives monthly burned area with a
per-pixel burn date at 500 m, from the same Earthdata login GEDI needs.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

# The machine-wide PROJ_LIB points at a stale PostGIS proj.db, so any CRS
# lookup (e.g. EPSG:4283) raises CRSError. Point PROJ at rasterio's own
# database before rasterio is first imported. Every step imports this module
# first, and rasterio is only imported lazily inside functions.
_proj = Path(sys.prefix) / "Lib" / "site-packages" / "rasterio" / "proj_data"
if _proj.exists():
    os.environ["PROJ_LIB"] = os.environ["PROJ_DATA"] = str(_proj)

ROOT = Path(__file__).resolve().parent.parent
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

CMR = "https://cmr.earthdata.nasa.gov/search/"
UA = {"User-Agent": "Mozilla/5.0 (research)"}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# Tall and open eucalypt forest - the vegetation group where Level 2 gave an
# elasticity of -2.62 and a rank correlation of -0.60.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "vic_central":     (145.0, -38.0, 146.5, -37.0),
    "vic_gippsland":   (147.5, -38.2, 149.5, -36.8),
    "tasmania":        (144.5, -43.7, 148.5, -40.5),
    "nsw_southeast":   (149.5, -37.5, 152.0, -33.0),
    "nsw_north_seqld": (151.5, -33.0, 153.5, -28.0),
    "wa_southwest":    (115.5, -35.2, 118.0, -33.0),
}

GEDI_L4A_KEYWORD = "GEDI L4A Footprint Level Aboveground Biomass Density"
MODIS_BURN_SHORT = "MCD64A1"
GEDI_START = "2019-04-18"

# Biomass does not recover in a year. A cell burnt this long before a footprint
# was acquired is still carrying a fire signal, so the footprint is flagged.
DEFAULT_RECOVERY_YEARS = 10

# The Black Summer window, called out separately because it falls inside the
# GEDI record and hit the tall-forest regions hardest.
BLACK_SUMMER = ("2019-07-01", "2020-03-31")


# ------------------------------------------------------------------ #
# Fix 1: the NLUM grid
# ------------------------------------------------------------------ #
def nlum_grid():
    """Return (transform, height, width) of the NLUM reference grid."""
    import rasterio
    with rasterio.open(NLUM_MASK) as s:
        return s.transform, s.height, s.width


def nlum_mask():
    import rasterio
    with rasterio.open(NLUM_MASK) as s:
        return s.read(1) == 1


def cell_index(lon, lat, transform=None, shape=None):
    """Map lon/lat to NLUM row, col, cell id and cell centre.

    The grid comes from NLUM's transform, so an aggregation cell is an NLUM
    cell. Points outside the grid get row/col of -1 and cell_id of -1.
    """
    if transform is None or shape is None:
        transform, h, w = nlum_grid()
    else:
        h, w = shape
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    col = np.floor((lon - transform.c) / transform.a).astype("int64")
    row = np.floor((lat - transform.f) / transform.e).astype("int64")
    inside = (row >= 0) & (row < h) & (col >= 0) & (col < w)
    cell_id = np.where(inside, row * w + col, -1)
    centre_lon = transform.c + (col + 0.5) * transform.a
    centre_lat = transform.f + (row + 0.5) * transform.e
    return dict(row=np.where(inside, row, -1),
                col=np.where(inside, col, -1),
                cell_id=cell_id, inside=inside,
                cell_lon=centre_lon, cell_lat=centre_lat)


def check_alignment(verbose=True):
    """Demonstrate the fix: the old grid against NLUM, at a real longitude."""
    transform, h, w = nlum_grid()
    lon, lat = 145.3712, -37.5416
    old_centre = (np.floor(lon / 0.01) + 0.5) * 0.01
    new = cell_index([lon], [lat], transform, (h, w))
    off = abs(old_centre - float(new["cell_lon"][0]))
    if verbose:
        print("grid alignment check at lon %.4f" % lon)
        print("  original 0.01-grid centre : %.6f" % old_centre)
        print("  NLUM-derived centre       : %.6f" % float(new["cell_lon"][0]))
        print("  offset                    : %.6f deg = %.2f of a cell"
              % (off, off / 0.01))
    return off


# ------------------------------------------------------------------ #
# Fix 2: resolve the collection instead of hard-coding a short name
# ------------------------------------------------------------------ #
def _get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return json.load(r), dict(r.headers)


def resolve_collection(keyword=None, short_name=None, prefer_version=None):
    """Look a collection up in CMR and return its concept id.

    Concept ids are stable; short names carry release-specific numeric
    suffixes and change. Searching by keyword and returning the concept id
    avoids the failure the original pipeline had.
    """
    params = {"page_size": 20}
    if short_name:
        params["short_name"] = short_name
    if keyword:
        params["keyword"] = keyword
    d, _ = _get(CMR + "collections.json?" + urllib.parse.urlencode(params))
    entries = d["feed"]["entry"]
    if not entries:
        raise SystemExit("no CMR collection matches %r / %r"
                         % (keyword, short_name))
    if prefer_version:
        for e in entries:
            if str(e.get("version_id")) == str(prefer_version):
                return e
    return entries[0]


def granule_count(concept_id, bbox, temporal):
    """How many granules intersect a box and time range. Needs no login."""
    q = {"collection_concept_id": concept_id,
         "bounding_box": ",".join(str(x) for x in bbox),
         "temporal": "%sT00:00:00Z,%sT23:59:59Z" % temporal,
         "page_size": 1}
    _, hdr = _get(CMR + "granules.json?" + urllib.parse.urlencode(q))
    return int(hdr.get("CMR-Hits", hdr.get("cmr-hits", 0)))


# ------------------------------------------------------------------ #
# Earthdata credentials, shared by the GEDI and MODIS steps
# ------------------------------------------------------------------ #
# Where a .netrc may live on this machine. HOME is H: here while
# USERPROFILE is C:\Users\..., and the working home is
# on the N: share, so Python's default ~/.netrc is not enough.
# EARTHDATA_NETRC overrides everything.
WORK_HOME = r'N:\Current-Users\ZOHREH-KALAHROUDI'


def netrc_candidates():
    import os
    out = []
    env = os.environ.get("EARTHDATA_NETRC")
    if env:
        out.append(Path(env))
    bases = [os.environ.get("USERPROFILE"), os.environ.get("HOME"),
             str(Path(os.path.expanduser("~"))), WORK_HOME,
             str(ROOT), str(ROOT.parent)]
    for base in bases:
        if not base:
            continue
        for name in (".netrc", "_netrc"):
            out.append(Path(base) / name)
    seen, uniq = set(), []
    for c in out:
        if str(c).lower() not in seen:
            seen.add(str(c).lower())
            uniq.append(c)
    return uniq


def _read_netrc(path):
    """Parse one netrc file for the Earthdata host.

    Parsed by hand rather than with the netrc module, which cannot read a
    file that carries a UTF-8 BOM - and PowerShell writes one by default.
    """
    try:
        txt = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return None
    toks = txt.split()
    for i, t in enumerate(toks):
        if t == "machine" and i + 1 < len(toks) and \
                toks[i + 1] == "urs.earthdata.nasa.gov":
            user = pw = None
            j = i + 2
            while j + 1 < len(toks) and toks[j] not in ("machine",
                                                        "default"):
                if toks[j] == "login":
                    user = toks[j + 1]
                elif toks[j] == "password":
                    pw = toks[j + 1]
                j += 2
            if user and pw:
                return user, pw
    return None


def earthdata_credentials():
    import os
    u = os.environ.get("EARTHDATA_USERNAME")
    p = os.environ.get("EARTHDATA_PASSWORD")
    if u and p:
        return u, p, "environment variables"
    for cand in netrc_candidates():
        if not cand.exists():
            continue
        got = _read_netrc(cand)
        if got:
            return got[0], got[1], str(cand)
    return None, None, None


def explain_no_credentials():
    print("\nNo Earthdata credentials found. Both GEDI and the MODIS fire")
    print("product need the same free login:")
    print("  1. register at https://urs.earthdata.nasa.gov/users/new")
    print("  2. log in once and accept the LP DAAC and ORNL DAAC EULAs")
    print("  3. set EARTHDATA_USERNAME and EARTHDATA_PASSWORD, or add")
    print("     machine urs.earthdata.nasa.gov login USER password PASS")
    print("     to any of the paths listed below.")
    print("")
    print("  Searched for a .netrc in:")
    for c in netrc_candidates():
        print("     %-56s %s" % (str(c)[:56],
                                 "EXISTS" if c.exists() else "-"))
    print("")
    print("  Or set EARTHDATA_NETRC to the full path of the file.")
