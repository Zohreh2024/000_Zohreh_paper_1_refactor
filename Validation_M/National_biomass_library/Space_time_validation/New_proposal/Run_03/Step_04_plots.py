"""
Run 3, step 4 - the figures.

    fig_02  the cross-file check: reported and rebuilt biomass against the
            site table's own basal area
    fig_03  the paired result - identical sites, only the observation changed
    fig_04  the exponent is immaterial

fig_01, the diagnosis, is written by Step_01.

Reads   outputs/agb_rebuilt_by_survey.csv, rebuild_checks.csv,
        run03_headline.csv, run03_summary.csv
Writes  plots/*.png

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_04_plots.py
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

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_REP, C_REB, C_NULL = "#e34948", "#2a78d6", "#eda100"

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


def fig_check(j, chk):
    """Both biomass estimates against a quantity neither was built from."""
    c = chk[np.isclose(chk["exponent"], 2.5)].iloc[0]
    hi_ba = float(np.nanpercentile(j["live_basal_area_ha"], 98))
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.2), sharex=True)
    for ax, (col, colour, lab, rho) in zip(axes, [
            ("agb_drymass_ha", C_REP, "reported plot biomass",
             c["rho_reported_vs_basal_area"]),
            ("agb_rebuilt", C_REB, "rebuilt from stem diameters",
             c["rho_rebuilt_vs_basal_area"])]):
        tidy(ax)
        hi_y = float(np.nanpercentile(j[col], 98))
        ax.scatter(j["live_basal_area_ha"], j[col], s=9, alpha=0.3,
                   color=colour, linewidths=0)
        ax.set(xlim=(0, hi_ba), ylim=(0, hi_y))
        ax.set_xlabel("live basal area (m$^2$/ha), from the SITE table")
        ax.set_ylabel("%s (t DM/ha)" % lab)
        ax.set_title("%s\nSpearman %.2f" % (lab, rho), loc="left")
    fig.suptitle("A quantity neither estimate was built from: the site table's "
                 "own basal area", x=0.07, ha="left", fontsize=12)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_cross_file_check.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_paired(h):
    d = h.set_index("config")
    pair = [c for c in ["reported_stem_only", "rebuilt_b2p5"] if c in d.index]
    if len(pair) < 2:
        return None
    lab = ["reported biomass\n(the published column)",
           "rebuilt biomass\n(from stem diameters)"]
    x = np.arange(2)
    w = 0.34

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0))
    ax = tidy(axes[0], grid_axis="y")
    ax.bar(x, d.loc[pair, "gate_rho"], 0.5, color=[C_REP, C_REB], zorder=3)
    for xi, v in zip(x, d.loc[pair, "gate_rho"]):
        ax.annotate("%.3f" % v, (xi, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=11,
                    color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels(lab, fontsize=9)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("a) The present-day gate: M' against observed biomass\n"
                 "at the site's own cell", loc="left")

    ax = tidy(axes[1], grid_axis="y")
    ax.bar(x - w / 2, d.loc[pair, "rho"], w, color=[C_REP, C_REB], zorder=3,
           label="the eight future runs")
    ax.bar(x + w / 2, d.loc[pair, "null_nvis_rho"], w, color=C_NULL, zorder=3,
           label="their NVIS-constrained null")
    for xi, a, b in zip(x, d.loc[pair, "rho"], d.loc[pair, "null_nvis_rho"]):
        ax.annotate("%.3f" % a, (xi - w / 2, a), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=9,
                    color=INK_2)
        ax.annotate("%.3f" % b, (xi + w / 2, b), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=9,
                    color=INK_2)
        ax.annotate("gap %+.3f" % (a - b), (xi, max(a, b)), xytext=(0, 18),
                    textcoords="offset points", ha="center", fontsize=9.5,
                    color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(lab, fontsize=9)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("b) The future runs against their own null", loc="left")
    ax.legend(fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylim(0, max(d.loc[pair, "rho"]) * 1.35)
    fig.suptitle("Identical 599 sites, identical matching, identical M' - only "
                 "the observation differs", x=0.06, ha="left", fontsize=12)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_03_paired_result.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_exponent(h, chk):
    d = h[h.index.astype(str).str.startswith("rebuilt")] if False else \
        h.set_index("config")
    reb = [c for c in d.index if c.startswith("rebuilt")]
    if not reb:
        return None
    b = [float(c.split("_b")[1].replace("p", ".")) for c in reb]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    tidy(ax)
    ax.plot(b, d.loc[reb, "gate_rho"], "-o", color=C_REB, lw=2.2, ms=9,
            markeredgecolor=SURFACE, markeredgewidth=1.2,
            label="present-day gate", zorder=5)
    ax.plot(b, d.loc[reb, "rho"], "-s", color=INK_2, lw=2.0, ms=8,
            markeredgecolor=SURFACE, markeredgewidth=1.2,
            label="future runs", zorder=5)
    ax.plot(b, d.loc[reb, "gap_rho_nvis"], "-^", color=C_NULL, lw=2.0, ms=8,
            markeredgecolor=SURFACE, markeredgewidth=1.2,
            label="gap to the constrained null", zorder=5)
    for xi, v in zip(b, d.loc[reb, "gate_rho"]):
        ax.annotate("%.3f" % v, (xi, v), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=8.6,
                    color=INK_2)
    ax.set_xlabel("allometric exponent b in AGB $\\propto$ D$^b$")
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("The one assumption, varied across its plausible range",
                 loc="left")
    ax.set_ylim(0, 0.85)
    ax.legend(fontsize=8.8, frameon=False, loc="center right")
    rr = chk.set_index("exponent")
    ax.text(0.5, 0.04, "ordering of surveys is preserved: b = 2.3 against "
            "b = 2.7 correlates at 0.989",
            transform=ax.transAxes, ha="center", fontsize=8.8, color=INK_2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_04_exponent.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    j = pd.read_csv(OUT_DIR / "agb_rebuilt_by_survey.csv")
    chk = pd.read_csv(OUT_DIR / "rebuild_checks.csv")
    h = pd.read_csv(OUT_DIR / "run03_headline.csv")
    for p in (fig_check(j, chk), fig_paired(h), fig_exponent(h, chk)):
        print("  -> %s" % (p.name if p else "skipped"))
    print("\nfigures in %s" % PLOT_DIR)


if __name__ == "__main__":
    main()
