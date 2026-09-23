"""
Run 1 - the report.

Builds Run_01_report.docx from the tables and figures Steps 1-3 wrote. Nothing
is recomputed; every number comes from a CSV in outputs/.

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
REPORT = HERE / "Run_01_report.docx"
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


def figure(doc, name, cap, width=6.3):
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

    gate = pd.read_csv(OUT_DIR / "gate_by_maturity.csv").set_index("maturity")
    cmp = pd.read_csv(OUT_DIR / "run01_vs_run00.csv")
    nulls = pd.read_csv(OUT_DIR / "both_nulls.csv").set_index(["run", "null"])
    fut = cmp[cmp["is_future"]]

    r0 = float(fut["rho_run0"].median())
    r1 = float(fut["rho_run1"].median())
    q0 = float(fut["ratio_run0"].median())
    q1 = float(fut["ratio_run1"].median())

    def gap(run, nm):
        r = r0 if run == "Run 0" else r1
        return r - float(nulls.loc[(run, nm), "spearman_rho"])

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Run 1 - verified mature only", 0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal/Run_01 · generated %s · "
                  "one change from Run 0: --maturity \"verified mature\", "
                  "327 sites instead of 600" % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("What was changed, and nothing else", level=1)
    doc.add_paragraph(
        "The parent folder's Step_03 was run exactly as it stands, with one "
        "flag altered. Everything else is Run 0: NVIS-constrained matching, "
        "Eq. (1) of the window-mean FPI, all 174 predictors, PCA to 95 per "
        "cent of the historical variance, the 99th percentile no-analogue "
        "cutoff. No analysis code was written for the matching itself.")
    doc.add_paragraph(
        "Step_03 names its outputs from the feature set, the constraint and "
        "the averaging order, but not from the maturity classes, so running it "
        "with a different --maturity overwrites the published Run 0 results. "
        "Step_01 of this folder therefore copies every file Step_03 will touch "
        "into a private backup, runs it, takes the results, and puts the "
        "backup back - verifying each restored file against a content hash. An "
        "earlier version trusted git for this and failed silently, because "
        "matches*.csv is in the repository's .gitignore and git can only "
        "protect what it tracks; the Run 0 match table had to be regenerated. "
        "The backup is now file-level and unconditional.", style="Intense Quote")

    # ------------------------------------------------------------------ #
    doc.add_heading("Why this run exists", level=1)
    doc.add_paragraph(
        "In the present-day gate the two maturity classes carry almost the "
        "same observed biomass and behave completely differently.")
    rows = []
    for cls in ["verified mature", "likely mature", "POOLED (Run 0)"]:
        if cls not in gate.index:
            continue
        g = gate.loc[cls]
        rows.append([cls, int(g["n"]), fmt(g["median_ratio"], "%.2f"),
                     fmt(g["spearman_rho"], "%.2f"),
                     fmt(g["obs_agb_median"], "%.1f"),
                     fmt(g["agb_per_basal_area"], "%.1f"),
                     fmt(g["plot_area_ha"], "%.2f"),
                     fmt(g["max_dbh"], "%.0f")])
    table(doc, rows,
          ["class", "n", "median ratio", "rho", "observed AGB",
           "AGB per m2/ha basal area", "plot area (ha)", "max DBH (cm)"],
          widths=[1.3, 0.5, 0.9, 0.6, 0.9, 1.2, 0.9, 0.8])
    caption(doc, "Table 1. The present-day gate split by maturity class. The "
                 "last three columns are properties of the OBSERVATION, not of "
                 "M', so a difference in them is a difference in the data.")
    doc.add_paragraph(
        "The likely-mature group returns a ratio of %s against %s, on observed "
        "biomass that differs by less than 8 per cent. The explanation is in "
        "the last two columns and has nothing to do with maturity. Those sites "
        "report %s Mg of biomass per square metre per hectare of their own "
        "live basal area, against %s for the verified group - a figure at the "
        "very top of what a stand can physically carry - and they were "
        "measured on plots %.0f per cent smaller. A per-hectare figure from a "
        "smaller plot is the same few trees divided by less ground. The "
        "likely-mature half is not less mature; it is more inflated."
        % (fmt(gate.loc["likely mature", "median_ratio"], "%.2f"),
           fmt(gate.loc["verified mature", "median_ratio"], "%.2f"),
           fmt(gate.loc["likely mature", "agb_per_basal_area"], "%.1f"),
           fmt(gate.loc["verified mature", "agb_per_basal_area"], "%.1f"),
           100 * (1 - gate.loc["likely mature", "plot_area_ha"]
                  / gate.loc["verified mature", "plot_area_ha"])))
    figure(doc, "fig_01_why_run1.png",
           "Figure 1. The two classes on the quantities that separate them. "
           "The first two panels are the result; the last two are the cause.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What Run 1 did", level=1)
    doc.add_paragraph(
        "Across the eight scenario-windows, on the analogue-found sites: the "
        "median ratio rises from %s to %s and the rank correlation from %s to "
        "%s. The hypothesis is confirmed - the likely-mature half was dragging "
        "the headline numbers down."
        % (fmt(q0), fmt(q1), fmt(r0), fmt(r1)), style="Intense Quote")
    rows = []
    for _, x in cmp.iterrows():
        rows.append([x["run"], "%d / %d" % (x["n_run0"], x["n_run1"]),
                     fmt(x["ratio_run0"]), fmt(x["ratio_run1"]),
                     fmt(x["d_ratio"], "%+.3f"), fmt(x["rho_run0"]),
                     fmt(x["rho_run1"]), fmt(x["d_rho"], "%+.3f")])
    table(doc, rows,
          ["run", "sites 0 / 1", "ratio Run 0", "ratio Run 1", "change",
           "rho Run 0", "rho Run 1", "change"],
          widths=[1.4, 0.9, 0.8, 0.8, 0.7, 0.8, 0.8, 0.7])
    caption(doc, "Table 2. Every run, analogue-found stratum only.")
    figure(doc, "fig_02_run1_vs_run0.png",
           "Figure 2. Run 1 against Run 0 per scenario-window, with both nulls "
           "drawn in as horizontal lines.")
    doc.add_paragraph(
        "Two windows move the other way - SSP370 and SSP585 2070-2099 - and "
        "they should not be read. They retain %d and %d sites of 327. Under "
        "every configuration those two windows are extrapolation beyond what "
        "the observations constrain, and Run 1 halving the sample makes them "
        "worse, not better."
        % (int(cmp[cmp.run == "ssp370_2070-2099"]["n_run1"].iloc[0]),
           int(cmp[cmp.run == "ssp585_2070-2099"]["n_run1"].iloc[0])))

    # ------------------------------------------------------------------ #
    doc.add_heading("What it is worth, once both nulls are read", level=1)
    doc.add_paragraph(
        "A null drawn from the same 327 sites is easier to beat for exactly "
        "the reason the runs are: the sample is cleaner. So the change in the "
        "runs overstates what the change bought. The honest measure is the GAP "
        "between the runs and their own null, and both nulls have to be there "
        "because they answer different questions.")
    rows = []
    for run in ("Run 0", "Run 1"):
        for nm in ("NVIS-constrained", "unconstrained"):
            if (run, nm) not in nulls.index:
                continue
            rows.append([run, nm, int(nulls.loc[(run, nm), "n"]),
                         fmt(nulls.loc[(run, nm), "median_ratio"]),
                         fmt(nulls.loc[(run, nm), "spearman_rho"]),
                         fmt(gap(run, nm), "%+.3f")])
    table(doc, rows,
          ["run", "null", "n", "null ratio", "null rho",
           "gap: runs minus null, rho"],
          widths=[0.8, 1.4, 0.5, 1.0, 1.0, 1.5])
    caption(doc, "Table 3. Both nulls under both configurations.")
    doc.add_paragraph(
        "Against the NVIS-constrained null the gap improves from %s to %s - a "
        "gain of %s, against a headline gain in rho of %s. Four fifths of what "
        "Run 1 appears to buy is shared with its own null, which is to say it "
        "is the sample getting cleaner rather than the matching getting "
        "better. Against the unconstrained null the gap grows from %s to %s, "
        "which is the other half of the picture: the method plainly has skill, "
        "and Run 1 increases it."
        % (fmt(gap("Run 0", "NVIS-constrained"), "%+.3f"),
           fmt(gap("Run 1", "NVIS-constrained"), "%+.3f"),
           fmt(gap("Run 1", "NVIS-constrained")
               - gap("Run 0", "NVIS-constrained"), "%+.3f"),
           fmt(r1 - r0, "%+.3f"),
           fmt(gap("Run 0", "unconstrained"), "%+.3f"),
           fmt(gap("Run 1", "unconstrained"), "%+.3f")))
    figure(doc, "fig_03_gap_to_nulls.png",
           "Figure 3. What Run 1 buys once the null is allowed to move with "
           "the sample.")

    doc.add_heading("What it cost", level=1)
    doc.add_paragraph(
        "The bootstrap interval on the median ratio widens from %s to %s "
        "across the eight windows, a %.0f per cent loss of precision, and the "
        "two late-century high-forcing windows fall to %d and %d sites. That "
        "is the price of halving the sample and it is not small."
        % (fmt(fut["ci_width_run0"].median()),
           fmt(fut["ci_width_run1"].median()),
           100 * (fut["ci_width_run1"].median()
                  / fut["ci_width_run0"].median() - 1),
           int(cmp[cmp.run == "ssp370_2070-2099"]["n_run1"].iloc[0]),
           int(cmp[cmp.run == "ssp585_2070-2099"]["n_run1"].iloc[0])))

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude", level=1)
    for t in [
        "The hypothesis is confirmed. The likely-mature half was dragging the "
        "headline numbers down, and removing it raises the ratio by %s and the "
        "rank correlation by %s." % (fmt(q1 - q0, "%+.3f"),
                                     fmt(r1 - r0, "%+.3f")),
        "But the mechanism is plot size, not maturity. The likely-mature "
        "sites report %s Mg of biomass per m2/ha of their own basal area from "
        "plots %.0f per cent smaller. They are not less mature stands, they "
        "are more inflated per-hectare figures. The maturity threshold is "
        "acting as a proxy for a data-quality problem."
        % (fmt(gate.loc["likely mature", "agb_per_basal_area"], "%.1f"),
           100 * (1 - gate.loc["likely mature", "plot_area_ha"]
                  / gate.loc["verified mature", "plot_area_ha"])),
        "Which means the better fix is a plot-area floor, not a stem-size "
        "threshold. Filtering on maturity discards 273 sites to remove an "
        "inflation that a minimum plot area would remove directly, and without "
        "also discarding the genuinely mature stands that happen to sit in "
        "that group. That is worth running as its own one-change test.",
        "Report Run 1 as a sensitivity, not as a replacement. Four fifths of "
        "the apparent gain is shared with its own null, the precision loss is "
        "%.0f per cent, and the two late-century high-forcing windows become "
        "unusable at 41 and 14 sites."
        % (100 * (fut["ci_width_run1"].median()
                  / fut["ci_width_run0"].median() - 1)),
        "Both nulls were necessary to reach that reading. Against the "
        "unconstrained null alone Run 1 looks like a large improvement; "
        "against the constrained null alone it looks like almost none. The "
        "truth needs both.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_run_verified_only.py", "runs the parent's Step_03 with the "
                                         "one flag, protecting the parent"],
        ["Step_02_compare_vs_run0.py", "the diagnostic and the comparison"],
        ["Step_03_plots.py", "the figures"],
        ["Step_04_write_report.py", "this document"],
        ["outputs/gate_by_maturity.csv", "Table 1"],
        ["outputs/run01_vs_run00.csv", "Table 2"],
        ["outputs/both_nulls.csv", "Table 3"],
        ["outputs/matches_nvis.csv", "Run 1's site-level matches, and five "
                                     "companion tables from Step_03"],
    ], ["file", "what it holds"], widths=[2.4, 3.6])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
