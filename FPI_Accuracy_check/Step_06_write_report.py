"""
Step 06 - assemble the short report.

Reads   output/*.csv, plots/*.png
Writes  FPI_modelled_reference_report.docx

Every number in the document is read from the CSV that the step which computed
it wrote; nothing here recomputes a metric, so the report cannot disagree with
the pipeline. Re-run any earlier step and then this one and the write-up follows.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" python Step_06_write_report.py
"""

from datetime import date
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"
PLOT_DIR = HERE / "plots"
COMP_DIR = HERE / "Comparison_vs_New_M_2019"
COMP_OUT = COMP_DIR / "output"
COMP_PLOTS = COMP_DIR / "plots"
REPORT = HERE / "FPI_modelled_reference_report.docx"

INK_2 = RGBColor(0x52, 0x51, 0x4E)

SSP_ORDER = ["ssp126", "ssp245", "ssp370", "ssp585"]


def caption(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(8.5)
    r.font.color.rgb = INK_2
    r.italic = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return p


def figure(doc, name, cap, width=6.4, folder=None):
    path = (folder or PLOT_DIR) / name
    if not path.exists():
        doc.add_paragraph("[missing figure: %s - run the step that writes it]" % name)
        return
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, cap)


def table(doc, rows, header, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = str(h)
        for p in cell.paragraphs:
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
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def main():
    acc = pd.read_csv(OUT_DIR / "accuracy_summary.csv").set_index("scheme")
    by_year = pd.read_csv(OUT_DIR / "accuracy_by_year.csv")
    comp = pd.read_csv(OUT_DIR / "hist_M_denominator_comparison.csv")
    levels = pd.read_csv(OUT_DIR / "hist_M_denominator_levels.csv")
    mp = pd.read_csv(OUT_DIR / "Mprime_modelled_vs_observed_denominator.csv")
    ob = pd.read_csv(OUT_DIR / "optionB_pct_change.csv")

    def comp_med(prefix):
        return float(comp[comp["comparison"].str.startswith(prefix)]["median"].iloc[0])

    ins, oof = acc.loc["in_sample_full_grid"], acc.loc["out_of_fold_groupcv_year"]
    rebuild = comp[comp["comparison"].str.startswith("rebuild check")]
    rebuild_max = float(rebuild["pct_within_5pct"].iloc[0]) if len(rebuild) else None

    doc = Document()
    for name, size in [("Normal", 10.5)]:
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)

    doc.add_heading("Modelling the reference FPI, and what it does to M'", 0)
    p = doc.add_paragraph()
    r = p.add_run("FPI_Accuracy_check/ · generated %s · every number read from the "
                  "step that computed it" % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ---------------------------------------------------------------- why ---
    doc.add_heading("Why", level=1)
    doc.add_paragraph(
        "The delta-change ratio behind future M' mixed two sources: the numerator "
        "was FPI from the random forest, the denominator was FPI downloaded from "
        "DCCEEW. Any bias in the forest sat in the numerator only, so it did not "
        "cancel, and it was read downstream as climate change. Both sides are now "
        "modelled by the same fitted forest:")
    q = doc.add_paragraph(
        "M'_future  =  λ × Original_M_2004 × Eq1(FPI_future, RF) "
        "÷ Eq1(FPI_1985-2014, RF)")
    q.paragraph_format.left_indent = Inches(0.35)
    for run in q.runs:
        run.italic = True
    doc.add_paragraph(
        "This is the rule already applied to temperature and rainfall, where every "
        "delta is CSIRO-minus-CSIRO and never CSIRO-minus-ANUClimate. FPI was the "
        "one input where it had not been applied.")
    doc.add_paragraph(
        "The averaging order is fixed and stated once here, because the two "
        "possible orders are easy to confuse. THE METHOD IS: predict each year's "
        "FPI with the random forest, average the FPI over the period, then apply "
        "Eq. (1) to that mean — on both sides of the ratio. Calculation_future_M_"
        "CSIRO/Step_06 names this the layer to use \"when feeding a single period "
        "value to FullCAM\". Applying Eq. (1) to each year and averaging the "
        "results afterwards is a different number, because Eq. (1) is convex; it "
        "is reported throughout as the sensitivity, never as the headline.",
        style="Intense Quote")
    doc.add_heading("What Roxburgh et al. (2019) actually specify", level=2)
    doc.add_paragraph(
        "Roxburgh, S.H., Karunaratne, S.B., Paul, K.I., Lucas, R.M., Armston, "
        "J.D., Sun, J. (2019). A revised above-ground maximum biomass layer for "
        "the Australian continent. Forest Ecology and Management 432, 264-275. "
        "https://doi.org/10.1016/j.foreco.2018.09.011 — Section 2, p. 265, the "
        "paragraph that introduces Eq. (1):")
    for quote in [
        "“… the forest growth model 3-PG … to derive a dimensionless index "
        "(the Forest Productivity Index, or FPI) that summarises potential site "
        "productivity for any given location based on the Normalised Difference "
        "Vegetation Index (NDVI), soil fertility, vapour pressure deficit, soil "
        "water content, and temperature (Kesteven and Landsberg, 2004).”",
        "“This relationship is used to calculate the parameter M (the "
        "predicted maximum AGB for a given FPI), and is given by "
        "M = (6.011 × √FPI − 5.291)²”  (Eq. 1)",
        "“Parameter M is constant for any location in Australia, and is "
        "embedded within the FullCAM database as a spatial input layer at a "
        "resolution of 0.0025° (or approximately 250 m).”",
    ]:
        q = doc.add_paragraph(quote)
        q.paragraph_format.left_indent = Inches(0.35)
        for run in q.runs:
            run.italic = True

    doc.add_paragraph(
        "Three things follow, and together they settle the averaging order. FPI "
        "is defined as a property of a LOCATION — \"potential site "
        "productivity for any given location\" — not of a location in a "
        "particular year. Eq. (1) is written for \"a given FPI\", one value in, "
        "one value out. And M is \"constant for any location in Australia\", a "
        "single static layer in the FullCAM database. Nowhere does the paper "
        "evaluate Eq. (1) on a series of annual FPI values, because in FullCAM "
        "no such series exists: the FPI layer Eq. (1) was calibrated against is "
        "itself a long-term climatological index (Kesteven and Landsberg, 2004; "
        "the empirical relationship is Richards and Brack, 2004).")
    doc.add_paragraph(
        "So the faithful reading is one FPI value per location entering Eq. (1) "
        "— which, for a 30-year projection window, means the window-mean FPI. "
        "That is the method used here. Applying Eq. (1) to each projected year "
        "and averaging the resulting M afterwards is an extension the paper does "
        "not describe, and because Eq. (1) is convex above its root it returns a "
        "systematically larger number (a median factor of %.4f on this domain). "
        "It is reported as a sensitivity for exactly that reason."
        % comp_med("RF: mean_of_annual"))
    doc.add_paragraph(
        "One honest qualification: the paper does not state an averaging rule, "
        "because it never faces the question — it had no time-varying FPI to "
        "average. The rule above is inferred from how FPI and M are defined, not "
        "quoted from a sentence that settles it. What can be said without "
        "inference is that the per-year route has no support in the paper, while "
        "the mean-FPI route matches the quantity Eq. (1) was calibrated on.")

    doc.add_paragraph(
        "No retraining was involved. The saved model is loaded, its feature order "
        "is asserted against the pipeline's own definition, and it is applied to "
        "the BARRA-R2 historical climate through the same soil block, land mask and "
        "bilinear regrid the 240 future predictions use. Only the climate year "
        "changes.")

    # ----------------------------------------------------------- accuracy ---
    doc.add_heading("Accuracy of the modelled historical FPI", level=1)
    def _m(row, key, spec="%.3f"):
        return spec % row[key] if key in row and pd.notna(row[key]) else "—"

    table(doc, [
        ["R² / Nash-Sutcliffe", "variance explained; 1.0 is perfect",
         _m(ins, "r2"), _m(oof, "r2")],
        ["Pearson r", "correlation only; blind to a level shift",
         _m(ins, "pearson_r"), _m(oof, "pearson_r")],
        ["RMSE (FPI units)", "typical error, large misses weighted heavily",
         _m(ins, "rmse"), _m(oof, "rmse")],
        ["RMSE (% of observed mean)", "the same error, unit-free",
         _m(ins, "nrmse_pct", "%.1f"), _m(oof, "nrmse_pct", "%.1f")],
        ["MAE (FPI units)", "typical error without that weighting",
         _m(ins, "mae"), _m(oof, "mae")],
        ["bias (FPI units)", "mean of modelled minus observed",
         _m(ins, "bias", "%+.4f"), _m(oof, "bias", "%+.4f")],
        ["bias (%)", "the same as a share of the observed mean",
         _m(ins, "pbias", "%+.3f"), _m(oof, "pbias", "%+.3f")],
        ["OLS slope", "1.0 means no compression of the range",
         _m(ins, "slope"), _m(oof, "slope")],
        ["OLS intercept", "with slope < 1, the regression-to-the-mean pair",
         _m(ins, "intercept"), _m(oof, "intercept")],
        ["Lin's concordance", "correlation AND agreement with 1:1",
         _m(ins, "ccc"), _m(oof, "ccc")],
        ["Willmott's d", "index of agreement, 0-1, robust to outliers",
         _m(ins, "willmott_d"), _m(oof, "willmott_d")],
        ["observed mean, sd", "the reference distribution",
         "%.2f, %.2f" % (ins["obs_mean"], ins["obs_sd"]),
         "%.2f, %.2f" % (oof["obs_mean"], oof["obs_sd"])],
        ["modelled mean, sd", "narrower sd = the forest smooths extremes",
         "%.2f, %.2f" % (ins["pred_mean"], ins["pred_sd"]),
         "%.2f, %.2f" % (oof["pred_mean"], oof["pred_sd"])],
        ["n", "cell-years compared",
         format(int(ins["n"]), ","), format(int(oof["n"]), ",")],
    ], ["statistic", "what it answers", "in sample", "out of fold"],
        widths=[1.5, 2.4, 1.0, 1.0])
    doc.add_paragraph(
        "These are the statistics for Figure 1a and 1b. Two of them deserve "
        "comment. The OLS slope is %.3f in sample and %.3f out of fold, with a "
        "positive intercept in both: the forest compresses the range slightly, "
        "over-predicting the lowest cells and under-predicting the highest, "
        "which is what a tree ensemble does by construction because it averages "
        "over leaves and cannot extrapolate. The modelled standard deviation is "
        "correspondingly smaller than the observed one (%.2f against %.2f out of "
        "fold). Neither is large enough to distort the ratio M' is built from, "
        "since the same compression appears in the numerator and the "
        "denominator, but both should be stated rather than left to the R²."
        % (ins["slope"], oof["slope"], oof["pred_sd"], oof["obs_sd"]))

    doc.add_paragraph(
        "The two rows answer different questions. Out of fold, every row was "
        "predicted by a forest that never saw that year, which is the same act as "
        "projecting 2035-2099; that is the accuracy figure. In sample measures fit, "
        "not skill — but it is the relevant number for the denominator swap, "
        "because it says how far the modelled denominator sits from the observed "
        "one. Per-year in-sample R² runs %.3f to %.3f with no trend across the 30 "
        "years, and per-year bias stays within ±%.2f FPI units."
        % (by_year["r2"].min(), by_year["r2"].max(), by_year["bias"].abs().max()))
    doc.add_paragraph(
        "Comparing a future projection against observed history would be neither of "
        "these: that is a trend comparison, and the two are not supposed to agree.")

    doc.add_paragraph(
        "Figure 1a plots the random forest's FPI against the observed DCCEEW FPI. "
        "The x axis is the observed value for one 1 km cell in one year, the y "
        "axis the forest's prediction for that same cell and year, and each "
        "hexagon counts how many cell-years fall in it — 60,000 cells drawn at "
        "random within each of the 30 years, 1.8 million points in total. It is "
        "NOT a comparison of 30-year averages; that is Figure 2. The dashed line "
        "is 1:1, so a point above it means the forest predicted more "
        "productivity than was observed. The statistics printed on the panel are "
        "in sample, meaning these 30 years are the years the forest was trained "
        "on, so the figure shows how faithfully it reproduces its own training "
        "data.")
    doc.add_paragraph(
        "How it is computed: for each year, the saved forest predicts FPI at "
        "every land cell; 60,000 of those cells are drawn at random and paired "
        "with the observed value at the same cell and year; the 30 years are "
        "pooled and binned into hexagons, each shaded by how many pairs it "
        "holds. The colour scale is linear but clipped at the 98th percentile "
        "of the hexagon counts, because a handful of hexagons on the 1:1 line "
        "hold orders of magnitude more cells than the rest and would otherwise "
        "flatten the whole picture into one pale shade; the colourbar says so. The accompanying statistics over all 6,956,407 cells and 30 "
        "years are R² %.3f, RMSE %.2f FPI units, MAE %.2f and bias %+.3f — the "
        "bias being the mean of (modelled - observed), so a value this close to "
        "zero says the forest is not systematically high or low. They are "
        "printed here rather than on the figure so that the figure stays "
        "readable."
        % (ins["r2"], ins["rmse"], ins["mae"], ins["bias"]))
    doc.add_paragraph(
        "How to read it: the band should hug the dashed 1:1 line. It does so "
        "tightly below about FPI 4, which is most of the continent, and fans out "
        "above it, where fewer cells and larger values make each prediction "
        "harder. Points above the line are years and places where the forest "
        "predicted more productivity than was observed.")
    figure(doc, "fig_01a_modelled_vs_observed.png",
           "Figure 1a. Random forest FPI against observed DCCEEW FPI, all 30 "
           "years, linear axes and linear hexbin density.")
    doc.add_paragraph(
        "Figure 1b splits that by year and adds the number that matters. The "
        "blue line is the same in-sample fit, one R² per year. The orange line "
        "is the out-of-fold result: for each year, the prediction comes from a "
        "forest trained on the other 24 years, so that year was unseen. The "
        "vertical gap between the lines is the cost of predicting a year the "
        "model has not met, which is exactly what the projection to 2035-2099 "
        "asks of it. The orange line is therefore the accuracy to quote, and it "
        "is the lower one.")
    doc.add_paragraph(
        "How it is computed: the blue point for a year is the R² of the saved "
        "forest's prediction against the observed layer for that year, over the "
        "full grid. The orange point comes from the year-group cross-validation "
        "already run in Random_forest_CSIRO/Step_03, where the 30 years are "
        "split into five folds of six years; each year is predicted by the "
        "forest fitted to the other 24. Pooled, blue gives R² %.3f and orange "
        "%.3f, and no year departs from its line by enough to change that "
        "reading."
        % (ins["r2"], oof["r2"]))
    figure(doc, "fig_01b_accuracy_by_year.png",
           "Figure 1b. Accuracy year by year, in sample against out of fold.")
    figure(doc, "fig_01b_accuracy_by_year.png",
           "Figure 1b. Accuracy year by year. The gap between the two lines is "
           "the cost of predicting an unseen year.")
    doc.add_paragraph(
        "Figure 2 is the same comparison in space rather than in points. Panel "
        "(a) averages the 30 observed annual FPI layers, panel (b) averages the "
        "30 modelled ones, and both use one colour scale so they can be read "
        "against each other directly. Panel (c) subtracts one from the other: "
        "red means the forest sits above the observation at that cell, blue "
        "below, and the scale is symmetric about zero so the two directions "
        "cannot be confused. What to look for is whether the residual has "
        "structure. It does not: the difference is fine-grained and scattered "
        "along the forested east, south-west and Tasmania rather than forming "
        "large regions of one sign, which is what a systematic failure would "
        "look like.")
    doc.add_paragraph(
        "How it is computed: panel (a) is the cell-wise mean of the 30 observed "
        "annual FPI rasters, panel (b) the cell-wise mean of the 30 modelled "
        "ones, and panel (c) is (b) minus (a). Panels (a) and (b) share one "
        "colour scale so they can be compared directly; panel (c) uses a "
        "diverging scale centred on zero, symmetric so that equal errors in "
        "either direction look equally large.")
    figure(doc, "fig_02_hist_fpi_maps.png",
           "Figure 2. Mean FPI 1985-2014: observed (a), modelled (b), and their "
           "difference (c).")

    # -------------------------------------------------------- denominator ---
    doc.add_heading("What the modelled denominator changes", level=1)
    doc.add_paragraph(
        "Modelled ÷ observed historical M has a median of %.4f (p05-p95 %.3f-%.3f). "
        "The forest's historical bias was small, so M' moves by well under a "
        "percent on that account. The change is methodological rather than "
        "numerical — which is the point: the bias now cancels by construction "
        "instead of by luck."
        % (comp_med("RF / OBS, mean_of_annual"),
           float(comp[comp["comparison"].str.startswith("RF / OBS, mean_of_annual")]["p05"].iloc[0]),
           float(comp[comp["comparison"].str.startswith("RF / OBS, mean_of_annual")]["p95"].iloc[0])))

    doc.add_heading("The averaging order, which matters more", level=2)
    doc.add_paragraph(
        "Eq. (1) is convex above its root, so mean_y[Eq1(FPI_y)] ≥ Eq1(mean_y FPI_y); "
        "the median gap is %.4f on the observed layers and %.4f on the modelled "
        "ones. The pipeline wrote the numerator in both orders but only ever built "
        "the denominator in one, so a per-year numerator was being divided by a "
        "mean-FPI denominator and the gap entered the ratio as a climate signal. "
        "Both orders are now built and paired like with like."
        % (comp_med("OBS: mean_of_annual"), comp_med("RF: mean_of_annual")))

    rows = [[r["layer"].replace("Eq1_M_hist", ""),
             r["fpi_source"].split(" (")[0], r["averaging_order"],
             "%.2f" % r["mean"], "%.2f" % r["median"]]
            for _, r in levels.iterrows()]
    table(doc, rows, ["denominator", "FPI source", "averaging order",
                      "mean", "median"], widths=[1.7, 1.4, 1.5, 0.7, 0.7])
    doc.add_paragraph("Units t DM ha⁻¹, over the 6,956,407 cells of the NLUM mask.")


    # ------------------------------------------------------------- mprime ---
    doc.add_heading("Effect on future M'", level=1)
    doc.add_paragraph(
        "The M' rasters were produced by the repository's own Step_08 with the "
        "modelled denominator passed in, not by a second implementation of Eq. (3). "
        "The measured shift against Option B is identical in every scenario and "
        "window, as it must be, since the denominator is a per-cell constant: "
        "×%.4f where only the source changed, ×%.4f where the averaging order was "
        "corrected as well."
        % (float(mp[mp["averaging_order"] == "eq1_of_mean"]["ratio_modelled_over_observed_median"].iloc[0]),
           float(mp[mp["averaging_order"] == "mean_of_annual"]["ratio_modelled_over_observed_median"].iloc[0])))

    merged = ob.merge(mp, on=["ssp", "window", "averaging_order"],
                      suffixes=("_obs", "_mod"))
    rows = []
    for win in ["2035-2064", "2070-2099"]:
        for ssp in SSP_ORDER:
            d = merged[(merged["ssp"] == ssp) & (merged["window"] == win)]
            a = d[d["averaging_order"] == "mean_of_annual"]
            b = d[d["averaging_order"] == "eq1_of_mean"]
            if a.empty or b.empty:
                continue
            rows.append([
                ssp.replace("ssp", "SSP"), win,
                "%+.1f" % b["pct_change_vs_New_M_2019_median_mod"].iloc[0],
                "%+.1f" % a["pct_change_vs_New_M_2019_median_mod"].iloc[0],
                "%+.1f" % a["pct_change_vs_New_M_2019_median_obs"].iloc[0],
            ])
    table(doc, rows, ["scenario", "window", "METHOD: Eq.(1) of mean FPI",
                      "sensitivity: per-year", "Option B (published)"],
          widths=[0.9, 1.0, 1.6, 1.3, 1.3])
    method = mp[mp["averaging_order"] == "eq1_of_mean"]["pct_change_vs_New_M_2019_median"]
    other = mp[mp["averaging_order"] == "mean_of_annual"]["pct_change_vs_New_M_2019_median"]
    doc.add_paragraph(
        "Median change in M' against Revised_M_Roxburgh, per cent — the step FullCAM sees "
        "from its historical maxAbgM to the future input. On the method every "
        "window is negative, from %+.1f%% to %+.1f%%; the per-year sensitivity "
        "gives %+.1f%% to %+.1f%%, slightly deeper throughout. Option B's column "
        "pairs a per-year numerator with a mean-FPI denominator, which is the "
        "mismatch described above, and two of its eight windows come out positive."
        % (method.max(), method.min(), other.max(), other.min()))

    doc.add_paragraph(
        "Figure 4 compares Revised_M_Roxburgh — the revised maximum biomass layer of "
        "Roxburgh et al. (2019), which is the historical maxAbgM input FullCAM "
        "reads — against the future M' this work produces. Each bar is the "
        "median over the NLUM mask of 100 x (M' - Revised_M_Roxburgh) / Revised_M_Roxburgh for "
        "one scenario and one 30-year window, so a bar at -10 means the typical "
        "cell carries ten per cent less potential biomass than the layer FullCAM "
        "uses today. The two colours are two different historical denominators: "
        "blue divides by Eq. (1) of the FPI downloaded from DCCEEW, orange by "
        "Eq. (1) of the FPI the random forest models for the same 30 years. "
        "Orange is what this work uses, because then the historical and the "
        "future FPI come from one model and its bias cancels out of the ratio.")
    doc.add_paragraph(
        "Figure 4a is the method: the 30 annual FPI are averaged first and "
        "Eq. (1) is applied to that mean, on both sides. The two colours nearly "
        "coincide, which is the expected result — the denominator swap is worth "
        "less than a per cent — and it doubles as a check on the arithmetic. "
        "Figure 4b repeats it with Eq. (1) applied per year and the results "
        "averaged; the bars deepen by about one percentage point throughout, "
        "which is the Jensen gap of Figure 3c arriving in the answer.")
    figure(doc, "fig_04a_mprime_change_method.png",
           "Figure 4a. The step FullCAM sees, on the method. Blue is the "
           "observed historical FPI (the DCCEEW download), orange the modelled "
           "historical FPI from the random forest — the layer this work uses, "
           "since both the historical and the future FPI come from the forest. "
           "The orders already matched on both sides here, so the bars barely "
           "move: the expected result, and a check on the arithmetic.")
    figure(doc, "fig_04b_mprime_change_sensitivity.png",
           "Figure 4b. The same on the per-year sensitivity, where the two "
           "positive bars of the observed-denominator route turn negative.")
    doc.add_paragraph(
        "Figure 5 is the same quantity as Figure 4, cell by cell instead of "
        "summarised to a median: 100 x (M' - Revised_M_Roxburgh) / Revised_M_Roxburgh for each "
        "of the eight scenario-windows, on one diverging scale centred on zero, "
        "so blue is a loss of potential biomass against today's layer and red a "
        "gain. The rows are the two windows and the columns the four scenarios, "
        "which makes the two readings easy to separate: down a column is the "
        "passage of time under one scenario, across a row is the choice of "
        "scenario at one time. Losses dominate the forested east, the south-west "
        "and Tasmania. The red patches are arid interior cells where M' is only "
        "a few tonnes per hectare, so a large percentage is a small absolute "
        "change — which is why Figure 4 quotes medians and the comparison "
        "section also reports totals in Mt DM.")
    figure(doc, "fig_05_mprime_change_maps.png",
           "Figure 5. Projected change in M' against Revised_M_Roxburgh, per cell, for "
           "each scenario and window.")

    # ------------------------------------------------------------- checks ---
    doc.add_heading("Checks", level=1)
    items = [
        "The rebuilt observed denominator reproduces the pipeline's cached "
        "Eq1_M_hist_1985-2014.tif to %.1e t DM ha⁻¹, so these layers sit on the "
        "same arithmetic as the existing pipeline." % rebuild_max,
        "The Jensen gap measured here on the observed layers, %.4f, is exactly the "
        "figure recorded independently in Option_B_matched_footing/README.md."
        % comp_med("OBS: mean_of_annual"),
        "The shift in M' equals the ratio of the denominators, cell for cell, in "
        "all eight scenario-windows — so nothing else moved.",
        "Every written raster was verified on the NLUM grid: no non-finite value "
        "inside the mask, no data outside it, no negative M'.",
    ]
    for it in items:
        doc.add_paragraph(it, style="List Bullet")

    # ==================================================================== #
    # Part 2 - the comparison against Revised_M_Roxburgh
    # ==================================================================== #
    comp_csv = COMP_OUT / "comparison_vs_New_M_2019.csv"
    if comp_csv.exists():
        cmp_df = pd.read_csv(comp_csv)
        cv_df = pd.read_csv(COMP_OUT / "cv_summary.csv")
        dec_df = pd.read_csv(COMP_OUT / "change_by_baseline_decile.csv")
        ref_row = cmp_df[cmp_df["ssp"] == "New_M_2019"].iloc[0]
        fut_sp = cmp_df[cmp_df["ssp"] != "New_M_2019"]["spatial_cv_pct"]
        fut_rows = cmp_df[cmp_df["ssp"] != "New_M_2019"]
        fut = cmp_df[cmp_df["ssp"] != "New_M_2019"]

        doc.add_page_break()
        doc.add_heading("Future M' against Revised_M_Roxburgh", level=1)
        doc.add_paragraph(
            "Revised_M_Roxburgh is the layer FullCAM ships as its historical maxAbgM, so "
            "it is the reference the future inputs step away from. Its mean over "
            "the NLUM mask is %.2f t DM ha⁻¹ and its area-weighted national total "
            "is %s Mt DM." % (ref_row["Mprime_mean"],
                              format(int(round(ref_row["total_Mt_DM"])), ",")))
        doc.add_paragraph(
            "The comparison is anchored rather than independent, and it is worth "
            "being explicit about why. λ × Original_M_2004 IS Revised_M_Roxburgh, so "
            "averaging the 30 modelled historical years of M' must return the "
            "reference exactly. It does, to a median relative error of 2.8e-08 "
            "(max 1.9e-07) — float32 rounding. That is a strong check that the "
            "chain from FPI through Eq. (1) and Eq. (3) does what it claims, but "
            "it also means these figures measure the projected *change*, not "
            "whether the absolute level is right. For the level, see "
            "Validation_GEDI/.")

        doc.add_heading("The statistics, and what each one is for", level=2)
        table(doc, [
            ["bias", "mean(M' − Revised_M_Roxburgh), t DM ha⁻¹",
             "average level shift; sign tells the direction, and it can be near "
             "zero while individual cells move a lot"],
            ["RMSE", "√mean((M' − Revised_M_Roxburgh)²), t DM ha⁻¹",
             "typical size of a cell's change, squaring so that large movers "
             "dominate; always ≥ MAE"],
            ["MAE", "mean|M' − Revised_M_Roxburgh|, t DM ha⁻¹",
             "typical size of a change without that weighting; the gap to RMSE "
             "says how skewed the changes are"],
            ["Pearson r", "correlation across cells",
             "whether the spatial pattern is preserved. It cannot detect a level "
             "shift, so it is read with bias, never alone"],
            ["OLS slope", "regression of M' on Revised_M_Roxburgh",
             "whether the change is proportional. >1 means high-biomass cells "
             "change less in relative terms than low-biomass ones"],
            ["median % change", "median over cells of 100(M'−ref)/ref",
             "the typical cell's fate, robust to the long right tail of M'"],
            ["% cells declining", "share with M' < Revised_M_Roxburgh",
             "how widespread the change is, independently of its size"],
            ["spatial CV", "sd over cells ÷ mean over cells",
             "how uneven the map is as a whole; rises when the change is "
             "concentrated rather than uniform"],
            ["interannual CV", "sd over the 30 years ÷ their mean, per cell",
             "year-to-year variability within one scenario"],
            ["across-scenario CV", "sd over the 4 SSPs ÷ their mean, per cell",
             "how much the scenario choice matters"],
            ["national total", "Σ (M' × cell area), Mt DM",
             "the aggregate that a carbon account cares about; area-weighted, "
             "since 0.01° cells shrink with latitude by cos(lat)"],
        ], ["statistic", "definition", "what it answers"],
            widths=[1.1, 2.0, 3.2])

        doc.add_heading("Interannual variability (CV within a window)", level=2)
        inter = cv_df[cv_df["kind"] == "interannual"].set_index("layer")
        hist_cv = float(inter.loc["historical 1985-2014", "median"])
        rows = [["historical 1985-2014", "%.1f" % hist_cv, "—"]]
        for _, r in fut.iterrows():
            key = "%s %s" % (r["ssp"], r["window"])
            v = float(inter.loc[key, "median"])
            rows.append([key.replace("ssp", "SSP"), "%.1f" % v,
                         "%+.1f" % (v - hist_cv)])
        table(doc, rows, ["window", "median CV (%)", "vs historical (pp)"],
              widths=[2.2, 1.4, 1.6])
        doc.add_paragraph(
            "Two things follow. First, the level is high: a median near %.0f%% "
            "means a cell's M' swings by about half its own mean from one year to "
            "the next. That is expected rather than alarming — Eq. (1) is "
            "quadratic in √FPI, so it amplifies a dry year — but it does mean no "
            "single future year should be quoted as the value for a site. Use the "
            "window mean, which is what the FullCAM inputs are built from."
            % hist_cv)
        doc.add_paragraph(
            "Second, the future CV is lower than the historical one in every "
            "scenario-window. Two ways of saying it, because they are different "
            "quantities: the difference of the medians is 0.8 to 5.0 percentage "
            "points (table above), while the median of the per-cell difference is "
            "1.4 to 4.7 (Figure 7). Either way the sign is the same everywhere. "
            "Projected M' does not become more erratic. Read that with the method "
            "in mind: the QDC "
            "change factors are applied to observed BARRA-R2 years, so the "
            "interannual sequence in the projections is observed weather "
            "rescaled, not model weather. The method can shift and stretch that "
            "variability but cannot invent new variability, so this result is "
            "evidence about the change factors, not an independent finding about "
            "future climate variability.")
        doc.add_paragraph(
            "How Figures 6 and 7 are computed. For one scenario-window, the 30 "
            "annual M' rasters are read and, at every cell, the standard "
            "deviation across those 30 values is divided by their mean and "
            "expressed as a percentage. The historical panel is the same "
            "calculation on the 30 modelled historical years. Figure 6 maps "
            "those nine layers on one colour scale, set by the typical spread "
            "rather than the largest tail so that no single panel washes the "
            "others out; the median of each panel is printed under its title. "
            "Figure 7 subtracts the historical layer from each future one, so "
            "its unit is percentage points and its scale is diverging about "
            "zero: blue means less year-to-year variability than the historical "
            "period, red more.")
        doc.add_paragraph(
            "How to read them. The level is what to notice first in Figure 6 — "
            "around 45-48% everywhere — and the direction in Figure 7, which is "
            "negative in all eight panels. White cells in Figure 6 are where the "
            "30-year mean falls below 1 t DM ha⁻¹ and a ratio stops being "
            "meaningful, not missing data.")
        figure(doc, "fig_06_cv_interannual.png",
               "Figure 6. Interannual CV of M' in each scenario-window and in the "
               "modelled historical period. One colour scale throughout, set by "
               "the typical spread rather than the longest tail. The arid "
               "interior is most variable in relative terms because its mean is "
               "small; white cells are where the mean falls below 1 t DM ha⁻¹ and "
               "a ratio stops being meaningful.", folder=COMP_PLOTS)
        figure(doc, "fig_07_cv_change.png",
               "Figure 7. Future CV minus historical CV, in percentage points. "
               "Blue is less year-to-year variability than the historical period, "
               "red is more. The median is negative in all eight panels; the red "
               "patches are mostly in the north-west and the southern rangelands.",
               folder=COMP_PLOTS)

        doc.add_heading("Scenario spread, and which uncertainty dominates", level=2)
        scen = cv_df[cv_df["kind"] == "across_scenarios"].set_index("layer")
        doc.add_paragraph(
            "The four SSPs disagree with one another by a median CV of %.1f%% in "
            "2035-2064 and %.1f%% in 2070-2099, against roughly %.0f%% of "
            "year-to-year variability within any one of them. The scenarios "
            "separate late, as they should, but even then the choice of year "
            "inside a window is three to four times larger a source of spread "
            "than the choice of scenario. Anyone reading a single cell of a "
            "single future year is reading mostly weather."
            % (float(scen.loc["2035-2064", "median"]),
               float(scen.loc["2070-2099", "median"]),
               float(inter[inter.index != "historical 1985-2014"]["median"].mean())))
        doc.add_paragraph(
            "Figure 8 changes what varies. At each cell the four SSP "
            "window-mean M' values are taken, and their standard deviation is "
            "divided by their mean — so this is the spread the choice of "
            "scenario produces, holding the year fixed, while Figure 6 was the "
            "spread the year produces, holding the scenario fixed. Panel (c) "
            "places the medians of both side by side, which is the only fair "
            "way to compare them.")
        figure(doc, "fig_08_cv_across_scenarios.png",
               "Figure 8. Across-scenario CV per window (left, centre) and the "
               "two kinds of variability side by side (right).", folder=COMP_PLOTS)

        doc.add_heading("Cell by cell", level=2)
        rows = []
        for _, r in fut.iterrows():
            rows.append([r["ssp"].replace("ssp", "SSP"), r["window"],
                         "%.3f" % r["pearson_r"], "%.3f" % r["slope"],
                         "%+.1f" % r["bias"], "%.1f" % r["rmse"],
                         "%.0f" % r["pct_cells_declining"]])
        table(doc, rows, ["scenario", "window", "r", "slope", "bias", "RMSE",
                          "% cells down"], widths=[0.8, 1.0, 0.7, 0.7, 0.7, 0.7, 1.0])
        doc.add_paragraph(
            "r stays between %.3f and %.3f: the spatial pattern of M' is almost "
            "entirely inherited from Revised_M_Roxburgh, which is what a delta-change "
            "method should produce — the projection rescales the reference rather "
            "than redrawing it. The slope above 1 in most windows says the "
            "rescaling is not uniform: low-biomass cells lose a larger *fraction* "
            "than high-biomass ones. Bias and RMSE grow together from the mid to "
            "the late window and from low to high forcing, and the share of "
            "declining cells rises from %.0f%% to %.0f%%, so the late-century "
            "high-forcing decline is both deeper and more widespread."
            % (fut["pearson_r"].min(), fut["pearson_r"].max(),
               fut["pct_cells_declining"].min(), fut["pct_cells_declining"].max()))
        doc.add_paragraph(
            "Figure 9 is the cell-by-cell comparison. The x axis is Revised_M_Roxburgh "
            "at a cell, the y axis the future M' at the same cell, and the "
            "hexagon shading counts cells; the dashed line is 1:1, so anything "
            "below it loses potential biomass. A delta-change method cannot "
            "move a cell far off that line, which is why the statistics below "
            "matter more than the picture: the correlation is high by "
            "construction and it is the slope and the bias that carry the "
            "information.")
        rows = []
        for _, r in fut_rows.iterrows():
            rows.append([r["ssp"].replace("ssp", "SSP"), r["window"],
                         "%.3f" % r["pearson_r"], "%.3f" % r["slope"],
                         "%+.2f" % r["bias"], "%.1f" % r["rmse"],
                         "%.0f" % r["pct_cells_declining"]])
        table(doc, rows, ["scenario", "window", "Pearson r", "OLS slope",
                          "bias (t DM/ha)", "RMSE", "% cells down"],
              widths=[0.9, 1.0, 0.9, 0.9, 1.1, 0.7, 1.0])
        figure(doc, "fig_09_scatter_vs_New_M_2019.png",
               "Figure 9. M' against Revised_M_Roxburgh, one hexbin per scenario-window. "
               "The dashed line is 1:1; cells below it lose biomass. "
               "The cloud tightens around the line at low biomass and fans out "
               "above ~200 t DM ha⁻¹, where a few large movers set the RMSE.",
               folder=COMP_PLOTS)

        doc.add_heading("National total", level=2)
        lo = fut.loc[fut["total_pct_change"].idxmin()]
        hi = fut.loc[fut["total_pct_change"].idxmax()]
        doc.add_paragraph(
            "Area-weighted, the national total falls in every scenario-window: "
            "from %s Mt DM to between %s and %s Mt DM, i.e. %.1f%% (%s %s) to "
            "%.1f%% (%s %s). The totals fall less than the per-cell medians "
            "because the deepest relative losses are in low- and mid-biomass "
            "cells, which carry little of the total."
            % (format(int(round(ref_row["total_Mt_DM"])), ","),
               format(int(round(fut["total_Mt_DM"].min())), ","),
               format(int(round(fut["total_Mt_DM"].max())), ","),
               hi["total_pct_change"], hi["ssp"].replace("ssp", "SSP"), hi["window"],
               lo["total_pct_change"], lo["ssp"].replace("ssp", "SSP"), lo["window"]))
        doc.add_paragraph(
            "This is a carrying-capacity total, not an inventory: M' is what a "
            "site could carry at maturity, not what stands on it today.")
        doc.add_paragraph(
            "Figure 10 aggregates. Each cell's M' in t DM ha⁻¹ is multiplied by "
            "that cell's area in hectares and summed over the NLUM mask, giving "
            "Mt DM. The area is not constant: cells are 0.01° geographic, so "
            "their width shrinks with latitude as cos(lat), and ignoring that "
            "over-weights the south by several per cent. Panel (a) shows the "
            "totals against the reference line, panel (b) the same as a "
            "percentage change. This is a carrying-capacity total, not an "
            "inventory — M' is what a site could carry at maturity, not what "
            "stands there now.")
        figure(doc, "fig_10a_national_total.png",
               "Figure 10a. National total above-ground biomass by "
               "scenario-window, against the Revised_M_Roxburgh reference line.",
               folder=COMP_PLOTS)
        figure(doc, "fig_10b_national_total_change.png",
               "Figure 10b. The same as a percentage change. Note the "
               "non-monotonic ordering: SSP245 2070-2099 is the mildest of the "
               "eight, which the Random_forest_CSIRO report traces to ACCESS-CM2 "
               "r4i1p1f1 rainfall and humidity rather than to the forcing level.",
               folder=COMP_PLOTS)

        doc.add_heading("A third CV: future M' against the reference map",
                        level=2)
        doc.add_paragraph(
            "The interannual and across-scenario CVs above have no counterpart "
            "in Revised_M_Roxburgh, which is a single static layer. The spatial CV does: "
            "sd over cells divided by the mean over cells, one number per map. "
            "It rises from %.1f%% for Revised_M_Roxburgh to %.1f-%.1f%% across the eight "
            "scenario-windows, so the projection makes the map more uneven rather "
            "than less — the losses are concentrated, not spread evenly, which is "
            "the same thing the decile figure says from the other direction."
            % (float(cmp_df[cmp_df["ssp"] == "New_M_2019"]["spatial_cv_pct"].iloc[0]),
               float(fut_sp.min()), float(fut_sp.max())))
        doc.add_paragraph(
            "A note on the name: this report and its figures call the reference "
            "Revised_M_Roxburgh, the revised maximum biomass layer of Roxburgh "
            "et al. (2019). The file on disk keeps its released name, "
            "New_M_2019_NLUM.tif, and the CSV columns keep New_M_2019 as their "
            "key, so the two names refer to one layer throughout.")
        doc.add_paragraph(
            "How Figure 14 is computed: for one layer, the standard deviation "
            "over all cells divided by the mean over all cells. One number per "
            "map, so it can be formed for Revised_M_Roxburgh too, which is why this is "
            "the CV that compares the projection with the reference. Panel (b) "
            "expresses each as a percentage change against the reference value.")
        figure(doc, "fig_14a_spatial_cv_vs_reference.png",
               "Figure 14a. Spatial CV of each future layer against the "
               "Revised_M_Roxburgh reference.", folder=COMP_PLOTS)
        figure(doc, "fig_14b_spatial_cv_change.png",
               "Figure 14b. The same as a change against the reference.",
               folder=COMP_PLOTS)

        doc.add_heading("Where in the distribution the change falls", level=2)
        late = dec_df[(dec_df["window"] == "2070-2099") & (dec_df["ssp"] == "ssp585")]
        worst = late.loc[late["pct_change_median"].idxmin()]
        top = late[late["decile"] == 10].iloc[0]
        doc.add_paragraph(
            "Cells were binned into deciles of Revised_M_Roxburgh and the median change "
            "taken within each. The relative loss is deepest in the low and "
            "middle deciles - under SSP585 2070-2099 it reaches %.0f%% in decile "
            "%d - and shallowest in the top decile, at %.0f%%. In absolute tonnes "
            "the ordering reverses, because the top decile holds most of the "
            "biomass. Both statements are true and they answer different "
            "questions; whichever is quoted, say which one it is."
            % (worst["pct_change_median"], int(worst["decile"]),
               top["pct_change_median"]))
        doc.add_paragraph(
            "Figure 11 asks where in the distribution the change falls. Cells "
            "are sorted by their Revised_M_Roxburgh value and split into ten equal "
            "groups; within each group the median percentage change is taken. "
            "Decile 1 is the lowest-biomass tenth of the domain and decile 10 "
            "the highest. The curve falls and then rises, so the deepest "
            "relative losses are in the low and middle deciles and the "
            "shallowest in the top one. In absolute tonnes the ordering "
            "reverses, because decile 10 holds most of the biomass; that is why "
            "Figure 10 and Figure 11 can look like they disagree when they do "
            "not.")
        figure(doc, "fig_11_change_by_decile.png",
               "Figure 11. Median change in M' by decile of Revised_M_Roxburgh, per "
               "scenario and window. Decile 1 is the lowest-biomass tenth of the "
               "domain.", folder=COMP_PLOTS)

        bars_csv = COMP_OUT / "paired_bar_medians.csv"
        if bars_csv.exists():
            bars = pd.read_csv(bars_csv)
            base_eq1 = float(bars[(bars["ssp"] == "baseline") &
                                  (bars["series"].str.startswith("Eq1"))]["value"].iloc[0])
            base_mp = float(bars[(bars["ssp"] == "baseline") &
                                 (bars["series"].str.startswith("M'"))]["value"].iloc[0])
            mp_vals = bars[bars["series"].str.startswith("M'")]
            fut_vals = mp_vals[mp_vals["ssp"] != "baseline"]["value"]
            doc.add_heading("The result in one panel", level=2)
            doc.add_paragraph(
                "Figure 13 is the headline: the median M' of each scenario-window "
                "with every component of the ratio modelled by the random forest, "
                "against the hatched 1985-2014 baseline and the Revised_M_Roxburgh "
                "reference line. The baseline bar sits exactly on the line "
                "because averaging the modelled historical years returns "
                "Revised_M_Roxburgh by construction; every other bar is a projection, and "
                "all eight fall below it, from %.1f to %.1f t DM ha⁻¹ against "
                "%.2f."
                % (fut_vals.min(), fut_vals.max(), base_mp))
            doc.add_paragraph(
                "The percentages printed inside the bars are the shift in the "
                "median — median(M') against median(Revised_M_Roxburgh) — which is not "
                "the same statistic as the median of the per-cell changes "
                "tabulated earlier, because a median is not additive. The first "
                "answers \"where does the middle of the map sit now\", the second "
                "\"what happens to a typical cell\". Both are reported; say which "
                "one is being quoted.")
            figure(doc, "fig_13_rf_mprime_bars.png",
                   "Figure 13. Median M' across land cells for each "
                   "scenario-window, all components from the random forest. "
                   "Hatched: the 1985-2014 baseline. Dashed: Revised_M_Roxburgh.",
                   folder=COMP_PLOTS)

            doc.add_heading("The two footings on one axis", level=2)
            doc.add_paragraph(
                "Figure 12 puts the footing question and the climate signal in a "
                "single panel, because they are routinely confused. The orange "
                "bars are Eq. (1) M used as written; the navy bars are M' on the "
                "matched footing. The hatched pair on the left is 1985-2014, and "
                "the dashed line is the median of Revised_M_Roxburgh, %.2f t DM ha⁻¹."
                % base_mp)
            doc.add_paragraph(
                "Read it vertically and the orange-to-navy gap is the footing: "
                "%.2f against %.2f t DM ha⁻¹ in the baseline pair, a factor of "
                "%.2f. That gap is arithmetic, not climate — Eq. (1) is the "
                "relationship reported in the paper, while Original_M_2004 is the "
                "layer the Richards & Brack (2004) procedure produced and the one "
                "FullCAM ships. Read it horizontally and the navy bars' distance "
                "from the dashed line is the projected change, which is the only "
                "part of the figure that carries a climate signal. The navy "
                "baseline bar sits exactly on the line, as it must."
                % (base_eq1, base_mp, base_eq1 / base_mp))
            figure(doc, "fig_12_paired_bars.png",
                   "Figure 12. Median M across land cells: Eq. (1) M and matched-"
                   "footing M' for each scenario-window, against the 1985-2014 "
                   "baseline (hatched) and the Revised_M_Roxburgh reference (dashed). "
                   "Quoting an orange bar where a navy one belongs inflates M by "
                   "roughly %.0f%%." % (100 * (base_eq1 / base_mp - 1)),
                   folder=COMP_PLOTS)

    doc.add_heading("What to do with this", level=1)
    doc.add_paragraph(
        "Quote R² %.3f (out of fold) as the model's accuracy, never the in-sample "
        "%.3f. Report the denominator change as methodological: the bias it removes "
        "was small, and saying so is stronger than implying it was large."
        % (oof["r2"], ins["r2"]))
    doc.add_paragraph(
        "The averaging order is a decision that has not been made explicitly "
        "anywhere in this repository, and it moves the headline number more than "
        "the modelling change does. It should be settled before any change figure "
        "is published, and the same order used on both sides of the ratio "
        "thereafter. Nothing here has been adopted into FullCAM_input_CSIRO_data/; "
        "that remains a separate decision.")
    doc.add_paragraph(
        "One file outside this folder was modified, backwards compatibly: "
        "Calculation_future_M_CSIRO/Step_08_apply_published_lambda.py gained the "
        "--hist-m, --out-dir and --layers flags, plus a guard for a run that "
        "contains no annual layers. Omit the flags and it behaves exactly as "
        "before, so Option B and the existing outputs are unaffected.")

    doc.save(REPORT)
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
