# Roxburgh_validation/

Roxburgh et al. (2019) validated his revised maximum-biomass layer `M′` against
the National Biomass Library with a specific protocol. This folder transplants
that protocol onto the **eight future M′ layers** — the ones whose every
component comes from the random forest — and, as the control, onto the two
present-day layers he scored himself.

Paper: `Paper_reading/roxbrugh-main.pdf` — *A revised above-ground maximum
biomass layer for the Australian continent*, Forest Ecology and Management 432
(2019) 264–275.

## What the protocol is

| his step | what it is | here |
|---|---|---|
| Eq. (2) | `λᵢ = Mᵢ / Oᵢ` per record | computed for every layer |
| Table 4 | ME, RMSE, EF (Eq. 4), LCC (Eq. 5), on untransformed data | `Step_02` |
| Table 2 | Forest / Woodland from NVIS Major Vegetation Subgroups | `Step_01`, verbatim, incl. his east-of-132° restriction on MVS 20/27/45 |
| Fig. 4 | observed against predicted, per layer | `fig_01a–c`, linear axes |
| Fig. 6b | frequency distributions + Kolmogorov–Smirnov | `Step_05`, `fig_03` |
| Fig. 8 | means by state × vegetation class | `Step_05`, `fig_04a/b` |
| §2.4 | spatial autocorrelation of the sample | `Step_05`, `fig_05` |

Two things he did that we cannot: the **satellite forest-cover continuity check**
over 1972–2016, and the **custodian-by-custodian disturbance metadata**
(his Supplementary Appendix A). Between them they took 14,453 records down to
5,739. That missing 60% turns out to matter more than anything else here.

## Running it

```powershell
cd Validation_M\National_biomass_library\Roxburgh_validation
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_build_records.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_fit_statistics.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_sample_sensitivity.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_observation_quality.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_distributions_and_strata.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_06_plots.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_07_write_report.py
```

`Step_01` defaults reproduce **his** sample construction — one row per
observation, no plot-size floor, no year bound. Every flag that departs from
that is named in its `--help` and tagged in the output filenames, so the
variants coexist.

## What a future layer can be asked

Comparing a future M′ against a present-day observation is **not** a validation
of the future. It asks whether the projected layer stays inside the envelope
observed maximum biomass defines, and where it leaves it, in which direction. A
divergence that grows with forcing is the projected change, not an error. The
present-day layers, which *can* be validated, sit beside the future ones in
every table so the two can be told apart.

## Results

### 1. The transplant is correct

Averaged over the records, the layers land on his published continental means:

| class | Original M here | his Table 5 | Revised M here | his Table 5 |
|---|---|---|---|---|
| Forest | 168.7 | 172.1 | 231.0 | 234.4 |
| Woodland | 81.0 | 48.5 | 68.0 | 49.5 |

Forest is close to exact. The rasters are being read on the right grid at the
right places.

### 2. The fit statistics do not reproduce — and the sample is why

| layer | n | ME | RMSE | EF | LCC | Roxburgh's own |
|---|---|---|---|---|---|---|
| Original M | 4,194 | −54.0 | 295.8 | **−0.23** | −0.10 | EF 0.14, LCC 0.25 |
| Revised_M_Roxburgh | 4,194 | −36.1 | 315.6 | **−0.41** | −0.08 | EF 0.40, LCC 0.62 |
| future M′ (8 layers) | 4,194 | −38 to −48 | ~316 | −0.39 to −0.42 | −0.08 | — |

Both present-day layers score **below zero**, meaning neither predicts these
observations better than their own mean. The layer is the same file Roxburgh
scored, so the whole gap belongs to the sample.

`Step_03` walks every sample decision one at a time, scoring the same layer.
Spearman ρ between observed biomass and `Revised_M_Roxburgh`:

| sample | n | ρ |
|---|---|---|
| Roxburgh's construction | 4,194 | **−0.14** |
| one row per site, maximum | 2,472 | −0.07 |
| plot ≥ 0.05 ha | 3,837 | −0.22 |
| plot ≥ 0.50 ha | 1,055 | −0.04 |
| library as at 2017 | 4,194 | −0.14 |
| biomass consistent with basal area | 3,210 | +0.08 |
| mature (verified or likely) | 963 | +0.11 |
| Forest only / Woodland only | 1,695 / 2,337 | −0.03 / −0.11 |
| **all this repo's filters, per site, mature only** | **600** | **+0.42** |

**No single filter recovers the agreement.** Only the full conjunction does,
on 600 of 4,194 records. The positive result the space-time validation reports
is real but narrow: those filters select a subsample on which the layer ranks
sites — not evidence that the layer ranks this library.

### 3. Why the observations cannot resolve it

**The biomass field itself is sound.** Rebuilding each plot figure from the
library's own stem list — summing stem dry mass within each subplot, dividing by
that subplot's area — reproduces the reported value at **ρ = 0.92** over 1,995
surveys, median ratio 1.08. The aggregation, subplot areas and per-hectare
scaling are all correct.

**But the per-hectare figure is dominated by plot size.** ρ(observed, plot area)
= **−0.56**, far stronger than ρ(observed, any layer):

| plot area | records | median observed | median M |
|---|---|---|---|
| ≤ 0.05 ha | 366 | **240** | 133 |
| 0.05–0.15 ha | 1,380 | 162 | 64 |
| 0.15–0.3 ha | 434 | 81 | 55 |
| 0.3–0.45 ha | 958 | 35 | 77 |
| > 0.45 ha | 1,056 | **11** | 98 |

A twenty-fold gradient from sampling geometry alone. A per-hectare figure from a
0.02 ha plot is one large tree multiplied by fifty, and plots that size are laid
out where there is something to measure. Nothing about a location predicts how
large a plot an agency chose there, so no spatial layer can track it.

It is not plot size standing in for region — the effect holds **within** each
provider. Inside Queensland NFPP (1,647 records, uniform 0.4 ha plots) ρ against
`Revised_M_Roxburgh` is **−0.24**. Only DSITI Queensland Herbarium reaches a
useful positive value (+0.39).

This is not a criticism of the library, which is a stem inventory and was never
assembled to be a wall-to-wall biomass map.

### 4. The errors are spatially clustered — his numbers are an upper bound

Residual correlation against separation:

| separation | 0–1 km | 2–5 | 5–10 | 10–20 | 50–100 | 100–200 | 200–500 | > 500 |
|---|---|---|---|---|---|---|---|---|
| correlation | 1.11 | 0.41 | 0.32 | 0.28 | 0.25 | 0.19 | 0.02 | −0.07 |

Roxburgh reports correlations below 0.2 beyond ~10 km and balanced his sample at
a 10 × 10 km scale. Here it does not fall below 0.2 until about **200 km**. A
random 70/30 split of a sample this clustered puts near neighbours on both sides,
so the withheld 30% is not independent and **EF 0.40 / LCC 0.62 flatter what an
independent sample would give**. That is his own §2.4 caveat, extended — and it
narrows the gap against our numbers from the other side.

### 5. What it says about the future layers

They are **indistinguishable** from the historical anchor and from each other
(EF −0.39 to −0.42, LCC −0.08 throughout). Expected, not disappointing: each
future layer differs from the anchor by a few per cent in the median while the
reference carries a twenty-fold plot-size artefact.

The one thing they do say shows in the distribution, not the fit statistics —
**as forcing rises the projection spreads**: the median falls while the upper
tail rises.

| layer | median | p95 | maximum |
|---|---|---|---|
| observed biomass | 53.3 | 771 | — |
| Original M | 90.0 | 272 | 473 |
| Revised_M_Roxburgh | 82.0 | 378 | 1,160 |
| future, SSP126 2035–2064 | 81.0 | 369 | 1,190 |
| future, SSP585 2070–2099 | **72.7** | 347 | **1,450** |

Roxburgh's original M could not exceed 473 t DM ha⁻¹ on these records; his
revision lifted the ceiling to ~1,160 (his Fig. 6b). The future layers keep that
ceiling and raise it with forcing while their medians fall — the same result the
comparison folder reports as a rising spatial coefficient of variation.

## What to conclude

> The protocol transplants correctly and the layers are read correctly, but the
> National Biomass Library as we can filter it **cannot discriminate** between
> these maximum-biomass layers — not between the eight future ones, and not even
> between the original FullCAM layer and Roxburgh's revision of it.

- **Do not quote EF or LCC from this folder as evidence about any layer.** Quote
  them as evidence about the reference.
- **Roxburgh's published statistics are an upper bound**, for the clustering
  reason above.
- **The filtering we cannot reproduce is the likely difference.** Obtaining his
  satellite cover-continuity screen and custodian disturbance metadata, or an
  equivalent, is the single most useful thing that would make this comparison
  work.
- **A plot-size floor is not a substitute.** Requiring ≥ 0.5 ha leaves 1,055
  records and still gives ρ = −0.04.
- **Evaluate the future layers on process instead.** The historical limit
  returning `New_M_2019` exactly, the change factors being bounded and smooth,
  the climate signal ordering with forcing — those are checked in
  `Option_B_matched_footing/` and `FPI_Accuracy_check/Comparison_vs_New_M_2019/`,
  and they are informative in a way this test is not.

## Figures

| figure | what it shows |
|---|---|
| `fig_01a/b/c` | observed against predicted, per layer, with ME/RMSE/EF/LCC and his own values (his Fig. 4, linear axes) |
| `fig_02a` | model efficiency of every layer, bootstrap intervals, his published values as diamonds |
| `fig_02b` | Lin's concordance, same basis |
| `fig_03` | frequency distributions against the observations (his Fig. 6b) |
| `fig_04a/b` | mean biomass by state, Forest and Woodland (his Fig. 8) |
| `fig_05` | spatial autocorrelation of the residual (his §2.4) |
| `fig_06` | **what each sample decision does to the agreement** — the key diagnostic |
| `fig_07` | reported biomass against plot size — the artefact behind it |

Axes are linear throughout. Roxburgh draws his Figs. 3 and 4 on log₁₀ axes with
the statistics computed on untransformed data; we keep his statistics and drop
his axes, because a log axis straightens exactly what these panels need to show.

## Outputs

```
outputs/records.csv                      one row per observation, every layer sampled
outputs/filter_trail.csv                 survivors after each filter
outputs/fit_statistics.csv               his Table 4, every layer
outputs/fit_statistics_by_class.csv      Forest / Woodland
outputs/fit_statistics_by_state.csv
outputs/lambda_summary.csv               his Eq. (2), per layer
outputs/sample_sensitivity.csv           every sample decision, one at a time
outputs/sample_sensitivity_by_class.csv
outputs/observation_quality.csv          the stem rebuild, per survey
outputs/provider_effects.csv             what each provider's biomass tracks
outputs/plot_area_bands.csv
outputs/ks_tests.csv                     his Fig. 6b
outputs/means_by_state_class.csv         his Fig. 8
outputs/spatial_autocorrelation.csv      his Sec. 2.4
Roxburgh_validation_report.docx
```
