"""
Step 3 - fetch GEDI L4A footprints, with the collection resolved rather than
hard-coded.

Corrected from Option_B_matched_footing/Validation/files/Level_4_01_fetch_gedi.py.
The science of that script was sound and most of it is carried over unchanged:
power beams only, sensitivity > 0.95, quality and degrade flags, filtering
inside the extraction loop so only survivors are held in memory, and granules
deleted after extraction.

Two things differ.

  1. The collection is resolved through CMR at run time (common.resolve_collection)
     instead of pinning the string "GEDI_L4A_AGB_Density_V2_1", which matches
     nothing - CMR's short name is GEDI_L4A_AGB_Density_V2_1_2056 and a query
     with the original returns zero granules for every region.

  2. Each footprint is given its NLUM row, column and cell id at extraction
     time, using common.cell_index. The original assigned cells on a bare
     0.01-degree grid offset half a cell from NLUM.

Run Step_01_check_sources.py first: it reports the granule count and the
download volume per region. The full six-region set is roughly a terabyte.

Search and download go through CMR and the authenticated session from Step 2,
not earthaccess, which is not installed in JinzhuLuto (and that env must not be
modified). Each granule's surviving footprints are checkpointed to
outputs/gedi_parts/<region>/<granule>.parquet, so an interrupted run resumes
without re-downloading what it already extracted.

Usage
    python Step_03_fetch_gedi.py --inspect --regions vic_central
    python Step_03_fetch_gedi.py --regions vic_central --max-granules 5
    python Step_03_fetch_gedi.py --regions vic_central tasmania
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import common as C
from Step_02_build_fire_mask import fetch, granule_urls, make_session

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
PARTS = OUT / "gedi_parts"
CACHE = HERE / "gedi_granules"
GEDI_END = "2024-11-27"

POWER_BEAMS = ["BEAM0101", "BEAM0110", "BEAM1000", "BEAM1011"]
COVERAGE_BEAMS = ["BEAM0000", "BEAM0001", "BEAM0010", "BEAM0011"]

VARIABLES = {
    "agbd": "agbd",
    "agbd_se": "agbd_se",
    "l4_quality_flag": "l4_quality_flag",
    "degrade_flag": "degrade_flag",
    "sensitivity": "sensitivity",
    "lat_lowestmode": "lat_lowestmode",
    "lon_lowestmode": "lon_lowestmode",
    "elev_lowestmode": "elev_lowestmode",
    "shot_number": "shot_number",
    "delta_time": "delta_time",
    "pft_class": "land_cover_data/pft_class",
}

MIN_SENSITIVITY = 0.95
GEDI_EPOCH = np.datetime64("2018-01-01T00:00:00")


def inspect_granule(path, max_depth=3):
    import h5py
    print("\nStructure of %s\n%s" % (path.name, "=" * 68))

    def walk(name, obj):
        depth = name.count("/")
        if depth > max_depth:
            return
        pad = "  " * depth
        if isinstance(obj, h5py.Dataset):
            print("%s%-28s %-14s %s" % (pad, name.split("/")[-1],
                                        str(obj.shape), obj.dtype))
        else:
            print("%s%s/" % (pad, name.split("/")[-1]))

    with h5py.File(path, "r") as f:
        beams = [k for k in f.keys() if k.startswith("BEAM")]
        print("Beams present: %s\n" % beams)
        if beams:
            f[beams[0]].visititems(walk)
    print("\nEvery path in VARIABLES must appear above before a full run.")


def extract(path, bbox, beams, transform, shape):
    import h5py
    west, south, east, north = bbox
    frames = []
    with h5py.File(path, "r") as f:
        for beam in beams:
            if beam not in f:
                continue
            grp = f[beam]
            missing = [p for p in VARIABLES.values() if p not in grp]
            if missing:
                print("     %s %s: missing %s" % (path.name, beam, missing))
                continue
            try:
                data = {k: grp[p][:] for k, p in VARIABLES.items()}
            except (KeyError, OSError) as exc:
                print("     %s %s: read failed (%s)" % (path.name, beam, exc))
                continue
            keep = ((data["l4_quality_flag"] == 1)
                    & (data["degrade_flag"] == 0)
                    & (data["sensitivity"] > MIN_SENSITIVITY)
                    & (data["agbd"] >= 0)
                    & np.isfinite(data["agbd"])
                    & (data["lon_lowestmode"] >= west)
                    & (data["lon_lowestmode"] <= east)
                    & (data["lat_lowestmode"] >= south)
                    & (data["lat_lowestmode"] <= north))
            if not keep.any():
                continue
            df = pd.DataFrame({k: v[keep] for k, v in data.items()})
            df["beam"] = beam
            df["beam_type"] = "power" if beam in POWER_BEAMS else "coverage"
            df["granule"] = path.name
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns={"lon_lowestmode": "lon",
                              "lat_lowestmode": "lat"})
    out["acq_time"] = (GEDI_EPOCH
                       + out["delta_time"].values.astype("timedelta64[s]"))
    # THE GRID FIX: NLUM cell identity, assigned here so nothing downstream
    # can reinvent a misaligned grid.
    idx = C.cell_index(out["lon"].values, out["lat"].values, transform, shape)
    out["nlum_row"] = idx["row"]
    out["nlum_col"] = idx["col"]
    out["cell_id"] = idx["cell_id"]
    out["cell_lon"] = idx["cell_lon"]
    out["cell_lat"] = idx["cell_lat"]
    return out[idx["inside"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", nargs="+", default=list(C.REGIONS),
                    choices=list(C.REGIONS))
    ap.add_argument("--max-granules", type=int, default=None)
    ap.add_argument("--all-beams", dest="power_only", action="store_false",
                    default=True)
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--keep-granules", action="store_true")
    ap.add_argument("--version", default="2.1")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    col = C.resolve_collection(keyword=C.GEDI_L4A_KEYWORD,
                               prefer_version=args.version)
    print("collection: %s v%s  (%s)" % (col.get("short_name"),
                                        col.get("version_id"), col.get("id")))

    user, pw, src = C.earthdata_credentials()
    if not user:
        C.explain_no_credentials()
        sys.exit(2)
    print("credentials via %s" % src)

    session = make_session(user, pw)
    beams = POWER_BEAMS if args.power_only else POWER_BEAMS + COVERAGE_BEAMS
    transform, h, w = C.nlum_grid()
    print("beams: %s" % beams)

    # A GEDI granule is an orbit segment, and one orbit often crosses several
    # regions (the two NSW boxes list the same ~994 granules). So collect the
    # regions each granule serves, download it once, extract every region
    # that has no checkpoint yet, then delete it.
    by_region = {}
    for region in args.regions:
        urls = granule_urls(col["id"], C.REGIONS[region], C.GEDI_START,
                            GEDI_END, suffix=".h5")
        if args.max_granules:
            urls = urls[:args.max_granules]
        by_region[region] = urls
        (PARTS / region).mkdir(parents=True, exist_ok=True)
        print("=== %s: %d granules ===" % (region, len(urls)))
        if args.inspect:
            fp = CACHE / urls[0].rsplit("/", 1)[-1]
            if fetch(session, urls[0], fp):
                inspect_granule(fp)
            return

    def part_path(region, u):
        return PARTS / region / (Path(u.rsplit("/", 1)[-1]).stem + ".parquet")

    serves = {}
    for region, urls in by_region.items():
        for u in urls:
            serves.setdefault(u, []).append(region)
    todo = [u for u in sorted(serves)
            if any(not part_path(r, u).exists() for r in serves[u])]
    print("\n%d distinct granules, %d already fully checkpointed, %d to fetch"
          % (len(serves), len(serves) - len(todo), len(todo)))

    for i, u in enumerate(todo, 1):
        fp = CACHE / u.rsplit("/", 1)[-1]
        if not fetch(session, u, fp):
            print("  [%d/%d] download failed: %s" % (i, len(todo), fp.name))
            continue
        got = []
        for region in serves[u]:
            part = part_path(region, u)
            if part.exists():
                continue
            try:
                df = extract(fp, C.REGIONS[region], beams, transform, (h, w))
            except Exception as exc:
                print("  [%d/%d] %s %s: extract failed (%s: %s)"
                      % (i, len(todo), fp.name, region,
                         type(exc).__name__, exc))
                continue
            if not df.empty:
                df["region"] = region
            df.to_parquet(part, index=False)
            got.append("%s %d" % (region, len(df)))
        print("  [%d/%d] %s: %s" % (i, len(todo), fp.name,
                                   ", ".join(got) or "nothing extracted"))
        if not args.keep_granules:
            try:
                fp.unlink()
            except OSError:
                pass

    frames, manifest = [], []
    for region, urls in by_region.items():
        for u in urls:
            part = part_path(region, u)
            if not part.exists():
                continue
            df = pd.read_parquet(part)
            manifest.append({"region": region, "granule": part.stem + ".h5",
                             "footprints": len(df)})
            if not df.empty:
                frames.append(df)
        print("  %-16s %d granules checkpointed of %d"
              % (region, sum(m["region"] == region for m in manifest),
                 len(urls)))

    if not frames:
        sys.exit("no footprints survived - loosen MIN_SENSITIVITY or widen "
                 "the regions")
    out = pd.concat(frames, ignore_index=True)
    # Region boxes can share an edge; a shot on it must be counted once.
    before = len(out)
    out = out.drop_duplicates("shot_number")
    if len(out) < before:
        print("  dropped %d footprints shared by two region boxes"
              % (before - len(out)))
    dst = OUT / "gedi_l4a_footprints.parquet"
    out.to_parquet(dst, index=False)
    pd.DataFrame(manifest).to_csv(OUT / "gedi_fetch_manifest.csv", index=False)
    print("\n%d footprints in %d NLUM cells -> %s"
          % (len(out), out.cell_id.nunique(), dst))


if __name__ == "__main__":
    main()
