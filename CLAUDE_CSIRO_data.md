# CLAUDE_CSIRO_data.md

The BARRA-R2 historical baseline (1985-2014) from CSIRO: what it is, how it was
downloaded, how it was aggregated and matched to NLUM, and every check that was
run. Companion to `Doc/CSIRO_historical_data_NLUM_processing_report.docx`, which
holds the same content in prose.

## Why this dataset

It is the exact observational dataset CSIRO's quantile-delta-change (QDC)
factors were applied to when producing the future projections already in
`Data/Raw/rainFall/`. Any comparison between projection and observation rests on
this being the same product, on the same grid, in the same units.

## Source

| | |
|---|---|
| Collection | `csiro:64206` — "Application-ready quantile-delta-change (QDC) scaled CMIP6 climate projections for Australia (time slices, 11km grid)" |
| DOI | `10.25919/nc64-tx11` |
| Licence | CC BY 4.0 |
| Attribution | Irving, Damien; Macadam, Ian; & King, Malcolm (2024). v1. CSIRO. Data Collection. |
| Landing page | https://data.csiro.au/collection/csiro:64206 |

The full collection is 16,596 files and 14.2 TB, almost all of it future
QDC-scaled projections for nine CMIP6 models. **The historical baseline is one
branch of that tree** — 270 files, 109.2 GB, on the native AUS-11 grid
(0.11 deg, ~11 km):

```
BARRA-R2/raw/historical/v1/day/<variable>/AUS-11/1985-2014/v20241104/
    <variable>_day_BARRA-R2_historical_v1_AUS-11_<year>.nc
```

BARRA-R2 is the Bureau of Meteorology's regional atmospheric reanalysis for
Australia, driven by ECMWF ERA5. It is **reanalysis, not gauge observation**.

## Download — `Step_0_download_data/download_CSIRO_historical_data.py`

DAP serves bytes from S3 behind pre-signed URLs, which differ from a plain
static host in two ways that shaped the downloader:

- **The signature covers GET only.** A HEAD returns 403, so the expected size
  comes from the API manifest, not `Content-Length`.
- **Signatures expire after 48 h.** A 403 mid-download re-signs against the
  per-file endpoint (which 302-redirects to a fresh URL) and resumes.

This is why it does not import `download()` from `download_worldclim_cmip6.py`
the way the other downloaders do. Everything else — `.part` files, Range resume,
size verification, retries — keeps the same shape.

The ~30 MB collection manifest is cached to `.dap_64206_manifest.json`
(gitignored); `--refresh-manifest` re-queries it.

**Verified:** 270/270 files present at the manifest size, 109.2 GB, zero
leftover `.part`, zero failures. One file per variable opens with a complete
year (365/366 daily steps) on a 646 x 1082 grid.

## The NLUM template

Every output matches `Data/NLUM_Mask/NLUM_2010-11_mask.tif`.

| property | value |
|---|---|
| dimensions | 3364 rows x 4071 columns |
| resolution | 0.01 x 0.01 deg |
| CRS | `GEOGCS["GDA94"]`, unnamed datum, GRS 1980 ellipsoid (a = 6378137, 1/f = 298.257222101) |
| transform | `(0.01, 0.0, 112.925, 0.0, -0.01, -10.015)` |
| bounds (W,S,E,N) | 112.925, -43.655, 153.635, -10.015 |
| total cells | 13,694,844 |
| **valid cells** (`mask == 1`) | **6,956,407** (50.8%) |
| NaN cells (`mask == 0`) | 6,738,437 |
| one float32 band | 52.2 MB |

The valid-cell count is **identical for every variable, year and band** — it is a
property of the mask, not the data, and it is what makes the nine variables
stackable.

## Pipeline — `Step_0_download_data/reproject_CSIRO_historical_to_NLUM.py`

Per raw file (one variable, one year):

| step | operation | detail |
|---|---|---|
| 1 | clip | Subset lat/lon to the NLUM box + 0.5 deg buffer while still lazy, so only ~1/6 of the AUS-11 domain is read. The buffer gives the resampler and the fill real data just outside the template instead of edge-of-array NaN. |
| 2 | aggregate | 365/366 daily steps -> 12 monthly bands |
| 3 | match | `reproject_match` onto NLUM: WGS 84 -> GDA94, 0.11 -> 0.01 deg, snapped to NLUM's exact grid. Bilinear. One band at a time to cap peak memory. |
| 4 | fill | NaN takes the nearest non-NaN value (Euclidean distance transform). **Only NaN is a gap** — 0 mm and 0 degC are real. |
| 5 | mask | Cells outside the NLUM mask -> NaN. Fill runs *before* mask so coastal cells pick up a real value first. |

Steps 3-5 and the 12-band layout are identical to `reproject_match_NLUM.py`,
whose helpers this script **imports rather than duplicates** — so these nine
variables sit on exactly the same footing as `tmin`/`tmax`/`prec`/`bioc`. That
import is why `reproject_match_NLUM.py`'s body now sits in `main()` behind an
`if __name__ == "__main__"` guard; running it directly is unchanged.

Runs on **loky, not threading** — `netCDF4-python` serialises every HDF5 call
behind a module-global lock, so threads take turns inside the library. Six
processes, template loaded lazily per worker.

## Monthly, not daily — read this before asking for daily

One float32 band on NLUM is 52.2 MB. Keeping the daily step would turn 109 GB of
source into **~5.1 TB** and 1-2 days of runtime, nearly all of it writing to the
share. Monthly gives **89.7 GB**, matches FullCAM's time step, and matches every
other variable in `Data/Processed/`.

Two aggregation rules:

- **`pr` is summed.** It is a rate in mm d-1, so summing daily values across a
  month gives the monthly total in mm — the quantity ANUClimate's `rain` carries
  and the one `Data/Processed/prec` holds for WorldClim.
- **The other eight are averaged.** They are state variables; the month's mean
  is the meaningful summary.

**`hursmax`, `hursmin` and `sfcWindmax` are monthly means of the daily extreme,
NOT monthly extremes.** These files answer "the average daily maximum wind speed
in January 1998", not "the highest wind speed observed in January 1998". For the
latter, go back to the daily source.

Aggregation uses `groupby("time.month")`, not `resample()` — each file is exactly
one calendar year so grouping on month is equivalent, and the installed pandas
rejects the `base` kwarg xarray's `resample` passes.

## Units — matched to ANUClimate v2-0 monthly

Output units follow
https://thredds.nci.org.au/thredds/catalog/gh70/ANUClimate/v2-0/stable/month
wherever ANUClimate has the variable, so these sit on the same footing as
FullCAM's historical inputs. ANUClimate's units were **read from the archive**,
not assumed.

| variable | source units | output units | ANUClimate counterpart | conversion |
|---|---|---|---|---|
| `pr` | mm d-1 | **mm month-1** | `rain` (mm month-1) | none (sum) |
| `tasmax` | degC | **degree Celsius** | `tmax` (degree Celsius) | none |
| `tasmin` | degC | **degree Celsius** | `tmin` (degree Celsius) | none |
| `rsds` | W m-2 | **MJ m-2 day-1** | `srad` (MJ m-2 day-1) | **x 0.0864** |
| `hurs` | % | % | none | none |
| `hursmax` | % | % | none | none |
| `hursmin` | % | % | none | none |
| `sfcWind` | m s-1 | m s-1 | none | none |
| `sfcWindmax` | m s-1 | m s-1 | none | none |

**`rsds` is the only conversion.** 1 W m-2 sustained for a day delivers
86,400 J m-2 = 0.0864 MJ m-2, so the monthly mean of the daily-mean flux x 0.0864
gives ANUClimate's "monthly total solar radiation" expressed — as it is there —
as a mean daily total.

**ANUClimate has no relative humidity or wind product.** Its `vp`/`vpd` are
vapour pressure and vapour pressure deficit in hPa: a different quantity,
derivable from RH + temperature but not reachable by a unit conversion. The
humidity and wind fields are therefore left in source units, unscaled.

Units are written into every GeoTIFF **twice** — a dataset tag and a per-band tag
— because the nine variables do not share a unit. Each file also tags its
`variable`, `aggregation` rule and `source` file name.

## Per-variable detail

Ranges span the full 30-year record, all 12 bands, valid mask cells only.

| variable | description | files | bands | units | aggregation |
|---|---|---|---|---|---|
| `pr` | Precipitation | 30 | 12 | mm month-1 | sum |
| `tasmax` | Maximum near-surface air temperature | 30 | 12 | degree Celsius | mean |
| `tasmin` | Minimum near-surface air temperature | 30 | 12 | degree Celsius | mean |
| `rsds` | Mean downwelling shortwave (solar) radiation | 30 | 12 | MJ m-2 day-1 | mean |
| `hurs` | Mean near-surface relative humidity | 30 | 12 | % | mean |
| `hursmax` | Maximum near-surface relative humidity | 30 | 12 | % | mean |
| `hursmin` | Minimum near-surface relative humidity | 30 | 12 | % | mean |
| `sfcWind` | Mean near-surface wind speed | 30 | 12 | m s-1 | mean |
| `sfcWindmax` | Maximum near-surface wind speed | 30 | 12 | m s-1 | mean |

| variable | raw GB | output GB | min (all years) | max (all years) | mean 2014 |
|---|---|---|---|---|---|
| `pr` | 21.2 | 10.9 | 0.00 | 2383.17 | 39.67 |
| `tasmax` | 5.9 | 9.8 | -0.40 | 44.80 | 28.81 |
| `tasmin` | 6.5 | 10.0 | -8.59 | 30.32 | 15.59 |
| `rsds` | 12.6 | 9.8 | 2.76 | 33.05 | 21.08 |
| `hurs` | 15.1 | 9.9 | 11.51 | 96.74 | 48.74 |
| `hursmax` | 16.1 | 9.8 | 19.08 | **104.22** | 70.27 |
| `hursmin` | 16.4 | 10.0 | 5.63 | 89.96 | 28.36 |
| `sfcWind` | 9.3 | 9.9 | 0.57 | 12.83 | 4.05 |
| `sfcWindmax` | 6.2 | 9.7 | 1.38 | 16.86 | 6.51 |

Totals: 270 raw files, 109.2 GB; 270 output files, 89.7 GB (LZW, tiled 256x256,
`BIGTIFF=IF_SAFER`). Bands are named `<variable>_01` ... `<variable>_12`, where
band k is calendar month k.

The 2383 mm monthly maximum for `pr` is real — tropical wet-season north
Queensland — not an outlier to chase.

## Alignment and integrity — all 270 files read back and audited

| check | requirement | result |
|---|---|---|
| band count | 12 per file | 270/270 |
| dimensions | 3364 x 4071 | 270/270 |
| affine transform | identical to NLUM mask | 270/270 |
| CRS | identical to NLUM mask | 270/270 |
| **NaN inside the mask** | zero | **0** across all files and bands |
| **data outside the mask** | zero | **0** across all files and bands |
| units tag | one consistent value per variable | 9/9 |
| valid cells per band | 6,956,407 | identical for every band |
| dtype / nodata | float32 / NaN | 270/270 |
| leftover `.tmp` | zero | 0 |

"NaN inside the mask" checks that the fill left no holes in the land surface;
"data outside the mask" checks that masking blanked everything beyond it. Both
being exactly zero means every band's NaN pattern is precisely the complement of
the NLUM mask.

## Independent validation

Two checks against sources outside this pipeline, so agreement means something.

**Precipitation vs the daily source.** 400 random valid NLUM cells x 12 months of
1985, against monthly totals recomputed straight from the daily NetCDF and
sampled nearest-neighbour on the 0.11 deg grid:

| | |
|---|---|
| r | **0.9818** |
| bias | -0.13 mm on a 38.5 mm source mean (-0.3%) |
| MAE | 1.79 mm |
| negative values | none |

The residual is what bilinear resampling at 11x refinement should produce — the
output is smoother than a nearest-neighbour sample of the coarse source, by
construction. The near-zero bias confirms no systematic error.

**Solar radiation vs ANUClimate**, January 1985:

| quantity | value |
|---|---|
| this pipeline, mean over NLUM mask | 28.09 MJ m-2 day-1 |
| ANUClimate `srad` 1985-01, domain mean | 28.55 MJ m-2 day-1 |
| difference | -0.46 (-1.6%) |
| this pipeline, range | 16.55 - 31.90 |
| ANUClimate `srad`, range | 16.6 - 32.3 |

Central value and spatial range both agree. A conversion error of the kind that
is easy to make here — confusing a daily total with an instantaneous flux — would
show up as a factor of 86,400 or of the month length, not 1.6%. What remains is a
real reanalysis-vs-gauge product difference, not a units problem.

## Relative humidity above 100% — this is correct data

`hursmax` reaches **104.22%** across the record. It is not a processing artefact.

| measurement (2014 file, NLUM box) | value |
|---|---|
| maximum in the raw daily source | **120.95%** |
| daily cell-values above 100% in the source | 513,261 of 43,575,525 (1.18%) |
| maximum of the source's own monthly means | **101.16%** |
| maximum in the processed 2014 output | **100.15%** |

Two things follow. Values above 100% are **present in the raw BARRA-R2 files
before this pipeline touches them** — over half a million cell-days in one year,
reaching 120.95%. And the processed output's maximum (100.15%) is *lower* than
the maximum of the source's own monthly means (101.16%), so aggregation and
bilinear resampling are **damping** these values, not creating them.

**Why the source contains them.** RH in BARRA-R2 is actual over saturation vapour
pressure, with saturation defined **with respect to liquid water**. Air can be
genuinely supersaturated with respect to water — most commonly at low
temperatures, where saturation over ice is lower than over water, so air
saturated over ice exceeds 100% when expressed over water. Model cloud
microphysics permits this state and the diagnostic reports it faithfully rather
than clipping. 104% is physically meaningful: not a missing-data sentinel, not an
overflow.

**Downstream.** Nothing here needs correcting. But any code assuming RH <= 100 —
dividing by 100 for a fraction, a validity check, a colour scale, a conversion to
vapour pressure or dew point — must either accept slightly-above-1.0 values or
clip explicitly. **Clip at the point of use, not in the archive**, because
clipping here would silently discard information the source deliberately kept.
The affected values sit within a few percent of the bound, in ~1% of daily
cell-values; after monthly averaging only a small number of cell-months exceed
100% at all.

## Caveats for downstream use

- **Temperature is already degC in the source.** No Kelvin conversion belongs
  downstream; applying one shifts every value by 273.15.
- **Precipitation is a daily rate in mm d-1, not a flux in kg m-2 s-1.** Monthly
  totals need no `x 86400` — unlike the BARRA-R2 `pr` that
  `Validation_rainfall_projections/Step_00c` fetches from NCI, which does.
- `hursmax`/`hursmin`/`sfcWindmax` are monthly means of daily extremes.
- RH can exceed 100%.
- **These are reanalysis values, not gauge observations.** Where FullCAM's
  historical inputs come from ANUClimate, the two differ systematically — roughly
  +3.0% annually in rainfall over 1985-2014 and considerably more month by month.
  A product difference, not an error in either. See the QDC section of
  `CLAUDE.md`.
- Regular geographic grid, so **no equal-area assumption holds**. Cell area
  shrinks with latitude; area-weight any spatial total.

## Locations, naming, reproduction

```
Data/Raw/CSIRO_historical_data/<variable>/
    <variable>_day_BARRA-R2_historical_v1_AUS-11_<year>.nc     # read-only

Data/Processed/CSIRO_historical_data/<variable>/
    <variable>_mon_BARRA-R2_historical_v1_AUS-11_<year>.tif
```

The provider's name is preserved except `day` -> `mon`, so nothing downstream can
mistake an aggregated file for the daily source and each output stays traceable
to the file it came from.

```powershell
conda run -n JinzhuLuto python Step_0_download_data\download_CSIRO_historical_data.py --dry-run
conda run -n JinzhuLuto python Step_0_download_data\download_CSIRO_historical_data.py --workers 8
conda run -n JinzhuLuto python Step_0_download_data\reproject_CSIRO_historical_to_NLUM.py --workers 6
```

Both scripts are resumable and skip completed work, so an interrupted run just
restarts. The reprojection script takes `--vars` to restrict the set, `--dry-run`
to list without writing, and `--overwrite` to force reprocessing.
