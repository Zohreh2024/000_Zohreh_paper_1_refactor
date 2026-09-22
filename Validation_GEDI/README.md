# Validation_GEDI/

Testing M′ against **GEDI L4A** — spaceborne lidar estimates of above-ground
biomass density, 2019–2024 — in six forested regions: `vic_central`,
`vic_gippsland`, `tasmania`, `nsw_southeast`, `nsw_north_seqld`, `wa_southwest`.

**The subject is the eight future M′ layers**, every component of the ratio
produced by the random forest. `New_M_2019` is the control.

## The one thing to understand first

> M′ is a **maximum**: the biomass a site could carry at maturity. GEDI measures
> what actually stands there now, after clearing, logging and fire. GEDI *below*
> M′ is the expected case and proves nothing. **GEDI above M′ is the only direct
> evidence against M′**, so every headline number here is an exceedance rate,
> never an R².

Applied to a *future* M′ this sharpens: present-day biomass exceeding a future
maximum says a stand **already** carries more than the model claims its site
will support decades from now. Not impossible — a drying climate can lower a
ceiling below the standing stock — but it is a strong, checkable claim, and the
rate should order with forcing if the projection is doing what it says.

## Why New_M_2019 is the control, not a rival

Every future layer is

```
M'_future = New_M_2019 × Eq1(mean FPI_future) ÷ Eq1(mean FPI_1985-2014)
```

which collapses to `New_M_2019` exactly when future FPI equals historical FPI.
The anchor **is** the historical limit of all eight. So a difference between a
future layer and the anchor is the projected climate change and nothing else —
same cells, same footprints, same fire treatment, same footing.

## Running it

```powershell
cd Validation_GEDI
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_check_sources.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_build_fire_mask.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_fetch_gedi.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_aggregate_cells.py --tag New_M_2019
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04b_attach_future_M.py
conda run --no-capture-output -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_05_analyse_vs_M.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_06_write_future_M_report.py
```

Steps 1–4 are the expensive ones (Step 3 downloads granules; Step 4 reads a
532 MB footprint table). **Step 4b exists so they are run once**: everything Step
4 computes from the footprints — the per-cell statistics, the fire flags, the
mean FPI — is independent of which M′ layer it is compared against, so Step 4b
re-samples the eight future layers at the same NLUM cell indices instead of
redoing the aggregation eight times.

| script | what it does |
|---|---|
| `Step_01_check_sources.py` | confirm the GEDI and MODIS collections resolve |
| `Step_02_build_fire_mask.py` | MODIS burned area → `fire/burn_year_*.tif` |
| `Step_03_fetch_gedi.py` | fetch L4A granules → `outputs/gedi_l4a_footprints.parquet` |
| `Step_04_aggregate_cells.py` | footprints → NLUM cells, attach M′ and FPI, apply fire flags |
| `Step_04b_attach_future_M.py` | attach the eight future layers to those cells |
| `Step_05_analyse_vs_M.py` | every statistic and figure |
| `Step_06_write_future_M_report.py` | `Validation_GEDI_future_M_report.docx` |

## Results

All on fire-excluded cells (133,429 of them), which drop any footprint whose
cell burned within the recovery window before acquisition.

### 1. The projection does not make the ceiling problem worse

| layer | median M′ | mean exceeds | p95 (n=30) exceeds | p95 of lower bounds exceeds |
|---|---|---|---|---|
| **New_M_2019 (anchor)** | 189.7 | 16.7% | 48.1% | 45.6% |
| SSP126 2035–2064 | 192.2 | 16.4% | 47.8% | 45.3% |
| SSP585 2035–2064 | 189.2 | 16.7% | 48.5% | 46.0% |
| SSP245 2070–2099 | 197.6 | 15.7% | 46.7% | 44.3% |
| SSP585 2070–2099 | 192.2 | 16.2% | 48.5% | 45.7% |

Across all eight the cell mean exceeds M′ in **15.7–16.7%** of cells against
**16.7%** for the anchor — a range of one percentage point, straddling the
anchor rather than moving away from it. The future layers are not contradicted
by measured biomass any more than the layer they are built from is.

Note what that also says about the anchor, which the future layers inherit:
GEDI's upper envelope exceeds M′ in **48%** of cells, and still **46%** when
every footprint is pushed to the bottom of its 90% interval. That is a
pre-existing property of `New_M_2019` in tall wet forest, and no projection
built by scaling that layer can fix it.

### 2. The change is small where GEDI can see it, and it widens rather than shifts

Future M′ ÷ anchor, cell by cell:

| layer | median | p10–p90 |
|---|---|---|
| SSP126 2035–2064 | 1.003 | 0.954–1.081 |
| SSP585 2035–2064 | 0.991 | 0.921–1.103 |
| SSP126 2070–2099 | 0.996 | 0.925–1.104 |
| SSP585 2070–2099 | **0.988** | **0.843–1.222** |

The median cell moves by under 2% under any scenario. What grows with forcing is
the **spread** — the p10–p90 band widens from 0.13 to 0.38. The projection
redistributes M′ here rather than shifting it, matching the rising spatial
coefficient of variation reported in
`FPI_Accuracy_check/Comparison_vs_New_M_2019/`.

This is also the main limitation. GEDI's footprints sit in tall wet forest —
precisely where the projected change is smallest. The deepest projected losses
fall in low- and mid-biomass cells that GEDI barely samples. **A test that
cannot see where the change is cannot be asked whether the change is right.**

### 3. The mechanism, tested across space — the projected change may be too *small*

Future M′ is present M′ scaled by `Eq1(FPI_future)/Eq1(FPI_hist)`, so the
projection's whole assumption is how much biomass a change in FPI buys. GEDI
can't see 2035–2100, but it can be asked the same question across space today.
Log-log slopes on closed evergreen-broadleaf cells (79,527 of them):

| elasticity of biomass w.r.t. FPI | slope |
|---|---|
| **Eq. (1)**, at the median FPI of 11.0 | **1.36** |
| M′ layers, across space | 1.11–1.18 |
| **GEDI p95 (n = 30)** | **1.67** (95% CI 1.64–1.69) |
| **GEDI cell mean** | **1.81** |

The observed gradient is **steeper** than the projection assumes, and the
confidence interval is narrow. Read in the direction that matters: Eq. (1)
converts a given change in FPI into a *smaller* change in biomass than the
observed spatial gradient implies, so if the space-for-time substitution holds,
a future decline in FPI should move M′ **further** than these layers move it.

Three reasons not to lean hard on it: a spatial gradient is not a temporal
response; GEDI's envelope is standing biomass rather than a maximum, so its
slope mixes the ceiling with how close stands have grown to it; and the
comparison is restricted to closed evergreen-broadleaf forest, where the FPI
range is narrowest.

## What to conclude

> GEDI does not contradict the future M′ layers, and it cannot confirm them.
> What it establishes is that the projection inherits the anchor's existing
> ceiling problem without adding to it, and that the mechanism driving the
> projected change is conservative relative to the observed spatial gradient.

- Quote the exceedance rates as a statement about **the anchor**, not about the
  scenarios — they differ by about half a percentage point across eight layers.
- The elasticity comparison is the one result bearing on the **size** of the
  projected change. Quote it with the space-for-time caveat attached.
- Nothing here tests a projected *level*.

## The retired Option A layer

This folder used to compare two present-day layers: `New_M_2019` (matched
footing, Option B) and `baseline_M_1985-2014` (Eq. (1) footing, Option A). That
footing was retired across the repository in September 2026, and `Step_05` no
longer scores it by default.

**Nothing was deleted.** The cell tables are still in `outputs/`, and

```powershell
python Step_05_analyse_vs_M.py --legacy-option-a
python make_validation_gedi_report.py
```

regenerates the older `Validation_GEDI_report.docx`, which is built around the
A-versus-B comparison. Run without that flag, `make_validation_gedi_report.py`
stops with a message saying so rather than failing obscurely.

## Figures

| figure | what it shows |
|---|---|
| `fig1_p95_vs_Mprime_anchor.png` | **control** — GEDI's upper envelope against the anchor, cell by cell |
| `fig2_future_exceedance.png` | **the headline** — how often present-day biomass already exceeds each projected future maximum, with the anchor as a dotted reference |
| `fig2_exceedance_by_fpi_bin.png` | exceedance by FPI bin, every layer |
| `fig3_map_p95_over_Mprime.png` | where the exceedance is |
| `fig4_fpi_elasticity_index.png` | how steeply biomass rises with FPI — GEDI against Eq. (1) and the layers |
| `fig5_exceedance_by_region.png` | exceedance by region, every layer |
| `fig6_future_over_anchor.png` | how much the projection moves M′ where GEDI can see it |

`fig1_p95_vs_Mprime_both_layers.png` is the superseded two-layer version kept
for the legacy report.

## Outputs

```
outputs/gedi_l4a_footprints.parquet          the footprints, 532 MB
outputs/gedi_cells_{all,unburnt}_*.csv       one per M' layer
outputs/analysis/overall_by_layer.csv        exceedance rates, every layer
outputs/analysis/future_over_anchor.csv      each future layer against the anchor
outputs/analysis/future_over_anchor_by_region.csv
outputs/analysis/fpi_elasticity.csv          the mechanism test
outputs/analysis/by_fpi_bin.csv, by_region.csv, by_forest_class.csv
outputs/analysis/footprint*.csv              the GEDI sample itself
Validation_GEDI_future_M_report.docx         the current report
Validation_GEDI_report.docx                  the legacy present-day report
```
