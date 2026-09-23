"""
Run 3, step 3 - the matching on the rebuilt biomass.

Five configurations, all mature, everything else held at Run 0 -
NVIS-constrained matching, Eq. (1) of the window-mean FPI, all 174 predictors,
PCA to 95 per cent, the 99th percentile cutoff. Both nulls in every
configuration; every metric from the analogue-found stratum.

    reported_all        Run 0: the reference table as published
    reported_stem_only  the same table, restricted to the sites that HAVE stem
                        data, so the rebuilt runs can be compared on identical
                        sites. Without this the comparison confounds the
                        recomputation with the change of sample.
    rebuilt_b2p3        biomass rebuilt from diameters, exponent 2.3
    rebuilt_b2p5        exponent 2.5 - the headline
    rebuilt_b2p7        exponent 2.7

The pairing is the point. reported_stem_only and rebuilt_b2p5 contain the same
sites, matched the same way, against the same M'. The only difference is where
the observed biomass came from: a column that does not track diameter, or the
diameters themselves.

Reads   outputs/reference_table_rebuilt_b*.csv       from Step_02
        ../../outputs/reference_table.csv
        ../Run_0/Step_A_run_ofat.py                  imported for its helpers
Writes  outputs/<config>/matches.csv, metrics.csv
        outputs/run03_summary.csv, run03_headline.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_run_and_compare.py
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


def ref_reported():
    return OF.reference("reference_table.csv")


def ref_rebuilt(tag):
    return pd.read_csv(OUT_DIR / ("reference_table_rebuilt_%s.csv" % tag),
                       low_memory=False)


def stem_sites():
    """The sites the rebuild covers - used to pair the reported run to it."""
    d = ref_rebuilt("b2p5")
    return set(d.loc[d["agb_rebuilt"].notna(), "site"])


CONFIGS = [
    ("reported_all", "Run 0 - the reference table as published",
     lambda: ref_reported(), False),
    ("reported_stem_only", "the published table, sites with stem data only",
     lambda: ref_reported(), True),
    ("rebuilt_b2p3", "biomass rebuilt from diameters, exponent 2.3",
     lambda: ref_rebuilt("b2p3"), False),
    ("rebuilt_b2p5", "biomass rebuilt from diameters, exponent 2.5",
     lambda: ref_rebuilt("b2p5"), False),
    ("rebuilt_b2p7", "biomass rebuilt from diameters, exponent 2.7",
     lambda: ref_rebuilt("b2p7"), False),
]


def execute(name, note, loader, restrict):
    cfg = dict(BASE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = loader()
    ref = ref[ref["maturity"].isin(MATURE)]
    if "agb_rebuilt" in ref.columns:
        ref = ref[ref["agb_rebuilt"].notna()]
    if restrict:
        ref = ref[ref["site"].isin(stem_sites())]
    ref = ref.reset_index(drop=True)
    print("    %d sites, median observed AGB %.1f" % (len(ref),
                                                      ref["agb"].median()))
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
                         n_analogue_found=len(found),
                         pct_no_analogue=100 * float(grp["no_analogue"].mean()),
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
    out.to_csv(OUT_DIR / "run03_summary.csv", index=False)

    fut = out[~out["run"].isin(CONTROLS)]
    g = fut.groupby("config").agg(
        sites=("n_sites", "max"), median_agb=("median_agb", "max"),
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
    g.reset_index().to_csv(OUT_DIR / "run03_headline.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
