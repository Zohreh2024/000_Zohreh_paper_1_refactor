"""
Combined run, step 1 - build the reference table.

Five decisions, each carried over from the run that established it. This is no
longer a one-change test: it is the configuration those tests point to, and the
report says plainly which evidence supports which part.

  1. BIOMASS REBUILT FROM STEM DIAMETERS (Run_03, b = 2.5).
     The library's stem-mass column is not aligned with the stem attributes -
     holding survey, plot, subplot, allometric model and species constant, mass
     has no relationship to diameter, although the documentation names diameter
     as the explanatory variable. Rebuilding from the diameters lifted the
     present-day gate from 0.416 to 0.732 on identical sites. The rebuilt
     values are taken from Run_03 unchanged rather than recomputed, so the two
     folders cannot drift apart.

  2. THE AGB-VERSUS-BASAL-AREA FLOOR IS RETIRED.
     It existed to exclude TERN and CSIRO wholesale, because their reported
     biomass contradicted their own basal area. After the rebuild they pass on
     their own merits - TERN from 5.7 to 98.1 per cent of surveys passing,
     CSIRO from 74.8 to 100 - so the filter is now excluding sound data for a
     defect that has been repaired.

  3. PLOT-AREA THRESHOLD 0.04 ha (Run_02).
     Readmits 201 DELWP Victoria visits, all at exactly 0.04 ha, median 225
     Mg/ha on 30.8 m2/ha of basal area for a ratio of 7.3 - right on the
     library median. They failed the old threshold by one hundredth of a
     hectare and nothing else, and they are almost the whole of the sample
     below 37 S.

  4. A CEILING ON THE AGB-TO-BASAL-AREA RATIO, replacing the plot-area floor as
     the inflation control.
     The floor tested in Plot_area_floor_method works, but it is a proxy: it
     removes inflation by removing small plots, including small plots that are
     internally consistent. A ceiling removes the inflated records directly -
     University of NSW at about 106, Queensland Herbarium at 35.6 - and leaves
     Victoria's 0.04 ha plots alone.

     The ceiling is set at the 95th percentile of the VERIFIED-MATURE group
     rather than at a round number, so it is calibrated on the stands the
     validation is about rather than chosen. It is computed on the REBUILT
     ratio, because that is the quantity the rest of the run uses.

  5. THE DBH MATURITY FILTER IS KEPT (Run_04).
     Every basal-area threshold drove the present-day gate to or below zero
     once the unlabelled sites entered, because those sites correlate
     negatively with M'. And M' is a ceiling, so validating it needs stands
     near their maximum.

Order matters. The ceiling is calibrated AFTER the rebuild, on rebuilt values,
because the reported ratios are the ones the rebuild exists to correct.

Reads   ../../Step_01_build_reference_table.py    imported, not modified
        ../Run_03/outputs/agb_rebuilt_by_survey.csv
Writes  outputs/reference_table_combined.csv
        outputs/build_trail.csv
        outputs/ceiling_calibration.csv
        outputs/provider_effects.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_build_table.py
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
MATURE = ["verified mature", "likely mature"]
VERIFIED = "verified mature"


def find_up(start, name):
    for d in [start] + list(start.parents):
        if (d / name).exists():
            return d
    raise SystemExit("%s not found above %s" % (name, start))


PARENT = find_up(HERE, "Step_01_build_reference_table.py")


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "stv_step01", PARENT / "Step_01_build_reference_table.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["stv_step01"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-area", type=float, default=0.04)
    ap.add_argument("--ceiling-percentile", type=float, default=95.0,
                    help="of the verified-mature group's rebuilt ratio")
    ap.add_argument("--exponent", default="b2p5",
                    help="which Run_03 rebuild to use")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trail = []

    # ---- 1 and 3: the base table, 0.04 ha, no AGB:BA floor ------------ #
    B = load_builder()
    print("parent thresholds: area %.2f ha, AGB per m2/ha basal area >= %.1f"
          % (B.MIN_AREA_HA, B.MIN_AGB_PER_BA))
    B.MIN_AREA_HA = args.min_area
    B.OUT_DIR = OUT_DIR
    argv = sys.argv
    sys.argv = ["Step_01_build_reference_table.py", "--keep-all-classes",
                "--keep-inconsistent-agb"]
    try:
        print("\nbuilding at %.2f ha with the AGB-versus-basal-area floor "
              "retired" % args.min_area)
        B.main()
    finally:
        sys.argv = argv
    src = OUT_DIR / "reference_table_noqc.csv"
    if not src.exists():
        raise SystemExit("expected %s" % src)
    ref = pd.read_csv(src, low_memory=False)
    trail.append(("base table: 0.04 ha, no consistency floor", len(ref)))
    for junk in ("reference_table_noqc.csv", "filter_trail_noqc.csv",
                 "reference_table_summary_noqc.csv"):
        p = OUT_DIR / junk
        if p.exists():
            shutil.move(str(p), str(OUT_DIR / junk.replace("_noqc", "_base")))

    # ---- 2: the rebuilt biomass, taken from Run_03 unchanged ---------- #
    reb_f = HERE.parent / "Run_03" / "outputs" / "agb_rebuilt_by_survey.csv"
    if not reb_f.exists():
        raise SystemExit("run Run_03/Step_02_recompute_agb.py first - %s"
                         % reb_f)
    reb = pd.read_csv(reb_f)
    per_site = (reb.sort_values("agb_rebuilt", ascending=False)
                .drop_duplicates("site")[["site", "agb_rebuilt"]])
    ref = ref.merge(per_site, on="site", how="left")
    ref["agb_reported"] = ref["agb"]
    covered = ref["agb_rebuilt"].notna()
    ref.loc[covered, "agb"] = ref.loc[covered, "agb_rebuilt"]
    print("\nrebuilt biomass attached to %d of %d sites"
          % (int(covered.sum()), len(ref)))
    with np.errstate(invalid="ignore", divide="ignore"):
        ref["agb_per_ba"] = ref["agb"] / ref["live_ba"]

    # ---- 5: the DBH maturity filter ----------------------------------- #
    ref = ref[ref["maturity"].isin(MATURE)].reset_index(drop=True)
    trail.append(("DBH maturity filter (verified or likely)", len(ref)))
    ref = ref[ref["agb_rebuilt"].notna()].reset_index(drop=True)
    trail.append(("rebuilt biomass available", len(ref)))

    # ---- 4: the ceiling, calibrated on the verified-mature group ------ #
    ver = ref.loc[ref["maturity"] == VERIFIED, "agb_per_ba"].dropna()
    ceiling = float(np.percentile(ver, args.ceiling_percentile))
    print("\nceiling from the %.0fth percentile of the verified-mature "
          "group's rebuilt ratio: %.2f Mg per m2/ha"
          % (args.ceiling_percentile, ceiling))
    cal = pd.DataFrame([dict(
        percentile=args.ceiling_percentile, ceiling=ceiling,
        verified_sites=len(ver),
        verified_median=float(ver.median()),
        verified_p75=float(np.percentile(ver, 75)),
        verified_p95=float(np.percentile(ver, 95)),
        verified_max=float(ver.max()))])
    cal.to_csv(OUT_DIR / "ceiling_calibration.csv", index=False)

    before = ref.copy()
    ref = ref[ref["agb_per_ba"] <= ceiling].reset_index(drop=True)
    trail.append(("ratio at or below the ceiling (%.1f)" % ceiling, len(ref)))

    dropped = before[~before["site"].isin(set(ref["site"]))]
    if len(dropped):
        print("\nthe ceiling removes %d sites, from:" % len(dropped))
        print(dropped.groupby("source").agg(
            sites=("agb", "size"), ratio=("agb_per_ba", "median"),
            agb=("agb", "median")).sort_values("sites", ascending=False)
            .head(6).round(1).to_string())

    prov = before.assign(kept=before["site"].isin(set(ref["site"]))).groupby(
        "source").agg(sites=("agb", "size"), kept=("kept", "sum"),
                      ratio_median=("agb_per_ba", "median"),
                      agb_median=("agb", "median"),
                      area_median=("area_ha", "median")).reset_index()
    prov["pct_kept"] = 100 * prov["kept"] / prov["sites"]
    prov.sort_values("sites", ascending=False).to_csv(
        OUT_DIR / "provider_effects.csv", index=False)

    dst = OUT_DIR / "reference_table_combined.csv"
    ref.to_csv(dst, index=False)
    pd.DataFrame(trail, columns=["step", "sites"]).to_csv(
        OUT_DIR / "build_trail.csv", index=False)

    print("\n--- build trail ---")
    for s, n in trail:
        print("  %-52s %5d" % (s, n))
    print("\n%s : %d sites (%d verified, %d likely), south of 37 S: %d"
          % (dst.name, len(ref),
             int((ref["maturity"] == VERIFIED).sum()),
             int((ref["maturity"] == "likely mature").sum()),
             int((ref["latitude"] < -37).sum())))
    print("median observed AGB %.1f, median ratio %.1f, median plot %.2f ha"
          % (ref["agb"].median(), ref["agb_per_ba"].median(),
             ref["area_ha"].median()))


if __name__ == "__main__":
    main()
