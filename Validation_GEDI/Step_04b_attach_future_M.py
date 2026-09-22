"""
Step 4b - attach the eight future M' layers to the cells Step 4 already built.

Everything Step 4 computes from the footprints - the per-cell GEDI statistics,
the fire flags, the mean FPI - is independent of which M' layer it is later
compared against. Only the sampled M' column changes. So rather than re-reading
the 532 MB footprint table eight more times, this step takes the cell table
Step 4 wrote for New_M_2019 and re-samples each future layer at the same NLUM
cell indices, writing one table per layer in exactly the format Step 5 reads.

The layers attached
-------------------
    Data/Processed/maxAbgM_v2/New_M_2019.tif                     the anchor
    FPI_Accuracy_check/output_Mprime_rf/eq1_of_mean/
        maxAbgMF_from_mean_fpi_<ssp>_<window>.tif                the eight

M' with every component of the ratio produced by the random forest, on the
method's averaging order - Eq. (1) of the window-mean FPI on both sides of

    M'_future = New_M_2019 x Eq1(mean FPI_future) / Eq1(mean FPI_1985-2014)

so the historical limit of the future layers IS the anchor, by construction.
That matters for reading Step 5: a difference between a future layer's
exceedance rate and the anchor's is entirely the projected climate change, with
nothing else moving.

What this makes testable
------------------------
GEDI measures the biomass standing in 2019-2024. A future M' is the maximum a
site could carry in 2035-2099. Present-day biomass exceeding a future maximum is
the one direct piece of evidence against a projection: it says a stand already
carries more than the model claims the site will be able to support decades from
now. That is not impossible - a drying climate can lower a site's ceiling below
its current stock, and the stand would then be expected to decline - but it is a
strong claim, it is checkable today, and the rate at which it happens should
order with forcing. Step 5 reports it.

Reads   outputs/gedi_cells_{all,unburnt}_New_M_2019.csv     from Step 4
Writes  outputs/gedi_cells_{all,unburnt}_<layer>.csv        one per future layer

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_04b_attach_future_M.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

ANCHOR_TAG = "New_M_2019"
MPRIME_DIR = (C.ROOT / "FPI_Accuracy_check" / "output_Mprime_rf" / "eq1_of_mean")
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]

# The columns Step 4 derives from M'. They have to be recomputed, not copied.
DERIVED = ["m_prime", "mprime_source", "mprime_over_p95", "p95_exceeds_mprime",
           "p95_n_exceeds_mprime"]


def future_layers():
    out = {}
    for w in WINDOWS:
        for s in SSPS:
            tag = "future_%s_%s" % (s, w)
            out[tag] = MPRIME_DIR / ("maxAbgMF_from_mean_fpi_%s_%s.tif"
                                     % (s, w))
    return out


def sample_at_cells(cells, raster, colname):
    """Sample a raster at NLUM cell centres by index, not by coordinate.

    The same function Step 4 uses, repeated here rather than imported so this
    step does not depend on Step 4 staying importable.
    """
    import rasterio
    with rasterio.open(raster) as s:
        a = s.read(1, masked=True).filled(np.nan)
    cells[colname] = a[cells["nlum_row"].values, cells["nlum_col"].values]
    return cells


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--anchor-tag", default=ANCHOR_TAG,
                    help="the Step 4 table to take the GEDI statistics from")
    ap.add_argument("--min-footprints", type=int, default=30,
                    help="must match the value Step 4 ran with, since it names "
                         "the fixed-n column")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    fixed_col = "agbd_p95_n%d" % args.min_footprints
    layers = future_layers()
    missing = [str(p) for p in layers.values() if not p.exists()]
    if missing:
        raise SystemExit("missing M' layer(s):\n  " + "\n  ".join(missing))

    for subset in ("all", "unburnt"):
        src = OUT / ("gedi_cells_%s_%s.csv" % (subset, args.anchor_tag))
        if not src.exists():
            raise SystemExit("run Step_04 first - %s is missing" % src)
        base = pd.read_csv(src)
        base = base.drop(columns=[c for c in DERIVED if c in base.columns])
        print("\n%s: %s cells from %s"
              % (subset, format(len(base), ","), src.name))

        for tag, path in layers.items():
            dst = OUT / ("gedi_cells_%s_%s.csv" % (subset, tag))
            if dst.exists() and not args.overwrite:
                print("  %-34s exists, kept" % tag)
                continue
            cells = base.copy()
            cells = sample_at_cells(cells, path, "m_prime")
            cells = cells[np.isfinite(cells.m_prime)].copy()
            cells["mprime_source"] = path.name
            cells["mprime_over_p95"] = cells.m_prime / cells.agbd_p95
            cells["p95_exceeds_mprime"] = cells.agbd_p95 > cells.m_prime
            cells["p95_n_exceeds_mprime"] = cells[fixed_col] > cells.m_prime
            cells.to_csv(dst, index=False)
            print("  %-34s %s cells, median M' %6.1f, mean AGBD exceeds M' in "
                  "%5.1f%% of cells"
                  % (tag, format(len(cells), ","), cells.m_prime.median(),
                     100 * (cells.agbd_mean > cells.m_prime).mean()))

    print("\ntables in %s" % OUT)


if __name__ == "__main__":
    main()
