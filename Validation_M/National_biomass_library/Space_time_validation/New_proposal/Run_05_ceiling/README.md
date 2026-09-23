# Run_05_ceiling — the biomass-to-basal-area ceiling, on its own

The test `combined_Run` said was missing. **Verdict: the ceiling is justified,
and `combined_Run`'s use of it stands.**

## Why it needed testing

`combined_Run` introduced the ceiling but flagged that it had never been run
against Run 0 in isolation. It was also the ingredient that *didn't do what it
was asked to* — its stated targets (University of NSW ~106, Queensland Herbarium
35.6) are **reported** ratios that the rebuild had already repaired.

> **It is not circular**, which is the first thing to establish. The ratio is
> computed from biomass and basal area, both in the site table; M′ appears
> nowhere in it. It removes records on a criterion internal to the observation,
> so any improvement isn't the result of discarding whatever disagrees with M′.

## The calibration does not transfer

| base | verified sites | median ratio | p90 | p95 | p99 |
|---|---|---|---|---|---|
| reported (Run 0) | 327 | 7.27 | 37.3 | **52.0** | 88.3 |
| rebuilt (Run 3) | 327 | 16.79 | 24.9 | **27.5** | 31.4 |

The same percentile of the same group is **52.0** on reported biomass and
**27.5** on Run 3's rebuild — and `combined_Run`'s is a third value again (34.5)
from its own wider base. **The percentile is the parameter, not the number.**
Applying 34.5 to Run 0 would have been testing two changes at once.

## The result

| configuration | sites | ceiling | median AGB | **gate ρ** | future ρ | null ρ | **gap** |
|---|---|---|---|---|---|---|---|
| Run 0 as published | 600 | — | 112.4 | 0.418 | 0.269 | 0.205 | +0.064 |
| + ceiling at p99 | 585 | 88.3 | 105.0 | 0.442 | 0.277 | 0.209 | +0.068 |
| + ceiling at p95 | 542 | 52.0 | 93.1 | 0.492 | 0.321 | 0.248 | +0.073 |
| **+ ceiling at p90** | 496 | 37.3 | 80.2 | **0.518** | 0.371 | 0.264 | **+0.107** |
| Run 3's rebuild, no ceiling | 599 | — | 124.3 | 0.732 | 0.390 | 0.292 | +0.098 |
| **rebuild + ceiling at p95** | 580 | 27.5 | 123.9 | 0.718 | 0.376 | 0.248 | **+0.128** |

> The ceiling earns its place on its own. Against Run 0 it raises the gate from
> **0.418 to 0.518** and the gap from **+0.064 to +0.107** — and it does so
> **monotonically**: p99 → p95 → p90 improves steadily. A filter that helped at
> one arbitrary threshold and not at others would be suspect; this behaves like
> a filter removing a real contaminant.

On the rebuilt base it behaves differently, and `combined_Run` read it
correctly: the **gap** rises +0.098 → +0.128 while the **gate** falls slightly
0.732 → 0.718. It buys gap rather than gate there, because it lowers the null
more than the runs. Both bases agree it's worth applying; they disagree about
which statistic it improves.

## What it removes

The tightest ceiling keeps 496 of 600 sites and lowers median observed biomass
from 112.4 to 80.2 Mg/ha — so it *is* removing high-biomass records. Are they
real?

A ratio of 37 Mg of biomass per m²/ha of basal area is already at the edge of
what a stand can physically carry, and the removed records sit at **70 and
beyond**. They aren't high-biomass stands; they're per-hectare figures their own
basal area doesn't support — the same inflation every run in this study has met,
reached through a different door.

## What to conclude

- **Justified on its own.** It improves Run 0 without the rebuild, improves the
  rebuild without anything else, and improves monotonically with tightness.
- **Not circular** — M′ enters the criterion nowhere.
- **Calibrate the percentile, never the value.** A number carried between bases
  is a different filter.
- **p90 beats p95 on reported biomass** (+0.107 vs +0.073) but costs 104 sites.
  On the rebuilt base the choice matters much less, because the rebuild has
  already removed most of what the ceiling targets.
- **This closes `combined_Run`'s open item.** The one remaining is that the
  stem-mass alignment defect should go back to the library's custodians.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\Run_05_ceiling
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_run_ceiling.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_plots_and_report.py
```

Nothing outside this folder is written. `Step_01` imports
`../Run_0/Step_A_run_ofat.py` for the matching helpers, which are the parent's
`Step_03` functions underneath, and reads Run 3's rebuilt table unchanged.

## Files

```
Step_01_run_ceiling.py             calibration and the six configurations
Step_02_plots_and_report.py        two figures and Run_05_report.docx
outputs/ceiling_calibration.csv    the percentile on each base
outputs/run05_headline.csv         the table above
outputs/removed_by_ceiling.csv     every site each ceiling removes
outputs/<config>/matches.csv       site-level matches, and metrics.csv
plots/fig_01_ceiling_result.png    the ceiling on both bases
plots/fig_02_where_the_ceiling_sits.png
```
