"""
Step 03 - which sample decision moves the fit statistics, and by how much.

Step_02 scores Roxburgh's own layer, New_M_2019, at ME -36 t DM/ha, EF -0.41 and
LCC -0.08 on our records. He reports -8.0, 0.40 and 0.62 on his. The layer is
the same file. So the whole of that gap is the sample, and this step finds out
which part of it.

The method is a one-at-a-time walk over every sample decision that differs
between his construction and ours, scoring the SAME layer each time:

    unit             one row per observation (his) or per site taking the
                     maximum (the space-time validation's)
    plot size        no minimum (his) against 0.05 and 0.5 ha
    vintage          the whole 2024 library against the 2017 cut he used
    biomass-basal    no consistency check (his) against 1 t per m2
    maturity         every stand against stem-verified mature only
    vegetation       everything against Forest only and Woodland only
    outliers         everything against trimming the top 1% of observations

Read the EF and LCC columns, not ME. A bias can be produced by shifting the
whole sample and tells you little; EF and LCC fall only when the RANKING breaks
down, and a layer that cannot rank sites is a layer that cannot be validated
against them at all.

Every variant is derived in memory from the unfiltered record table, so this
step re-reads no rasters and runs in seconds.

Reads   outputs/records.csv        built with every optional filter off
Writes  outputs/sample_sensitivity.csv
        outputs/sample_sensitivity_by_class.csv

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_sample_sensitivity.py
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"

MATURE = ["verified mature", "likely mature"]
DEFAULT_LAYERS = ["M_original_2004", "M_revised_Roxburgh",
                  "M_future_ssp585_2070-2099"]


def ef(obs, pred):
    denom = float(((obs - obs.mean()) ** 2).sum())
    return np.nan if denom == 0 else 1.0 - float(((obs - pred) ** 2).sum()) / denom


def lcc(obs, pred):
    o, e = obs - obs.mean(), pred - pred.mean()
    denom = float((o ** 2).mean()) + float((e ** 2).mean()) \
        + (obs.mean() - pred.mean()) ** 2
    return np.nan if denom == 0 else 2.0 * float((o * e).mean()) / denom


def score(d, layer):
    obs = d["agb"].to_numpy(float)
    pred = d[layer].to_numpy(float)
    g = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[g], pred[g]
    if len(obs) < 10:
        return dict(n=len(obs))
    return dict(
        n=int(len(obs)),
        obs_mean=float(obs.mean()), obs_median=float(np.median(obs)),
        pred_mean=float(pred.mean()),
        ME=float((pred - obs).mean()),
        RMSE=float(np.sqrt(((pred - obs) ** 2).mean())),
        EF=ef(obs, pred), LCC=lcc(obs, pred),
        pearson_r=float(np.corrcoef(obs, pred)[0, 1]),
        spearman_rho=float(sps.spearmanr(obs, pred).correlation),
        median_ratio=float(np.median(pred / obs)),
    )


def to_sites(d):
    """Collapse repeat visits to one row per site, taking the maximum."""
    keep = d.sort_values("agb", ascending=False).drop_duplicates("site")
    return keep.reset_index(drop=True)


def variants(d):
    """(name, group, subset) for every sample decision, one at a time."""
    yield ("Roxburgh's construction (the baseline here)", "baseline", d)

    yield ("one row per site, maximum measurement", "unit", to_sites(d))

    for a in (0.05, 0.5):
        yield ("plot at least %.2f ha" % a, "plot size",
               d[d["area_ha"] >= a])

    yield ("library as at 2017, the vintage he used", "vintage",
           d[d["year"] <= 2017])

    yield ("biomass consistent with basal area", "biomass-basal",
           d[d["agb_per_ba"] >= 1.0])

    yield ("stem-verified mature only", "maturity",
           d[d["maturity"] == "verified mature"])
    yield ("mature (verified or likely)", "maturity",
           d[d["maturity"].isin(MATURE)])

    for cls in ("Forest", "Woodland"):
        yield ("%s only" % cls, "vegetation", d[d["veg_class"] == cls])

    hi = float(np.percentile(d["agb"], 99))
    yield ("top 1%% of observations trimmed (> %.0f t DM/ha)" % hi, "outliers",
           d[d["agb"] <= hi])

    # everything this repo applies, together - the sample the rest of the
    # repository actually validates against
    repo = d[(d["area_ha"] >= 0.05) & (d["agb_per_ba"] >= 1.0)
             & (d["year"] >= 1985)]
    yield ("all of this repo's filters together", "combined", repo)
    yield ("this repo's filters, one row per site", "combined", to_sites(repo))
    yield ("this repo's filters, per site, mature only", "combined",
           to_sites(repo)[to_sites(repo)["maturity"].isin(MATURE)])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layers", nargs="*", default=DEFAULT_LAYERS)
    args = ap.parse_args()

    d = pd.read_csv(OUT_DIR / "records.csv", low_memory=False)
    print("base sample: %s records\n" % format(len(d), ","))

    rows = []
    for name, group, sub in variants(d):
        for layer in args.layers:
            if layer not in sub.columns:
                continue
            r = score(sub, layer)
            r.update(variant=name, group=group, layer=layer)
            rows.append(r)
    out = pd.DataFrame(rows)
    cols = ["group", "variant", "layer", "n", "obs_mean", "pred_mean",
            "median_ratio", "ME", "RMSE", "EF", "LCC", "pearson_r",
            "spearman_rho"]
    out = out[[c for c in cols if c in out.columns]]
    out.to_csv(OUT_DIR / "sample_sensitivity.csv", index=False)

    key = "M_revised_Roxburgh"
    show = out[out["layer"] == key]
    print("scoring %s - the layer Roxburgh himself scored at "
          "ME -8.0, RMSE 200.7, EF 0.40, LCC 0.62\n" % key)
    print("%-48s %6s %8s %8s %7s %7s %7s"
          % ("sample", "n", "obs mean", "ME", "EF", "LCC", "r"))
    print("-" * 96)
    for _, r in show.iterrows():
        print("%-48s %6d %8.1f %8.1f %7.2f %7.2f %7.2f"
              % (r["variant"][:48], r["n"], r["obs_mean"], r["ME"],
                 r["EF"], r["LCC"], r["pearson_r"]))

    # the same walk, inside each vegetation class, since the classes have very
    # different biomass ranges and a statistic pooled over both is dominated by
    # whichever class carries the spread
    rows = []
    for cls, sub_cls in d.groupby("veg_class"):
        if cls == "Excluded":
            continue
        for name, group, sub in variants(sub_cls):
            for layer in args.layers:
                if layer not in sub.columns:
                    continue
                r = score(sub, layer)
                r.update(variant=name, group=group, layer=layer, veg_class=cls)
                rows.append(r)
    by_cls = pd.DataFrame(rows)
    by_cls = by_cls[["veg_class"] + [c for c in cols if c in by_cls.columns]]
    by_cls.to_csv(OUT_DIR / "sample_sensitivity_by_class.csv", index=False)

    print("\nwithin each vegetation class, %s:" % key)
    sel = by_cls[(by_cls["layer"] == key) & (by_cls["group"].isin(
        ["baseline", "plot size", "combined"]))]
    print(sel[["veg_class", "variant", "n", "obs_mean", "ME", "EF", "LCC",
               "pearson_r"]].to_string(index=False,
                                       float_format=lambda v: "%.2f" % v))
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
