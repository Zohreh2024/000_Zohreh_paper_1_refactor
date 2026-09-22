"""
Step 02 - Roxburgh's four fit statistics, on every layer.

The paper judges a maximum-biomass layer on four numbers (his Section 2.5 and
Table 4), two for accuracy and two for overall agreement:

    ME     mean error, E - O averaged. The sign is the bias: negative is
           under-prediction. Roxburgh's Table 4 gives -35.3 t DM/ha for the
           original FullCAM M and -8.0 for the revised M' on withheld data.
    RMSE   root mean squared error, the precision. 239.1 and 200.7.
    EF     model efficiency (Nash & Sutcliffe 1970), his Eq. (4):
               EF = 1 - sum (O_i - E_i)^2 / sum (O_i - Obar)^2
           1.0 is perfect; 0.0 means the layer is no better than predicting the
           mean of the observations everywhere; negative is worse than that.
           0.14 and 0.40.
    LCC    Lin's concordance correlation coefficient, his Eq. (5):
               LCC = 2 S_OE^2 / (S_O^2 + S_E^2 + (Obar - Ebar)^2)
           agreement with the 1:1 line, not with any line. Correlation alone
           cannot see a constant offset or a wrong slope; LCC can. 0.25 and
           0.62.

All four are computed on UNTRANSFORMED data, as the paper states, even where a
figure is later drawn on transformed axes.

Why reproducing the first two rows matters
------------------------------------------
Original_M_2004 and New_M_2019 are the two layers Roxburgh himself scored. Our
sample is not his - the 2024 library without his satellite cover-continuity
check or his custodian disturbance metadata - so the numbers will not match his exactly, and they are not meant to. What they
establish is the ORDERING: if the protocol has been transplanted correctly, the
revised layer must score better than the original on our sample too, in the same
direction and by a comparable margin. Only then is it worth applying the same
statistics to the eight future layers.

Bootstrap intervals accompany every statistic, because with 600 records - and
64 of them Forest - a difference of 0.05 in EF is not necessarily a difference
at all.

Reads   outputs/records.csv
Writes  outputs/fit_statistics.csv             every layer, whole sample
        outputs/fit_statistics_by_class.csv    Forest / Woodland
        outputs/fit_statistics_by_state.csv
        outputs/lambda_summary.csv             Roxburgh Eq. (2), per layer

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_fit_statistics.py
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
BOOT = 2000

# Roxburgh et al. (2019) Table 4, for the two layers the paper scored itself.
ROXBURGH_TABLE_4 = {
    "M_original_2004": dict(ME=-35.3, RMSE=239.1, EF=0.14, LCC=0.25,
                            scope="Original M, n = 5739"),
    "M_revised_Roxburgh": dict(ME=-8.0, RMSE=200.7, EF=0.40, LCC=0.62,
                               scope="M'-Validation, n = 5739"),
}


def ef(obs, pred):
    """Model efficiency, Roxburgh Eq. (4) / Nash & Sutcliffe (1970)."""
    denom = float(((obs - obs.mean()) ** 2).sum())
    if denom == 0:
        return np.nan
    return 1.0 - float(((obs - pred) ** 2).sum()) / denom


def lcc(obs, pred):
    """Lin's concordance correlation coefficient, Roxburgh Eq. (5).

    Written with the population (biased) moments the definition uses, so that
    the covariance term and the two variances are on the same footing.
    """
    o, e = obs - obs.mean(), pred - pred.mean()
    s_oe = float((o * e).mean())
    s_o = float((o ** 2).mean())
    s_e = float((e ** 2).mean())
    denom = s_o + s_e + (obs.mean() - pred.mean()) ** 2
    if denom == 0:
        return np.nan
    return 2.0 * s_oe / denom


def stats_of(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    g = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[g], pred[g]
    if len(obs) < 3:
        return dict(n=len(obs), ME=np.nan, RMSE=np.nan, EF=np.nan, LCC=np.nan,
                    median_ratio=np.nan, obs_median=np.nan, pred_median=np.nan)
    return dict(
        n=int(len(obs)),
        ME=float((pred - obs).mean()),
        RMSE=float(np.sqrt(((pred - obs) ** 2).mean())),
        EF=ef(obs, pred),
        LCC=lcc(obs, pred),
        median_ratio=float(np.median(pred / obs)),
        obs_median=float(np.median(obs)),
        pred_median=float(np.median(pred)),
    )


def boot_ci(obs, pred, fn, n_boot=BOOT, seed=0):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    g = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[g], pred[g]
    if len(obs) < 10:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(obs), (n_boot, len(obs)))
    vals = np.array([fn(obs[i], pred[i]) for i in idx])
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def layer_names(d):
    return [c for c in d.columns
            if c.startswith("M_") and not c.startswith("lambda_")]


def table_for(d, label=""):
    rows = []
    for c in layer_names(d):
        r = stats_of(d["agb"], d[c])
        r["layer"] = c
        if label:
            r["stratum"] = label
        lo, hi = boot_ci(d["agb"], d[c], ef)
        r["EF_lo"], r["EF_hi"] = lo, hi
        lo, hi = boot_ci(d["agb"], d[c], lcc)
        r["LCC_lo"], r["LCC_hi"] = lo, hi
        rows.append(r)
    cols = (["layer"] + (["stratum"] if label else [])
            + ["n", "obs_median", "pred_median", "median_ratio",
               "ME", "RMSE", "EF", "EF_lo", "EF_hi", "LCC", "LCC_lo", "LCC_hi"])
    return pd.DataFrame(rows)[cols]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default="records.csv",
                    help="which record table to score. Whatever tag Step_01 "
                         "gave it carries through to every output file, so the "
                         "sample variants never overwrite one another")
    ap.add_argument("--min-n", type=int, default=20,
                    help="a stratum with fewer records than this is reported "
                         "but flagged, never quietly dropped")
    args = ap.parse_args()

    d = pd.read_csv(OUT_DIR / args.records, low_memory=False)
    suf = args.records[len("records"):-len(".csv")]
    print("%d records, %d layers" % (len(d), len(layer_names(d))))

    overall = table_for(d)
    overall.to_csv(OUT_DIR / ("fit_statistics%s.csv" % suf), index=False)

    by_class = pd.concat(
        [table_for(sub, cls) for cls, sub in d.groupby("veg_class")],
        ignore_index=True)
    by_class["underpowered"] = by_class["n"] < args.min_n
    by_class.to_csv(OUT_DIR / ("fit_statistics_by_class%s.csv" % suf), index=False)

    by_state = pd.concat(
        [table_for(sub, st) for st, sub in d.groupby("state")],
        ignore_index=True)
    by_state["underpowered"] = by_state["n"] < args.min_n
    by_state.to_csv(OUT_DIR / ("fit_statistics_by_state%s.csv" % suf), index=False)

    lam = []
    for c in layer_names(d):
        v = d["lambda_" + c].to_numpy()
        v = v[np.isfinite(v)]
        lam.append(dict(layer=c, n=len(v), median=float(np.median(v)),
                        p05=float(np.percentile(v, 5)),
                        p25=float(np.percentile(v, 25)),
                        p75=float(np.percentile(v, 75)),
                        p95=float(np.percentile(v, 95)),
                        pct_over_1=float(100 * np.mean(v > 1))))
    pd.DataFrame(lam).to_csv(OUT_DIR / ("lambda_summary%s.csv" % suf), index=False)

    # ---- the transplant check ------------------------------------------- #
    print("\n--- Roxburgh Table 4, reproduced on this sample ---")
    print("%-24s %7s %8s %8s %7s %7s   %s"
          % ("layer", "n", "ME", "RMSE", "EF", "LCC", "Roxburgh's own"))
    for _, r in overall.iterrows():
        pub = ROXBURGH_TABLE_4.get(r["layer"])
        note = ("ME %+.1f RMSE %.1f EF %.2f LCC %.2f  [%s]"
                % (pub["ME"], pub["RMSE"], pub["EF"], pub["LCC"], pub["scope"])
                if pub else "")
        print("%-24s %7d %8.1f %8.1f %7.2f %7.2f   %s"
              % (r["layer"], r["n"], r["ME"], r["RMSE"], r["EF"], r["LCC"],
                 note))

    o = overall.set_index("layer")
    if {"M_original_2004", "M_revised_Roxburgh"} <= set(o.index):
        d_ef = o.loc["M_revised_Roxburgh", "EF"] - o.loc["M_original_2004", "EF"]
        d_lcc = (o.loc["M_revised_Roxburgh", "LCC"]
                 - o.loc["M_original_2004", "LCC"])
        print("\nrevised minus original on this sample: EF %+.2f, LCC %+.2f"
              % (d_ef, d_lcc))
        print("Roxburgh's own gain, on his 5,739 records:  EF %+.2f, LCC %+.2f"
              % (ROXBURGH_TABLE_4["M_revised_Roxburgh"]["EF"]
                 - ROXBURGH_TABLE_4["M_original_2004"]["EF"],
                 ROXBURGH_TABLE_4["M_revised_Roxburgh"]["LCC"]
                 - ROXBURGH_TABLE_4["M_original_2004"]["LCC"]))

    print("\nby vegetation class")
    print(by_class[["layer", "stratum", "n", "ME", "RMSE", "EF", "LCC"]]
          .to_string(index=False, float_format=lambda v: "%.2f" % v))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
