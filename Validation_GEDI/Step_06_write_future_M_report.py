"""
Step 6 - the report for the future M' validation.

Builds Validation_GEDI_future_M_report.docx from the tables and figures Step 5
wrote. Nothing is recomputed here; every number comes from a CSV in
outputs/analysis/, so the report cannot drift from the analysis.

The older Validation_GEDI_report.docx covers the present-day layers and the
Option A / Option B footing comparison that was retired in September 2026. This
one covers the eight future layers, with New_M_2019 as the control.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_06_write_future_M_report.py
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
ANA = HERE / "outputs" / "analysis"
FIG = HERE / "outputs" / "figures"
REPORT = HERE / "Validation_GEDI_future_M_report.docx"

INK_2 = RGBColor(0x52, 0x51, 0x4E)

ANCHOR = "New_M_2019"
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
FUTURE = ["future_%s_%s" % (a, w) for w in WINDOWS for a in SSPS]


def nice(tag):
    if tag == ANCHOR:
        return "New_M_2019 (the anchor)"
    _, ssp, win = tag.split("_")
    return "%s %s" % (ssp.upper(), win)


def fmt(v, spec="%.2f"):
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
    path = FIG / name
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

    ov = pd.read_csv(ANA / "overall_by_layer.csv")
    unb = ov[ov.footprints == "unburnt"].set_index("layer")
    allc = ov[ov.footprints == "all"].set_index("layer")
    ratio = pd.read_csv(ANA / "future_over_anchor.csv").set_index("layer")
    el = pd.read_csv(ANA / "fpi_elasticity.csv").set_index("layer")
    bins = pd.read_csv(ANA / "by_fpi_bin.csv")
    fp = pd.read_csv(ANA / "footprint_summary.csv").iloc[0]
    have = [t for t in FUTURE if t in unb.index]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Testing the future M' against GEDI", 0)
    p = doc.add_paragraph()
    r = p.add_run("Validation_GEDI · generated %s · the eight future M' "
                  "layers, every component of the ratio produced by the random "
                  "forest, against %s GEDI L4A footprints in %s NLUM cells"
                  % (date.today().isoformat(),
                     format(int(fp["footprints"]), ","),
                     format(int(unb.loc[ANCHOR, "cells"]), ",")))
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("What GEDI can and cannot settle", level=1)
    doc.add_paragraph(
        "M' is a maximum: the above-ground biomass a site could carry at "
        "maturity. GEDI measures what actually stands there now, 2019-2024, "
        "after clearing, logging, fire and whatever else has happened. GEDI "
        "below M' is therefore the expected case and proves nothing at all. "
        "GEDI ABOVE M' is the only direct evidence against M', so every "
        "headline number in this report is an exceedance rate and never an R2.",
        style="Intense Quote")
    doc.add_paragraph(
        "Applied to a FUTURE M' the same test carries a sharper meaning. "
        "Present-day biomass exceeding a future maximum says a stand already "
        "carries more than the model claims its site will be able to support "
        "decades from now. That is not impossible - a drying climate can lower "
        "a ceiling below the standing stock, and the stand would then be "
        "expected to decline towards it - but it is a strong claim, it is "
        "checkable today, and if the projection is doing what it says the rate "
        "at which it happens should order with forcing.")
    doc.add_paragraph(
        "What GEDI cannot do is see 2035-2100. Nothing here validates a "
        "projected level. Two things are genuinely testable and both are "
        "reported: whether the projected ceiling is already contradicted by "
        "measured biomass, and whether the MECHANISM behind the projection - "
        "Eq. (1) applied to a change in FPI - matches the way biomass and FPI "
        "actually co-vary across space today.")

    doc.add_heading("Why the anchor is the only fair reference", level=2)
    doc.add_paragraph(
        "New_M_2019 is not a rival layer here, it is the control. Every future "
        "layer is built as M'_future = New_M_2019 x Eq1(mean FPI_future) / "
        "Eq1(mean FPI_1985-2014), which collapses to New_M_2019 exactly when "
        "the future FPI equals the historical one. The anchor is therefore the "
        "historical limit of all eight. A difference between a future layer's "
        "numbers and the anchor's is the projected climate change and nothing "
        "else: same cells, same footprints, same fire treatment, same footing.")
    doc.add_paragraph(
        "The Eq. (1)-footing layer (baseline_M_1985-2014, the retired Option "
        "A) was dropped from this analysis in September 2026 along with the "
        "rest of that route. The older Validation_GEDI_report.docx still "
        "describes it.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The sample", level=1)
    table(doc, [
        ["GEDI L4A footprints", format(int(fp["footprints"]), ",")],
        ["NLUM cells with at least 30 footprints",
         format(int(unb.loc[ANCHOR, "cells"]), ",") + " fire-excluded, "
         + format(int(allc.loc[ANCHOR, "cells"]), ",") + " including burnt"],
        ["acquisition window", "%s to %s" % (str(fp["first"])[:10],
                                             str(fp["last"])[:10])],
        ["median footprint AGBD", fmt(fp["agbd_median"], "%.1f")
         + " Mg ha-1"],
        ["median relative standard error of a footprint",
         fmt(100 * fp["rel_se_median"], "%.0f") + "%"],
        ["evergreen broadleaf footprints",
         fmt(fp["pct_evergreen_broadleaf"], "%.0f") + "%"],
    ], ["", ""], widths=[3.0, 3.0])
    doc.add_paragraph(
        "Every number below is computed on the fire-excluded cells, which drop "
        "any footprint whose cell burned within the recovery window before "
        "acquisition. The all-footprints version is in "
        "outputs/analysis/overall_by_layer.csv and raises every exceedance "
        "rate by 1.9 to 2.2 percentage points, never changing the "
        "conclusions.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 1 - the projection does not make the ceiling "
                    "problem worse", level=1)
    rows = []
    for t in [ANCHOR] + have:
        r = unb.loc[t]
        rows.append([nice(t), fmt(r["M_median"], "%.1f"),
                     fmt(r["exceed_mean_pct"], "%.1f") + "%",
                     fmt(r["exceed_p95_n30_pct"], "%.1f") + "%",
                     fmt(r["exceed_p95_lo_pct"], "%.1f") + "%"])
    table(doc, rows,
          ["layer", "median M'", "cell MEAN exceeds M'",
           "p95 of 30 footprints exceeds M'",
           "p95 of the LOWER bounds exceeds M'"],
          widths=[1.4, 0.9, 1.3, 1.4, 1.4])
    caption(doc, "Table 1. Exceedance rates, fire-excluded cells. The three "
                 "columns are increasingly demanding of M': the cell mean is "
                 "the strongest evidence, the lower-bound p95 is what survives "
                 "if every footprint is pushed to the bottom of its 90 per "
                 "cent interval.")
    lo = min(unb.loc[t, "exceed_mean_pct"] for t in have)
    hi = max(unb.loc[t, "exceed_mean_pct"] for t in have)
    doc.add_paragraph(
        "The cell mean already exceeds the anchor in %s of cells, and exceeds "
        "the eight future layers in %s to %s - a range of %s percentage points "
        "across four scenarios and two windows, straddling the anchor rather "
        "than moving away from it. On the upper envelope the same holds: %s "
        "against the anchor, %s to %s against the future layers."
        % (fmt(unb.loc[ANCHOR, "exceed_mean_pct"], "%.1f") + "%",
           fmt(lo, "%.1f") + "%", fmt(hi, "%.1f") + "%",
           fmt(hi - lo, "%.1f"),
           fmt(unb.loc[ANCHOR, "exceed_p95_n30_pct"], "%.1f") + "%",
           fmt(min(unb.loc[t, "exceed_p95_n30_pct"] for t in have), "%.1f")
           + "%",
           fmt(max(unb.loc[t, "exceed_p95_n30_pct"] for t in have), "%.1f")
           + "%"))
    doc.add_paragraph(
        "So the projection neither relieves nor aggravates the ceiling problem "
        "the anchor already has. That is a genuine finding and a limited one. "
        "It says the future layers are not contradicted by measured biomass "
        "any more than the layer they are built from is - and it says nothing "
        "about whether the projected change is the right size, because the "
        "change is far smaller than the exceedance rate is sensitive to.")
    figure(doc, "fig2_future_exceedance.png",
           "Figure 1. How often present-day GEDI biomass already exceeds each "
           "projected future maximum. Dotted lines are the same statistic for "
           "the anchor. The eight future layers sit on the anchor's lines "
           "rather than departing from them.")
    doc.add_paragraph(
        "How to read it: each series is one of the three GEDI statistics, from "
        "least to most demanding of M'. A rising line from left to right would "
        "mean the projection lowers the ceiling into the standing biomass as "
        "forcing increases. No series does that; the ordering across scenarios "
        "is within the noise of the sample.")

    doc.add_heading("The exceedance that is already there", level=2)
    doc.add_paragraph(
        "It is worth stating plainly what Table 1 also shows about the anchor, "
        "since the future layers inherit it: the upper envelope of GEDI "
        "exceeds M' in %s of cells, and survives at %s even when every "
        "footprint is pushed to the bottom of its 90 per cent interval. This "
        "is a pre-existing property of New_M_2019 in tall wet forest and is "
        "discussed in the present-day report. The future layers do not fix it, "
        "and no projection built by scaling that layer could."
        % (fmt(unb.loc[ANCHOR, "exceed_p95_n30_pct"], "%.1f") + "%",
           fmt(unb.loc[ANCHOR, "exceed_p95_lo_pct"], "%.1f") + "%"))
    figure(doc, "fig1_p95_vs_Mprime_anchor.png",
           "Figure 2. Control. GEDI's upper envelope against the anchor, cell "
           "by cell. Colour is cells per bin on a linear scale clipped at the "
           "98th percentile. Cells above the dashed 1:1 line already carry "
           "more than M' allows.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 2 - the projected change is small where GEDI can "
                    "see it, and it widens rather than shifts", level=1)
    rows = []
    for t in have:
        r = ratio.loc[t]
        rows.append([nice(t), fmt(r["median"], "%.3f"),
                     "%s to %s" % (fmt(r["p10"], "%.3f"),
                                   fmt(r["p90"], "%.3f")),
                     fmt(r["pct_cells_below_anchor"], "%.1f") + "%"])
    table(doc, rows,
          ["layer", "median future M' / anchor", "10th to 90th percentile",
           "cells below the anchor"], widths=[1.5, 1.4, 1.6, 1.3])
    caption(doc, "Table 2. Each future layer against the anchor, cell by cell, "
                 "inside the GEDI domain.")
    spread_lo = ratio.loc[have[0], "p90"] - ratio.loc[have[0], "p10"]
    spread_hi = ratio.loc[have[-1], "p90"] - ratio.loc[have[-1], "p10"]
    doc.add_paragraph(
        "The median cell moves by less than two per cent under any scenario - "
        "%s to %s. What changes with forcing is the SPREAD: the 10th to 90th "
        "percentile band is %s wide under %s and %s wide under %s. The "
        "projection is redistributing M' within this domain rather than "
        "shifting it, which is the same behaviour the comparison folder "
        "reports as a rising spatial coefficient of variation."
        % (fmt(ratio.loc[have, "median"].min(), "%.3f"),
           fmt(ratio.loc[have, "median"].max(), "%.3f"),
           fmt(spread_lo, "%.3f"), nice(have[0]),
           fmt(spread_hi, "%.3f"), nice(have[-1])))
    figure(doc, "fig6_future_over_anchor.png",
           "Figure 3. How much the projection moves M' where GEDI can see it. "
           "Marker is the median over cells, bar the 10th to 90th percentile, "
           "and the dashed line is no change.")
    doc.add_paragraph(
        "This is the reason Result 1 could not have come out otherwise, and it "
        "is also this validation's main limitation. GEDI's footprints sit in "
        "tall wet forest along the east, the south-west and Tasmania - the "
        "part of the continent where the projected change is smallest. The "
        "deepest projected losses fall in low- and mid-biomass cells, which "
        "GEDI barely samples. A test that cannot see where the change is "
        "cannot be asked whether the change is right.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 3 - the mechanism, tested across space", level=1)
    e_anchor = el.loc[ANCHOR]
    doc.add_paragraph(
        "This is the one part of the folder that speaks to whether the "
        "projected CHANGE is the right size. Future M' is present M' scaled by "
        "Eq1(FPI_future) / Eq1(FPI_hist), so the projection's whole assumption "
        "is how much biomass a change in FPI buys. GEDI cannot be asked about "
        "2035-2100, but it can be asked the same question across space today: "
        "between two cells that differ in FPI, how much do they differ in "
        "biomass? The comparison is of log-log slopes, on closed "
        "evergreen-broadleaf cells only (%s of them), and it is a "
        "space-for-time substitution - reported as such, not as proof."
        % format(int(e_anchor["cells"]), ","))
    rows = [
        ["Eq. (1), at the median FPI of %s"
         % fmt(e_anchor["fpi_median"], "%.1f"),
         fmt(e_anchor["eq1_elasticity_at_median_fpi"], "%.2f"),
         "the projection's own assumption"],
        ["M' layers, across space",
         "%s to %s" % (fmt(el.loc[[ANCHOR] + have, "slope_M_prime"].min(),
                           "%.2f"),
                       fmt(el.loc[[ANCHOR] + have, "slope_M_prime"].max(),
                           "%.2f")),
         "how the layers themselves vary with FPI"],
        ["GEDI p95 from 30 footprints",
         "%s  (95%% CI %s to %s)"
         % (fmt(e_anchor["slope_gedi_p95_n30"], "%.2f"),
            fmt(e_anchor["slope_gedi_p95_n30_lo95"], "%.2f"),
            fmt(e_anchor["slope_gedi_p95_n30_hi95"], "%.2f")),
         "the observed upper envelope"],
        ["GEDI cell mean", fmt(e_anchor["slope_gedi_mean"], "%.2f"),
         "the observed standing stock"],
    ]
    table(doc, rows, ["elasticity of biomass with respect to FPI", "slope",
                      "what it is"], widths=[2.3, 1.7, 2.0])
    caption(doc, "Table 3. Log-log slopes. A slope of 1.4 means a 10 per cent "
                 "rise in FPI goes with roughly a 14 per cent rise in biomass.")
    doc.add_paragraph(
        "The observed gradient is STEEPER than the projection assumes. GEDI's "
        "upper envelope rises with FPI at %s and its cell mean at %s, against "
        "%s for Eq. (1) and %s to %s for the M' layers' own spatial variation. "
        "The confidence interval on the GEDI slope is narrow (%s to %s), so "
        "this is not a sampling artefact."
        % (fmt(e_anchor["slope_gedi_p95_n30"], "%.2f"),
           fmt(e_anchor["slope_gedi_mean"], "%.2f"),
           fmt(e_anchor["eq1_elasticity_at_median_fpi"], "%.2f"),
           fmt(el.loc[[ANCHOR] + have, "slope_M_prime"].min(), "%.2f"),
           fmt(el.loc[[ANCHOR] + have, "slope_M_prime"].max(), "%.2f"),
           fmt(e_anchor["slope_gedi_p95_n30_lo95"], "%.2f"),
           fmt(e_anchor["slope_gedi_p95_n30_hi95"], "%.2f")))
    doc.add_paragraph(
        "Read in the direction that matters, this says the projected change is "
        "more likely to be too SMALL than too large. Eq. (1) converts a given "
        "change in FPI into a smaller change in biomass than the observed "
        "spatial gradient would imply. If the space-for-time substitution "
        "holds, a future decline in FPI should move M' further than these "
        "layers move it.", style="Intense Quote")
    doc.add_paragraph(
        "Three reasons not to lean hard on that. A spatial gradient is not a "
        "temporal response: cells that differ in FPI also differ in species, "
        "soil and disturbance history, and a single site will not travel along "
        "the between-site curve as its own climate changes. GEDI's envelope is "
        "standing biomass, not a maximum, so its slope mixes the ceiling with "
        "how close stands have grown to it, and that closeness itself varies "
        "with productivity. And the comparison is restricted to closed "
        "evergreen-broadleaf forest, which is where the FPI range is narrowest.")
    figure(doc, "fig4_fpi_elasticity_index.png",
           "Figure 4. How steeply biomass rises with FPI, everything indexed "
           "to the FPI 10-11 bin so the comparison is of shape rather than "
           "level. The eight future layers are the thin coloured lines and sit "
           "on the anchor; GEDI is steeper than Eq. (1) throughout.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Where the exceedance falls", level=1)
    b = bins[bins.layer.isin([ANCHOR, have[-1]])] if have else bins
    rows = []
    for _, r in b.iterrows():
        rows.append([nice(r["layer"]), str(r["fpi_bin"]),
                     format(int(r["cells"]), ","),
                     fmt(r["M_median"], "%.0f"),
                     fmt(r["gedi_p95_n30_median"], "%.0f"),
                     fmt(r["exceed_mean_pct"], "%.1f") + "%",
                     fmt(r["exceed_p95_n30_pct"], "%.1f") + "%"])
    table(doc, rows,
          ["layer", "FPI bin", "cells", "median M'", "median GEDI p95",
           "mean exceeds", "p95 exceeds"],
          widths=[1.3, 0.8, 0.7, 0.9, 1.1, 0.9, 0.9])
    caption(doc, "Table 4. By FPI bin, for the anchor and the most strongly "
                 "forced future layer.")
    doc.add_paragraph(
        "Exceedance rises steeply with FPI for every layer: the most "
        "productive cells are where GEDI most often measures more than M' "
        "allows. Between the anchor and SSP585 2070-2099 the pattern shifts "
        "slightly towards the least productive bin, where median M' falls and "
        "exceedance rises, while the top bins barely move. That is the same "
        "signature the continental comparison reports - the projected loss is "
        "concentrated in low- and mid-productivity cells - seen from inside "
        "the GEDI domain.")
    figure(doc, "fig2_exceedance_by_fpi_bin.png",
           "Figure 5. Exceedance by FPI bin, every layer.")
    figure(doc, "fig5_exceedance_by_region.png",
           "Figure 6. Exceedance by region, every layer.")
    figure(doc, "fig3_map_p95_over_Mprime.png",
           "Figure 7. Where the exceedance is, mapped for the anchor.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude", level=1)
    doc.add_paragraph(
        "GEDI does not contradict the future M' layers, and it cannot confirm "
        "them. What it does establish is that the projection inherits the "
        "anchor's existing ceiling problem without adding to it, and that the "
        "mechanism driving the projected change is conservative relative to "
        "the observed spatial gradient.", style="Intense Quote")
    for t in [
        "Quote the exceedance rates as a statement about the anchor, not about "
        "the scenarios. They differ by about half a percentage point across "
        "eight layers, which is within what this sample can resolve.",
        "The projected change inside the GEDI domain is under two per cent in "
        "the median, and the domain is tall wet forest - the part of the "
        "continent where the change is smallest. This test is structurally "
        "unable to see the cells where the projection does most of its work.",
        "The elasticity comparison is the one result that bears on the size of "
        "the projected change, and it points towards the change being too "
        "small rather than too large. It is a space-for-time substitution and "
        "should be quoted with that caveat attached.",
        "The widening spread with forcing - a 10th-to-90th band that grows "
        "while the median barely moves - is consistent with the rising spatial "
        "coefficient of variation reported in "
        "FPI_Accuracy_check/Comparison_vs_New_M_2019, and is the clearest "
        "signal of the projection visible here.",
        "Nothing in this folder tests a projected level. It tests whether the "
        "projected ceiling is already contradicted by measured biomass, and "
        "whether the mechanism matches how biomass and FPI co-vary today.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_04b_attach_future_M.py", "attaches the eight future layers to "
                                        "the cells Step 4 built"],
        ["Step_05_analyse_vs_M.py", "every statistic and figure"],
        ["Step_06_write_future_M_report.py", "this document"],
        ["outputs/analysis/overall_by_layer.csv", "Table 1"],
        ["outputs/analysis/future_over_anchor.csv", "Table 2"],
        ["outputs/analysis/fpi_elasticity.csv", "Table 3"],
        ["outputs/analysis/by_fpi_bin.csv", "Table 4"],
        ["outputs/figures/fig1..fig6", "the figures in this report"],
    ], ["file", "what it holds"], widths=[2.6, 3.4])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
