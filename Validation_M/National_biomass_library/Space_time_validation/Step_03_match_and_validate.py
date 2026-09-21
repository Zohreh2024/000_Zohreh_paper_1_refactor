"""
Step 03 - the match, and the statistics that come out of it.

For each NBL site, find the future grid cell whose FPI predictors are closest to
that site's historical predictors, then compare the biomass the site actually
carries against the M' projected for that cell. If the chain climate -> FPI ->
Eq. (1) -> lambda is transporting a climate signal correctly, the two should
agree; if the chain merely interpolates inside the range it was fitted on, they
will not.

The space the match happens in
------------------------------
All 174 predictors, standardised by the HISTORICAL land-cell mean and standard
deviation so that the reference and the future live in one comparable space, then
projected onto the principal components of that same historical sample (default:
enough components for 95% of its variance). PCA is not cosmetic here. The raw
predictors are strongly collinear - twelve monthly temperatures move together -
so plain Euclidean distance counts one physical signal a dozen times and the 83
soil columns outvote the climate. Whitened components give each independent
direction of variation one vote, which is what "closest" ought to mean.

`--features climate` repeats everything on the 91 climate columns alone. That is
the stricter reading of the test: soil does not change between now and 2100, so
including it mostly constrains the analogue to sit on similar soil, which is
desirable but is not what is being validated. Both are reported.

No-analogue cells are not silently matched
------------------------------------------
Some historical climates have no future counterpart, and forcing a match onto
them manufactures agreement or disagreement out of nothing. The distance to the
nearest neighbour is kept for every site, and a site is flagged `no_analogue`
when that distance exceeds the 99th percentile of the within-historical nearest
neighbour distances - i.e. further than historical cells typically are from each
other. Metrics are reported with and without those sites.

Three controls, because a number without one means little
---------------------------------------------------------
  same_cell     M' at the site's OWN cell today, against observed AGB. This is
                the present-day gate: if this fails, nothing downstream can be
                trusted, and the failure is not about climate change at all.
  historical    the analogue search run against the HISTORICAL table instead of
                a future one. The matched cell is a present-day cell with a
                present-day M'. Any disagreement here is the matching method's
                own error, and the future numbers should be read against it,
                not against zero.
  random        cells drawn at random. The floor: whatever skill the method has
                must beat this.

Statistics, and why each is here
--------------------------------
M is a maximum and an observed AGB is one stand at one moment, so the error
distribution is asymmetric by construction and no single statistic is adequate.
Reported per run: n, median observed, median predicted, median ratio and its
bootstrap interval, mean and median bias, RMSE, MAE, MdAPE, Pearson r, Spearman
rho, R^2, R^2 in logs, Lin's concordance, Nash-Sutcliffe, the Theil-Sen slope of
predicted on observed, % of sites over-predicted, % within a factor of two, and
the mean matching distance. Ratios and logs carry the weight, because biomass
spans three orders of magnitude and a plain RMSE is then a statement about the
largest sites only.

Reads   outputs/reference_table.csv, outputs/tables/*.npz
Writes  outputs/matches_<run>.csv            one row per site, per run
        outputs/metrics_by_run.csv           every run, every stratum
        outputs/metrics_by_maturity.csv
        outputs/no_analogue_summary.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_match_and_validate.py --features all
    ... --features climate
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy import stats
from scipy.spatial import cKDTree
from sklearn.decomposition import PCA

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
TAB_DIR = OUT_DIR / "tables"
ROOT = HERE.parents[2]
NVIS_PATH = (ROOT / "Data" / "Processed" / "NVIS"
             / "nvis_mvs_pre1750_mode_NLUM.tif")
UNCLASSIFIED = (0, 99, 255)
# The other averaging order of the same fully-modelled M'. Only the M' layer
# differs between the two - the 174 predictors are identical - so the variant is
# run by swapping the M' read at the pooled cells, not by rebuilding the tables.
EQ1_OF_MEAN_DIR = (ROOT / "FPI_Accuracy_check" / "output_Mprime_rf"
                   / "eq1_of_mean")
MEAN_OF_ANNUAL_DIR = (ROOT / "FPI_Accuracy_check" / "output_Mprime_rf"
                      / "mean_of_annual")

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
N_SOIL = 83
MATURE = ["verified mature", "likely mature"]
BOOT = 2000
SPACE_INFO = {}


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

def theil_sen(x, y):
    try:
        return float(stats.theilslopes(y, x)[0])
    except Exception:                                      # noqa: BLE001
        return np.nan


def ccc(obs, pred):
    """Lin's concordance: correlation AND agreement with the 1:1 line."""
    vo, vp = obs.var(), pred.var()
    cov = np.mean((obs - obs.mean()) * (pred - pred.mean()))
    denom = vo + vp + (obs.mean() - pred.mean()) ** 2
    return float(2 * cov / denom) if denom else np.nan


def boot_median_ratio(ratio, n_boot=BOOT, seed=0):
    rng = np.random.default_rng(seed)
    if ratio.size < 5:
        return np.nan, np.nan
    idx = rng.integers(0, ratio.size, (n_boot, ratio.size))
    meds = np.median(ratio[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def metrics(obs, pred, dist=None):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    ok = np.isfinite(obs) & np.isfinite(pred) & (obs > 0) & (pred > 0)
    obs, pred = obs[ok], pred[ok]
    if obs.size < 3:
        return {"n": int(obs.size)}

    err = pred - obs
    ratio = pred / obs
    lo, hi = boot_median_ratio(ratio)
    sse = float(np.sum(err ** 2))
    sst = float(np.sum((obs - obs.mean()) ** 2))
    lo_o, lo_p = np.log(obs), np.log(pred)

    out = {
        "n": int(obs.size),
        "obs_median": float(np.median(obs)),
        "pred_median": float(np.median(pred)),
        "median_ratio": float(np.median(ratio)),
        "median_ratio_lo": lo, "median_ratio_hi": hi,
        "median_bias": float(np.median(err)),
        "mean_bias": float(err.mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "mae": float(np.abs(err).mean()),
        "mdape_pct": float(np.median(np.abs(ratio - 1)) * 100),
        "pearson_r": float(np.corrcoef(obs, pred)[0, 1]),
        "spearman_rho": float(stats.spearmanr(obs, pred).correlation),
        "r2": 1 - sse / sst if sst else np.nan,
        "r2_log": float(1 - np.sum((lo_p - lo_o) ** 2)
                        / np.sum((lo_o - lo_o.mean()) ** 2)),
        "ccc": ccc(obs, pred),
        "nse": 1 - sse / sst if sst else np.nan,
        "theil_sen_slope": theil_sen(obs, pred),
        "pct_over": float(100 * np.mean(pred > obs)),
        "pct_within_2x": float(100 * np.mean((ratio > 0.5) & (ratio < 2))),
        "pct_within_5x": float(100 * np.mean((ratio > 0.2) & (ratio < 5))),
    }
    if dist is not None and np.isfinite(dist[ok]).any():
        out["mean_match_distance"] = float(np.nanmean(dist[ok]))
    return out


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #

# The reduced matching set: the seven annual climate means, and one slice -
# the shallowest - of each soil property that matters to growth. Sixteen
# columns instead of 174. It exists because a nearest neighbour found in a very
# high-dimensional space is only nominally the nearest: as dimension grows the
# spread of pairwise distances shrinks relative to their mean, so every
# candidate sits at roughly the same distance and the winner is decided by
# noise. `relative_contrast()` measures that directly, and both sets are
# reported so the effect can be seen rather than argued about.
REDUCED_SOIL = ["AWC", "BDW", "CLY", "SND", "SOC", "NTO", "Phos", "pHc", "DES"]


def feature_block(X, names, which):
    if which == "climate":
        return X[:, N_SOIL:], list(names[N_SOIL:])
    if which == "reduced":
        keep = []
        for pre in REDUCED_SOIL:
            hit = [i for i, n in enumerate(names[:N_SOIL]) if str(n).startswith(pre)]
            if hit:
                keep.append(hit[0])
        keep += [i for i, n in enumerate(names) if str(n).endswith("_ann")]
        keep = sorted(set(keep))
        return X[:, keep], [str(names[i]) for i in keep]
    return X, list(names)


def relative_contrast(P, pool, seed=0):
    """(mean distance - nearest distance) / nearest distance, in this space.

    The standard measure of distance concentration. A large value means the
    nearest neighbour really is nearer than a typical cell; as it approaches
    zero, `nearest` stops meaning anything.
    """
    rng = np.random.default_rng(seed)
    q = P[rng.choice(len(P), size=min(500, len(P)), replace=False)]
    sub = pool[rng.choice(len(pool), size=min(20000, len(pool)), replace=False)]
    d = np.sqrt(((q[:, None, :] - sub[None, :, :]) ** 2).sum(-1))
    dmin = d.min(axis=1)
    return float(np.median((d.mean(axis=1) - dmin) / np.maximum(dmin, 1e-9)))


def build_space(hist_X, n_components, seed=0):
    """Standardise on the historical sample, then whiten onto its PCs."""
    mu = hist_X.mean(axis=0)
    sd = hist_X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = (hist_X - mu) / sd
    pca = PCA(n_components=n_components, svd_solver="full", random_state=seed)
    pca.fit(Z)
    return mu, sd, pca


def project(X, mu, sd, pca):
    return pca.transform((X - mu) / sd).astype("float32")


def nn_match(query, pool, k=1):
    tree = cKDTree(pool)
    dist, idx = tree.query(query, k=k, workers=-1)
    return dist, idx


def nn_match_within_class(query, site_class, pool, pool_class, min_cells):
    """Nearest neighbour restricted to the site's own NVIS class.

    Climate and soil can be matched exactly and still pair a rainforest site
    with a cell that carries mallee: the two are different vegetation and carry
    different biomass for reasons this chain does not model. Constraining the
    search to the site's own pre-1750 Major Vegetation Subgroup removes that
    confound, at the cost of a smaller candidate pool.

    A class with fewer than `min_cells` cells in the pool cannot support a
    search, so those sites fall back to an unconstrained match and are flagged.
    A fallback is not a failure to report quietly - it means the future domain
    holds almost none of that vegetation type's climate, which is itself a
    result.
    """
    n = query.shape[0]
    dist = np.full(n, np.inf)
    idx = np.zeros(n, dtype=np.int64)
    fallback = np.zeros(n, dtype=bool)

    for cls in np.unique(site_class):
        sel = site_class == cls
        pool_sel = np.flatnonzero(pool_class == cls)
        if pool_sel.size < min_cells:
            fallback[sel] = True
            continue
        d, j = cKDTree(pool[pool_sel]).query(query[sel], k=1, workers=-1)
        dist[sel] = d
        idx[sel] = pool_sel[j]

    if fallback.any():
        d, j = cKDTree(pool).query(query[fallback], k=1, workers=-1)
        dist[fallback] = d
        idx[fallback] = j
    return dist, idx, fallback


def run_one(label, ref, ref_P, tab, pool_P, cutoff, seed=0, random_match=False,
            site_class=None, pool_class=None, min_cells=25):
    """One matching run: every site against one pool of cells."""
    n_pool = pool_P.shape[0]
    constrained = site_class is not None and pool_class is not None
    fallback = np.zeros(ref_P.shape[0], dtype=bool)

    if random_match:
        rng = np.random.default_rng(seed)
        if constrained:
            # The null has to be drawn under the same constraint, or it would
            # be testing the constraint rather than the matching.
            idx = np.zeros(ref_P.shape[0], dtype=np.int64)
            for cls in np.unique(site_class):
                sel = site_class == cls
                pool_sel = np.flatnonzero(pool_class == cls)
                if pool_sel.size < min_cells:
                    idx[sel] = rng.integers(0, n_pool, int(sel.sum()))
                    fallback[sel] = True
                else:
                    idx[sel] = rng.choice(pool_sel, int(sel.sum()))
        else:
            idx = rng.integers(0, n_pool, ref_P.shape[0])
        dist = np.full(ref_P.shape[0], np.nan)
    elif constrained:
        dist, idx, fallback = nn_match_within_class(
            ref_P, site_class, pool_P, pool_class, min_cells)
    else:
        dist, idx = nn_match(ref_P, pool_P, k=1)

    out = ref[["site", "x", "y", "agb", "M_hist", "fpi_hist", "maturity",
               "max_dbh", "year", "source"]].copy()
    out["run"] = label
    out["match_x"] = tab["x"][idx]
    out["match_y"] = tab["y"][idx]
    out["M_matched"] = tab["mprime"][idx]
    out["fpi_matched"] = tab["fpi"][idx]
    out["match_distance"] = dist
    out["no_analogue"] = dist > cutoff if np.isfinite(cutoff) else False
    out["class_fallback"] = fallback
    if site_class is not None:
        out["mvs_site"] = site_class
        out["mvs_match"] = pool_class[idx] if pool_class is not None else np.nan
    # How far the analogue sits from the site, in kilometres - a diagnostic, not
    # a criterion: a good climate analogue may legitimately be far away.
    out["displacement_km"] = 111.32 * np.sqrt(
        (out["match_y"] - out["y"]) ** 2
        + ((out["match_x"] - out["x"]) * np.cos(np.deg2rad(out["y"]))) ** 2)
    return out



def paired_log_ratio(matches, out_path):
    """Each site against ITSELF, so the vegetation type cancels.

    A site's agreement is e = log10(M'_matched / AGB_observed). Comparing two
    runs at the same site,

        delta = e_future - e_baseline = log10(M'_future / M'_baseline)

    and the observed AGB cancels exactly. That matters because the unpaired
    ratios in `metrics_by_run` mix two things: how well M' tracks biomass at a
    site, and which vegetation types happen to sit in the sample. The paired
    difference removes both - every site is its own control - and leaves only
    what the matching changed.

    Two baselines are reported, and they answer different questions:

      vs same_cell_present_day    everything the analogue changed: the search
                                  procedure AND the projected climate
      vs historical_analogue      the search procedure is held fixed and only
                                  the climate moves, so this isolates the
                                  projected change

    The sign convention is the future minus the baseline, so a negative median
    means the analogue carries less M' than the site's own present-day value.
    A Wilcoxon signed-rank test on the paired differences gives the p-value;
    with n in the hundreds it detects differences far smaller than matter, so
    read the median and its interval first and the p-value last.
    """
    wide = matches.pivot_table(index="site", columns="run", values="M_matched",
                               aggfunc="first")
    agb = matches.groupby("site")["agb"].first()
    ok_runs = [c for c in wide.columns if c.startswith("ssp")]
    rows = []
    for base in ("same_cell_present_day", "historical_analogue"):
        if base not in wide.columns:
            continue
        for run in ok_runs:
            a, b = wide[run], wide[base]
            g = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
            d = np.log10(a[g] / b[g]).to_numpy()
            if len(d) < 10:
                continue
            rng = np.random.default_rng(0)
            boot = np.median(rng.choice(d, (BOOT, len(d)), replace=True), axis=1)
            try:
                pval = float(stats.wilcoxon(d).pvalue)
            except ValueError:
                pval = np.nan
            rows.append(dict(
                baseline=base, run=run, n=int(len(d)),
                median_log10_ratio=float(np.median(d)),
                lo=float(np.percentile(boot, 2.5)),
                hi=float(np.percentile(boot, 97.5)),
                median_ratio=float(10 ** np.median(d)),
                pct_sites_lower=float(100 * np.mean(d < 0)),
                wilcoxon_p=pval,
                median_agb=float(agb.reindex(wide.index[g]).median())))
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    return df


def load_table(path):
    z = np.load(path, allow_pickle=True)
    return {k: z[k] for k in z.files}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", choices=["all", "climate", "reduced"],
                    default="all",
                    help="which predictors define the matching space; "
                         "`all` is the 174 the random forest uses, "
                         "`reduced` the 16-column set of annual climate "
                         "means plus one slice of each key soil property, "
                         "the sensitivity for distance concentration")
    ap.add_argument("--variance", type=float, default=0.95,
                    help="PCA variance kept (default 0.95)")
    ap.add_argument("--maturity", nargs="*", default=MATURE,
                    help="maturity classes in the headline sample")
    ap.add_argument("--constrain", choices=["none", "nvis"], default="nvis",
                    help="restrict each site's candidates to its own pre-1750 "
                         "NVIS Major Vegetation Subgroup (default)")
    ap.add_argument("--mprime-order", choices=["eq1_of_mean", "mean_of_annual"],
                    default="eq1_of_mean",
                    help="which averaging order of M' to validate. Both have a "
                         "random-forest historical denominator; they differ in "
                         "whether Eq. (1) is applied per year and then averaged, "
                         "or to the averaged FPI")
    ap.add_argument("--reference-table", default="reference_table.csv",
                    help="which reference table to validate. The default has "
                         "passed the AGB-vs-basal-area consistency filter; "
                         "`reference_table_noqc.csv` is the pre-September-2026 "
                         "sample that still carries the corrupt TERN and CSIRO "
                         "biomass records, and its outputs take a _noqc suffix")
    ap.add_argument("--min-class-cells", type=int, default=25,
                    help="a class with fewer pool cells than this falls back to "
                         "an unconstrained match, flagged in the output")
    args = ap.parse_args()

    ref_all = pd.read_csv(OUT_DIR / args.reference_table, low_memory=False)
    hist = load_table(TAB_DIR / "historical_table.npz")
    names = np.array([str(n) for n in hist["feature_names"]])

    ref = ref_all[ref_all["maturity"].isin(args.maturity)].reset_index(drop=True)
    print("reference sites: %d of %d (%s)"
          % (len(ref), len(ref_all), ", ".join(args.maturity)))

    # --- NVIS, the vegetation constraint ---------------------------------- #
    site_cls = pool_cls = None
    if args.constrain == "nvis":
        if not NVIS_PATH.exists():
            sys.exit("%s not found - run Step_00_prepare_nvis.py first" % NVIS_PATH)
        with rasterio.open(NVIS_PATH) as s:
            nvis = s.read(1)
        site_cls = nvis[ref["row"].to_numpy(), ref["col"].to_numpy()].astype("int16")
        pool_cls = nvis[hist["rows"], hist["cols"]].astype("int16")
        n_unclassified = int(np.isin(site_cls, list(UNCLASSIFIED)).sum())
        print("NVIS constraint: %d MVS classes among the sites, %d classes in "
              "the pool, %d site(s) unclassified"
              % (len(np.unique(site_cls)), len(np.unique(pool_cls)),
                 n_unclassified))
        ref = ref.assign(mvs=site_cls)

    ref_X = ref[list(names)].to_numpy("float32")
    hist_X, _ = feature_block(hist["X"], names, args.features)
    ref_X, _ = feature_block(ref_X, names, args.features)

    mu, sd, pca = build_space(hist_X, args.variance)
    print("space: %s features -> %d components (%.1f%% of historical variance)"
          % (hist_X.shape[1], pca.n_components_,
             100 * pca.explained_variance_ratio_.sum()))

    hist_P = project(hist_X, mu, sd, pca)
    ref_P = project(ref_X, mu, sd, pca)
    rc = relative_contrast(ref_P, hist_P)
    SPACE_INFO.update(n_features=int(hist_X.shape[1]),
                      n_components=int(pca.n_components_),
                      variance_pct=float(
                          100 * pca.explained_variance_ratio_.sum()),
                      relative_contrast=float(rc))
    print("       relative contrast %.2f - the median site's nearest cell is "
          "%.0f%% nearer than a typical one" % (rc, 100 * rc / (1 + rc)))

    # How far apart are historical cells from each other? That sets the scale on
    # which a future distance counts as "no analogue".
    d_self, _ = cKDTree(hist_P).query(hist_P, k=2, workers=-1)
    cutoff = float(np.percentile(d_self[:, 1], 99))
    print("no-analogue cutoff: %.3f (99th percentile of within-historical NN "
          "distance)" % cutoff)

    runs, frames = [], []

    # --- control 1: the site's own cell, today ---------------------------- #
    same = ref[["site", "x", "y", "agb", "M_hist", "fpi_hist", "maturity",
                "max_dbh", "year", "source"]].copy()
    same["run"] = "same_cell_present_day"
    same["match_x"], same["match_y"] = same["x"], same["y"]
    same["M_matched"] = same["M_hist"]
    same["fpi_matched"] = same["fpi_hist"]
    same["match_distance"] = 0.0
    same["no_analogue"] = False
    same["displacement_km"] = 0.0
    same["class_fallback"] = False
    if site_cls is not None:
        same["mvs_site"] = site_cls
        same["mvs_match"] = site_cls
    frames.append(same)

    # --- control 2: present-day analogue ---------------------------------- #
    frames.append(run_one("historical_analogue", ref, ref_P, hist, hist_P, cutoff,
                          site_class=site_cls, pool_class=pool_cls,
                          min_cells=args.min_class_cells))

    # --- control 3: random ----------------------------------------------- #
    frames.append(run_one("random_cells", ref, ref_P, hist, hist_P, cutoff,
                          random_match=True, site_class=site_cls,
                          pool_class=pool_cls, min_cells=args.min_class_cells))

    # --- the eight scenario-windows --------------------------------------- #
    for win in WINDOWS:
        for ssp in SSPS:
            p = TAB_DIR / ("future_table_%s_%s.npz" % (ssp, win))
            if not p.exists():
                print("  missing %s - run Step_02" % p.name)
                continue
            tab = load_table(p)
            # The M' is always re-read from the raster for the order asked
            # for, whichever order Step_02 happened to store. An earlier version
            # only overrode for eq1_of_mean, so once that became Step_02's
            # default the mean_of_annual run silently duplicated it.
            alt = (EQ1_OF_MEAN_DIR / ("maxAbgMF_from_mean_fpi_%s_%s.tif"
                                      % (ssp, win))
                   if args.mprime_order == "eq1_of_mean"
                   else MEAN_OF_ANNUAL_DIR / ("maxAbgMF_%s_%s_mean.tif"
                                              % (ssp, win)))
            if not alt.exists():
                sys.exit("missing %s" % alt)
            with rasterio.open(alt) as s_alt:
                a = s_alt.read(1).astype("float64")
                if s_alt.nodata is not None and not np.isnan(s_alt.nodata):
                    a = np.where(a == s_alt.nodata, np.nan, a)
            tab["mprime"] = a[tab["rows"], tab["cols"]].astype("float32")
            fut_X, _ = feature_block(tab["X"], names, args.features)
            fut_P = project(fut_X, mu, sd, pca)
            frames.append(run_one("%s_%s" % (ssp, win), ref, ref_P, tab,
                                  fut_P, cutoff, site_class=site_cls,
                                  pool_class=pool_cls,
                                  min_cells=args.min_class_cells))
            print("  matched %s %s" % (ssp, win), flush=True)

    matches = pd.concat(frames, ignore_index=True)
    suffix = {"all": "", "climate": "_climate_only",
              "reduced": "_reduced"}[args.features]
    if args.constrain == "nvis":
        suffix += "_nvis"
    if args.mprime_order == "mean_of_annual":
        suffix += "_mean_of_annual"
    if "noqc" in args.reference_table:
        suffix += "_noqc"
    matches.to_csv(OUT_DIR / ("matches%s.csv" % suffix), index=False)
    pd.DataFrame([SPACE_INFO]).to_csv(
        OUT_DIR / ("matching_space%s.csv" % suffix), index=False)

    # --- metrics ---------------------------------------------------------- #
    for label, grp in matches.groupby("run", sort=False):
        for stratum, sub in [("all matched", grp),
                             ("analogue found", grp[~grp["no_analogue"]])]:
            m = metrics(sub["agb"].to_numpy(), sub["M_matched"].to_numpy(),
                        sub["match_distance"].to_numpy())
            runs.append(dict(run=label, stratum=stratum, features=args.features,
                             constraint=args.constrain,
                             n_no_analogue=int(grp["no_analogue"].sum()),
                             n_class_fallback=int(grp["class_fallback"].sum()),
                             median_displacement_km=float(
                                 np.nanmedian(sub["displacement_km"])), **m))
    runs_df = pd.DataFrame(runs)
    runs_df.to_csv(OUT_DIR / ("metrics_by_run%s.csv" % suffix), index=False)

    paired = paired_log_ratio(
        matches, OUT_DIR / ("paired_log_ratio%s.csv" % suffix))
    print("\npaired per-site comparison (log10 M'_run / M'_baseline, AGB cancels)")
    print(paired.to_string(index=False, float_format=lambda v: "%.3f" % v))

    by_mat = []
    for (label, mat), sub in matches.groupby(["run", "maturity"], sort=False):
        m = metrics(sub["agb"].to_numpy(), sub["M_matched"].to_numpy())
        by_mat.append(dict(run=label, maturity=mat, features=args.features, **m))
    pd.DataFrame(by_mat).to_csv(
        OUT_DIR / ("metrics_by_maturity%s.csv" % suffix), index=False)

    na = matches.groupby("run")["no_analogue"].agg(["sum", "size"]).reset_index()
    na["pct"] = 100 * na["sum"] / na["size"]
    na.to_csv(OUT_DIR / ("no_analogue_summary%s.csv" % suffix), index=False)

    show = ["run", "stratum", "n", "obs_median", "pred_median", "median_ratio",
            "spearman_rho", "r2_log", "pct_within_2x", "median_displacement_km"]
    print("\n" + runs_df[show].to_string(
        index=False, float_format=lambda v: "%.3f" % v))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
