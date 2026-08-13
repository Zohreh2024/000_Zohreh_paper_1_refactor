# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Python environment

**Always use the `JinzhuLuto` conda environment.** Never use `base`, and never call a
bare `python` — the machine has ~30 conda envs and no env is auto-activated
(`auto_activate_base` is `false`), so a bare `python` resolves to
`C:\Program Files\Python36\python.exe`, which is the wrong interpreter.

```
Name:   JinzhuLuto
Path:   C:\ProgramData\Anaconda3\envs\JinzhuLuto
Python: 3.8.19
```

### Running code

Run every script, module, and one-off snippet through `conda run`:

```powershell
conda run -n JinzhuLuto python <script.py> [args]
conda run -n JinzhuLuto python -c "import rasterio; print(rasterio.__version__)"
conda run -n JinzhuLuto pip list
```

**If `-n JinzhuLuto` fails with `EnvironmentLocationNotFound`, use the full prefix
path instead** — some shells on this machine put *miniconda3* on `PATH` rather than
Anaconda3, and `~/.condarc` sets `envs_dirs` to `F:\Zohreh\conda_env` and
`C:\ProgramData\Anaconda3\envs\zoenv`, neither of which contains `JinzhuLuto`:

```powershell
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python <script.py>
```

`-p` takes an absolute prefix and ignores `envs_dirs`, so it works from any shell.

Use `--no-capture-output` when the command has live progress output (`tqdm` bars,
long downloads) — otherwise `conda run` buffers stdout until the process exits:

```powershell
conda run --no-capture-output -n JinzhuLuto python Step_0_download_data\download_worldclim_cmip6.py
```

Installing packages goes through the same env:

```powershell
conda install -n JinzhuLuto <pkg>
conda run -n JinzhuLuto pip install <pkg>
```

## Repository layout

Numbered step directories run in order; each is a self-contained stage of the
pipeline.

| Path | Purpose |
|---|---|
| `Step_0_download_data/` | Fetch raw rasters, then clip/reproject them to NLUM |
| `Step_0b_published_lambda/` | Fetch DCCEEW's PUBLISHED lambda + `Original_M_2004` |
| `Step_1_RF_for_FPI/` | Random forest predicting future FPI from soil + climate |
| `REVISED_ORIGINAL_M_2004/` | Future M' via Eq. (3) on the `Original_M_2004` footing |
| `Comparison_between_lambda_and_ratio/` | Why the two lambda layers differ |
| `Validation_temperature_projections/` | `avgAirTemp` = (tmin+tmax)/2, + validation vs ANUClimate |
| `Validation_rainfall_projections/` | `rainFall` checks vs ANUClimate / BARRA-R2 |
| `Validation_rainfall_projections/BOM_vs_ANUClimate_2024/` | BOM AGCD vs ANUClimate, 2024, both on NLUM |
| `Validation_open_pan_projections/` | `openPanEvap` checks vs ANUClimate |
| `Paper_reading/` | `paper_revised_M.pdf`, Roxburgh et al. (2019) |
| `Data/Raw/` | Untouched downloads, one sub-directory per variable |
| `Data/Processed/` | NLUM-matched output, mirrors `Data/Raw/`'s sub-directories |
| `Data/Input_for_FullCAM/` | Final FullCAM inputs, one sub-directory per variable |
| `Data/NLUM_Mask/` | `NLUM_2010-11_mask.tif`, the reprojection template |

`Data/Input_for_FullCAM/<var>/<SSP>/<var>_<SSP>_<period>.nc` (+ `.tif`) is the
shared output convention for every FullCAM variable — `band`/`lat`/`lon` dims,
12 bands, EPSG:4283, NaN outside the NLUM mask. Periods are `2020-2040`,
`2041-2060`, `2061-2080`, `2081-2100`; the first spans 21 years and the rest 20,
which is deliberate and matches `forestProdIx`.

## Two lambdas — read this before touching M'

Roxburgh et al. (2019) Eq. (3) is `M' = lambda * M`. **Lambda is only valid
against the exact `M` it was divided by**, and this repo contains two different
layers that have both been called lambda:

| layer | definition | pair it with |
|---|---|---|
| `Data/Processed/maxAbgM_v2/transfer_Eq1M_to_NewM_1970_2002.tif` | `New_M_2019 / Eq1(FPI 1970-2002)` | Eq. (1) M from `Step_1/Step_06` |
| `Step_0b_published_lambda/output/lambda_published.tif` | `New_M_2019 / Original_M_2004` (DCCEEW, the paper's actual lambda) | `Original_M_2004`-footing M from `REVISED_ORIGINAL_M_2004/Step_06` |

Crossing them inflates `M'` by ~46%, because `Eq1(FPI 1970-2002)` overstates
`Original_M_2004` by a median factor of 1.46 (31.44 vs 18.65 t DM ha-1). Eq. (1)
is the relationship *reported* in the paper, not the Richards & Brack (2004)
procedure that produced the layer FullCAM ships.

Both routes reach the same answer (r = 0.9997) — the legacy one because Eq. (1)
cancels between the transfer factor and Step_06, the revised one because every
intermediate sits on the `Original_M_2004` footing. Prefer the revised route in
writing, since it is citable as the paper's own equation. Full reasoning:
`Comparison_between_lambda_and_ratio/WHY_THEY_DIFFER.md` and
`REVISED_ORIGINAL_M_2004/WHY_THIS_REVISION.md`.

`transfer_Eq1M_to_NewM_1970_2002.tif` was called `lambda_1970_2002.tif` until
Aug 2026; it was renamed because the name was the cause of the confusion.

Scripts in `Step_0_download_data/`:

| Script | Purpose |
|---|---|
| `download_worldclim_cmip6.py` | CLI. ACCESS-CM2 future scenarios, 64 multi-band tif |
| `download_worldclim_historical.py` | CLI. WorldClim 2.1 historical 1970-2000, 4 zips -> 55 tif |
| `download_fpi.py` | CLI. Forest Productivity Index, 37 map-sheet tiles from data.gov.au |
| `download_CSIRO_historical_data.py` | CLI. BARRA-R2 historical baseline 1985-2014 from CSIRO DAP csiro:64206 |
| `reproject_match_NLUM.py` | Plain script, run top-to-bottom. Clips/reprojects/fills every variable |
| `mosaic_match_fpi_NLUM.py` | Plain script. Mosaics the 37 FPI tiles per year, then matches to NLUM |

The three WorldClim/FPI downloaders share the resumable `download()` from
`download_worldclim_cmip6.py` — import it rather than writing new download logic.
`download_CSIRO_historical_data.py` carries its own copy because CSIRO DAP serves
bytes from pre-signed S3 URLs: the signature covers GET only (a HEAD is 403, so
the expected size comes from the API manifest, not `Content-Length`) and expires
after 48 h, so a long download re-signs mid-flight from the per-file endpoint.

Scripts in `Step_1_RF_for_FPI/` (run in order):

| Script | Purpose |
|---|---|
| `Step_01_organise_input_files.py` | Build `data/X_data.nc` (67 bands) and `data/Y_data.nc` |
| `Step_02_build_model.py` | Fit the random forest, write `data/random_forest_model.pkl` |
| `Step_03_prediction.py` | Predict FPI for each scenario x period -> `output/*.tif` |
| `Step_06_Calculating_Future_MAGB.py` | Eq. (1) M from future FPI (Eq. (1) footing) |
| `Step_07_applying_lambda_for_future_M.py` | x the transfer factor -> `maxAbgMF` (delta-change route) |

Scripts in `Step_0b_published_lambda/` and `REVISED_ORIGINAL_M_2004/`:

| Script | Purpose |
|---|---|
| `get_published_lambda.py` | Download + NLUM-match `Ratio_OriginalM_to_NewM` and `Original_M_2004`; self-verifies Eq. (3) and the lambda==1 plateau, exits non-zero if either fails |
| `Step_06_future_M_original2004.py` | Future M = `Original_M_2004 x Eq1(FPI_fut)/Eq1(FPI_hist)` |
| `Step_07_apply_published_lambda.py` | Eq. (3) with the published lambda, + cross-check vs the legacy route |

## Rainfall is QDC-CMIP6 — read this before touching `rainFall`

`Data/Raw/rainFall/` is **not** raw GCM output. It is CSIRO's QDC-CMIP6
application-ready dataset (`Doc/Csiro_data_report.pdf`, Climate Innovation Hub
Technical Note 5), and the originals at
`N:/Current-Users/ZOHREH-KALAHROUDI/rainfall_FOLDER_21_april2026/` state the
method in the filename:

```
qdc-multiplicative-monthly-q100-linear-maxaf5-annual-change-matched
    _BARRA-R2-baseline-1985-2014_model-baseline-1985-2014
```

ACCESS-CM2 `r4i1p1f1`, quantile changes applied **multiplicatively to observed
BARRA-R2 data** from 1985-2014. Three consequences that are easy to get wrong:

- **Each "future year" is an observed year rescaled.** `2035` is observed 1985,
  `2064` is observed 2014, and the late window restarts, so `2070` is observed
  1985 again. Verified: correlating annual totals year-for-year between the two
  windows gives r = +0.979 to +0.996. The interannual variability in the
  projections is observed weather, not model weather.
  **Anchor each window on its own start** — the windows are 35 years apart, so
  a single mod-30 cycle counted from 2035 maps 2070 to 1990 and silently shifts
  the whole late window by five years:

  ```
  observed(y) = 1985 + ((y - 2070) mod 30)    for y >= 2070 (incl. 2100)
  observed(y) = 1985 + ((y - 2035) mod 30)    otherwise
  ```
- **Only 2035-2064 and 2070-2099 exist.** Everything else in the delivered
  series is gap-fill. Technical Note §4.2 says the two windows were separated
  deliberately "so that users do not attempt to join them".
- **2010-2014 are BARRA-R2 observations**, not CMIP6 historical output. They are
  byte-identical across scenarios because no change factor has been applied yet.
  Verified twice: r = +0.9878 against ANUClimate on de-seasonalised anomalies,
  and r = **1.0000** against BARRA-R2 monthly `pr` reconstructed independently
  (`pr × days × 86400`, bilinear to NLUM — domain mean 17.68 mm both, 2013-07).

**Two observational bases.** QDC was applied to BARRA-R2; FullCAM's historical
rainfall is ANUClimate. Over 1985-2014 they differ by +3.0% annually (494.3 vs
479.7 mm) and far more seasonally — BARRA-R2 is +18% in November, +16% in
October, −6% in March. That is a product difference, not model error, and no
adjustment to the projections removes it.

**The two products are NOT homogeneous across the QDC baseline.** ANUClimate
runs 8-18% drier than BARRA-R2 through 1985-1995, then agrees within ~3% from
1996 on:

| year | 1985 | 1987 | 1990 | 1993 | 1996 | 2000 | 2005 | 2010 | 2014 |
|---|---|---|---|---|---|---|---|---|---|
| ANUClim / BARRA-R2 | 0.856 | 0.819 | 0.901 | 0.952 | 0.986 | 1.034 | 1.001 | 1.042 | 0.982 |

So the +3.0% full-baseline gap is driven almost entirely by 1985-1995, and a
delta-change transfer calibrated on the full baseline carries that early-period
artefact into every future year. If the transfer is ever refined, calibrate it
on a homogeneous sub-period (1996-2014) rather than 1985-2014.

**Never interpolate rainfall in mm.** The delivered series does, and it produced
negative rainfall in 2100 (3.7-4.1% of cell-months, to −29 mm in SSP585) and a
dry bias in 2015-2034 from anchoring on two individual dry years. Interpolate
the dimensionless change factor instead: it is bounded below by zero and varies
smoothly with warming. Extrapolating from three years is worse still — a 3-point
OLS through 2097-2099 gives 21% negative cell-months, to −813 mm.

Two routes now exist, and they are not interchangeable:

| output | base | how gaps are filled |
|---|---|---|
| `Data/Input_for_FullCAM/rainFall/` | BARRA-R2 | as delivered — mm-interpolated 2015-2034 and 2065-2069; 2100 rebuilt as the 2097-2099 mean |
| `Data/Input_for_FullCAM/rainFall_anuclim/` | **ANUClimate** | change factor interpolated across the gaps only; CSIRO's windows used unchanged; nothing extrapolated |

Prefer `rainFall_anuclim` — it sits on the same product FullCAM uses, so the
observational base cancels.

Scripts in `Validation_rainfall_projections/` (run in order):

| Script | Purpose |
|---|---|
| `Step_00_rebuild_2100.py` | Replace the negative-carrying 2100 layer with the 2097-2099 mean -> `Data/Processed/rainFall/` |
| `Step_00b_fetch_ANUClimate_monthly.py` | ANUClimate v2-0 monthly rain 1985-2024, 480 files, resumable |
| `Step_00c_fetch_BARRA_R2_baseline.py` | BARRA-R2 monthly `pr` 1985-2014 from NCI `ob53`, 360 files (~1.3 MB each) |
| `Step_01_validate_rainFall.py` | Audit all 364 files: grid, NaN, units, provenance |
| `Step_02_period_averages_for_FullCAM.py` | The four FullCAM periods on the delivered BARRA-R2 series |
| `Step_03_compare_vs_ANUClimate_2024.py` | 2020-2040 vs observed 2024 — a units check, not a validation |
| `Step_04_validate_vs_historical_2010_2014.py` | BARRA-R2 vs ANUClimate, 2010-2014 — two observational products |
| `Step_05_climatology_2035_2064_vs_observed.py` | Projected 30-year climatology vs the observed normal |
| `Step_06_qdc_change_factors.py` | Recover `f = QDC climatology / BARRA-R2 1985-2014` per cell per month |
| `Step_07_apply_factors_to_ANUClimate.py` | `f x ANUClimate`, every year 2015-2100, then the four periods |
| `Step_08_scatter_vs_ANUClimate_normal.py` | Scatter both bases against the observed 1985-2014 normal, r2/RMSE/MAE |

Step_08 quantifies what choosing the wrong base costs, on the annual total
averaged over all four scenarios and periods:

| base | r2 | RMSE | MAE |
|---|---|---|---|
| `rainFall_anuclim` | **0.975** | **64.4 mm** | **46.6 mm** |
| `rainFall` (delivered) | 0.863 | 141.7 mm | 83.5 mm |

The delivered series has slightly *smaller* mean bias (24.7 vs 31.5 mm) while
being far worse spatially — its continental average happens to land close. Quote
r2 and bias together; either alone misleads here.

Note the top row of `scatter_vs_normal_annual_by_base.png` is not an independent
validation: `rainFall_anuclim` **is** `f x ANUClimate`, so scattering it against
ANUClimate measures the change factor, and a tight band just below 1:1 is the
expected result. The informative comparison is between the two rows, which
isolates the product difference because both carry the same change signal.

Scripts in `Validation_rainfall_projections/BOM_vs_ANUClimate_2024/`:

| Script | Purpose |
|---|---|
| `Step_01_prepare_on_NLUM.py` | Audit both products, reproject/fill/mask to NLUM -> `nlum_aligned/*.tif` + `.nc` |
| `Step_02_scatter_BOM_vs_ANUClimate.py` | Monthly + annual hexbin scatters, difference map, stats |

**Two gridded observational products, not a validation.** BOM AGCD
(`Data/Raw/Rainfall_BOM_2024/`, 0.05 deg) and ANUClimate v2-0 (0.01 deg) both
interpolate the same ~4000 Bureau rain gauges, so agreement is expected and the
scatter measures interpolation method, not measurement error. For 2024 they
agree almost exactly in the aggregate — annual domain mean 595.3 mm both,
difference −0.1 mm (−0.0%), annual r2 0.982, monthly r2 0.92–0.99 — while
disagreeing locally: only 51.5% of cells fall within 5% of each other, p1–p99 of
the annual difference is −203 to +145 mm.

Three traps, all handled in `Step_01`:

- **ANUClimate's ocean sentinel is −999.0, not NaN** (52% of its cells). It must
  become NaN *before* resampling or bilinear blends −999 into coastal cells.
- **BOM AGCD has no land mask at all** — zero NaN, the interpolated surface just
  continues over the ocean (the SW corner, far off WA, reads 22.6 mm for
  January). Nothing needs filling, but its coastal cells rest on no gauge.
- **Neither grid is a crop of NLUM.** Measured offsets from NLUM cell centres:
  BOM 0.40 cells, ANUClimate **0.50** — ANUClimate's centres (112.005 + 0.01k,
  −9.005 − 0.01k) land exactly on NLUM's cell edges, so despite sharing 0.01 deg
  it is a 2x2 average, not a copy. Cropping it by index instead is wrong by up
  to 145 mm. NLUM's transform *prints* as 112.92 / −10.02 only because
  rasterio's `Affine.__repr__` rounds to 2 dp; the centres are 112.93 / −10.02.

Scripts in `Validation_temperature_projections/` (run in order):

| Script | Purpose |
|---|---|
| `Step_01_check_inputs.py` | Audit all 728 tmin/tmax files: NLUM grid, GDA94, Celsius, 12 months |
| `Step_02_build_avgAirTemp.py` | `avgAirTemp = (tasmin + tasmax) / 2`, 364 scenario-years |
| `Step_03_period_averages.py` | The four FullCAM periods, `.nc` + `.tif` |
| `Step_04_fetch_ANUClimate_tavg_2024.py` | Observed `tavg` 2024 from NCI THREDDS |
| `Step_05_scatter_vs_ANUClimate_2024.py` | 2020-2040 vs observed 2024: r2, RMSE, MAE, bias, NSE |

`Data/Raw/Temperature/Temperature_<ssp>/{tmin,tmax}/` holds the CSIRO-derived
monthly `tasmin`/`tasmax`, 2010-2100, **already NLUM-matched and already
converted K -> Celsius** by the upstream step. No further unit conversion
belongs downstream: Celsius is an interval scale, so `(tmin + tmax) / 2` is
valid on it directly. The `units` attribute is spelled `degC` on some files and
`deg_C` on others, and is absent on 208 of the 728 — the same unit either way,
so unit checks fall back to the value range (Celsius sits near 0-45, Kelvin
near 300).

`Data/Raw/` sub-directories and their contents:

| Directory | Contents |
|---|---|
| `bioc/` | CMIP6 **future** bioclimatic, 16 files x 19 bands |
| `prec/` | CMIP6 **future** precipitation, 16 files x 12 bands |
| `tmax/` | CMIP6 **future** maximum temperature, 16 x 12 bands |
| `tmin/` | CMIP6 **future** minimum temperature, 16 x 12 bands |
| `hist_bio/` | WorldClim **historical** bioclimatic, 19 single-band files |
| `hist_prec/` | WorldClim **historical** precipitation, 12 single-band files |
| `hist_tmax/` | WorldClim **historical** maximum temperature, 12 files |
| `hist_tmin/` | WorldClim **historical** minimum temperature, 12 files |
| `fpi/<tile>/` | Forest Productivity Index, 37 tiles x 53 yearly rasters |
| `maxAbgM_v1/` | `Original_M_2004`, `Ratio_OriginalM_to_NewM` (DCCEEW v1.0) |
| `maxAbgM_v2/` | `New_M_2019` (DCCEEW v2.0) |
| `soil_N/` | Soil total nitrogen, 6 depth slices |
| `soil_P/` | Soil phosphorus, 6 depth slices |
| `data_for_openPan/` | Inputs for the openPan step |
| `Rainfall_BOM_2024/BOM_rainfall_2024/` | BOM AGCD monthly rainfall 2024, 12 files at 0.05 deg |
| `CSIRO_historical_data/<var>/` | BARRA-R2 historical baseline, **daily** 1985-2014 on the native AUS-11 (~11 km) grid — 9 vars x 30 years, 109 GB. This is the observational baseline the QDC change factors in `Data/Raw/rainFall/` were applied to. Full detail: `CLAUDE_CSIRO_data.md` |
| `_worldclim_zips/`, `_fpi_zips/` | Download caches; safe to delete once extracted |

**Historical vs future are separate directories on purpose.** Training uses
historical, prediction uses future, and both must be clipped/reprojected/filled
identically or the model is fitted and applied on different footings. Note the
variable code differs between products: historical bioclim is `bio`, CMIP6
bioclim is `bioc`.

**Every FPI zip contains identically named rasters** (`1970_001.tif` ...
`2022_001.tif`) with no tile prefix, so each tile must extract into its own
`fpi/<tile>/` sub-directory or the 37 tiles overwrite one another.

## Conventions

- **Never rename downloaded files.** Raw rasters keep the provider's original
  file name (e.g. `wc2.1_30s_bioc_ACCESS-CM2_ssp245_2021-2040.tif`) so they stay
  traceable to the source.
- **`Data/Raw/` sub-directories are named for the provider's variable code**, so
  no name mapping is needed anywhere in the pipeline — WorldClim's `bioc` lives
  in `Data/Raw/bioc/`, `tmin` in `Data/Raw/tmin/`, and so on.
- **Raw data is read-only.** Never write derived output into `Data/Raw/` — each
  step writes to its own output location.
- Downloads are large (single WorldClim rasters run 5–22 GB). Prefer resumable,
  skip-if-present logic over re-fetching, and check `Data/Raw/` before downloading.
- `Data/` lives on the `N:` mapped drive, which resolves to the UNC path
  `\\shares.deakin.edu.au\school-les-m\Planet-A\...`. Python's `Path.resolve()`
  expands `N:` to that UNC form — this is the same location, not an error.
- Parallel work uses `joblib` with `backend="threading"` for I/O-bound tasks —
  **except anything that reads or writes NetCDF/HDF5 in bulk.** `netCDF4-python`
  serialises every HDF5 call behind a module-global lock, so threads take turns
  inside the library and do not overlap I/O at all. Measured on this share,
  reading six ~166 MB files:

  | | throughput |
  |---|---|
  | 1 file, serial | 29 MB/s |
  | 6 threads | 36 MB/s |
  | 6 processes | 116 MB/s |

  Use `backend="loky"` for those steps. Windows spawns rather than forks, so
  every worker re-imports the module: put the driver behind
  `if __name__ == "__main__"` or the workers re-run the whole pipeline, and load
  the NLUM mask lazily per process rather than at import time. See
  `Validation_temperature_projections/Step_02_build_avgAirTemp.py`, which moves
  ~181 GB and is hours faster this way. Downloads are genuinely network-bound
  and stay on `threading`.

## Data sources

- WorldClim 2.1 CMIP6 30s (future), GCM `ACCESS-CM2`:
  https://www.worldclim.org/data/cmip6/cmip6_clim30s.html
  Files served from `https://geodata.ucdavis.edu/cmip6/30s/`
- WorldClim 2.1 historical 30s (1970-2000):
  https://www.worldclim.org/data/worldclim21.html
  Files served from `https://geodata.ucdavis.edu/climate/worldclim/2_1/base/`
- Forest Productivity Index v1.0 (Sept 2024), DCCEEW, 1970-2022 at ~1 km GDA94:
  https://data.gov.au/data/dataset/forest-productivity-index-version-1-0-sept-2024-release
  Resource URLs are read from the CKAN API, not hard-coded, because the portal
  can re-issue resource UUIDs.
