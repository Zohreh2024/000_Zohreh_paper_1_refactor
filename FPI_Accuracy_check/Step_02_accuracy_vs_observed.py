"""
Step 02 - accuracy of the modelled historical FPI against the observed layers.

Two numbers, and they answer different questions
------------------------------------------------
in-sample      `output/fpi_rf_<year>.tif` against
               `Random_forest_CSIRO/required_data/fpi/fpi_<year>.tif`.
               These 30 years trained the model, so this measures fit, not
               skill. It is the right diagnostic for the ratio - it says how
               far the modelled denominator sits from the observed one, which
               is exactly the quantity that moves M' when the denominator is
               swapped.

out-of-fold    `Random_forest_CSIRO/data/oof_groupcv_year.npz`, the year-group
               cross-validation: every row was predicted by a forest that never
               saw that year. Projecting 2035-2099 is the same act, so this is
               the number to quote as accuracy. It is on the downsampled
               training cells (every 10th row and column), not the full grid.

Comparing a future projection against observed history would be neither - that
is a trend comparison, and the two are not supposed to agree.

Writes  output/accuracy_by_year.csv          in-sample, per year, full grid
        output/accuracy_summary.csv          pooled in-sample + pooled OOF
        output/oof_accuracy_by_year.csv      out-of-fold, per year
        plots/fig_fpi_rf_vs_observed.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_accuracy_vs_observed.py
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402

HERE = Path(__file__).resolve().parent
RF_DIR = HERE.parent / "Random_forest_CSIRO"
OUT_DIR = HERE / "output"
PLOT_DIR = HERE / "plots"
OBS_DIR = RF_DIR / "required_data" / "fpi"
OOF_PATH = RF_DIR / "data" / "oof_groupcv_year.npz"
HIST_YEARS = list(range(1985, 2015))

SUBSAMPLE = 50_000          # points per year kept for the pooled figure


def metrics(obs, pred):
    obs = obs.astype("float64")
    pred = pred.astype("float64")
    resid = pred - obs
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    return {
        "n": int(obs.size),
        "r2": 1 - ss_res / ss_tot if ss_tot else np.nan,
        "pearson_r": float(np.corrcoef(obs, pred)[0, 1]),
        "rmse": float(np.sqrt(np.mean(resid ** 2))),
        "mae": float(np.mean(np.abs(resid))),
        "bias": float(np.mean(resid)),
        "pbias": float(100 * np.sum(resid) / np.sum(obs)),
        "obs_mean": float(obs.mean()),
        "pred_mean": float(pred.mean()),
        "obs_sd": float(obs.std()),
        "pred_sd": float(pred.std()),
    }


def read(path):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float32")
        if s.nodata is not None and not np.isnan(s.nodata):
            a[a == s.nodata] = np.nan
    return a


def in_sample():
    rng = np.random.default_rng(42)
    rows, samp_o, samp_p = [], [], []

    for year in HIST_YEARS:
        pf = OUT_DIR / ("fpi_rf_%d.tif" % year)
        of = OBS_DIR / ("fpi_%d.tif" % year)
        if not pf.exists():
            print("  %d: no modelled raster, skipped" % year)
            continue
        if not of.exists():
            print("  %d: no observed raster, skipped" % year)
            continue

        p, o = read(pf), read(of)
        if p.shape != o.shape:
            print("  %d: shape mismatch %s vs %s, skipped" % (year, p.shape, o.shape))
            continue

        ok = np.isfinite(p) & np.isfinite(o)
        m = dict(metrics(o[ok], p[ok]), year=year)
        rows.append(m)

        n_ok = int(ok.sum())
        idx = rng.choice(n_ok, min(SUBSAMPLE, n_ok), replace=False)
        samp_o.append(o[ok][idx])
        samp_p.append(p[ok][idx])
        print("  %d: R2 %.4f  RMSE %.4f  bias %+.4f  n %s"
              % (year, m["r2"], m["rmse"], m["bias"], format(m["n"], ",")))

    if not rows:
        sys.exit("nothing compared - run Step_01 first")

    df = pd.DataFrame(rows).sort_values("year")
    df.to_csv(OUT_DIR / "accuracy_by_year.csv", index=False)
    return df, np.concatenate(samp_o), np.concatenate(samp_p)


def out_of_fold():
    """The year-group CV predictions Step_03 of the RF pipeline already wrote."""
    if not OOF_PATH.exists():
        print("  %s not found - skipping the out-of-fold report" % OOF_PATH.name)
        return None, None
    z = np.load(OOF_PATH)
    y_true, y_pred, year = z["y_true"], z["y_pred"], z["year"]
    pooled = metrics(y_true, y_pred)
    rows = []
    for yr in np.unique(year):
        s = year == yr
        rows.append(dict(metrics(y_true[s], y_pred[s]), year=int(yr)))
    df = pd.DataFrame(rows).sort_values("year")
    df.to_csv(OUT_DIR / "oof_accuracy_by_year.csv", index=False)
    print("  pooled R2 %.4f over %s rows, %d years"
          % (pooled["r2"], format(pooled["n"], ","), len(rows)))
    return pooled, df


def figure(obs, pred, df_in, pooled_in, df_oof):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4))

    hi = float(np.nanpercentile(np.concatenate([obs, pred]), 99.8))
    ax1.hexbin(obs, pred, gridsize=90, bins="log", cmap="Blues", mincnt=1,
               extent=(0, hi, 0, hi))
    ax1.plot([0, hi], [0, hi], "k-", lw=1.4, label="1:1")
    ax1.set_xlim(0, hi)
    ax1.set_ylim(0, hi)
    ax1.set_xlabel("observed FPI (DCCEEW)")
    ax1.set_ylabel("modelled FPI (random forest, in sample)")
    ax1.set_title("R$^2$ = %.4f   RMSE = %.3f   bias = %+.4f"
                  % (pooled_in["r2"], pooled_in["rmse"], pooled_in["bias"]))
    ax1.legend(frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.plot(df_in["year"], df_in["r2"], "o-", color="#1b3a5c", label="in sample")
    if df_oof is not None:
        ax2.plot(df_oof["year"], df_oof["r2"], "s--", color="#c8791a",
                 label="out of fold (year-group CV)")
    ax2.set_xlabel("year")
    ax2.set_ylabel("R$^2$")
    ax2.set_title("Accuracy by year")
    ax2.legend(frameon=False)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    dst = PLOT_DIR / "fig_fpi_rf_vs_observed.png"
    fig.savefig(dst, dpi=170)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("in-sample, full NLUM grid:")
    df_in, obs, pred = in_sample()
    pooled_in = metrics(obs, pred)

    print("\nout-of-fold (year-group CV, downsampled training cells):")
    pooled_oof, df_oof = out_of_fold()

    summary = [dict(pooled_in, scheme="in_sample_full_grid",
                    note="pooled over a 50k-per-year subsample; "
                         "per-year rows use every cell")]
    if pooled_oof:
        summary.append(dict(pooled_oof, scheme="out_of_fold_groupcv_year",
                            note="quote this one as accuracy"))
    pd.DataFrame(summary).to_csv(OUT_DIR / "accuracy_summary.csv", index=False)

    print("\n" + "=" * 66)
    for row in summary:
        print("%-26s R2 %.4f  RMSE %.4f  MAE %.4f  bias %+.4f  pbias %+.3f%%"
              % (row["scheme"], row["r2"], row["rmse"], row["mae"],
                 row["bias"], row["pbias"]))
    print("=" * 66)
    print("Quote the out-of-fold row as accuracy. The in-sample row is the fit,")
    print("and is the relevant one for how far the modelled denominator of M'")
    print("sits from the observed one.")

    if not args.no_figure:
        try:
            print("figure -> %s" % figure(obs, pred, df_in, pooled_in, df_oof))
        except Exception as exc:                            # noqa: BLE001
            print("figure skipped: %s" % exc)

    print("tables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
