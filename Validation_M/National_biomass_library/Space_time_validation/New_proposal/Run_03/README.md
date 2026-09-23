# Run_03 — rebuilding biomass from the stem diameters

The one run that needed new code. It produced the largest change any run in
this study has made — and it changed the diagnosis it started from.

## What was proposed, and what the data says

**Proposed:** 12,505 Eucalyptus stems in 199 survey events carry the "single
stemmed acacia trees" allometry; their masses don't scale with diameter;
recompute those records with a eucalypt allometry.

**The first half checks out almost exactly** — 12,471 stems in **exactly** 199
events (TERN 8,985, CSIRO 2,857), and the masses are indeed nonsense: the
largest stem in the group, 479 cm, is assigned **0 kg**.

**The second half does not survive.** The correctly assigned stems fail the
identical test:

| test | value |
|---|---|
| R² of ln(mass) on ln(diameter), **correctly assigned** eucalypt stems | **0.013**, slope −0.195 |
| median ρ(diameter, mass) within subplot | +0.0006 (2,435 subplots, **0%** above 0.9) |
| median ρ within subplot **and** model **and** species | **−0.004** (2,133 groups, **0%** above 0.9) |
| ρ(sum of stems ÷ area, reported plot AGB) | **0.92** |

In the largest single subplot a 0.89 cm stem is assigned 486 kg and a 98 cm stem
48 kg. The library's own documentation says `diameter` is *"the explanatory
variable in the allometric model"* — so within one model and one species, mass
must rise with diameter. It doesn't, anywhere.

> **The mass column is not aligned, row for row, with the stem attributes beside
> it.** The per-survey *sum* is sound (ρ 0.92 against the site table), and a
> permutation preserves a sum.

So the proposed fix can't be carried out: identifying "the mis-allometried
records" needs the model label to correspond to the species, and it doesn't —
the same file assigns "Eucalypt trees" to *Myrsine*, *Zanthoxylum* and *Ficus*.

## What was done instead

Discard the mass column; rebuild from the diameters for all 2,009 surveys with
stem data:

```
AGB(subplot) = a · Σ D^b / subplot area,   averaged over the survey's subplots
```

**No external coefficients are imported, because none are needed.** `b` sets the
*shape* — how strongly a plot is dominated by its largest stems, hence the order
of plots — and is varied across 2.3–2.7 rather than assumed. `a` sets only the
*level*, and is recovered from data already shown sound: it puts the median
rebuilt plot biomass onto the median reported one. **Shape from the stems, level
from the library's own aggregate.**

### The check that matters

Compared against `live_basal_area_ha`, which lives in the **site** table and was
not used to build it — a genuine cross-file test:

| | ρ vs basal area |
|---|---|
| reported plot biomass | **0.31** |
| **rebuilt from diameters** | **0.87** |
| rebuilt vs reported | 0.30 |

A substantial reordering, not a cosmetic one. And the exponent is immaterial:
b = 2.3 and b = 2.7 rank the surveys at **ρ 0.989**, with every result below
moving less than 0.003 across that range.

## The result — paired, on identical sites

`reported_stem_only` and `rebuilt_b2p5` contain the **same 599 sites**, matched
the same way, against the same M′. Only the observed biomass differs.

| configuration | sites | **gate ρ** | ratio | future ρ | null ρ | gap |
|---|---|---|---|---|---|---|
| reported, all | 600 | 0.418 | 0.465 | 0.269 | 0.205 | +0.064 |
| reported, stem sites only | 599 | 0.416 | 0.464 | 0.268 | 0.207 | +0.061 |
| **rebuilt, b = 2.5** | 599 | **0.732** | 0.386 | **0.390** | 0.292 | **+0.098** |
| rebuilt, b = 2.3 / 2.7 | 599 | 0.737 / 0.724 | — | 0.392 / 0.391 | — | +0.097 / +0.093 |

> The present-day gate — M′ against observed biomass at the site's own cell, the
> most direct test in the whole validation — rises from **0.42 to 0.73**. The
> paired control rules out the sample: restricting the published table to the
> same 599 sites reproduces the published numbers almost exactly.

**A substantial part of the "present-day gate does not pass" conclusion was a
property of the library's biomass column, not of M′.**

## It also rescues the sources the filter was excluding

| provider | AGB per m²/ha BA before → after | passes the filter |
|---|---|---|
| **TERN Australia** | 0.08 → 31.6 | 5.7% → **98.1%** |
| **CSIRO** | 15.2 → 16.2 | 74.8% → **100%** |
| University of NSW | 87.3 → **8.6** | (also fixes the Run 2 anomaly) |

The AGB-versus-basal-area consistency filter existed to exclude TERN and CSIRO
wholesale. With the rebuild they pass on their own merits.

### One limitation this exposes

A single global scale constant doesn't suit every plot. TERN's rebuilt median is
about **2,300 t DM/ha** — at or beyond the top of anything Australian forest
carries — because those are 1 ha plots holding stems up to 479 cm and a power law
rewards them heavily. Their *ordering* is now sensible and they're no longer
excluded wholesale, which is what the run set out to achieve; their absolute
*level* should not be quoted.

More generally: because `a` is calibrated to the library's own median, the
**ratio** of M′ to observed biomass is not independent of the library. **The rank
correlation is the robust result here.**

## What to conclude

- The premise was right, the diagnosis wrong — the fault is column alignment,
  not a mis-assigned allometry.
- Rebuilding from diameters works: 0.87 against 0.31 on the cross-file check.
- **The present-day gate largely passes once the observation is sound** — ρ 0.73
  against 0.42 on identical sites. The largest change any run here has produced,
  and attributable to the observation rather than the sample.
- The consistency filter can be retired for these sources.
- Quote the ranking, not the level.
- **This should be reported to the library's custodians.** The defect is in the
  delivered file, and it affects every stem-level use of the National Biomass
  Library.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\Run_03
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_diagnose_allometry.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_recompute_agb.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_run_and_compare.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_write_report.py
```

Nothing outside this folder is written. `Step_02` takes the parent's reference
table and replaces only its `agb` column, so the 174 predictors are untouched
and no climate extraction is repeated. `Step_03` imports
`../Run_0/Step_A_run_ofat.py` for the matching helpers, which are the parent's
`Step_03` functions underneath.

## Files

```
Step_01_diagnose_allometry.py          the diagnosis
Step_02_recompute_agb.py               the rebuild and the reference tables
Step_03_run_and_compare.py             the five configurations
Step_04_plots.py                       figures 2-4
Step_05_write_report.py                Run_03_report.docx
outputs/allometry_diagnosis.csv        the six tests
outputs/mis_assigned_by_source.csv     the 12,471 stems, by provider
outputs/within_group_scaling.csv       the within-group correlations
outputs/rebuild_checks.csv             the cross-file check, per exponent
outputs/agb_rebuilt_by_survey.csv      rebuilt biomass per survey
outputs/reference_table_rebuilt_b*.csv one per exponent
outputs/run03_headline.csv             the comparison table above
outputs/<config>/matches.csv           site-level matches, and metrics.csv
plots/fig_01_mass_vs_diameter.png      the diagnosis
plots/fig_02_cross_file_check.png      rebuilt and reported vs basal area
plots/fig_03_paired_result.png         the paired result
plots/fig_04_exponent.png              the exponent is immaterial
```
