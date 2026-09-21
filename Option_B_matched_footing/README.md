# Option_B_matched_footing/

Future M′ on the **Original_M_2004 footing**, so that λ multiplies the layer it
was actually divided by. This is the footing the project uses; the Eq.(1)
footing was retired in September 2026.

```
M'_future  =  λ × Original_M_2004 × Eq1(FPI_future) ÷ Eq1(FPI_1985-2014)
```


## Running it

```powershell
cd Option_B_matched_footing
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_01_recover_lambda_and_original_M.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_02_run_matched_footing.py --jobs 8
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_03_build_fullcam_inputs.py
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python Step_04_verify.py
```

Step 02 takes roughly half an hour for 256 rasters and is idempotent — it
skips if `output_Mprime/` is already populated (`--force` to rebuild).

## The steps

| script | what it does |
|---|---|
| `Step_01_recover_lambda_and_original_M.py` | recovers λ and `Original_M_2004`, which are not in this tree, and proves the recovery against three independently recorded numbers |
| `Step_02_run_matched_footing.py` | invokes the repository's own `Step_08 --footing original2004`, then moves its output here |
| `Step_03_build_fullcam_inputs.py` | the eight window means as FullCAM NetCDF, using `fullcam_io.write_annual` — from the **mean-FPI** layer (see below) |
| `Step_04_verify.py` | four acceptance tests; exits non-zero on failure |

**Step 01 writes outside this folder, deliberately.** `Step_08` reads
`Step_02_published_lambda/output/{lambda_published,original_M_2004}.tif` and has
no flag to change those paths, so Step 01 puts copies there as well as in
`layers/`. Those two files did not previously exist, so nothing was overwritten.

**Step 02 does not reimplement anything.** It runs the pipeline's own Step_08,
so the arithmetic, NaN handling, the `MIN_HIST_M` floor and the metadata are the
pipeline's, not a second version that could drift from it.

## Outputs

| path | contents |
|---|---|
| `layers/` | `lambda_published.tif`, `original_M_2004.tif` |
| `output_Mprime/` | 240 annual + 8 window means + 8 `from_mean_fpi` rasters, `Mprime_summary.csv` |
| `fullcam_inputs/` | `maxAbgMF_<SSP>_<window>.nc` and `.tif`, 8 each |
| `outputs/` | `recovery_checks.csv`, `verification.csv`, `fullcam_inputs_summary.csv`, `step_08_original2004.log` |
| `figures/` | `fig_boundary_repaired.png` / `.pdf` |

To adopt Option B, copy `fullcam_inputs/*.nc` over `FullCAM_input_CSIRO_data/M/`.
Do not do that until the footing decision is made.

### Which averaging order the inputs use (changed Sept 2026)

Step_02 writes each window in two orders, and Eq. (1) is convex so they differ:

| layer | meaning |
|---|---|
| `maxAbgMF_<ssp>_<win>_mean.tif` | `mean_y[Eq1(FPI_y)]` — Eq. (1) per year, then averaged |
| `maxAbgMF_from_mean_fpi_<ssp>_<win>.tif` | `Eq1(mean_y FPI_y)` — the window-mean FPI enters Eq. (1) |

`Step_03` now builds the FullCAM inputs from the **second**, which is what
Eq. (1) is defined on. Roxburgh et al. (2019), Sec. 2, p. 265: FPI "summarises
potential site productivity for any given location", Eq. (1) gives "the
predicted maximum AGB for a given FPI", and "parameter M is constant for any
location in Australia" — one FPI per location in, one M out. The repository said
the same already: `Calculation_future_M_CSIRO/Step_06` names `M_from_mean_fpi`
the layer to use "when feeding a single period value to FullCAM".

It previously used the first. The written inputs are therefore **3.8% to 4.8%
lower** at the median than before:

| | SSP1-2.6 | SSP2-4.5 | SSP3-7.0 | SSP5-8.5 |
|---|---|---|---|---|
| 2035–2064 | −4.2% | −4.8% | −4.4% | −3.9% |
| 2070–2099 | −4.6% | −3.8% | −4.0% | −3.8% |

`--order mean_of_annual` restores the previous behaviour, and every written
NetCDF records which order produced it in its `averaging_order` attribute.

`Step_04_verify.py` follows the same `--order` flag, so it verifies the layer
that is actually written. Tests 1 and 2 are invariant to the choice — the same
numerator appears on both sides of test 1, and it cancels out of test 2's A/B
ratio entirely — and the rerun confirms that empirically (unchanged at
1.9e-04 pp and ×1.456). Only the boundary step moves.

## Recovery checks (Step 01)

λ and `Original_M_2004` are not files in this tree — `Data/Raw/maxAbgM_v1/`
is absent — so both are recovered by division:

```
λ                = maxAbgMF_<ssp>_<win>_mean ÷ M_<ssp>_<win>_mean
Original_M_2004  = New_M_2019 ÷ λ
```

λ is time-invariant, so all eight scenario-windows must agree; the measured
spread between them is **1.9e-06**. Three numbers recorded independently in
`CLAUDE.md` must come out, and the script exits non-zero otherwise:

| check | recovered | expected |
|---|---|---|
| λ median | 1.0000 | 1.0 |
| λ exactly 1 | 42.57% | 42.6% |
| `Original_M_2004` median | 18.653 | 18.65 |

`Data/Processed/maxAbgM_v2/original_M_1970_2002.tif` is **not**
`Original_M_2004` — its median is 31.4, which is Eq.(1) M. Using it would
silently reintroduce the mixed footing.

## Acceptance tests (Step 04)

Three checks, all on the matched footing; the script exits non-zero if any
fails.

**1. The historical limit is exact.** Setting `FPI_future = FPI_historical`
must return `New_M_2019`, since the ratio is then 1. Measured through the
factors Step_08 actually used: median relative error **2.8e-08**, p99 1.0e-07.
This is what makes the FullCAM boundary continuous — the historical input
FullCAM reads and the historical limit of the future inputs are one layer.

**2. The step FullCAM sees is the projected change and nothing else.** On the
matched footing this holds by construction; the test catches a broken rebuild.
Measured on the layers Step_03 writes: **−21.3% to −1.8%** across the eight
scenario-windows, negative in every one.

**3. Every written layer is sound on the grid.** No non-finite value inside the
NLUM mask, nothing outside it, no negative M'. All eight pass.

The Eq.(1)-footing route — λ applied directly to Eq. (1) M, which mixed the two
footings — was retired in September 2026. The A-versus-B comparisons this
folder used to carry (the climate-signal cancellation, the ×1.456 level ratio,
the two-footing boundary figure) went with it and are in the git history.

## An inconsistency this rebuild exposed — read before quoting any change

There are **two different historical baselines** in this repository, built with
different averaging orders, and they do not give the same projected change:

| file | construction | used by |
|---|---|---|
| `Writing_paper_01/output/baseline_M_1985-2014.tif` | λ × mean_y[Eq1(FPI_y)] — Eq.(1) per year, then averaged | the footing memo, the paper figures |
| `Calculation_future_M_CSIRO/output/Eq1_M_hist_1985-2014.tif` | Eq1(mean_y FPI_y) — FPI averaged, then Eq.(1) | **Step_08 itself**, as the denominator of the delta-change ratio |

Eq.(1) is convex above its root, so by Jensen's inequality the per-year order is
always the larger: the per-cell median of the ratio is **1.0319**. The
consequence for the reported change is not small:

| denominator | projected change in M, across the 8 windows |
|---|---|
| `baseline_M_1985-2014.tif` | −23.17% to −3.06% |
| `Eq1_M_hist_1985-2014.tif` (what Step_08 uses) | −18.63% to **+1.13%** |

Two of the eight windows change sign. This is **not** a footing effect — the
footing cancels exactly, as test 1 shows — it is purely the averaging order of
the historical denominator. Which of the two is the intended baseline is a
decision that has not been made anywhere in this repository, and it should be
made explicitly and applied consistently before any change figure is published.

Note that `Footing_decision_M_prime.docx` quotes the first row (−23.17% to
−3.06%) and a level factor of ×1.58, because its diagnostic reconstructed
Option B using `baseline_M_1985-2014.tif`'s convention. The real Step_08 output
in this folder gives ×1.456 and the second row. The memo's central claim — that
the footing does not touch the climate signal — is unaffected and is confirmed
here to 1.9e-04 percentage points.
