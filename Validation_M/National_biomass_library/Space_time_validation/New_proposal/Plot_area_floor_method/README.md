# Plot_area_floor_method — Run 2

A **plot-area floor instead of the maturity filter**. Six floors, against Run 0
(mature, 600 sites) and Run 1 (verified only, 327 sites).

Everything else is held at Run 0: NVIS-constrained matching, `eq1_of_mean`, all
174 predictors, PCA to 95%, 99th-percentile cutoff. Both nulls in every
configuration; every metric from the `analogue found` stratum.

## Why this run follows from Run 1

Run 1 removed the likely-mature half and the result improved — but its
diagnostic found the mechanism, and the mechanism wasn't maturity:

| class | n | ratio | ρ | observed AGB | AGB per m²/ha BA | plot area |
|---|---|---|---|---|---|---|
| verified mature | 327 | 0.61 | 0.49 | 117.5 | 7.3 | 0.40 ha |
| likely mature | 273 | 0.34 | 0.39 | 109.8 | **17.4** | **0.24 ha** |

Almost the same biomass; 2.4× the inflation; plots 40% smaller. That group isn't
less mature, it's more inflated. So the maturity threshold is a **proxy**, and
filtering on the thing itself should work better — and cheaper, since the
maturity filter throws away every site with no stem data at all (1,088 of 1,688)
whether or not it was well measured. A floor keeps them.

## The floor removes the inflation directly

| floor | sites | median plot | median AGB per m²/ha BA |
|---|---|---|---|
| none (Run 0, mature) | 600 | 0.24 ha | 10.2 |
| ≥ 0.10 ha | 1,326 | 0.25 ha | 7.1 |
| ≥ 0.20 ha | 871 | 0.40 ha | 6.3 |
| ≥ 0.25 ha | 676 | 0.50 ha | 5.2 |
| ≥ 0.30 ha | 607 | 0.50 ha | 5.0 |
| ≥ 0.40 ha | 584 | 0.50 ha | 4.8 |
| ≥ 0.50 ha | 365 | 0.50 ha | 4.0 |

Monotone, and at 0.25 ha the sample is **larger than Run 0's 600** at half the
inflation.

## The ratio rises past 1 — and so does its null

> Raising the floor removes the inflation, which is the point. But it also
> lowers the observed biomass of whatever survives, because larger plots report
> less biomass per hectare. So **any** ratio of M′ to observed biomass rises as
> the floor rises — for every M′, including a random one.

| configuration | sites | median ratio | its constrained null | difference |
|---|---|---|---|---|
| Run 0: mature, no floor | 600 | 0.465 | 0.445 | +0.020 |
| Run 1: verified only | 327 | 0.557 | 0.478 | +0.079 |
| ≥ 0.25 ha | 676 | 1.204 | 0.992 | +0.212 |
| ≥ 0.30 ha | 607 | 1.274 | 1.141 | +0.133 |
| **≥ 0.40 ha** | **584** | **1.275** | 1.102 | **+0.173** |
| ≥ 0.50 ha | 365 | 1.441 | 1.255 | +0.186 |

M′/AGB goes from 0.465 to **1.275** — M′ ends up *above* observed biomass, the
direction a maximum should err in, and the opposite of the under-prediction the
published gate reports. **The present-day gate failure is largely an artefact of
small plots.** But the null moves the same way, so the ratio alone proves
nothing. This is exactly why both nulls are carried.

## The gap to the null is where the answer is

| configuration | sites | ρ | null ρ | **gap vs constrained** | gap vs unconstrained |
|---|---|---|---|---|---|
| Run 0: mature, no floor | 600 | 0.269 | 0.205 | +0.064 | +0.240 |
| Run 1: verified only | 327 | 0.371 | 0.286 | +0.084 | +0.426 |
| ≥ 0.10 ha | 1,326 | 0.155 | 0.141 | +0.015 | +0.173 |
| ≥ 0.20 ha | 871 | 0.118 | 0.151 | **−0.033** | +0.086 |
| ≥ 0.25 ha | 676 | 0.244 | 0.210 | +0.034 | +0.268 |
| ≥ 0.30 ha | 607 | 0.338 | 0.230 | +0.107 | +0.312 |
| **≥ 0.40 ha** | **584** | 0.351 | 0.223 | **+0.128** | +0.357 |
| ≥ 0.50 ha | 365 | 0.447 | 0.339 | +0.107 | +0.410 |
| 0.25 ha **and** mature | 298 | 0.372 | 0.380 | **−0.007** | +0.408 |

> **≥ 0.40 ha is the best configuration**: 584 sites against Run 1's 327 — 79%
> more — and a gap of **+0.128** against Run 1's +0.084 and Run 0's +0.064.

Two results there need caution rather than celebration:

- **The sweep is not monotone.** The 0.20 ha floor falls *below* its own null
  (−0.033) while 0.10 and 0.25 sit above it. With a few hundred sites and a
  small rank correlation, differences of 0.03–0.05 are within what the sample
  resolves. Read the **0.30–0.50 ha block** (gap consistently +0.107 to +0.128),
  not any single floor.
- **Do not stack the two filters.** 0.25 ha *plus* maturity leaves 298 sites and
  a gap of −0.007 — no skill above the null at all. They are redundant, not
  complementary: they remove the same records, and stacking them strips out the
  variation the matching needs in order to have anything to rank.

## What to conclude

- Run 1 was **right about the effect, wrong about the cause**. The
  likely-mature half dragged the numbers down because those plots are small, not
  because those stands are immature.
- **A plot-area floor is the better filter** — 79% more sites and half again the
  skill above the null.
- **The published under-prediction should not be quoted without this.** With a
  0.40 ha floor M′ sits above observed biomass rather than at half of it.
- **Choose from the 0.30–0.50 ha block**, not a single value.
- This is still a one-change test against Run 0 and inherits its limits — the
  late-century high-forcing windows are extrapolation under every configuration,
  and no floor repairs that.

## Running it

```powershell
cd Validation_M\National_biomass_library\Space_time_validation\New_proposal\Plot_area_floor_method
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_run_area_floors.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_compare.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_write_report.py
```

About 30 s per configuration. `Step_01` imports `../Run_0/Step_A_run_ofat.py`
for its helpers — which are the parent's `Step_03` functions underneath — so the
matching, metrics and bootstrap are unchanged and nothing outside this folder is
written.

## Files

```
Step_01_run_area_floors.py        the nine configurations
Step_02_compare.py                the comparison and the figures
Step_03_write_report.py           Plot_area_floor_report.docx
outputs/config_matrix.csv         what each configuration is
outputs/area_floor_summary.csv    one row per configuration per run
outputs/area_floor_comparison.csv the tables above
outputs/<config>/matches.csv      site-level matches, and metrics.csv
plots/fig_01_ratio_and_rho.png    the sweep, with both nulls
plots/fig_02_gap_to_null.png      the decision figure
plots/fig_03_tradeoff.png         sites kept against skill gained
```
