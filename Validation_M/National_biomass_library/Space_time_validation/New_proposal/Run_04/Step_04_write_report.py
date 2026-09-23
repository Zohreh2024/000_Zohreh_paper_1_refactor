"""
Run 4, step 4 - the report.

Builds Run_04_report.docx from the tables and figures Steps 1-3 wrote.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_04_write_report.py
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
REPORT = HERE / "Run_04_report.docx"
INK_2 = RGBColor(0x52, 0x51, 0x4E)


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

    cal = pd.read_csv(OUT_DIR / "calibration.csv")
    cls = pd.read_csv(OUT_DIR / "class_summary.csv")
    h = pd.read_csv(OUT_DIR / "run04_headline.csv").set_index("config")
    halves = pd.read_csv(OUT_DIR / "expansion_halves.csv")
    prov = pd.read_csv(OUT_DIR / "expansion_providers.csv")
    auc = float(cal["auc"].iloc[0])

    dbh = h.loc["dbh_rule"]
    lab = h.loc["ba_07_labelled"]
    exp = h.loc["ba_07"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Run 4 - a maturity rule on basal area instead of stem "
                    "diameter", 0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal/Run_04 · generated %s · "
                  "the most expensive and most debatable of the runs, left last"
                  % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("The problem", level=1)
    doc.add_paragraph(
        "Maturity is assigned from the tree list: a stem of 50 cm or more is "
        "verified mature, a largest stem of 30-50 cm is likely mature, below "
        "that is young or shrubby. That rule needs stem records, and only "
        "2,047 of the library's 15,904 site visits have any. The four largest "
        "sources have none at all - Forestry Corporation NSW with 6,718 "
        "visits, Queensland NFPP with 3,158, Forestry Tasmania with 2,201 and "
        "Parks and Wildlife WA with 898, every one of them at zero per cent "
        "coverage. So the rule caps the reference sample at 600 sites of the "
        "1,688 that survive every other filter.")
    doc.add_paragraph(
        "Live basal area is reported in the SITE table for almost every visit. "
        "A rule on it could reach the other 1,088. The question is what that "
        "costs.")

    doc.add_heading("Calibrating it", level=1)
    rows = [[r["maturity"], int(r["sites"]), fmt(r["ba_median"], "%.2f"),
             "%s to %s" % (fmt(r["ba_p25"], "%.1f"), fmt(r["ba_p75"], "%.1f")),
             fmt(r["agb_median"], "%.1f")] for _, r in cls.iterrows()]
    table(doc, rows, ["class", "sites", "median basal area (m2/ha)",
                      "interquartile range", "median AGB"],
          widths=[1.3, 0.7, 1.5, 1.3, 1.0])
    caption(doc, "Table 1. Basal area by maturity class.")
    doc.add_paragraph(
        "The class medians separate about as the proposal expected - 14.75 "
        "m2/ha for verified mature, 6.75 for likely and 2.99 for young. "
        "Calibrated on the 756 reference sites that carry a DBH label, basal "
        "area reproduces the mature/not-mature distinction at an area under "
        "the ROC curve of %s. That is better than it had any right to be: 0.5 "
        "is a coin toss and 0.8 is usually called decent." % fmt(auc, "%.3f"))
    doc.add_paragraph(
        "It should not be better, because the two quantities measure different "
        "things. Maturity is defined by the LARGEST STEM; basal area is the "
        "summed cross-section of ALL stems over the plot area. A sparse stand "
        "of huge old trees and a dense thicket of saplings can carry the same "
        "basal area, so the rule cannot separate an old stand from a crowded "
        "young one. The AUC of 0.80 says the confusion is less damaging than "
        "it might have been, not that it is absent.")
    rows = [[fmt(r["threshold"], "%.0f"), fmt(r["sensitivity"], "%.2f"),
             fmt(r["specificity"], "%.2f"),
             fmt(r["balanced_accuracy"], "%.3f"),
             int(r["sites_selected_all"])] for _, r in cal.iterrows()]
    table(doc, rows, ["threshold (m2/ha)", "sensitivity", "specificity",
                      "balanced accuracy", "sites selected of 1,688"],
          widths=[1.2, 1.0, 1.0, 1.2, 1.5])
    caption(doc, "Table 2. The trade-off at each threshold.")
    doc.add_paragraph(
        "One number in Table 1 should have been a warning. The 932 unverified "
        "sites - the ones with no stem record, which the rule exists to reach "
        "- have a median basal area of 15.72 m2/ha, ABOVE the verified mature "
        "group's 14.75. Either they really are mature, or basal area is not "
        "discriminating maturity among them. The labelled data cannot settle "
        "which, because the label those sites would be judged on is exactly "
        "what they lack.", style="Intense Quote")
    figure(doc, "fig_01_calibration.png",
           "Figure 1. What the rule has to separate, how well it does it, and "
           "the trade-off at each threshold.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The result", level=1)
    doc.add_paragraph(
        "The design separates the two things the rule does - change the "
        "criterion, and expand the sample - by running the criterion on the "
        "labelled sites alone as well as on everything.")
    rows = []
    for cfg in h.index:
        x = h.loc[cfg]
        rows.append([cfg, int(x["sites"]), int(x["labelled"]),
                     fmt(x["pct_dbh_mature"], "%.0f") + "%",
                     fmt(x["gate_rho"]), fmt(x["ratio"]), fmt(x["rho"]),
                     fmt(x["null_nvis_rho"]),
                     fmt(x["gap_rho_nvis"], "%+.3f")])
    table(doc, rows,
          ["configuration", "sites", "labelled", "of which DBH-mature",
           "gate rho", "ratio", "future rho", "null rho", "gap"],
          widths=[1.3, 0.6, 0.7, 1.1, 0.8, 0.7, 0.8, 0.7, 0.7])
    caption(doc, "Table 3. Every configuration, analogue-found sites only.")
    doc.add_paragraph(
        "The criterion is fine. Applied to the labelled sites alone it gives a "
        "present-day gate of %s and a future rank correlation of %s, against "
        "%s and %s for the DBH rule - slightly lower, on 461 sites instead of "
        "600, which is what a weaker criterion should look like."
        % (fmt(lab["gate_rho"]), fmt(lab["rho"]), fmt(dbh["gate_rho"]),
           fmt(dbh["rho"])))
    doc.add_paragraph(
        "The expansion destroys it. Adding the 779 sites with no stem record "
        "takes the gate from %s to %s and the future runs from %s to %s - both "
        "below zero. Every threshold behaves the same way: 5, 9 and 14 m2/ha "
        "all land between -0.04 and -0.08. This is not a dilution, it is a "
        "reversal."
        % (fmt(lab["gate_rho"]), fmt(exp["gate_rho"]), fmt(lab["rho"]),
           fmt(exp["rho"])), style="Intense Quote")
    figure(doc, "fig_02_criterion_vs_expansion.png",
           "Figure 2. The criterion works on the sites it was calibrated on; "
           "the sample it unlocks does not.")

    doc.add_heading("Why", level=2)
    rows = [[r["group"].replace("\n", " "), int(r["n"]),
             fmt(r["rho"], "%+.3f"), fmt(r["area"], "%.2f"),
             fmt(r["per_ba"], "%.1f")] for _, r in halves.iterrows()]
    table(doc, rows, ["half of the expanded sample", "sites",
                      "rho of observed AGB with M'", "median plot (ha)",
                      "AGB per m2/ha BA"], widths=[1.9, 0.7, 1.5, 1.1, 1.1])
    caption(doc, "Table 4. The two halves.")
    doc.add_paragraph(
        "The 461 labelled sites give a rank correlation with M' of %s. The 779 "
        "the rule adds give %s. They do not merely carry less signal - they "
        "carry the opposite sign, which is why the pooled result falls below "
        "zero rather than towards it."
        % (fmt(halves.iloc[0]["rho"], "%+.3f"),
           fmt(halves.iloc[1]["rho"], "%+.3f")))
    rows = [[r["source"][:36], int(r["n"]), fmt(r["rho"], "%+.2f"),
             fmt(r["area"], "%.2f"), fmt(r["per_ba"], "%.1f")]
            for _, r in prov.iterrows()]
    table(doc, rows, ["provider", "sites added", "rho with M'",
                      "median plot (ha)", "AGB per m2/ha BA"],
          widths=[2.2, 0.9, 1.0, 1.1, 1.1])
    caption(doc, "Table 5. Who the unlabelled sites come from.")
    doc.add_paragraph(
        "All three are providers this repository has already flagged. Parks "
        "and Wildlife WA and Queensland NFPP both return a negative "
        "correlation with M'; the Roxburgh folder found the same for "
        "Queensland NFPP on its 1,647 records at uniform 0.4 ha plots. Darwin "
        "Centre for Bushfire Research reports 601 Mg/ha of biomass on 0.08 ha "
        "plots, an AGB-to-basal-area ratio of 44.6 - savanna measured on "
        "eighth-hectare plots, which is the small-plot inflation the whole "
        "study keeps returning to.")
    figure(doc, "fig_03_what_the_expansion_adds.png",
           "Figure 3. The two halves of the expanded sample, and the providers "
           "the unlabelled half comes from.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude", level=1)
    for t in [
        "The rule is sound and the sample is not. Basal area reproduces the "
        "DBH label at AUC %s and performs comparably on the sites where both "
        "exist. The problem is entirely in what it unlocks."
        % fmt(auc, "%.2f"),
        "Do not adopt it. On every threshold tested the expanded sample gives "
        "a present-day gate at or below zero, against %s for the DBH rule. "
        "Nearly doubling the sample is worth nothing if the added half "
        "correlates negatively with what is being validated."
        % fmt(dbh["gate_rho"]),
        "The 1,088 sites without stem records are not simply unmeasured, they "
        "are differently measured. They come from providers whose plot sizes "
        "and biomass values this study has repeatedly found unusable, and no "
        "maturity rule can repair that - the defect is in the biomass, not in "
        "the maturity.",
        "The stem-record requirement is doing more than it appears to. It "
        "looks like a maturity filter and is also, incidentally, a "
        "data-quality filter: the providers that record stems are the "
        "providers whose biomass behaves. That is worth stating explicitly "
        "wherever the 600-site cap is described as a limitation.",
        "If the sample must grow, grow it on measurement quality rather than "
        "on maturity. Run 3 showed that rebuilding biomass from stem diameters "
        "lifts the gate from 0.42 to 0.73 - but it needs stem records, so it "
        "reaches the same 600 sites. Reaching further requires providers to "
        "supply stem data, not a different rule applied to what they did "
        "supply.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_calibrate_rule.py", "the calibration and its skill"],
        ["Step_02_run_and_compare.py", "the six configurations"],
        ["Step_03_plots.py", "figures 2 and 3"],
        ["Step_04_write_report.py", "this document"],
        ["outputs/calibration.csv", "Table 2"],
        ["outputs/class_summary.csv", "Table 1"],
        ["outputs/run04_headline.csv", "Table 3"],
        ["outputs/expansion_halves.csv", "Table 4"],
        ["outputs/expansion_providers.csv", "Table 5"],
    ], ["file", "what it holds"], widths=[2.3, 3.7])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
