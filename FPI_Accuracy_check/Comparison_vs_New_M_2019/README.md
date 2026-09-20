# Comparison_vs_New_M_2019/

Future M′ — built with every component from the random forest — against
`New_M_2019`, the layer FullCAM ships as its historical maxAbgM. Variability
first, then the ordinary comparison metrics, one metric per figure.

Everything here reads from the parent folder and writes only inside this one:

```
inputs   ../output/fpi_rf_<year>.tif                              30 modelled historical years
         ../output_Mprime_rf/mean_of_annual/maxAbgMF_*.tif        240 annual + 8 window means
         ../output_Mprime_rf/mean_of_annual/scale_Eq1_to_original2004.tif
         Step_02_published_lambda/output/lambda_published.tif
         Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif
```

## Running it

```powershell
cd FPI_Accuracy_check\Comparison_vs_New_M_2019
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_07_compare_vs_New_M_2019.py --jobs 5
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_08_plots_comparison.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_09_paired_bars.py
```

Step_07 streams 270 rasters (~25 GB read) and takes roughly 15 minutes; it keeps
existing CV rasters unless `--overwrite` is passed. Step_08 recomputes nothing —
every number in a figure comes from Step_07's CSVs.

## "Coefficient of variation" means three different things here

All three are computed, because they answer different questions and are easy to
confuse:

| | what varies | what it tells you |
|---|---|---|
| **interannual** | the 30 years within one scenario-window, per cell | how much M′ moves from year to year under a single scenario |
| **across-scenario** | the four SSP window means, per cell | how much the scenario choice matters |
| **spatial** | cells within one layer, one number per layer | how spread out the map is as a whole (in the CSV) |

`New_M_2019` is a single layer and has no interannual dimension, so the
historical reference for the first row is rebuilt from the 30 **modelled**
historical years on the same footing — `M′_hist,y = λ × Original_M_2004 ×
Eq1(FPI_rf,y) ÷ D`. That makes the future and historical CVs comparable, and it
also gives a hard check: averaged over the 30 years that expression collapses to
`λ × Original_M_2004`, which *is* `New_M_2019`, so `mean_y M′_hist` must
reproduce the reference cell for cell. Step_07 prints that error rather than
assuming it.

## Figures

| figure | metric |
|---|---|
| `fig_06_cv_interannual.png` | interannual CV, eight scenario-windows plus the modelled historical period |
| `fig_07_cv_change.png` | future CV − historical CV, in percentage points |
| `fig_08_cv_across_scenarios.png` | scenario disagreement, and how it compares with interannual variability |
| `fig_09_scatter_vs_New_M_2019.png` | M′ against the reference cell by cell, with r, slope, bias, RMSE |
| `fig_10_totals.png` | area-weighted national total biomass, Mt DM, and its change |
| `fig_11_change_by_decile.png` | median change by decile of `New_M_2019` — where in the distribution the loss falls |
| `fig_13_rf_mprime_bars.png` | **the headline bar chart**: median M′ per scenario-window, every component from the random forest, against the hatched 1985–2014 baseline and the `New_M_2019` reference line (`Step_09_paired_bars.py --mode rf_only`) |
| `fig_12_paired_bars.png` | the same layout with Eq. (1) M beside it, so the footing gap and the climate signal sit on one axis (`--mode footings`) |

Percentages inside the bars of `fig_13` are the shift in the **median**
(`median(M′)` against `median(New_M_2019)`), which is a different statistic from
the median of the per-cell changes in `comparison_vs_New_M_2019.csv` — a median
is not additive. The first says where the middle of the map now sits, the second
what happens to a typical cell; both are reported, so state which one is quoted.

## Tables

| file | contents |
|---|---|
| `output/comparison_vs_New_M_2019.csv` | per scenario-window: mean, median, bias, RMSE, MAE, Pearson r, OLS slope, median and mean % change, % of cells declining, spatial CV, and the national total in Mt DM |
| `output/cv_summary.csv` | the distribution (mean, median, p05, p95) of each CV layer |
| `output/change_by_baseline_decile.csv` | median and quartile change per decile of `New_M_2019` |
| `output/cv/*.tif` | the CV layers themselves, on the NLUM grid |

## Results

**The chain checks out.** `mean_y M′_hist` reproduces `New_M_2019` to a median
relative error of **2.8e-08** (max 1.9e-07), i.e. to float32 rounding. Everything
below is therefore a statement about the projected change, not about the level.

**Interannual CV is large and does not grow.** Median CV of M′ within a window:

| | historical | SSP126 | SSP245 | SSP370 | SSP585 |
|---|---|---|---|---|---|
| 2035–2064 | 48.3% | 46.2 | 46.5 | 45.5 | 44.2 |
| 2070–2099 | 48.3% | 47.5 | 43.4 | 44.5 | 44.9 |

Two things follow. First, ~48% is *large* — a cell's M′ swings by roughly half
its own mean from year to year, because Eq. (1) is quadratic in √FPI and so
amplifies a dry year. Any single future year is a poor estimate of the window;
quote window means. Second, the future CV is **1.4 to 4.7 percentage points
lower** than historical in every scenario-window (`fig_07`). Projected M′ is not
becoming more erratic — if anything slightly less so, and mostly where the mean
itself falls. (That 1.4–4.7 pp is the median of the per-cell difference; the
difference of the two medians is 0.8–5.0 pp — different quantities, same sign
everywhere.) Read that with care: the QDC change factors are applied to
*observed* BARRA-R2 years, so the interannual sequence is observed weather
rescaled, not model weather (see the repo's `CLAUDE.md`), and the method cannot
generate new variability of its own.

**Scenario choice matters far less than the year.** Across-scenario CV is 5.9%
mid-century and 12.4% late-century, against ~45% interannual. The scenarios
separate late, as they should, but even then the year-to-year spread within one
scenario is three to four times larger.

**Cell by cell, M′ tracks the reference closely and sits just below it.**
Pearson r 0.984–0.998, OLS slope 0.999–1.057, bias −0.4 to −5.2 t DM ha⁻¹,
RMSE 5.8–16.2. The share of cells that decline rises from 67% (SSP126
2035–2064) to 91% (SSP585 2070–2099).

**National total**, area-weighted, against 34,363 Mt DM for `New_M_2019`:
−2.5% to −4.8% by mid-century, −1.1% (SSP245) to −11.9% (SSP585) late. The
totals fall less than the per-cell medians (−3.2% to −22.8%) because the deepest
relative losses are in low- and mid-biomass cells, which carry little of the
total — `fig_11`.

**Where the loss falls.** Relative loss peaks in deciles 2–5 of `New_M_2019`
(−32% under SSP585 2070–2099) and is shallowest in the top decile (−6%). In
absolute tonnes the picture inverts, since the top decile holds most of the
biomass; report whichever one the audience needs, and say which it is.

## Two things to keep in mind when quoting these

**The comparison is anchored, not independent.** `λ × Original_M_2004` is
`New_M_2019`, so the historical end of this chain reproduces the reference by
construction. What the comparison measures is the *projected change*, not
whether the absolute level is right; for an independent check of the level, see
`Validation_GEDI/` and `Option_B_matched_footing/Validation/`.

**The national total is area-weighted.** Cells are 0.01° geographic, so their
area shrinks with latitude by `cos(lat)`; an unweighted sum over-counts the
south by several per cent. `cell_area_ha()` in Step_07 does the weighting, and
the totals are in Mt DM over the whole NLUM mask — a carrying-capacity figure,
not an inventory estimate, since M′ is what a site could carry rather than what
stands on it.
