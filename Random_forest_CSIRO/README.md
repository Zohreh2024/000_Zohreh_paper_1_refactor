# Random_forest_CSIRO

Future FPI from CSIRO climate: a random forest trained on the 30 observed years
1985-2014 and applied to each future year 2035-2064 and 2070-2099 under four
SSPs.

This is `Step_01_RF_for_FPI` re-fitted on different inputs. The modelling code
is the same idea; the inputs and therefore the training design are not.

## Run order

```powershell
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_00_audit_inputs.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_aggregate_climate.py --jobs 32
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_build_training_table.py --jobs 10
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02b_export_training_netcdf.py --gridded
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_build_model.py --jobs 48
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_predict_future.py --jobs 6
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04b_export_netcdf.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_plots.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_07_scenario_diagnostic.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_06_write_report.py
```

Step_01 and Step_04 are resumable: both skip work whose output already exists,
so an interrupted run continues rather than restarting.

| Script | Purpose |
|---|---|
| `Step_00_audit_inputs.py` | Grid audit: every raster against NLUM, footprint overlap, climate coverage |
| `common.py` | Paths, the fixed feature order, bilinear regridding, metrics |
| `Step_01_aggregate_climate.py` | 1,890 daily NetCDF (~1.5 TB) -> 12 monthly values per variable-year |
| `Step_02_build_training_table.py` | One row per (cell, year), 1985-2014 -> `data/training_table.npz` |
| `Step_02b_export_training_netcdf.py` | The same table as NetCDF, flat or gridded |
| `Step_03_build_model.py` | Three cross-validation schemes, then the final fit |
| `Step_04_predict_future.py` | 240 FPI rasters + 8 window means on the NLUM grid |
| `Step_04b_export_netcdf.py` | The same projections as 8 NetCDF cubes |
| `Step_05_plots.py` | Validation and projection figures |
| `Step_07_scenario_diagnostic.py` | Land-weighted climate change per scenario-window vs the FPI response |
| `Step_06_write_report.py` | `Random_forest_CSIRO_report.docx` |
| `Step_08_scatter_hist_vs_future.py` | Observed mean FPI 1990-2022 vs the 8 projected window means: R2/RMSE/MAE |

## The design in one paragraph

`Step_01_RF_for_FPI` regressed a single 1970-2000 mean FPI map on a single
1970-2000 climate normal. Every cell contributed one row, the model saw only
spatial variation, and it therefore cannot say what FPI would be in one
particular future year. Here each of the 30 historical years is its own
training sample of every cell - 1985 climate against 1985 FPI, 1994 against
1994 - so the fit sees interannual variation directly and a year-by-year
projection is a question the model was trained to answer. Soil is held constant:
the same 83 bands repeat down the 30 rows of a cell and enter all 240 future
predictions unchanged.

## Inputs

| | |
|---|---|
| Target | `required_data/fpi/fpi_<year>.tif`, 1985-2014, 1 km NLUM |
| Historical climate | BARRA-R2 daily, 7 variables x 30 years, 0.11 deg AUS-11 |
| Future climate | QDC-CMIP6 (ACCESS-CM2 r4i1p1f1 on a BARRA-R2 baseline), 7 x 4 SSP x 60 years |
| Soil | 83 rasters from 13 properties, static, 1 km NLUM |

174 predictors: 83 soil, plus 12 monthly aggregates and one annual aggregate for
each of the 7 climate variables. Rainfall is summed, everything else averaged.

## Grid consistency, checked not assumed

`Step_00_audit_inputs.py` verified all 136 soil and FPI rasters share one grid -
3364 x 4071 at 0.01 deg, origin 112.925 / -10.015, GDA94, one CRS - including
`soil_N` and `soil_P`, whose file names lack the `_NLUM` suffix the others
carry. Soil and FPI footprints are the *same* mask, 6,956,407 cells, with zero
cells in either that are missing from the other, so no gap-filling is needed and
the projection has no holes the target does not have. Climate has 0.000% NaN
over the Australian crop and that crop strictly encloses NLUM on both axes, so
bilinear interpolation always has four real corners.

Climate is resampled, not reprojected: it is already regular lat/lon in the same
geographic coordinates as NLUM, so 0.11 -> 0.01 deg is pure interpolation with
no datum change.

## Three things worth knowing before changing anything

**The 0.11 -> 0.01 deg regrid is never stored.** One year of all 7 variables on
the NLUM grid is ~4.6 GB and the projection walks 240 of them. Climate is
bilinearly interpolated onto NLUM coordinates at the point of use, by the same
function in training and in prediction (`common.climate_features_at`).

**Cross-validate by year, not at random.** Every cell contributes 30 rows that
share all 83 soil values, so a random split puts 1994 and 1995 of the same cell
on opposite sides and mostly measures memorisation. `Step_03` scores three
schemes - random 5-fold, spatial 2-degree block CV, and year-group CV - and the
year-group number is the one to quote, because projecting 2035-2099 is exactly
the act of predicting years the model never saw.

**The scenario ordering is not monotonic, and that is the forcing's doing.**
Projected FPI tracks land-weighted humidity and rainfall change at r = +0.97
across the eight scenario-windows, and ACCESS-CM2 `r4i1p1f1` under ssp245 in
2070-2099 is barely drier than the baseline (rainfall -0.8%) while ssp126 over
the same years is much drier (-9.8%). Temperature *is* ordered by forcing, but
this model keys on humidity and rainfall, so it inherits their disorder. Claim
"FPI declines in every scenario, strongly late-century under high forcing";
do not claim a forcing-response ordering in 2035-2064. See `Step_07`.

**A random forest cannot extrapolate.** It predicts a mean over training-set
leaves, so a late-century climate hotter than anything in 1985-2014 is answered
with the response at the edge of the training envelope. The high-forcing,
late-window projections are conservative by construction; the effect is
strongest in ssp585 2070-2099.

## Outputs

```
data/monthly_climate/<historical|ssp>/<var>/<var>_<set>_<year>_monthly.nc
data/training_table.npz            2,086,920 x 174 (what Step_03 reloads)
data/X_train.nc, y_train.nc        the same table as NetCDF, (sample, feature)
data/X_train_gridded.nc, y_train_gridded.nc   (year, feature, y, x), --gridded only
data/random_forest_model.pkl       model + its feature order
data/cv_metrics.csv                per scheme and per fold
data/cv_metrics_by_year.csv        year-group CV, year by year
data/oof_<scheme>.npz              out-of-fold prediction for every row
data/feature_importances.csv
data/scenario_climate_diagnostic.csv  land-weighted climate per scenario-window
data/scenario_climate_vs_fpi.csv      that climate change vs the FPI response
output/fpi_<ssp>_<year>.tif        240 rasters, float32, LZW, NLUM/GDA94
output/fpi_<ssp>_<window>_mean.tif 8 window means
output/netcdf/fpi_<ssp>_<period>.nc   fpi(year, lat, lon) + fpi_mean(lat, lon)
output/netcdf/fpi_all_period_means.nc the 8 window means in one file
output/domain_mean_fpi_by_year.csv
plots/*.png
Random_forest_CSIRO_report.docx
```
