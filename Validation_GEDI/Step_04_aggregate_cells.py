"""
Step 4 - aggregate footprints to NLUM cells, attach M' and FPI, apply the
fire flags.

Corrected from Level_4_03_attach_fpi.py. Three differences.

  1. Cells are NLUM cells. The cell identity was assigned in step 3 from
     NLUM's own transform, so M' and FPI are sampled at the centre of the
     same cell the footprints were pooled into. The original pooled on a
     0.01-degree grid offset half a cell from NLUM and then sampled at a point
     lying on an NLUM cell boundary.

  2. Fire flags are attached. For each cell the most recent burn year before
     each footprint's acquisition is looked up from the step 2 rasters, and a
     footprint is flagged when its cell burned within --recovery-years of
     acquisition. Black Summer is flagged separately. Cells are then
     summarised both with and without burnt footprints, so the effect of the
     fires on the answer is visible rather than assumed away.

  3. p99 is not reported below --min-footprints-p99. With 30 footprints the
     99th percentile is simply the maximum, which is not a percentile and is
     badly behaved. p95 remains the working statistic.

Usage
    python Step_04_aggregate_cells.py --mprime <New_M_2019.tif> \\
        --fpi-dir <annual FPI 1985-2014> --min-footprints 30
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
FIRE = HERE / "fire"

DEFAULT_MPRIME = (C.ROOT / "Data" / "Processed" / "maxAbgM_v2"
                  / "New_M_2019.tif")
DEFAULT_FPI = C.ROOT / "Random_forest_CSIRO" / "required_data" / "fpi"


def load_fire_stack(shape):
    """last-burn-year per cell, and the per-year rasters if present."""
    import rasterio
    years = {}
    for p in sorted(FIRE.glob("burn_year_*.tif")):
        y = int(p.stem.split("_")[-1])
        with rasterio.open(p) as s:
            years[y] = s.read(1).astype(bool)
    if not years:
        print("  no fire rasters found in %s - run Step_02 first. "
              "Continuing WITHOUT fire flags." % FIRE)
    return years


def attach_fire(df, years, recovery):
    """Flag a footprint if its cell burned within `recovery` years before it."""
    if not years:
        df["burnt_before_acq"] = False
        df["black_summer"] = False
        df["years_since_fire"] = np.nan
        return df
    acq_year = pd.to_datetime(df["acq_time"]).dt.year.values
    rows, cols = df["nlum_row"].values, df["nlum_col"].values
    last = np.zeros(len(df), dtype="int32")
    bs = np.zeros(len(df), dtype=bool)
    for y, arr in years.items():
        hit = arr[rows, cols]
        last = np.where(hit & (y <= acq_year) & (y > last), y, last)
        if y in (2019, 2020):
            bs |= hit
    df["last_burn_year"] = last
    df["years_since_fire"] = np.where(last > 0, acq_year - last, np.nan)
    df["burnt_before_acq"] = (last > 0) & ((acq_year - last) <= recovery)
    df["black_summer"] = bs
    return df


def sample_at_cells(cells, raster, colname):
    """Sample a raster at NLUM cell centres by index, not by coordinate."""
    import rasterio
    with rasterio.open(raster) as s:
        a = s.read(1, masked=True).filled(np.nan)
    cells[colname] = a[cells["nlum_row"].values, cells["nlum_col"].values]
    return cells


def mean_fpi(cells, fpi_dir, pattern="fpi_*.tif"):
    import rasterio
    files = sorted(Path(fpi_dir).glob(pattern))
    files = [f for f in files
             if f.stem.split("_")[-1].isdigit()
             and 1985 <= int(f.stem.split("_")[-1]) <= 2014]
    if not files:
        raise SystemExit("no annual FPI rasters in %s" % fpi_dir)
    r, c = cells["nlum_row"].values, cells["nlum_col"].values
    acc = np.zeros((len(files), len(cells)), dtype="float64")
    for i, f in enumerate(files):
        with rasterio.open(f) as s:
            acc[i] = s.read(1, masked=True).filled(np.nan)[r, c]
    cells["fpi_mean"] = np.nanmean(acc, axis=0)
    cells["fpi_sd"] = np.nanstd(acc, axis=0)
    print("  FPI averaged over %d annual rasters" % len(files))
    return cells


def fixed_n_p95(df, n=30, draws=25, seed=0):
    """p95 from `draws` random subsamples of exactly `n` footprints per cell.

    A naive p95 rises with the number of footprints, so busy cells look taller
    than sparse ones for sampling reasons alone. Holding n fixed removes that
    (the same correction as Option_B_matched_footing suggestion S3).
    """
    rng = np.random.default_rng(seed)
    out = {}
    for cid, v in df.groupby("cell_id")["agbd"]:
        a = v.values
        if a.size < n:
            continue
        out[cid] = np.mean([np.quantile(rng.choice(a, n, replace=False), 0.95)
                            for _ in range(draws)])
    return pd.Series(out, name="agbd_p95_n%d" % n)


def summarise(df, min_fp, min_p99, label):
    g = df.groupby("cell_id")
    out = pd.DataFrame({
        "n_footprints": g["agbd"].size(),
        "agbd_mean": g["agbd"].mean(),
        "agbd_median": g["agbd"].median(),
        "agbd_p95": g["agbd"].quantile(0.95),
        "agbd_p99": g["agbd"].quantile(0.99),
        "agbd_max": g["agbd"].max(),
        "agbd_se_mean": g["agbd_se"].mean(),
        "sensitivity_mean": g["sensitivity"].mean(),
        "nlum_row": g["nlum_row"].first(),
        "nlum_col": g["nlum_col"].first(),
        "cell_lon": g["cell_lon"].first(),
        "cell_lat": g["cell_lat"].first(),
        "region": g["region"].first(),
        "burnt_frac": g["burnt_before_acq"].mean(),
        "black_summer_frac": g["black_summer"].mean(),
    }).reset_index()
    before = len(out)
    out = out[out.n_footprints >= min_fp].copy()
    fixed = fixed_n_p95(df[df.cell_id.isin(out.cell_id)], n=min_fp)
    out[fixed.name] = out.cell_id.map(fixed)
    # p99 on a handful of shots is the maximum, not a percentile.
    out.loc[out.n_footprints < min_p99, "agbd_p99"] = np.nan
    print("  %-22s %6d cells -> %6d with >= %d footprints "
          "(p99 kept for %d)"
          % (label, before, len(out), min_fp,
             int((out.n_footprints >= min_p99).sum())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--footprints",
                    default=str(OUT / "gedi_l4a_footprints.parquet"))
    ap.add_argument("--mprime", default=str(DEFAULT_MPRIME))
    ap.add_argument("--tag", default=None,
                    help="suffix for output files, so runs against different "
                         "M' layers do not overwrite each other")
    ap.add_argument("--fpi-dir", default=str(DEFAULT_FPI))
    ap.add_argument("--min-footprints", type=int, default=30)
    ap.add_argument("--min-footprints-p99", type=int, default=100)
    ap.add_argument("--recovery-years", type=int,
                    default=C.DEFAULT_RECOVERY_YEARS)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    src = Path(args.footprints)
    if not src.exists():
        raise SystemExit("run Step_03 first - %s is missing" % src)
    df = pd.read_parquet(src)
    print("%d footprints, %d NLUM cells" % (len(df), df.cell_id.nunique()))

    transform, h, w = C.nlum_grid()
    years = load_fire_stack((h, w))
    df = attach_fire(df, years, args.recovery_years)
    if years:
        print("  burnt within %d years of acquisition: %.1f%% of footprints"
              % (args.recovery_years, 100 * df.burnt_before_acq.mean()))
        print("  in a 2019-20 fire footprint            : %.1f%%"
              % (100 * df.black_summer.mean()))

    print("\naggregating")
    allc = summarise(df, args.min_footprints, args.min_footprints_p99, "all")
    unb = summarise(df[~df.burnt_before_acq], args.min_footprints,
                    args.min_footprints_p99, "fire-excluded")

    for name, cells in (("all", allc), ("unburnt", unb)):
        if cells.empty:
            print("  %s: no cells survived" % name)
            continue
        cells = sample_at_cells(cells, args.mprime, "m_prime")
        cells = mean_fpi(cells, args.fpi_dir)
        cells = cells[np.isfinite(cells.m_prime)
                      & np.isfinite(cells.fpi_mean)].copy()
        cells["mprime_source"] = Path(args.mprime).name
        cells["mprime_over_p95"] = cells.m_prime / cells.agbd_p95
        cells["p95_exceeds_mprime"] = cells.agbd_p95 > cells.m_prime
        fixed_col = "agbd_p95_n%d" % args.min_footprints
        cells["p95_n_exceeds_mprime"] = cells[fixed_col] > cells.m_prime
        suffix = "_%s" % args.tag if args.tag else ""
        dst = OUT / ("gedi_cells_%s%s.csv" % (name, suffix))
        cells.to_csv(dst, index=False)
        print("\n%s: %d cells" % (name, len(cells)))
        print("  FPI %.2f to %.2f, median p95 AGBD %.1f Mg/ha"
              % (cells.fpi_mean.min(), cells.fpi_mean.max(),
                 cells.agbd_p95.median()))
        print("  median M'/p95 %.2f, p95 exceeds M' in %.1f%% of cells"
              % (cells.mprime_over_p95.median(),
                 100 * cells.p95_exceeds_mprime.mean()))
        print("  fixed-n p95 exceeds M' in %.1f%% of cells"
              % (100 * cells.p95_n_exceeds_mprime.mean()))
        print("  wrote %s" % dst)


if __name__ == "__main__":
    main()
