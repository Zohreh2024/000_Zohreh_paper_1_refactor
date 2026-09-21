# FPI_Accuracy_check/

Model the **historical** FPI with the same random forest that made the
projections, check it against the observed FPI, and rebuild M' so that both
sides of the delta-change ratio come from one model.

```
before   M' = λ × Original_M_2004 × Eq1(FPI_future, random forest)
                                  ÷ Eq1(FPI_1985-2014, DCCEEW download)

after    M' = λ × Original_M_2004 × Eq1(FPI_future,    random forest)
                                  ÷ Eq1(FPI_1985-2014, random forest)
```

Any bias in the forest sits in the numerator only in the first form, so it does
not cancel and is read downstream as climate change. This is the rule already
applied to temperature and rainfall — every delta is CSIRO-minus-CSIRO, never
CSIRO-minus-ANUClimate. FPI was the one input where it was not applied.

## Running it

```powershell
cd FPI_Accuracy_check
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_predict_historical_fpi.py --jobs 6
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_accuracy_vs_observed.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_M_hist_from_modelled_fpi.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_future_Mprime_modelled_footing.py --jobs 8
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_06_write_report.py
```

Step_01 is the long one (30 full-grid predictions, ~200 s each, 6 at a time) and
is resumable — it skips any year whose raster already exists. Step_04 is
idempotent in the same way; pass `--force` to rebuild.

| script | what it does |
|---|---|
| `Step_01_predict_historical_fpi.py` | the saved forest applied to the BARRA-R2 historical climate, 1985–2014, full NLUM grid |
| `Step_02_accuracy_vs_observed.py` | modelled vs observed FPI: in-sample per year, plus the out-of-fold number |
| `Step_03_M_hist_from_modelled_fpi.py` | Eq. (1) M from the modelled FPI, in both averaging orders, vs the observed denominator |
| `Step_04_future_Mprime_modelled_footing.py` | runs the pipeline's own Step_08 with the modelled denominator, then compares against Option B |
| `Step_05_plots.py` | the five report figures, from the CSVs and rasters the steps above wrote |
| `Step_06_write_report.py` | `FPI_modelled_reference_report.docx` |

The report and the figures recompute no metric — every number is read from the
CSV written by the step that computed it, so re-running any step and then
Step_05/Step_06 keeps the write-up and the numbers in step.

`_superseded_accuracy_fpi_historical.py` is the original single-file draft. It
was written against a layout this repository does not have — one GeoTIFF per
predictor in a features directory, `random_forest_model.joblib` beside an
`inspect_artifacts.py`, `feature_order.npy` — and its `build_feature_matrix`
would have silently mis-ordered the 174 columns. Kept only for reference.

## No retraining, and no new model

Step_01 loads `Random_forest_CSIRO/data/random_forest_model.pkl` and asserts its
feature order against `common.feature_names()` before predicting. Soil, land
mask and the 0.11° → 0.01° bilinear regrid all come from
`Random_forest_CSIRO/common.py`, so the historical prediction and the 240 future
ones are produced by identical code paths with only the climate year swapped.

The land mask is soil-derived, as in `Step_04_predict_future.py`, and
deliberately **not** the observed FPI footprint: masking one side of the ratio
to where FPI happened to be observed would leave holes on that side only.

## Which accuracy number to quote

| | what it measures |
|---|---|
| in sample, full grid (`accuracy_by_year.csv`) | fit. These 30 years trained the model, so this is not skill. It **is** the right diagnostic for the denominator swap, because it says how far the modelled denominator sits from the observed one. |
| out of fold, year-group CV (`accuracy_summary.csv`) | skill. Every row predicted by a forest that never saw that year — the same act as projecting 2035–2099. **Quote this one.** It comes from `Random_forest_CSIRO/data/oof_groupcv_year.npz`, on the downsampled training cells. |

Comparing a future projection against observed history is neither: that is a
trend comparison, and the two are not supposed to agree.

## Results

**Accuracy.** Out of fold, year-group CV: **R² 0.931, RMSE 0.754, bias +0.004**.
In sample on the full grid: R² 0.968, RMSE 0.513, bias +0.002, with per-year R²
between 0.953 and 0.974 and no trend across the 30 years.

**The denominator swap is small.** Modelled ÷ observed historical M has a median
of **1.0066** (p05–p95 0.818–1.228), so the forest's historical bias was slight
and M′ moves by well under a percent on that account alone. The change is
methodological rather than numerical — which is the point: the bias now cancels
by construction instead of by luck.

**M′ moves by exactly the denominator ratio, and by nothing else.** The measured
shift against Option B is the same in every scenario and window, as it must be,
since the denominator is a per-cell constant:

| pairing | M′ vs Option B (median) | what changed |
|---|---|---|
| **`eq1_of_mean` — the method** | ×0.9908 | denominator modelled instead of downloaded |
| `mean_of_annual` — sensitivity | ×0.9441 | that, **and** the averaging order corrected |

**The method is `eq1_of_mean`:** predict each year's FPI, average the FPI over
the period, then apply Eq. (1) to that mean — on both sides of the ratio. That
is the quantity Eq. (1) is defined on: Roxburgh et al. (2019) Sec. 2 p. 265 give
Eq. (1) as "the predicted maximum AGB for a given FPI", with FPI "potential site
productivity for any given location" and M "constant for any location in
Australia". `Calculation_future_M_CSIRO/Step_06` says the same in the repo's own
words. The per-year order is reported throughout as a sensitivity.

The projected change FullCAM sees at the boundary, against `New_M_2019`, is
**−2.6% to −21.2%** on the method across the eight scenario-windows (−3.2% to
−22.8% on the per-year sensitivity), negative in all of them.
Option B's `eq1_of_mean`-denominator numbers ran −18.6% to **+1.13%**, i.e. two
windows came out positive; those sign flips were the Jensen mismatch, not a
climate signal, and pairing by averaging order removes them.

**Two rebuild checks passed.** `Eq1_M_histOBS_eq1_of_mean.tif` reproduces the
pipeline's cached `Eq1_M_hist_1985-2014.tif` to 3.1e-05 t DM ha⁻¹, and the
observed Jensen gap measured here, **1.0319**, is exactly the figure recorded
independently in `Option_B_matched_footing/README.md`.

## The averaging order has to match, and now does

Eq. (1) is convex above its root, so by Jensen's inequality
`mean_y[Eq1(FPI_y)] ≥ Eq1(mean_y FPI_y)`, with a median gap of ~1.03 on this
domain. `Step_06` writes the numerator in both orders. Step_03 therefore writes
the denominator in both, and Step_04 runs Step_08 twice, pairing like with like:

| run | numerator | denominator |
|---|---|---|
| `mean_of_annual` | `M_<ssp>_<year>.tif`, `M_<ssp>_<window>_mean.tif` | `Eq1_M_histRF_mean_of_annual.tif` |
| `eq1_of_mean` | `M_from_mean_fpi_<ssp>_<window>.tif` | `Eq1_M_histRF_eq1_of_mean.tif` |

Mixing them puts the Jensen gap into the ratio, where it reads as a climate
signal — two of the eight windows change sign on that alone. See
`Option_B_matched_footing/README.md`, "An inconsistency this rebuild exposed".

## What was changed outside this folder

One file, backwards compatibly:
`Calculation_future_M_CSIRO/Step_08_apply_published_lambda.py` gained three
optional flags — `--hist-m` (use this raster as the ratio denominator),
`--out-dir`, and `--layers` (select one averaging order). Omit all three and the
script behaves exactly as before, so `Option_B_matched_footing/Step_02` and the
existing outputs are unaffected. Its closing summary also gained a guard for the
case where a run contains no annual layers, which `--layers eq1_of_mean` is the
first caller to hit (it raised `min() arg is an empty sequence` after all the
rasters had already been written and verified). Step_04 calls that script rather than
reimplementing Eq. (3), so the NaN handling, the `MIN_HIST_M` floor, λ and the
metadata stay the pipeline's and cannot drift.

## Outputs

```
output/fpi_rf_<year>.tif                         30 modelled historical years
output/fpi_rf_1985-2014_mean.tif
output/accuracy_by_year.csv, accuracy_summary.csv, oof_accuracy_by_year.csv
output/Eq1_M_hist{RF,OBS}_{mean_of_annual,eq1_of_mean}.tif   4 denominators
output/hist_M_denominator_levels.csv, hist_M_denominator_comparison.csv
output/Mprime_modelled_vs_observed_denominator.csv
output_Mprime_rf/mean_of_annual/maxAbgMF_*.tif   240 annual + 8 window means
output_Mprime_rf/eq1_of_mean/maxAbgMF_*.tif        8
output/optionB_pct_change.csv                    Option B's change vs New_M_2019
plots/fig_01_accuracy.png                        modelled vs observed, R2 by year
plots/fig_02_hist_fpi_maps.png                   mean FPI: observed, modelled, difference
plots/fig_03_denominator.png                     the swap, and the averaging order
plots/fig_04_mprime_change.png                   the step FullCAM sees
plots/fig_05_mprime_change_maps.png              where the change sits
FPI_modelled_reference_report.docx
```

`Eq1_M_histOBS_eq1_of_mean.tif` reproduces the denominator the pipeline uses
today (`Calculation_future_M_CSIRO/output/Eq1_M_hist_1985-2014.tif`); Step_03
checks it against that file and says so, so the rebuild is verified rather than
assumed.

Nothing here is adopted into `FullCAM_input_CSIRO_data/` — the FullCAM inputs
still come from whichever footing the project has decided on.
