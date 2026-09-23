# Run_02 — plot-area threshold 0.05 → 0.04 ha

**One constant.** The parent's `Step_01_build_reference_table.py` carries
`MIN_AREA_HA = 0.05`; this rebuilds the reference table at `0.04`. Nothing else
in the filter trail changes, and the matching is Run 0's throughout — both nulls
in every configuration, every metric from the `analogue found` stratum.

**Reported as a sensitivity.** The original plot-size rationale still stands.

## What it buys: southern coverage

| threshold | mature sites | south of 37°S | furthest south | DELWP Victoria |
|---|---|---|---|---|
| 0.05 ha | 600 | **4** | −38.1° | 0 |
| 0.04 ha | 778 | **113** | −39.1° | 178 |

At 0.05 ha the mature sample has **four** sites below 37°S — Victoria and
Tasmania are effectively absent from the validation of a continental layer. At
0.04 ha there are 113. This is the only filter choice tested anywhere in this
study that changes that.

## Who supplies them

Of the 283 visits admitted only by the change:

| provider | visits | median AGB | median BA | AGB per m²/ha BA | plot area |
|---|---|---|---|---|---|
| **DELWP Victoria** | **201** | 225 | 30.8 | 7.3 | all exactly 0.04 ha |
| University of Queensland | 28 | 620 | 15.7 | 39.5 | 0.04 ha |
| **University of NSW** | 27 | 68 | **0.6** | **~106** | 0.04 ha |
| DSITI Queensland Herbarium | 17 | 557 | 8.4 | 66.6 | 0.04 ha |
| Dept of Parks and Wildlife (WA) | 7 | 429 | 51.0 | 10.8 | 0.04 ha |

The gain is **concentrated, not diffuse**, which is what makes it checkable.
DELWP's plots are all exactly 0.04 ha and their values are ordinary — 225 Mg/ha
on 30.8 m²/ha of basal area is a ratio of 7.3, right on the library median.
They fail the 0.05 ha threshold by one hundredth of a hectare and nothing else.

University of NSW is the exception to watch: 27 visits at a biomass-to-basal-area
ratio near **106**, which passes the consistency filter only because that filter
is a floor and not a ceiling. Everything below is run with and without them.

## What it does to the result

| configuration | sites | south | ratio | ρ | null ρ | gap | no-analogue |
|---|---|---|---|---|---|---|---|
| 0.05 ha (Run 0) | 600 | 4 | 0.465 | 0.269 | 0.205 | +0.064 | 16.1% |
| **0.04 ha** | **778** | **113** | 0.515 | 0.309 | 0.225 | **+0.084** | 18.8% |
| 0.04 ha, no UNSW | 770 | 113 | 0.514 | 0.309 | 0.262 | +0.047 | 19.0% |
| 0.04 ha, southern only | 113 | 113 | 0.846 | 0.071 | 0.071 | **+0.000** | 35.0% |

Unlike Run 1, this gains **sites *and* metrics** — 778 against 600 — so there's
no precision trade-off to weigh.

### Two reasons not to over-read it

**The southern sites carry no skill of their own.** Matched alone, the 113 sites
below 37°S give ρ 0.071 against a null of 0.071 — a gap of **exactly zero**.
They're underpowered at that size with 35% no-analogue, so this isn't evidence
*against* them; but the improvement in the pooled result is not coming from the
new southern sites ranking well. It comes from the sample being larger.

**The metric change is within the noise.** Dropping the eight University of NSW
sites — **1% of the sample** — moves the gap by **0.037**, while the change from
0.05 to 0.04 ha moves it by **+0.020**.

> When removing 1% of the sites shifts the statistic nearly twice as far as the
> intervention does, the intervention cannot be quoted as an effect on that
> statistic.

## Why this stays a sensitivity

The rationale for the threshold hasn't changed: median biomass falls from 276
Mg/ha on plots under 0.05 ha to 11 over 0.5 ha, a gradient produced by sampling
geometry rather than vegetation. The companion study in
`../Plot_area_floor_method/` pushes the same lever the other way and finds that
**raising** the floor to 0.40 ha lifts M′/AGB from 0.465 to 1.275 and the gap
from +0.064 to **+0.128** — the largest improvement any single change in this
study has produced.

> The two runs point in opposite directions on the same parameter, and they are
> not in conflict. The plot-size artefact is real and raising the floor removes
> it. Lowering the floor admits more of it, and is justified by **coverage**
> rather than by measurement quality. Both belong in the record; neither should
> be adopted silently.

## What to conclude

- **Quote the coverage gain** — 4 southern sites become 113, and the validation
  stops being a statement about Queensland and New South Wales alone.
- **Don't quote the metric gain.** Not resolvable at this sample size.
- **Name the provider.** This is really a sensitivity to including DELWP
  Victoria, not to a threshold, and should be described that way.
- **Watch University of NSW** — a ceiling on the biomass-to-basal-area ratio is
  worth its own one-change test.
- **Keep 0.05 ha as the default.** The plot-size rationale stands and the gains
  lie in the other direction.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\Run_02
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_build_004_table.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_run_and_compare.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_write_report.py
```

`Step_01` imports the parent's `Step_01_build_reference_table.py`, patches
`MIN_AREA_HA` and `OUT_DIR` in the imported module, and calls its `main()`. The
parent file is never modified and nothing is written outside this folder.
`Step_02` imports `../Run_0/Step_A_run_ofat.py` for the matching helpers, which
are the parent's `Step_03` functions underneath.

## Files

```
Step_01_build_004_table.py           rebuilds the reference table at 0.04 ha
Step_02_run_and_compare.py           the four configurations
Step_03_plots.py                     three figures
Step_04_write_report.py              Run_02_report.docx
outputs/reference_table_min004.csv   1,945 sites (778 mature)
outputs/filter_trail_min004.csv      survivors after each filter
outputs/admitted_by_the_change.csv   who supplies the 283 new visits
outputs/coverage.csv                 what each threshold covers
outputs/run02_summary.csv            one row per configuration per run
outputs/run02_headline.csv           the comparison table above
outputs/<config>/matches.csv         site-level matches, and metrics.csv
plots/fig_01_coverage.png            where the new sites are
plots/fig_02_metrics.png             the runs against their null, and the gap
plots/fig_03_stability.png           the effect against the noise
```
