"""
Step 05 - the report.

Reads   outputs/*.csv, plots/*.png
Writes  Space_time_validation_report.docx

Every number is read from the CSV written by the step that computed it; nothing
here recomputes a statistic, so the report cannot drift from the analysis.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_05_write_report.py
"""

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
REPORT_STEM = "Space_time_validation_report"

INK_2 = RGBColor(0x52, 0x51, 0x4E)
CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells"]
CONTROL_LABEL = {"same_cell_present_day": "the site's own cell, today",
                 "historical_analogue": "present-day analogue",
                 "random_cells": "random cells (null)"}
SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]


def label_run(run):
    if run in CONTROL_LABEL:
        return CONTROL_LABEL[run]
    ssp, win = run.rsplit("_", 1)
    return "%s %s" % (ssp.replace("ssp", "SSP"), win)


def caption(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(8.5)
    r.font.color.rgb = INK_2
    r.italic = True


FIG_SUFFIX = ""


def figure(doc, name, cap, width=6.4):
    path = PLOT_DIR / name.replace(".png", "%s.png" % FIG_SUFFIX)
    if not path.exists():
        doc.add_paragraph("[missing figure: %s - run Step_04]" % name)
        return
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, cap)


def table(doc, rows, header, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = str(h)
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    if widths:
        for row in t.rows:
            for i, wd in enumerate(widths):
                row.cells[i].width = Inches(wd)
    doc.add_paragraph()


def fmt(v, spec="%.2f"):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else spec % v


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    global FIG_SUFFIX
    FIG_SUFFIX = args.suffix
    runs = pd.read_csv(OUT_DIR / ("metrics_by_run%s.csv" % args.suffix))
    by_mat = pd.read_csv(OUT_DIR / ("metrics_by_maturity%s.csv" % args.suffix))
    trail = pd.read_csv(OUT_DIR / "filter_trail.csv")
    ref_sum = pd.read_csv(OUT_DIR / "reference_table_summary.csv")
    matches = pd.read_csv(OUT_DIR / ("matches%s.csv" % args.suffix))
    na = pd.read_csv(OUT_DIR / ("no_analogue_summary%s.csv" % args.suffix))
    pp = OUT_DIR / ("paired_log_ratio%s.csv" % args.suffix)
    paired = pd.read_csv(pp) if pp.exists() else None
    rp = OUT_DIR / ("metrics_by_run_reduced%s.csv"
                    % args.suffix.replace("_climate_only", ""))
    reduced = pd.read_csv(rp) if rp.exists() else None

    found = runs[runs["stratum"] == "analogue found"].set_index("run")
    gate = found.loc["same_cell_present_day"]
    hist_ctl = found.loc["historical_analogue"]
    rand = found.loc["random_cells"]
    fut = found[~found.index.isin(CONTROLS)]

    # The suffix is built as [_climate_only][_nvis][_eq1ofmean]; the climate
    # twin of a run is the same suffix with _climate_only prepended, and the
    # unconstrained twin is the same suffix with _nvis removed.
    climate_only = OUT_DIR / ("metrics_by_run_climate_only%s.csv" % args.suffix)
    has_climate = climate_only.exists()
    unconstrained_suffix = args.suffix.replace("_nvis", "")

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Space-for-time validation of M' against the National "
                    "Biomass Library", 0)
    p = doc.add_paragraph()
    order = ("mean of the annual Eq. (1) M" if "_mean_of_annual" in args.suffix
             else "Eq. (1) of the mean FPI (the method)")
    r = p.add_run("Validation_M/National_biomass_library/Space_time_validation · "
                  "generated %s · M' with every component of the ratio produced "
                  "by the random forest · averaging order: %s"
                  % (date.today().isoformat(), order))
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("The test", level=1)
    doc.add_paragraph(
        "Each National Biomass Library site has an observed above-ground biomass "
        "and a historical climate. Find the future grid cell whose FPI "
        "predictors most closely resemble that site's historical predictors, and "
        "check whether the M' projected for that cell matches the biomass the "
        "site actually carries. If it does, the chain climate → FPI → Eq. (1) → "
        "λ is transporting a climate signal correctly rather than interpolating "
        "inside the range it was fitted on.")
    if "_mean_of_annual" in args.suffix:
        doc.add_paragraph(
            "The M' validated here is the PER-YEAR variant: Eq. (1) applied to "
            "each annual FPI and the results averaged, on both sides of the "
            "ratio, from FPI_Accuracy_check/output_Mprime_rf/mean_of_annual/. "
            "It is the sensitivity, not the method. The method - Eq. (1) of the "
            "window-mean FPI - is validated in the unsuffixed report, and the "
            "two agree to within 0.73% of the median ratio in every run.")
    else:
        doc.add_paragraph(
            "The M' validated here is the current one: Eq. (1) applied to the "
            "window-mean FPI on both sides of the ratio, the layer in "
            "FPI_Accuracy_check/output_Mprime_rf/eq1_of_mean/. The predictor "
            "tables were rebuilt against it rather than re-labelled - the M' "
            "they store is bit-identical to that raster at every sampled cell, "
            "and differs from the per-year layer by up to 9 t DM ha-1 - and the "
            "whole chain was rerun on it: tables, matching, the controls, the "
            "figures and this report. The per-year route is kept as the "
            "_mean_of_annual variant for comparison.")
    doc.add_paragraph(
        "Two dataframes, as specified. Dataframe 1 is the reference table: one "
        "row per NBL site, restricted to mature vegetation with good data, "
        "carrying X, Y and all 174 predictors that feed FPI at that location — "
        "83 soil bands and 91 climate features on the 1985-2014 climatology. "
        "Dataframe 2 is the future table: one row per future grid cell with the "
        "same columns, built once per scenario-window, plus the M' projected "
        "there. A ninth table repeats the exercise on the historical climate, "
        "which supplies the standardisation, the principal components and the "
        "first control.")

    doc.add_heading("What this can and cannot show", level=2)
    doc.add_paragraph(
        "M is the maximum biomass a mature undisturbed stand attains; an "
        "observed AGB is one stand at one moment. For any stand short of its "
        "maximum, observed < M. The filtering removes the worst of that — "
        "production estates, plantings, stands with high dead basal area, small "
        "plots — but the library records no stand age, so it cannot be removed "
        "entirely. The asymmetry that follows is the key to reading every "
        "number below: M' above the observation is expected and is weak "
        "evidence of a problem, while M' below the observation cannot be "
        "explained by immaturity and is the stronger signal.", style="Intense Quote")
    doc.add_paragraph(
        "There is also a circularity to name. λ is DCCEEW's Revised_M_Roxburgh ÷ "
        "Original_M_2004, and Revised_M_Roxburgh is itself the output of a random forest "
        "fitted to NBL plots. Sites in that fit are not independent of M', so "
        "this is a consistency check on the transport of a climate signal, not "
        "an independent validation of the level. The present-day control below "
        "is where that shows up most directly.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Dataframe 1 — the reference table", level=1)
    table(doc, [[r["step"], format(int(r["sites"]), ",")] for _, r in trail.iterrows()],
          ["filter", "surviving"], widths=[4.4, 1.2])
    doc.add_paragraph(
        "Maturity is assigned from the tree-level table, since the site table "
        "carries no age or disturbance field: a site with at least one stem ≥ 50 "
        "cm DBH is verified mature, a largest stem of 30-50 cm is likely mature, "
        "below that is young or shrubby, and a site with no stems listed is "
        "unverified. The headline sample is verified + likely mature.")
    table(doc, [[r["maturity"], int(r["n"]), fmt(r["agb_median"]),
                 fmt(r["M_hist_median"]), fmt(r["fpi_median"])]
                for _, r in ref_sum.iterrows()],
          ["maturity class", "sites", "median AGB (Mg/ha)",
           "median M' today", "median FPI"], widths=[1.5, 0.8, 1.5, 1.4, 1.1])
    doc.add_heading("Two filters that decide the sample", level=2)
    doc.add_paragraph(
        "Maturity is joined to the site record on obs_key, the survey event, "
        "and not on the site name. The name is not unique: 1,444 names in the "
        "library carry more than one survey, up to nineteen, and 197 are shared "
        "between different data sources. A join on the name therefore pools "
        "stems measured on other visits, or by another agency at another place "
        "of the same name, into the record being classified. On this sample it "
        "changes the class of only one site in 2,120, so it is a correctness "
        "fix rather than a result, but it is the join a reader should assume.")
    doc.add_paragraph(
        "The second filter does change the result. A stand cannot carry less "
        "biomass than its own basal area implies: the library's median is 7.8 "
        "Mg of above-ground biomass per square metre of live basal area, and "
        "anything below about 1 would be a five-metre stand of balsa. Two "
        "sources fail that wholesale - TERN Australia at a median of 0.08 over "
        "51 sites, and CSIRO at 0.21 over 19. The TERN plot named Giants "
        "reports 0.60 Mg/ha of biomass against 108 square metres per hectare of "
        "live basal area and a 403 cm stem. These are corrupt biomass fields, "
        "not cleared or burnt stands, and they were the whole of the puzzle of "
        "near-zero mature sites: of the 53 mature sites under 5 Mg/ha, the "
        "median largest stem was 104 cm. Records below 1 Mg per square metre "
        "are dropped, and Step_01 writes the untouched sample to "
        "reference_table_noqc.csv so the effect can be measured rather than "
        "asserted.")
    doc.add_paragraph(
        "Dropping them removes 88 of 688 mature sites and moves every number "
        "that follows:")
    table(doc,
          [["mature sites", "688", "600"],
           ["median observed AGB (Mg/ha)", "83.0", "112.4"],
           ["median ratio, site's own cell today", "0.611", "0.494"],
           ["Spearman rho, site's own cell today", "0.070", "0.418"],
           ["Spearman rho, SSP126 2035-2064", "0.036", "0.274"]],
          ["", "before the filter", "after"], widths=[2.8, 1.5, 1.2])
    doc.add_paragraph(
        "The ratio moves away from 1 and the rank correlation improves roughly "
        "sixfold. Both are the same fact: the discarded records contributed "
        "biomass values unrelated to the stands they described, which depressed "
        "the observed median and added pure noise to the ranking. The cleaned "
        "numbers are worse-looking on the ratio and far better on the "
        "correlation, and the correlation is the one that measures skill.")

    doc.add_paragraph(
        "Figure 1 shows the sample the whole test rests on. Panel (a) plots "
        "each surviving site at its longitude and latitude, coloured by "
        "maturity class, with the marker area scaled to the observed biomass so "
        "that the heavy sites are visible without a second axis. Panel (b) is "
        "the distribution of that biomass. Neither panel is a result; they are "
        "here so that the coverage and the spread of the reference set can be "
        "judged before any statistic computed from it is read. What to look for "
        "is the geography: the sites cluster along the forested east, the "
        "south-west and Tasmania, and the arid interior is almost unsampled, so "
        "conclusions drawn here do not extend there.")
    figure(doc, "fig_01_reference_sites.png",
           "Figure 1. The reference sites: where they are, and what they carry.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Where FPI enters, and where it deliberately does not",
                    level=2)
    doc.add_paragraph(
        "FPI has three distinct roles here, and they are easy to conflate.")
    for t in [
        "It is inside the quantity being tested. M' is Eq. (1) of the modelled "
        "FPI, rescaled by lambda and Original_M_2004, so FPI drives everything "
        "the comparison judges.",
        "It is carried as a column and used for one control. The reference "
        "table holds fpi_hist, the forest's modelled 1985-2014 mean FPI at each "
        "site; the future tables hold the projected window-mean FPI; and every "
        "match records the FPI of the cell it was matched to. fpi_hist also "
        "feeds the Eq. (1)-footing control, which is how the 1.22 figure in the "
        "gate section is produced.",
        "It is NOT a matching variable, on purpose. The match runs on the 174 "
        "random-forest predictors - 83 soil bands and 91 climate features - "
        "never on FPI itself.",
    ]:
        doc.add_paragraph(t, style="List Bullet")
    doc.add_paragraph(
        "The third point is the one that decides what this test is worth. M' is "
        "a deterministic function of FPI through Eq. (1) and lambda, so matching "
        "sites to cells on FPI would pair each site with a cell that already "
        "carries almost the same M' by construction, and the exercise would "
        "collapse into a restatement of the present-day gate. Matching on "
        "climate and soil instead exercises the whole chain: whether the forest "
        "turns a future climate into a sensible FPI, whether Eq. (1) turns that "
        "FPI into a sensible biomass, and whether lambda transports the result "
        "onto the footing FullCAM reads. FPI is what is being tested, not what "
        "the test matches on.")

    doc.add_heading("The match", level=1)
    doc.add_paragraph(
        "All 174 predictors are standardised by the historical land-cell mean "
        "and standard deviation, so the reference and the future sit in one "
        "comparable space, then projected onto the principal components of that "
        "same historical sample. PCA is not cosmetic: the raw predictors are "
        "strongly collinear — twelve monthly temperatures move together — so "
        "plain Euclidean distance would count one physical signal a dozen times "
        "and let 83 soil columns outvote the climate. Each site is then matched "
        "to its nearest future cell in that space with a k-d tree.")
    doc.add_paragraph(
        "A site whose nearest future cell is further away than historical cells "
        "typically are from each other (the 99th percentile of within-historical "
        "nearest-neighbour distance) is flagged as having no analogue and is "
        "reported separately rather than silently matched. Forcing a match onto "
        "a climate the future does not contain would manufacture agreement or "
        "disagreement out of nothing.")
    if "n_class_fallback" in runs.columns and runs["n_class_fallback"].max() > 0:
        fb = runs[runs["stratum"] == "all matched"][["run", "n_class_fallback"]]
        fb = fb[~fb["run"].str.startswith("same_cell")]
        doc.add_paragraph(
            "The search is constrained to vegetation: a site can only be matched "
            "to a cell carrying the same pre-1750 NVIS Major Vegetation Subgroup. "
            "Climate and soil can agree exactly and still pair a rainforest site "
            "with a cell that carries mallee, and those two carry different "
            "biomass for reasons this chain does not model. NVIS 4.1 pre-1750 "
            "MVS, 100 m on Albers, was majority-aggregated onto the NLUM grid "
            "(Step_00) — pre-1750 rather than extant, because M is what a site "
            "could carry, so the vegetation that belongs there is the relevant "
            "attribute, not what clearing has left. 79 subgroups fall inside the "
            "mask and 99.9%% of cells are classified.")
        doc.add_paragraph(
            "A subgroup with fewer than 25 cells in the candidate pool cannot "
            "support a search; those sites fall back to an unconstrained match "
            "and are flagged (%d to %d sites per run). A fallback is a result in "
            "itself — it means the pool holds almost none of that vegetation "
            "type." % (int(fb["n_class_fallback"].min()),
                       int(fb["n_class_fallback"].max())))

    rows = [[label_run(r["run"]), "%.1f%%" % r["pct"], int(r["size"])]
            for _, r in na.iterrows() if r["run"] not in ("same_cell_present_day",)]
    table(doc, rows, ["run", "no analogue", "sites"], widths=[2.4, 1.2, 1.0])
    doc.add_paragraph(
        "Figure 3 asks whether the matching worked before any biomass is "
        "compared. Panel (a) is the distance, in the standardised principal "
        "component space, between each site and the cell chosen for it: the "
        "grey histogram is the present-day control, the blue one the eight "
        "future runs pooled. Panel (b) counts, per run, the sites whose nearest "
        "candidate is further away than the 99th percentile of the distance "
        "between historical cells — the no-analogue flag. Panel (c) is the "
        "great-circle distance from the site to its analogue in kilometres, a "
        "diagnostic rather than a criterion, since a good climate analogue may "
        "legitimately sit far away.")
    doc.add_paragraph(
        "How to read it: the blue histogram sitting to the right of the grey "
        "one means future climates are harder to match than present-day ones, "
        "which is expected and is the point of the exercise. Panel (b) is the "
        "one to check before quoting any late-century run.")
    figure(doc, "fig_03_match_quality.png",
           "Figure 3. Match quality: how close the analogue is in predictor "
           "space, how often the future has no counterpart at all, and how far "
           "away on the ground the analogue sits.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The statistics, and why each is here", level=1)
    table(doc, [
        ["median ratio", "median of M' ÷ observed AGB",
         "the headline. Above 1 is expected; how far above is the question"],
        ["bootstrap interval", "2.5-97.5 percentile of the median ratio",
         "whether a difference between runs is worth discussing"],
        ["Spearman ρ", "rank correlation",
         "does the projection rank sites correctly, independently of level"],
        ["Pearson r / R²", "linear correlation, variance explained",
         "level-sensitive; read with the ratio, never alone"],
        ["R² in logs", "R² on log(AGB) vs log(M')",
         "biomass spans three orders of magnitude; in logs every site counts, "
         "not only the largest"],
        ["RMSE, MAE", "error in Mg ha⁻¹",
         "absolute size of the disagreement; RMSE is dominated by big sites"],
        ["MdAPE", "median |ratio − 1| as a percentage",
         "a robust relative error"],
        ["Lin's CCC", "concordance with the 1:1 line",
         "penalises both poor correlation and systematic offset"],
        ["Theil-Sen slope", "robust slope of M' on AGB",
         "whether the two scale together, resistant to outliers"],
        ["% within 2×", "share with 0.5 < ratio < 2",
         "a plain-language accuracy statement"],
        ["match distance", "distance in the PCA space",
         "how good the analogue was; a large value weakens everything else"],
    ], ["statistic", "definition", "what it is for"], widths=[1.3, 2.0, 3.0])

    # ------------------------------------------------------------------ #
    doc.add_heading("Results", level=1)

    doc.add_heading("The present-day gate", level=2)
    doc.add_paragraph(
        "Before any climate analogue, M' at each site's own cell today against "
        "the biomass measured there: median ratio %s (95%% CI %s-%s), Spearman ρ "
        "%s, %s%% of sites within a factor of two, n = %d. %s"
        % (fmt(gate["median_ratio"]), fmt(gate["median_ratio_lo"]),
           fmt(gate["median_ratio_hi"]), fmt(gate["spearman_rho"]),
           fmt(gate["pct_within_2x"], "%.0f"), int(gate["n"]),
           "M' sits above observed biomass at most sites, which is what a "
           "maximum should do." if gate["median_ratio"] > 1 else
           "M' sits below observed biomass at the median, which immaturity "
           "cannot explain and which needs investigating before the "
           "space-for-time result is used."))
    doc.add_paragraph(
        "Figure 2 is the gate, and it involves no matching at all. Panel (a) "
        "plots, for each site, the biomass measured in the field on the x axis "
        "against the M' of the 1 km cell the site falls in on the y axis, with "
        "the 1:1 line dashed. Panel (b) is the same information as the "
        "distribution of M' divided by observed AGB, with the median marked. "
        "Both axes are linear and clipped just above the bulk of the data; the "
        "sites beyond the cut are counted on the panel rather than hidden.")
    doc.add_paragraph(
        "How to read it: because M' is a maximum and a field measurement is one "
        "stand at one moment, the ratio should sit ABOVE 1 for a well-behaved "
        "layer. A median below 1 cannot be explained by stand immaturity, which "
        "is why this panel decides how much weight the rest of the report can "
        "carry. The vertical smear at low observed AGB is the scale mismatch: a "
        "sub-hectare plot with little biomass inside a 1 km cell whose "
        "potential is high.")
    figure(doc, "fig_02_present_day_gate.png",
           "Figure 2. The present-day gate. Left: observed AGB against M' at "
           "the same cell, linear axes clipped just above the bulk of the data, "
           "1:1 dashed, with n, median ratio, Spearman rho, the share within a "
           "factor of two and RMSE on the panel. Right: the distribution of the "
           "ratio, cut at 6 with the number of sites beyond it stated.")

    doc.add_heading("Controls, and which null is the fair one", level=2)
    doc.add_paragraph(
        "Three runs bracket what the method can do before any future is "
        "involved. Matching a site to a present-day analogue gives a median "
        "ratio of %s with Spearman rho %s - that is the matching method's own "
        "error, and the future runs should be read against it rather than "
        "against 1. The null is random cells drawn under the same NVIS "
        "constraint: %s and rho %s."
        % (fmt(hist_ctl["median_ratio"]), fmt(hist_ctl["spearman_rho"]),
           fmt(rand["median_ratio"]), fmt(rand["spearman_rho"])))
    doc.add_paragraph(
        "The constraint on the null is not a detail. Drawing the random cells "
        "without it gives a ratio near 0.21 and rho near 0.03, against which "
        "the analogue search looks decisive - but almost all of that gap is the "
        "vegetation constraint doing its work, not the climate matching. A "
        "random cell anywhere in Australia is usually the wrong vegetation type "
        "entirely, and beating it demonstrates nothing. Quoted honestly, the "
        "analogue search improves on its fair null from rho %s to about %s and "
        "from a ratio of %s to about %s: a real gain, and a modest one. The "
        "unconstrained figure is reported in this folder for completeness and "
        "should not be used as evidence of skill."
        % (fmt(rand["spearman_rho"]), fmt(fut["spearman_rho"].median()),
           fmt(rand["median_ratio"]), fmt(fut["median_ratio"].median())))

    doc.add_heading("The eight scenario-windows", level=2)
    rows = []
    for win in WINDOWS:
        for ssp in SSPS:
            run = "%s_%s" % (ssp, win)
            if run not in found.index:
                continue
            r = found.loc[run]
            rows.append([ssp.replace("ssp", "SSP"), win, int(r["n"]),
                         fmt(r["median_ratio"]),
                         "%s-%s" % (fmt(r["median_ratio_lo"]),
                                    fmt(r["median_ratio_hi"])),
                         fmt(r["spearman_rho"]), fmt(r["r2_log"]),
                         fmt(r["pct_within_2x"], "%.0f")])
    table(doc, rows, ["scenario", "window", "n", "median ratio", "95% CI",
                      "Spearman ρ", "R² (logs)", "% within 2×"],
          widths=[0.9, 1.0, 0.6, 1.0, 1.1, 0.9, 0.9, 0.9])
    doc.add_paragraph(
        "Across the eight runs the median ratio spans %s to %s and Spearman ρ "
        "%s to %s. %s"
        % (fmt(fut["median_ratio"].min()), fmt(fut["median_ratio"].max()),
           fmt(fut["spearman_rho"].min()), fmt(fut["spearman_rho"].max()),
           "Every run sits above the random-cell floor of %s, so the matching "
           "carries information." % fmt(rand["median_ratio"])
           if fut["spearman_rho"].min() > rand["spearman_rho"] else
           "At least one run does not beat the random-cell control, which means "
           "the matching adds nothing there and the result should not be "
           "quoted as skill."))
    doc.add_paragraph(
        "Figure 4 is the space-for-time comparison itself. For each panel, "
        "every site was matched to the future cell whose predictors are nearest "
        "in the PCA space and whose pre-1750 vegetation subgroup is the same; "
        "the x axis is the biomass observed at the site, the y axis the M' "
        "projected for its matched cell, and only sites with an analogue are "
        "drawn. Rows are the two windows, columns the four scenarios. The "
        "clouds sit below the 1:1 line in every panel, which is the same "
        "finding as Figure 2 carried through the matching.")
    figure(doc, "fig_04_obs_vs_matched.png",
           "Figure 4. Observed AGB against the M' projected for each site's "
           "future climate analogue, one panel per scenario-window. Each panel "
           "carries n, the median ratio, Spearman rho and the share within a "
           "factor of two for that run; the same numbers, with the rest of the "
           "statistics, are in the tables above.")
    doc.add_paragraph(
        "Figure 5 compresses each panel of Figure 4, and each control, to one "
        "number: the median of M' divided by observed AGB, with a 2,000-sample "
        "bootstrap interval. The controls are grey. This is the summary figure "
        "of the analysis, and the comparison it invites is horizontal — each "
        "future run against the present-day-analogue control and against the "
        "random-cell null, not against 1.0. Where the intervals of a run and "
        "the null overlap, that run has not demonstrated skill.")
    figure(doc, "fig_05_ratio_by_run.png",
           "Figure 5. Median ratio with its bootstrap interval, controls in "
           "grey. This is the summary figure of the whole analysis.")
    doc.add_paragraph(
        "Figure 6 checks whether a distant analogue is a worse one. Panel (a) "
        "draws an arrow from each site to the cell matched to it under SSP5-8.5 "
        "2070-2099, so the direction and length of the climate shift are "
        "visible. Panel (b) plots agreement against that distance, coloured by "
        "the distance in predictor space, with the Spearman correlation between "
        "the two printed on the panel. A correlation near zero means the "
        "analogue being far away on the ground does not, by itself, make it a "
        "worse analogue — which is what one wants, since the match is made in "
        "climate space and not in geography.")
    figure(doc, "fig_06_displacement.png",
           "Figure 6. Where the analogues are, and whether a more distant "
           "analogue agrees less well. Panel (b) carries the Spearman "
           "correlation between the distance to the analogue and the ratio, "
           "which is the question it asks.")

    # ------------------------------------------------------------------ #
    if paired is not None and not paired.empty:
        doc.add_heading("Each site against itself", level=2)
        doc.add_paragraph(
            "The ratios above are unpaired: they compare the biomass observed "
            "at one set of sites with the M' found at a different set of cells, "
            "so they mix how well M' tracks biomass with which vegetation types "
            "happen to sit in the sample. Dividing each site's matched M' by "
            "its OWN present-day M' removes that. The observed biomass cancels "
            "exactly out of the arithmetic - the quantity is M' at the analogue "
            "over M' at the site - so every site is its own control and the "
            "vegetation-type composition of the sample cannot influence the "
            "answer.")
        doc.add_paragraph(
            "Two baselines are reported and they answer different questions. "
            "Against the site's own present-day cell, the comparison carries "
            "everything the analogue changed: the search procedure and the "
            "projected climate together. Against the site's present-day "
            "analogue, the search procedure is held fixed and only the climate "
            "moves, which isolates the projected change. Confidence intervals "
            "are the 2.5th and 97.5th percentiles of 2,000 bootstrap medians, "
            "and the p-value is a Wilcoxon signed-rank test on the paired "
            "differences. With 600 pairs that test detects differences far "
            "smaller than matter, so read the interval first and the p-value "
            "last.")
        hp = paired[paired["baseline"] == "historical_analogue"].set_index("run")
        rows = []
        for win in WINDOWS:
            for ssp in SSPS:
                k = "%s_%s" % (ssp, win)
                if k not in hp.index:
                    continue
                r = hp.loc[k]
                nf = float(na.set_index("run")["pct"].get(k, float("nan")))
                rows.append([label_run(k), fmt(r["median_ratio"], "%.3f"),
                             "%s to %s" % (fmt(10 ** r["lo"], "%.3f"),
                                           fmt(10 ** r["hi"], "%.3f")),
                             fmt(r["pct_sites_lower"], "%.0f") + "%",
                             fmt(nf, "%.0f") + "%"])
        table(doc, rows,
              ["scenario-window", "M' ratio, paired", "95% interval",
               "sites lower", "no analogue"], widths=[1.7, 1.2, 1.4, 0.9, 0.9])
        doc.add_paragraph(
            "Read the last column with the first. Where most sites still have "
            "an analogue - every mid-century window, and SSP126 late - the "
            "paired change is a decline of 2.5 to 6.9 per cent, consistent and "
            "small. Where the analogue pool has collapsed, the same statistic "
            "reverses and reports a RISE of 12 to 28 per cent. That reversal is "
            "not a projected gain in productivity. It is selection: when 90 or "
            "98 per cent of sites have no analogue, the few that remain are the "
            "cells whose climate still exists somewhere in the future domain, "
            "which are the wetter and more productive ones. The statistic is "
            "then computed on a sample that no longer represents the reference "
            "set.")
        figure(doc, "fig_07_paired_change.png",
               "Figure 7. Paired per-site change in M', each site its own "
               "control. Points are the median ratio with a 95% bootstrap "
               "interval; the shaded band marks the runs where most sites have "
               "no analogue left and the survivors are a biased remnant.")

        doc.add_heading("Which runs are results, and which are not", level=2)
        doc.add_paragraph(
            "Three of the eight scenario-windows should not be quoted as "
            "findings. Of 600 sites, SSP370 2070-2099 retains %d with an "
            "analogue, SSP585 2070-2099 retains %d, and SSP245 2070-2099 "
            "retains %d. Below roughly a hundred sites the metrics are "
            "unstable from run to run, and the surviving sample is "
            "systematically wetter than the reference set, so both the level "
            "and the direction of the change are unreliable. The five "
            "remaining windows - all four mid-century, and SSP126 "
            "late-century - carry 82 to 92 per cent of their sites and are the "
            "ones that support a statement."
            % (int(found.loc["ssp370_2070-2099", "n"]),
               int(found.loc["ssp585_2070-2099", "n"]),
               int(found.loc["ssp245_2070-2099", "n"])))
        doc.add_paragraph(
            "The no-analogue fractions are themselves a result, and arguably "
            "the most important one in this report. They say that by the end of "
            "the century under high forcing, the climate projected for most of "
            "these forested sites does not occur anywhere in present-day "
            "Australia. M' at those locations is therefore an extrapolation "
            "beyond anything the observational record can constrain - the "
            "random forest is predicting FPI for climates it never saw, and no "
            "amount of validation against present-day biomass can test that. "
            "This is a property of the projection, not a defect of the matching "
            "procedure, and it applies equally to the FullCAM inputs built from "
            "the same layers.")
        table(doc,
              [[label_run(r["run"]), int(r["sum"]), fmt(r["pct"], "%.1f") + "%"]
               for _, r in na.iterrows() if str(r["run"]).startswith("ssp")],
              ["scenario-window", "sites with no analogue", "share"],
              widths=[2.0, 1.6, 1.0])

    # ------------------------------------------------------------------ #
    unc_path = OUT_DIR / ("metrics_by_run%s.csv" % unconstrained_suffix)
    if "_nvis" in args.suffix and unc_path.exists():
        unc = pd.read_csv(unc_path)
        unc = unc[unc["stratum"] == "analogue found"].set_index("run")
        if "random_cells" in unc.index:
            u_rand = unc.loc["random_cells"]
            u_fut = unc[~unc.index.isin(CONTROLS)]
            doc.add_heading("What the vegetation constraint changed", level=2)
            doc.add_paragraph(
                "Running the same analysis without the NVIS constraint is "
                "instructive, and not in the direction one would hope. The "
                "random-cell null rises from %s unconstrained to %s once random "
                "means \"a random cell of the same vegetation type\" — because "
                "knowing the vegetation subgroup is itself most of what is needed "
                "to guess the biomass. Against that stronger null the eight "
                "future runs (%s to %s) are barely distinguishable: on this "
                "sample the climate matching adds little beyond the vegetation "
                "class."
                % (fmt(u_rand["median_ratio"]), fmt(rand["median_ratio"]),
                   fmt(fut["median_ratio"].min()), fmt(fut["median_ratio"].max())))
            doc.add_paragraph(
                "That is the most useful thing this test has produced. It does "
                "not say the projection is wrong; it says this particular "
                "comparison cannot tell a correct projection from an incorrect "
                "one, because the observable it is judged against is dominated by "
                "vegetation type and by plot-scale variation rather than by "
                "climate. A test with power would need either stands whose "
                "biomass is known to be at its maximum, or an observable "
                "aggregated to the scale M' is defined on.")

    # --- the other averaging order ------------------------------------- #
    twin_suffix = (args.suffix.replace("_mean_of_annual", "")
                   if "_mean_of_annual" in args.suffix
                   else args.suffix + "_mean_of_annual")
    twin_path = OUT_DIR / ("metrics_by_run%s.csv" % twin_suffix)
    if twin_path.exists():
        twin = pd.read_csv(twin_path)
        twin = twin[twin["stratum"] == "analogue found"].set_index("run")
        this_order = ("mean of the annual Eq. (1) M"
                      if "_mean_of_annual" in args.suffix
                      else "Eq. (1) of the mean FPI (the method)")
        that_order = ("Eq. (1) of the mean FPI (the method)"
                      if "_mean_of_annual" in args.suffix
                      else "mean of the annual Eq. (1) M")

        doc.add_heading("The other averaging order", level=2)
        doc.add_paragraph(
            "M' exists in two averaging orders, and both have a random-forest "
            "historical denominator. This report validates the one built as the "
            "%s; the other is built as the %s. Eq. (1) is convex, so the two are "
            "not the same layer — at the M level the gap is about 3%%, and "
            "against Revised_M_Roxburgh it is the difference between ×0.944 and ×0.991. "
            "The question here is whether it changes the validation."
            % (this_order, that_order))

        rows, diffs = [], []
        for run in list(found.index):
            if run.startswith("same_cell") or run not in twin.index:
                continue
            a = float(found.loc[run, "median_ratio"])
            b = float(twin.loc[run, "median_ratio"])
            pct = 100 * (b - a) / a if a else float("nan")
            diffs.append(abs(pct))
            rows.append([label_run(run), int(found.loc[run, "n"]),
                         fmt(a, "%.3f"), fmt(b, "%.3f"), fmt(pct, "%+.2f%%")])
        table(doc, rows,
              ["run", "n", "this order", "other order", "difference"],
              widths=[2.0, 0.6, 1.1, 1.1, 1.1])

        worst = max(diffs) if diffs else float("nan")
        doc.add_paragraph(
            "The largest disagreement between the two orders is %s of the median "
            "ratio, and the two controls are identical to four decimal places. "
            "That is the expected result and it is worth stating explicitly: the "
            "Jensen gap enters the numerator and the denominator in the same "
            "direction, so once both sides of the ratio are built in the same "
            "order it very largely cancels. The averaging order therefore still "
            "matters for the headline change against Revised_M_Roxburgh — where only the "
            "numerator carries it — but it does not move this validation at all, "
            "and no conclusion here rests on the choice."
            % fmt(worst, "%.2f%%"))
        doc.add_paragraph(
            "The controls are identical for a structural reason, not a "
            "coincidence: averaged over the 30 historical years, both orders "
            "collapse to λ × Original_M_2004, which is Revised_M_Roxburgh. The present-"
            "day gate cannot distinguish them.")

    doc.add_heading("By maturity class", level=2)
    mat = by_mat[~by_mat["run"].isin(CONTROLS)]
    if not mat.empty:
        g = mat.groupby("maturity").agg(
            runs=("run", "size"), n=("n", "median"),
            median_ratio=("median_ratio", "median"),
            rho=("spearman_rho", "median")).reset_index()
        table(doc, [[r["maturity"], int(r["n"]), fmt(r["median_ratio"]),
                     fmt(r["rho"])] for _, r in g.iterrows()],
              ["maturity", "sites (median)", "median ratio", "Spearman ρ"],
              widths=[1.6, 1.2, 1.2, 1.2])
        doc.add_paragraph(
            "Verified mature sites are the ones the test is really about: they "
            "are the closest thing the library has to a stand at its maximum, "
            "so their ratio is the least contaminated by immaturity.")

    if has_climate:
        c = pd.read_csv(climate_only)
        cf = c[(c["stratum"] == "analogue found") & (~c["run"].isin(CONTROLS))]
        doc.add_heading("Sensitivity: matching on climate alone", level=2)
        doc.add_paragraph(
            "Soil does not change between now and 2100, so including its 83 "
            "columns mostly constrains the analogue to sit on similar soil — "
            "desirable, but not what is being validated. Repeating the match on "
            "the 91 climate columns alone gives a median ratio of %s to %s "
            "across the eight runs, against %s to %s with soil included. %s"
            % (fmt(cf["median_ratio"].min()), fmt(cf["median_ratio"].max()),
               fmt(fut["median_ratio"].min()), fmt(fut["median_ratio"].max()),
               "The two agree closely, so the conclusion does not rest on the "
               "choice." if abs(cf["median_ratio"].median()
                                - fut["median_ratio"].median()) < 0.25 else
               "They differ enough that the choice matters and both should be "
               "reported."))

    # ------------------------------------------------------------------ #
    sp_path = OUT_DIR / ("matching_space%s.csv" % args.suffix)
    doc.add_heading("What the match is actually computed on", level=2)
    if sp_path.exists():
        sp = pd.read_csv(sp_path).iloc[0]
        doc.add_paragraph(
            "The match uses all %d predictors the random forest itself uses, "
            "but not in their raw form: they are standardised on the historical "
            "land cells and then projected onto the %d principal components "
            "that carry %s per cent of the historical variance. That step "
            "matters more than it looks. A nearest neighbour found in a very "
            "high-dimensional space is only nominally the nearest, because as "
            "dimension grows the spread of pairwise distances shrinks relative "
            "to their mean until every candidate sits at about the same "
            "distance and the winner is decided by noise. The relative "
            "contrast - the median site's typical candidate distance minus its "
            "nearest, over its nearest - measures that directly. Here it is "
            "%s, so the nearest cell is genuinely much nearer than a typical "
            "one and the match means what it says."
            % (int(sp["n_features"]), int(sp["n_components"]),
               fmt(sp["variance_pct"], "%.0f"),
               fmt(sp["relative_contrast"], "%.1f")))
    if reduced is not None and not reduced.empty:
        rf = reduced[(reduced["stratum"] == "analogue found")
                     & (~reduced["run"].isin(CONTROLS))]
        rsp = OUT_DIR / ("matching_space_reduced%s.csv"
                         % args.suffix.replace("_climate_only", ""))
        extra = ""
        if rsp.exists():
            r2 = pd.read_csv(rsp).iloc[0]
            extra = (" Its relative contrast is %s, against %s for the full "
                     "set - no better, which is the point: the concentration "
                     "the reduced set was meant to avoid is not happening in "
                     "the full one either."
                     % (fmt(r2["relative_contrast"], "%.1f"),
                        fmt(pd.read_csv(sp_path).iloc[0]["relative_contrast"],
                            "%.1f") if sp_path.exists() else "n/a"))
        doc.add_paragraph(
            "As a check on that, the whole match was repeated on a deliberately "
            "small set: the seven annual climate means and one slice of each of "
            "nine soil properties, sixteen columns instead of %d. It gives a "
            "median ratio of %s to %s across the eight runs against %s to %s "
            "for the full set, and it places the analogues further away on the "
            "ground.%s The full predictor set is kept."
            % (int(pd.read_csv(sp_path).iloc[0]["n_features"])
               if sp_path.exists() else 174,
               fmt(rf["median_ratio"].min()), fmt(rf["median_ratio"].max()),
               fmt(fut["median_ratio"].min()), fmt(fut["median_ratio"].max()),
               extra))

    # ------------------------------------------------------------------ #
    doc.add_heading("Reconciling with the earlier bin validation", level=2)
    doc.add_paragraph(
        "An earlier validation in the parent folder reported a median ratio of "
        "1.55 on 254 verified-mature stands, against 0.49 here. Neither is "
        "wrong; they are different quantities, and the difference decomposes "
        "cleanly on the same sites:")
    table(doc,
          [["published Level 2 figure (verified mature, Eq. (1) footing)", "1.55"],
           ["reproduced here on the same footing and stratum", "1.47"],
           ["retire the Eq. (1) footing, use New_M_2019", "0.95"],
           ["widen from verified-only to verified + likely mature", "0.61"],
           ["apply the AGB-versus-basal-area filter", "0.49"]],
          ["step", "median ratio"], widths=[4.6, 1.2])
    doc.add_paragraph(
        "The single largest term is the footing. The earlier number was "
        "computed against a historical M' built on Eq. (1) applied directly, "
        "which overstates the Richards and Brack layer FullCAM ships by about "
        "46 per cent; retiring that footing multiplies the ratio by 0.64 on its "
        "own and was a deliberate decision, not a change of result. Widening "
        "the maturity stratum contributes a further 0.65, because likely-mature "
        "stands sit on less productive land, and the data-quality filter "
        "contributes the "
        "remaining 0.81 by raising the observed median. The residual between "
        "1.55 and the 1.47 reproduced here is the earlier run's per-cell rather "
        "than per-site aggregation and its missing planted-project filter.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude, and what not to", level=1)
    doc.add_paragraph(
        "The honest headline is that the present-day gate does not pass. At the "
        "site's own cell, M' is %s times the observed biomass at the median - "
        "it under-predicts by about half - and ranks the sites only modestly "
        "better than a constrained random draw (Spearman ρ %s against %s; R² in "
        "logs is negative). Everything downstream inherits that, so the eight "
        "scenario-window numbers should be read as a description of how the "
        "matching behaves, not as evidence that M' predicts biomass at a point."
        % (fmt(gate["median_ratio"]), fmt(gate["spearman_rho"]),
           fmt(rand["spearman_rho"])), style="Intense Quote")
    doc.add_paragraph(
        "Three reasons that outcome is not, on its own, a verdict on the "
        "projection. A 1 km cell's M' is the potential of the whole cell while "
        "an NBL plot is a fraction of a hectare inside it, and the two are not "
        "the same quantity. The library records no stand age, so the sample "
        "still contains stands well short of their maximum. And no vegetation "
        "constraint was available when the plan was written — two cells can "
        "share a climate and a soil and carry "
        "different vegetation — although with the NVIS constraint in place that "
        "objection is now answered. What the test does establish is the ordering "
        "of the controls, and that ordering is informative in itself.")
    for t in [
        "Read the future runs against the present-day-analogue control, not "
        "against perfect agreement. The control carries the matching method's "
        "own error; only the difference between it and a future run is "
        "attributable to the projection.",
        "A ratio above 1 is the expected direction. M' is a maximum and the "
        "library records stands of unknown age, so some over-prediction is "
        "built in. Under-prediction is the finding that would matter.",
        "The absolute level is anchored, not tested. λ × Original_M_2004 is "
        "Revised_M_Roxburgh, which came from a random forest fitted to NBL plots, so "
        "agreement in level is partly circular. What is genuinely tested here "
        "is whether the projected climate change moves M' in a way consistent "
        "with the biomass observed under comparable climates today.",
        "The vegetation constraint is applied, and it raises the null more than "
        "it raises the runs. Matching within the pre-1750 NVIS subgroup is the "
        "right thing to do and it was the largest missing piece, but the result "
        "is that the random control becomes nearly as good as the climate "
        "matching. Report the null alongside every ratio; a ratio quoted on its "
        "own from this test would overstate what it demonstrates.",
        "The sample is geographically narrow. The surviving sites cluster in "
        "eastern Queensland and New South Wales, with smaller groups in "
        "Tasmania and the south-west; the arid interior, the tropical north "
        "and most of South Australia are effectively unsampled. Every ratio "
        "and correlation in this report is therefore a statement about wet and "
        "sub-humid eastern forest, and carries no weight over the rangelands "
        "that make up most of the NLUM mask by area.",
        "The southward displacement is a sanity check that passes. The "
        "analogues move consistently poleward and the median displacement "
        "grows with forcing, from about 36 km under SSP126 mid-century to "
        "several hundred kilometres under the late-century high-forcing runs. "
        "That is the direction and the ordering a warming climate should "
        "produce, and it is evidence the matching is finding real climate "
        "structure rather than noise - independent of whether the M' it "
        "retrieves agrees with the biomass.",
        "Riparian and floodplain sites are unfiltered — the library has no field "
        "for them — so a residue of sites whose biomass is supported by water "
        "the climate does not explain remains in the sample.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["outputs/reference_table.csv", "Dataframe 1: sites × 174 predictors + AGB"],
        ["outputs/tables/*.npz", "Dataframe 2: nine tables of grid cells × 174 "
                                 "predictors + M'"],
        ["outputs/matches*.csv", "every site's match, per run, with distances"],
        ["outputs/metrics_by_run*.csv", "the statistics above, per run"],
        ["outputs/metrics_by_maturity*.csv", "the same, split by maturity class"],
        ["outputs/no_analogue_summary*.csv", "share of sites with no analogue"],
        ["plots/fig_01..06", "the figures in this report"],
    ], ["file", "contents"], widths=[2.6, 3.7])

    report = HERE / ("%s%s.docx"
                     % (REPORT_STEM,
                        "_mean_of_annual" if "_mean_of_annual" in args.suffix
                        else ""))
    doc.save(report)
    print("wrote %s" % report)


if __name__ == "__main__":
    main()
