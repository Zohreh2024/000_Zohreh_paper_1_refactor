#!/usr/bin/env python3
"""
Step 2 of 2 - model the reference FPI, check its accuracy, rebuild M-prime.

This is what Brett asked for:

    "You have to go back and use your machine learning to model reference FPI,
     and use the modelled reference and future in here."
    "Don't combine a data set calculated by someone else with your data set
     that's modelled using machine learning."

Why it matters
--------------
The M-prime ratio currently mixes two sources:

    Eq1(FPI_future from your RF)  /  Eq1(FPI_historical downloaded)

Any bias in the random forest sits in the numerator only, so it does not
cancel. It is then read as climate change. With both sides modelled:

    Eq1(RF future)  /  Eq1(RF historical)     -> the bias cancels

This is the same rule already applied to temperature and rainfall, where every
delta is computed CSIRO-minus-CSIRO and never CSIRO-minus-ANUClimate. FPI was
the one input where it was not applied.

Commands
--------
    # 1. predict historical FPI, one raster per year
    python model_reference_fpi.py predict --data-dir DATA --features-dir FEAT --out-dir OUT

    # 2. accuracy of modelled vs actual historical FPI
    python model_reference_fpi.py accuracy --pred-dir OUT --actual-dir ACTUAL

    # 3. rebuild the M-prime denominator and all eight scenarios
    python model_reference_fpi.py mprime --pred-dir OUT --future-fpi-dir FUT \\
        --baseline /path/to/New_M_2019.tif --out-dir MOUT

Install
-------
    pip install joblib scikit-learn rasterio numpy pandas matplotlib

Run inspect_artifacts.py first. The feature order must match the model exactly;
a wrong order gives plausible numbers with no error raised.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Eq. (1) of Roxburgh et al. (2019)
EQ1_A = 6.011
EQ1_B = 5.291

REFERENCE_YEARS = list(range(1985, 2015))
CHUNK = 400_000          # cells per prediction chunk - keeps memory bounded


def eq1(fpi: np.ndarray) -> np.ndarray:
    """Predicted maximum AGB for a given FPI. Clipped at zero below the root."""
    root = EQ1_A * np.sqrt(np.clip(fpi, 0, None)) - EQ1_B
    return np.where(root > 0, root ** 2, 0.0)


# --------------------------------------------------------------------------
# Raster helpers
# --------------------------------------------------------------------------

def read_raster(path: Path) -> tuple[np.ndarray, dict]:
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(1).astype("float64")
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        prof = src.profile.copy()
    return a, prof


def write_raster(path: Path, arr: np.ndarray, profile: dict) -> None:
    import rasterio
    prof = profile.copy()
    prof.update(dtype="float32", count=1, compress="lzw", nodata=np.nan)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(arr.astype("float32"), 1)


def year_from_name(name: str) -> int | None:
    import re
    m = re.search(r"(19|20)\d{2}", name)
    return int(m.group(0)) if m else None


# --------------------------------------------------------------------------
# Command: predict
# --------------------------------------------------------------------------

def cmd_predict(args) -> None:
    """
    Run the saved random forest over the historical predictors.

    No retraining. The same fitted model that produced the future FPI is applied
    to the historical climate, so both sides of the ratio come from one source.
    """
    import joblib

    data_dir = Path(args.data_dir)
    feat_dir = Path(args.features_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading model from {data_dir / 'random_forest_model.joblib'}")
    model = joblib.load(data_dir / "random_forest_model.joblib")
    if args.n_jobs:
        try:
            model.n_jobs = args.n_jobs
        except Exception:
            pass

    names = getattr(model, "feature_names_in_", None)
    if names is None:
        order_file = data_dir / "feature_order.npy"
        if order_file.exists():
            names = np.load(order_file, allow_pickle=True)
        else:
            sys.exit("Cannot determine feature order. Run inspect_artifacts.py first.")
    names = [str(n) for n in names]
    print(f"  {len(names)} features, {getattr(model, 'n_estimators', '?')} trees")

    years = args.years or REFERENCE_YEARS
    print(f"  years: {years[0]}-{years[-1]} ({len(years)})")

    for year in years:
        out_path = out_dir / f"fpi_rf_{year}.tif"
        if out_path.exists() and not args.overwrite:
            print(f"  {year}: exists, skipping (use --overwrite to redo)")
            continue

        t0 = time.time()
        X, profile, valid = build_feature_matrix(feat_dir, year, names)
        if X is None:
            print(f"  {year}: predictors not found, skipped")
            continue

        n = X.shape[0]
        pred = np.empty(n, dtype="float32")
        for s in range(0, n, CHUNK):
            e = min(s + CHUNK, n)
            pred[s:e] = model.predict(X[s:e]).astype("float32")
            if args.verbose and (s // CHUNK) % 5 == 0:
                print(f"      {e:,}/{n:,}", end="\r")

        shape = (profile["height"], profile["width"])
        grid = np.full(shape, np.nan, dtype="float32")
        grid.flat[valid] = pred

        write_raster(out_path, grid, profile)
        print(f"  {year}: {n:,} cells, median {np.nanmedian(grid):.3f}, "
              f"{time.time() - t0:.0f}s -> {out_path.name}")

    print(f"\nDone. Rasters in {out_dir}")


def build_feature_matrix(feat_dir: Path, year: int, names: list[str]):
    """
    Assemble the predictor matrix for one year, in the model's column order.

    Expects one GeoTIFF per feature. Climate layers are looked up with the year
    in the filename; soil layers are static and reused every year, which mirrors
    how the future prediction was built.

    If your predictors live in NetCDF or a single stacked file, replace this
    function - it is the only part that touches your storage layout.
    """
    cols, profile, mask = [], None, None

    for nm in names:
        cand = list(feat_dir.rglob(f"*{nm}*{year}*.tif")) or \
               list(feat_dir.rglob(f"*{year}*{nm}*.tif")) or \
               list(feat_dir.rglob(f"*{nm}*.tif"))          # static soil layer
        if not cand:
            print(f"      missing predictor: {nm}")
            return None, None, None

        arr, prof = read_raster(cand[0])
        if profile is None:
            profile = prof
            mask = np.isfinite(arr)
        else:
            mask &= np.isfinite(arr)
        cols.append(arr)

    valid = np.flatnonzero(mask.ravel())
    X = np.column_stack([c.ravel()[valid] for c in cols]).astype("float32")
    return X, profile, valid


# --------------------------------------------------------------------------
# Command: accuracy
# --------------------------------------------------------------------------

def cmd_accuracy(args) -> None:
    """
    Modelled historical FPI against actual historical FPI.

    This is an accuracy assessment. Comparing a future projection against
    observed history is a trend comparison, not an accuracy assessment - as
    Brett put it, the two are not supposed to be the same.
    """
    pred_dir, act_dir = Path(args.pred_dir), Path(args.actual_dir)
    rows, all_p, all_a = [], [], []

    for pf in sorted(pred_dir.glob("fpi_rf_*.tif")):
        year = year_from_name(pf.name)
        cand = list(act_dir.rglob(f"*{year}*.tif")) + list(act_dir.rglob(f"*{year}*.nc"))
        if not cand:
            print(f"  {year}: no actual layer found, skipped")
            continue

        p, _ = read_raster(pf)
        a, _ = read_raster(cand[0])
        if p.shape != a.shape:
            print(f"  {year}: shape mismatch {p.shape} vs {a.shape}, skipped")
            continue

        ok = np.isfinite(p) & np.isfinite(a)
        pv, av = p[ok], a[ok]
        rows.append(metrics(av, pv) | {"year": year, "n": int(ok.sum())})

        # subsample for the pooled figure, so it stays plottable
        idx = np.random.default_rng(42).choice(pv.size, min(50_000, pv.size), False)
        all_p.append(pv[idx]); all_a.append(av[idx])
        print(f"  {year}: R2 {rows[-1]['r2']:.4f}  RMSE {rows[-1]['rmse']:.4f}  "
              f"bias {rows[-1]['bias']:+.4f}")

    if not rows:
        sys.exit("Nothing compared - check --actual-dir and the filenames.")

    df = pd.DataFrame(rows).sort_values("year")
    out = Path(args.out_csv or "fpi_rf_accuracy_by_year.csv")
    df.to_csv(out, index=False)

    p, a = np.concatenate(all_p), np.concatenate(all_a)
    pooled = metrics(a, p)

    print(f"\n{'=' * 70}\nPOOLED ACROSS YEARS\n{'=' * 70}")
    for k, v in pooled.items():
        print(f"  {k:<10} {v:.5f}")
    print(f"\n  per-year table -> {out}")
    print("\n  Note: the model was fitted on these years, so this is an in-sample")
    print("  check. For the number to quote as accuracy, use the out-of-fold")
    print("  results already in cv_metrics.csv - groupcv_year is the one that")
    print("  matches what a projection actually asks of the model.")

    try:
        scatter_figure(a, p, df, pooled)
        print("  figure -> fig_fpi_rf_vs_actual.png")
    except Exception as exc:
        print(f"  figure skipped: {exc}")


def metrics(obs: np.ndarray, pred: np.ndarray) -> dict:
    resid = pred - obs
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    return {
        "r2": 1 - ss_res / ss_tot if ss_tot else np.nan,
        "pearson_r": float(np.corrcoef(obs, pred)[0, 1]),
        "rmse": float(np.sqrt(np.mean(resid ** 2))),
        "mae": float(np.mean(np.abs(resid))),
        "bias": float(np.mean(resid)),
        "pbias": float(100 * np.sum(resid) / np.sum(obs)),
        "obs_mean": float(obs.mean()),
        "pred_mean": float(pred.mean()),
    }


def scatter_figure(a, p, df, pooled):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4))

    ax1.hexbin(a, p, gridsize=90, bins="log", cmap="Blues", mincnt=1)
    lim = [0, float(np.nanpercentile(np.concatenate([a, p]), 99.8))]
    ax1.plot(lim, lim, "k-", lw=1.4, label="1:1")
    ax1.set_xlim(lim); ax1.set_ylim(lim)
    ax1.set_xlabel("actual historical FPI")
    ax1.set_ylabel("modelled historical FPI (random forest)")
    ax1.set_title(f"R\u00b2 = {pooled['r2']:.4f}   RMSE = {pooled['rmse']:.3f}   "
                  f"bias = {pooled['bias']:+.4f}")
    ax1.legend(frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.plot(df["year"], df["r2"], "o-", color="#1b3a5c", label="R\u00b2")
    ax2b = ax2.twinx()
    ax2b.plot(df["year"], df["bias"], "s--", color="#c8791a", label="bias")
    ax2b.axhline(0, color="grey", lw=1)
    ax2.set_xlabel("year"); ax2.set_ylabel("R\u00b2", color="#1b3a5c")
    ax2b.set_ylabel("bias", color="#c8791a")
    ax2.set_title("Accuracy by year")
    ax2.spines[["top"]].set_visible(False)

    fig.tight_layout()
    fig.savefig("fig_fpi_rf_vs_actual.png", dpi=170)


# --------------------------------------------------------------------------
# Command: mprime
# --------------------------------------------------------------------------

def cmd_mprime(args) -> None:
    """
    Rebuild the denominator from modelled reference FPI and redo all scenarios.

    Order of operations matters and is applied identically on both sides:
    Eq. (1) is evaluated on EACH annual raster and the results are averaged,
    never Eq. (1) of the 30-year mean FPI. Eq. (1) is convex, so by Jensen's
    inequality the two orders differ - and if the numerator used one order and
    the denominator the other, the difference would enter the ratio as a
    spurious climate signal.
    """
    pred_dir = Path(args.pred_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- denominator ---------------------------------------------------
    files = sorted(pred_dir.glob("fpi_rf_*.tif"))
    files = [f for f in files if (y := year_from_name(f.name)) and 1985 <= y <= 2014]
    if not files:
        sys.exit(f"No modelled reference rasters in {pred_dir}")
    if len(files) != 30:
        print(f"  WARNING: {len(files)} reference years found, expected 30")

    print(f"Building denominator from {len(files)} modelled reference years")
    acc, profile, n = None, None, 0
    for f in files:
        a, prof = read_raster(f)
        if profile is None:
            profile = prof
        e = eq1(a)
        acc = e if acc is None else acc + e
        n += 1
    D = acc / n
    write_raster(out_dir / "D_denominator_rf.tif", D, profile)
    print(f"  denominator median: {np.nanmedian(D):.3f}")

    if args.old_denominator:
        old, _ = read_raster(Path(args.old_denominator))
        if old.shape == D.shape:
            ok = np.isfinite(old) & np.isfinite(D) & (old > 0)
            r = D[ok] / old[ok]
            print(f"\n  new vs old denominator (downloaded FPI):")
            print(f"    median ratio {np.median(r):.4f}   "
                  f"p05 {np.percentile(r, 5):.4f}   p95 {np.percentile(r, 95):.4f}")
            print("    A ratio near 1.000 means the RF bias was small and M-prime")
            print("    will barely move; the change is then methodological rather")
            print("    than numerical, which is still the right thing to report.")

    # --- baseline ------------------------------------------------------
    base, base_prof = read_raster(Path(args.baseline))
    print(f"\nBaseline {Path(args.baseline).name}: median {np.nanmedian(base):.3f}")

    # --- scenarios -----------------------------------------------------
    fut_dir = Path(args.future_fpi_dir)
    groups: dict[str, list[Path]] = {}
    for f in sorted(fut_dir.rglob("*.tif")):
        import re
        m = re.search(r"(ssp\d{3})", f.name.lower())
        y = year_from_name(f.name)
        if not m or not y:
            continue
        window = "mid" if 2035 <= y <= 2064 else "late" if 2070 <= y <= 2099 else None
        if window:
            groups.setdefault(f"{m.group(1)}_{window}", []).append(f)

    if not groups:
        sys.exit(f"No future FPI rasters matched in {fut_dir}")

    rows = []
    for key in sorted(groups):
        fs = groups[key]
        acc, n = None, 0
        for f in fs:
            a, _ = read_raster(f)
            e = eq1(a)
            acc = e if acc is None else acc + e
            n += 1
        N = acc / n

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(D > 0, N / D, np.nan)
        mprime = base * ratio

        write_raster(out_dir / f"Mprime_{key}.tif", mprime, base_prof)

        ok = np.isfinite(mprime) & np.isfinite(base) & (base > 0)
        pct = (mprime[ok] - base[ok]) / base[ok] * 100
        rows.append({
            "scenario_window": key,
            "n_years": n,
            "median_ratio": float(np.nanmedian(ratio)),
            "median_Mprime": float(np.nanmedian(mprime)),
            "median_pct_change": float(np.median(pct)),
            "p05_pct": float(np.percentile(pct, 5)),
            "p95_pct": float(np.percentile(pct, 95)),
            "pct_cells_declining": float(np.mean(pct < 0) * 100),
        })
        print(f"  {key:<16} {n:>2} yrs   median M' {rows[-1]['median_Mprime']:6.2f}   "
              f"change {rows[-1]['median_pct_change']:+7.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "mprime_summary.csv", index=False)
    print(f"\nRasters and mprime_summary.csv -> {out_dir}")
    print(f"Historical M' is the baseline itself, median {np.nanmedian(base):.2f} "
          "- the ratio is 1 by construction.")


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("predict", help="model historical FPI with the saved RF")
    p1.add_argument("--data-dir", required=True)
    p1.add_argument("--features-dir", required=True,
                    help="folder holding the historical predictor rasters")
    p1.add_argument("--out-dir", required=True)
    p1.add_argument("--years", type=int, nargs="+", default=None)
    p1.add_argument("--n-jobs", type=int, default=-1)
    p1.add_argument("--overwrite", action="store_true")
    p1.add_argument("--verbose", action="store_true")
    p1.set_defaults(func=cmd_predict)

    p2 = sub.add_parser("accuracy", help="modelled vs actual historical FPI")
    p2.add_argument("--pred-dir", required=True)
    p2.add_argument("--actual-dir", required=True)
    p2.add_argument("--out-csv", default=None)
    p2.set_defaults(func=cmd_accuracy)

    p3 = sub.add_parser("mprime", help="rebuild M-prime on the modelled reference")
    p3.add_argument("--pred-dir", required=True)
    p3.add_argument("--future-fpi-dir", required=True)
    p3.add_argument("--baseline", required=True, help="New_M_2019.tif")
    p3.add_argument("--out-dir", required=True)
    p3.add_argument("--old-denominator", default=None,
                    help="the previous D built from downloaded FPI, to compare")
    p3.set_defaults(func=cmd_mprime)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()