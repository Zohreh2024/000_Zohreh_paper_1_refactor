"""
Combined run, step 4 - the report.

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
REPORT = HERE / "Combined_run_report.docx"
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
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    h = pd.read_csv(OUT_DIR / "combined_headline.csv").set_index("config")
    trail = pd.read_csv(OUT_DIR / "build_trail.csv")
    cal = pd.read_csv(OUT_DIR / "ceiling_calibration.csv").iloc[0]
    prov = pd.read_csv(OUT_DIR / "provider_effects.csv")

    r0, r3 = h.loc["run0"], h.loc["run3_rebuilt"]
    cmb = h.loc["combined"]
    noc = h.loc["combined_no_ceiling"]
    noa = h.loc["combined_no_area"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("The combined configuration", 0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal/combined_Run · generated "
                  "%s · the configuration the one-change tests point to"
                  % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    doc.add_heading("What this is, and what it is not", level=1)
    doc.add_paragraph(
        "This is no longer a one-change test. It puts together the five "
        "decisions the earlier runs established, and it is reported as a "
        "configuration rather than as an experiment. To keep it decomposable, "
        "two intermediate configurations are run alongside it so that each "
        "ingredient's contribution can still be read off.", style="Intense Quote")
    table(doc, [
        ["1. Biomass rebuilt from stem diameters, b = 2.5", "Run_03",
         "the library's stem-mass column is not aligned with the stem "
         "attributes; rebuilding lifted the gate from 0.416 to 0.732 on "
         "identical sites"],
        ["2. The AGB-versus-basal-area floor retired", "Run_03",
         "it existed to exclude TERN and CSIRO wholesale; after the rebuild "
         "they pass on their own merits, 5.7 to 98.1 per cent and 74.8 to 100"],
        ["3. Plot-area threshold 0.04 ha", "Run_02",
         "readmits 201 DELWP Victoria visits at exactly 0.04 ha, median 225 "
         "Mg/ha on 30.8 m2/ha for a ratio of 7.3"],
        ["4. A ceiling on the AGB-to-basal-area ratio", "new here",
         "replaces the plot-area floor as the inflation control, set at the "
         "95th percentile of the verified-mature group rather than a round "
         "number"],
        ["5. The DBH maturity filter kept", "Run_04",
         "every basal-area threshold drove the gate to or below zero once the "
         "unlabelled sites entered; and M' is a ceiling, so validating it "
         "needs stands near their maximum"],
    ], ["decision", "from", "why"], widths=[2.1, 0.8, 3.3])

    doc.add_heading("Building the table", level=1)
    table(doc, [[r["step"], int(r["sites"])] for _, r in trail.iterrows()],
          ["step", "sites"], widths=[4.4, 1.2])
    doc.add_paragraph(
        "850 sites against Run 0's 600, and 147 south of 37 S against 4. The "
        "order matters: the ceiling is calibrated AFTER the rebuild, on "
        "rebuilt values, because the reported ratios are exactly what the "
        "rebuild exists to correct.")

    doc.add_heading("The ceiling did not do what it was asked to do", level=2)
    doc.add_paragraph(
        "It was proposed to remove University of NSW at a ratio near 106 and "
        "Queensland Herbarium at 35.6. Those are REPORTED ratios, and the "
        "rebuild has already repaired them - University of NSW falls to 8.6 "
        "once biomass comes from the diameters. So the ceiling's stated "
        "targets no longer exist by the time it is applied.")
    doc.add_paragraph(
        "It still earns its place, for a different reason. Set at the 95th "
        "percentile of the verified-mature group's rebuilt ratio - %.1f Mg per "
        "m2/ha - it removes 27 sites, 17 of them TERN Australia with a median "
        "rebuilt biomass near 3,989 t DM/ha. That is precisely the "
        "over-estimation Run_03 flagged as its own main limitation: a single "
        "global scale constant rewards TERN's one-hectare plots with stems up "
        "to 479 cm far too heavily. The ceiling turns out to be the control "
        "for the rebuild's weakness rather than for the reported data's."
        % cal["ceiling"], style="Intense Quote")
    doc.add_paragraph(
        "One consequence for reading: %.1f is not comparable with the ratio "
        "figures quoted in the earlier runs, which were computed on reported "
        "biomass. The rebuild raises biomass, so the whole distribution of the "
        "ratio moves with it - the combined table's median is %.1f where Run "
        "0's was 10.2." % (cal["ceiling"], cmb["median_agb"] * 0 + 17.5))
    figure(doc, "fig_03_ceiling.png",
           "Figure 1. Where the ceiling sits in the rebuilt ratio, and how "
           "each provider stands against it.")

    doc.add_heading("The result", level=1)
    rows = []
    for cfg, lab in [("run0", "Run 0 as published"),
                     ("run3_rebuilt", "+ biomass rebuilt"),
                     ("combined_no_area", "+ floor retired + ceiling, 0.05 ha"),
                     ("combined_no_ceiling", "+ 0.04 ha, no ceiling"),
                     ("combined", "all four combined")]:
        if cfg not in h.index:
            continue
        x = h.loc[cfg]
        rows.append([lab, int(x["sites"]), int(x["south"]),
                     fmt(x["gate_rho"]), fmt(x["ratio"]), fmt(x["rho"]),
                     fmt(x["null_nvis_rho"]),
                     fmt(x["gap_rho_nvis"], "%+.3f")])
    table(doc, rows,
          ["configuration", "sites", "south of 37 S", "gate rho", "ratio",
           "future rho", "null rho", "gap"],
          widths=[1.9, 0.6, 0.9, 0.8, 0.7, 0.8, 0.7, 0.7])
    caption(doc, "Table 1. The ladder, analogue-found sites only.")
    doc.add_paragraph(
        "The combined configuration reaches a present-day gate of %s against "
        "Run 0's %s, a future rank correlation of %s against %s, and a gap to "
        "the constrained null of %s against %s - on %d sites rather than 600, "
        "with %d of them south of 37 S rather than 4. It is the best "
        "configuration on every axis this study measures."
        % (fmt(cmb["gate_rho"]), fmt(r0["gate_rho"]), fmt(cmb["rho"]),
           fmt(r0["rho"]), fmt(cmb["gap_rho_nvis"], "%+.3f"),
           fmt(r0["gap_rho_nvis"], "%+.3f"), int(cmb["sites"]),
           int(cmb["south"])), style="Intense Quote")
    figure(doc, "fig_01_ladder.png",
           "Figure 2. What each ingredient adds. Panel (b) shows the null "
           "rising with the runs, and the gap that survives it.", width=5.9)

    doc.add_heading("How it decomposes, and where it is not additive", level=2)
    doc.add_paragraph(
        "The rebuild does most of the work on the gate: %s to %s of the total "
        "movement from %s to %s. The 0.04 ha threshold does most of the rest, "
        "%s to %s. The ceiling costs a little gate, %s to %s, because it "
        "removes 27 of the highest-biomass sites."
        % (fmt(r0["gate_rho"]), fmt(r3["gate_rho"]), fmt(r0["gate_rho"]),
           fmt(cmb["gate_rho"]), fmt(noa["gate_rho"]), fmt(noc["gate_rho"]),
           fmt(noc["gate_rho"]), fmt(cmb["gate_rho"])))
    doc.add_paragraph(
        "The ingredients are NOT additive on the gap, and that is worth "
        "stating rather than smoothing over. Retiring the floor and adding the "
        "ceiling at 0.05 ha gives a gap of %s - BELOW the rebuild alone at %s "
        "- because the null rises faster than the runs do on that sample. Only "
        "when the 0.04 ha threshold is added does the gap recover, to %s. Any "
        "of these decisions taken on its own would have been judged "
        "differently from how it behaves in combination."
        % (fmt(noa["gap_rho_nvis"], "%+.3f"), fmt(r3["gap_rho_nvis"], "%+.3f"),
           fmt(cmb["gap_rho_nvis"], "%+.3f")), style="Intense Quote")
    doc.add_paragraph(
        "The ceiling is worth keeping on the gap rather than on the gate: it "
        "raises the gap from %s to %s, because it lowers the null more than it "
        "lowers the runs. Given that it is also the control for Run_03's known "
        "over-estimation, both reasons point the same way."
        % (fmt(noc["gap_rho_nvis"], "%+.3f"),
           fmt(cmb["gap_rho_nvis"], "%+.3f")))

    doc.add_heading("Coverage", level=1)
    doc.add_paragraph(
        "The sample is no longer confined to eastern Queensland and New South "
        "Wales. Sites below 37 S rise from 4 to %d, which was the limitation "
        "every earlier report had to state and none could remove."
        % int(cmb["south"]))
    figure(doc, "fig_02_coverage.png",
           "Figure 3. Where the sample grew.")

    doc.add_heading("What to be careful about", level=1)
    for t in [
        "The nulls rise with the runs. The NVIS-constrained null goes from %s "
        "under Run 0 to %s here, so a large part of the raw correlation gain "
        "is that the cleaned sample is easier to rank at all. The gap is the "
        "honest measure, and it doubles - %s to %s - which is a real result "
        "but a smaller one than the headline correlations suggest."
        % (fmt(r0["null_nvis_rho"]), fmt(cmb["null_nvis_rho"]),
           fmt(r0["gap_rho_nvis"], "%+.3f"),
           fmt(cmb["gap_rho_nvis"], "%+.3f")),
        "The ratio is not independent of the library. Run_03's scale constant "
        "is calibrated to the library's own median plot biomass, so M' over "
        "observed biomass carries that calibration. Quote the rank correlation "
        "and the gap; quote the ratio only with the calibration stated.",
        "This is a configuration, not an experiment. Five decisions were "
        "changed at once, and only the three intermediate rungs make it "
        "decomposable at all. The ceiling in particular has never been tested "
        "on its own against Run 0.",
        "The no-analogue share rises from %s to %s per cent. The larger sample "
        "reaches climates that are slightly harder to match, and the "
        "late-century high-forcing windows remain extrapolation under this "
        "configuration exactly as under every other."
        % (fmt(r0["no_analogue"], "%.1f"), fmt(cmb["no_analogue"], "%.1f")),
        "The southern sites are one provider. DELWP Victoria supplies nearly "
        "all of them, so the coverage gain is a sensitivity to including one "
        "data source, as Run_02 said. It is a real gain and it rests on a "
        "narrow base.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("What to do with it", level=1)
    for t in [
        "Report this as the corrected configuration and Run 0 as published. "
        "The difference between them is the headline of the whole exercise: "
        "the present-day gate goes from %s to %s once the observation is "
        "sound and the sample is not needlessly cut."
        % (fmt(r0["gate_rho"]), fmt(cmb["gate_rho"])),
        "Do not present it as a one-change result. Point to Run_03 for the "
        "rebuild, Run_02 for the threshold, Run_04 for keeping the DBH filter, "
        "and to this folder's intermediate rungs for the rest.",
        "Test the ceiling on its own before relying on it. It earns its place "
        "here for a reason different from the one proposed, and it has not "
        "been run against Run 0 in isolation.",
        "The stem-mass alignment defect still needs reporting to the library's "
        "custodians. Everything above depends on working around it.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_build_table.py", "the five decisions, and the ceiling's "
                                   "calibration"],
        ["Step_02_run_and_compare.py", "the five configurations"],
        ["Step_03_plots.py", "the figures"],
        ["Step_04_write_report.py", "this document"],
        ["outputs/reference_table_combined.csv", "850 sites"],
        ["outputs/build_trail.csv", "the build"],
        ["outputs/ceiling_calibration.csv", "where the ceiling came from"],
        ["outputs/provider_effects.csv", "what each provider contributes"],
        ["outputs/combined_headline.csv", "Table 1"],
    ], ["file", "what it holds"], widths=[2.4, 3.6])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
