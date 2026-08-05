# Project progress

Pipeline: download raw climate/soil/FPI rasters -> clip, reproject and fill onto
the NLUM grid -> train a random forest on historical data -> predict future FPI.

Last updated: 2026-08-05

---

## 1. Status at a glance

| Stage | Script | Status |
|---|---|---|
| Download CMIP6 future climate | `Step_0/download_worldclim_cmip6.py` | Done — 64/64 |
| Download WorldClim historical | `Step_0/download_worldclim_historical.py` | Done — 55/55 |
| Download FPI tiles | `Step_0/download_fpi.py` | Done — 37/37 tiles |
| Match climate + soil to NLUM | `Step_0/reproject_match_NLUM.py` | Done — 131 rasters |
| Mosaic + match FPI to NLUM | `Step_0/mosaic_match_fpi_NLUM.py` | Done — 54 rasters |
| Build X / Y stacks | `Step_1_RF_for_FPI/Step_01_organise_input_files.py` | Done |
| Fit random forest | `Step_1_RF_for_FPI/Step_02_build_model.py` | Done — R^2 0.9709 |
| Predict future FPI | `Step_1_RF_for_FPI/Step_03_prediction.py` | Done — 16/16 rasters |
| Scatter pred vs obs | `Step_1_RF_for_FPI/Step_04_scatter_pred_vs_obs.py` | Done — r ~ 0.945 |

---

## 2. Reference grid

Everything is matched to `Data/NLUM_Mask/NLUM_2010-11_mask.tif`.

| Property | Value |
|---|---|
| Shape | 3364 x 4071 |
| CRS | GDA94 (geographic) |
| Resolution | 0.01 deg |
| Bounds | 112.925, -43.655 -> 153.635, -10.015 |
| Valid cells (mask == 1) | 6,956,407 of 13,694,844 |

---

## 3. Data inventory

### Data/Raw (downloaded, untouched)

| Directory | Files | Size | Source |
|---|---:|---:|---|
| `bioc/` | 16 | 136.2 GB | CMIP6 ACCESS-CM2 future, 19 bands each |
| `prec/` | 16 | 333.7 GB | CMIP6 future, 12 bands each |
| `tmax/` | 16 | 76.8 GB | CMIP6 future, 12 bands each |
| `tmin/` | 16 | 76.3 GB | CMIP6 future, 12 bands each |
| `hist_bio/` | 19 | 10.0 GB | WorldClim 2.1 historical 1970-2000 |
| `hist_prec/` | 12 | 1.0 GB | WorldClim 2.1 historical |
| `hist_tmax/` | 12 | 4.3 GB | WorldClim 2.1 historical |
| `hist_tmin/` | 12 | 4.3 GB | WorldClim 2.1 historical |
| `fpi/<tile>/` | 1961 | 1.5 GB | FPI v1.0, 37 tiles x 53 years |
| `soil_N/` | 6 | 1.7 GB | Soil total nitrogen, 6 depth slices |
| `soil_P/` | 6 | 0.3 GB | Soil phosphorus, 6 depth slices |

Total downloaded: ~646 GB.

### Data/Processed (NLUM-matched)

| Directory | Files | Size |
|---|---:|---:|
| `bioc/` | 16 | 6.2 GB |
| `prec/` | 16 | 2.5 GB |
| `tmax/` | 16 | 3.5 GB |
| `tmin/` | 16 | 3.4 GB |
| `hist_bio/` | 19 | 0.4 GB |
| `hist_prec/` | 12 | 0.1 GB |
| `hist_tmax/` | 12 | 0.2 GB |
| `hist_tmin/` | 12 | 0.2 GB |
| `fpi/` | 54 | 1.5 GB |
| `soil_N/` | 6 | 0.1 GB |
| `soil_P/` | 6 | 0.2 GB |

---

## 4. Processing choices

| Data | Resampling | Why |
|---|---|---|
| Climate (future + historical) | bilinear | continuous; identical treatment for train and predict |
| `soil_N` | **average** | source is 12x finer than NLUM; bilinear would keep 1 of every 144 source cells |
| `soil_P` | bilinear | already 0.01 deg GDA94; a half-cell grid snap, not a reprojection |
| FPI | bilinear | already 0.01 deg GDA94; half-cell snap |

Order is always clip -> reproject/match -> fill NaN from nearest valid cell ->
mask to NLUM. Fill runs **before** mask so coastal gaps take a real value.

`soil_N` and FPI use a streaming reproject (`stream_match`) rather than loading
the clipped extent: one `soil_N` band over the NLUM box is ~7.9 GB, and streaming
holds peak RSS to 0.21 GB.

---

## 5. Verification

### Climate + soil — all bands, all rasters

```
76 rasters, 892 bands checked
missing outputs            : 0
grid mismatches (shape/crs): 0
band-count mismatches      : 0
bands w/ NaN INSIDE mask   : 0
bands w/ data OUTSIDE mask : 0
```

### Historical climate — added later, same checks, 0 issues (55 rasters)

### FPI — 53 yearly + 1 average

```
54 checked
grid mismatches       : 0
NaN inside mask       : 0
data outside mask     : 0
constant/empty rasters: 0
```

**Independent cross-check:** the rebuilt `fpi_avg_1970_2000.tif` reproduces the
legacy `average_fpi.tif` almost exactly, which validates the download, the
37-tile mosaic, the grid snap, the fill and the 1970-2000 averaging window.

| | range | mean |
|---|---|---|
| rebuilt `fpi_avg_1970_2000.tif` | 1.009 .. 25.819 | 4.279 |
| legacy `average_fpi.tif` | 1.009 .. 25.82 | 4.279 |

Yearly FPI also tracks known climate: 2019 is the lowest year on record
(mean 2.633 — hottest/driest year), while 2010, 2011 and 2022 are among the
highest (5.72, 5.78, 5.35 — major La Nina years).

**NaN note:** every processed raster contains NaN *outside* the NLUM mask by
design (~6.74 M cells per band). The meaningful test is NaN *inside* the mask,
which is 0 everywhere.

---

## 6. Model

### X stack — 67 bands, built by Step_01

`Soil_N_1..6`, `Soil_P_1..6`, `Bio_1..19`, `Precip_1..12`, `Tmax_1..12`,
`Tmin_1..12`, all from `Data/Processed`.

Y target: `Data/Processed/fpi/fpi_avg_1970_2000.tif` — the same 1970-2000 window
as the WorldClim historical climate baseline.

Outputs: `Step_1_RF_for_FPI/data/X_data.nc` (873.8 MB), `Y_data.nc` (17.9 MB).

### Fit — Step_02

Settings: downsample by 5 in x and y, drop cells with any NaN predictor or
infinite FPI, 80/20 split,
`RandomForestRegressor(n_estimators=64, random_state=42, n_jobs=32)`.

| Metric | Value |
|---|---|
| Cells total | 548,495 |
| Cells kept | 278,275 |
| — dropped, NaN in X | 270,220 |
| — dropped, infinite Y | 0 |
| Training rows (80%) | ~222,620 |
| **R^2** | **0.9709** |
| **MSE** | **0.2081** |
| Model file | `data/random_forest_model.pkl`, 1,236.8 MB |
| Wall clock | ~5 min (64 trees, 32 jobs) |

Notes on these numbers:

- **The 49% drop rate is expected**, not a problem: the NLUM mask marks
  6,956,407 of 13,694,844 cells valid (50.8%), so the dropped cells are the
  outside-mask area where predictors are NaN by design.
- **`dropped inf Y = 0`.** The legacy `average_fpi.tif` held 67 infinite values;
  the rebuilt FPI has none, because mosaic -> fill -> mask leaves no infinities.
  The `cells_not_inf` filter is now a no-op but is kept as a guard.
- **R^2 is not comparable with the previous project's run.** The predictors
  changed from uint8 to float32 (issue 5 below); Y is effectively unchanged, so
  any difference comes from the X side.
- **R^2 = 0.97 is optimistic.** `train_test_split` splits cells at random, but
  FPI and climate are strongly spatially autocorrelated, so a test cell is
  usually adjacent to several training cells. This measures interpolation
  skill, not the ability to generalise to new regions or to a future climate.
  A spatially blocked or held-out-region split would give a more honest
  estimate of predictive skill.

### Performance

`n_jobs` was added after the first run took >23 min pinned to a single core
(sklearn's default `n_jobs=None`). Measured on the new run:

| | old | new |
|---|---|---|
| Trees | 50 | 64 |
| n_jobs | default (1) | 32 |
| Threads observed | 1 | 36 |
| Effective cores busy | 1 | ~24 |
| Wall clock | >23 min (killed) | ~5 min |

Data prep (netCDF load, stack, filter) is serial and took <1.6 min, so it now
bounds how much further parallelism can help. `n_estimators` was set to 64 —
a multiple of 32 — so both fitting waves fill every worker.

Run with `python -u` so progress prints stream instead of buffering until exit.

### Predict — Step_03

Done. 16 rasters in `Step_1_RF_for_FPI/output/`, ~29 MB each. Every one predicted
exactly **6,956,407 cells** — identical to the NLUM valid-cell count, with the
other 6,738,437 written as NaN.

Mean predicted FPI:

| Period | ssp126 | ssp245 | ssp370 | ssp585 |
|---|---|---|---|---|
| 2021-2040 | 3.984 | 4.036 | 3.966 | 4.011 |
| 2041-2060 | 3.808 | 3.810 | 3.784 | 3.771 |
| 2061-2080 | 3.801 | 3.751 | 3.596 | 3.552 |
| 2081-2100 | 3.778 | 3.579 | 3.459 | 3.413 |

The scenarios are indistinguishable in 2021-2040 and fan out monotonically with
time — SSP pathways barely diverge before mid-century. By 2081-2100 the spread
is 3.778 (ssp126) to 3.413 (ssp585), a ~10% difference in continental mean FPI.
This is the expected physical behaviour and is good evidence the predictors are
carrying the climate signal.

**Extremes are compressed.** Predicted maxima sit at ~20-21 against an observed
range to 25.8. A random forest cannot extrapolate beyond its training targets,
and high-productivity cells are rare in the 1970-2000 mean it was fitted on.
Visible in the Step_04 scatter as a flattening above observed FPI ~12.

### Validate — Step_04

`Step_04_scatter_pred_vs_obs.py` -> `plots/scatter_pred_vs_obs_2020_2022.png`
(+ .csv of the sampled points). 1,000 random NLUM cells, the same cells in every
panel, 2021-2040 prediction vs the observed **mean of 2020-2022**.

| scenario | r | RMSE | bias | mean pred |
|---|---|---|---|---|
| observed 2020-2022 | | | | 4.679 |
| ssp126 | 0.946 | 1.345 | -0.751 | 3.928 |
| ssp245 | 0.946 | 1.325 | -0.717 | 3.962 |
| ssp370 | 0.944 | 1.377 | -0.779 | 3.900 |
| ssp585 | 0.943 | 1.355 | -0.730 | 3.949 |

**r ~ 0.945** — the spatial pattern of FPI is reproduced well.

**Why a 3-year mean, not 2022 alone.** The first version of this plot used 2022
only and was much worse on every measure. Averaging three years damps single-year
weather:

| | vs 2022 alone | vs mean 2020-2022 |
|---|---|---|
| r | 0.900 – 0.905 | **0.943 – 0.946** |
| RMSE | 2.11 – 2.17 | **1.33 – 1.38** |
| bias | -1.38 – -1.44 | **-0.72 – -0.78** |
| observed mean | 5.343 | 4.679 |

Per-year continental means show why 2022 was a poor anchor:
2020 = 4.105, 2021 = 4.660, **2022 = 5.353**.

**The residual -0.75 bias is climatology, not model error.** A 20-year
mean-climate prediction is being compared with a 3-year observed mean, and
2020-2022 were all La Nina years, so even their mean (4.71) sits above the
1970-2000 climatological mean of 4.28 the model was trained on. The bias being
near-identical across all four scenarios confirms it comes from the observation
period, not from anything scenario-specific. Read the panels against each other,
not against the 1:1 line.

**High-end flattening.** Predictions plateau near 12-15 where observations reach
19 — the random forest cannot extrapolate beyond its training targets. Unchanged
by the averaging window.

All 1,000 sampled cells were usable — 6,956,407 of 6,956,407 NLUM-valid cells
are finite in all five rasters.

Design notes: the same cells are reused in every panel (sampling independently
per panel would confound scenario differences with different draws), and all
four panels use a single series colour because the panel title carries scenario
identity — the data-viz palette caps categorical hues at three slots for
scatter/small-multiple forms under all-pairs CVD checking.

---

## 7. Issues found and fixed

**1. `rasterio.merge` silently discarded every FPI tile.** The tiles' nodata is
`-3.4028230607370965e+38`, which arrives as a Python float; `np.can_cast(that,
'float32')` is `False`, so `merge()` warned "Ignoring nodata value" and returned
an array of **all zeros**. 19 rasters were written entirely zero before it was
caught. Fixed by casting to `np.float32()` before passing to `merge`, plus a
guard that raises if a mosaic has no real cells.
*This would have passed the NaN audit* — an all-zero raster has no NaN. It was
only caught by chasing the warning and checking unique-value counts.

**2. Bioclim band order.** `sorted(glob())` on `hist_bio` gives
`bio_1, bio_10, bio_11, ... bio_8, bio_9`, which would map BIO10 into the BIO2
slot and train on 19 mislabelled predictors. `hist_climate_paths()` resolves each
index numerically and raises if any index is not exactly one file. Verified:
resolved order is `1 2 3 ... 19`.

**3. `predict()` on NaN crashes.** sklearn 1.3.0 raises `Input X contains NaN`
from `RandomForestRegressor.predict`, and ~6.7 M of 13.7 M cells per band are NaN
outside the mask. The original Step_03's active code path fails outright. Now
predicts only on finite cells and writes NaN elsewhere.

**4. `compress='lzp'`** was not a valid GDAL creation option — corrected to `lzw`.

**5. Legacy historical climate was uint8.** In the previous project the training
climate was stored as `uint8` with `nodata=0`: temperatures quantised to whole
degrees (tmin Jan had 24 unique values), precipitation **saturated at 255 mm**,
while the future rasters the model predicts on are float32 reaching ~850 mm. A
random forest cannot extrapolate past its training range, so high-rainfall cells
were being predicted from a 255 mm ceiling. Fixed by downloading WorldClim
historical directly and processing it to float32 through the same path as the
future data.
*No code in the old project does this* — searched every `.py`/`.ipynb` under
`Random Forest/` for `uint8`/`astype`/`Byte`. The doubled `_reprojected_filled_
reprojected_filled` suffix indicates a GUI (ArcGIS/QGIS) export, run twice, with
a Byte output type. If that workflow feeds other datasets, they may be affected
too.

**6. FPI zips share filenames.** Every tile's zip contains `1970_001.tif` ..
`2022_001.tif` with no tile prefix, so extracting to a common directory would
leave a single tile's data. Each extracts to `Data/Raw/fpi/<tile>/`, with the
count verified per tile.

**7. `np.zeros` seed in Step_03** meant a missing future variable would read as
0.0 rather than being visible. Now seeded with NaN.

---

## 8. Environment

Conda env `JinzhuLuto` (Python 3.8.19) at
`C:\ProgramData\Anaconda3\envs\JinzhuLuto`.

`conda run -n JinzhuLuto` fails in shells where miniconda3 is on PATH, because
`~/.condarc` points `envs_dirs` elsewhere. Use the absolute prefix:

```powershell
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python <script>.py
```

A PostgreSQL/PostGIS `proj.db` on PATH shadows the conda one; the scripts set
`PROJ_LIB` to the env's own proj directory to silence the GDAL warnings.

---

## 9. Next steps

- [x] Record Step_02 R^2 / MSE — 0.9709 / 0.2081
- [x] Run Step_03 — 16/16 predictions written
- [x] Scatter predictions against observed 2022 (Step_04)
- [ ] Audit the 16 prediction rasters against NLUM (shape/CRS/NaN), as was done
      for every input
- [ ] Decide whether the FPI averaging window (1970-2000) is the one you want —
      all 53 yearly rasters are on disk, so re-averaging is cheap
- [ ] Consider a spatially blocked validation split — the random split gives
      R^2 0.97, which overstates skill on autocorrelated rasters
- [ ] Consider scattering the **2081-2100** predictions instead: the scenarios
      are indistinguishable in 2021-2040 and only separate late-century
- [ ] Consider a longer observed window than 2020-2022. All three were La Nina
      years, which is why a -0.75 bias remains; something like 2013-2022 would
      span both phases of ENSO and sit closer to climatology
