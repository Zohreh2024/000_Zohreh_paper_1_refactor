# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Python environment

**Always use the `JinzhuLuto` conda environment.** Never use `base`, and never call a
bare `python` — the machine has ~30 conda envs and no env is auto-activated
(`auto_activate_base` is `false`), so a bare `python` resolves to
`C:\Program Files\Python36\python.exe`, which is the wrong interpreter.

```
Name:   JinzhuLuto
Path:   C:\ProgramData\Anaconda3\envs\JinzhuLuto
Python: 3.8.19
```

### Running code

Run every script, module, and one-off snippet through `conda run`:

```powershell
conda run -n JinzhuLuto python <script.py> [args]
conda run -n JinzhuLuto python -c "import rasterio; print(rasterio.__version__)"
conda run -n JinzhuLuto pip list
```

**If `-n JinzhuLuto` fails with `EnvironmentLocationNotFound`, use the full prefix
path instead** — some shells on this machine put *miniconda3* on `PATH` rather than
Anaconda3, and `~/.condarc` sets `envs_dirs` to `F:\Zohreh\conda_env` and
`C:\ProgramData\Anaconda3\envs\zoenv`, neither of which contains `JinzhuLuto`:

```powershell
conda run -p "C:\ProgramData\Anaconda3\envs\JinzhuLuto" python <script.py>
```

`-p` takes an absolute prefix and ignores `envs_dirs`, so it works from any shell.

Use `--no-capture-output` when the command has live progress output (`tqdm` bars,
long downloads) — otherwise `conda run` buffers stdout until the process exits:

```powershell
conda run --no-capture-output -n JinzhuLuto python Step_0_download_data\download_worldclim_cmip6.py
```

Installing packages goes through the same env:

```powershell
conda install -n JinzhuLuto <pkg>
conda run -n JinzhuLuto pip install <pkg>
```

## Repository layout

Numbered step directories run in order; each is a self-contained stage of the
pipeline.

| Path | Purpose |
|---|---|
| `Step_0_download_data/` | Fetch raw rasters, then clip/reproject them to NLUM |
| `Step_1_RF_for_FPI/` | Random forest predicting future FPI from soil + climate |
| `Data/Raw/` | Untouched downloads, one sub-directory per variable |
| `Data/Processed/` | NLUM-matched output, mirrors `Data/Raw/`'s sub-directories |
| `Data/NLUM_Mask/` | `NLUM_2010-11_mask.tif`, the reprojection template |

Scripts in `Step_0_download_data/`:

| Script | Purpose |
|---|---|
| `download_worldclim_cmip6.py` | CLI. ACCESS-CM2 future scenarios, 64 multi-band tif |
| `download_worldclim_historical.py` | CLI. WorldClim 2.1 historical 1970-2000, 4 zips -> 55 tif |
| `download_fpi.py` | CLI. Forest Productivity Index, 37 map-sheet tiles from data.gov.au |
| `reproject_match_NLUM.py` | Plain script, run top-to-bottom. Clips/reprojects/fills every variable |
| `mosaic_match_fpi_NLUM.py` | Plain script. Mosaics the 37 FPI tiles per year, then matches to NLUM |

All three downloaders share the resumable `download()` from
`download_worldclim_cmip6.py` — import it rather than writing new download logic.

Scripts in `Step_1_RF_for_FPI/` (run in order):

| Script | Purpose |
|---|---|
| `Step_01_organise_input_files.py` | Build `data/X_data.nc` (67 bands) and `data/Y_data.nc` |
| `Step_02_build_model.py` | Fit the random forest, write `data/random_forest_model.pkl` |
| `Step_03_prediction.py` | Predict FPI for each scenario x period -> `output/*.tif` |

`Data/Raw/` sub-directories and their contents:

| Directory | Contents |
|---|---|
| `bioc/` | CMIP6 **future** bioclimatic, 16 files x 19 bands |
| `prec/` | CMIP6 **future** precipitation, 16 files x 12 bands |
| `tmax/` | CMIP6 **future** maximum temperature, 16 x 12 bands |
| `tmin/` | CMIP6 **future** minimum temperature, 16 x 12 bands |
| `hist_bio/` | WorldClim **historical** bioclimatic, 19 single-band files |
| `hist_prec/` | WorldClim **historical** precipitation, 12 single-band files |
| `hist_tmax/` | WorldClim **historical** maximum temperature, 12 files |
| `hist_tmin/` | WorldClim **historical** minimum temperature, 12 files |
| `fpi/<tile>/` | Forest Productivity Index, 37 tiles x 53 yearly rasters |
| `soil_N/` | Soil total nitrogen, 6 depth slices |
| `soil_P/` | Soil phosphorus, 6 depth slices |
| `data_for_openPan/` | Inputs for the openPan step |
| `_worldclim_zips/`, `_fpi_zips/` | Download caches; safe to delete once extracted |

**Historical vs future are separate directories on purpose.** Training uses
historical, prediction uses future, and both must be clipped/reprojected/filled
identically or the model is fitted and applied on different footings. Note the
variable code differs between products: historical bioclim is `bio`, CMIP6
bioclim is `bioc`.

**Every FPI zip contains identically named rasters** (`1970_001.tif` ...
`2022_001.tif`) with no tile prefix, so each tile must extract into its own
`fpi/<tile>/` sub-directory or the 37 tiles overwrite one another.

## Conventions

- **Never rename downloaded files.** Raw rasters keep the provider's original
  file name (e.g. `wc2.1_30s_bioc_ACCESS-CM2_ssp245_2021-2040.tif`) so they stay
  traceable to the source.
- **`Data/Raw/` sub-directories are named for the provider's variable code**, so
  no name mapping is needed anywhere in the pipeline — WorldClim's `bioc` lives
  in `Data/Raw/bioc/`, `tmin` in `Data/Raw/tmin/`, and so on.
- **Raw data is read-only.** Never write derived output into `Data/Raw/` — each
  step writes to its own output location.
- Downloads are large (single WorldClim rasters run 5–22 GB). Prefer resumable,
  skip-if-present logic over re-fetching, and check `Data/Raw/` before downloading.
- `Data/` lives on the `N:` mapped drive, which resolves to the UNC path
  `\\shares.deakin.edu.au\school-les-m\Planet-A\...`. Python's `Path.resolve()`
  expands `N:` to that UNC form — this is the same location, not an error.
- Parallel work uses `joblib` with `backend="threading"` for I/O-bound tasks.

## Data sources

- WorldClim 2.1 CMIP6 30s (future), GCM `ACCESS-CM2`:
  https://www.worldclim.org/data/cmip6/cmip6_clim30s.html
  Files served from `https://geodata.ucdavis.edu/cmip6/30s/`
- WorldClim 2.1 historical 30s (1970-2000):
  https://www.worldclim.org/data/worldclim21.html
  Files served from `https://geodata.ucdavis.edu/climate/worldclim/2_1/base/`
- Forest Productivity Index v1.0 (Sept 2024), DCCEEW, 1970-2022 at ~1 km GDA94:
  https://data.gov.au/data/dataset/forest-productivity-index-version-1-0-sept-2024-release
  Resource URLs are read from the CKAN API, not hard-coded, because the portal
  can re-issue resource UUIDs.
