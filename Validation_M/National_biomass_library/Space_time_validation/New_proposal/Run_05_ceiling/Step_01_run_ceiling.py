"""
Run 5 - the AGB-to-basal-area ceiling, tested on its own.

Why this run exists
-------------------
combined_Run introduced a ceiling on the ratio of biomass to the stand's own
live basal area, and its report flagged that the ceiling had never been tested
against Run 0 in isolation. It was also the one ingredient of that
configuration that did not do what it was asked to do: it was proposed to
remove University of NSW at a ratio near 106 and Queensland Herbarium at 35.6,
but those are REPORTED ratios and the rebuild had already repaired them. This
run supplies the missing test.

The calibration is not transferable, so it is redone
----------------------------------------------------
combined_Run set the ceiling at the 95th percentile of the verified-mature
group's REBUILT ratio, which is 34.5. Against Run 0 the quantity is the
REPORTED ratio, whose distribution is far wider - the same percentile of the
same group is 51.97. Applying 34.5 to Run 0 would be testing two changes at
once, so the ceiling is recalibrated on each base it is applied to, and the
percentile rather than the value is what is held fixed.

    verified-mature reported ratio     median 7.27, p90 37.3, p95 52.0, p99 88.3
    verified-mature rebuilt ratio      p95 34.5   (combined_Run)

The percentile itself is a free parameter, so three are run.

The configurations
------------------
    run0                   Run 0 as published                        600 sites
    ceiling_p90            Run 0 + ceiling at the verified p90       496
    ceiling_p95            Run 0 + ceiling at the verified p95       542
    ceiling_p99            Run 0 + ceiling at the verified p99       585
    rebuilt                Run 3's rebuilt biomass, no ceiling       599
    rebuilt_ceiling_p95    + the ceiling, as combined_Run applies it

The last two are the second question this run answers: the ceiling's marginal
effect on the rebuilt base, which is the only place combined_Run actually uses
it. They are labelled separately because they are a different comparison, not a
continuation of the first four.

Everything else is Run 0 throughout: NVIS-constrained matching, Eq. (1) of the
window-mean FPI, all 174 predictors, PCA to 95 per cent, the 99th percentile
cutoff. Both nulls in every configuration; every metric from the
analogue-found stratum.

Reads   ../../outputs/reference_table.csv
        ../Run_03/outputs/reference_table_rebuilt_b2p5.csv
        ../Run_0/Step_A_run_ofat.py            imported for its helpers
Writes  outputs/ceiling_calibration.csv
        outputs/removed_by_ceiling.csv
        outputs/<config>/matches.csv, metrics.csv
        outputs/run05_summary.csv, run05_headline.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_run_ceiling.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
OFAT = HERE.parent / "Run_0" / "Step_A_run_ofat.py"
MATURE = ["verified mature", "likely mature"]
VERIFIED = "verified mature"


def load_ofat():
    spec = importlib.util.spec_from_file_location("ofat_runner", OFAT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ofat_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


OF = load_ofat()
SSPS, WINDOWS, CONTROLS = OF.SSPS, OF.WINDOWS, OF.CONTROLS
BASE = dict(OF.BASELINE)


def base_reported():
    d = OF.reference("reference_table.csv")
    return d[d["maturity"].isin(MATURE)].copy()


def base_rebuilt():
    d = pd.read_csv(HERE.parent / "Run_03" / "outputs"
                    / "reference_table_rebuilt_b2p5.csv", low_memory=False)
    return d[d["maturity"].isin(MATURE) & d["agb_rebuilt"].notna()].copy()


def ceiling_of(d, pct):
    """The percentile of the verified-mature group's ratio, on THIS base."""
    v = d.loc[d["maturity"] == VERIFIED, "agb_per_ba"].dropna()
    return float(np.percentile(v, pct))


def execute(name, note, loader, pct=None):
    cfg = dict(BASE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = loader()
    ceiling = np.nan
    removed = None
    if pct is not None:
        ceiling = ceiling_of(ref, pct)
        removed = ref[ref["agb_per_ba"] > ceiling].copy()
        ref = ref[ref["agb_per_ba"] <= ceiling]
        print("    ceiling at the verified p%g = %.2f; removes %d sites"
              % (pct, ceiling, len(removed)))
    ref = ref.reset_index(drop=True)
    print("    %d sites, median AGB %.1f, median ratio %.1f"
          % (len(ref), ref["agb"].median(), ref["agb_per_ba"].median()))
    if len(ref) < 25:
        return None, None

    hist_X, _ = OF.S3.feature_block(hist["X"], names, cfg["features"])
    ref_X, _ = OF.S3.feature_block(ref[list(names)].to_numpy("float32"), names,
                                   cfg["features"])
    mu, sd, pca = OF.S3.build_space(hist_X, cfg["variance"])
    hist_P = OF.S3.project(hist_X, mu, sd, pca)
    ref_P = OF.S3.project(ref_X, mu, sd, pca)

    d_self, _ = cKDTree(hist_P).query(hist_P, k=2, workers=-1)
    cutoff = float(np.percentile(d_self[:, 1], cfg["cutoff_pct"]))

    site_cls = OF.nvis_at(ref["row"].to_numpy(), ref["col"].to_numpy())
    pool_cls = OF.nvis_at(hist["rows"], hist["cols"])

    frames = []
    same = ref[["site", "x", "y", "agb", "M_hist", "fpi_hist", "maturity",
                "year", "source"]].copy()
    same["run"] = "same_cell_present_day"
    same["match_x"], same["match_y"] = same["x"], same["y"]
    same["M_matched"], same["fpi_matched"] = same["M_hist"], same["fpi_hist"]
    same["match_distance"] = 0.0
    same["no_analogue"] = False
    same["class_fallback"] = False
    same["displacement_km"] = 0.0
    frames.append(same)

    frames.append(OF.one_run("historical_analogue", ref, ref_P, hist, hist_P,
                             cutoff, cfg, site_class=site_cls,
                             pool_class=pool_cls))
    frames.append(OF.one_run("random_cells_nvis", ref, ref_P, hist, hist_P,
                             cutoff, cfg, random_match=True,
                             site_class=site_cls, pool_class=pool_cls))
    frames.append(OF.one_run("random_cells_unconstrained", ref, ref_P, hist,
                             hist_P, cutoff, cfg, random_match=True))

    for win in WINDOWS:
        for ssp in SSPS:
            t = tab["future_table_%s_%s" % (ssp, win)]
            fut_X, _ = OF.S3.feature_block(t["X"], names, cfg["features"])
            fut_P = OF.S3.project(fut_X, mu, sd, pca)
            mp = OF.mprime_at(cfg["order"], ssp, win, t["rows"], t["cols"])
            frames.append(OF.one_run("%s_%s" % (ssp, win), ref, ref_P, t,
                                     fut_P, cutoff, cfg, site_class=site_cls,
                                     pool_class=pool_cls, mprime_override=mp))

    matches = pd.concat(frames, ignore_index=True)
    dst = OUT_DIR / name
    dst.mkdir(parents=True, exist_ok=True)
    matches.to_csv(dst / "matches.csv", index=False)

    rows = []
    for label, grp in matches.groupby("run", sort=False):
        found = grp[~grp["no_analogue"]]
        m = OF.S3.metrics(found["agb"].to_numpy(),
                          found["M_matched"].to_numpy(),
                          found["match_distance"].to_numpy())
        rows.append(dict(config=name, note=note, run=label, n_sites=len(grp),
                         percentile=pct if pct is not None else np.nan,
                         ceiling=ceiling, n_analogue_found=len(found),
                         pct_no_analogue=100 * float(grp["no_analogue"].mean()),
                         median_agb=float(ref["agb"].median()),
                         median_agb_per_ba=float(
                             ref["agb_per_ba"].median()), **m))
    met = pd.DataFrame(rows)
    met.to_csv(dst / "metrics.csv", index=False)

    fut = met[~met["run"].isin(CONTROLS)]
    gate = met[met["run"] == "same_cell_present_day"]["spearman_rho"].iloc[0]
    nn = met[met["run"] == "random_cells_nvis"]["spearman_rho"].iloc[0]
    print("    gate rho %.3f   future rho %.3f   null %.3f   gap %+.3f   %.0fs"
          % (gate, fut["spearman_rho"].median(), nn,
             fut["spearman_rho"].median() - nn, time.time() - t0))
    return met, removed


CONFIGS = [
    ("run0", "Run 0 as published", base_reported, None),
    ("ceiling_p90", "Run 0 + ceiling at the verified p90", base_reported, 90),
    ("ceiling_p95", "Run 0 + ceiling at the verified p95", base_reported, 95),
    ("ceiling_p99", "Run 0 + ceiling at the verified p99", base_reported, 99),
    ("rebuilt", "Run 3's rebuilt biomass, no ceiling", base_rebuilt, None),
    ("rebuilt_ceiling_p95", "rebuilt + ceiling, as combined_Run applies it",
     base_rebuilt, 95),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- the calibration, on both bases ------------------------------- #
    cal = []
    for nm, loader in (("reported (Run 0)", base_reported),
                       ("rebuilt (Run 3)", base_rebuilt)):
        d = loader()
        v = d.loc[d["maturity"] == VERIFIED, "agb_per_ba"].dropna()
        r = dict(base=nm, verified_sites=len(v), median=float(v.median()))
        for q in (90, 95, 99):
            r["p%d" % q] = float(np.percentile(v, q))
            r["keeps_p%d" % q] = int((d["agb_per_ba"]
                                      <= np.percentile(v, q)).sum())
        r["mature_sites"] = len(d)
        cal.append(r)
    calib = pd.DataFrame(cal)
    calib.to_csv(OUT_DIR / "ceiling_calibration.csv", index=False)
    print("=== the ceiling, calibrated on each base ===")
    print(calib.to_string(index=False, float_format=lambda v: "%.2f" % v))

    todo = CONFIGS
    if args.only:
        todo = [c for c in CONFIGS if any(c[0].startswith(p)
                                          for p in args.only)]
    mets, rems = [], []
    for c in todo:
        m, rm = execute(*c)
        if m is not None:
            mets.append(m)
        if rm is not None and len(rm):
            rems.append(rm.assign(config=c[0])[
                ["config", "site", "source", "agb", "live_ba", "agb_per_ba",
                 "area_ha", "maturity"]])
    out = pd.concat(mets, ignore_index=True)
    out.to_csv(OUT_DIR / "run05_summary.csv", index=False)
    if rems:
        pd.concat(rems, ignore_index=True).to_csv(
            OUT_DIR / "removed_by_ceiling.csv", index=False)

    fut = out[~out["run"].isin(CONTROLS)]
    g = fut.groupby("config").agg(
        sites=("n_sites", "max"), ceiling=("ceiling", "max"),
        median_agb=("median_agb", "max"),
        agb_per_ba=("median_agb_per_ba", "max"),
        ratio=("median_ratio", "median"),
        rho=("spearman_rho", "median"),
        no_analogue=("pct_no_analogue", "median")).round(3)
    n = out[out["run"] == "random_cells_nvis"].set_index("config")
    u = out[out["run"] == "random_cells_unconstrained"].set_index("config")
    g["null_nvis_rho"] = n["spearman_rho"].round(3)
    g["gap_rho_nvis"] = (g["rho"] - g["null_nvis_rho"]).round(3)
    g["null_free_rho"] = u["spearman_rho"].round(3)
    g["gate_rho"] = out[out["run"] == "same_cell_present_day"]\
        .set_index("config")["spearman_rho"].round(3)
    order = [c[0] for c in CONFIGS if c[0] in g.index]
    g = g.reindex(order)
    print("\n=== summary, future runs (median of the eight) ===")
    print(g[["sites", "ceiling", "median_agb", "agb_per_ba", "ratio",
             "rho", "null_nvis_rho", "gap_rho_nvis", "gate_rho",
             "no_analogue"]].to_string())
    g.reset_index().to_csv(OUT_DIR / "run05_headline.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
