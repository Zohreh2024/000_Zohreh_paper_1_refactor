# New_proposal/

The space-for-time validation re-run **one change at a time**.

The parent folder settles several questions at once — which sites count as
mature, whether matching is constrained to vegetation, which averaging order,
which predictors, how far is too far. When a result moves under a configuration
that changed four things, nothing can be said about which of the four moved it.

So every run here changes **exactly one** parameter against Run 0 and holds the
rest fixed. A run's difference from Run 0 is then attributable to that
parameter. The runs are comparable to each other *only through Run 0*, never
directly.

**Nothing in `Space_time_validation/` is modified.** This folder imports its
`Step_03` as a module and reuses the matching, the metrics and the bootstrap
unchanged, but selects its own inputs and writes only inside `New_proposal/`.

## Two rules carried through every run

**1. Both nulls, always.** Random cells drawn under the same NVIS constraint,
*and* random cells drawn without it. They answer different questions and neither
alone is the answer:

| null | Run 0 | what it tells you |
|---|---|---|
| unconstrained | ratio **0.210**, ρ **0.029** | the analogue search beats it decisively — this is what shows the method has skill at all |
| NVIS-constrained | ratio **0.445**, ρ **0.205** | the gap to the real runs is small — this is how much of that skill is knowing the vegetation subgroup rather than matching the climate |

Quoting only the first overstates the method; quoting only the second
understates it.

**2. Metrics from the `analogue found` stratum.** A site beyond the no-analogue
cutoff still gets a match — there is always a nearest cell — but that match is
not an analogue. Forced matches inflate the median ratio in the late-century
runs while ρ collapses. Every number here is computed on sites that retained an
analogue, with the no-analogue share reported beside it.

## Run 0 reproduces the published configuration

Before any delta means anything, the baseline has to reproduce. It does,
exactly: present-day analogue 0.491 / ρ 0.300, constrained null 0.445 / 0.205,
unconstrained null 0.210 / 0.029 — the same numbers as the parent folder.

## The run matrix

| run | changed | how |
|---|---|---|
| `run00_baseline` | (none) | 600 mature sites, NVIS-constrained, `eq1_of_mean` |
| `run01_verified_only` | maturity | verified mature only (327 sites) |
| `run02_unconstrained` | matching constraint | no NVIS constraint |
| `run03_mean_of_annual` | averaging order | mean of the annual Eq. (1) M |
| `run04_climate_only` | predictors | the 91 climate columns only |
| `run05_reduced` | predictors | 16 columns: annual climate + key soil |
| `run06_variance_99` | PCA variance | 0.99 instead of 0.95 |
| `run07_cutoff_95` | no-analogue cutoff | 95th percentile instead of 99th |
| `run08_k5` | neighbours | mean of the 5 nearest instead of 1 |
| `run09_noqc` | data quality | without the AGB-vs-basal-area filter (688 sites) |
| `run10_minclass_100` | NVIS fallback | a subgroup needs 100 pool cells, not 25 |

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_A_run_ofat.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_B_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_C_write_report.py
```

About 30 s per run; the nine predictor tables are loaded once and reused.
`--only run00 run02` runs a subset and merges into the existing summary.

## The reading rule that comes first

> **A change that also moves the no-analogue share is not a like-for-like
> comparison.** The metric is then computed on a different set of surviving
> sites, and those survivors are not a random subset — they are the sites whose
> climate still has a counterpart, systematically the wetter and more productive
> ones. ρ can rise simply because the awkward sites were removed.

Runs are flagged on that basis at a threshold of 10 points against Run 0's own
16.1% no-analogue share. Two runs fail it, and **both look like improvements and
are not**:

| run | Δ no-analogue | apparent Δρ | median sites left |
|---|---|---|---|
| `run07_cutoff_95` | **+46 pp** | +0.133 | 97 of 600 |
| `run04_climate_only` | **+65 pp** | −0.115 | 79 of 600 |

Tightening the cutoff discards the marginal matches and ρ duly rises — on a
sixth of the sample. Dropping the soil columns collapses the space to five
components, which shrinks every distance in it, and against a cutoff computed in
that same shrunken space most sites end up with no analogue.

## What actually moves the result

Run 0: median ratio **0.465**, ρ **0.269** across the eight scenario-windows.
Attributable changes only, largest first:

| run | changed | sites | Δρ | Δratio |
|---|---|---|---|---|
| `run09_noqc` | data quality | 688 | **−0.179** | +0.121 |
| `run01_verified_only` | maturity | 327 | **+0.103** | +0.096 |
| `run05_reduced` | predictors | 600 | −0.035 | +0.001 |
| `run02_unconstrained` | matching constraint | 600 | −0.017 | −0.001 |
| `run06_variance_99` | PCA variance | 600 | +0.014 | +0.023 |
| `run10_minclass_100` | NVIS fallback | 600 | +0.001 | −0.000 |
| `run03_mean_of_annual` | averaging order | 600 | **+0.000** | −0.001 |

*(`run08_k5` gains +0.071 but raises the no-analogue share by 12 pp, so it sits
just past the threshold — suggestive, not settled.)*

> **The two changes that move the result are both about the sample, not the
> method.** Removing the biomass-vs-basal-area filter costs 0.179 of rank
> correlation; restricting to stem-verified mature stands gains 0.103. Every
> methodological choice tested moves ρ by less than 0.04, and two of them by
> less than 0.002.

### Run by run

- **`run01` verified-mature only** — both ratio and ρ rise, on half the sample.
  The expected direction, and the cleanest evidence here that the
  likely-mature half carries stands short of their maximum. Cost: 327 sites and
  wider intervals on everything.
- **`run02` unconstrained** — barely moves the future runs, but *raises* the
  present-day analogue's ρ (0.300 → 0.349). The constraint isn't improving the
  match, it's restricting the pool; a site's best climate analogue is sometimes
  in another subgroup. Keep it for the reason it was added, but it isn't buying
  accuracy.
- **`run03` averaging order** — changes nothing, Δρ = +0.000. The cleanest
  possible confirmation that the Jensen gap cancels when numerator and
  denominator are built in the same order.
- **`run06` PCA variance 0.99** — more than doubles the components (18 → 41) and
  changes essentially nothing. The extra components carry noise.
- **`run09` noqc** — the most damaging change tested. ρ collapses while the
  ratio rises toward 1: the same fact twice, since those records contribute
  biomass values unrelated to the stands they describe.
- **`run10` fallback threshold** — nothing measurable. The fallback is rare.

## What to take from this

- **The configuration is not the problem.** Nothing methodological moves ρ by as
  much as 0.04 without also changing which sites survive. Tuning the matcher is
  wasted effort.
- **The sample is the problem.** The data-quality filter and the maturity
  threshold account for essentially all the movement, and both are decisions
  about which observations to admit.
- **Report both nulls, every time.** A ratio quoted against neither is
  uninterpretable.
- **Never read a metric whose no-analogue share moved.** Two of eleven runs
  would have been quoted as gains if the surviving sample hadn't been reported
  alongside.
- **Run 0 remains the configuration to publish.** Run 1 is the one defensible
  alternative and should be reported as a sensitivity, not a replacement —
  halving the sample widens every interval.

## Figures

| figure | what it shows |
|---|---|
| `fig_01_delta_rho.png` | what each single change does to ρ, grey where the sample also changed |
| `fig_02_delta_ratio.png` | the same for the median ratio |
| `fig_03_both_nulls.png` | the runs, the present-day control and **both nulls**, every configuration |
| `fig_04_no_analogue_share.png` | which changes also changed the sample — read this first |
| `fig_05_by_scenario_window.png` | per scenario-window, for the changes that moved the result |

## Outputs

```
outputs/run_matrix.csv            what each run changed
outputs/ofat_summary.csv          one row per run per stratum
outputs/ofat_deltas.csv           every run against Run 0, with the comparability flag
outputs/<run_id>/matches.csv      the site-level matches of that run
outputs/<run_id>/metrics.csv      that run's statistics
New_proposal_report.docx
```
