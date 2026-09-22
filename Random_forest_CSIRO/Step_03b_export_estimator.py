"""
Re-export the fitted forest as a bare estimator, and as joblib.

Reads   data/random_forest_model.pkl
Writes  data/random_forest_estimator.pkl    the RandomForestRegressor alone
        data/random_forest_model.joblib     the same dict, joblib-compressed
        data/model_card.txt                 what the file is and how to use it

Step_03 saves a dict - `{"model", "feature_names", "n_soil", "years"}` - rather
than the estimator on its own, so the column contract travels with the weights
and Step_04 can refuse to predict if the two ever disagree. That is the right
default, but it means `pickle.load(f).predict(X)` does not work, which is what
most downstream code and most people expect.

So both forms exist. Use the dict when you care about correctness, the bare
estimator when you need drop-in compatibility with code written against
Step_01_RF_for_FPI, which pickled the estimator directly.

The joblib copy is the same dict with joblib's compression, which stores the
large NumPy arrays inside the trees far more compactly than pickle does.
"""

import pickle
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, MODEL_PATH, feature_names

ESTIMATOR_PATH = DATA_DIR / "random_forest_estimator.pkl"
JOBLIB_PATH = DATA_DIR / "random_forest_model.joblib"
CARD_PATH = DATA_DIR / "model_card.txt"


def main():
    with open(MODEL_PATH, "rb") as f:
        blob = pickle.load(f)
    model = blob["model"]
    names = list(blob["feature_names"])

    if names != feature_names():
        raise AssertionError("saved feature order does not match common.feature_names()")

    with open(ESTIMATOR_PATH, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    joblib.dump(blob, JOBLIB_PATH, compress=3)

    import sklearn
    p = model.get_params()
    card = f"""FPI random forest - CSIRO BARRA-R2 / QDC-CMIP6

Files
  random_forest_model.pkl        pickle of a dict:
                                   model          RandomForestRegressor
                                   feature_names  {len(names)} names, the fit order
                                   n_soil         {blob['n_soil']}
                                   years          {blob['years'][0]}..{blob['years'][-1]}
  random_forest_estimator.pkl    pickle of the RandomForestRegressor alone
  random_forest_model.joblib     the dict again, joblib-compressed

Estimator
  sklearn            {sklearn.__version__}
  n_estimators       {p['n_estimators']}
  max_features       {p['max_features']}
  min_samples_leaf   {p['min_samples_leaf']}
  random_state       {p['random_state']}
  n_features_in_     {model.n_features_in_}

Target
  Forest Productivity Index, annual, dimensionless

Predictor order (this is the contract - X columns must be in exactly this order)
  [0:{blob['n_soil']}]    soil, static
  [{blob['n_soil']}:{len(names)}]  climate, per year: for each of hurs, hursmax,
             hursmin, pr, rsds, tasmax, tasmin - twelve monthly aggregates
             (pr summed, the rest averaged) then one annual aggregate

Use
  import pickle, numpy as np
  blob  = pickle.load(open("random_forest_model.pkl", "rb"))
  model, names = blob["model"], blob["feature_names"]
  # X: (n_cells, {len(names)}) float32, columns in `names` order, no NaN
  y = model.predict(X)

  # or, drop-in for code written against Step_01_RF_for_FPI:
  model = pickle.load(open("random_forest_estimator.pkl", "rb"))

Trained on
  {blob['years'][0]}-{blob['years'][-1]}, one row per (NLUM cell, year),
  2,086,920 rows. Soil is static and repeats down the 30 rows of a cell.

Caveat
  A random forest predicts a mean over training-set leaves and cannot
  extrapolate. Climate beyond the {blob['years'][0]}-{blob['years'][-1]} envelope
  is answered with the response at the edge of that envelope, so late-century
  high-forcing projections are conservative by construction.
"""
    CARD_PATH.write_text(card, encoding="utf-8")

    for p_ in (MODEL_PATH, ESTIMATOR_PATH, JOBLIB_PATH, CARD_PATH):
        print(f"{p_.name:32s} {p_.stat().st_size / 1e6:9.1f} MB")


if __name__ == "__main__":
    main()
