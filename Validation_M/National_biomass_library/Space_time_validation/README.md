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
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_match_and_validate.py --features reduced
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

**Both averaging orders were run, and they agree to within 0.33%** of the median
ratio in every run — the Jensen gap largely cancels once numerator and
denominator are built in the same order, which is what matched pairing is for.

| script | what it does |
|---|---|
| `Step_00_prepare_nvis.py` | NVIS 4.1 pre-1750 MVS (100 m Albers) majority-aggregated onto the NLUM grid |
| `Step_01_build_reference_table.py` | Dataframe 1 — one row per NBL site, mature and well-measured, with all 174 FPI predictors on the 1985–2014 climatology |
| `Step_02_build_future_table.py` | Dataframe 2 — one row per grid cell with the same columns, per scenario-window, plus the M′ projected there (and a historical twin) |
| `Step_03_match_and_validate.py` | the nearest-analogue match in PCA space, the controls, and every statistic |
| `Step_04_plots.py` | seven figures |
| `Step_05_write_report.py` | `Space_time_validation_report.docx` |

## The two dataframes, as specified

**Dataframe 1**, `outputs/reference_table.csv`: X, Y, 83 soil bands, 91 climate
features (1985–2014 mean), observed AGB, M′ today, FPI today, maturity class and
the provenance columns. 1,688 sites survive the filters; **600** are verified or
likely mature, which is the headline sample.

The filter trail is in `outputs/filter_trail.csv`: 15,904 site visits → biomass
present → live basal area → dead basal area under 20% → production estates out →
planted projects out → measured 1985 or later → sampled area ≥ 0.05 ha → biomass
≤ 1500 Mg ha⁻¹ → **AGB ≥ 1 Mg per m² of live basal area** → one row per site (the
maximum measurement, because M is a maximum).

Maturity comes from the tree-level table, since the site table has no age or
disturbance field: ≥ 1 stem of 50 cm DBH is *verified mature*, a largest stem of
30–50 cm is *likely mature*. It is joined on **`obs_key`, the survey event, not
on the site name** — 1,444 names carry more than one survey (up to 19) and 197
are shared across sources, so a join on the name pools stems from other visits
and other agencies into the record. On this sample it moves one site in 2,120,
but it is the join to assume.

### The basal-area consistency filter

A stand cannot carry less biomass than its own basal area implies. The library's
median is 7.8 Mg of AGB per m² of live basal area; below about 1 would be a
five-metre stand of balsa. Two sources fail that wholesale:

| source | median AGB per m² BA | sites |
|---|---|---|
| TERN Australia | 0.08 | 51 |
| CSIRO | 0.21 | 19 |
| *(whole mature sample)* | *7.8* | *688* |

The TERN plot `Giants` reports **0.60 Mg/ha of biomass against 108 m²/ha of live
basal area and a 403 cm stem**. These are corrupt biomass fields, not cleared or
burnt stands, and they were the entire explanation for the near-zero "mature"
sites — of the 53 mature sites under 5 Mg/ha, the median largest stem was 104 cm.

Dropping them removes 88 of 688 mature sites and moves everything downstream:

| | before | after |
|---|---|---|
| mature sites | 688 | 600 |
| median observed AGB | 83.0 | 112.4 Mg/ha |
| median ratio, site's own cell today | 0.611 | **0.494** |
| Spearman ρ, site's own cell today | 0.070 | **0.418** |
| Spearman ρ, SSP126 2035–2064 | 0.036 | **0.274** |

The ratio moves further from 1 while the rank correlation improves roughly
sixfold — the same fact seen twice. The discarded records carried biomass values
unrelated to the stands they described, which depressed the observed median and
added pure noise to the ranking. `--keep-inconsistent-agb` writes
`reference_table_noqc.csv` so the effect stays measurable rather than asserted,
and `Step_03 --reference-table reference_table_noqc.csv` validates against it.

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
reported separately. That flag is not cosmetic: under SSP5-8.5 2070-2099 only
**15 of 600** sites still have a future counterpart, so most of the late-century
high-forcing "matches" are to climates that do not exist in the present-day
domain at all.

**The match does not suffer from distance concentration.** A nearest neighbour
in a very high-dimensional space is only nominally nearest, because the spread
of pairwise distances shrinks relative to their mean as dimension grows. The
relative contrast -- the median site's typical candidate distance minus its
nearest, over its nearest -- is **7.9** on the 174-predictor space (18 PCs) and
**8.8** on a deliberately small 16-column set (7 annual climate means + one slice
of 9 soil properties, 8 PCs). Almost identical, so the PCA step has already
removed the problem; and the reduced set is no better on any metric while
displacing the analogues further on the ground (23.6 vs 19.4 km median). The
full set is kept. `--features reduced` reproduces the check.

## Results, in brief

Every number below is the `analogue found` stratum of the NVIS-constrained run
on the method's averaging order.

**The present-day gate does not pass.** At the site's own cell, M' is **0.49x**
the observed biomass at the median -- it under-predicts by about half -- and
ranks the sites only modestly better than a constrained random draw (Spearman
rho 0.42 against 0.21; R2 in logs negative; 34% of sites within a factor of two).

**Quote the constrained null, not the unconstrained one.** Random cells drawn
*without* the vegetation constraint give a ratio of 0.21 and rho 0.03, against
which the analogue search looks decisive -- but nearly all of that gap is the
NVIS constraint doing the work, since a random cell anywhere in Australia is
usually the wrong vegetation type entirely. Against its fair null the search
improves rho from **0.21 to about 0.27** and the ratio from **0.445 to about
0.49**: a real gain, and a modest one. The unconstrained figure is kept for
completeness and is not evidence of skill.

**Read the future runs against the present-day-analogue control (0.49, rho
0.30), not against 1.** Only the difference between the two is attributable to
the projection; the rest is the matching method's own error.

### The paired per-site comparison -- `fig_07`

The unpaired ratios mix two things: how well M' tracks biomass, and which
vegetation types happen to sit in the sample. Dividing each site's matched M' by
its **own** present-day M' removes both -- the observed biomass cancels exactly
-- so every site is its own control.

| scenario-window | M' ratio, paired | no analogue |
|---|---|---|
| SSP126 2035-2064 | 0.967 | 8% |
| SSP245 2035-2064 | 0.975 | 10% |
| SSP370 2035-2064 | 0.966 | 14% |
| SSP585 2035-2064 | 0.943 | 18% |
| SSP126 2070-2099 | 0.931 | 11% |
| SSP245 2070-2099 | 0.996 | 52% |
| SSP370 2070-2099 | **1.123** | 90% |
| SSP585 2070-2099 | **1.277** | 98% |

Baseline is each site's own present-day analogue, so the search procedure is
held fixed and only the climate moves.

**Read the last column with the first.** Where most sites still have an analogue
the paired change is a consistent small decline of 2.5-6.9%. Where the pool has
collapsed the same statistic reverses and reports a *rise* of 12-28%. That
reversal is not a projected gain in productivity -- it is selection. When 90% or
98% of sites have no analogue, the survivors are the cells whose climate still
exists somewhere, which are the wetter and more productive ones, and the
statistic is computed on a sample that no longer represents the reference set.

### Which runs are results

SSP370 2070-2099 retains 62 of 600 sites, SSP585 2070-2099 retains 15, and
SSP245 2070-2099 retains 287. **Do not quote those three as findings.** The five
remaining windows -- all four mid-century, and SSP126 late-century -- keep
82-92% of their sites.

The no-analogue fractions are themselves a result, and arguably the most
important one here: by late century under high forcing, the climate projected
for most of these forested sites **does not occur anywhere in present-day
Australia**. M' there is an extrapolation beyond what the observational record
can constrain -- the random forest is predicting FPI for climates it never saw
-- and that applies equally to the FullCAM inputs built from the same layers.

### Reconciling with the earlier bin validation

The earlier validation in the parent folder reported **1.55** on 254
verified-mature stands, against **0.49** here. Neither is wrong; on the same
sites the difference decomposes cleanly:

| step | median ratio |
|---|---|
| published Level 2 figure (verified mature, Eq. (1) footing) | 1.55 |
| reproduced here on the same footing and stratum | 1.47 |
| retire the Eq. (1) footing, use `New_M_2019` | 0.95 |
| widen from verified-only to verified + likely mature | 0.61 |
| apply the AGB-vs-basal-area filter | **0.49** |

The largest single term is the footing: the earlier number sat on Eq. (1)
applied directly, which overstates the Richards & Brack layer FullCAM ships by
~46%, so retiring it multiplies the ratio by 0.64 on its own -- a deliberate
decision, not a change of result. The residual between 1.55 and 1.47 is the
earlier run's per-cell rather than per-site aggregation and its missing
planted-project filter.

### Sanity checks that pass

The analogues move consistently **poleward**, and the median displacement grows
with forcing -- 36 km (SSP126 mid) to several hundred km (late, high forcing).
That is the direction and the ordering a warming climate should produce, and it
is evidence the matching finds real climate structure, independent of whether
the M' it retrieves agrees with the biomass.

### The limit that bounds everything above

The sample is geographically narrow: surviving sites cluster in eastern
Queensland and New South Wales, with smaller groups in Tasmania and the
south-west. The arid interior, the tropical north and most of South Australia
are effectively unsampled. Every ratio and correlation here is a statement about
**wet and sub-humid eastern forest**, and carries no weight over the rangelands
that make up most of the NLUM mask by area.

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
outputs/reference_table_noqc.csv         the same without the basal-area filter
outputs/filter_trail.csv                 survivors after each filter
outputs/reference_table_summary.csv      by maturity class
outputs/tables/*.npz, *_slim.csv         Dataframe 2, nine sets
outputs/matches_nvis.csv                 the method, NVIS-constrained
outputs/matches.csv                      the method, unconstrained
outputs/matches_nvis_mean_of_annual.csv  the per-year sensitivity
outputs/matches_climate_only_nvis.csv    the climate-only variant
outputs/matches_reduced_nvis.csv         the 16-predictor variant
outputs/matches_nvis_noqc.csv            without the basal-area filter
outputs/nvis_class_counts.csv            MVS classes inside the NLUM mask
outputs/metrics_by_run*.csv              every statistic, per run and stratum
outputs/metrics_by_maturity*.csv
outputs/no_analogue_summary*.csv
outputs/paired_log_ratio*.csv            the paired per-site comparison
outputs/matching_space*.csv              features, components, relative contrast
plots/fig_01..07                         the figures
Space_time_validation_report.docx
```
