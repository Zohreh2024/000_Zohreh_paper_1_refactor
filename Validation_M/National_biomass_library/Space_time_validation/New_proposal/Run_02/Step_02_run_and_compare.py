"""
Run 2 - the matching at 0.04 ha, against Run 0 at 0.05 ha.

Four configurations, all mature (verified + likely), everything else held at
Run 0 - NVIS-constrained matching, Eq. (1) of the window-mean FPI, all 174
predictors, PCA to 95 per cent, the 99th percentile cutoff:

    floor_005            the parent's reference table, 600 sites  = Run 0
    floor_004            the rebuilt table at 0.04 ha, 778 sites
    floor_004_no_unsw    the same, dropping University of NSW, whose 27 visits
                         report a median 68 Mg/ha on 0.6 m2/ha of basal area -
                         a ratio near 106, which passes the consistency filter
                         only because that filter is a floor and not a ceiling
    floor_004_south      the southern sites alone, below 37 S, where the change
                         does its work

Both nulls are computed in every configuration and every metric comes from the
analogue-found stratum, as in every run of this study.

Reads   outputs/reference_table_min004.csv        from Step_01
        ../../outputs/reference_table.csv         the 0.05 ha table
        ../Run_0/Step_A_run_ofat.py               imported for its helpers
Writes  outputs/<config>/matches.csv, metrics.csv
        outputs/run02_summary.csv
        outputs/coverage.csv

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
SOUTH = -37.0


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


def reference_005():
    return OF.reference("reference_table.csv")


def reference_004():
    return pd.read_csv(OUT_DIR / "reference_table_min004.csv", low_memory=False)


CONFIGS = [
    ("floor_005", "the parent's 0.05 ha table - Run 0", reference_005,
     dict(drop_source=None, south_only=False)),
    ("floor_004", "the rebuilt 0.04 ha table", reference_004,
     dict(drop_source=None, south_only=False)),
    ("floor_004_no_unsw", "0.04 ha, without University of NSW",
     reference_004, dict(drop_source="University of NSW", south_only=False)),
    ("floor_004_south", "0.04 ha, southern sites only (below 37 S)",
     reference_004, dict(drop_source=None, south_only=True)),
]


def execute(name, note, loader, opt):
    cfg = dict(BASE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = loader()
    ref = ref[ref["maturity"].isin(MATURE)]
    if opt.get("drop_source"):
        before = len(ref)
        ref = ref[ref["source"] != opt["drop_source"]]
        print("    dropped %d %s sites" % (before - len(ref),
                                           opt["drop_source"]))
    if opt.get("south_only"):
        ref = ref[ref["latitude"] < SOUTH]
    ref = ref.reset_index(drop=True)
    n_south = int((ref["latitude"] < SOUTH).sum())
    print("    %d sites, %d south of %.0f S, median plot %.3f ha"
          % (len(ref), n_south, abs(SOUTH), ref["area_ha"].median()))
    if len(ref) < 25:
        print("    too few sites to match - skipped")
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
        rows.append(dict(config=name, note=note, run=label,
                         n_sites=len(grp), n_analogue_found=len(found),
                         n_south=n_south,
                         pct_no_analogue=100 * float(grp["no_analogue"].mean()),
                         median_plot_ha=float(ref["area_ha"].median()),
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


def coverage():
    """Where the two thresholds put their sites."""
    rows = []
    for name, loader in (("0.05 ha", reference_005), ("0.04 ha",
                                                      reference_004)):
        d = loader()
        d = d[d["maturity"].isin(MATURE)]
        rows.append(dict(
            threshold=name, sites=len(d),
            south_of_37=int((d["latitude"] < SOUTH).sum()),
            median_plot_ha=float(d["area_ha"].median()),
            median_agb=float(d["agb"].median()),
            median_agb_per_ba=float(d["agb_per_ba"].median()),
            lat_min=float(d["latitude"].min()),
            n_delwp=int((d["source"] == "DELWP Victoria").sum())))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cov = coverage()
    cov.to_csv(OUT_DIR / "coverage.csv", index=False)
    print("=== what each threshold covers (mature sites) ===")
    print(cov.to_string(index=False, float_format=lambda v: "%.2f" % v))

    todo = CONFIGS
    if args.only:
        todo = [c for c in CONFIGS if any(c[0].startswith(p)
                                          for p in args.only)]
    out = [execute(*c) for c in todo]
    out = pd.concat([o for o in out if o is not None], ignore_index=True)
    out.to_csv(OUT_DIR / "run02_summary.csv", index=False)

    print("\n=== summary, future runs (median of the eight) ===")
    fut = out[~out["run"].isin(CONTROLS)]
    g = fut.groupby("config").agg(
        sites=("n_sites", "max"), south=("n_south", "max"),
        ratio=("median_ratio", "median"), rho=("spearman_rho", "median"),
        no_analogue=("pct_no_analogue", "median")).round(3)
    n = out[out["run"] == "random_cells_nvis"].set_index("config")
    u = out[out["run"] == "random_cells_unconstrained"].set_index("config")
    g["null_nvis_rho"] = n["spearman_rho"].round(3)
    g["gap_rho_nvis"] = (g["rho"] - g["null_nvis_rho"]).round(3)
    g["null_free_rho"] = u["spearman_rho"].round(3)
    print(g.to_string())
    g.reset_index().to_csv(OUT_DIR / "run02_headline.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
