"""
Run 4, step 1 - calibrate a maturity rule on live basal area.

The problem this addresses
--------------------------
Maturity is currently assigned from the tree list: a stem of 50 cm or more is
verified mature, a largest stem of 30-50 cm is likely mature, below that is
young or shrubby. That rule needs stem records, and only 2,047 of the library's
15,904 site visits have any. The four largest sources have none at all:

    Forestry Corporation Commercial Estate (NSW)   6,718 visits, 0% with stems
    Queensland NFPP                                3,158 visits, 0%
    Forestry Tasmania                              2,201 visits, 0%
    Department of Parks and Wildlife (WA)            898 visits, 0%

So the rule caps the reference sample at 600 sites, of the 1,688 that survive
every other filter. A rule on live basal area - which the SITE table reports for
almost every visit - could be applied to all of them.

What this step does, and what it is honest about
------------------------------------------------
It calibrates the basal-area rule on the 756 reference sites that DO carry a
DBH-based label, and then reports how well it reproduces that label. The rule is
only worth applying if that reproduction is decent, and the step is written to
show the answer either way rather than to justify the rule.

There is a reason for caution built into the two quantities. Maturity is defined
by the LARGEST STEM; basal area is the summed cross-section of ALL stems over
the plot area. A sparse stand of huge old trees and a dense thicket of saplings
can carry the same basal area. So the rule cannot separate an old stand from a
crowded young one, and any gain in sample size is bought with that confusion.

The class medians make the case worth testing and also flag the difficulty:

    verified mature   14.75 m2/ha      n = 327
    likely mature      6.75            n = 273
    young or shrubby   2.99            n = 156
    unverified        15.72            n = 932   <- no label, and the HIGHEST

The unverified group's basal area sits above the verified group's. Either those
sites really are mature - which is the case for applying the rule - or basal
area is not discriminating maturity in that group at all. Nothing in the
labelled data can settle which, and the report says so.

Reads   ../../outputs/reference_table.csv
Writes  outputs/calibration.csv          thresholds and their skill
        outputs/roc.csv                  the full curve
        outputs/class_summary.csv
        plots/fig_01_calibration.png

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_calibrate_rule.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"
MATURE = ["verified mature", "likely mature"]

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_MAT, C_IMM, C_UNV = "#2a78d6", "#eb6834", "#b9b8b4"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="both"):
    ax.tick_params(labelsize=9, colors=INK_2, length=2.5, width=0.6)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID_C, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.6)
        ax.spines[sp].set_color("#c9c8c4")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    return ax


def stv_dir():
    for d in [HERE] + list(HERE.parents):
        if (d / "Step_03_match_and_validate.py").exists():
            return d
    raise SystemExit("Space_time_validation not found")


def roc(y, score):
    """Sensitivity and specificity at every distinct threshold."""
    order = np.argsort(-score)
    y, score = y[order], score[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    P, N = y.sum(), (1 - y).sum()
    tpr, fpr = tp / P, fp / N
    auc = float(np.trapz(tpr, fpr))
    return pd.DataFrame({"threshold": score, "sensitivity": tpr,
                         "one_minus_specificity": fpr}), auc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--thresholds", nargs="*", type=float,
                    default=[5, 7, 9, 10, 12, 14, 16, 20])
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    ref = pd.read_csv(stv_dir() / "outputs" / "reference_table.csv",
                      low_memory=False)
    ref["labelled"] = ref["max_dbh"].notna()
    lab = ref[ref["labelled"] & ref["live_ba"].notna()].copy()
    lab["is_mature"] = lab["maturity"].isin(MATURE).astype(int)
    print("reference table %d sites; %d carry a DBH label and a basal area"
          % (len(ref), len(lab)))

    cls = ref.groupby("maturity").agg(
        sites=("live_ba", "size"), ba_median=("live_ba", "median"),
        ba_p25=("live_ba", lambda v: float(np.nanpercentile(v, 25))),
        ba_p75=("live_ba", lambda v: float(np.nanpercentile(v, 75))),
        agb_median=("agb", "median")).reset_index()
    cls.to_csv(OUT_DIR / "class_summary.csv", index=False)
    print("\n%s" % cls.to_string(index=False,
                                 float_format=lambda v: "%.2f" % v))

    curve, auc = roc(lab["is_mature"].to_numpy(),
                     lab["live_ba"].to_numpy(float))
    curve.to_csv(OUT_DIR / "roc.csv", index=False)
    print("\n=== can basal area reproduce the DBH label? ===")
    print("  area under the ROC curve: %.3f" % auc)
    print("  (0.5 is a coin toss; 0.7 is weak but usable; 0.8 is decent)")

    rows = []
    for th in args.thresholds:
        pred = (lab["live_ba"] >= th).astype(int)
        tp = int(((pred == 1) & (lab["is_mature"] == 1)).sum())
        fp = int(((pred == 1) & (lab["is_mature"] == 0)).sum())
        fn = int(((pred == 0) & (lab["is_mature"] == 1)).sum())
        tn = int(((pred == 0) & (lab["is_mature"] == 0)).sum())
        sens = tp / max(tp + fn, 1)
        spec = tn / max(tn + fp, 1)
        rows.append(dict(
            threshold=th, true_mature=tp, false_mature=fp,
            missed_mature=fn, true_immature=tn,
            sensitivity=sens, specificity=spec,
            balanced_accuracy=(sens + spec) / 2,
            accuracy=(tp + tn) / len(lab),
            sites_selected_all=int((ref["live_ba"] >= th).sum())))
    cal = pd.DataFrame(rows)
    cal["auc"] = auc
    cal.to_csv(OUT_DIR / "calibration.csv", index=False)
    print("\n%s" % cal[["threshold", "sensitivity", "specificity",
                        "balanced_accuracy", "sites_selected_all"]].to_string(
        index=False, float_format=lambda v: "%.3f" % v))

    best = cal.loc[cal["balanced_accuracy"].idxmax()]
    print("\nbest balanced accuracy at %.0f m2/ha: sensitivity %.2f, "
          "specificity %.2f, selects %d of %d sites"
          % (best["threshold"], best["sensitivity"], best["specificity"],
             best["sites_selected_all"], len(ref)))

    # ---- the figure --------------------------------------------------- #
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.6))
    ax = tidy(axes[0], grid_axis="y")
    bins = np.linspace(0, np.nanpercentile(ref["live_ba"], 97), 40)
    for cl, colour in (("verified mature", C_MAT), ("likely mature", "#7fb3f0"),
                       ("young or shrubby", C_IMM)):
        v = ref.loc[ref["maturity"] == cl, "live_ba"].dropna()
        ax.hist(v, bins=bins, histtype="step", lw=2.0, color=colour,
                label="%s (%d)" % (cl, len(v)), zorder=4)
    v = ref.loc[ref["maturity"] == "unverified", "live_ba"].dropna()
    ax.hist(v, bins=bins, color=C_UNV, alpha=0.55,
            label="unverified (%d) - no label" % len(v), zorder=3)
    ax.axvline(best["threshold"], color=INK, lw=1.4, ls="--", zorder=5)
    ax.set_xlabel("live basal area (m$^2$/ha)")
    ax.set_ylabel("sites")
    ax.set_title("a) What basal area has to separate", loc="left")
    ax.legend(fontsize=8.2, frameon=False)

    ax = tidy(axes[1])
    ax.plot(curve["one_minus_specificity"], curve["sensitivity"], lw=2.2,
            color=C_MAT, zorder=4)
    ax.plot([0, 1], [0, 1], color=INK_2, lw=1.1, ls="--", zorder=3)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.set_xlabel("1 - specificity (immature sites wrongly kept)")
    ax.set_ylabel("sensitivity (mature sites kept)")
    ax.set_title("b) How well it reproduces the DBH label\nAUC = %.3f" % auc,
                 loc="left")

    ax = tidy(axes[2], grid_axis="y")
    x = np.arange(len(cal))
    ax.bar(x - 0.2, cal["sensitivity"], 0.38, color=C_MAT,
           label="sensitivity", zorder=3)
    ax.bar(x + 0.2, cal["specificity"], 0.38, color=C_IMM,
           label="specificity", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels([("%g" % t) for t in cal["threshold"]], fontsize=8.6)
    ax.set_xlabel("threshold (m$^2$/ha)")
    ax.set_title("c) The trade-off at each threshold", loc="left")
    ax.legend(fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "fig_01_calibration.png", dpi=200)
    plt.close(fig)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
