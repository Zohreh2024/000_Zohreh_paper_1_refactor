"""
Step 04 - future M' with BOTH sides of the ratio modelled by the same forest.

    M'_future = lambda x Original_M_2004 x Eq1(FPI_future) / Eq1(FPI_1985-2014)
                                              ^                 ^
                                        random forest      random forest
                                                           (was: observed FPI)

This does NOT reimplement the arithmetic. It invokes the repository's own
`Calculation_future_M_CSIRO/Step_08_apply_published_lambda.py --footing
original2004`, passing the modelled denominator through the `--hist-m` flag, so
the NaN handling, the MIN_HIST_M floor, lambda and the metadata are the
pipeline's and cannot drift from it. `Option_B_matched_footing/Step_02` runs the
same script the same way, with the observed denominator.

Two runs, because the averaging order has to match
--------------------------------------------------
Step_06 writes the numerator in two averaging orders and they are not the same
number (Eq. (1) is convex; median gap ~1.03). Each is paired here with the
denominator built in the SAME order by Step_03:

    run                numerator                        denominator
    mean_of_annual     M_<ssp>_<window>_mean.tif        Eq1_M_histRF_mean_of_annual
                       M_<ssp>_<year>.tif
    eq1_of_mean        M_from_mean_fpi_<ssp>_<win>.tif  Eq1_M_histRF_eq1_of_mean

Mixing them puts the Jensen gap into the ratio, where it reads as climate
change; that is the unresolved inconsistency described in
`Option_B_matched_footing/README.md`, and pairing by order settles it.

Writes  output_Mprime_rf/mean_of_annual/maxAbgMF_*.tif   240 annual + 8 means
        output_Mprime_rf/eq1_of_mean/maxAbgMF_*.tif        8
        output/Mprime_modelled_vs_observed_denominator.csv
        logs/step08_<run>.log

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_04_future_Mprime_modelled_footing.py --jobs 8
"""

import argparse
import os
import subprocess
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
STEP08 = ROOT / "Calculation_future_M_CSIRO" / "Step_08_apply_published_lambda.py"
OUT_DIR = HERE / "output"
MPRIME_DIR = HERE / "output_Mprime_rf"
LOG_DIR = HERE / "logs"
OPTION_B = ROOT / "Option_B_matched_footing" / "output_Mprime"
LAMBDA = ROOT / "Step_02_published_lambda" / "output" / "lambda_published.tif"
ORIGINAL_M = ROOT / "Step_02_published_lambda" / "output" / "original_M_2004.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"
ENV_PREFIX = r"C:\ProgramData\Anaconda3\envs\JinzhuLuto"

RUNS = [
    ("mean_of_annual", "Eq1_M_histRF_mean_of_annual.tif"),
    ("eq1_of_mean", "Eq1_M_histRF_eq1_of_mean.tif"),
]

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]


def run_step08(run_name, hist_m, jobs, force):
    dest = MPRIME_DIR / run_name
    existing = sorted(dest.glob("maxAbgMF_*.tif")) if dest.exists() else []
    if existing and not force:
        print("%s: %d rasters already present, skipping (--force to rebuild)"
              % (run_name, len(existing)))
        return dest

    dest.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / ("step08_%s.log" % run_name)

    cmd = ["conda", "run", "--no-capture-output", "-p", ENV_PREFIX, "python",
           str(STEP08), "--footing", "original2004", "--jobs", str(jobs),
           "--hist-m", str(hist_m), "--out-dir", str(dest),
           "--layers", run_name]
    print("\n=== %s ===\n%s\n" % (run_name, " ".join(cmd[6:])))
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, cwd=str(STEP08.parent),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            sys.stdout.write(line)
            fh.write(line)
        code = proc.wait()
    if code != 0:
        sys.exit("Step_08 (%s) failed with exit code %d - see %s" % (run_name, code, log))
    return dest


def read(path):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a[a == s.nodata] = np.nan
    return a


def compare(valid):
    """M' on the modelled denominator vs M' on the observed one (Option B).

    Also reports the change each implies against the historical baseline
    lambda x Original_M_2004, which is New_M_2019 by construction and is what
    FullCAM reads as the historical maxAbgM - so this column is the step FullCAM
    sees at the boundary between its historical and its future input.
    """
    base = None
    if LAMBDA.exists() and ORIGINAL_M.exists():
        base = read(LAMBDA) * read(ORIGINAL_M)

    rows = []
    for ssp in SSPS:
        for win in WINDOWS:
            for run_name, stem in [("mean_of_annual", "maxAbgMF_%s_%s_mean.tif" % (ssp, win)),
                                   ("eq1_of_mean", "maxAbgMF_from_mean_fpi_%s_%s.tif" % (ssp, win))]:
                new_p = MPRIME_DIR / run_name / stem
                old_p = OPTION_B / stem
                if not new_p.exists():
                    continue
                new = read(new_p)
                row = dict(ssp=ssp, window=win, averaging_order=run_name, layer=stem,
                           Mprime_modelled_mean=float(np.nanmean(new[valid])),
                           Mprime_modelled_median=float(np.nanmedian(new[valid])))
                if old_p.exists():
                    old = read(old_p)
                    ok = valid & np.isfinite(new) & np.isfinite(old) & (old > 0)
                    r = new[ok] / old[ok]
                    row.update(Mprime_observed_mean=float(np.nanmean(old[valid])),
                               ratio_modelled_over_observed_median=float(np.median(r)),
                               ratio_p05=float(np.percentile(r, 5)),
                               ratio_p95=float(np.percentile(r, 95)))
                if base is not None:
                    ok = valid & np.isfinite(new) & np.isfinite(base) & (base > 0)
                    pct = 100 * (new[ok] - base[ok]) / base[ok]
                    row.update(pct_change_vs_New_M_2019_median=float(np.median(pct)),
                               pct_change_p05=float(np.percentile(pct, 5)),
                               pct_change_p95=float(np.percentile(pct, 95)),
                               pct_cells_declining=float(100 * np.mean(pct < 0)))
                rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--compare-only", action="store_true")
    args = ap.parse_args()

    for run_name, hist_name in RUNS:
        hist_m = OUT_DIR / hist_name
        if not hist_m.exists():
            sys.exit("missing %s - run Step_03 first" % hist_m)

    if not args.compare_only:
        for run_name, hist_name in RUNS:
            run_step08(run_name, OUT_DIR / hist_name, args.jobs, args.force)

    with rasterio.open(NLUM_MASK) as t:
        valid = t.read(1) == 1

    df = compare(valid)
    if df.empty:
        sys.exit("no M' layers found to compare")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUT_DIR / "Mprime_modelled_vs_observed_denominator.csv"
    df.to_csv(dst, index=False)

    show = ["ssp", "window", "averaging_order", "Mprime_modelled_mean"]
    for c in ["ratio_modelled_over_observed_median", "pct_change_vs_New_M_2019_median"]:
        if c in df.columns:
            show.append(c)
    print("\n" + df[show].to_string(index=False, float_format=lambda v: "%8.4f" % v))
    print("\nratio_modelled_over_observed_median is how much M' moves when the")
    print("denominator is modelled rather than downloaded. pct_change_vs_New_M_2019")
    print("is the step FullCAM sees from its historical maxAbgM to this future input.")
    print("\nrasters in %s\ntable    %s" % (MPRIME_DIR, dst))


if __name__ == "__main__":
    main()
