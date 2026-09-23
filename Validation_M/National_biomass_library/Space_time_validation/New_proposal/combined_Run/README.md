# combined_Run — the configuration the one-change tests point to

Five decisions together. **Not a one-change test** — reported as a configuration,
with two intermediate rungs so it stays decomposable.

| # | decision | from | why |
|---|---|---|---|
| 1 | biomass **rebuilt from stem diameters**, b = 2.5 | Run_03 | the stem-mass column isn't aligned with the stem attributes; rebuilding lifted the gate 0.416 → 0.732 on identical sites |
| 2 | **AGB-vs-basal-area floor retired** | Run_03 | it existed to exclude TERN and CSIRO wholesale; after the rebuild they pass on merit (5.7 → 98.1%, 74.8 → 100%) |
| 3 | **plot-area threshold 0.04 ha** | Run_02 | readmits 201 DELWP Victoria visits at exactly 0.04 ha, 225 Mg/ha on 30.8 m²/ha, ratio 7.3 |
| 4 | **ceiling on the AGB-to-basal-area ratio** | new | replaces the plot-area floor as the inflation control, at the 95th percentile of the verified-mature group rather than a round number |
| 5 | **DBH maturity filter kept** | Run_04 | every basal-area threshold drove the gate to ≤ 0 once unlabelled sites entered; M′ is a ceiling, so validating it needs stands near maximum |

## Building the table

| step | sites |
|---|---|
| base table: 0.04 ha, no consistency floor | 2,389 |
| DBH maturity filter | 877 |
| rebuilt biomass available | 877 |
| ratio at or below the ceiling (34.5) | **850** |

**850 sites** against Run 0's 600, and **147 south of 37°S** against 4. The
ceiling is calibrated *after* the rebuild, on rebuilt values, because the
reported ratios are exactly what the rebuild exists to correct.

### The ceiling didn't do what it was asked to do

It was proposed to remove University of NSW (~106) and Queensland Herbarium
(35.6). Those are **reported** ratios — and the rebuild has already repaired
them: UNSW falls to **8.6** once biomass comes from the diameters. The stated
targets no longer exist by the time the ceiling is applied.

> It still earns its place, for a different reason. At **34.5** Mg per m²/ha it
> removes 27 sites, **17 of them TERN** with a median rebuilt biomass near
> **3,989 t DM/ha** — precisely the over-estimation Run_03 flagged as its own
> main limitation, where one global scale constant rewards TERN's 1 ha plots
> with 479 cm stems far too heavily. **The ceiling is the control for the
> rebuild's weakness, not for the reported data's.**

Note 34.5 isn't comparable with the ratio figures in earlier runs, which used
reported biomass. The rebuild raises biomass, so the whole distribution moves —
this table's median ratio is 17.5 where Run 0's was 10.2.

## The result

| configuration | sites | south | **gate ρ** | ratio | future ρ | null ρ | **gap** |
|---|---|---|---|---|---|---|---|
| Run 0 as published | 600 | 4 | 0.418 | 0.465 | 0.269 | 0.205 | +0.064 |
| + biomass rebuilt | 599 | 4 | 0.732 | 0.386 | 0.390 | 0.292 | +0.098 |
| + floor retired + ceiling, 0.05 ha | 667 | 33 | 0.784 | 0.384 | 0.464 | 0.401 | +0.063 |
| + 0.04 ha, no ceiling | 877 | 161 | 0.857 | 0.351 | 0.624 | 0.505 | +0.119 |
| **all four combined** | **850** | **147** | **0.844** | 0.356 | **0.602** | 0.473 | **+0.129** |

> Gate **0.844** against Run 0's 0.418; future ρ **0.602** against 0.269; gap
> **+0.129** against +0.064 — on 850 sites rather than 600, with 147 south of
> 37°S rather than 4. **The best configuration on every axis this study
> measures.**

### Where it is *not* additive

The rebuild does most of the gate work (0.418 → 0.732). The 0.04 ha threshold
does most of the rest (0.784 → 0.857). But on the **gap** the ingredients
interact:

- Retiring the floor + adding the ceiling at 0.05 ha gives a gap of **+0.063** —
  *below* the rebuild alone at +0.098, because the null rises faster than the
  runs on that sample.
- Only when 0.04 ha is added does the gap recover, to +0.129.

**Any of these decisions judged on its own would have been judged differently
from how it behaves in combination.**

The ceiling is worth keeping on the *gap* rather than the gate: it costs
0.857 → 0.844 on the gate but raises the gap +0.119 → +0.129, since it lowers
the null more than the runs. With the Run_03 limitation, both reasons agree.

## What to be careful about

- **The nulls rise with the runs** — 0.205 → 0.473. Much of the raw correlation
  gain is that the cleaned sample is easier to rank at all. The gap is the
  honest measure, and it doubles: real, but smaller than the headline suggests.
- **The ratio isn't independent of the library.** Run_03's scale constant is
  calibrated to the library's own median. Quote ρ and the gap.
- **This is a configuration, not an experiment.** The ceiling has never been
  tested on its own against Run 0.
- **No-analogue rises** 16.1% → 19.7%, and the late-century high-forcing windows
  remain extrapolation exactly as under every other configuration.
- **The southern sites are one provider** — DELWP Victoria. A real gain on a
  narrow base.

## What to do with it

- **Report this as the corrected configuration, Run 0 as published.** The
  difference is the headline of the whole exercise: the present-day gate goes
  from 0.42 to 0.84 once the observation is sound and the sample isn't
  needlessly cut.
- **Don't present it as a one-change result.** Point to Run_03, Run_02, Run_04
  and this folder's intermediate rungs.
- **Test the ceiling on its own** before relying on it.
- **The stem-mass alignment defect still needs reporting to the library's
  custodians.** Everything here works around it.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\combined_Run
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_build_table.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_run_and_compare.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_write_report.py
```

`Step_01` imports the parent's `Step_01_build_reference_table.py`, patches
`MIN_AREA_HA` and `OUT_DIR` in the imported module and calls its `main()` with
`--keep-inconsistent-agb`; the parent file is never modified and nothing is
written outside this folder. The rebuilt biomass is taken from
`../Run_03/outputs/agb_rebuilt_by_survey.csv` unchanged, so the two folders
cannot drift apart. `Step_02` imports `../Run_0/Step_A_run_ofat.py` for the
matching helpers.

## Files

```
Step_01_build_table.py                 the five decisions and the calibration
Step_02_run_and_compare.py             the five configurations
Step_03_plots.py                       three figures
Step_04_write_report.py                Combined_run_report.docx
outputs/reference_table_combined.csv   850 sites
outputs/reference_table_base.csv       2,389 sites, before maturity and ceiling
outputs/build_trail.csv                the build
outputs/ceiling_calibration.csv        where 34.5 came from
outputs/provider_effects.csv           what each provider contributes
outputs/combined_headline.csv          the ladder table above
outputs/<config>/matches.csv           site-level matches, and metrics.csv
plots/fig_01_ladder.png                what each ingredient adds
plots/fig_02_coverage.png              where the sample grew
plots/fig_03_ceiling.png               where the ceiling sits
```
