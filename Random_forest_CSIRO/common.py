"""
Shared configuration and helpers for the CSIRO-driven FPI random forest.

This pipeline is the Step_01_RF_for_FPI random forest re-fitted on a different
set of inputs:

    target      annual FPI 1985-2014          required_data/fpi/fpi_<year>.tif
    climate     BARRA-R2 daily, 7 variables   required_data/CSIRO_historical_data/
    future      QDC-CMIP6 daily, 4 SSPs       required_data/CSIRO_future_data/
    soil        83 static NLUM rasters        required_data/Soil_data/

Three things differ from Step_01_RF_for_FPI and drive the whole design:

1. The model is annual, not climatological. Step_01 fitted one 1970-2000 mean
   FPI against one 1970-2000 climate normal - a single map. Here each of the 30
   historical years is its own training sample, so the model learns how FPI
   responds to a *particular year's* weather, which is what predicting FPI for
   each future year 2035-2064 / 2070-2099 requires.

2. The climate is daily on the native AUS-11 grid (0.11 deg, lat/lon regular,
   646 x 1082, reaching well past Australia), not annual rasters already matched
   to NLUM. `Step_01_aggregate_climate.py` collapses it to 12 monthly aggregates
   per variable per year, and the 0.11 -> 0.01 deg regrid happens by bilinear
   interpolation at the point of use, never as a stored raster: one NLUM-grid
   year of all 7 variables is ~4.6 GB, and the projection walks 240 of them.

3. Soil is held constant into the future, exactly as asked - the same 83 bands
   enter both the training table and every future prediction.

Feature order is defined once here, by `climate_feature_names()` and
`soil_files()`, and both the training table and the prediction stack are built
through those functions, so the two cannot drift apart.
"""

from pathlib import Path

import numpy as np
import xarray as xr

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

STEP_DIR = Path(__file__).resolve().parent
REQUIRED = STEP_DIR / "required_data"

HIST_CLIM_DIR = REQUIRED / "CSIRO_historical_data"
FUT_CLIM_DIR = REQUIRED / "CSIRO_future_data"
SOIL_DIR = REQUIRED / "Soil_data"
FPI_DIR = REQUIRED / "fpi"

DATA_DIR = STEP_DIR / "data"
MONTHLY_DIR = DATA_DIR / "monthly_climate"      # Step_01 output
OUTPUT_DIR = STEP_DIR / "output"
PLOTS_DIR = STEP_DIR / "plots"

X_TABLE_PATH = DATA_DIR / "training_table.npz"
MODEL_PATH = DATA_DIR / "random_forest_model.pkl"

# --------------------------------------------------------------------------- #
# Periods and scenarios
# --------------------------------------------------------------------------- #

HIST_YEARS = list(range(1985, 2015))            # 30 training years
FUTURE_YEARS = list(range(2035, 2065)) + list(range(2070, 2100))
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]

# --------------------------------------------------------------------------- #
# Climate variables
# --------------------------------------------------------------------------- #

# All 7 CSIRO variables are used. `how` is the monthly reduction: rainfall is a
# flux that accumulates, everything else is a state that averages. Daily pr is
# already delivered in mm d-1 (checked on both the historical and the QDC files)
# so a monthly sum is millimetres with no unit conversion.
CLIM_VARS = {
    "hurs": "mean",       # near-surface relative humidity, %
    "hursmax": "mean",    # daily maximum relative humidity, %
    "hursmin": "mean",    # daily minimum relative humidity, %
    "pr": "sum",          # precipitation, mm d-1 -> mm month-1
    "rsds": "mean",       # surface downwelling shortwave, W m-2
    "tasmax": "mean",     # daily maximum near-surface air temperature, degC
    "tasmin": "mean",     # daily minimum near-surface air temperature, degC
}

# Crop the 646 x 1082 AUS-11 domain (lat -57.97..12.98, lon 88.48..207.4) down
# to Australia before doing anything else. The NLUM grid spans
# x 112.92..153.63, y -43.66..-10.02; the margin here is ~1 deg, comfortably
# more than the one coarse cell bilinear interpolation needs at the edge.
BBOX = dict(lat=slice(-44.8, -9.0), lon=slice(111.9, 154.7))

MONTHS = list(range(1, 13))


def climate_feature_names():
    """The 91 climate predictor names, in the fixed order the model expects.

    Per variable: 12 monthly aggregates then one annual aggregate. The annual
    term is redundant in principle - a tree could reconstruct it - but only by
    a deep chain of splits, since trees cannot add. Giving it directly is the
    cheap way to let a single split key on "a dry year" rather than on twelve
    separately-dry months.
    """
    names = []
    for var in CLIM_VARS:
        names += [f"{var}_m{m:02d}" for m in MONTHS]
        names.append(f"{var}_ann")
    return names


def soil_files():
    """The 83 static soil rasters, in a fixed sorted order.

    Every `*.tif` under Soil_data except the 11 `*_gapfill_flag_*` layers, which
    record where the provider interpolated rather than measuring - provenance
    metadata, not a soil property.
    """
    paths = sorted(
        p for p in SOIL_DIR.rglob("*.tif") if "gapfill_flag" not in p.name
    )
    if not paths:
        raise FileNotFoundError(f"no soil rasters under {SOIL_DIR}")
    return paths


def soil_feature_names():
    return [p.stem.replace("_EV_N_P_AU", "").replace("_NLUM", "") for p in soil_files()]


def feature_names():
    return soil_feature_names() + climate_feature_names()


# --------------------------------------------------------------------------- #
# File location
# --------------------------------------------------------------------------- #

def raw_climate_file(var, year, ssp=None):
    """Locate one raw daily NetCDF. `ssp=None` means the historical baseline."""
    if ssp is None:
        hits = sorted((HIST_CLIM_DIR / var).glob(f"*_{year}.nc"))
    else:
        hits = sorted((FUT_CLIM_DIR / var / ssp).glob(f"*_{year}_*.nc"))
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected 1 file for {var} {ssp or 'historical'} {year}, got {len(hits)}"
        )
    return hits[0]


def monthly_path(var, year, ssp=None):
    """Where Step_01 writes / Step_02+ read the 12-band monthly aggregate."""
    sub = "historical" if ssp is None else ssp
    return MONTHLY_DIR / sub / var / f"{var}_{sub}_{year}_monthly.nc"


def climate_jobs():
    """Every (var, year, ssp) the pipeline needs, historical and future."""
    jobs = [(v, y, None) for v in CLIM_VARS for y in HIST_YEARS]
    jobs += [(v, y, s) for v in CLIM_VARS for s in SSPS for y in FUTURE_YEARS]
    return jobs


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

METRIC_LABELS = {
    "n": "n",
    "r2": "R2 (coefficient of determination)",
    "pearson_r": "Pearson r",
    "rmse": "RMSE",
    "mae": "MAE",
    "mape": "MAPE (%)",
    "bias": "Mean bias (pred - obs)",
    "pbias": "Percent bias (%)",
    "nse": "Nash-Sutcliffe efficiency",
    "willmott_d": "Willmott index of agreement",
    "explained_variance": "Explained variance",
    "obs_mean": "Observed mean",
    "pred_mean": "Predicted mean",
    "obs_sd": "Observed SD",
    "pred_sd": "Predicted SD",
}


def regression_metrics(obs, pred):
    """The usual regression scores, on one pass over the arrays.

    `r2` and `nse` are the same formula - 1 - SSE/SST - and are reported under
    both names because the machine-learning and the hydrology/ecology
    literatures each expect their own. `explained_variance` differs from them
    only by removing the mean bias first, so a gap between the two is exactly
    the bias term.
    """
    obs = np.asarray(obs, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    err = pred - obs
    sse = float(np.sum(err ** 2))
    sst = float(np.sum((obs - obs.mean()) ** 2))

    denom = np.sum((np.abs(pred - obs.mean()) + np.abs(obs - obs.mean())) ** 2)
    nonzero = np.abs(obs) > 1e-9

    return {
        "n": int(obs.size),
        "r2": 1.0 - sse / sst if sst > 0 else np.nan,
        "pearson_r": float(np.corrcoef(obs, pred)[0, 1]),
        "rmse": float(np.sqrt(sse / obs.size)),
        "mae": float(np.mean(np.abs(err))),
        "mape": float(np.mean(np.abs(err[nonzero] / obs[nonzero])) * 100),
        "bias": float(err.mean()),
        "pbias": float(100 * err.sum() / obs.sum()) if obs.sum() != 0 else np.nan,
        "nse": 1.0 - sse / sst if sst > 0 else np.nan,
        "willmott_d": float(1.0 - sse / denom) if denom > 0 else np.nan,
        "explained_variance": float(1.0 - np.var(err) / np.var(obs)),
        "obs_mean": float(obs.mean()),
        "pred_mean": float(pred.mean()),
        "obs_sd": float(obs.std()),
        "pred_sd": float(pred.std()),
    }


# --------------------------------------------------------------------------- #
# NLUM grid
# --------------------------------------------------------------------------- #

def nlum_template():
    """A 2D float32 DataArray on the NLUM grid, used for coords and for output.

    Read lazily and from FPI rather than held at import time, so loky workers
    that re-import this module on spawn do not each pay for it.
    """
    import rioxarray as rxr

    da = rxr.open_rasterio(FPI_DIR / f"fpi_{HIST_YEARS[0]}.tif").squeeze(drop=True)
    da.attrs.pop("long_name", None)
    return da.astype(np.float32)


# --------------------------------------------------------------------------- #
# Climate -> features
# --------------------------------------------------------------------------- #

def load_monthly(var, year, ssp=None):
    """The 12-band monthly aggregate for one variable-year, on the 0.11 deg grid."""
    with xr.open_dataset(monthly_path(var, year, ssp)) as ds:
        return ds[var].load()


def annual_from_monthly(da, how):
    """Collapse 12 monthly bands to the single annual term."""
    return da.sum("month") if how == "sum" else da.mean("month")


def bilinear_weights(src, dst):
    """Index pair and upper weight for linearly interpolating `src` at `dst`.

    `src` must be 1-D and ascending. Points outside the source range are
    clipped to the edge rather than extrapolated - with the BBOX above that
    never triggers on the NLUM grid, and clipping fails loudly as a flat edge
    rather than quietly as a runaway linear extension if the box is ever
    tightened.
    """
    src = np.asarray(src, dtype=np.float64)
    dst = np.clip(np.asarray(dst, dtype=np.float64), src[0], src[-1])
    i1 = np.clip(np.searchsorted(src, dst, side="left"), 1, src.size - 1)
    i0 = i1 - 1
    w = (dst - src[i0]) / (src[i1] - src[i0])
    return i0, i1, w.astype(np.float32)


def _interp_cube(cube, src_lat, src_lon, lat, lon, pointwise):
    """Bilinear `cube` (band, lat, lon) onto points or onto a grid.

    Written out rather than handed to `DataArray.interp` for the memory
    profile. The two branches are the same interpolation but must be reached
    differently: separably on a grid, where doing the latitude pass first
    collapses the array to (band, n_lat_out, 390) before the longitude pass
    ever touches the 4,071-column axis; and by an explicit four-corner gather
    at scattered points, where that same first pass would instead expand to
    (band, n_points, 390) and blow up.
    """
    j0, j1, wy = bilinear_weights(src_lat, lat)
    i0, i1, wx = bilinear_weights(src_lon, lon)

    if pointwise:
        c00 = cube[:, j0, i0]
        c01 = cube[:, j0, i1]
        c10 = cube[:, j1, i0]
        c11 = cube[:, j1, i1]
        top = c00 * (1.0 - wx) + c01 * wx
        bot = c10 * (1.0 - wx) + c11 * wx
        return top * (1.0 - wy) + bot * wy

    rows = cube[:, j0, :] * (1.0 - wy)[None, :, None] + cube[:, j1, :] * wy[None, :, None]
    return (rows[:, :, i0] * (1.0 - wx)[None, None, :]
            + rows[:, :, i1] * wx[None, None, :])


def climate_features_at(year, ssp, lat, lon, pointwise):
    """Bilinearly interpolate every climate feature onto the requested points.

    `lat`/`lon` are 1-D. With `pointwise=True` they are paired coordinates of
    length n and the result is (91, n); with `pointwise=False` they are the axes
    of a full grid and the result is (91, len(lat), len(lon)).

    Interpolating here rather than storing NLUM-grid climate is what keeps this
    tractable: a single year of all 7 variables on NLUM is ~4.6 GB, and the
    prediction loop alone walks 240 of them.
    """
    out = []
    for var, how in CLIM_VARS.items():
        da = load_monthly(var, year, ssp)
        cube = np.concatenate(
            [da.values, annual_from_monthly(da, how).values[None]], axis=0
        ).astype(np.float32)
        out.append(_interp_cube(cube, da.lat.values, da.lon.values,
                                lat, lon, pointwise))
    return np.concatenate(out, axis=0)
