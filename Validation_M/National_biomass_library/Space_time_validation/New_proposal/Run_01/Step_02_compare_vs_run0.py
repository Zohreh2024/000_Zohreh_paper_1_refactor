"""
Run 1 against Run 0, and the diagnostic that motivated it.

Three things, in order.

1. WHY THE TWO CLASSES DIFFER. The present-day gate, split by maturity class,
   on the quantities that bear on it: the ratio, the rank correlation, the
   observed biomass, the plot area, and biomass per unit of the stand's own
   live basal area. The last one is the diagnostic. It has nothing to do with
   M' - it is internal to the observation - so a difference in it is a
   difference in the data, not in the model.

2. RUN 1 AGAINST RUN 0, everywhere. Both read from the `analogue found`
   stratum, and both nulls are carried, because a change of sample changes the
   nulls too and a delta against a moving null means nothing.

3. WHAT IT COST. Halving the sample widens every interval. The bootstrap
   interval on the median ratio is reported for both runs so the gain can be
   read against the precision lost.

Reads   outputs/*.csv                      Run 1, from Step_01
        ../../outputs/*_nvis.csv           Run 0, the published configuration
        ../../outputs/reference_table.csv
Writes  outputs/gate_by_maturity.csv
        outputs/run01_vs_run00.csv
        outputs/summary.csv

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_compare_vs_run0.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
SRC_OUT = HERE.parents[1] / "outputs"
# The one-at-a-time study, which computes BOTH nulls in every run.
OFAT_OUT = HERE.parent / "Run_0" / "outputs"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
FUTURE = ["%s_%s" % (a, w) for w in WINDOWS for a in SSPS]
CONTROLS = ["same_cell_present_day", "historical_analogue", "random_cells"]
BOOT = 2000


def boot_median_ratio(r, n_boot=BOOT, seed=0):
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    meds = np.median(rng.choice(r, (n_boot, len(r)), replace=True), axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def gate_by_maturity(ref, m0):
    """The present-day gate split by class - the reason Run 1 exists."""
    g = m0[m0["run"] == "same_cell_present_day"].merge(
        ref[["site", "agb_per_ba", "live_ba", "area_ha", "n_stems"]],
        on="site", how="left")
    rows = []
    for cls, s in g.groupby("maturity"):
        ratio = (s["M_matched"] / s["agb"]).to_numpy()
        lo, hi = boot_median_ratio(ratio)
        rows.append(dict(
            maturity=cls, n=len(s),
            median_ratio=float(np.median(ratio)), ratio_lo=lo, ratio_hi=hi,
            spearman_rho=float(sps.spearmanr(s["agb"], s["M_matched"]).correlation),
            obs_agb_median=float(s["agb"].median()),
            M_median=float(s["M_matched"].median()),
            agb_per_basal_area=float(s["agb_per_ba"].median()),
            live_basal_area=float(s["live_ba"].median()),
            plot_area_ha=float(s["area_ha"].median()),
            max_dbh=float(s["max_dbh"].median()),
            n_stems=float(s["n_stems"].median())))
    both = g[g["maturity"].isin(["verified mature", "likely mature"])]
    ratio = (both["M_matched"] / both["agb"]).to_numpy()
    lo, hi = boot_median_ratio(ratio)
    rows.append(dict(
        maturity="POOLED (Run 0)", n=len(both),
        median_ratio=float(np.median(ratio)), ratio_lo=lo, ratio_hi=hi,
        spearman_rho=float(sps.spearmanr(both["agb"],
                                         both["M_matched"]).correlation),
        obs_agb_median=float(both["agb"].median()),
        M_median=float(both["M_matched"].median()),
        agb_per_basal_area=float(both["agb_per_ba"].median()),
        live_basal_area=float(both["live_ba"].median()),
        plot_area_ha=float(both["area_ha"].median()),
        max_dbh=float(both["max_dbh"].median()),
        n_stems=float(both["n_stems"].median())))
    return pd.DataFrame(rows)


def found_rows(metrics):
    """The analogue-found stratum, which is the only one worth reading."""
    d = metrics[metrics["stratum"] == "analogue found"].copy()
    return d.set_index("run")


def interval_from_matches(matches):
    """A bootstrap interval on the median ratio, per run, analogue-found only."""
    rows = []
    for run, g in matches.groupby("run", sort=False):
        f = g[~g["no_analogue"]] if "no_analogue" in g.columns else g
        r = (f["M_matched"] / f["agb"]).to_numpy()
        lo, hi = boot_median_ratio(r)
        rows.append(dict(run=run, ratio_lo=lo, ratio_hi=hi,
                         n_found=int(len(f))))
    return pd.DataFrame(rows).set_index("run")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    ref = pd.read_csv(SRC_OUT / "reference_table.csv", low_memory=False)
    m0 = pd.read_csv(SRC_OUT / "matches_nvis.csv")
    m1 = pd.read_csv(OUT_DIR / "matches_nvis.csv")
    r0 = found_rows(pd.read_csv(SRC_OUT / "metrics_by_run_nvis.csv"))
    r1 = found_rows(pd.read_csv(OUT_DIR / "metrics_by_run_nvis.csv"))
    i0, i1 = interval_from_matches(m0), interval_from_matches(m1)

    # Step_03 draws its null under whatever constraint the run used, so with
    # --constrain nvis it produces the CONSTRAINED null only. The
    # unconstrained one is required beside it, and comes from the one-at-a-time
    # study next door, which computes both in every run on the same seed - its
    # constrained null reproduces Step_03's exactly, which is what makes the
    # pairing legitimate.
    nulls = []
    for rid, tag in (("run00_baseline", "Run 0"),
                     ("run01_verified_only", "Run 1")):
        f = OFAT_OUT / rid / "metrics.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f).set_index("run")
        for nm, lab in (("random_cells_nvis", "NVIS-constrained"),
                        ("random_cells_unconstrained", "unconstrained")):
            if nm in d.index:
                nulls.append(dict(run=tag, null=lab,
                                  median_ratio=float(d.loc[nm, "median_ratio"]),
                                  spearman_rho=float(d.loc[nm, "spearman_rho"]),
                                  n=int(d.loc[nm, "n"])))
    if nulls:
        nd = pd.DataFrame(nulls)
        nd.to_csv(OUT_DIR / "both_nulls.csv", index=False)
        print("=== both nulls, Run 0 and Run 1 ===")
        print(nd.to_string(index=False, float_format=lambda v: "%.3f" % v))
        print()

    # --- 1. the diagnostic ------------------------------------------------ #
    gate = gate_by_maturity(ref, m0)
    gate.to_csv(OUT_DIR / "gate_by_maturity.csv", index=False)
    print("=== the present-day gate, split by maturity class ===")
    print(gate[["maturity", "n", "median_ratio", "spearman_rho",
                "obs_agb_median", "agb_per_basal_area", "plot_area_ha",
                "max_dbh"]].to_string(
        index=False, float_format=lambda v: "%.2f" % v))

    # --- 2. Run 1 against Run 0 ------------------------------------------- #
    rows = []
    for run in list(r0.index):
        if run not in r1.index:
            continue
        a, b = r0.loc[run], r1.loc[run]
        rows.append(dict(
            run=run,
            n_run0=int(a["n"]), n_run1=int(b["n"]),
            ratio_run0=float(a["median_ratio"]),
            ratio_run1=float(b["median_ratio"]),
            d_ratio=float(b["median_ratio"] - a["median_ratio"]),
            rho_run0=float(a["spearman_rho"]),
            rho_run1=float(b["spearman_rho"]),
            d_rho=float(b["spearman_rho"] - a["spearman_rho"]),
            no_analogue_run0=float(100 * a["n_no_analogue"] / 600
                                   if "n_no_analogue" in a else np.nan),
            ratio_ci_run0="%.3f-%.3f" % (i0.loc[run, "ratio_lo"],
                                         i0.loc[run, "ratio_hi"])
            if run in i0.index else "",
            ratio_ci_run1="%.3f-%.3f" % (i1.loc[run, "ratio_lo"],
                                         i1.loc[run, "ratio_hi"])
            if run in i1.index else "",
            ci_width_run0=float(i0.loc[run, "ratio_hi"] - i0.loc[run, "ratio_lo"])
            if run in i0.index else np.nan,
            ci_width_run1=float(i1.loc[run, "ratio_hi"] - i1.loc[run, "ratio_lo"])
            if run in i1.index else np.nan))
    cmp = pd.DataFrame(rows)
    cmp["is_future"] = cmp["run"].isin(FUTURE)
    cmp.to_csv(OUT_DIR / "run01_vs_run00.csv", index=False)

    print("\n=== Run 1 (verified only) against Run 0, analogue-found ===")
    print(cmp[["run", "n_run0", "n_run1", "ratio_run0", "ratio_run1",
               "d_ratio", "rho_run0", "rho_run1", "d_rho"]].to_string(
        index=False, float_format=lambda v: "%.3f" % v))

    fut = cmp[cmp["is_future"]]
    print("\n=== the eight scenario-windows, median ===")
    print("  ratio  %.3f -> %.3f   (%+.3f)"
          % (fut["ratio_run0"].median(), fut["ratio_run1"].median(),
             fut["d_ratio"].median()))
    print("  rho    %.3f -> %.3f   (%+.3f)"
          % (fut["rho_run0"].median(), fut["rho_run1"].median(),
             fut["d_rho"].median()))
    print("  bootstrap interval on the median ratio widened from %.3f to %.3f"
          % (fut["ci_width_run0"].median(), fut["ci_width_run1"].median()))

    summary = pd.DataFrame([dict(
        quantity="median ratio, eight future windows",
        run0=fut["ratio_run0"].median(), run1=fut["ratio_run1"].median(),
        delta=fut["d_ratio"].median()),
        dict(quantity="Spearman rho, eight future windows",
             run0=fut["rho_run0"].median(), run1=fut["rho_run1"].median(),
             delta=fut["d_rho"].median()),
        dict(quantity="sites",
             run0=float(cmp["n_run0"].max()), run1=float(cmp["n_run1"].max()),
             delta=float(cmp["n_run1"].max() - cmp["n_run0"].max())),
        dict(quantity="width of the 95% interval on the median ratio",
             run0=fut["ci_width_run0"].median(),
             run1=fut["ci_width_run1"].median(),
             delta=fut["ci_width_run1"].median()
             - fut["ci_width_run0"].median())])
    summary.to_csv(OUT_DIR / "summary.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
