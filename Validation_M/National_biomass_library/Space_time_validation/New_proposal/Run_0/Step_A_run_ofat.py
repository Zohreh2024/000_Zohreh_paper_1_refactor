"""
Step A - the space-for-time validation re-run one change at a time.

The point of the design
-----------------------
The validation next door makes several choices at once - which sites count as
mature, whether matching is constrained to vegetation, which averaging order,
which predictors, how far is too far. When a result moves, a configuration that
changed four things cannot say which one moved it. So every run here changes
EXACTLY ONE thing against Run 0 and holds everything else fixed. The difference
between a run and Run 0 is then attributable, and the runs are comparable to
each other only through Run 0, never directly to one another.

Run 0 is the current configuration: 600 mature sites (327 verified + 273
likely), NVIS-constrained matching, Eq. (1) of the window-mean FPI.

Nothing in Space_time_validation/ is modified. This folder imports the existing
Step_03 as a module and reuses its functions - the matching, the metrics, the
bootstrap - but owns its own input selection and writes only inside
New_proposal/. The reference tables and the nine predictor tables are read from
the parent folder in place.

Two rules carried through every run
-----------------------------------
1. BOTH NULLS ARE REPORTED, ALWAYS. Random cells drawn under the NVIS
   constraint, and random cells drawn without it. They measure different
   things and both are needed to read a run honestly:

     constrained null      about 0.45, close to the real runs. It says that
                           knowing a site's pre-1750 vegetation subgroup is
                           most of what is needed to guess its biomass, so a
                           ratio quoted alone overstates what the matching adds.
     unconstrained null    about 0.20-0.22 with rho near 0.03. It is what shows
                           the method has skill at all, since the analogue
                           search beats it decisively.

   Neither alone is the answer. Quoting only the constrained null understates
   the method; quoting only the unconstrained one overstates it.

2. METRICS COME FROM THE ANALOGUE-FOUND STRATUM. A site whose nearest future
   cell lies beyond the no-analogue cutoff is still assigned a match by the
   k-d tree - there is always a nearest cell - but that match is not an
   analogue. Including those forced matches inflates the median ratio in the
   late-century runs while the rank correlation collapses. Every headline
   number here is computed on the sites that actually retained an analogue,
   and the no-analogue share is reported beside it so the reader knows how
   much of the sample that is.

The runs
--------
Each row changes one parameter. Cost is dominated by the projection and the
k-d tree, so the ordering below is roughly cheapest first; the nine predictor
tables are loaded once and reused across every run.

    run00  baseline                 the current configuration
    run01  maturity                 verified mature only (327 sites)
    run02  constraint               no NVIS constraint on the match
    run03  averaging order          mean of the annual Eq. (1) M
    run04  predictors               the 91 climate columns only
    run05  predictors               16 columns: annual climate + key soil
    run06  PCA variance             0.99 instead of 0.95
    run07  no-analogue cutoff       95th percentile instead of 99th
    run08  neighbours               mean of the 5 nearest instead of 1
    run09  data quality             the sample without the AGB-vs-basal-area
                                    filter (688 sites)
    run10  NVIS fallback            a subgroup needs 100 pool cells, not 25

Reads   ../outputs/reference_table.csv, reference_table_noqc.csv
        ../outputs/tables/*.npz
        Data/Processed/NVIS/nvis_mvs_pre1750_mode_NLUM.tif
        FPI_Accuracy_check/output_Mprime_rf/<order>/maxAbgMF_*.tif
Writes  outputs/<run_id>/matches.csv
        outputs/<run_id>/metrics.csv
        outputs/ofat_summary.csv          one row per run per stratum
        outputs/ofat_deltas.csv           every run against Run 0
        outputs/run_matrix.csv            what each run changed

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_A_run_ofat.py
    ... --only run00 run02          just those runs
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" \
    if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                 # noqa: E402
from scipy.spatial import cKDTree                               # noqa: E402

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent                      # Space_time_validation/
SRC_OUT = PARENT / "outputs"
OUT_DIR = HERE / "outputs"

ROOT = PARENT.parents[2]
NVIS_PATH = ROOT / "Data" / "Processed" / "NVIS" / "nvis_mvs_pre1750_mode_NLUM.tif"
MPRIME = {
    "eq1_of_mean": (ROOT / "FPI_Accuracy_check" / "output_Mprime_rf"
                    / "eq1_of_mean", "maxAbgMF_from_mean_fpi_%s_%s.tif"),
    "mean_of_annual": (ROOT / "FPI_Accuracy_check" / "output_Mprime_rf"
                       / "mean_of_annual", "maxAbgMF_%s_%s_mean.tif"),
}

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
MATURE = ["verified mature", "likely mature"]
VERIFIED = ["verified mature"]

CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells_nvis", "random_cells_unconstrained"]


# --------------------------------------------------------------------------- #
# Import the existing matcher without modifying or running it
# --------------------------------------------------------------------------- #

def load_step03():
    """Import Space_time_validation/Step_03 as a module.

    Importing executes its module level only - the constants, the function
    definitions and the sys.path insertion it needs for `common`. main() is
    guarded by __name__, so nothing runs and nothing is written.
    """
    path = PARENT / "Step_03_match_and_validate.py"
    spec = importlib.util.spec_from_file_location("stv_step03", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["stv_step03"] = mod
    spec.loader.exec_module(mod)
    return mod


S3 = load_step03()


# --------------------------------------------------------------------------- #
# The run matrix - one change each
# --------------------------------------------------------------------------- #

BASELINE = dict(
    reference_table="reference_table.csv",
    maturity=MATURE,
    constrain="nvis",
    order="eq1_of_mean",
    features="all",
    variance=0.95,
    cutoff_pct=99.0,
    k=1,
    min_class_cells=25,
)

RUNS = [
    ("run00_baseline", "(none)", "the current configuration", {}),
    ("run01_verified_only", "maturity",
     "verified mature only, dropping the likely-mature half",
     dict(maturity=VERIFIED)),
    ("run02_unconstrained", "matching constraint",
     "no NVIS constraint on the analogue search",
     dict(constrain="none")),
    ("run03_mean_of_annual", "averaging order",
     "mean of the annual Eq. (1) M rather than Eq. (1) of the mean FPI",
     dict(order="mean_of_annual")),
    ("run04_climate_only", "predictors",
     "the 91 climate columns, dropping the 83 soil columns",
     dict(features="climate")),
    ("run05_reduced", "predictors",
     "16 columns: 7 annual climate means and one slice of 9 soil properties",
     dict(features="reduced")),
    ("run06_variance_99", "PCA variance kept",
     "0.99 of the historical variance rather than 0.95",
     dict(variance=0.99)),
    ("run07_cutoff_95", "no-analogue cutoff",
     "the 95th percentile of within-historical NN distance, not the 99th",
     dict(cutoff_pct=95.0)),
    ("run08_k5", "neighbours averaged",
     "the mean of the 5 nearest cells rather than the single nearest",
     dict(k=5)),
    ("run09_noqc", "data quality",
     "the sample without the AGB-versus-basal-area consistency filter",
     dict(reference_table="reference_table_noqc.csv")),
    ("run10_minclass_100", "NVIS fallback threshold",
     "a subgroup needs 100 pool cells before it constrains, not 25",
     dict(min_class_cells=100)),
]


# --------------------------------------------------------------------------- #
# Inputs, loaded once
# --------------------------------------------------------------------------- #

_CACHE = {}


def tables():
    if "tab" not in _CACHE:
        t0 = time.time()
        d = {}
        for name in ["historical_table"] + [
                "future_table_%s_%s" % (a, w) for w in WINDOWS for a in SSPS]:
            z = np.load(SRC_OUT / "tables" / ("%s.npz" % name),
                        allow_pickle=True)
            d[name] = {k: z[k] for k in z.files}
        _CACHE["tab"] = d
        print("loaded %d predictor tables in %.0fs" % (len(d), time.time() - t0))
    return _CACHE["tab"]


def reference(name):
    if name not in _CACHE:
        _CACHE[name] = pd.read_csv(SRC_OUT / name, low_memory=False)
    return _CACHE[name]


def nvis_at(rows, cols):
    if "nvis" not in _CACHE:
        with rasterio.open(NVIS_PATH) as s:
            _CACHE["nvis"] = s.read(1)
    a = _CACHE["nvis"]
    return a[rows, cols]


def mprime_at(order, ssp, win, rows, cols):
    """The M' of the requested averaging order, at the pool cells.

    Read from the raster every time rather than trusting whatever order
    Step_02 happened to store in the npz - that ambiguity was a real bug once.
    """
    d, pat = MPRIME[order]
    path = d / (pat % (ssp, win))
    key = "mp:%s" % path
    if key not in _CACHE:
        with rasterio.open(path) as s:
            a = s.read(1).astype("float64")
            if s.nodata is not None and not np.isnan(s.nodata):
                a = np.where(a == s.nodata, np.nan, a)
        _CACHE[key] = a
    return _CACHE[key][rows, cols].astype("float32")


# --------------------------------------------------------------------------- #
# Matching, with the two parameters Step_03 does not expose
# --------------------------------------------------------------------------- #

def match_k(query, pool_P, k):
    """Nearest-k, returning the neighbour indices and the mean distance.

    k = 1 is the ordinary nearest neighbour. For k > 1 the matched M' becomes
    the mean over the k nearest cells, which trades a little bias for a lot of
    variance: a single cell's M' carries the full noise of one FPI prediction.
    """
    dist, idx = cKDTree(pool_P).query(query, k=k, workers=-1)
    if k == 1:
        return dist, idx[:, None] if idx.ndim == 1 else idx
    return dist.mean(axis=1), idx


def match_k_within_class(query, site_class, pool_P, pool_class, min_cells, k):
    """The same, inside each site's own NVIS subgroup."""
    n = query.shape[0]
    dist = np.full(n, np.nan)
    idx = np.zeros((n, k), dtype=np.int64)
    fallback = np.zeros(n, dtype=bool)
    for cls in np.unique(site_class):
        sel = site_class == cls
        pool_sel = np.flatnonzero(pool_class == cls)
        if pool_sel.size < max(min_cells, k):
            fallback[sel] = True
            continue
        d, j = cKDTree(pool_P[pool_sel]).query(query[sel], k=k, workers=-1)
        if k == 1:
            d, j = d[:, None], j[:, None]
        dist[sel] = d.mean(axis=1)
        idx[sel] = pool_sel[j]
    if fallback.any():
        d, j = cKDTree(pool_P).query(query[fallback], k=k, workers=-1)
        if k == 1:
            d, j = d[:, None], j[:, None]
        dist[fallback] = d.mean(axis=1)
        idx[fallback] = j
    return dist, idx, fallback


def one_run(label, ref, ref_P, tab, pool_P, cutoff, cfg, seed=0,
            random_match=False, site_class=None, pool_class=None,
            mprime_override=None):
    """One matching run: every site against one pool of cells."""
    k = cfg["k"]
    n = ref_P.shape[0]
    n_pool = pool_P.shape[0]
    constrained = site_class is not None and pool_class is not None
    fallback = np.zeros(n, dtype=bool)

    if random_match:
        rng = np.random.default_rng(seed)
        if constrained:
            idx1 = np.zeros(n, dtype=np.int64)
            for cls in np.unique(site_class):
                sel = site_class == cls
                pool_sel = np.flatnonzero(pool_class == cls)
                if pool_sel.size < cfg["min_class_cells"]:
                    idx1[sel] = rng.integers(0, n_pool, int(sel.sum()))
                    fallback[sel] = True
                else:
                    idx1[sel] = rng.choice(pool_sel, int(sel.sum()))
        else:
            idx1 = rng.integers(0, n_pool, n)
        idx = idx1[:, None]
        dist = np.full(n, np.nan)
    elif constrained:
        dist, idx, fallback = match_k_within_class(
            ref_P, site_class, pool_P, pool_class, cfg["min_class_cells"], k)
    else:
        dist, idx = match_k(ref_P, pool_P, k)

    mp = tab["mprime"] if mprime_override is None else mprime_override
    out = ref[["site", "x", "y", "agb", "M_hist", "fpi_hist", "maturity",
               "year", "source"]].copy()
    out["run"] = label
    out["match_x"] = tab["x"][idx].mean(axis=1)
    out["match_y"] = tab["y"][idx].mean(axis=1)
    out["M_matched"] = np.nanmean(np.asarray(mp)[idx], axis=1)
    out["fpi_matched"] = np.nanmean(tab["fpi"][idx], axis=1)
    out["match_distance"] = dist
    out["no_analogue"] = dist > cutoff if np.isfinite(cutoff) else False
    out["class_fallback"] = fallback
    out["displacement_km"] = 111.32 * np.sqrt(
        (out["match_y"] - out["y"]) ** 2
        + ((out["match_x"] - out["x"]) * np.cos(np.deg2rad(out["y"]))) ** 2)
    return out


# --------------------------------------------------------------------------- #
# One configuration, start to finish
# --------------------------------------------------------------------------- #

def execute(run_id, changed, note, override):
    cfg = dict(BASELINE)
    cfg.update(override)
    t0 = time.time()
    print("\n=== %s - changed: %s ===" % (run_id, changed))
    print("    %s" % note)

    tab = tables()
    hist = tab["historical_table"]
    names = np.array([str(x) for x in hist["feature_names"]])

    ref_all = reference(cfg["reference_table"])
    ref = ref_all[ref_all["maturity"].isin(cfg["maturity"])].reset_index(
        drop=True)
    print("    %d reference sites" % len(ref))

    hist_X, _ = S3.feature_block(hist["X"], names, cfg["features"])
    ref_X, _ = S3.feature_block(ref[list(names)].to_numpy("float32"), names,
                                cfg["features"])
    mu, sd, pca = S3.build_space(hist_X, cfg["variance"])
    hist_P = S3.project(hist_X, mu, sd, pca)
    ref_P = S3.project(ref_X, mu, sd, pca)
    print("    space: %d features -> %d components"
          % (hist_X.shape[1], pca.n_components_))

    d_self, _ = cKDTree(hist_P).query(hist_P, k=2, workers=-1)
    cutoff = float(np.percentile(d_self[:, 1], cfg["cutoff_pct"]))

    # NVIS classes. Always computed, because the unconstrained null still has
    # to be reported when the run itself is unconstrained.
    site_cls = nvis_at(ref["row"].to_numpy(), ref["col"].to_numpy())
    pool_cls = nvis_at(hist["rows"], hist["cols"])
    use_cls = (site_cls, pool_cls) if cfg["constrain"] == "nvis" else (None, None)

    frames = []

    # control 1 - the site's own cell today
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

    # control 2 - a present-day analogue, the matching method's own error
    frames.append(one_run("historical_analogue", ref, ref_P, hist, hist_P,
                          cutoff, cfg, site_class=use_cls[0],
                          pool_class=use_cls[1]))

    # controls 3 and 4 - BOTH nulls, every run, whatever the run's own setting
    frames.append(one_run("random_cells_nvis", ref, ref_P, hist, hist_P,
                          cutoff, cfg, random_match=True,
                          site_class=site_cls, pool_class=pool_cls))
    frames.append(one_run("random_cells_unconstrained", ref, ref_P, hist,
                          hist_P, cutoff, cfg, random_match=True))

    # the eight scenario-windows
    for win in WINDOWS:
        for ssp in SSPS:
            t = tab["future_table_%s_%s" % (ssp, win)]
            fut_X, _ = S3.feature_block(t["X"], names, cfg["features"])
            fut_P = S3.project(fut_X, mu, sd, pca)
            mp = mprime_at(cfg["order"], ssp, win, t["rows"], t["cols"])
            frames.append(one_run("%s_%s" % (ssp, win), ref, ref_P, t, fut_P,
                                  cutoff, cfg, site_class=use_cls[0],
                                  pool_class=use_cls[1], mprime_override=mp))

    matches = pd.concat(frames, ignore_index=True)
    dst = OUT_DIR / run_id
    dst.mkdir(parents=True, exist_ok=True)
    matches.to_csv(dst / "matches.csv", index=False)

    # --- metrics, on the analogue-found stratum ------------------------- #
    rows = []
    for label, grp in matches.groupby("run", sort=False):
        found = grp[~grp["no_analogue"]]
        m = S3.metrics(found["agb"].to_numpy(), found["M_matched"].to_numpy(),
                       found["match_distance"].to_numpy())
        rows.append(dict(
            run_id=run_id, changed=changed, note=note, run=label,
            n_sites=len(grp), n_analogue_found=len(found),
            pct_no_analogue=100 * float(grp["no_analogue"].mean()),
            median_displacement_km=float(
                np.nanmedian(found["displacement_km"])), **m))
    met = pd.DataFrame(rows)
    met.to_csv(dst / "metrics.csv", index=False)

    fut = met[~met["run"].isin(CONTROLS)]
    print("    %-26s ratio %.3f  rho %.3f" % ("future runs (median)",
                                              fut["median_ratio"].median(),
                                              fut["spearman_rho"].median()))
    for c in ("historical_analogue", "random_cells_nvis",
              "random_cells_unconstrained"):
        r = met[met["run"] == c]
        if len(r):
            print("    %-26s ratio %.3f  rho %.3f"
                  % (c, r["median_ratio"].iloc[0], r["spearman_rho"].iloc[0]))
    print("    %.0fs" % (time.time() - t0))
    return met


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None,
                    help="run only these ids, e.g. run00 run02")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = RUNS
    if args.only:
        todo = [r for r in RUNS if any(r[0].startswith(p) for p in args.only)]
        if not todo:
            raise SystemExit("no run matched %s" % args.only)

    pd.DataFrame([{"run_id": a, "changed": b, "what": c,
                   "override": "; ".join("%s=%s" % kv for kv in d.items())
                               or "(baseline)"}
                  for a, b, c, d in RUNS]).to_csv(
        OUT_DIR / "run_matrix.csv", index=False)

    out = [execute(*r) for r in todo]
    summary = pd.concat(out, ignore_index=True)
    dst = OUT_DIR / "ofat_summary.csv"
    if dst.exists() and args.only:
        old = pd.read_csv(dst)
        old = old[~old["run_id"].isin(summary["run_id"].unique())]
        summary = pd.concat([old, summary], ignore_index=True)
    summary.to_csv(dst, index=False)

    # --- every run against Run 0 ---------------------------------------- #
    base = summary[summary["run_id"] == "run00_baseline"]
    if len(base):
        b = base.set_index("run")
        rows = []
        for rid, g in summary.groupby("run_id"):
            if rid == "run00_baseline":
                continue
            g = g.set_index("run")
            common = [r for r in g.index if r in b.index]
            rows.append(dict(
                run_id=rid, changed=g["changed"].iloc[0],
                d_ratio_future=float(
                    (g.loc[common, "median_ratio"]
                     - b.loc[common, "median_ratio"])[
                        [c for c in common if c not in CONTROLS]].median()),
                d_rho_future=float(
                    (g.loc[common, "spearman_rho"]
                     - b.loc[common, "spearman_rho"])[
                        [c for c in common if c not in CONTROLS]].median()),
                d_pct_no_analogue=float(
                    (g.loc[common, "pct_no_analogue"]
                     - b.loc[common, "pct_no_analogue"])[
                        [c for c in common if c not in CONTROLS]].median()),
                n_sites=int(g["n_sites"].iloc[0])))
        deltas = pd.DataFrame(rows)
        # A change that also moves the no-analogue share is no longer a
        # like-for-like comparison: the metric is then computed on a different,
        # self-selected subset of sites, and a gain can be pure survivorship.
        # Ten points is the threshold; beyond it the delta is not attributable
        # to the change alone and the run is flagged rather than dropped.
        deltas["sample_comparable"] = deltas["d_pct_no_analogue"].abs() < 10
        deltas["interpretation"] = np.where(
            deltas["sample_comparable"], "delta attributable to the change",
            "sample also changed - delta confounded by which sites survive")
        deltas.to_csv(OUT_DIR / "ofat_deltas.csv", index=False)

    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
