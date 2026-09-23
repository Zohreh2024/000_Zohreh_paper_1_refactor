# Run_04 — a maturity rule on basal area instead of stem diameter

The most expensive and most debatable run, left last. **Verdict: don't adopt
it** — but not for the reason expected. The rule is sound; the sample it
unlocks is not.

## The problem

Maturity needs stem records, and only **2,047 of 15,904** site visits have any.
The four largest sources have **none at all**:

| source | visits | with stem records |
|---|---|---|
| Forestry Corporation NSW | 6,718 | **0%** |
| Queensland NFPP | 3,158 | **0%** |
| Forestry Tasmania | 2,201 | **0%** |
| Parks and Wildlife WA | 898 | **0%** |

So the DBH rule caps the reference sample at **600 of 1,688** sites. Live basal
area is reported for almost every visit and could reach the other 1,088.

## Calibrating it

| class | sites | median basal area | IQR |
|---|---|---|---|
| verified mature | 327 | **14.75** m²/ha | 9.2–20.4 |
| likely mature | 273 | **6.75** | 4.1–12.1 |
| young or shrubby | 156 | **2.99** | 0.9–7.0 |
| *unverified (no label)* | *932* | ***15.72*** | *8.9–26.5* |

Calibrated on the 756 labelled sites, basal area reproduces the
mature/not-mature distinction at **AUC 0.800** — better than it deserves to be,
since maturity is defined by the *largest stem* while basal area is the summed
cross-section of *all* stems. A sparse stand of old giants and a dense thicket
of saplings carry the same basal area.

| threshold | sensitivity | specificity | balanced accuracy | selects |
|---|---|---|---|---|
| 5 m²/ha | 0.82 | 0.65 | **0.732** | 1,377 |
| 7 | 0.70 | 0.75 | 0.727 | 1,240 |
| 9 | 0.59 | 0.81 | 0.704 | 1,083 |
| 14 | 0.36 | 0.93 | 0.642 | 745 |

> One number should have been a warning: the 932 **unverified** sites — the ones
> the rule exists to reach — have a median basal area of **15.72**, *above* the
> verified group's 14.75. Either they really are mature, or basal area isn't
> discriminating maturity among them. The labelled data can't settle it, because
> the label they'd be judged on is exactly what they lack.

## The result

The design separates the two things the rule does — change the criterion, and
expand the sample:

| configuration | sites | labelled | **gate ρ** | ratio | future ρ | null ρ | gap |
|---|---|---|---|---|---|---|---|
| DBH rule (Run 0) | 600 | 600 | **0.418** | 0.465 | 0.269 | 0.205 | +0.064 |
| **BA ≥ 7, labelled only** | 461 | 461 | **0.320** | 0.378 | 0.240 | 0.014 | +0.226 |
| BA ≥ 5, all | 1,377 | 545 | **−0.038** | 0.757 | −0.058 | −0.033 | −0.025 |
| BA ≥ 7, all | 1,240 | 461 | **−0.023** | 0.809 | −0.044 | −0.049 | +0.005 |
| BA ≥ 9, all | 1,083 | 385 | −0.036 | 0.897 | −0.052 | −0.040 | −0.012 |
| BA ≥ 14, all | 745 | 224 | −0.075 | 1.063 | −0.084 | −0.082 | −0.002 |

**The criterion is fine.** On labelled sites alone it gives a gate of 0.320 and
future ρ 0.240, against 0.418 and 0.269 for the DBH rule — slightly lower on 461
sites instead of 600, which is what a weaker criterion should look like.

> **The expansion destroys it.** Adding the 779 sites with no stem record takes
> the gate from 0.320 to −0.023 and the future runs from 0.240 to −0.044. Every
> threshold lands between −0.04 and −0.08. This is a reversal, not a dilution.

## Why

| half of the expanded sample | sites | ρ of observed AGB with M′ | median plot | AGB per m²/ha BA |
|---|---|---|---|---|
| labelled (has stem data) | 461 | **+0.320** | 0.24 ha | 10.2 |
| **unlabelled (added by the rule)** | 779 | **−0.109** | 0.13 ha | 5.2 |

They don't merely carry less signal — they carry the **opposite sign**, which is
why the pooled result falls below zero rather than towards it.

| provider added | sites | ρ with M′ | median plot | AGB per m²/ha BA |
|---|---|---|---|---|
| Parks and Wildlife WA | 365 | −0.06 | 0.13 ha | 4.2 |
| Queensland NFPP | 280 | −0.06 | 0.40 ha | 4.4 |
| Darwin Centre for Bushfire Research | 134 | +0.15 | **0.08 ha** | **44.6** |

All three were already flagged by earlier work. The Roxburgh folder found
Queensland NFPP at ρ −0.24 on its 1,647 records; Darwin reports 601 Mg/ha on
eighth-hectare plots — the small-plot inflation this study keeps returning to.

## What to conclude

- **The rule is sound and the sample is not.** AUC 0.80, comparable performance
  where both labels exist. The problem is entirely in what it unlocks.
- **Don't adopt it.** Nearly doubling the sample is worth nothing when the added
  half correlates *negatively* with what's being validated.
- **The 1,088 sites without stem records aren't simply unmeasured — they're
  differently measured.** No maturity rule repairs that; the defect is in the
  biomass, not the maturity.
- **The stem-record requirement is doing more than it appears to.** It looks
  like a maturity filter and is *also* a data-quality filter: the providers who
  record stems are the providers whose biomass behaves. Worth saying explicitly
  wherever the 600-site cap is described as a limitation.
- **If the sample must grow, grow it on measurement quality.** Run 3 lifted the
  gate from 0.42 to 0.73 by rebuilding biomass from stem diameters — but that
  needs stem records too, so it reaches the same 600 sites. Going further
  requires providers to supply stem data, not a different rule applied to what
  they did supply.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\Run_04
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_calibrate_rule.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_run_and_compare.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_write_report.py
```

Nothing outside this folder is written. `Step_02` imports
`../Run_0/Step_A_run_ofat.py` for the matching helpers, which are the parent's
`Step_03` functions underneath.

## Files

```
Step_01_calibrate_rule.py          the calibration and its skill
Step_02_run_and_compare.py         the six configurations
Step_03_plots.py                   figures 2-3
Step_04_write_report.py            Run_04_report.docx
outputs/class_summary.csv          basal area by maturity class
outputs/calibration.csv            thresholds, sensitivity, specificity
outputs/roc.csv                    the full ROC curve
outputs/run04_headline.csv         the comparison table above
outputs/expansion_halves.csv       labelled against unlabelled
outputs/expansion_providers.csv    who the unlabelled sites come from
outputs/<config>/matches.csv       site-level matches, and metrics.csv
plots/fig_01_calibration.png       what the rule must separate, and how well
plots/fig_02_criterion_vs_expansion.png   the decisive comparison
plots/fig_03_what_the_expansion_adds.png  where the damage comes from
```
