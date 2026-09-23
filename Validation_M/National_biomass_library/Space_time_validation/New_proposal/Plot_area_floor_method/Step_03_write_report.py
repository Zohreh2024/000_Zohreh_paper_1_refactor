"""
Run 2 - the report.

Builds Plot_area_floor_report.docx from the tables and figures Steps 1-2 wrote.
Nothing is recomputed.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_03_write_report.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"
REPORT = HERE / "Plot_area_floor_report.docx"
INK_2 = RGBColor(0x52, 0x51, 0x4E)

FLOORS = ["area_010", "area_020", "area_025", "area_030", "area_040",
          "area_050"]


def fmt(v, spec="%.3f"):
    try:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "n/a"
        return spec % v
    except (TypeError, ValueError):
        return str(v)


def caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.italic = True
    r.font.color.rgb = INK_2


def figure(doc, name, cap, width=6.4):
    path = PLOT_DIR / name
    if not path.exists():
        return False
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, cap)
    return True


def table(doc, rows, header, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for c, h in zip(t.rows[0].cells, header):
        c.text = str(h)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = str(v)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    if widths:
        for row in t.rows:
            for c, w in zip(row.cells, widths):
                c.width = Inches(w)
    doc.add_paragraph()
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    d = pd.read_csv(OUT_DIR / "area_floor_comparison.csv").set_index("config")
    best = d.loc[d["gap_rho_nvis"].idxmax()]
    best_id = d["gap_rho_nvis"].idxmax()
    r0, r1 = d.loc["mature_nofloor"], d.loc["verified_nofloor"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Run 2 - a plot-area floor instead of the maturity filter",
                    0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal/Plot_area_floor_method · "
                  "generated %s · six floors, against Run 0 and Run 1"
                  % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("Why this run follows from Run 1", level=1)
    doc.add_paragraph(
        "Run 1 removed the likely-mature half and the result improved. But the "
        "diagnostic that motivated it found the mechanism, and the mechanism "
        "was not maturity. The two classes carried almost the same observed "
        "biomass - 117.5 against 109.8 Mg/ha - while the likely-mature group "
        "reported 17.4 Mg of biomass per square metre per hectare of its own "
        "live basal area against 7.3, from plots 40 per cent smaller. A "
        "per-hectare figure from a smaller plot is the same few trees divided "
        "by less ground. That group is not less mature; it is more inflated.")
    doc.add_paragraph(
        "If that is right, the maturity threshold is a proxy and filtering on "
        "the thing itself should do better. It should also be cheaper: the "
        "maturity filter discards every site with no stem data at all - 1,088 "
        "of 1,688 - whether or not those sites are well measured. A plot-area "
        "floor keeps them.", style="Intense Quote")
    doc.add_paragraph(
        "Everything else is held at Run 0: NVIS-constrained matching, Eq. (1) "
        "of the window-mean FPI, all 174 predictors, PCA to 95 per cent of the "
        "historical variance, the 99th percentile no-analogue cutoff. Both "
        "nulls are computed in every configuration and every metric comes from "
        "the analogue-found stratum, as in every run of this study.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The floor does remove the inflation", level=1)
    rows = []
    for cfg in FLOORS:
        if cfg not in d.index:
            continue
        x = d.loc[cfg]
        rows.append([fmt(x["min_area_ha"], "%.2f") + " ha", int(x["n_sites"]),
                     fmt(x["median_plot_ha"], "%.2f"),
                     fmt(x["median_agb_per_ba"], "%.1f")])
    table(doc, [["none (Run 0, mature)", int(r0["n_sites"]),
                 fmt(r0["median_plot_ha"], "%.2f"),
                 fmt(r0["median_agb_per_ba"], "%.1f")]] + rows,
          ["floor", "sites", "median plot (ha)",
           "median AGB per m2/ha basal area"],
          widths=[1.6, 0.8, 1.3, 2.0])
    caption(doc, "Table 1. What each floor does to the sample.")
    doc.add_paragraph(
        "Biomass per unit basal area falls monotonically as the floor rises, "
        "from %s with no floor to %s at 0.50 ha. That is the inflation being "
        "removed, and it is removed directly rather than through a proxy. Note "
        "the sample sizes: at 0.25 ha the sample is LARGER than Run 0's 600 "
        "and carries half the inflation, because the floor keeps the "
        "unverified sites the maturity filter discards."
        % (fmt(r0["median_agb_per_ba"], "%.1f"),
           fmt(d.loc["area_050", "median_agb_per_ba"], "%.1f")
           if "area_050" in d.index else "n/a"))

    # ------------------------------------------------------------------ #
    doc.add_heading("The ratio rises past 1 - and so does its null", level=1)
    doc.add_paragraph(
        "Raising the floor does two things at once. It removes the inflation, "
        "which is the point. But it also lowers the observed biomass of "
        "whatever survives, because larger plots report less biomass per "
        "hectare. So any ratio of M' to observed biomass rises as the floor "
        "rises, for every M' INCLUDING a randomly chosen one.", style="Intense Quote")
    rows = []
    for cfg in ["mature_nofloor", "verified_nofloor"] + FLOORS:
        if cfg not in d.index:
            continue
        x = d.loc[cfg]
        rows.append([cfg, int(x["n_sites"]), fmt(x["ratio"]),
                     fmt(x["null_nvis_ratio"]),
                     fmt(x["ratio"] - x["null_nvis_ratio"], "%+.3f")])
    table(doc, rows,
          ["configuration", "sites", "median ratio",
           "its NVIS-constrained null", "difference"],
          widths=[1.5, 0.7, 1.1, 1.6, 0.9])
    caption(doc, "Table 2. The ratio against the null that moved with it.")
    doc.add_paragraph(
        "The headline is striking: M'/AGB rises from %s under Run 0 to %s at "
        "the 0.40 ha floor, which puts M' ABOVE observed biomass - the "
        "direction a maximum should err in, and the opposite of the "
        "under-prediction the published gate reports. The failure of the "
        "present-day gate is largely an artefact of small plots, not a "
        "property of M'."
        % (fmt(r0["ratio"]), fmt(d.loc["area_040", "ratio"])
           if "area_040" in d.index else "n/a"))
    doc.add_paragraph(
        "But the null does the same thing, from %s to %s, so the ratio alone "
        "proves nothing. This is exactly why both nulls are carried through "
        "every run of this study."
        % (fmt(r0["null_nvis_ratio"]),
           fmt(d.loc["area_040", "null_nvis_ratio"])
           if "area_040" in d.index else "n/a"))
    figure(doc, "fig_01_ratio_and_rho.png",
           "Figure 1. The sweep, with both nulls drawn in and Run 0, Run 1 and "
           "the combined filter as horizontal references.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The gap to the null is where the answer is", level=1)
    doc.add_paragraph(
        "Subtracting each configuration's own null leaves what the matching "
        "actually contributes. On that axis the floor beats the maturity "
        "filter, and it does so while keeping far more sites.")
    rows = []
    for cfg in ["mature_nofloor", "verified_nofloor"] + FLOORS + \
               ["area_025_mature"]:
        if cfg not in d.index:
            continue
        x = d.loc[cfg]
        rows.append([cfg, int(x["n_sites"]), fmt(x["rho"]),
                     fmt(x["null_nvis_rho"]), fmt(x["gap_rho_nvis"], "%+.3f"),
                     fmt(x["gap_rho_free"], "%+.3f"),
                     fmt(x["pct_no_analogue"], "%.1f") + "%"])
    table(doc, rows,
          ["configuration", "sites", "rho", "null rho",
           "gap vs constrained null", "gap vs unconstrained null",
           "no-analogue"],
          widths=[1.4, 0.6, 0.7, 0.8, 1.3, 1.4, 0.9])
    caption(doc, "Table 3. Both gaps, every configuration.")
    doc.add_paragraph(
        "The best configuration is %s: %d sites, a gap of %s to the "
        "constrained null against Run 0's %s and Run 1's %s. It retains %.0f "
        "per cent more sites than Run 1 and returns a gap half again as large."
        % (best_id, int(best["n_sites"]), fmt(best["gap_rho_nvis"], "%+.3f"),
           fmt(r0["gap_rho_nvis"], "%+.3f"), fmt(r1["gap_rho_nvis"], "%+.3f"),
           100 * (best["n_sites"] / r1["n_sites"] - 1)))
    figure(doc, "fig_02_gap_to_null.png",
           "Figure 2. Skill above the constrained null - the only axis the "
           "area floor does not inflate. The dashed line is Run 0.")
    doc.add_paragraph(
        "Two results in that figure deserve comment rather than celebration. "
        "The sweep is not monotone: the 0.20 ha floor falls BELOW its own null "
        "at %s while 0.10 and 0.25 sit above it. With a few hundred sites and "
        "a rank correlation this small, differences of 0.03 to 0.05 are within "
        "what the sample can resolve, so the useful reading is the block from "
        "0.30 ha upward, where the gap is consistently 0.107 to 0.128, rather "
        "than any single floor."
        % fmt(d.loc["area_020", "gap_rho_nvis"], "%+.3f")
        if "area_020" in d.index else "")
    doc.add_paragraph(
        "And applying BOTH filters together is worse than either alone: 0.25 "
        "ha plus the maturity filter leaves 298 sites and a gap of %s, below "
        "zero. The two are redundant, not complementary - they remove the same "
        "records - and stacking them removes the variation the matching needs "
        "in order to have anything to rank."
        % (fmt(d.loc["area_025_mature", "gap_rho_nvis"], "%+.3f")
           if "area_025_mature" in d.index else "n/a"))
    figure(doc, "fig_03_tradeoff.png",
           "Figure 3. What each filter costs in sites and returns in skill.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude", level=1)
    for t in [
        "Run 1's hypothesis was right about the effect and wrong about the "
        "cause. The likely-mature half was dragging the numbers down, but "
        "because those plots are small, not because those stands are immature.",
        "A plot-area floor is the better filter. At %s it keeps %d sites "
        "against Run 1's %d - %.0f per cent more - and returns a gap to the "
        "constrained null of %s against Run 1's %s."
        % (best_id.replace("area_0", "0.") + " ha", int(best["n_sites"]),
           int(r1["n_sites"]), 100 * (best["n_sites"] / r1["n_sites"] - 1),
           fmt(best["gap_rho_nvis"], "%+.3f"),
           fmt(r1["gap_rho_nvis"], "%+.3f")),
        "The present-day gate failure is largely an artefact. With a 0.40 ha "
        "floor M'/AGB is %s rather than %s - M' sits above observed biomass, "
        "which is what a maximum should do. That is a statement about the "
        "library's plot sizes, not a vindication of M', because the null moves "
        "the same way; but the published under-prediction should not be quoted "
        "without it."
        % (fmt(d.loc["area_040", "ratio"]) if "area_040" in d.index else "n/a",
           fmt(r0["ratio"])),
        "Do not stack the two filters. Together they leave 298 sites and no "
        "skill above the null at all.",
        "Choose the floor from the 0.30-0.50 ha block, not from a single "
        "value. The sweep is not monotone below 0.30 ha and the differences "
        "there are within what a few hundred sites can resolve.",
        "This remains a one-change test against Run 0 and inherits its limits: "
        "the late-century high-forcing windows are extrapolation under every "
        "configuration, and no floor repairs that.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_run_area_floors.py", "the nine configurations"],
        ["Step_02_compare.py", "the comparison and the figures"],
        ["Step_03_write_report.py", "this document"],
        ["outputs/config_matrix.csv", "what each configuration is"],
        ["outputs/area_floor_summary.csv", "one row per configuration per run"],
        ["outputs/area_floor_comparison.csv", "Tables 1-3"],
        ["outputs/<config>/matches.csv", "site-level matches"],
        ["plots/fig_01..03", "the figures in this report"],
    ], ["file", "what it holds"], widths=[2.3, 3.7])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
