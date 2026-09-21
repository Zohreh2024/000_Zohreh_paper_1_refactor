# Space_time_validation/

Space-for-time validation of the **new M′** — the one whose every component comes
from the random forest — against the National Biomass Library.

```
For each NBL site:  find the future grid cell whose FPI predictors are closest
                    to that site's historical predictors,
                    then compare observed biomass with the M' projected there.
```

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_00_prepare_nvis.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_build_reference_table.py --keep-all-classes
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_build_future_table.py --jobs 6
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_match_and_validate.py --features all
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_match_and_validate.py --features climate
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_plots.py --suffix _nvis
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_write_report.py --suffix _nvis
```

Step_02 is the long one (~5 min: nine tables, 69,564 cells each, 30 years of
climate per table) and skips tables that already exist.

**The M′ validated here is the method**: `Eq1(mean_y FPI_y)` on both sides of
the ratio — predict each year's FPI, average the FPI over the window, then apply
Eq. (1) (Roxburgh et al. 2019, Sec. 2, p. 265). That is the default of every
step. `--constrain none` drops the vegetation constraint and
`--mprime-order mean_of_annual` runs the per-year sensitivity; outputs, figures
and reports carry a suffix naming whatever produced them (`_nvis`,
`_nvis_mean_of_annual`, …), so the variants coexist rather than overwrite one
another. The unsuffixed report is the method.

**Both averaging orders were run, and they agree to within 0.73%** of the median
ratio in every run — the Jensen gap largely cancels once numerator and
denominator are built in the same order, which is what matched pairing is for.

| script | what it does |
|---|---|
| `Step_00_prepare_nvis.py` | NVIS 4.1 pre-1750 MVS (100 m Albers) majority-aggregated onto the NLUM grid |
| `Step_01_build_reference_table.py` | Dataframe 1 — one row per NBL site, mature and well-measured, with all 174 FPI predictors on the 1985–2014 climatology |
| `Step_02_build_future_table.py` | Dataframe 2 — one row per grid cell with the same columns, per scenario-window, plus the M′ projected there (and a historical twin) |
| `Step_03_match_and_validate.py` | the nearest-analogue match in PCA space, the controls, and every statistic |
| `Step_04_plots.py` | six figures |
| `Step_05_write_report.py` | `Space_time_validation_report.docx` |

## The two dataframes, as specified

**Dataframe 1**, `outputs/reference_table.csv`: X, Y, 83 soil bands, 91 climate
features (1985–2014 mean), observed AGB, M′ today, FPI today, maturity class and
the provenance columns. 2,120 sites survive the filters; **688** are verified or
likely mature, which is the headline sample.

The filter trail is in `outputs/filter_trail.csv`: 15,904 site visits → biomass
present → live basal area → dead basal area under 20% → production estates out →
planted projects out → measured 1985 or later → sampled area ≥ 0.05 ha → biomass
≤ 1500 Mg ha⁻¹ → one row per site (the maximum measurement, because M is a
maximum).

Maturity comes from the tree-level table, since the site table has no age or
disturbance field: ≥ 1 stem of 50 cm DBH is *verified mature*, a largest stem of
30–50 cm is *likely mature*.

**Dataframe 2**, `outputs/tables/*.npz`: the same 174 columns for 69,564 land
cells (every 10th cell, the rate the random forest's own training table used),
once per scenario-window, plus `mprime` and `fpi`. A slim CSV beside each holds
X, Y, M′, FPI and the seven annual climate means for reading by eye.

## The match

All 174 predictors standardised on the historical land-cell distribution, then
projected onto its principal components (18 components, 95% of variance), then a
k-d tree nearest neighbour. PCA matters here: the raw predictors are strongly
collinear — twelve monthly temperatures move together — so plain Euclidean
distance counts one physical signal a dozen times and lets 83 soil columns
outvote the climate.

**The search is constrained to vegetation.** A site can only be matched to a
cell carrying the same pre-1750 NVIS Major Vegetation Subgroup. Climate and soil
can agree exactly and still pair a rainforest site with a cell that carries
mallee, and those two carry different biomass for reasons this chain does not
model. Pre-1750 rather than extant extent, because M is what a site *could*
carry: a cleared paddock that was wet sclerophyll forest in 1750 still has the
climate and soil of wet sclerophyll forest. 79 subgroups fall inside the mask,
99.9% of cells are classified, and a subgroup with fewer than 25 cells in the
pool falls back to an unconstrained match, flagged in the output.

A site whose nearest future cell is further than the 99th percentile of
within-historical nearest-neighbour distance is flagged `no_analogue` and
reported separately. That flag is not cosmetic: under SSP5-8.5 2070–2099 only
**58 of 688** sites still have a future counterpart, so most of the late-century
high-forcing "matches" are to climates that do not exist in the present-day
domain at all.

## Results, in brief

**The present-day gate does not pass.** At the site's own cell, M′ is **0.61×**
the observed biomass at the median and ranks the sites barely better than chance
(Spearman ρ 0.15; R² in logs negative; 30% of sites within a factor of two).

**The footing straddles the observations.** Evaluating Eq. (1) on the same
modelled FPI at the same cells gives a median ratio of **1.22** against **0.61**
for λ × Original_M_2004 — a factor of 2.0 between the two footings. Eq. (1) M
sits above observed mature biomass, which is the direction a maximum should err
in; the matched footing sits below it, which immaturity cannot explain. Neither
reproduces the ranking.

**The vegetation constraint raises the null more than it raises the runs, and
that is the most useful thing this test produced.** Unconstrained, random cells
give a ratio of 0.27, which makes the future runs look like skill. Once "random"
means *a random cell of the same vegetation subgroup*, the null rises to 0.59 —
against which the future runs (0.42–0.79, present-day analogue 0.64) are barely
distinguishable. Knowing the pre-1750 vegetation
subgroup is most of what is needed to guess the biomass; the climate matching
adds little beyond it on this sample.

That does not say the projection is wrong. It says this comparison cannot tell a
correct projection from an incorrect one, because the observable is dominated by
vegetation type and plot-scale variation rather than by climate. Quote the null
beside every ratio; a ratio on its own from this test overstates what it shows.

**Read the future runs against the present-day-analogue control (0.64), not
against 1.** Only the difference between the two is attributable to the
projection; the rest is the matching method's own error.

## Why a failed gate is not by itself a verdict on M′

- A 1 km cell's M′ is the potential of the whole cell; an NBL plot is a fraction
  of a hectare inside it. They are not the same quantity, and the scatter in
  `fig_02` is what that mismatch looks like.
- The library records no stand age, so the sample still contains stands well
  short of their maximum even after filtering.
- The vegetation constraint is now applied (it was the largest missing piece),
  so "two cells share a climate but carry different vegetation" is answered.
  What it revealed is that the null was understated without it.
- λ derives from `New_M_2019`, which is itself the output of a random forest
  fitted to NBL plots, so agreement in *level* is partly circular. What is
  genuinely tested is whether a projected climate change moves M′ consistently
  with biomass observed under comparable climates today.

## Outputs

```
outputs/reference_table.csv              Dataframe 1
outputs/filter_trail.csv                 survivors after each filter
outputs/reference_table_summary.csv      by maturity class
outputs/tables/*.npz, *_slim.csv         Dataframe 2, nine sets
outputs/matches_nvis.csv                 the method, NVIS-constrained
outputs/matches.csv                      the method, unconstrained
outputs/matches_nvis_mean_of_annual.csv  the per-year sensitivity
outputs/matches_climate_only_nvis.csv    the climate-only variant
outputs/nvis_class_counts.csv            MVS classes inside the NLUM mask
outputs/metrics_by_run.csv               every statistic, per run and stratum
outputs/metrics_by_maturity.csv
outputs/no_analogue_summary.csv
plots/fig_01..06                         the figures
Space_time_validation_report.docx
```
