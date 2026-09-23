"""
Run 4, step 2 - the matching under a basal-area maturity rule.

Configurations, all with everything else held at Run 0 - NVIS-constrained
matching, Eq. (1) of the window-mean FPI, all 174 predictors, PCA to 95 per
cent, the 99th percentile cutoff. Both nulls in every configuration; every
metric from the analogue-found stratum.

    dbh_rule            Run 0: the DBH rule, 600 sites
    ba_05 .. ba_14      live basal area at or above the threshold, applied to
                        every site including the 932 with no stem record
    ba_07_labelled      the basal-area rule applied ONLY to the sites that
                        carry a DBH label. This is the control that separates
                        the two things the rule does: change the criterion,
                        and expand the sample. Without it a movement cannot be
                        attributed to either.

Why the sample expansion is the point, and the risk in it
---------------------------------------------------------
The DBH rule caps the sample at 600 of 1,688 sites because 932 have no stem
record at all. The basal-area rule reaches them. But it reproduces the DBH
label at an AUC of 0.80, not 1.0, so some of what it admits is not mature - and
the 932 unlabelled sites cannot be checked, because the label they would be
checked against is exactly what they lack.

The unlabelled group's median basal area is 15.7 m2/ha, above the verified
group's 14.8. Either those sites really are mature, or basal area is not
discriminating maturity there. The labelled data cannot settle it. What the
runs below CAN show is whether the larger sample behaves like the smaller one.

Reads   ../../outputs/reference_table.csv
        ../Run_0/Step_A_run_ofat.py            imported for its helpers
Writes  outputs/<config>/matches.csv, metrics.csv
        outputs/run04_summary.csv, run04_headline.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_run_and_compare.py
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


def load_ofat():
    spec = importlib.util.spec_from_file_location("ofat_runner", OFAT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ofat_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


OF = load_ofat()
MATURE = OF.MATURE
SSPS, WINDOWS, CONTROLS = OF.SSPS, OF.WINDOWS, OF.CONTROLS
BASE = dict(OF.BASELINE)

CONFIGS = [
    ("dbh_rule", "Run 0 - the DBH rule", dict(rule="dbh")),
    ("ba_05", "live basal area at least 5 m2/ha", dict(rule="ba", th=5.0)),
    ("ba_07", "live basal area at least 7 m2/ha", dict(rule="ba", th=7.0)),
    ("ba_09", "live basal area at least 9 m2/ha", dict(rule="ba", th=9.0)),
    ("ba_14", "live basal area at least 14 m2/ha", dict(rule="ba", th=14.0)),
    ("ba_07_labelled", "basal area at least 7, labelled sites only",
     dict(rule="ba", th=7.0, labelled_only=True)),
]


def select(ref, opt):
    if opt["rule"] == "dbh":
        return ref[ref["maturity"].isin(MATURE)]
    d = ref[ref["live_ba"].notna() & (ref["live_ba"] >= opt["th"])]
    if opt.get("labelled_only"):
        d = d[d["max_dbh"].notna()]
    return d


def execute(name, note, opt):
    cfg = dict(BASE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = select(OF.reference("reference_table.csv"), opt).reset_index(drop=True)
    n_lab = int(ref["max_dbh"].notna().sum())
    agree = np.nan
    if n_lab:
        agree = float(ref.loc[ref["max_dbh"].notna(), "maturity"]
                      .isin(MATURE).mean())
    print("    %d sites   %d carry a DBH label   of those, %.0f%% are "
          "DBH-mature   median basal area %.1f"
          % (len(ref), n_lab, 100 * agree if np.isfinite(agree) else 0,
             ref["live_ba"].median()))
    if len(ref) < 25:
        print("    too few sites - skipped")
        return None

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
                         n_labelled=n_lab, pct_dbh_mature=100 * agree,
                         n_analogue_found=len(found),
                         pct_no_analogue=100 * float(grp["no_analogue"].mean()),
                         median_ba=float(ref["live_ba"].median()),
                         median_agb=float(ref["agb"].median()), **m))
    met = pd.DataFrame(rows)
    met.to_csv(dst / "metrics.csv", index=False)

    fut = met[~met["run"].isin(CONTROLS)]
    print("    future runs   ratio %.3f  rho %.3f  no-analogue %.1f%%"
          % (fut["median_ratio"].median(), fut["spearman_rho"].median(),
             fut["pct_no_analogue"].median()))
    for c in ("random_cells_nvis", "random_cells_unconstrained"):
        r = met[met["run"] == c]
        if len(r):
            print("    %-27s ratio %.3f  rho %.3f"
                  % (c, r["median_ratio"].iloc[0], r["spearman_rho"].iloc[0]))
    print("    %.0fs" % (time.time() - t0))
    return met


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    todo = CONFIGS
    if args.only:
        todo = [c for c in CONFIGS if any(c[0].startswith(p)
                                          for p in args.only)]
    out = [execute(*c) for c in todo]
    out = pd.concat([o for o in out if o is not None], ignore_index=True)
    out.to_csv(OUT_DIR / "run04_summary.csv", index=False)

    fut = out[~out["run"].isin(CONTROLS)]
    g = fut.groupby("config").agg(
        sites=("n_sites", "max"), labelled=("n_labelled", "max"),
        pct_dbh_mature=("pct_dbh_mature", "max"),
        median_ba=("median_ba", "max"), median_agb=("median_agb", "max"),
        ratio=("median_ratio", "median"), rho=("spearman_rho", "median"),
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
    print(g.to_string())
    g.reset_index().to_csv(OUT_DIR / "run04_headline.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
