"""
Combined run, step 2 - the matching, and what each ingredient contributes.

Five configurations. Everything not named is Run 0: NVIS-constrained matching,
Eq. (1) of the window-mean FPI, all 174 predictors, PCA to 95 per cent, the
99th percentile cutoff. Both nulls in every configuration; every metric from
the analogue-found stratum.

    run0                Run 0 as published: reported biomass, 0.05 ha,
                        consistency floor, DBH maturity.          600 sites
    run3_rebuilt        Run 3: the same, with biomass rebuilt.    599
    combined_no_area    rebuilt + floor retired + ceiling, but the threshold
                        left at 0.05 ha - isolates the 0.04 ha change
    combined_no_ceiling rebuilt + floor retired + 0.04 ha, no ceiling -
                        isolates the ceiling
    combined            all four together                          850

The two middle configurations exist so the combination can be decomposed. A
combined run that moves the result says nothing about which ingredient moved
it, and this study has spent five runs establishing that distinction.

Reads   outputs/reference_table_combined.csv          from Step_01
        ../Run_03/outputs/reference_table_rebuilt_b2p5.csv
        ../../outputs/reference_table.csv
        ../Run_0/Step_A_run_ofat.py                   imported for its helpers
Writes  outputs/<config>/matches.csv, metrics.csv
        outputs/combined_summary.csv, combined_headline.csv

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
MATURE = ["verified mature", "likely mature"]


def load_ofat():
    spec = importlib.util.spec_from_file_location("ofat_runner", OFAT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ofat_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


OF = load_ofat()
SSPS, WINDOWS, CONTROLS = OF.SSPS, OF.WINDOWS, OF.CONTROLS
BASE = dict(OF.BASELINE)


def ref_run0():
    d = OF.reference("reference_table.csv")
    return d[d["maturity"].isin(MATURE)]


def ref_run3():
    d = pd.read_csv(HERE.parent / "Run_03" / "outputs"
                    / "reference_table_rebuilt_b2p5.csv", low_memory=False)
    return d[d["maturity"].isin(MATURE) & d["agb_rebuilt"].notna()]


def ref_combined():
    return pd.read_csv(OUT_DIR / "reference_table_combined.csv",
                       low_memory=False)


def ref_combined_no_ceiling():
    """The combined table before the ceiling was applied."""
    d = ref_combined()
    # rebuild it: the base table, mature, rebuilt biomass, no ceiling
    base = pd.read_csv(OUT_DIR / "reference_table_base.csv", low_memory=False)
    reb = pd.read_csv(HERE.parent / "Run_03" / "outputs"
                      / "agb_rebuilt_by_survey.csv")
    per_site = (reb.sort_values("agb_rebuilt", ascending=False)
                .drop_duplicates("site")[["site", "agb_rebuilt"]])
    base = base.merge(per_site, on="site", how="left")
    cov = base["agb_rebuilt"].notna()
    base.loc[cov, "agb"] = base.loc[cov, "agb_rebuilt"]
    with np.errstate(invalid="ignore", divide="ignore"):
        base["agb_per_ba"] = base["agb"] / base["live_ba"]
    return base[base["maturity"].isin(MATURE) & cov]


def ref_combined_no_area():
    """The combined recipe with the threshold left at 0.05 ha."""
    d = ref_combined_no_ceiling()
    cal = pd.read_csv(OUT_DIR / "ceiling_calibration.csv")
    ceiling = float(cal["ceiling"].iloc[0])
    d = d[(d["area_ha"] >= 0.05) & (d["agb_per_ba"] <= ceiling)]
    return d


CONFIGS = [
    ("run0", "Run 0 as published", ref_run0),
    ("run3_rebuilt", "Run 3: biomass rebuilt from diameters", ref_run3),
    ("combined_no_area", "rebuilt + floor retired + ceiling, 0.05 ha",
     ref_combined_no_area),
    ("combined_no_ceiling", "rebuilt + floor retired + 0.04 ha, no ceiling",
     ref_combined_no_ceiling),
    ("combined", "all four together", ref_combined),
]


def execute(name, note, loader):
    cfg = dict(BASE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = loader().reset_index(drop=True)
    south = int((ref["latitude"] < -37).sum())
    print("    %d sites, %d south of 37 S, median AGB %.1f, median ratio %.1f"
          % (len(ref), south, ref["agb"].median(),
             ref["agb_per_ba"].median()))
    if len(ref) < 25:
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
                         n_south=south, n_analogue_found=len(found),
                         pct_no_analogue=100 * float(grp["no_analogue"].mean()),
                         median_agb=float(ref["agb"].median()), **m))
    met = pd.DataFrame(rows)
    met.to_csv(dst / "metrics.csv", index=False)

    fut = met[~met["run"].isin(CONTROLS)]
    gate = met[met["run"] == "same_cell_present_day"]["spearman_rho"].iloc[0]
    nn = met[met["run"] == "random_cells_nvis"]["spearman_rho"].iloc[0]
    print("    gate rho %.3f   future rho %.3f   null %.3f   gap %+.3f"
          % (gate, fut["spearman_rho"].median(), nn,
             fut["spearman_rho"].median() - nn))
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
    out.to_csv(OUT_DIR / "combined_summary.csv", index=False)

    fut = out[~out["run"].isin(CONTROLS)]
    g = fut.groupby("config").agg(
        sites=("n_sites", "max"), south=("n_south", "max"),
        median_agb=("median_agb", "max"), ratio=("median_ratio", "median"),
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
    print(g.to_string())
    g.reset_index().to_csv(OUT_DIR / "combined_headline.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
