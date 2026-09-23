"""
Run 4, step 3 - the figures.

    fig_02  the decisive comparison: the criterion works, the expansion does not
    fig_03  what the expansion adds, provider by provider

fig_01, the calibration, is written by Step_01.

Reads   outputs/run04_headline.csv, ../../outputs/reference_table.csv
Writes  plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_plots.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from matplotlib.patches import Patch                           # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402
from scipy import stats                                        # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_DBH, C_OK, C_BAD, C_NULL = "#6b6a66", "#2a78d6", "#e34948", "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="y"):
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
    raise SystemExit("not found")


LABEL = {"dbh_rule": "DBH rule\n(Run 0)", "ba_05": "BA $\\geq$ 5",
         "ba_07": "BA $\\geq$ 7", "ba_09": "BA $\\geq$ 9",
         "ba_14": "BA $\\geq$ 14",
         "ba_07_labelled": "BA $\\geq$ 7\nlabelled sites only"}


def fig_decisive(h):
    d = h.set_index("config")
    order = [c for c in ["dbh_rule", "ba_07_labelled", "ba_05", "ba_07",
                         "ba_09", "ba_14"] if c in d.index]
    x = np.arange(len(order))
    colours = [C_DBH if c == "dbh_rule" else
               C_OK if c == "ba_07_labelled" else C_BAD for c in order]

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.2))
    ax = tidy(axes[0])
    ax.bar(x, d.loc[order, "gate_rho"], 0.58, color=colours, zorder=3)
    ax.axhline(0, color="#333333", lw=1.1, zorder=5)
    for xi, v, n in zip(x, d.loc[order, "gate_rho"], d.loc[order, "sites"]):
        ax.annotate("%.3f\nn = %d" % (v, n), (xi, v),
                    xytext=(0, 5 if v >= 0 else -24),
                    textcoords="offset points", ha="center", fontsize=8.6,
                    color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL.get(c, c) for c in order], fontsize=8.4)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("a) The present-day gate", loc="left")

    ax = tidy(axes[1])
    w = 0.38
    ax.bar(x - w / 2, d.loc[order, "rho"], w, color=colours, zorder=3,
           label="the eight future runs")
    ax.bar(x + w / 2, d.loc[order, "null_nvis_rho"], w, color=C_NULL, zorder=3,
           label="their NVIS-constrained null")
    ax.axhline(0, color="#333333", lw=1.1, zorder=5)
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL.get(c, c) for c in order], fontsize=8.4)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("b) The future runs against their own null", loc="left")
    ax.legend(fontsize=8.5, frameon=False)
    fig.suptitle("The criterion works on the sites it was calibrated on; the "
                 "sample it unlocks does not", x=0.06, ha="left", fontsize=12)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_criterion_vs_expansion.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_expansion():
    ref = pd.read_csv(stv_dir() / "outputs" / "reference_table.csv",
                      low_memory=False)
    sel = ref[ref["live_ba"] >= 7]
    lab = sel[sel["max_dbh"].notna()]
    unl = sel[sel["max_dbh"].isna()]

    rows = []
    for name, d in (("labelled\n(has stem data)", lab),
                    ("unlabelled\n(added by the rule)", unl)):
        rows.append(dict(group=name, n=len(d),
                         rho=stats.spearmanr(d["agb"], d["M_hist"]).correlation,
                         area=d["area_ha"].median(),
                         per_ba=d["agb_per_ba"].median()))
    g = pd.DataFrame(rows)

    prov = unl.groupby("source").agg(
        n=("agb", "size"), area=("area_ha", "median"),
        per_ba=("agb_per_ba", "median")).reset_index()
    prov["rho"] = [stats.spearmanr(unl[unl["source"] == s]["agb"],
                                   unl[unl["source"] == s]["M_hist"]).correlation
                   if (unl["source"] == s).sum() >= 20 else np.nan
                   for s in prov["source"]]
    prov = prov.sort_values("n", ascending=False).head(5)

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0))
    ax = tidy(axes[0])
    ax.bar([0, 1], g["rho"], 0.5, color=[C_OK, C_BAD], zorder=3)
    ax.axhline(0, color="#333333", lw=1.1, zorder=5)
    for xi, r in g.iterrows():
        ax.annotate("%+.3f\nn = %d" % (r["rho"], r["n"]), (xi, r["rho"]),
                    xytext=(0, 5 if r["rho"] >= 0 else -24),
                    textcoords="offset points", ha="center", fontsize=9.5,
                    color=INK_2)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(g["group"], fontsize=9)
    ax.set_ylabel("Spearman of observed biomass with M'", fontsize=9)
    ax.set_title("a) The two halves of the expanded sample", loc="left")

    ax = tidy(axes[1])
    y = np.arange(len(prov))[::-1]
    ax.barh(y, prov["rho"].fillna(0), 0.55, color=C_BAD, zorder=3)
    ax.axvline(0, color="#333333", lw=1.1, zorder=5)
    for yi, r in zip(y, prov.itertuples()):
        ax.text(0.004 if (r.rho or 0) >= 0 else -0.004, yi,
                "%+.2f   n=%d, plots %.2f ha, AGB/BA %.1f"
                % (r.rho if np.isfinite(r.rho) else 0, r.n, r.area, r.per_ba),
                va="center", ha="left" if (r.rho or 0) >= 0 else "right",
                fontsize=8.2, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels([s[:34] for s in prov["source"]], fontsize=8.4)
    ax.set_xlabel("Spearman of observed biomass with M'")
    ax.set_title("b) Who the unlabelled sites come from", loc="left")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 0.05, hi + 0.30)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_what_the_expansion_adds.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    prov.to_csv(OUT_DIR / "expansion_providers.csv", index=False)
    g.to_csv(OUT_DIR / "expansion_halves.csv", index=False)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(OUT_DIR / "run04_headline.csv")
    for p in (fig_decisive(h), fig_expansion()):
        print("  -> %s" % p.name)
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
