"""
Step 03 - historical M from the MODELLED FPI, in both averaging orders.

This builds the denominator of the M' delta-change ratio

    M'_future = lambda x Original_M_2004 x Eq1(FPI_future) / Eq1(FPI_1985-2014)

from `Step_01`'s modelled historical FPI rather than from the observed DCCEEW
layers, so that both sides of the ratio come from the same random forest.

The averaging order is not a detail
-----------------------------------
Eq. (1) is convex above its root, so by Jensen's inequality

    mean_y[ Eq1(FPI_y) ]  >=  Eq1( mean_y FPI_y )

and the two differ by a median factor of about 1.03 on this domain. Step_06
writes the numerator in BOTH orders - `M_<ssp>_<window>_mean.tif` is the mean of
the annual Eq. (1) M, `M_from_mean_fpi_<ssp>_<window>.tif` is Eq. (1) of the
mean FPI - so this step writes the denominator in both orders too. Pairing a
per-year numerator with a mean-FPI denominator puts the Jensen gap into the
ratio, where it reads as a climate signal; two of the eight windows change sign
on that alone (see `Option_B_matched_footing/README.md`).

Four denominators are written, so every comparison is available:

    Eq1_M_histRF_mean_of_annual.tif    mean_y Eq1(FPI_rf_y)     <- modelled
    Eq1_M_histRF_eq1_of_mean.tif       Eq1(mean_y FPI_rf_y)     <- modelled
    Eq1_M_histOBS_mean_of_annual.tif   mean_y Eq1(FPI_obs_y)    <- observed
    Eq1_M_histOBS_eq1_of_mean.tif      Eq1(mean_y FPI_obs_y)    <- observed

The last one reproduces `Calculation_future_M_CSIRO/output/Eq1_M_hist_1985-2014.tif`,
which is what the pipeline uses today; the script checks it against that file
and reports the difference, so the rebuild is verified rather than assumed.

Eq. (1), its coefficients and the clip at its root are taken verbatim from
Step_06/Step_08 (`M = (6.011*sqrt(FPI) - 5.291)**2`, clipped at FPI = 0.774787).

Writes  output/Eq1_M_hist{RF,OBS}_{mean_of_annual,eq1_of_mean}.tif
        output/hist_M_denominator_comparison.csv
        output/fpi_obs_1985-2014_mean.tif

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_M_hist_from_modelled_fpi.py
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_DIR = HERE / "output"

RF_FPI_DIR = OUT_DIR                                     # Step_01 output
OBS_FPI_DIR = ROOT / "Random_forest_CSIRO" / "required_data" / "fpi"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"
PIPELINE_HIST_M = (ROOT / "Calculation_future_M_CSIRO" / "output"
                   / "Eq1_M_hist_1985-2014.tif")

HIST_YEARS = list(range(1985, 2015))

M_A, M_B = 6.011, 5.291                                  # Eq. (1), as in Step_06
M_ROOT = (M_B / M_A) ** 2                                # 0.774787

_ref = {}


def reference():
    if not _ref:
        with rasterio.open(NLUM_MASK) as t:
            _ref["valid"] = t.read(1) == 1
            _ref["shape"] = (t.height, t.width)
            _ref["crs"] = t.crs
            _ref["transform"] = t.transform
    return _ref


def read_on_grid(path):
    ref = reference()
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if (s.height, s.width) != ref["shape"]:
            raise ValueError("%s: shape %s != NLUM %s"
                             % (path.name, (s.height, s.width), ref["shape"]))
        if s.transform != ref["transform"]:
            raise ValueError("%s: transform differs from the NLUM template" % path.name)
        if s.nodata is not None and not np.isnan(s.nodata):
            a[a == s.nodata] = np.nan
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
    """Eq. (1) with the parabola cut at its root, exactly as Step_06 applies it."""
    x = np.clip(fpi, M_ROOT, None)
    with np.errstate(invalid="ignore"):
        return (M_A * np.sqrt(x) - M_B) ** 2


def accumulate(paths, label):
    """Both averaging orders in one pass over the 30 annual rasters."""
    ref = reference()
    acc_m = np.zeros(ref["shape"], dtype="float64")       # sum of Eq1(FPI_y)
    acc_f = np.zeros(ref["shape"], dtype="float64")       # sum of FPI_y
    n_below = 0
    for p in paths:
        fpi = read_on_grid(p)
        n_below += int((fpi[ref["valid"]] < M_ROOT).sum())
        acc_f += fpi
        acc_m += eq1(fpi)
        print("    %s" % p.name)
    n = len(paths)
    mean_of_annual = acc_m / n
    mean_fpi = acc_f / n
    eq1_of_mean = eq1(mean_fpi)
    print("  %s: %d years, %s cell-years below the Eq.(1) root (clipped to M=0)"
          % (label, n, format(n_below, ",")))
    return mean_of_annual, eq1_of_mean, mean_fpi


def stats(arr, valid):
    v = arr[valid]
    return {
        "mean": float(np.nanmean(v)),
        "median": float(np.nanmedian(v)),
        "p05": float(np.nanpercentile(v, 5)),
        "p95": float(np.nanpercentile(v, 95)),
        "min": float(np.nanmin(v)),
        "max": float(np.nanmax(v)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    ref = reference()
    valid = ref["valid"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rf_paths = [RF_FPI_DIR / ("fpi_rf_%d.tif" % y) for y in HIST_YEARS]
    missing = [p.name for p in rf_paths if not p.exists()]
    if missing:
        sys.exit("missing %d modelled year(s) - run Step_01 first: %s"
                 % (len(missing), ", ".join(missing[:5])))

    obs_paths = [OBS_FPI_DIR / ("fpi_%d.tif" % y) for y in HIST_YEARS]
    missing = [p.name for p in obs_paths if not p.exists()]
    if missing:
        sys.exit("missing observed FPI: %s" % ", ".join(missing[:5]))

    print("modelled FPI (random forest):")
    rf_annual, rf_of_mean, rf_mean_fpi = accumulate(rf_paths, "RF")
    print("observed FPI (DCCEEW):")
    obs_annual, obs_of_mean, obs_mean_fpi = accumulate(obs_paths, "OBS")

    common = dict(units="t DM ha-1",
                  equation="M = (6.011 * sqrt(FPI) - 5.291) ** 2",
                  reference="Roxburgh et al. 2019, For. Ecol. Manage. 432:264-275, Eq. 1",
                  period="1985-2014")

    written = []
    for arr, name, src, order in [
        (rf_annual, "Eq1_M_histRF_mean_of_annual", "random forest (Step_01)", "mean_y Eq1(FPI_y)"),
        (rf_of_mean, "Eq1_M_histRF_eq1_of_mean", "random forest (Step_01)", "Eq1(mean_y FPI_y)"),
        (obs_annual, "Eq1_M_histOBS_mean_of_annual", "observed DCCEEW FPI", "mean_y Eq1(FPI_y)"),
        (obs_of_mean, "Eq1_M_histOBS_eq1_of_mean", "observed DCCEEW FPI", "Eq1(mean_y FPI_y)"),
    ]:
        dst = OUT_DIR / (name + ".tif")
        if dst.exists() and not args.overwrite:
            print("  %s exists, kept (--overwrite to redo)" % dst.name)
        else:
            write_gtiff(np.where(valid, arr, np.nan), dst, name,
                        dict(common, long_name=name, fpi_source=src,
                             averaging_order=order))
        written.append((name, arr, src, order))

    write_gtiff(np.where(valid, rf_mean_fpi, np.nan),
                OUT_DIR / "fpi_rf_1985-2014_mean_masked.tif",
                "fpi_rf_mean", dict(units="1", long_name="mean modelled FPI 1985-2014"))
    write_gtiff(np.where(valid, obs_mean_fpi, np.nan),
                OUT_DIR / "fpi_obs_1985-2014_mean.tif",
                "fpi_obs_mean", dict(units="1", long_name="mean observed FPI 1985-2014"))

    # --- the checks -------------------------------------------------------
    rows = []
    for name, arr, src, order in written:
        rows.append(dict(layer=name, fpi_source=src, averaging_order=order,
                         **stats(arr, valid)))

    def ratio_stats(num, den, label):
        ok = valid & np.isfinite(num) & np.isfinite(den) & (den > 0)
        r = num[ok] / den[ok]
        return dict(comparison=label,
                    median=float(np.median(r)),
                    mean=float(np.mean(r)),
                    p05=float(np.percentile(r, 5)),
                    p95=float(np.percentile(r, 95)),
                    pct_within_5pct=float(100 * np.mean(np.abs(r - 1) < 0.05)))

    comps = [
        ratio_stats(rf_annual, obs_annual, "RF / OBS, mean_of_annual (the denominator swap)"),
        ratio_stats(rf_of_mean, obs_of_mean, "RF / OBS, eq1_of_mean"),
        ratio_stats(rf_annual, rf_of_mean, "RF: mean_of_annual / eq1_of_mean (Jensen gap)"),
        ratio_stats(obs_annual, obs_of_mean, "OBS: mean_of_annual / eq1_of_mean (Jensen gap)"),
    ]

    if PIPELINE_HIST_M.exists():
        pipe = read_on_grid(PIPELINE_HIST_M)
        d = np.abs(pipe - obs_of_mean)[valid]
        comps.append(dict(comparison="rebuild check vs %s" % PIPELINE_HIST_M.name,
                          median=float(np.nanmedian(d)), mean=float(np.nanmean(d)),
                          p05=float(np.nanpercentile(d, 5)),
                          p95=float(np.nanpercentile(d, 95)),
                          pct_within_5pct=float(np.nanmax(d))))
        print("\nrebuild check: max |this Eq1_M_histOBS_eq1_of_mean - %s| = %.3e t DM ha-1"
              % (PIPELINE_HIST_M.name, float(np.nanmax(d))))
        if float(np.nanmax(d)) > 1e-3:
            print("  WARNING: the rebuild does not reproduce the pipeline's cached "
                  "denominator - do not use these layers until that is understood")

    pd.DataFrame(rows).to_csv(OUT_DIR / "hist_M_denominator_levels.csv", index=False)
    pd.DataFrame(comps).to_csv(OUT_DIR / "hist_M_denominator_comparison.csv", index=False)

    print("\n%-34s %9s %9s %9s" % ("layer", "mean", "median", "p95"))
    for r in rows:
        print("%-34s %9.3f %9.3f %9.3f" % (r["layer"], r["mean"], r["median"], r["p95"]))

    print("\n%-52s %8s %8s %8s" % ("ratio", "median", "p05", "p95"))
    for c in comps[:4]:
        print("%-52s %8.4f %8.4f %8.4f" % (c["comparison"], c["median"], c["p05"], c["p95"]))

    print("\nThe first row is what swapping the denominator does to M': the future\n"
          "M' moves by the reciprocal of it, cell by cell. A median near 1.000 means\n"
          "the forest's historical bias was small and the change is methodological\n"
          "rather than numerical - which is still the right thing to report.")
    print("\noutputs in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
