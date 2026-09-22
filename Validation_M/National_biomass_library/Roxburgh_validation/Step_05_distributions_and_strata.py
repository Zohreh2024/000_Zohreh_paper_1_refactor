"""
Step 05 - the three comparisons Roxburgh makes that are not fit statistics.

1. FREQUENCY DISTRIBUTIONS, with Kolmogorov-Smirnov tests (his Fig. 6b and
   Section 3.3). He compares the distribution of observed biomass with the
   distributions of M and M' and tests whether they could have come from the
   same distribution, reporting P = 0.061 for M' against the observations and
   P < 0.001 for M. The point is not the p-value - with thousands of records
   almost anything is significant - but the SHAPE: his original M could never
   exceed 500 t DM/ha while the observations reached 1500, and the revised
   layer moved the whole distribution into overlap. The same test applied to
   the eight future layers asks whether the projection keeps that overlap.

2. MEANS BY STATE AND VEGETATION CLASS (his Fig. 8). Observed against each
   layer, Forest and Woodland separately, state by state. This is where a
   layer that is right on average but wrong everywhere in particular shows
   itself.

3. SPATIAL AUTOCORRELATION (his Section 2.4). He found correlations below 0.2
   beyond about 10 km and balanced the sample by up-sampling at a 10 x 10 km
   scale before fitting. The same correlogram is computed here on the residual
   O - M, because it decides how much of any agreement is independent evidence:
   if neighbouring plots are strongly correlated then a 70/30 random split
   leaks between calibration and validation, and the validation statistics are
   optimistic. That matters directly for reading Roxburgh's own Table 4.

Reads   outputs/records.csv
Writes  outputs/ks_tests.csv
        outputs/means_by_state_class.csv
        outputs/spatial_autocorrelation.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_05_distributions_and_strata.py
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"

EARTH_R_KM = 6371.0
DIST_BINS_KM = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 3000]
MAX_PAIRS = 4_000_000          # a random subsample beyond this many pairs


def layer_names(d):
    return [c for c in d.columns
            if c.startswith("M_") and not c.startswith("lambda_")]


def ks_table(d):
    obs = d["agb"].to_numpy(float)
    obs = obs[np.isfinite(obs)]
    rows = []
    for c in layer_names(d):
        v = d[c].to_numpy(float)
        v = v[np.isfinite(v)]
        if len(v) < 10:
            continue
        ks = sps.ks_2samp(obs, v)
        rows.append(dict(
            layer=c, n_obs=len(obs), n_layer=len(v),
            obs_median=float(np.median(obs)), layer_median=float(np.median(v)),
            obs_p95=float(np.percentile(obs, 95)),
            layer_p95=float(np.percentile(v, 95)),
            obs_max=float(obs.max()), layer_max=float(v.max()),
            ks_statistic=float(ks.statistic), ks_p=float(ks.pvalue),
            pct_layer_over_obs_p95=float(
                100 * np.mean(v > np.percentile(obs, 95)))))
    return pd.DataFrame(rows)


def means_by_stratum(d):
    rows = []
    layers = layer_names(d)
    for (st, cls), s in d.groupby(["state", "veg_class"]):
        if cls == "Excluded":
            continue
        r = dict(state=st, veg_class=cls, n=len(s),
                 observed=float(s["agb"].mean()))
        for c in layers:
            r[c] = float(s[c].mean())
        rows.append(r)
    for cls, s in d.groupby("veg_class"):
        if cls == "Excluded":
            continue
        r = dict(state="ALL", veg_class=cls, n=len(s),
                 observed=float(s["agb"].mean()))
        for c in layers:
            r[c] = float(s[c].mean())
        rows.append(r)
    return pd.DataFrame(rows)


def correlogram(d, layer, seed=0):
    """Correlation of the residual O - M against separation distance.

    Great-circle distance on all pairs, or a random subsample of them when the
    sample is large enough that the full pair list would not fit. Within each
    distance bin the correlation is Moran-like: the mean product of the two
    standardised residuals, which is what Roxburgh's Supplementary Fig. A
    reports.
    """
    res = (d["agb"] - d[layer]).to_numpy(float)
    lat = np.radians(d["latitude"].to_numpy(float))
    lon = np.radians(d["longitude"].to_numpy(float))
    g = np.isfinite(res) & np.isfinite(lat) & np.isfinite(lon)
    res, lat, lon = res[g], lat[g], lon[g]
    z = (res - res.mean()) / res.std()

    n = len(z)
    rng = np.random.default_rng(seed)
    n_pairs = n * (n - 1) // 2
    if n_pairs > MAX_PAIRS:
        i = rng.integers(0, n, MAX_PAIRS)
        j = rng.integers(0, n, MAX_PAIRS)
        ok = i != j
        i, j = i[ok], j[ok]
    else:
        i, j = np.triu_indices(n, 1)

    dlat = lat[j] - lat[i]
    dlon = lon[j] - lon[i]
    a = (np.sin(dlat / 2) ** 2
         + np.cos(lat[i]) * np.cos(lat[j]) * np.sin(dlon / 2) ** 2)
    dist = 2 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    prod = z[i] * z[j]

    rows = []
    edges = DIST_BINS_KM
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (dist >= lo) & (dist < hi)
        if sel.sum() < 30:
            continue
        rows.append(dict(layer=layer, lo_km=lo, hi_km=hi, pairs=int(sel.sum()),
                         correlation=float(prod[sel].mean())))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default="records.csv")
    ap.add_argument("--layer", default="M_revised_Roxburgh",
                    help="which layer's residual the correlogram uses")
    args = ap.parse_args()

    d = pd.read_csv(OUT_DIR / args.records, low_memory=False)
    suf = args.records[len("records"):-len(".csv")]
    print("%s records" % format(len(d), ","))

    ks = ks_table(d)
    ks.to_csv(OUT_DIR / ("ks_tests%s.csv" % suf), index=False)
    print("\n--- 1. distributions against the observations "
          "(Kolmogorov-Smirnov) ---")
    print("Roxburgh: M' against observations P = 0.061, original M P < 0.001\n")
    print(ks[["layer", "obs_median", "layer_median", "obs_p95", "layer_p95",
              "layer_max", "ks_statistic", "ks_p"]]
          .to_string(index=False, float_format=lambda v: "%.3g" % v))

    ms = means_by_stratum(d)
    ms.to_csv(OUT_DIR / ("means_by_state_class%s.csv" % suf), index=False)
    print("\n--- 2. means by state and vegetation class ---")
    cols = ["state", "veg_class", "n", "observed", "M_original_2004",
            "M_revised_Roxburgh", "M_future_ssp585_2070-2099"]
    print(ms[[c for c in cols if c in ms.columns]]
          .to_string(index=False, float_format=lambda v: "%.1f" % v))

    cg = correlogram(d, args.layer)
    cg.to_csv(OUT_DIR / ("spatial_autocorrelation%s.csv" % suf), index=False)
    print("\n--- 3. spatial autocorrelation of the residual O - %s ---"
          % args.layer)
    print("Roxburgh: correlations below 0.2 beyond about 10 km\n")
    print(cg.to_string(index=False, float_format=lambda v: "%.3f" % v))
    near = cg[cg["hi_km"] <= 10]["correlation"]
    if len(near):
        print("\n  within 10 km the residual correlation is %.2f"
              % float(near.mean()))
        print("  %s" % ("clustered enough that a random 70/30 split leaks "
                        "between calibration and validation"
                        if float(near.mean()) > 0.2 else
                        "weak enough that a random split is close to "
                        "independent"))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
