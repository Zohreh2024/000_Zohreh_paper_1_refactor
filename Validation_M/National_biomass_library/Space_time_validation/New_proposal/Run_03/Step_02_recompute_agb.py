"""
Run 3, step 2 - rebuild plot biomass from the stem diameters.

Step_01 showed the stem mass column is not aligned with the stem attributes, so
no subset of it can be repaired. This step discards it and rebuilds biomass
from the diameters, which are a direct measurement.

The form, and why no external coefficients are used
---------------------------------------------------
Tree allometries are power laws in diameter, AGB = a * D^b, with b for
Australian trees in the range 2.3 to 2.7. Two things follow, and together they
let the rebuild proceed without importing coefficients this repository cannot
check:

  b sets the SHAPE. It decides how strongly a plot's biomass is dominated by
  its largest stems, and so it decides the ORDER of plots. The order turns out
  to be nearly invariant across the plausible range, which this step
  demonstrates rather than assumes by running b = 2.3, 2.5 and 2.7.

  a sets only the LEVEL, as a single multiplicative constant. It is therefore
  recoverable from data already known to be sound: Step_01 established that the
  library's PLOT-level totals are consistent (summed by survey and divided by
  area they reproduce the site table at Spearman 0.92) even though the
  stem-level values are not. So `a` is chosen to put the median rebuilt plot
  biomass onto the median reported plot biomass, over the surveys where both
  exist.

Shape from the stems, level from the library's own aggregate. Nothing is
imported and nothing is invented; the one assumption, the exponent, is varied
and reported.

    AGB(subplot) = a * sum(D^b) / subplot area
    AGB(survey)  = mean over the subplots of that survey

Subplot by subplot, because the subplot is the unit that carries an area.

The check that matters
----------------------
The rebuilt biomass is compared with `live_basal_area_ha`, which lives in the
SITE table and was not used to build it. That is a genuine cross-file test: the
tree list's diameters against the site list's basal area. The reported biomass
fails it at Spearman 0.06; anything derived from the diameters should pass it
comfortably, and if it does not, the diameters are wrong too.

Reads   ../../../NBL_download/biolib_treelist.csv, biolib_sitelist.csv
        ../../outputs/reference_table.csv        for the predictor columns
Writes  outputs/agb_rebuilt_by_survey.csv
        outputs/rebuild_checks.csv
        outputs/reference_table_rebuilt_b<b>.csv     one per exponent
        outputs/maturity_and_filter_changes.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_recompute_agb.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
EXPONENTS = [2.3, 2.5, 2.7]
MIN_AGB_PER_BA = 1.0          # the parent's consistency filter
MATURE = ["verified mature", "likely mature"]


def nbl_dir():
    for d in [HERE] + list(HERE.parents):
        if (d / "National_biomass_library" / "NBL_download").exists():
            return d / "National_biomass_library" / "NBL_download"
        if (d / "NBL_download").exists():
            return d / "NBL_download"
    raise SystemExit("NBL_download not found")


def stv_dir():
    for d in [HERE] + list(HERE.parents):
        if (d / "Step_03_match_and_validate.py").exists():
            return d
    raise SystemExit("Space_time_validation not found")


def rebuild(t, b):
    """Plot biomass index from diameters, subplot by subplot."""
    w = t.assign(p=t["diameter"] ** b)
    per_sub = w.groupby(["obs_key", "plot", "subplot"]).agg(
        p_sum=("p", "sum"), area=("subplotarea_ha", "first"),
        stems=("diameter", "size")).reset_index()
    per_sub = per_sub[per_sub["area"] > 0]
    per_sub["index_ha"] = per_sub["p_sum"] / per_sub["area"]
    out = per_sub.groupby("obs_key").agg(
        index_ha=("index_ha", "mean"), subplots=("index_ha", "size"),
        stems=("stems", "sum")).reset_index()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exponents", nargs="*", type=float, default=EXPONENTS)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    NBL, STV = nbl_dir(), stv_dir()

    t = pd.read_csv(NBL / "biolib_treelist.csv", low_memory=False,
                    usecols=["obs_key", "plot", "subplot", "subplotarea_ha",
                             "diameter"])
    for c in ("diameter", "subplotarea_ha"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["diameter", "subplotarea_ha"])
    t = t[(t["diameter"] > 0) & (t["subplotarea_ha"] > 0)]
    print("%s stems in %s surveys" % (format(len(t), ","),
                                      format(t["obs_key"].nunique(), ",")))

    site = pd.read_csv(NBL / "biolib_sitelist.csv", low_memory=False,
                       usecols=["obs_key", "site", "source", "agb_drymass_ha",
                                "live_basal_area_ha", "sampledarea_ha"])
    for c in ("agb_drymass_ha", "live_basal_area_ha", "sampledarea_ha"):
        site[c] = pd.to_numeric(site[c], errors="coerce")

    ref = pd.read_csv(STV / "outputs" / "reference_table.csv", low_memory=False)
    print("reference table: %d sites (%d mature)"
          % (len(ref), int(ref["maturity"].isin(MATURE).sum())))

    checks, tables = [], {}
    for b in args.exponents:
        r = rebuild(t, b)
        j = r.merge(site, on="obs_key", how="inner")
        j = j.dropna(subset=["agb_drymass_ha"])
        j = j[j["agb_drymass_ha"] > 0]
        # the level, from the library's own sound aggregate
        a = float(j["agb_drymass_ha"].median() / j["index_ha"].median())
        j["agb_rebuilt"] = a * j["index_ha"]

        rho_ba_new = stats.spearmanr(j["agb_rebuilt"],
                                     j["live_basal_area_ha"],
                                     nan_policy="omit").correlation
        rho_ba_old = stats.spearmanr(j["agb_drymass_ha"],
                                     j["live_basal_area_ha"],
                                     nan_policy="omit").correlation
        rho_old_new = stats.spearmanr(j["agb_rebuilt"],
                                      j["agb_drymass_ha"]).correlation
        checks.append(dict(
            exponent=b, scale_a=a, surveys=len(j),
            rho_rebuilt_vs_basal_area=rho_ba_new,
            rho_reported_vs_basal_area=rho_ba_old,
            rho_rebuilt_vs_reported=rho_old_new,
            median_rebuilt=float(j["agb_rebuilt"].median()),
            median_reported=float(j["agb_drymass_ha"].median())))
        tables[b] = j[["obs_key", "site", "source", "agb_rebuilt",
                       "agb_drymass_ha", "live_basal_area_ha",
                       "sampledarea_ha", "stems", "subplots"]].copy()

    chk = pd.DataFrame(checks)
    chk.to_csv(OUT_DIR / "rebuild_checks.csv", index=False)
    print("\n=== the cross-file check: diameters against the site table's "
          "basal area ===")
    print(chk[["exponent", "surveys", "rho_reported_vs_basal_area",
               "rho_rebuilt_vs_basal_area", "rho_rebuilt_vs_reported",
               "scale_a"]].to_string(index=False,
                                     float_format=lambda v: "%.4g" % v))

    # how much does the exponent change the ORDER of surveys?
    base = tables[args.exponents[0]].set_index("obs_key")["agb_rebuilt"]
    print("\n=== does the exponent change the ordering? ===")
    for b in args.exponents[1:]:
        other = tables[b].set_index("obs_key")["agb_rebuilt"]
        common = base.index.intersection(other.index)
        print("  b=%.1f against b=%.1f : spearman %.4f"
              % (b, args.exponents[0],
                 stats.spearmanr(base.loc[common], other.loc[common]).correlation))

    # ---- rebuild the reference table, one per exponent ---------------- #
    changes = []
    for b in args.exponents:
        j = tables[b]
        # one row per site, matching the parent's max-measurement rule
        per_site = j.sort_values("agb_rebuilt", ascending=False)\
                    .drop_duplicates("site")[["site", "agb_rebuilt",
                                              "live_basal_area_ha"]]
        new = ref.merge(per_site, on="site", how="left")
        covered = new["agb_rebuilt"].notna()
        new["agb_reported"] = new["agb"]
        new.loc[covered, "agb"] = new.loc[covered, "agb_rebuilt"]
        with np.errstate(invalid="ignore", divide="ignore"):
            new["agb_per_ba"] = new["agb"] / new["live_ba"]
        keep = new["agb_per_ba"] >= MIN_AGB_PER_BA
        changes.append(dict(
            exponent=b, sites=len(new), with_stem_data=int(covered.sum()),
            mature_before=int(ref["maturity"].isin(MATURE).sum()),
            mature_after=int(new.loc[keep, "maturity"].isin(MATURE).sum()),
            pass_consistency=int(keep.sum()),
            median_agb_before=float(ref["agb"].median()),
            median_agb_after=float(new["agb"].median())))
        dst = OUT_DIR / ("reference_table_rebuilt_b%s.csv"
                         % str(b).replace(".", "p"))
        new[keep].to_csv(dst, index=False)
        print("  wrote %s : %d sites, %d mature"
              % (dst.name, int(keep.sum()),
                 int(new.loc[keep, "maturity"].isin(MATURE).sum())))

    ch = pd.DataFrame(changes)
    ch.to_csv(OUT_DIR / "maturity_and_filter_changes.csv", index=False)
    tables[args.exponents[len(args.exponents) // 2]].to_csv(
        OUT_DIR / "agb_rebuilt_by_survey.csv", index=False)
    print("\n%s" % ch.to_string(index=False, float_format=lambda v: "%.1f" % v))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
