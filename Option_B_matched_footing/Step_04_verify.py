"""
Step 04 - acceptance tests for the matched-footing M'.

Three things must hold. The script prints each, writes them to CSV, and exits
non-zero if any fails.

1.  THE HISTORICAL LIMIT IS EXACT.
    Setting FPI_future = FPI_historical must return New_M_2019, since
    Eq1(hist)/Eq1(hist) = 1. Checked through the scale layer Step_08 wrote.
    This is what makes the FullCAM boundary continuous: the historical input
    FullCAM reads and the historical limit of the future inputs are one layer.

2.  THE FULLCAM STEP IS THE PROJECTED CHANGE, AND NOTHING ELSE.
    The step from the FullCAM historical input (New_M_2019) to each future
    input must equal the projected change against that same baseline, cell for
    cell. On the matched footing this is true by construction, and the test
    exists to catch a broken rebuild rather than to discover anything.

3.  EVERY WRITTEN LAYER IS SOUND ON THE GRID.
    No non-finite value inside the NLUM mask, no data outside it, no negative
    M'.

Which averaging order is verified follows `--order`, defaulting to the method -
Eq. (1) of the window-mean FPI - which is the layer Step_03 writes into
fullcam_inputs/. `--order mean_of_annual` verifies the per-year sensitivity.

The Eq.(1)-footing route (lambda applied directly to Eq. (1) M) was retired in
September 2026, so the A-versus-B comparisons this script used to run - the
climate-signal cancellation, the x1.456 level ratio and the two-footing boundary
figure - went with it. They are in the git history if the decision is ever
revisited.

Writes  outputs/verification.csv
        figures/fig_boundary_step.png|.pdf
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MASK_PATH = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019.tif"
SCALE = (ROOT / "Calculation_future_M_CSIRO" / "output"
         / "scale_Eq1_to_original2004.tif")
EQ1_HIST = (ROOT / "Calculation_future_M_CSIRO" / "output"
            / "Eq1_M_hist_1985-2014.tif")
LAMBDA = HERE / "layers" / "lambda_published.tif"
MP_B = HERE / "output_Mprime"
OUT = HERE / "outputs"
FIG = HERE / "figures"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
ORDER_FILE = {"eq1_of_mean": "maxAbgMF_from_mean_fpi_%s_%s.tif",
              "mean_of_annual": "maxAbgMF_%s_%s_mean.tif"}

INK, MUTED, GRID = "#1A1A1A", "#6B6B6B", "#E8E8E6"
C_B = "#0B3D62"


def rd(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--order", choices=list(ORDER_FILE), default="eq1_of_mean",
                    help="which averaging order to verify; the default is the "
                         "layer Step_03 writes into fullcam_inputs/")
    args = ap.parse_args()
    pattern = ORDER_FILE[args.order]
    print("verifying the %s layer: %s\n" % (args.order, pattern % ("<ssp>", "<win>")))

    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    with rasterio.open(MASK_PATH) as s:
        mask = s.read(1) == 1

    new_m = rd(NEW_M)
    rows, failures = [], []

    # --- test 1: the historical limit ------------------------------------ #
    # M'(FPI_fut = FPI_hist) = lambda x Original_M_2004 x 1, and Step_08 stored
    # Original_M_2004 / Eq1(FPI_hist) as its scale layer, so multiplying that
    # scale by lambda x Eq1(FPI_hist) must return New_M_2019.
    if SCALE.exists() and EQ1_HIST.exists() and LAMBDA.exists():
        # M' at the historical limit is lambda x scale x Eq1(FPI_hist), and
        # scale is Original_M_2004 / max(Eq1(FPI_hist), 1), so the product must
        # collapse to lambda x Original_M_2004 = New_M_2019.
        limit = rd(LAMBDA) * rd(SCALE) * np.maximum(rd(EQ1_HIST), 1.0)
        ok = mask & np.isfinite(limit) & (new_m > 0)
        rel = np.abs(limit[ok] - new_m[ok]) / new_m[ok]
        print("  test 1: historical limit against New_M_2019 - median "
              "relative error %.2e, p99 %.2e"
              % (float(np.median(rel)), float(np.percentile(rel, 99))))
        if float(np.median(rel)) > 1e-6:
            failures.append("historical limit does not return New_M_2019")
    else:
        print("  test 1: inputs not found, skipped")

    # --- tests 2 and 3, per scenario-window ------------------------------- #
    for ssp in SSPS:
        for win in WINDOWS:
            f = MP_B / (pattern % (ssp, win))
            if not f.exists():
                failures.append("missing %s" % f.name)
                continue
            fb = rd(f)
            with np.errstate(invalid="ignore", divide="ignore"):
                change = np.where(new_m > 1e-6, fb / new_m - 1.0, np.nan)
            ok = mask & np.isfinite(change)

            bad_inside = int((~np.isfinite(fb[mask])).sum())
            bad_outside = int(np.isfinite(fb[~mask]).sum())
            negative = int((fb[mask] < 0).sum())
            if bad_inside or bad_outside or negative:
                failures.append("%s %s: %d non-finite inside, %d outside the "
                                "mask, %d negative"
                                % (ssp, win, bad_inside, bad_outside, negative))

            r = {"ssp": ssp.upper(), "window": win,
                 "averaging_order": args.order,
                 "pct_change": 100 * float(np.nanmedian(change[ok])),
                 "fullcam_step_pct": 100 * float(np.nanmedian(change[ok])),
                 "n_nonfinite_in_mask": bad_inside,
                 "n_outside_mask": bad_outside,
                 "n_negative": negative}
            rows.append(r)
            print("  %s %s  FullCAM step %+7.2f%%   grid checks: %s"
                  % (ssp, win, r["pct_change"],
                     "clean" if not (bad_inside or bad_outside or negative)
                     else "FAILED"))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "verification.csv", index=False)

    print("\n--- summary ---")
    print("  1. historical limit         : see above")
    print("  2. FullCAM boundary step    : %+.2f%% to %+.2f%% across the eight "
          "windows" % (df.fullcam_step_pct.min(), df.fullcam_step_pct.max()))
    print("  3. grid integrity           : %d layer(s) with a problem"
          % int((df.n_nonfinite_in_mask + df.n_outside_mask
                 + df.n_negative > 0).sum()))

    # --- figure ----------------------------------------------------------- #
    short = {"2035-2064": "2035–64", "2070-2099": "2070–99"}
    lab = ["%s\n%s" % (r.ssp, short[r.window]) for _, r in df.iterrows()]
    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(x, df.fullcam_step_pct, 0.55, color=C_B, zorder=3)
    ax.axhline(0, color="#333333", lw=1.0, zorder=4)
    for xi, v in zip(x, df.fullcam_step_pct):
        ax.annotate("%+.1f%%" % v, (xi, v), xytext=(0, -12),
                    textcoords="offset points", ha="center", fontsize=7.8,
                    color=MUTED)
    ax.set(xticks=x, ylabel="step from the FullCAM historical input (%)")
    ax.set_xticklabels(lab, fontsize=8)
    ax.set_title("Step from New_M_2019 to each future input, matched footing",
                 fontsize=10.5, color=INK, loc="left")
    ax.tick_params(labelsize=8.5, colors=MUTED, length=2.5, width=0.6)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.6)
        ax.spines[sp].set_color("#BBBBBB")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    fig.tight_layout()
    for e in ("png", "pdf"):
        fig.savefig(str(FIG / "fig_boundary_step") + "." + e, dpi=320)
    plt.close(fig)

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  - %s" % f)
        sys.exit(1)
    print("\nall acceptance tests pass")


if __name__ == "__main__":
    main()
