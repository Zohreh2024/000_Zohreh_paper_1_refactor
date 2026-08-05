"""
Fit the random forest that maps soil + climate predictors to FPI.

Adapted from Refactor_JZ/Step_02_build_modely.py. Logic is unchanged; paths are
now resolved relative to this script rather than the current working directory,
so it can be run from anywhere.

Reads  data/X_data.nc, data/Y_data.nc   (written by Step_01)
Writes data/random_forest_model.pkl
"""

import pickle
from pathlib import Path

import numpy as np
import xarray as xr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DATA_DIR = Path(__file__).resolve().parent / "data"
X_PATH = DATA_DIR / "X_data.nc"
Y_PATH = DATA_DIR / "Y_data.nc"
MODEL_PATH = DATA_DIR / "random_forest_model.pkl"

DOWNSAMPLE = 5          # take every Nth cell in x and y
TRAIN_SIZE = 0.8
N_ESTIMATORS = 64       # a multiple of N_JOBS, so every worker gets equal work
RANDOM_STATE = 42

# Tree fitting is embarrassingly parallel and sklearn's default (None) uses a
# single core - the first run took ~1,210 CPU-seconds pinned to one thread. The
# box has 128 physical / 256 logical cores, so 32 is a modest share.
# Does not change the model: random_state keeps results reproducible.
N_JOBS = 32


# --------------------------------------------------------------------------- #
# Load and reshape
# --------------------------------------------------------------------------- #

X_ds = xr.open_dataset(X_PATH)["data"]
Y_ds = xr.open_dataset(Y_PATH)["data"].expand_dims({"band": ["Y"]}, axis=0)

X_ds_downsample = X_ds.isel(x=slice(None, None, DOWNSAMPLE), y=slice(None, None, DOWNSAMPLE))
Y_ds_downsample = Y_ds.isel(x=slice(None, None, DOWNSAMPLE), y=slice(None, None, DOWNSAMPLE))

# Reshape to 2D arrays for model fitting
X_stack = X_ds_downsample.stack(cell=("x", "y")).reset_index("cell").transpose("cell", "band")
Y_stack = Y_ds_downsample.stack(cell=("x", "y")).reset_index("cell").transpose("cell", "band")

# Drop cells outside AUS (NaN in any predictor) and cells with infinite FPI.
cells_in_AUS = np.logical_not(np.isnan(np.sum(X_stack.values, 1)))
cells_not_inf = np.logical_not(np.isinf(np.sum(Y_stack.values, 1)))
keep = cells_in_AUS & cells_not_inf

X_sel = X_stack.sel(cell=keep)
Y_sel = Y_stack.sel(cell=keep)

print(f"cells total      : {X_stack.sizes['cell']:,}")
print(f"cells kept       : {int(keep.sum()):,}")
print(f"  dropped NaN X  : {int((~cells_in_AUS).sum()):,}")
print(f"  dropped inf Y  : {int((~cells_not_inf).sum()):,}")


# --------------------------------------------------------------------------- #
# Fit
# --------------------------------------------------------------------------- #

X_train, X_test, Y_train, Y_test = train_test_split(
    X_sel.values,
    Y_sel.values,
    train_size=TRAIN_SIZE,
    random_state=RANDOM_STATE,
)

model = RandomForestRegressor(
    n_estimators=N_ESTIMATORS,
    random_state=RANDOM_STATE,
    n_jobs=N_JOBS,
)
model.fit(X_train, Y_train.ravel())

y_pred = model.predict(X_test)
print(f"\nModel R^2: {r2_score(Y_test, y_pred):.4f}")
print(f"Model Mean Squared Error: {mean_squared_error(Y_test, y_pred):.4f}")


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(MODEL_PATH, "wb") as f:
    pickle.dump(model, f)

print(f"wrote {MODEL_PATH}")
