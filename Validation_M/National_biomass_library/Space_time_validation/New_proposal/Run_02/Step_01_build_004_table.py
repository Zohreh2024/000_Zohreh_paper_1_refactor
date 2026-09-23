"""
Run 2 - lower the plot-area threshold from 0.05 to 0.04 ha.

One constant. The parent's Step_01_build_reference_table.py carries

    MIN_AREA_HA = 0.05

and this run rebuilds the reference table with 0.04 instead. Nothing else in
the filter trail changes: the same biomass and basal-area requirements, the same
dead-basal-area limit, the same production and planted-project exclusions, the
same 1985 cut-off, the same AGB-versus-basal-area consistency filter, the same
one-row-per-site collapse.

What the change buys
--------------------
Measured on the raw library with every other filter applied:

    threshold   mature visits   sites south of 37 S
    0.05 ha        605                 5
    0.04 ha        808               131

The southern coverage is the point. At 0.05 ha the sample has five sites below
37 S - Victoria and Tasmania are effectively absent from a validation of a
continental layer. At 0.04 ha there are 131.

Almost all of the gain is one provider. Of the 283 visits admitted only by the
change:

    DELWP Victoria                          201    median AGB 225   BA 30.8
    University of Queensland                 28    median AGB 620   BA 15.7
    University of NSW                        27    median AGB  68   BA  0.6
    DSITI Queensland Herbarium               17    median AGB 557   BA  8.4
    Department of Parks and Wildlife (WA)     7    median AGB 429   BA 51.0

DELWP's plots are all exactly 0.04 ha and their values are sane - a median of
225 Mg/ha of biomass on 30.8 m2/ha of live basal area is an ordinary tall wet
eucalypt forest, and the ratio between them is 7.3, right on the library
median. They fail the 0.05 ha threshold by a hundredth of a hectare and by
nothing else.

Why this is a sensitivity and not a new default
-----------------------------------------------
The rationale for the threshold has not changed. Measured on this library,
median biomass falls from 276 Mg/ha on plots under 0.05 ha to 11 over 0.5 ha, a
gradient produced by sampling geometry rather than vegetation, and Run 2's
companion study (Plot_area_floor_method) shows the same effect running the
other way: raising the floor to 0.40 ha lifts M'/AGB from 0.465 to 1.275.
Lowering the threshold admits more of exactly the artefact that study is trying
to remove.

Two things make it worth measuring anyway. The gain is concentrated in one
provider whose plots are internally consistent, so it is checkable rather than
diffuse. And it buys the one thing no other filter choice has bought: southern
coverage. Report it as a sensitivity, quote it beside the 0.05 ha result, and
say which provider is carrying it.

Note the University of NSW rows: 27 visits at a median 68 Mg/ha on 0.6 m2/ha of
basal area, a ratio of about 106. That passes the consistency filter because
that filter is a floor, not a ceiling. Step_02 reports the result with and
without them.

Reads   ../../Step_01_build_reference_table.py    imported, not modified
        ../../../NBL_download/biolib_sitelist.csv, biolib_treelist.csv
Writes  outputs/reference_table_min004.csv
        outputs/filter_trail_min004.csv
        outputs/reference_table_summary_min004.csv
        outputs/admitted_by_the_change.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_build_004_table.py
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"


def find_parent(start):
    for d in [start] + list(start.parents):
        if (d / "Step_01_build_reference_table.py").exists():
            return d
    raise SystemExit("could not find Step_01_build_reference_table.py above %s"
                     % start)


PARENT = find_parent(HERE)


def load_builder():
    """Import the parent's Step_01 without running or modifying it."""
    spec = importlib.util.spec_from_file_location(
        "stv_step01", PARENT / "Step_01_build_reference_table.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["stv_step01"] = mod
    spec.loader.exec_module(mod)
    return mod


def admitted_table(B, floor_new, floor_old):
    """The visits the change lets in, and who measured them."""
    d = pd.read_csv(B.SITES, low_memory=False)
    agb = pd.to_numeric(d["agb_drymass_ha"], errors="coerce")
    ba = pd.to_numeric(d["live_basal_area_ha"], errors="coerce")
    dba = pd.to_numeric(d["dead_basal_area_ha"], errors="coerce")
    area = pd.to_numeric(d["sampledarea_ha"], errors="coerce")
    yr = pd.to_datetime(d["obs_time"], errors="coerce").dt.year

    keep = agb.notna() & (agb > 0) & ba.notna() & (ba > 0)
    keep &= (dba / (ba + dba)).fillna(0) < 0.2
    keep &= ~d["source"].isin(B.PRODUCTION)
    keep &= ~d["project"].isin(B.PLANTED_PROJECTS)
    keep &= yr >= 1985
    keep &= agb <= B.MAX_AGB
    with np.errstate(invalid="ignore", divide="ignore"):
        per = agb / ba
    keep &= per >= B.MIN_AGB_PER_BA
    band = keep & area.notna() & (area >= floor_new) & (area < floor_old)

    s = d[band].copy()
    s["agb"] = agb[band]
    s["live_ba"] = ba[band]
    s["area_ha"] = area[band]
    s["agb_per_ba"] = per[band]
    s["latitude"] = pd.to_numeric(s["latitude"], errors="coerce")
    out = s.groupby("source").agg(
        visits=("agb", "size"), agb_median=("agb", "median"),
        basal_area_median=("live_ba", "median"),
        agb_per_ba_median=("agb_per_ba", "median"),
        area_min=("area_ha", "min"), area_max=("area_ha", "max"),
        lat_min=("latitude", "min"), lat_max=("latitude", "max"),
        south_of_37=("latitude", lambda v: int((v < -37).sum()))
    ).reset_index().sort_values("visits", ascending=False)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-area", type=float, default=0.04,
                    help="the one constant this run changes (parent: 0.05)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    B = load_builder()
    old_floor = float(B.MIN_AREA_HA)
    print("parent threshold %.2f ha -> this run %.2f ha"
          % (old_floor, args.min_area))

    adm = admitted_table(B, args.min_area, old_floor)
    adm.to_csv(OUT_DIR / "admitted_by_the_change.csv", index=False)
    print("\nvisits admitted only by the change: %d, from %d providers"
          % (int(adm["visits"].sum()), len(adm)))
    print(adm[["source", "visits", "agb_median", "basal_area_median",
               "agb_per_ba_median", "south_of_37"]].head(8).to_string(
        index=False, float_format=lambda v: "%.1f" % v))

    # Patch the two module globals and run the parent's own main(). Nothing in
    # the parent folder is written, because OUT_DIR is redirected first.
    B.MIN_AREA_HA = args.min_area
    B.OUT_DIR = OUT_DIR
    argv = sys.argv
    sys.argv = ["Step_01_build_reference_table.py", "--keep-all-classes"]
    try:
        print("\nrebuilding the reference table at %.2f ha" % args.min_area)
        B.main()
    finally:
        sys.argv = argv

    for stem in ("reference_table", "filter_trail", "reference_table_summary"):
        src = OUT_DIR / ("%s.csv" % stem)
        if src.exists():
            shutil.move(str(src), str(OUT_DIR / ("%s_min004.csv" % stem)))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
