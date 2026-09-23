"""
Run 5, step 2 - the figures and the report.

    fig_01  the ceiling on both bases, against Run 0 and against the rebuild
    fig_02  where each ceiling sits, and what it removes

Reads   outputs/run05_headline.csv, ceiling_calibration.csv,
        removed_by_ceiling.csv, ../../outputs/reference_table.csv
Writes  plots/*.png, Run_05_report.docx

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_02_plots_and_report.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from docx import Document                                      # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH                  # noqa: E402
from docx.shared import Inches, Pt, RGBColor                   # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"
REPORT = HERE / "Run_05_report.docx"
INK_2 = RGBColor(0x52, 0x51, 0x4E)
MATURE = ["verified mature", "likely mature"]

SURFACE, INK, INK2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_REP, C_REB, C_NULL, C_GAP = "#6b6a66", "#2a78d6", "#eda100", "#1baf7a"

LABEL = {"run0": "Run 0", "ceiling_p99": "+ p99\n(88.3)",
         "ceiling_p95": "+ p95\n(52.0)", "ceiling_p90": "+ p90\n(37.3)",
         "rebuilt": "Run 3\nrebuilt", "rebuilt_ceiling_p95": "rebuilt\n+ p95"}
REPORTED = ["run0", "ceiling_p99", "ceiling_p95", "ceiling_p90"]
REBUILT = ["rebuilt", "rebuilt_ceiling_p95"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="y"):
    ax.tick_params(labelsize=9, colors=INK2, length=2.5, width=0.6)
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


def fmt(v, spec="%.3f"):
    try:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "n/a"
        return spec % v
    except (TypeError, ValueError):
        return str(v)


def fig_result(h):
    d = h.set_index("config")
    order = [c for c in REPORTED + REBUILT if c in d.index]
    x = np.arange(len(order))
    colours = [C_REP if c in REPORTED else C_REB for c in order]
    w = 0.38

    fig, axes = plt.subplots(2, 1, figsize=(10.2, 8.2), sharex=True)
    ax = tidy(axes[0])
    ax.bar(x, d.loc[order, "gate_rho"], 0.56, color=colours, zorder=3)
    ax.axhline(float(d.loc["run0", "gate_rho"]), color=C_REP, lw=1.2, ls="--",
               zorder=4)
    if "rebuilt" in d.index:
        ax.axhline(float(d.loc["rebuilt", "gate_rho"]), color=C_REB, lw=1.2,
                   ls="--", zorder=4)
    for xi, v, n in zip(x, d.loc[order, "gate_rho"], d.loc[order, "sites"]):
        ax.annotate("%.3f\nn = %d" % (v, n), (xi, v), xytext=(0, 5),
                    textcoords="offset points", ha="center", fontsize=8.8,
                    color=INK2)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("a) The present-day gate", loc="left")
    ax.set_ylim(0, 0.95)

    ax = tidy(axes[1])
    ax.bar(x - w / 2, d.loc[order, "rho"], w, color=colours, zorder=3,
           label="the eight future runs")
    ax.bar(x + w / 2, d.loc[order, "null_nvis_rho"], w, color=C_NULL, zorder=3,
           label="their NVIS-constrained null")
    for xi, a, b in zip(x, d.loc[order, "rho"], d.loc[order, "null_nvis_rho"]):
        ax.annotate("gap %+.3f" % (a - b), (xi, max(a, b)), xytext=(0, 16),
                    textcoords="offset points", ha="center", fontsize=9,
                    color=INK)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("b) The future runs against their own null", loc="left")
    ax.legend(fontsize=8.6, frameon=False)
    ax.set_ylim(0, 0.55)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([LABEL.get(c, c) for c in order], fontsize=8.8)
    axes[-1].text(0.995, -0.17, "grey: on reported biomass    blue: on Run 3's "
                  "rebuild    dashed: each base without a ceiling",
                  transform=axes[-1].transAxes, ha="right", fontsize=8,
                  color=INK2)
    fig.tight_layout()
    dst = PLOT_DIR / "fig_01_ceiling_result.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_where(cal, removed):
    ref = pd.read_csv(stv_dir() / "outputs" / "reference_table.csv",
                      low_memory=False)
    mat = ref[ref["maturity"].isin(MATURE)]
    c = cal[cal["base"].str.startswith("reported")].iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0))
    ax = tidy(axes[0], grid_axis="y")
    hi = 120
    for cl, colour in (("verified mature", C_REB), ("likely mature", "#7fb3f0")):
        v = mat.loc[mat["maturity"] == cl, "agb_per_ba"].dropna()
        ax.hist(v[v <= hi], bins=45, histtype="step", lw=2.0, color=colour,
                label="%s (%d)" % (cl, len(v)), zorder=4)
    for q, colour in ((90, "#e34948"), (95, "#eb6834"), (99, "#eda100")):
        ax.axvline(float(c["p%d" % q]), color=colour, lw=1.5, ls="--", zorder=5)
        ax.text(float(c["p%d" % q]), ax.get_ylim()[1] * (0.95 - 0.07 * (q - 90) / 9),
                " p%d = %.0f" % (q, c["p%d" % q]), fontsize=8.4, color=colour,
                va="top")
    ax.set_xlabel("reported AGB per m$^2$/ha of live basal area")
    ax.set_ylabel("sites")
    ax.set_title("a) Where each ceiling sits on Run 0's own quantity",
                 loc="left")
    ax.legend(fontsize=8.6, frameon=False, loc="center right")

    ax = tidy(axes[1], grid_axis="x")
    rm = removed[removed["config"] == "ceiling_p90"]
    if len(rm):
        g = rm.groupby("source").agg(n=("agb", "size"),
                                     ratio=("agb_per_ba", "median")).reset_index()
        g = g.sort_values("n", ascending=False).head(7)
        y = np.arange(len(g))[::-1]
        ax.barh(y, g["n"], 0.6, color="#e34948", zorder=3)
        for yi, r in zip(y, g.itertuples()):
            ax.text(r.n + 0.6, yi, "median ratio %.0f" % r.ratio, va="center",
                    fontsize=8.4, color=INK2)
        ax.set_yticks(y)
        ax.set_yticklabels([s[:34] for s in g["source"]], fontsize=8.4)
        ax.set_xlabel("sites removed by the p90 ceiling")
        lo, hi2 = ax.get_xlim()
        ax.set_xlim(0, hi2 * 1.45)
    ax.set_title("b) Who the tightest ceiling removes", loc="left")
    fig.tight_layout()
    dst = PLOT_DIR / "fig_02_where_the_ceiling_sits.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #

def caption(doc, t):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.font.size = Pt(9)
    r.font.italic = True
    r.font.color.rgb = INK_2


def figure(doc, name, cap, width=6.3):
    path = PLOT_DIR / name
    if not path.exists():
        return
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, cap)


def table(doc, rows, header, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for c, h in zip(t.rows[0].cells, header):
        c.text = str(h)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(9)
    for rr in rows:
        cells = t.add_row().cells
        for c, v in zip(cells, rr):
            c.text = str(v)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    if widths:
        for r in t.rows:
            for c, w in zip(r.cells, widths):
                c.width = Inches(w)
    doc.add_paragraph()


def build_report(h, cal, removed):
    d = h.set_index("config")
    r0, p90 = d.loc["run0"], d.loc["ceiling_p90"]
    reb, rebc = d.loc["rebuilt"], d.loc["rebuilt_ceiling_p95"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("Run 5 - the biomass-to-basal-area ceiling, on its own", 0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal/Run_05_ceiling · "
                  "generated %s · the test combined_Run said was missing"
                  % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    doc.add_heading("Why", level=1)
    doc.add_paragraph(
        "combined_Run introduced a ceiling on the ratio of observed biomass to "
        "the stand's own live basal area, and flagged that it had never been "
        "tested against Run 0 in isolation. It was also the ingredient that "
        "did not do what it was asked to do: it was proposed to remove "
        "University of NSW at about 106 and Queensland Herbarium at 35.6, but "
        "those are REPORTED ratios and the rebuild had already repaired them. "
        "This run supplies the missing test.")
    doc.add_paragraph(
        "The ceiling is not circular, which is the first thing to establish. "
        "It is computed from biomass and basal area, both reported in the site "
        "table, and M' appears nowhere in it. It removes records on a "
        "criterion internal to the observation, so any improvement it produces "
        "is not the result of discarding whatever disagrees with M'.",
        style="Intense Quote")

    doc.add_heading("The calibration does not transfer", level=1)
    rows = [[r["base"], int(r["verified_sites"]), fmt(r["median"], "%.2f"),
             fmt(r["p90"], "%.1f"), fmt(r["p95"], "%.1f"),
             fmt(r["p99"], "%.1f")] for _, r in cal.iterrows()]
    table(doc, rows, ["base", "verified sites", "median ratio", "p90", "p95",
                      "p99"], widths=[1.6, 1.0, 1.1, 0.8, 0.8, 0.8])
    caption(doc, "Table 1. The verified-mature group's ratio on each base.")
    doc.add_paragraph(
        "The same percentile of the same group is 52.0 on reported biomass and "
        "27.5 on Run 3's rebuild, because the rebuild changes the whole "
        "distribution. combined_Run's 34.5 is a third value again, from its "
        "own wider base. So the ceiling must be recalibrated wherever it is "
        "applied, and it is the PERCENTILE that is the parameter, not the "
        "number. Applying combined_Run's 34.5 to Run 0 would have been testing "
        "two changes at once.")

    doc.add_heading("The result", level=1)
    rows = []
    for cfg, lab in [("run0", "Run 0 as published"),
                     ("ceiling_p99", "+ ceiling at the verified p99"),
                     ("ceiling_p95", "+ ceiling at the verified p95"),
                     ("ceiling_p90", "+ ceiling at the verified p90"),
                     ("rebuilt", "Run 3's rebuild, no ceiling"),
                     ("rebuilt_ceiling_p95", "rebuild + ceiling at p95")]:
        if cfg not in d.index:
            continue
        x = d.loc[cfg]
        rows.append([lab, int(x["sites"]), fmt(x["ceiling"], "%.1f"),
                     fmt(x["median_agb"], "%.1f"), fmt(x["gate_rho"]),
                     fmt(x["rho"]), fmt(x["null_nvis_rho"]),
                     fmt(x["gap_rho_nvis"], "%+.3f")])
    table(doc, rows, ["configuration", "sites", "ceiling", "median AGB",
                      "gate rho", "future rho", "null rho", "gap"],
          widths=[1.9, 0.6, 0.7, 0.9, 0.8, 0.8, 0.7, 0.7])
    caption(doc, "Table 2. Analogue-found sites only.")
    doc.add_paragraph(
        "The ceiling earns its place on its own. Against Run 0 it raises the "
        "present-day gate from %s to %s and the gap to the constrained null "
        "from %s to %s, and it does so MONOTONICALLY - the tighter the "
        "ceiling, the larger the gain, through p99, p95 and p90. A filter that "
        "improved the result at one arbitrary threshold and not at others "
        "would be suspect; this one behaves like a filter removing a real "
        "contaminant."
        % (fmt(r0["gate_rho"]), fmt(p90["gate_rho"]),
           fmt(r0["gap_rho_nvis"], "%+.3f"), fmt(p90["gap_rho_nvis"], "%+.3f")),
        style="Intense Quote")
    figure(doc, "fig_01_ceiling_result.png",
           "Figure 1. The ceiling on both bases. Dashed lines are each base "
           "without a ceiling.", width=5.9)
    doc.add_paragraph(
        "On the rebuilt base it behaves differently and combined_Run read it "
        "correctly: the gap rises from %s to %s while the gate falls slightly, "
        "%s to %s. The ceiling buys gap rather than gate there, because it "
        "lowers the null more than it lowers the runs. Both bases agree that "
        "it is worth applying; they disagree about which statistic it improves."
        % (fmt(reb["gap_rho_nvis"], "%+.3f"),
           fmt(rebc["gap_rho_nvis"], "%+.3f"), fmt(reb["gate_rho"]),
           fmt(rebc["gate_rho"])))

    doc.add_heading("What it costs, and what it removes", level=1)
    doc.add_paragraph(
        "The tightest ceiling keeps %d of 600 sites and lowers the median "
        "observed biomass from %s to %s Mg/ha. It is removing high-biomass "
        "records, and the question is whether they are real."
        % (int(p90["sites"]), fmt(r0["median_agb"], "%.1f"),
           fmt(p90["median_agb"], "%.1f")))
    rm = removed[removed["config"] == "ceiling_p90"]
    if len(rm):
        g = rm.groupby("source").agg(
            sites=("agb", "size"), ratio=("agb_per_ba", "median"),
            agb=("agb", "median"), area=("area_ha", "median")).reset_index()
        g = g.sort_values("sites", ascending=False)
        table(doc, [[r["source"][:36], int(r["sites"]),
                     fmt(r["ratio"], "%.1f"), fmt(r["agb"], "%.0f"),
                     fmt(r["area"], "%.2f")] for _, r in g.head(8).iterrows()],
              ["provider", "sites removed", "median ratio", "median AGB",
               "median plot (ha)"], widths=[2.2, 1.0, 1.0, 1.0, 1.1])
    doc.add_paragraph(
        "A ratio of 37 Mg of biomass per square metre per hectare of basal "
        "area is already at the edge of what a stand can physically carry, and "
        "the records above it sit at 70 and beyond. They are not high-biomass "
        "stands; they are per-hectare figures that their own basal area does "
        "not support. That is the same inflation every run in this study has "
        "met, reached through a different door.")
    figure(doc, "fig_02_where_the_ceiling_sits.png",
           "Figure 2. Where each ceiling falls on Run 0's own quantity, and "
           "who the tightest one removes.")

    doc.add_heading("What to conclude", level=1)
    for t in [
        "The ceiling is justified on its own and combined_Run's use of it "
        "stands. It improves Run 0 without the rebuild, improves the rebuild "
        "without anything else, and improves monotonically with tightness.",
        "It is not circular. The ratio is computed from two site-table columns "
        "and M' enters nowhere, so it cannot be removing records for "
        "disagreeing with the layer.",
        "Calibrate the percentile, never the value. The same percentile is "
        "52.0 on reported biomass, 27.5 on Run 3's rebuild and 34.5 on "
        "combined_Run's wider base. A number carried between bases is a "
        "different filter.",
        "p90 is the better choice than p95 on reported biomass - gap %s "
        "against %s - but it costs 104 sites, and on the rebuilt base the "
        "difference between percentiles is much smaller because the rebuild "
        "has already removed most of what the ceiling targets."
        % (fmt(p90["gap_rho_nvis"], "%+.3f"),
           fmt(d.loc["ceiling_p95", "gap_rho_nvis"], "%+.3f")),
        "This closes the open item combined_Run listed. The remaining one is "
        "that the stem-mass alignment defect should go back to the library's "
        "custodians.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_run_ceiling.py", "the calibration and the six runs"],
        ["Step_02_plots_and_report.py", "the figures and this document"],
        ["outputs/ceiling_calibration.csv", "Table 1"],
        ["outputs/run05_headline.csv", "Table 2"],
        ["outputs/removed_by_ceiling.csv", "every site each ceiling removes"],
        ["outputs/<config>/matches.csv", "site-level matches, and metrics.csv"],
    ], ["file", "what it holds"], widths=[2.4, 3.6])
    doc.save(str(REPORT))
    return REPORT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(OUT_DIR / "run05_headline.csv")
    cal = pd.read_csv(OUT_DIR / "ceiling_calibration.csv")
    rm = pd.read_csv(OUT_DIR / "removed_by_ceiling.csv")
    for p in (fig_result(h), fig_where(cal, rm)):
        print("  -> %s" % p.name)
    print("wrote %s" % build_report(h, cal, rm))


if __name__ == "__main__":
    main()
