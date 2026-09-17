"""
Step 1 - verify the two fixes and size the job, before downloading anything.

Runs with no credentials. NASA's Common Metadata Repository is open for
search; only the file downloads are authenticated.

It does three things:

  1. Proves the grid fix, by printing the original 0.01-degree cell centre and
     the NLUM-derived one for the same longitude, with the offset between them.
  2. Proves the short-name fix, by resolving the GEDI L4A and MODIS burned-area
     collections through CMR and printing the concept ids and the real short
     names - including the numeric suffix the original pipeline was missing.
  3. Counts granules and estimates download volume per region, so the scale of
     the job is known before it starts rather than after.

Writes  outputs/source_check.csv
"""

from pathlib import Path

import pandas as pd

import common as C

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

GEDI_MB = 235.0        # measured from a sample granule
MODIS_MB = 1.7


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("FIX 1  the aggregation grid")
    print("=" * 68)
    off = C.check_alignment()
    print("  -> an aggregation cell is now an NLUM cell by construction"
          if off > 0 else "  -> grids already aligned")

    print("\n" + "=" * 68)
    print("FIX 2  resolving collections instead of hard-coding short names")
    print("=" * 68)
    gedi = C.resolve_collection(keyword=C.GEDI_L4A_KEYWORD,
                                prefer_version="2.1")
    print("  GEDI L4A")
    print("    original script used : GEDI_L4A_AGB_Density_V2_1   "
          "(returns 0 granules)")
    print("    actual short name    : %s" % gedi.get("short_name"))
    print("    concept id           : %s" % gedi.get("id"))
    print("    version              : %s" % gedi.get("version_id"))
    print("    record               : %s to %s"
          % ((gedi.get("time_start") or "?")[:10],
             (gedi.get("time_end") or "ongoing")[:10]))

    try:
        v3 = C.resolve_collection(keyword=C.GEDI_L4A_KEYWORD,
                                  prefer_version="3")
        if str(v3.get("version_id")) == "3":
            print("    note: a version 3 exists - %s (%s)"
                  % (v3.get("short_name"), v3.get("id")))
    except SystemExit:
        pass

    fire = C.resolve_collection(short_name=C.MODIS_BURN_SHORT)
    print("\n  MODIS burned area")
    print("    short name           : %s" % fire.get("short_name"))
    print("    concept id           : %s" % fire.get("id"))
    print("    version              : %s" % fire.get("version_id"))
    print("    record               : %s to %s"
          % ((fire.get("time_start") or "?")[:10],
             (fire.get("time_end") or "ongoing")[:10]))

    print("\n" + "=" * 68)
    print("SCALE  granules per region, so the job is sized before it starts")
    print("=" * 68)
    end = "2024-11-27"
    rows = []
    for name, bbox in C.REGIONS.items():
        ng = C.granule_count(gedi["id"], bbox, (C.GEDI_START, end))
        nf = C.granule_count(fire["id"], bbox, ("2019-01-01", end))
        rows.append({"region": name, "bbox": str(bbox),
                     "gedi_granules": ng,
                     "gedi_gb_estimate": round(ng * GEDI_MB / 1000, 1),
                     "modis_granules": nf,
                     "modis_mb_estimate": round(nf * MODIS_MB, 1)})
        print("  %-17s GEDI %5d granules (~%5.0f GB)   MODIS %4d (~%4.0f MB)"
              % (name, ng, ng * GEDI_MB / 1000, nf, nf * MODIS_MB))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "source_check.csv", index=False)
    print("\n  TOTAL            GEDI %5d granules (~%5.0f GB)   MODIS %4d"
          % (df.gedi_granules.sum(), df.gedi_gb_estimate.sum(),
             df.modis_granules.sum()))
    print("\n  Granules overlap between adjacent regions, so the true total is")
    print("  lower than the sum. Even so this is a terabyte-scale transfer:")
    print("  start with one or two regions and check the surviving cell count")
    print("  before committing to the rest.")
    print("\nwrote %s" % (OUT / "source_check.csv"))


if __name__ == "__main__":
    main()
