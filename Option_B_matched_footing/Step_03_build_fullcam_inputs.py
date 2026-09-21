"""
Step 03 - FullCAM maxAbgMF inputs on the matched footing.

Turns the eight window means from Step_02 into the NetCDF form FullCAM reads,
using `FullCAM_input_CSIRO_data/fullcam_io.write_annual` so the dims, dtype,
CRS and attributes match every other input in that set exactly: a single data
variable `maxAbgMF`, dims ('y', 'x') with y descending, float64, EPSG:4283,
NaN outside the NLUM mask.

These are written HERE rather than into FullCAM_input_CSIRO_data/M/, so that
nothing in the existing input set changes until the footing decision is made.
To adopt Option B, copy fullcam_inputs/*.nc over FullCAM_input_CSIRO_data/M/.

The companion memo's section 4 is the reason this matters: the FullCAM
historical input (Historical_Anuclim_1985-2014/maxAbgMF.nc) is New_M_2019,
which is on the Original_M_2004 footing. These futures sit on that same
footing, so the step between baseline and future is the projected climate
change and nothing else. Step_04 verifies exactly that.

Which window layer, and why
---------------------------
Step_02 writes each window in two averaging orders, and they are not the same
number because Eq. (1) is convex:

    maxAbgMF_<ssp>_<win>_mean.tif           mean_y[ Eq1(FPI_y) ]
    maxAbgMF_from_mean_fpi_<ssp>_<win>.tif  Eq1( mean_y FPI_y )

This step uses the SECOND, which is what Eq. (1) is defined on. Roxburgh et al.
(2019), Section 2, p. 265: FPI "summarises potential site productivity for any
given location", Eq. (1) gives "the predicted maximum AGB for a given FPI", and
"parameter M is constant for any location in Australia". One FPI per location
in, one M out - so for a 30-year window it is the window-mean FPI that enters
the equation. Calculation_future_M_CSIRO/Step_06 says the same in the repository's
own words: use `M_from_mean_fpi` "when feeding a single period value to FullCAM".

It previously used the first, which is an extension the paper does not describe
and which runs about 3% high by Jensen's inequality. `--order mean_of_annual`
restores the old behaviour for comparison.

Writes  fullcam_inputs/maxAbgMF_<SSP>_<window>.nc      8
        fullcam_inputs/maxAbgMF_<SSP>_<window>.tif     8
        outputs/fullcam_inputs_summary.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "FullCAM_input_CSIRO_data"))
from fullcam_io import grid_coords, verify, write_annual  # noqa: E402

MASK_PATH = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"
SRC = HERE / "output_Mprime"
DEST = HERE / "fullcam_inputs"
OUT = HERE / "outputs"

VAR = "maxAbgMF"
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
FOOTING_NOTE = ("M' = lambda_published x Original_M_2004 x Eq1(FPI_future) / "
                "Eq1(FPI_1985-2014). Matched footing: lambda's denominator "
                "and its multiplicand are the same layer, so Eq.(3) is applied "
                "to matched terms and the historical limit is New_M_2019.")
ORDER_FILE = {"eq1_of_mean": "%s_from_mean_fpi_%s_%s.tif",
              "mean_of_annual": "%s_%s_%s_mean.tif"}
ORDER_NOTE = {
    "eq1_of_mean": "Eq1(mean_y FPI_y): the window-mean FPI enters Eq. (1), "
                   "which is the quantity Eq. (1) is defined on "
                   "(Roxburgh et al. 2019, Sec. 2, p. 265)",
    "mean_of_annual": "mean_y[Eq1(FPI_y)]: Eq. (1) per year, then averaged - "
                      "an extension the paper does not describe, about 3% high "
                      "by Jensen's inequality",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--order", choices=list(ORDER_FILE), default="eq1_of_mean",
                    help="which averaging order of the window mean to write "
                         "(default: the method)")
    args = ap.parse_args()
    print("averaging order: %s" % args.order)
    print("  %s" % ORDER_NOTE[args.order])

    DEST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    with rasterio.open(MASK_PATH) as s:
        mask = s.read(1) == 1
        transform, height, width = s.transform, s.height, s.width
    y, x = grid_coords(transform, height, width)

    rows = []
    for ssp in SSPS:
        for win in WINDOWS:
            src = SRC / (ORDER_FILE[args.order] % (VAR, ssp, win))
            if not src.exists():
                sys.exit("missing %s - run Step_02 first" % src)
            with rasterio.open(src) as s:
                a = s.read(1, masked=True).filled(np.nan).astype("float64")
            a = np.where(mask, a, np.nan)

            stem = "%s_%s_%s" % (VAR, ssp.upper(), win)
            nc = DEST / (stem + ".nc")
            write_annual(
                nc, a, y, x,
                var_attrs=dict(units="t DM ha-1",
                               long_name="maximum above-ground biomass, "
                                         "future (Original_M_2004 footing)",
                               footing="original2004",
                               averaging_order=args.order,
                               averaging_note=ORDER_NOTE[args.order],
                               note=FOOTING_NOTE),
                attrs=dict(scenario=ssp.upper(), period=win,
                           source=str(src),
                           built_by="Option_B_matched_footing/"
                                    "Step_03_build_fullcam_inputs.py"))
            verify(nc, shape=(height, width), valid=mask)

            with rasterio.open(MASK_PATH) as s:
                prof = dict(s.profile)
            prof.update(dtype="float32", count=1, nodata=np.nan,
                        compress="lzw", tiled=True, blockxsize=256,
                        blockysize=256)
            with rasterio.open(DEST / (stem + ".tif"), "w", **prof) as dst:
                dst.write(a.astype("float32"), 1)
                dst.update_tags(units="t DM ha-1", footing="original2004",
                                averaging_order=args.order)

            rows.append({"scenario": ssp.upper(), "window": win,
                         "file": nc.name,
                         "median": float(np.nanmedian(a[mask])),
                         "mean": float(np.nanmean(a[mask])),
                         "min": float(np.nanmin(a[mask])),
                         "max": float(np.nanmax(a[mask])),
                         "n_nan_in_mask": int((mask & ~np.isfinite(a)).sum())})
            print("  %-34s median %6.2f  mean %6.2f  t DM/ha"
                  % (nc.name, rows[-1]["median"], rows[-1]["mean"]))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "fullcam_inputs_summary.csv", index=False)
    bad = int(df.n_nan_in_mask.sum())
    print("\n%d files written to %s" % (len(df), DEST))
    print("NaN inside the NLUM mask across all files: %d" % bad)
    if bad:
        sys.exit("unexpected NaN inside the mask")


if __name__ == "__main__":
    main()
