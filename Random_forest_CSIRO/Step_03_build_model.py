"""
Cross-validate and fit the random forest that maps soil + annual climate to FPI.

Reads   data/training_table.npz
Writes  data/random_forest_model.pkl
        data/cv_metrics.csv            metrics per scheme, and per fold
        data/cv_metrics_by_year.csv     temporal-CV skill, year by year
        data/oof_<scheme>.npz           out-of-fold predictions for every row
        data/feature_importances.csv

Three cross-validation schemes, because one number would be misleading
---------------------------------------------------------------------
Step_01_RF_for_FPI used a single random 80/20 split. That was defensible there -
one row per cell, so the two halves were at least different places. It is not
defensible here: every cell contributes 30 rows that share all 83 soil values
and differ only in one year's weather, so a random split puts 1994 and 1995 of
the same cell on both sides and the score mostly measures memorisation.

    kfold_random     5-fold over rows          the optimistic number, and the
                                               one comparable with Step_01
    blockcv_space    5-fold over 2 deg blocks  can it predict an unseen region
    groupcv_year     5-fold over years         can it predict an unseen year

`groupcv_year` is the one to quote: predicting 2035-2099 is exactly the act of
predicting years the model never saw. Expect it well below `kfold_random`; that
gap is the size of the leak, not a defect.

Spatial folds are contiguous 2-degree blocks rather than randomly chosen cells.
Holding out scattered cells leaves each one ringed by its own neighbours in the
training set, and at 1 km FPI is strongly autocorrelated, so random-cell
holdout scores nearly as high as no holdout at all and measures nothing.

Every scheme produces an out-of-fold prediction for every row - each row is
predicted exactly once, by the fold that did not train on it - so the metrics
below are computed on the whole 30-year table, not on one fifth of it.

The saved model is refitted on all 30 years afterwards. Cross-validation is
what measures skill; there is then no reason to hand the projection a model
trained on four fifths of the record.
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, KFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, MODEL_PATH, X_TABLE_PATH, regression_metrics

N_ESTIMATORS = 64
RANDOM_STATE = 42
N_JOBS = 96
N_FOLDS = 5

# Breiman's p/3 for regression, not sklearn's default of 1.0 that Step_01 used.
# This is a cost decision that the table's shape forces. A split search sorts
# the node's samples once per candidate feature, so the fit scales linearly in
# max_features; at 1.0 over 174 predictors and 1.67 M training rows a single
# fold took over 40 minutes and the 16 fits here would have taken ~13 hours.
# p/3 is 58 features per split and runs 3x faster.
#
# The accuracy cost is small and the direction is not even certain: these
# predictors are heavily redundant - six depth slices of every soil property,
# twelve months of every climate variable - so a split restricted to a random
# 58 of them almost always still sees a near-equivalent of the best one, while
# the extra randomness decorrelates the trees, which is the mechanism the
# ensemble averages over.
MAX_FEATURES = 1.0 / 3.0

# Not in Step_01, and the one hyperparameter that genuinely changed. With ~2 M
# rows a fully grown forest is ~17 GB of tree structure and spends its last
# splits separating individual cell-years; stopping at 5 samples per leaf cuts
# that roughly fivefold and costs almost nothing in skill, because FPI is smooth
# and carries real observational noise at that scale.
MIN_SAMPLES_LEAF = 5

# Side of the spatial CV blocks, in NLUM cells before downsampling: 200 cells =
# 2 degrees ~ 200 km, comfortably wider than the range over which FPI is
# autocorrelated.
BLOCK_CELLS = 200

SCHEMES = ["kfold_random", "blockcv_space", "groupcv_year"]


def make_model(n_jobs):
    return RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
        n_jobs=n_jobs,
        max_features=MAX_FEATURES,
        min_samples_leaf=MIN_SAMPLES_LEAF,
    )


def fold_iter(scheme, n, year, cell_row, cell_col, n_folds):
    if scheme == "kfold_random":
        return KFold(n_splits=n_folds, shuffle=True,
                     random_state=RANDOM_STATE).split(np.arange(n))
    if scheme == "blockcv_space":
        groups = ((cell_row // BLOCK_CELLS).astype(np.int64) * 10_000
                  + (cell_col // BLOCK_CELLS))
    elif scheme == "groupcv_year":
        groups = year.astype(np.int64)
    else:
        raise ValueError(scheme)
    return GroupKFold(n_splits=n_folds).split(np.arange(n), groups=groups)


def run_cv(scheme, X, y, year, cell_row, cell_col, n_folds, n_jobs):
    """Out-of-fold predictions for every row, plus the per-fold metrics."""
    oof = np.full(len(y), np.nan, dtype=np.float32)
    fold_id = np.full(len(y), -1, dtype=np.int8)
    rows = []

    for k, (tr, te) in enumerate(
            fold_iter(scheme, len(y), year, cell_row, cell_col, n_folds)):
        t0 = time.time()
        m = make_model(n_jobs)
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te]).astype(np.float32)
        fold_id[te] = k
        del m
        r = regression_metrics(y[te], oof[te])
        r.update(scheme=scheme, fold=k, n_train=len(tr), n_test=len(te),
                 seconds=round(time.time() - t0, 1))
        rows.append(r)
        held = (f"years {sorted(set(year[te].tolist()))}" if scheme == "groupcv_year"
                else f"{len(te):,} rows")
        print(f"  fold {k}: {held}  R2={r['r2']:.4f}  RMSE={r['rmse']:.4f}  "
              f"{r['seconds']:.0f}s")

    if fold_id.min() < 0:
        raise AssertionError(f"{scheme}: {int((fold_id < 0).sum())} rows never held out")

    overall = regression_metrics(y, oof)
    overall.update(scheme=scheme, fold="all", n_train=np.nan, n_test=len(y),
                   seconds=np.nan)
    print(f"  {scheme} pooled out-of-fold: R2={overall['r2']:.4f}  "
          f"RMSE={overall['rmse']:.4f}  MAE={overall['mae']:.4f}  "
          f"bias={overall['bias']:+.4f}  NSE={overall['nse']:.4f}")

    np.savez_compressed(DATA_DIR / f"oof_{scheme}.npz",
                        y_true=y, y_pred=oof, fold=fold_id,
                        year=year, cell_row=cell_row, cell_col=cell_col)
    return rows + [overall], oof


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=N_JOBS)
    ap.add_argument("--folds", type=int, default=N_FOLDS)
    ap.add_argument("--schemes", nargs="*", default=SCHEMES)
    ap.add_argument("--skip-cv", action="store_true")
    args = ap.parse_args()

    d = np.load(X_TABLE_PATH, allow_pickle=True)
    X, y = d["X"], d["y"]
    year, cell_row, cell_col = d["year"], d["cell_row"], d["cell_col"]
    names = list(d["feature_names"])
    n_soil = int(d["n_soil"])

    cells = np.unique(cell_row.astype(np.int64) * 100_000 + cell_col)
    print(f"X {X.shape}  y {y.shape}  {X.nbytes / 1e9:.2f} GB")
    print(f"{len(np.unique(year))} years {year.min()}-{year.max()}, "
          f"{len(cells):,} distinct cells, "
          f"{len(names)} features ({n_soil} soil + {len(names) - n_soil} climate)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    metrics = []

    if not args.skip_cv:
        for scheme in args.schemes:
            print(f"\n{scheme}  ({args.folds} folds)")
            rows, oof = run_cv(scheme, X, y, year, cell_row, cell_col,
                               args.folds, args.jobs)
            metrics += rows

            if scheme == "groupcv_year":
                by_year = []
                for yr in np.unique(year):
                    m = year == yr
                    r = regression_metrics(y[m], oof[m])
                    r.update(year=int(yr), n=int(m.sum()))
                    by_year.append(r)
                pd.DataFrame(by_year).to_csv(
                    DATA_DIR / "cv_metrics_by_year.csv", index=False)

        pd.DataFrame(metrics).to_csv(DATA_DIR / "cv_metrics.csv", index=False)

    print(f"\nfinal fit on all {len(y):,} rows")
    t0 = time.time()
    model = make_model(args.jobs)
    model.fit(X, y)
    print(f"  {time.time() - t0:.0f}s")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "feature_names": names,
                     "n_soil": n_soil, "years": sorted(np.unique(year).tolist())}, f)

    imp = pd.DataFrame({"feature": names, "importance": model.feature_importances_})
    imp["kind"] = ["soil"] * n_soil + ["climate"] * (len(names) - n_soil)
    imp = imp.sort_values("importance", ascending=False)
    imp.to_csv(DATA_DIR / "feature_importances.csv", index=False)

    print("\ntop 15 predictors")
    print(imp.head(15).to_string(index=False))
    print(f"\nsoil importance total   : {imp.loc[imp['kind'] == 'soil', 'importance'].sum():.3f}")
    print(f"climate importance total: {imp.loc[imp['kind'] == 'climate', 'importance'].sum():.3f}")
    print(f"\nwrote {MODEL_PATH}")


if __name__ == "__main__":
    main()
