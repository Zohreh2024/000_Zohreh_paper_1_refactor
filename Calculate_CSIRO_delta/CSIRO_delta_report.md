# CSIRO_delta_report.md

Change signals between the CSIRO future and historical climatologies. Companion
to `calculate_CSIRO_delta.py` in this folder.

## What was produced

Two sets, in two folders, because they are two different quantities:

| folder | quantity | files | variables |
|---|---|---|---|
| `Data/Processed/CSIRO_Delta` | **ratio**, future / historical | 64 (+64 `.nc`) | all 8 |
| `Data/Processed/CSIRO_Delta_additive` | **difference**, future - historical | 16 (+16 `.nc`) | `tasmax`, `tasmin` |

```
CSIRO_Delta/<var>_<ssp>_delta_<window>_over_1985-2014.tif   (+ .nc)
CSIRO_Delta_additive/<var>_<ssp>_diff_<window>_over_1985-2014.tif   (+ .nc)
```

The stem says `delta` for the ratio and `diff` for the difference, so the two
cannot be confused even if the files are ever moved together.

| property | value |
|---|---|
| inputs | `Data/Processed/CSIRO_avg/{FUTURE,HISTORICAL}` |
| windows | mid = 2035-2064, late = 2070-2099 |
| reference | 1985-2014, the single historical climatology |
| scenarios | ssp126, ssp245, ssp370, ssp585 |
| bands | 12; band k = future month k against historical month k |
| grid | NLUM, 3364 x 4071, 0.01 deg, GDA94, NaN outside the mask |
| units | ratio: `1` (dimensionless). difference: the variable's own units |

Both inputs are already on the NLUM grid, so this is **pure arithmetic with no
resampling** - grid, transform, CRS, band layout and mask pass through untouched.

## The ratio is right for seven variables and wrong for two

`pr`, `rsds`, `hurs`, `hursmax`, `hursmin` and `sfcWind` are non-negative
quantities on a **ratio scale**. Their zero is absolute - zero rainfall is no
rainfall - so "20% wetter" is meaningful, and the factor is exactly what a
delta-change application consumes.

`tasmax` and `tasmin` are in degC, an **interval scale**. Its zero is a
convention (the freezing point of water), not an absence of temperature, so a
quotient carries no physical meaning. Two consequences, both visible in the
output:

1. **Where the denominator crosses zero, the ratio diverges.** Historical
   `tasmin` reaches -5.00 degC, so cells near 0 degC divide by almost nothing.
2. **Even where it does not diverge, the number is not interpretable.** A
   `tasmax` ratio of 1.207 does not mean "20.7% warmer" in any usable sense - it
   depends entirely on where Celsius happens to put its zero. The same warming
   expressed in Kelvin would give 1.019.

`tasmax` escapes the first problem only by luck: its historical minimum is
+1.54 degC, so it never crosses zero. It does not escape the second.

Both were still computed, because they were asked for. Every temperature file in
`CSIRO_Delta` carries a `warning` tag in its metadata recording why its ratio is
not meaningful, so the caveat travels with the data rather than living only in a
report.

## Results: ratio (future / historical)

Median over the NLUM mask, across all 12 bands.

### The seven ratio-scale variables

| variable | window | ssp126 | ssp245 | ssp370 | ssp585 |
|---|---|---|---|---|---|
| `pr` | mid | 0.941 | 0.876 | 0.948 | 0.931 |
| | late | 0.856 | 0.951 | **0.782** | 0.844 |
| `hurs` | mid | 0.978 | 0.961 | 0.972 | 0.966 |
| | late | 0.942 | 0.960 | 0.911 | **0.894** |
| `hursmax` | mid | 0.983 | 0.972 | 0.974 | 0.971 |
| | late | 0.958 | 0.966 | 0.929 | **0.907** |
| `hursmin` | mid | 0.973 | 0.953 | 0.971 | 0.966 |
| | late | 0.929 | 0.957 | 0.900 | **0.895** |
| `rsds` | mid | 1.007 | 1.012 | 1.004 | 1.006 |
| | late | 1.016 | 1.011 | 1.015 | 1.014 |
| `sfcWind` | mid | 0.999 | 1.006 | 1.008 | 1.011 |
| | late | 1.000 | 0.995 | 1.011 | 1.016 |

Full ranges stay bounded and physical throughout: `pr` 0.134-3.695, `hurs`
0.579-1.158, `hursmax` 0.629-1.120, `hursmin` 0.533-1.244, `rsds` 0.964-1.191,
`sfcWind` 0.778-1.224.

Reading these:

- **Humidity dries monotonically with forcing in the late window**, all three
  measures agreeing (ssp585 late: 0.894 / 0.907 / 0.895). Consistent with
  warming raising saturation vapour pressure faster than moisture supply.
- **Rainfall is not monotonic** and should not be expected to be. The continental
  median cancels opposing north/south signals; use the spatial fields.
- **`rsds` and `sfcWind` barely move** - within about 1.6% of 1.0 in every
  scenario and window, with no clear ordering.

### The two temperature variables

| `tasmax` ratio | min | max | median |
|---|---|---|---|
| ssp126 late | 1.021 | 1.922 | 1.079 |
| ssp585 late | 1.089 | 4.124 | 1.207 |

| `tasmin` ratio | min | max | median |
|---|---|---|---|
| ssp126 mid | **-12,227** | **10,642** | 1.114 |
| ssp126 late | -12,833 | 20,250 | 1.131 |
| ssp245 mid | -17,188 | 20,008 | 1.132 |
| ssp245 late | -27,863 | 47,169 | 1.219 |
| ssp370 mid | -20,487 | 37,245 | 1.153 |
| ssp370 late | -47,274 | 76,903 | 1.318 |
| ssp585 mid | -19,849 | 29,824 | 1.171 |
| ssp585 late | **-60,290** | **102,944** | 1.376 |

Cells exceeding |ratio| > 10 number 3,088 to 21,737 per file - only 0.00% to
0.03% of the mask, but **spatially clustered** in alpine and inland-winter areas
rather than scattered, so a regional analysis can land entirely inside the
affected zone.

**The medians are the trap.** They look reasonable (1.11-1.38) and are even
monotonic in forcing, so a summary statistic or a default-scaled map gives no
hint that the tails span five orders of magnitude.

## Results: difference (future - historical), temperature

Median over the NLUM mask, in degC - the physically meaningful form.

| variable | window | ssp126 | ssp245 | ssp370 | ssp585 |
|---|---|---|---|---|---|
| `tasmax` | mid | +1.82 | +2.19 | +2.37 | +2.57 |
| | late | +2.18 | +3.22 | +5.00 | **+5.87** |
| `tasmin` | mid | +1.73 | +2.04 | +2.35 | +2.52 |
| | late | +1.90 | +3.21 | +4.74 | **+5.75** |

Full ranges: `tasmax` +0.30 to +8.60 degC, `tasmin` +0.19 to +7.69 degC, across
every scenario and window. **No divergence anywhere.**

The contrast is the whole argument. The same `tasmin` ssp585 late data:

| form | range | median |
|---|---|---|
| ratio | -60,290 to +102,944 | 1.376 |
| difference | +2.61 to +7.69 degC | +5.75 |

Both describe the same cells. Only one is readable, and only one is monotonic in
forcing in a way that survives inspection of the full distribution rather than
just the centre.

## Method and guards

```
ratio       out = future / historical
difference  out = future - historical
```

per cell, per band, then masked to NLUM's valid cells.

- **Zero denominators become NaN, not inf.** A ratio against nothing is
  undefined, and `inf` would poison every downstream statistic. The count is
  reported per file; none of the 64 ratio files hit this, because no historical
  climatology contains an exact zero over the mask.
- **Nothing is clipped.** An extreme ratio is a real fact about its denominator.
  Capping it at, say, +/-10 would have produced a tidy-looking temperature file
  and hidden the entire problem documented above. The run instead *counts* the
  extremes and reports them.
- **Shapes are checked** before dividing; a future file whose shape differs from
  its historical counterpart is skipped with a message rather than broadcast.

## Metadata on every file

| tag | example |
|---|---|
| `quantity` | `ratio, future divided by historical` |
| `variable` / `scenario` / `window` | `tasmin` / `ssp585` / `2070-2099` |
| `window_label` | `late` |
| `reference` | `1985-2014` |
| `numerator` | `CSIRO_tasmin_ssp585_monthly_avg_2070-2099_NLUM.tif` |
| `denominator` | `CSIRO_tasmin_monthly_avg_1985-2014_NLUM.tif` |
| `units` | `1` for ratios, `degree Celsius` for differences |
| `warning` | present on temperature ratios only |

Numerator and denominator are named explicitly, so any output can be traced back
to the exact pair of files that produced it.

## Recommendation

For the conversation with supervisors, the position this report supports:

1. **Use `CSIRO_Delta` for the six non-temperature variables.** The ratio is
   correct there and is the form a delta-change application needs.
2. **Use `CSIRO_Delta_additive` for `tasmax` and `tasmin`.** The additive
   difference in degC is the standard way climate change in temperature is
   expressed, and is what CMIP6 and the QDC method itself use for temperature.
3. If a temperature *ratio* is genuinely wanted for some reason, compute it in
   **Kelvin**, where zero is absolute. That is well defined, though the numbers
   are uninformative (about 1.02 for +5.9 degC of warming) precisely because the
   additive form is what carries the signal.

## Reproduction

```powershell
conda run -n JinzhuLuto python Calculate_CSIRO_delta\calculate_CSIRO_delta.py --dry-run
conda run -n JinzhuLuto python Calculate_CSIRO_delta\calculate_CSIRO_delta.py --workers 8
conda run -n JinzhuLuto python Calculate_CSIRO_delta\calculate_CSIRO_delta.py --additive --vars tasmax tasmin
```

Resumable - an output that already exists is skipped. `--vars` and `--ssps`
restrict the set, `--out-dir` overrides the destination, `--overwrite` forces
rewriting.
