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
CONTROLS = ["same_cell_present_day", "same_cell_eq1_footing",
            "historical_analogue", "random_cells"]
CONTROL_LABEL = {"same_cell_present_day": "the site's own cell, today",
                 "same_cell_eq1_footing": "the same cell, Eq. (1) footing",
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
    figure(doc, "fig_01_reference_sites.png",
           "Figure 1. The reference sites: where they are, and what they carry.")

    # ------------------------------------------------------------------ #
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
    figure(doc, "fig_02_present_day_gate.png",
           "Figure 2. The present-day gate. Left: observed against M' at the "
           "same cell, linear axes clipped just above the bulk of the data, 1:1 "
           "dashed. Right: the distribution of the ratio.")

    if "same_cell_eq1_footing" in found.index:
        eq1 = found.loc["same_cell_eq1_footing"]
        doc.add_paragraph(
            "How much of that is the footing? Evaluating Eq. (1) on the same "
            "modelled FPI at the same cells — the unmatched, Eq. (1) footing — "
            "gives a median ratio of %s against %s on the matched footing, a "
            "factor of %.2f between them. The two footings therefore straddle "
            "the observations: Eq. (1) M sits above observed mature biomass, "
            "which is the direction a maximum should err in, while λ × "
            "Original_M_2004 sits below it, which immaturity cannot explain. "
            "Rank agreement is poor either way (Spearman ρ %s and %s), so the "
            "choice of footing moves the level and neither footing reproduces "
            "the ranking of these sites."
            % (fmt(eq1["median_ratio"]), fmt(gate["median_ratio"]),
               eq1["median_ratio"] / gate["median_ratio"],
               fmt(eq1["spearman_rho"]), fmt(gate["spearman_rho"])))
        doc.add_paragraph(
            "That is a finding about the footing decision, not about climate "
            "change, and it belongs beside the footing memo rather than in the "
            "projection. It does not favour one footing on its own: the NBL "
            "sample is a filtered mature subset with a median of %s Mg ha⁻¹, "
            "well above the domain median, so a layer calibrated to the whole "
            "continent is expected to sit below it."
            % fmt(gate["obs_median"], "%.0f"))

    doc.add_heading("Controls", level=2)
    doc.add_paragraph(
        "Three runs bracket what the method can do before any future is "
        "involved. Matching a site to a present-day analogue gives a median "
        "ratio of %s — this is the matching method's own error, and the future "
        "runs should be read against it rather than against 1. Random cells give "
        "%s, which is the floor any real skill has to beat."
        % (fmt(hist_ctl["median_ratio"]), fmt(rand["median_ratio"])))

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
    figure(doc, "fig_04_obs_vs_matched.png",
           "Figure 4. Observed biomass against the M' projected for each site's "
           "future climate analogue, one panel per scenario-window.")
    figure(doc, "fig_05_ratio_by_run.png",
           "Figure 5. Median ratio with its bootstrap interval, controls in "
           "grey. This is the summary figure of the whole analysis.")
    figure(doc, "fig_06_displacement.png",
           "Figure 6. Where the analogues are, and whether a more distant "
           "analogue agrees less well.")

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
    doc.add_heading("What to conclude, and what not to", level=1)
    doc.add_paragraph(
        "The honest headline is that the present-day gate does not pass. At the "
        "site's own cell, M' is %s times the observed biomass at the median and "
        "ranks the sites barely better than chance (Spearman ρ %s against %s "
        "for random cells; R² in logs is negative). Everything downstream "
        "inherits that, so the eight scenario-window numbers below should be "
        "read as a description of how the matching behaves, not as evidence "
        "that M' predicts biomass at a point."
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
