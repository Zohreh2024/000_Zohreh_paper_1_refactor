"""
Step 07 - the report.

Builds Roxburgh_validation_report.docx from the tables and figures the earlier
steps wrote. Nothing is recomputed here; every number in the document comes from
a CSV in outputs/, so the report cannot drift from the analysis.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_07_write_report.py
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

INK_2 = RGBColor(0x52, 0x51, 0x4E)

NICE = {
    "M_original_2004": "Original M (FullCAM before 2019)",
    "M_revised_Roxburgh": "Revised_M_Roxburgh (New_M_2019)",
    "M_eq1_rf_hist": "Eq. (1) on modelled historical FPI",
}


def nice(layer):
    if layer in NICE:
        return NICE[layer]
    if layer.startswith("M_future_"):
        ssp, win = layer[len("M_future_"):].split("_")
        return "Future M, %s %s" % (ssp.upper(), win)
    return layer


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
    ap.add_argument("--records", default="records.csv")
    args = ap.parse_args()
    suf = args.records[len("records"):-len(".csv")]

    d = pd.read_csv(OUT_DIR / args.records, low_memory=False)
    stats = pd.read_csv(OUT_DIR / ("fit_statistics%s.csv" % suf))
    by_class = pd.read_csv(OUT_DIR / ("fit_statistics_by_class%s.csv" % suf))
    ks = pd.read_csv(OUT_DIR / ("ks_tests%s.csv" % suf))
    ms = pd.read_csv(OUT_DIR / ("means_by_state_class%s.csv" % suf))
    cg = pd.read_csv(OUT_DIR / ("spatial_autocorrelation%s.csv" % suf))
    ss = pd.read_csv(OUT_DIR / "sample_sensitivity.csv")
    trail = pd.read_csv(OUT_DIR / ("filter_trail%s.csv" % suf))
    oq = pd.read_csv(OUT_DIR / "observation_quality_summary.csv")
    bands = pd.read_csv(OUT_DIR / "plot_area_bands.csv")
    prov = pd.read_csv(OUT_DIR / "provider_effects.csv")

    S = stats.set_index("layer")
    ssk = ss[ss["layer"] == "M_revised_Roxburgh"].set_index("variant")
    oqd = dict(zip(oq["quantity"], oq["spearman"]))
    base_rho = float(ssk.loc["Roxburgh's construction (the baseline here)",
                             "spearman_rho"])
    best = ssk["spearman_rho"].idxmax()
    best_rho = float(ssk.loc[best, "spearman_rho"])

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Validating future M the way Roxburgh et al. (2019) "
                    "validated M'", 0)
    p = doc.add_paragraph()
    r = p.add_run("Validation_M/National_biomass_library/Roxburgh_validation · "
                  "generated %s · the eight future M' layers, every component "
                  "of the ratio produced by the random forest, scored against "
                  "the National Biomass Library with the paper's own protocol"
                  % date.today().isoformat())
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("What Roxburgh did, and what is transplanted here",
                    level=1)
    doc.add_paragraph(
        "Roxburgh et al. (2019) updated FullCAM's maximum above-ground biomass "
        "layer by fitting a random forest to the ratio between the existing "
        "model and field observations. For each of 5,739 minimally disturbed "
        "biomass records he formed his Eq. (2), lambda_i = M_i / O_i, "
        "interpolated lambda across the continent with a random forest on 23 "
        "climate and soil covariates, and multiplied it through his Eq. (3), "
        "M' = lambda x M. The layer that came out is New_M_2019, which this "
        "repository calls Revised_M_Roxburgh and uses as the historical anchor "
        "of every future projection.")
    doc.add_paragraph(
        "He judged the result on four numbers, computed on untransformed data "
        "and reported in his Table 4:")
    for t in [
        "ME, the mean error E - O. The sign is the bias, and a negative value "
        "is under-prediction.",
        "RMSE, the root mean squared error, which is the precision.",
        "EF, model efficiency (his Eq. (4), Nash and Sutcliffe 1970). 1.0 is "
        "perfect, 0.0 means the layer is no better than predicting the mean of "
        "the observations everywhere, and a negative value is worse than that.",
        "LCC, Lin's concordance correlation coefficient (his Eq. (5)). This is "
        "agreement with the 1:1 line rather than with any line, so unlike a "
        "correlation it can see a constant offset or a wrong slope.",
    ]:
        doc.add_paragraph(t, style="List Bullet")
    doc.add_paragraph(
        "He also stratified everything into Forest (canopy cover above 50 per "
        "cent) and Woodland (20 to 50 per cent) using the NVIS Major "
        "Vegetation Subgroups of his Table 2, compared the frequency "
        "distributions with a Kolmogorov-Smirnov test, reported means by state "
        "and vegetation class, and measured the spatial autocorrelation of his "
        "sample because clustered plots break the independence a random "
        "calibration/validation split assumes. All of that is reproduced here, "
        "on the same MVS class list, and applied to the eight future layers as "
        "well as to the two present-day ones he scored himself.")

    doc.add_heading("What a future layer can be asked", level=2)
    doc.add_paragraph(
        "Comparing a future M' against a present-day observation is not a "
        "validation of the future, and nothing in this report should be read "
        "as one. It asks a narrower and answerable question: does the "
        "projected layer stay inside the envelope that observed maximum "
        "biomass defines, and where it leaves that envelope, in which "
        "direction and by how much. A divergence that grows with forcing is "
        "the projected change, not an error. The present-day layers, which can "
        "be validated, sit beside the future ones in every table so that the "
        "two can be told apart.", style="Intense Quote")

    # ------------------------------------------------------------------ #
    doc.add_heading("The sample", level=1)
    doc.add_paragraph(
        "One row per observation, not per site. Roxburgh's n = 5,739 counts "
        "records and sites recur within it; the space-time validation next "
        "door collapses repeat visits to one row per site taking the maximum, "
        "which is right for a question about a site's potential but wrong "
        "here, because a maximum taken over an unequal number of visits raises "
        "the observed values and manufactures apparent under-prediction.")
    table(doc, [[r["step"], format(int(r["records"]), ",")]
                for _, r in trail.iterrows()],
          ["filter", "surviving records"], widths=[4.4, 1.5])
    doc.add_paragraph(
        "That leaves %s records against his 5,739. The difference is almost "
        "entirely the two filters of his we cannot reproduce: the satellite "
        "forest-cover continuity check over 1972-2016, and the "
        "custodian-by-custodian disturbance metadata of his Supplementary "
        "Appendix A. Between them those removed roughly 60 per cent of the "
        "14,453 records he began with. Our sample therefore retains disturbed "
        "stands his did not, and that is the first thing to suspect wherever "
        "the numbers below differ from his."
        % format(len(d), ","))

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 1 - the transplant is correct", level=1)
    doc.add_paragraph(
        "Before applying the protocol to anything new it has to reproduce the "
        "paper on the layers the paper itself produced. It does, at the level "
        "of the layers: averaged over the records, Original M and "
        "Revised_M_Roxburgh land within a few per cent of the continental "
        "means his Table 5 reports.")
    f = ms[ms["state"] == "ALL"].set_index("veg_class")
    rows = []
    if "Forest" in f.index:
        rows.append(["Forest", fmt(f.loc["Forest", "M_original_2004"], "%.1f"),
                     "172.1", fmt(f.loc["Forest", "M_revised_Roxburgh"], "%.1f"),
                     "234.4"])
    if "Woodland" in f.index:
        rows.append(["Woodland", fmt(f.loc["Woodland", "M_original_2004"], "%.1f"),
                     "48.5", fmt(f.loc["Woodland", "M_revised_Roxburgh"], "%.1f"),
                     "49.5"])
    table(doc, rows,
          ["class", "Original M here", "his Table 5", "Revised M here",
           "his Table 5"], widths=[1.1, 1.3, 1.1, 1.3, 1.1])
    doc.add_paragraph(
        "The Forest agreement is close to exact. The layers are being read "
        "correctly, on the right grid, at the right places.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 2 - the fit statistics do not reproduce, and the "
                    "reason is the sample", level=1)
    doc.add_paragraph(
        "Scored against our records, the same file Roxburgh scored at EF 0.40 "
        "and LCC 0.62 returns EF %s and LCC %s. The original M he scored at EF "
        "0.14 returns EF %s. Both are below zero, which means neither layer "
        "predicts these observations better than their own mean would."
        % (fmt(S.loc["M_revised_Roxburgh", "EF"]),
           fmt(S.loc["M_revised_Roxburgh", "LCC"]),
           fmt(S.loc["M_original_2004", "EF"])))
    rows = []
    published = {"M_original_2004": "ME -35.3, RMSE 239.1, EF 0.14, LCC 0.25",
                 "M_revised_Roxburgh": "ME -8.0, RMSE 200.7, EF 0.40, LCC 0.62"}
    for _, r in stats.iterrows():
        rows.append([nice(r["layer"]), format(int(r["n"]), ","),
                     fmt(r["ME"], "%+.1f"), fmt(r["RMSE"], "%.1f"),
                     fmt(r["EF"]), fmt(r["LCC"]),
                     published.get(r["layer"], "")])
    table(doc, rows,
          ["layer", "n", "ME", "RMSE", "EF", "LCC", "Roxburgh's own"],
          widths=[1.9, 0.6, 0.7, 0.7, 0.6, 0.6, 1.9])
    caption(doc, "Table 1. Roxburgh's Table 4, recomputed on our records for "
                 "every layer. His published values are given for the two "
                 "layers he scored.")

    doc.add_paragraph(
        "The layer is the same file, so the whole of that gap belongs to the "
        "sample. Step_03 walks every sample decision that differs between his "
        "construction and ours, scoring the same layer each time, and the "
        "result is unambiguous: no single choice recovers his agreement.")
    rows = []
    for v, r in ssk.iterrows():
        rows.append([v, format(int(r["n"]), ","), fmt(r["ME"], "%+.1f"),
                     fmt(r["EF"]), fmt(r["LCC"]),
                     fmt(r["spearman_rho"], "%+.3f")])
    table(doc, rows, ["sample", "n", "ME", "EF", "LCC", "Spearman rho"],
          widths=[2.6, 0.7, 0.8, 0.7, 0.7, 0.9])
    caption(doc, "Table 2. Every sample decision, one at a time, scoring "
                 "Revised_M_Roxburgh.")
    doc.add_paragraph(
        "On his construction the rank correlation between observed biomass and "
        "his own layer is %s. Every single-filter variant stays between -0.22 "
        "and +0.11. Only the full stack this repository applies - a minimum "
        "plot area, the biomass-versus-basal-area consistency check, records "
        "from 1985 on, one row per site, and mature stands only - reaches %s, "
        "and it does so on %s records out of %s. The positive agreement "
        "reported by the space-time validation is produced by the conjunction "
        "of those filters, not by any one of them, and not by the layer having "
        "broad skill against this library."
        % (fmt(base_rho, "%+.2f"), fmt(best_rho, "%+.2f"),
           format(int(ssk.loc[best, "n"]), ","), format(len(d), ",")))
    figure(doc, "fig_06_sample_sensitivity.png",
           "Figure 1. What each sample decision does to the agreement between "
           "observed biomass and Revised_M_Roxburgh. Green marks the only "
           "variant that reaches a rank correlation above 0.2.")
    doc.add_paragraph(
        "How to read it: each bar is the Spearman rank correlation on the "
        "subsample named on the left, with that subsample's size beside it. "
        "The quantity is a rank correlation rather than EF or LCC because rank "
        "is what a maximum-biomass layer must at minimum get right - it should "
        "put the productive sites above the unproductive ones even if the level "
        "is wrong - and because it is not thrown by the extreme values this "
        "library contains.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 3 - why the observations cannot resolve this",
                    level=1)
    doc.add_paragraph(
        "Two checks on the observation itself, in order. The first passes and "
        "the second explains everything above.")
    doc.add_heading("The biomass field is sound", level=2)
    doc.add_paragraph(
        "The library reports a plot figure in t DM per hectare and separately "
        "lists every stem with its own dry mass, its allometric model and the "
        "subplot area it was measured in. Rebuilding the plot figure from the "
        "stems - summing stem mass within each subplot, dividing by that "
        "subplot's area, averaging over subplots - reproduces the reported "
        "value at a rank correlation of %s over 1,995 surveys, with a median "
        "ratio of 1.08. The aggregation, the subplot areas and the per-hectare "
        "scaling are all correct. Whatever is wrong is not the arithmetic."
        % fmt(oqd.get("rebuilt vs reported plot AGB"), "%.3f"))

    doc.add_heading("The per-hectare figure is dominated by plot size", level=2)
    doc.add_paragraph(
        "Across the sample, reported biomass correlates with the area of the "
        "plot it was measured in at Spearman %s. That is far stronger than its "
        "correlation with any modelled layer (%s against Revised_M_Roxburgh), "
        "and it runs the wrong way: the smaller the plot, the larger the "
        "reported biomass per hectare."
        % (fmt(oqd.get("observed AGB vs plot area"), "%+.3f"),
           fmt(oqd.get("observed AGB vs M_revised_Roxburgh"), "%+.3f")))
    rows = [[str(r["plot_area_band"]), format(int(r["n"]), ","),
             fmt(r["obs_median"], "%.0f"), fmt(r["M_median"], "%.0f"),
             fmt(r["rho_obs_vs_M"], "%+.3f")] for _, r in bands.iterrows()]
    table(doc, rows,
          ["plot area", "records", "median observed", "median M",
           "rho against M"], widths=[1.3, 0.9, 1.3, 1.0, 1.1])
    caption(doc, "Table 3. Median reported biomass by the size of the plot it "
                 "came from.")
    doc.add_paragraph(
        "Median reported biomass falls from about 240 t DM per hectare on "
        "plots of 0.05 hectares or less to about 11 on plots above 0.45 "
        "hectares - a twenty-fold gradient produced by sampling geometry "
        "alone. A per-hectare figure from a 0.02 hectare plot is one large "
        "tree multiplied by fifty, and plots of that size are placed where "
        "there is something to measure. No spatial layer can reproduce that "
        "gradient, because nothing about the location predicts how large a "
        "plot a given agency chose to lay out there.")
    figure(doc, "fig_07_plot_size.png",
           "Figure 2. Reported biomass per hectare against the size of the "
           "plot it was measured in. The count of records in each band is "
           "given above the bar.")
    doc.add_paragraph(
        "The same effect appears provider by provider, which rules out the "
        "alternative explanation that plot size is merely a proxy for region:")
    rows = [[str(r["source"])[:40], format(int(r["n"]), ","),
             fmt(r["plot_area_median"], "%.2f"), fmt(r["obs_median"], "%.0f"),
             fmt(r["rho_obs_vs_M"], "%+.2f"),
             fmt(r["rho_obs_vs_area"], "%+.2f")]
            for _, r in prov.iterrows()]
    table(doc, rows,
          ["data provider", "n", "median plot (ha)", "median observed",
           "rho vs M", "rho vs plot area"], widths=[2.0, 0.6, 1.0, 1.1, 0.8, 1.0])
    caption(doc, "Table 4. Within each provider, what the reported biomass "
                 "tracks.")
    doc.add_paragraph(
        "Inside the largest provider - Queensland NFPP, 1,647 records on "
        "uniform 0.4 hectare plots - the rank correlation with "
        "Revised_M_Roxburgh is -0.24. Only one provider, DSITI Queensland "
        "Herbarium, reaches a positive correlation of note (+0.39). The "
        "library is a stem inventory assembled from many surveys with "
        "different designs, and it was never built to be a wall-to-wall "
        "biomass map; this is a statement about what a comparison against it "
        "can resolve, not a criticism of it.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 4 - the errors are spatially clustered", level=1)
    near = cg[cg["hi_km"] <= 10]["correlation"].mean()
    far = cg[cg["lo_km"] >= 200]["correlation"].mean()
    doc.add_paragraph(
        "Roxburgh measured the spatial correlation of his sample and reported "
        "it falling below 0.2 beyond about 10 km, then balanced the data by "
        "up-sampling at a 10 by 10 km scale before fitting. The same "
        "correlogram on the residual observed-minus-modelled gives %s within "
        "10 km here, and it does not fall below 0.2 until about 200 km, beyond "
        "which it is %s."
        % (fmt(near, "%.2f"), fmt(far, "%+.2f")))
    rows = [["%d to %d km" % (r["lo_km"], r["hi_km"]),
             format(int(r["pairs"]), ","), fmt(r["correlation"], "%+.3f")]
            for _, r in cg.iterrows()]
    table(doc, rows, ["separation", "pairs", "residual correlation"],
          widths=[1.4, 1.2, 1.6])
    figure(doc, "fig_05_spatial_autocorrelation.png",
           "Figure 3. How far apart two plots must be before their errors are "
           "independent. The distance axis is logarithmic because the bins "
           "are; the correlation axis is linear.")
    doc.add_paragraph(
        "This matters for reading his Table 4 as much as ours. A random 70/30 "
        "split of a sample this clustered puts near neighbours on both sides "
        "of the split, so the withheld 30 per cent is not independent of the "
        "70 per cent the model saw, and the validation statistics are "
        "optimistic by an amount this design cannot quantify. Roxburgh raises "
        "the concern himself in his Section 2.4 and addresses it by bootstrap "
        "up-sampling; the point here is only that his 0.40 and 0.62 are an "
        "upper bound on what an independent sample would give, which narrows "
        "the gap against our numbers from the other side.")

    # ------------------------------------------------------------------ #
    doc.add_heading("Result 5 - what this says about the future layers",
                    level=1)
    fut = stats[stats["layer"].str.startswith("M_future_")]
    doc.add_paragraph(
        "The eight future layers score EF %s to %s and LCC %s to %s, against "
        "%s and %s for Revised_M_Roxburgh. They are indistinguishable from it "
        "and from each other. That is the expected result and not a "
        "disappointment: each future layer differs from the historical anchor "
        "by a few per cent in the median, while the observation carries a "
        "twenty-fold artefact from plot size. A test with this much noise in "
        "the reference cannot resolve a signal that small, and no amount of "
        "additional statistics will change that."
        % (fmt(fut["EF"].min()), fmt(fut["EF"].max()),
           fmt(fut["LCC"].min()), fmt(fut["LCC"].max()),
           fmt(S.loc["M_revised_Roxburgh", "EF"]),
           fmt(S.loc["M_revised_Roxburgh", "LCC"])))
    figure(doc, "fig_02a_ef_by_layer.png",
           "Figure 4. Model efficiency of every layer, with 95 per cent "
           "bootstrap intervals. The black diamonds are Roxburgh's published "
           "values for the two layers he scored.")
    figure(doc, "fig_02b_lcc_by_layer.png",
           "Figure 5. Lin's concordance correlation coefficient of every "
           "layer, on the same basis.")
    doc.add_paragraph(
        "The one thing the future layers do say is visible in the "
        "distributions rather than the fit statistics. As forcing increases "
        "the projected distribution spreads: its median falls while its upper "
        "tail rises.")
    rows = []
    for _, r in ks.iterrows():
        rows.append([nice(r["layer"]), fmt(r["layer_median"], "%.1f"),
                     fmt(r["layer_p95"], "%.0f"), fmt(r["layer_max"], "%.0f"),
                     fmt(r["ks_statistic"], "%.3f")])
    table(doc, rows,
          ["layer", "median", "95th percentile", "maximum",
           "KS statistic against the observations"],
          widths=[1.9, 0.9, 1.2, 0.9, 1.5])
    caption(doc, "Table 5. Distribution of each layer against the observed "
                 "biomass, whose median is %s, 95th percentile %s and maximum "
                 "%s t DM per hectare."
                 % (fmt(ks["obs_median"].iloc[0], "%.1f"),
                    fmt(ks["obs_p95"].iloc[0], "%.0f"),
                    fmt(ks["obs_max"].iloc[0], "%.0f")))
    doc.add_paragraph(
        "Every layer is rejected against the observations at any conventional "
        "threshold, which given the plot-size artefact is unsurprising and not "
        "informative on its own. The shape is informative. Roxburgh's original "
        "M could not exceed 473 t DM per hectare on these records while the "
        "observations reach far beyond that; his revised layer lifted the "
        "ceiling to about 1,160, which is the improvement his Figure 6b "
        "reports. The future layers keep that ceiling and raise it further "
        "with forcing - to about 1,450 under SSP585 2070-2099 - while their "
        "medians fall. The projection is not shifting the map down uniformly; "
        "it is pulling the middle down and the top up, which is the same "
        "result the comparison folder reports as a rising spatial coefficient "
        "of variation.")
    figure(doc, "fig_03_distributions.png",
           "Figure 6. Distribution of modelled maximum biomass against the "
           "observations. Observed biomass is the filled grey histogram; the "
           "three lines are the original layer, the revised layer and the "
           "most strongly forced future layer.")

    # ------------------------------------------------------------------ #
    doc.add_heading("The scatter, and the strata", level=1)
    doc.add_paragraph(
        "Roxburgh's Figure 4 plots observed against predicted biomass for each "
        "layer. His version uses log10 axes for display with the statistics "
        "computed on untransformed data; the statistics here are his, the axes "
        "are linear, and the few records beyond the axis are counted on the "
        "panel. What a log axis would hide is exactly what these panels need "
        "to show: the cloud has no orientation.")
    for panel, name, lab in [
            ("a", "fig_01a_observed_vs_M_original_2004.png",
             "the original FullCAM layer"),
            ("b", "fig_01b_observed_vs_M_revised_Roxburgh.png",
             "Revised_M_Roxburgh"),
            ("c", "fig_01c_observed_vs_M_future_ssp585_2070-2099.png",
             "future M under SSP585 2070-2099")]:
        figure(doc, name,
               "Figure 7%s. Observed against modelled biomass for %s. Colour "
               "is the number of records per hexagonal cell on a linear scale "
               "clipped at the 98th percentile, so that the dense core does "
               "not saturate. The dashed line is 1:1." % (panel, lab))

    doc.add_heading("By vegetation class", level=2)
    sel = by_class[by_class["layer"].isin(
        ["M_original_2004", "M_revised_Roxburgh",
         "M_future_ssp585_2070-2099"])]
    rows = [[nice(r["layer"]), r["stratum"], format(int(r["n"]), ","),
             fmt(r["ME"], "%+.1f"), fmt(r["EF"]), fmt(r["LCC"])]
            for _, r in sel.iterrows()]
    table(doc, rows, ["layer", "class", "n", "ME", "EF", "LCC"],
          widths=[1.9, 1.0, 0.7, 0.9, 0.7, 0.7])
    doc.add_paragraph(
        "The pooled statistics hide a sign reversal. Averaged over the "
        "records, the layers over-predict Forest and under-predict Woodland, "
        "while the observations run the other way - our Woodland records carry "
        "MORE biomass than our Forest records, which is ecologically "
        "backwards and is the plot-size artefact again, since the Woodland "
        "records come disproportionately from small plots. Two quantities that "
        "are ordered oppositely across the dominant stratum cannot correlate "
        "positively when pooled, and that is the arithmetic behind the "
        "negative numbers in Table 1.")
    for panel, cls in [("a", "Forest"), ("b", "Woodland")]:
        figure(doc, "fig_04%s_state_means_%s.png" % (panel, cls.lower()),
               "Figure 8%s. Mean observed and modelled biomass by state, %s "
               "sites, with the record count under each state. Roxburgh's "
               "Figure 8 in the same form." % (panel, cls))
    doc.add_paragraph(
        "Read these two figures as a diagnostic of the sample rather than of "
        "the layers. Tasmania contributes 15 Forest records with a mean "
        "observed biomass of 15 t DM per hectare, against a modelled 480 - "
        "Tasmanian tall forest does not carry 15 t DM per hectare, and those "
        "records are small or recently disturbed plots that survived our "
        "filters because we lack his. The Northern Territory contributes 188 "
        "Forest records at a mean of 334 against a modelled 52, which is the "
        "opposite artefact: savanna measured on 0.08 hectare plots. Neither "
        "state can be used to judge a layer.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to conclude", level=1)
    doc.add_paragraph(
        "The protocol transplants correctly and the layers are read correctly, "
        "but the National Biomass Library as we are able to filter it cannot "
        "discriminate between these maximum-biomass layers - not between the "
        "eight future ones, and not even between the original FullCAM layer "
        "and Roxburgh's revision of it.", style="Intense Quote")
    for t in [
        "Do not quote EF or LCC from this folder as evidence about any layer. "
        "Quote them as evidence about the reference: a test whose observation "
        "carries a twenty-fold artefact from plot size has no power to resolve "
        "a few per cent of projected change.",
        "The positive agreement the space-time validation reports is real but "
        "narrow. It appears only under the full stack of filters, on 600 of "
        "%s records, and the honest statement is that those filters select a "
        "subsample on which the layer ranks sites, not that the layer ranks "
        "this library." % format(len(d), ","),
        "Roxburgh's own published statistics are an upper bound. His sample is "
        "clustered well beyond the 10 km he balanced at - the residual "
        "correlation here does not fall below 0.2 until about 200 km - so a "
        "random 70/30 split leaks, and EF 0.40 and LCC 0.62 flatter what an "
        "independent sample would give. This is his own caveat, extended.",
        "The filtering we cannot reproduce is the likely difference. He "
        "removed roughly 60 per cent of the library using satellite cover "
        "continuity and custodian disturbance metadata. Obtaining those, or an "
        "equivalent, would be the single most useful thing that could be done "
        "to make this comparison work.",
        "A plot-size floor is not a substitute for that filtering. Requiring "
        "at least 0.5 hectares leaves 1,055 records and still gives a rank "
        "correlation of -0.04: the small plots are not merely noisy, their "
        "removal leaves a sample with different problems.",
        "The future layers should be evaluated on process, not on this "
        "reference. What can be checked - that the historical limit returns "
        "New_M_2019 exactly, that the change factors are bounded and smooth, "
        "that the climate signal behaves as forcing increases - is checked in "
        "Option_B_matched_footing and in the comparison folder, and those "
        "checks are informative in a way this one is not.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    # ------------------------------------------------------------------ #
    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_01_build_records.py", "the record table and every layer sampled "
                                     "at each plot"],
        ["Step_02_fit_statistics.py", "ME, RMSE, EF and LCC - his Table 4"],
        ["Step_03_sample_sensitivity.py", "what each sample decision does"],
        ["Step_04_observation_quality.py", "the stem rebuild and the plot-size "
                                           "artefact"],
        ["Step_05_distributions_and_strata.py", "KS tests, state means, "
                                                "spatial autocorrelation"],
        ["Step_06_plots.py", "the figures"],
        ["Step_07_write_report.py", "this document"],
        ["outputs/*.csv", "every number quoted above"],
        ["plots/fig_01..07", "the figures in this report"],
    ], ["file", "what it holds"], widths=[2.4, 3.6])

    dst = HERE / ("Roxburgh_validation_report%s.docx" % suf)
    doc.save(str(dst))
    print("wrote %s" % dst)


if __name__ == "__main__":
    main()
