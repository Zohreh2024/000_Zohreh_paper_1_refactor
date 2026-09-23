"""
Run 2 - a plot-area floor instead of the maturity filter.

Why this run follows from Run 1
-------------------------------
Run 1 removed the likely-mature half and the result improved: ratio 0.465 to
0.557, rank correlation 0.269 to 0.371. But the diagnostic that motivated it
found the mechanism, and the mechanism was not maturity. The two classes carry
almost the same observed biomass:

    class             n     ratio   rho    AGB/BA   plot area
    verified mature   327   0.61    0.49    7.3      0.40 ha
    likely mature     273   0.34    0.39   17.4      0.24 ha

17.4 Mg of biomass per square metre per hectare of a stand's own live basal
area is at the top of what a stand can physically carry, and those sites were
measured on plots 40 per cent smaller. A per-hectare figure from a smaller plot
is the same few trees divided by less ground. The likely-mature group is not
less mature; it is more inflated.

If that is right, the maturity threshold is a proxy, and filtering on the thing
itself should work better. It should also be cheaper: the maturity filter
discards every site with no stem data at all - 1,088 of 1,688 - whether or not
those sites are well measured. A plot-area floor keeps them.

The floors are not arbitrary. Measured on this reference table, biomass per unit
basal area falls monotonically as the floor rises:

    floor      sites   verified  likely  other   median AGB/BA
    none       1688     327       273    1088     9.0
    0.10 ha    1326     327       269     730     7.1
    0.20 ha     871     245       195     431     6.3
    0.25 ha     676     191       107     378     5.2
    0.30 ha     607     182        87     338     5.0
    0.40 ha     584     178        82     324     4.8
    0.50 ha     365     154        69     142     4.0

At 0.25 ha the sample is LARGER than Run 0's 600 and carries half the
inflation, which is the configuration this run exists to test.

What is held fixed
------------------
Everything else is Run 0: NVIS-constrained matching, Eq. (1) of the window-mean
FPI, all 174 predictors, PCA to 95 per cent of the historical variance, the
99th percentile no-analogue cutoff. The two rules carried through every run in
this study apply here too - BOTH nulls are computed in every configuration, and
every metric comes from the analogue-found stratum.

Nothing outside this folder is written. The matching, the metrics and the
bootstrap are the parent's Step_03 functions, imported through the
one-at-a-time study's runner next door, which already owns its own IO.

The configurations
------------------
    mature_nofloor        Run 0 reproduced: maturity filter, no area floor
    verified_nofloor      Run 1 reproduced: verified only, no area floor
    area_010 .. area_050  NO maturity filter, area floor only
    area_025_mature       both together, to see whether they are complementary
                          or redundant

Reads   ../../outputs/reference_table.csv, tables/*.npz
        ../Run_0/Step_A_run_ofat.py            imported, not modified
Writes  outputs/<config>/matches.csv, metrics.csv
        outputs/area_floor_summary.csv
        outputs/config_matrix.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_run_area_floors.py
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
    """Import the one-at-a-time runner for its helpers.

    It owns the table loading, the NVIS lookup, the M' sampling and the
    matching, all of which are the parent's Step_03 functions underneath.
    Importing runs its module level only; its main() is guarded.
    """
    spec = importlib.util.spec_from_file_location("ofat_runner", OFAT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ofat_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


OF = load_ofat()
MATURE = OF.MATURE
VERIFIED = ["verified mature"]
SSPS, WINDOWS = OF.SSPS, OF.WINDOWS
CONTROLS = OF.CONTROLS

BASE = dict(OF.BASELINE)

CONFIGS = [
    ("mature_nofloor", "Run 0 reproduced - maturity filter, no area floor",
     dict(maturity=MATURE, min_area=0.0)),
    ("verified_nofloor", "Run 1 reproduced - verified mature only",
     dict(maturity=VERIFIED, min_area=0.0)),
    ("area_010", "plot area at least 0.10 ha, every maturity class",
     dict(maturity=None, min_area=0.10)),
    ("area_020", "plot area at least 0.20 ha, every maturity class",
     dict(maturity=None, min_area=0.20)),
    ("area_025", "plot area at least 0.25 ha, every maturity class",
     dict(maturity=None, min_area=0.25)),
    ("area_030", "plot area at least 0.30 ha, every maturity class",
     dict(maturity=None, min_area=0.30)),
    ("area_040", "plot area at least 0.40 ha, every maturity class",
     dict(maturity=None, min_area=0.40)),
    ("area_050", "plot area at least 0.50 ha, every maturity class",
     dict(maturity=None, min_area=0.50)),
    ("area_025_mature", "both filters together - 0.25 ha AND mature",
     dict(maturity=MATURE, min_area=0.25)),
]


def execute(name, note, override):
    """One configuration, start to finish.

    The same sequence as the one-at-a-time runner's execute(), with a plot-area
    filter added and the maturity filter made optional. Kept here rather than
    pushed into that runner so Run_0 stays exactly as it was published.
    """
    cfg = dict(BASE)
    cfg.update({k: v for k, v in override.items() if k != "min_area"})
    min_area = float(override.get("min_area", 0.0))
    maturity = override.get("maturity", MATURE)
    t0 = time.time()
    print("\n=== %s ===\n    %s" % (name, note))

    tab = OF.tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref = OF.reference(cfg["reference_table"])
    if maturity is not None:
        ref = ref[ref["maturity"].isin(maturity)]
    if min_area > 0:
        ref = ref[ref["area_ha"] >= min_area]
    ref = ref.reset_index(drop=True)
    print("    %d sites   median plot %.2f ha   median AGB per m2/ha basal "
          "area %.1f" % (len(ref), ref["area_ha"].median(),
                         ref["agb_per_ba"].median()))

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
    use = (site_cls, pool_cls) if cfg["constrain"] == "nvis" else (None, None)

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
                             cutoff, cfg, site_class=use[0], pool_class=use[1]))
    # Both nulls, every configuration - the rule carried through this study.
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
                                     fut_P, cutoff, cfg, site_class=use[0],
                                     pool_class=use[1], mprime_override=mp))

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
        rows.append(dict(
            config=name, note=note, min_area_ha=min_area,
            maturity="all" if maturity is None else "+".join(maturity),
            run=label, n_sites=len(grp), n_analogue_found=len(found),
            pct_no_analogue=100 * float(grp["no_analogue"].mean()),
            median_plot_ha=float(ref["area_ha"].median()),
            median_agb_per_ba=float(ref["agb_per_ba"].median()),
            **m))
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
    pd.DataFrame([{"config": a, "what": b,
                   "min_area_ha": c.get("min_area", 0.0),
                   "maturity": "all" if c.get("maturity") is None
                               else "+".join(c["maturity"])}
                  for a, b, c in CONFIGS]).to_csv(
        OUT_DIR / "config_matrix.csv", index=False)

    out = pd.concat([execute(*c) for c in todo], ignore_index=True)
    dst = OUT_DIR / "area_floor_summary.csv"
    if dst.exists() and args.only:
        old = pd.read_csv(dst)
        old = old[~old["config"].isin(out["config"].unique())]
        out = pd.concat([old, out], ignore_index=True)
    out.to_csv(dst, index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
