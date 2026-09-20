"""
Step 07 - compare the future M' against New_M_2019, and measure its variability.

New_M_2019 is the layer FullCAM ships as its historical maxAbgM, and it is what
the future inputs step away from, so it is the right reference. Note that on this
footing the comparison is not circular but it is *anchored*: M' = lambda x
Original_M_2004 x Eq1(FPI_fut)/Eq1(FPI_hist), and lambda x Original_M_2004 IS
New_M_2019, so the mean of the 30 modelled historical years reproduces the
reference exactly wherever the denominator was not floored. That identity is
checked below rather than assumed - it is the tightest available test that the
chain from FPI to M' does what it claims.

Three coefficients of variation, because "CV" can mean three things here
-----------------------------------------------------------------------
interannual    sd over the 30 years of a scenario-window, divided by their mean,
               per cell. How much the projected M' moves from year to year. The
               historical equivalent is computed from the 30 modelled historical
               years on the same footing, so the two are comparable and the
               question "does interannual variability increase?" has an answer.
               New_M_2019 itself is a single layer and has no interannual
               dimension - that is why the historical reference is rebuilt here.

across-scenario  sd over the four SSPs of their window-mean M', divided by their
               mean, per cell. How much the scenario choice matters, which is a
               different kind of uncertainty from the year-to-year one.

spatial        sd over cells divided by the mean over cells, one number per
               layer. Reported in the CSV for the future windows and for
               New_M_2019, so the spread of the map can be compared as a whole.

Everything else is the ordinary comparison: bias, RMSE, MAE, Pearson r, the
share of cells declining, and the area-weighted national total in Mt DM, which
is the number that actually matters for a carbon account.

Reads   ../output_Mprime_rf/mean_of_annual/maxAbgMF_<ssp>_<year>.tif  240
        ../output/fpi_rf_<year>.tif                                    30
        ../output_Mprime_rf/mean_of_annual/scale_Eq1_to_original2004.tif
        Step_02_published_lambda/output/lambda_published.tif
        Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif

Writes  output/cv/cv_interannual_<ssp>_<window>.tif                    8
        output/cv/cv_interannual_historical_1985-2014.tif
        output/cv/cv_across_scenarios_<window>.tif                     2
        output/cv/mean_Mprime_historical_1985-2014.tif
        output/comparison_vs_New_M_2019.csv        per scenario-window metrics
        output/cv_summary.csv                      CV distributions
        output/change_by_baseline_decile.csv       where the change concentrates

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_07_compare_vs_New_M_2019.py --jobs 4
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402
from joblib import Parallel, delayed                           # noqa: E402

HERE = Path(__file__).resolve().parent            # FPI_Accuracy_check/Comparison_vs_New_M_2019
PARENT = HERE.parent                              # FPI_Accuracy_check
ROOT = PARENT.parent                              # the repository root
OUT_DIR = HERE / "output"
CV_DIR = OUT_DIR / "cv"
FPI_RF_DIR = PARENT / "output"                    # Step_01's modelled historical FPI
MPRIME_DIR = PARENT / "output_Mprime_rf" / "mean_of_annual"
SCALE = MPRIME_DIR / "scale_Eq1_to_original2004.tif"
LAMBDA = ROOT / "Step_02_published_lambda" / "output" / "lambda_published.tif"
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019_NLUM.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = {"2035-2064": range(2035, 2065), "2070-2099": range(2070, 2100)}
HIST_YEARS = list(range(1985, 2015))

M_A, M_B = 6.011, 5.291                                  # Eq. (1)
M_ROOT = (M_B / M_A) ** 2

_ref = {}


def reference():
    if not _ref:
        with rasterio.open(NLUM_MASK) as t:
            _ref["valid"] = t.read(1) == 1
            _ref["shape"] = (t.height, t.width)
            _ref["crs"] = t.crs
            _ref["transform"] = t.transform
            _ref["bounds"] = t.bounds
    return _ref


def read(path):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
    return a


def write_gtiff(arr, dst_path, description, tags):
    ref = reference()
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_suffix(".tif.tmp")
    with rasterio.open(
        tmp, "w", driver="GTiff",
        height=ref["shape"][0], width=ref["shape"][1], count=1,
        dtype="float32", nodata=np.nan,
        crs=ref["crs"], transform=ref["transform"],
        compress="LZW", tiled=True, blockxsize=256, blockysize=256,
        BIGTIFF="IF_SAFER",
    ) as dst:
        dst.write(arr.astype("float32"), 1)
        dst.set_band_description(1, description)
        dst.update_tags(**tags)
    tmp.replace(dst_path)
    return dst_path


def eq1(fpi):
    x = np.clip(fpi, M_ROOT, None)
    with np.errstate(invalid="ignore"):
        return (M_A * np.sqrt(x) - M_B) ** 2


def cell_area_ha():
    """Area of each 0.01 deg cell, hectares, varying with latitude.

    Geographic cells are not equal-area, so a national total that ignores this
    over-weights the south. 0.01 deg of latitude is a fixed 1.1132 km; 0.01 deg
    of longitude is that times cos(lat).
    """
    ref = reference()
    t = ref["transform"]
    rows = np.arange(ref["shape"][0])
    lat = t.f + (rows + 0.5) * t.e                    # t.e is negative
    km_lat = 111.32 * abs(t.e)
    km_lon = 111.32 * abs(t.a) * np.cos(np.deg2rad(lat))
    area_km2 = km_lat * km_lon                        # per row
    return (area_km2 * 100.0)[:, None]                # km2 -> ha, broadcast over columns


def stack_stats(paths, jobs, transform=None):
    """Mean and sd across a list of rasters, streamed, without holding the stack.

    Each worker accumulates its own float64 sum and sum-of-squares over a slice
    of the years; the slices are then combined. float64 throughout - a float32
    sum of squares of values in the hundreds loses the variance.
    """
    ref = reference()
    groups = [list(g) for g in np.array_split(np.array(paths, dtype=object),
                                              min(jobs, len(paths)))]

    def accumulate(group):
        s = np.zeros(ref["shape"], dtype="float64")
        s2 = np.zeros(ref["shape"], dtype="float64")
        n = 0
        for p in group:
            a = read(p)
            if transform is not None:
                a = transform(a)
            s += a
            s2 += a * a
            n += 1
        return s, s2, n

    parts = Parallel(n_jobs=len(groups), backend="threading")(
        delayed(accumulate)(g) for g in groups if len(g))

    s = sum(p[0] for p in parts)
    s2 = sum(p[1] for p in parts)
    n = sum(p[2] for p in parts)
    mean = s / n
    var = np.maximum(s2 / n - mean * mean, 0.0)       # population variance
    return mean, np.sqrt(var * n / (n - 1)), n        # sample sd


def cv_of(mean, sd, valid, floor=1.0):
    """sd / mean as a percentage, only where the mean is meaningfully non-zero."""
    with np.errstate(invalid="ignore", divide="ignore"):
        cv = np.where(valid & (mean > floor), 100.0 * sd / mean, np.nan)
    return cv


def dist(arr, valid):
    v = arr[valid & np.isfinite(arr)]
    return dict(mean=float(v.mean()), median=float(np.median(v)),
                p05=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    ref = reference()
    valid = ref["valid"]
    CV_DIR.mkdir(parents=True, exist_ok=True)

    base = read(NEW_M)
    area = np.broadcast_to(cell_area_ha(), ref["shape"])
    tot_factor = area / 1e6                            # t DM ha-1 x ha -> Mt DM

    print("New_M_2019: mean %.2f t DM ha-1, national total %.0f Mt DM"
          % (np.nanmean(base[valid]), np.nansum((base * tot_factor)[valid])))

    # --- historical M' on the same footing --------------------------------- #
    hist_mean_path = CV_DIR / "mean_Mprime_historical_1985-2014.tif"
    hist_cv_path = CV_DIR / "cv_interannual_historical_1985-2014.tif"
    if hist_cv_path.exists() and hist_mean_path.exists() and not args.overwrite:
        hist_mean, hist_cv = read(hist_mean_path), read(hist_cv_path)
        print("historical M' layers already present, kept")
    else:
        factor = read(LAMBDA) * read(SCALE)            # lambda x Original_M_2004 / D
        paths = [FPI_RF_DIR / ("fpi_rf_%d.tif" % y) for y in HIST_YEARS]
        print("historical: %d modelled years -> M' = factor x Eq1(FPI)" % len(paths))
        hist_mean, hist_sd, _ = stack_stats(paths, args.jobs,
                                            transform=lambda a: factor * eq1(a))
        hist_cv = cv_of(hist_mean, hist_sd, valid)
        write_gtiff(np.where(valid, hist_mean, np.nan), hist_mean_path,
                    "mean_Mprime_historical",
                    dict(units="t DM ha-1",
                         long_name="mean modelled historical M' 1985-2014"))
        write_gtiff(hist_cv, hist_cv_path, "cv_interannual_historical",
                    dict(units="%", long_name="interannual CV of M', 1985-2014"))

    # The identity check: mean_y M'_hist_y should BE New_M_2019.
    ok = valid & np.isfinite(hist_mean) & np.isfinite(base) & (base > 0)
    rel = np.abs(hist_mean[ok] - base[ok]) / base[ok]
    print("identity check  mean_y M'_hist = New_M_2019:  median |rel. error| %.2e, "
          "p99 %.2e, max %.2e" % (np.median(rel), np.percentile(rel, 99), rel.max()))

    # --- per scenario-window ----------------------------------------------- #
    rows, cv_rows, window_means = [], [], {}
    cv_rows.append(dict(layer="historical 1985-2014", kind="interannual",
                        **dist(hist_cv, valid)))

    for win, years in WINDOWS.items():
        for ssp in SSPS:
            paths = [MPRIME_DIR / ("maxAbgMF_%s_%d.tif" % (ssp, y)) for y in years]
            paths = [p for p in paths if p.exists()]
            if len(paths) != len(list(years)):
                print("  %s %s: %d of %d annual rasters found"
                      % (ssp, win, len(paths), len(list(years))))
            cv_path = CV_DIR / ("cv_interannual_%s_%s.tif" % (ssp, win))

            mean, sd, n = stack_stats(paths, args.jobs)
            cv = cv_of(mean, sd, valid)
            if args.overwrite or not cv_path.exists():
                write_gtiff(cv, cv_path, "cv_interannual_%s_%s" % (ssp, win),
                            dict(units="%", long_name="interannual CV of M'",
                                 n_years=str(n)))
            window_means[(ssp, win)] = mean

            ok = valid & np.isfinite(mean) & np.isfinite(base) & (base > 0)
            m, b = mean[ok], base[ok]
            resid = m - b
            pct = 100 * resid / b
            tot_m = float(np.nansum((mean * tot_factor)[valid & np.isfinite(mean)]))
            tot_b = float(np.nansum((base * tot_factor)[valid & np.isfinite(base)]))
            rows.append(dict(
                ssp=ssp, window=win, n_years=n, n_cells=int(ok.sum()),
                Mprime_mean=float(m.mean()), Mprime_median=float(np.median(m)),
                New_M_2019_mean=float(b.mean()),
                bias=float(resid.mean()), rmse=float(np.sqrt((resid ** 2).mean())),
                mae=float(np.abs(resid).mean()),
                pearson_r=float(np.corrcoef(b, m)[0, 1]),
                slope=float(np.polyfit(b, m, 1)[0]),
                pct_change_median=float(np.median(pct)),
                pct_change_mean=float(pct.mean()),
                pct_cells_declining=float(100 * np.mean(pct < 0)),
                total_Mt_DM=tot_m, total_Mt_DM_New_M_2019=tot_b,
                total_pct_change=100 * (tot_m - tot_b) / tot_b,
                spatial_cv_pct=float(100 * m.std() / m.mean()),
            ))
            cv_rows.append(dict(layer="%s %s" % (ssp, win), kind="interannual",
                                **dist(cv, valid)))
            print("  %s %s: M' mean %.2f (base %.2f), median change %+.1f%%, "
                  "interannual CV median %.1f%%"
                  % (ssp, win, m.mean(), b.mean(), np.median(pct),
                     np.nanmedian(cv[valid])))

        # --- spread across the four scenarios, this window ------------------ #
        stack = np.stack([window_means[(s, win)] for s in SSPS])
        s_mean = stack.mean(axis=0)
        s_sd = stack.std(axis=0, ddof=1)
        s_cv = cv_of(s_mean, s_sd, valid)
        write_gtiff(s_cv, CV_DIR / ("cv_across_scenarios_%s.tif" % win),
                    "cv_across_scenarios_%s" % win,
                    dict(units="%", long_name="CV of window-mean M' across the 4 SSPs"))
        cv_rows.append(dict(layer=win, kind="across_scenarios", **dist(s_cv, valid)))
        print("  %s: across-scenario CV median %.1f%%" % (win, np.nanmedian(s_cv[valid])))

    # New_M_2019's own spatial spread, for the CSV
    bv = base[valid & np.isfinite(base)]
    rows.append(dict(ssp="New_M_2019", window="reference", n_years=1,
                     n_cells=int(bv.size), Mprime_mean=float(bv.mean()),
                     Mprime_median=float(np.median(bv)),
                     New_M_2019_mean=float(bv.mean()),
                     spatial_cv_pct=float(100 * bv.std() / bv.mean()),
                     total_Mt_DM=float(np.nansum((base * tot_factor)[valid])),
                     total_Mt_DM_New_M_2019=float(np.nansum((base * tot_factor)[valid])),
                     total_pct_change=0.0))

    pd.DataFrame(rows).to_csv(OUT_DIR / "comparison_vs_New_M_2019.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(OUT_DIR / "cv_summary.csv", index=False)

    # --- where the change concentrates ------------------------------------- #
    ok = valid & np.isfinite(base) & (base > 0)
    edges = np.percentile(base[ok], np.arange(0, 101, 10))
    edges[-1] += 1e-6
    binned = np.digitize(base[ok], edges[1:-1])
    dec_rows = []
    for (ssp, win), mean in window_means.items():
        pct = 100 * (mean[ok] - base[ok]) / base[ok]
        for b_i in range(10):
            sel = binned == b_i
            if not sel.any():
                continue
            dec_rows.append(dict(ssp=ssp, window=win, decile=b_i + 1,
                                 baseline_lo=float(edges[b_i]),
                                 baseline_hi=float(edges[b_i + 1]),
                                 baseline_median=float(np.median(base[ok][sel])),
                                 pct_change_median=float(np.median(pct[sel])),
                                 pct_change_p25=float(np.percentile(pct[sel], 25)),
                                 pct_change_p75=float(np.percentile(pct[sel], 75)),
                                 n=int(sel.sum())))
    pd.DataFrame(dec_rows).to_csv(OUT_DIR / "change_by_baseline_decile.csv", index=False)

    print("\ntables in %s\nCV rasters in %s" % (OUT_DIR, CV_DIR))


if __name__ == "__main__":
    main()
