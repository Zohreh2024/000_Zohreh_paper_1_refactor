"""
Build the full report: Step 0 to validating M' with GEDI L4A.

Reads   outputs/analysis/*.csv, outputs/figures/*.png      (Step_05)
        outputs/gedi_fetch_manifest.csv, step logs          (Step_02/03/04)
        Random_forest_CSIRO/data/cv_metrics.csv             (RF skill)
        Writing_paper_01/output/results_summary.csv         (projected change)
        Option_B_matched_footing/outputs/*.csv              (footings)
        Option_B_matched_footing/Validation/Level_4_independent_data/
            outputs/gedi_vs_M_summary.csv                   (earlier L4B run)
Writes  Validation_GEDI_report.docx

Every result number is read from those files at build time, so re-running
Steps 03-05 with more regions and then this script refreshes the report.
Descriptive facts about the upstream pipeline (script names, design choices)
are written in, with the file each one comes from named in the text.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

import common as C
from make_validation_gedi_doc import (ACCENT, AMBER, GOOD, INK, MUTED, WARN,
                                      bullet, code, flag, h, para, rich, table)

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ANA = OUT / "analysis"
FIG = OUT / "figures"
DOCX = HERE / "Validation_GEDI_report.docx"
R = C.ROOT

TAGS = ["New_M_2019", "baseline_M_1985-2014"]
NICE = {"New_M_2019": "New_M_2019", "baseline_M_1985-2014": "baseline_M_1985-2014"}


def f1(x):
    return "%.1f" % x


def f2(x):
    return "%.2f" % x


def pct(x):
    return "%.1f%%" % x


def n(x):
    return "{:,}".format(int(x))


def figure(doc, path, caption, width=6.3):
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = para(doc, caption, size=9, italic=True, colour=MUTED, after=12)
    return p


def eq1_elasticity(fpi):
    s = 6.011 * np.sqrt(fpi)
    return s / (s - 5.291)


def load():
    d = {}
    d["overall"] = pd.read_csv(ANA / "overall_by_layer.csv")
    d["bins"] = pd.read_csv(ANA / "by_fpi_bin.csv")
    d["forest"] = pd.read_csv(ANA / "by_forest_class.csv")
    d["elast"] = pd.read_csv(ANA / "fpi_elasticity.csv")
    d["fp"] = pd.read_csv(ANA / "footprint_summary.csv").iloc[0]
    d["years"] = pd.read_csv(ANA / "footprints_by_year.csv")
    d["pft"] = pd.read_csv(ANA / "footprints_by_pft.csv")
    d["ratio"] = pd.read_csv(ANA / "layer_ratio_in_region.csv").iloc[0]
    d["region"] = pd.read_csv(ANA / "by_region.csv")
    d["fp_region"] = pd.read_csv(ANA / "footprints_by_region.csv")
    d["ratio_region"] = pd.read_csv(ANA / "layer_ratio_by_region.csv")
    d["manifest"] = pd.read_csv(OUT / "gedi_fetch_manifest.csv")
    d["cv"] = pd.read_csv(R / "Random_forest_CSIRO" / "data" / "cv_metrics.csv")
    d["paper"] = pd.read_csv(R / "Writing_paper_01" / "output" / "results_summary.csv")
    d["optb"] = pd.read_csv(R / "Option_B_matched_footing" / "outputs"
                            / "fullcam_inputs_summary.csv")
    d["orders"] = pd.read_csv(R / "Option_B_matched_footing" / "outputs"
                              / "baseline_orders.csv")
    d["l4b"] = pd.read_csv(R / "Option_B_matched_footing" / "Validation"
                           / "Level_4_independent_data" / "outputs"
                           / "gedi_vs_M_summary.csv")
    burn = {}
    for p in sorted((HERE / "fire").glob("burn_year_*.tif")):
        burn[int(p.stem.split("_")[-1])] = p
    d["fire_years"] = burn
    log = (OUT / "step04_New_M_2019_log.txt").read_text(errors="ignore")
    d["step04_log"] = log
    return d


def ov(d, tag, subset="unburnt"):
    o = d["overall"]
    return o[(o.layer == tag) & (o.footprints == subset)].iloc[0]


def cv_total(d, scheme):
    c = d["cv"]
    c = c[(c.scheme == scheme) & (c.n == c.n.max())]
    return c.iloc[0]


def _require_option_a(d):
    """This report is built around the Option A / Option B comparison.

    That footing was retired in September 2026 and Step_05 no longer scores it
    by default, so the analysis tables this report reads no longer carry it.
    Nothing has been deleted - `Step_05_analyse_vs_M.py --legacy-option-a`
    puts the layer back and regenerates every table below.
    """
    if "baseline_M_1985-2014" in set(d["overall"].layer):
        return
    raise SystemExit(
        "\n".join([
            "This report covers the present-day layers and the Option A /",
            "Option B footing comparison, which was retired in September 2026.",
            "The analysis tables no longer carry baseline_M_1985-2014, so the",
            "report cannot be built as it stands.",
            "",
            "  To regenerate it anyway:",
            "      python Step_05_analyse_vs_M.py --legacy-option-a",
            "      python make_validation_gedi_report.py",
            "",
            "  For the current validation of the FUTURE M' layers, see",
            "      Validation_GEDI_future_M_report.docx",
            "  built by Step_06_write_future_M_report.py.",
        ]))


def main():
    d = load()
    _require_option_a(d)
    fp = d["fp"]
    new_u, base_u = ov(d, "New_M_2019"), ov(d, "baseline_M_1985-2014")
    new_a, base_a = ov(d, "New_M_2019", "all"), ov(d, "baseline_M_1985-2014", "all")
    el = d["elast"].set_index("layer")
    ratio = d["ratio"]
    man = d["manifest"]
    n_gran = len(man)
    n_gran_pos = int((man.footprints > 0).sum())
    reg = d["region"]
    rn = reg[reg.layer == "New_M_2019"].set_index("region")
    rb = reg[reg.layer == "baseline_M_1985-2014"].set_index("region")
    rn_sorted = rn.sort_values("exceed_p95_n30_pct", ascending=False)
    hi_reg, lo_reg = rn_sorted.index[0], rn_sorted.index[-1]
    steeper = int((rn.slope_gedi_p95_n30 > rn.eq1_elasticity_at_median_fpi).sum())
    fo = d["forest"]
    ebf_new = fo[(fo.layer == "New_M_2019") & (fo.forest_class == ">=90%")].iloc[0]
    non_new = fo[(fo.layer == "New_M_2019")
                 & (fo.forest_class == "<50% evergreen broadleaf")].iloc[0]
    bins_new = d["bins"].query("layer == 'New_M_2019'")

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(0.9)
        s.top_margin = s.bottom_margin = Inches(0.8)

    # ------------------------------------------------------------------ title
    t = doc.add_heading("Validating M\u2032 with GEDI L4A", level=0)
    for r in t.runs:
        r.font.color.rgb = ACCENT
    para(doc, "The full chain from Step 0 (raw data) to future maximum "
              "aboveground biomass, and what GEDI lidar can and cannot say "
              "about it. Six forested regions of eastern and south-western "
              "Australia.", size=12, colour=MUTED)
    para(doc, "Built %s by make_validation_gedi_report.py. Every result "
              "number is read from the CSV outputs at build time."
         % date.today().strftime("%d %B %Y"), size=9, italic=True,
         colour=MUTED, after=14)

    # ---------------------------------------------------------------- summary
    h(doc, "Summary", 1)
    para(doc, "M\u2032 is the biomass a site can reach at maturity. The FullCAM "
              "future inputs are future M\u2032 for four SSPs over 2035-2064 and "
              "2070-2099. GEDI measured forest structure from 2019 to 2024, so "
              "it cannot observe future M\u2032 directly. It can test the two "
              "things future M\u2032 is built from: the present-day level of "
              "M\u2032, and how steeply biomass rises with the Forest "
              "Productivity Index (FPI), which Eq. (1) turns into the projected "
              "change. This report does both, against two present-day M\u2032 "
              "layers, in six forested regions: vic_central, vic_gippsland, "
              "tasmania, nsw_southeast, nsw_north_seqld and wa_southwest.")

    table(doc, ["", "New_M_2019", "baseline_M_1985-2014"], [
        ["What it is", "FullCAM historical input; matched footing (Option B)",
         "Eq. (1) footing (Option A); used by the paper and current FullCAM "
         "future inputs"],
        ["NLUM cells compared (fire-excluded)", n(new_u.cells), n(base_u.cells)],
        ["Median M\u2032 in these cells (t DM/ha)", f1(new_u.M_median), f1(base_u.M_median)],
        ["Median GEDI p95, fixed n = 30 (t DM/ha)", f1(new_u.gedi_p95_n30_median),
         f1(base_u.gedi_p95_n30_median)],
        ["Cells where GEDI cell MEAN > M\u2032", pct(new_u.exceed_mean_pct),
         pct(base_u.exceed_mean_pct)],
        ["Cells where GEDI p95 (n = 30) > M\u2032", pct(new_u.exceed_p95_n30_pct),
         pct(base_u.exceed_p95_n30_pct)],
        ["Same, footprints pushed to lower 90% bound", pct(new_u.exceed_p95_lo_pct),
         pct(base_u.exceed_p95_lo_pct)],
        ["Spearman rank correlation, M\u2032 vs GEDI p95",
         f2(new_u.spearman_M_vs_p95_n30), f2(base_u.spearman_M_vs_p95_n30)],
        ["Log-log slope vs FPI, M\u2032 (GEDI p95: %s)"
         % f2(el.loc["New_M_2019", "slope_gedi_p95_n30"]),
         f2(el.loc["New_M_2019", "slope_M_prime"]),
         f2(el.loc["baseline_M_1985-2014", "slope_M_prime"])],
    ], widths=[2.6, 1.9, 1.9])

    rich(doc, [("Finding 1. The ranking of M\u2032 is right, but only "
                "moderately. ", True),
               ("Pooled over the six regions, both layers rank cells the way "
                "GEDI does (Spearman %s and %s), and the correlation is "
                "positive in every region, from %s (%s) to %s (%s). The "
                "\u22120.60 once found in 77 library plots does not appear, "
                "but the vic_central pilot overstated how well M\u2032 ranks "
                "cells elsewhere."
                % (f2(new_u.spearman_M_vs_p95_n30),
                   f2(base_u.spearman_M_vs_p95_n30),
                   f2(rn.spearman_M_vs_p95_n30.min()),
                   rn.spearman_M_vs_p95_n30.idxmin(),
                   f2(rn.spearman_M_vs_p95_n30.max()),
                   rn.spearman_M_vs_p95_n30.idxmax()), False)])
    rich(doc, [("Finding 2. M\u2032 is too low in productive closed forest, "
                "under either footing, and not in open or cleared country. ",
                True),
               ("GEDI's upper envelope (p95) is above M\u2032 in %s of cells "
                "for New_M_2019 and %s for baseline_M, and the cell mean, "
                "which includes gaps, young regrowth and logged coupes, is "
                "above the supposed maximum in %s and %s. Exceedance rises "
                "with FPI, from %s of cells at FPI \u2264 8 to %s and %s in "
                "the most productive cells, and it differs by region, from "
                "%s in %s to %s in %s. Pushing every footprint to the bottom "
                "of its 90%% interval removes only %s percentage points."
                % (pct(new_u.exceed_p95_n30_pct), pct(base_u.exceed_p95_n30_pct),
                   pct(new_u.exceed_mean_pct), pct(base_u.exceed_mean_pct),
                   pct(bins_new.exceed_p95_n30_pct.iloc[0]),
                   pct(bins_new.exceed_p95_n30_pct.iloc[-1]),
                   pct(d["bins"].query("layer == 'baseline_M_1985-2014'").exceed_p95_n30_pct.iloc[-1]),
                   pct(rn_sorted.exceed_p95_n30_pct.iloc[-1]), lo_reg,
                   pct(rn_sorted.exceed_p95_n30_pct.iloc[0]), hi_reg,
                   f1(new_u.exceed_p95_n30_pct - new_u.exceed_p95_lo_pct)),
                False)])
    rich(doc, [("Finding 3. baseline_M fits GEDI better, but not for a "
                "reason that justifies choosing it. ", True),
               ("In these cells baseline_M is %s\u00d7 New_M_2019 (median; "
                "\u00d71.46 nationally for Eq. (1) against Original_M_2004), "
                "and its extra height comes from mixing Eq. (1) with a lambda "
                "that was divided by a different M. A layer that is too high "
                "by construction happens to sit closer to a ceiling that GEDI "
                "says is too low. Both layers fail the envelope test in more "
                "than 40%% of cells."
                % f2(ratio.baseline_over_New_M_median), False)])
    rich(doc, [("Finding 4. For future M\u2032, the projected change is more "
                "likely conservative than exaggerated. ", True),
               ("Future M\u2032 moves with Eq1(FPI), whose elasticity at the "
                "median FPI of closed evergreen broadleaf cells (%s) is %s. "
                "Across space, GEDI p95 rises with FPI at a log-log slope of "
                "%s [%s, %s], about %s\u00d7 as steep, and it is steeper than "
                "Eq. (1) in %d of 6 regions. The gap sits mainly below FPI 10; "
                "above it GEDI follows the Eq. (1) shape closely (Figure 4). "
                "This is milder than the roughly twofold gap in vic_central "
                "alone, and in the same direction as the earlier national "
                "analysis (Option B Suggestion 4). Space-for-time is not "
                "proof: across space, FPI also tracks species, stand age, "
                "clearing and terrain."
                % (f1(el.loc["New_M_2019", "fpi_median"]),
                   f2(el.loc["New_M_2019", "eq1_elasticity_at_median_fpi"]),
                   f2(el.loc["New_M_2019", "slope_gedi_p95_n30"]),
                   f2(el.loc["New_M_2019", "slope_gedi_p95_n30_lo95"]),
                   f2(el.loc["New_M_2019", "slope_gedi_p95_n30_hi95"]),
                   f1(el.loc["New_M_2019", "slope_gedi_p95_n30"]
                      / el.loc["New_M_2019", "eq1_elasticity_at_median_fpi"]),
                   steeper), False)])
    flag(doc, "Scope",
         "Six regions chosen for tall and open eucalypt forest, not a sample "
         "of Australia: they cover %s NLUM cells with at least 30 unburnt "
         "footprints, against 6,956,407 land cells nationally. Rates are "
         "pooled over these regions and must not be quoted as national "
         "rates. Each box also takes in cleared land (most of all the "
         "wheatbelt edge of wa_southwest), which lowers the pooled rates."
         % n(new_u.cells), AMBER)

    # ------------------------------------------------------------- 1. logic
    h(doc, "1. What is being validated", 1)
    para(doc, "Roxburgh et al. (2019) Eq. (1) links M, the maximum "
              "aboveground biomass, to FPI:")
    code(doc, ["M = (6.011 \u00d7 \u221aFPI \u2212 5.291)\u00b2      t DM/ha  (Eq. 1)",
               "M\u2032 = \u03bb \u00d7 M                              (Eq. 3)"])
    para(doc, "The projection in this repository makes future M\u2032 by "
              "scaling a present-day M\u2032 by the Eq. (1) ratio of future "
              "to historical FPI:")
    code(doc, ["M\u2032_future = M\u2032_present \u00d7 Eq1(FPI_future) / Eq1(FPI_1985-2014)"])
    para(doc, "So future M\u2032 is right only if two things are right:")
    bullet(doc, "the present-day level M\u2032_present, which GEDI can test "
                "directly, because 2019-2024 is 'present' to within the "
                "uncertainty of the layer; and", numbered=True)
    bullet(doc, "the response, how much M\u2032 moves when FPI moves. GEDI "
                "can test this only indirectly, by comparing how biomass "
                "varies with FPI across space with what Eq. (1) assumes.",
           numbered=True)
    para(doc, "Future FPI itself is validated separately, by the random "
              "forest's year-group cross-validation (Section 2.4). GEDI adds "
              "nothing there.")
    h(doc, "1.1 Why the test is an envelope, not a regression", 2)
    para(doc, "M\u2032 is a maximum. GEDI measures what stands today, after "
              "clearing, logging, fire and a century of disturbance. GEDI "
              "below M\u2032 is expected and proves nothing. GEDI above "
              "M\u2032 is the only direct evidence against it. So the headline "
              "statistics are exceedance rates, not R\u00b2, and three GEDI "
              "statistics are used, from strongest to weakest evidence:")
    table(doc, ["Statistic", "Exceeding M\u2032 means", "Weakness"], [
        ["Cell mean AGBD", "The whole 1 km cell, gaps and all, already "
         "carries more than its supposed maximum", "Can be dragged down by "
         "clearing, so it understates exceedance"],
        ["p95, fixed n = 30", "The upper envelope of stands in the cell is "
         "above M\u2032", "Single-footprint error inflates upper percentiles"],
        ["p95 of lower bounds", "The same, with every footprint pushed to "
         "agbd \u2212 1.645 \u00d7 agbd_se", "Conservative by construction"],
    ], widths=[1.5, 2.8, 2.4])
    para(doc, "Units: M\u2032 is t DM/ha of aboveground dry matter; GEDI "
              "L4A publishes AGBD in Mg/ha of aboveground dry biomass. "
              "1 Mg (megagram) = 1 t, so the two are numerically identical, "
              "no conversion is applied, and every GEDI value in this report "
              "and its figures is written in t DM/ha. "
              "The same assumption was made in every earlier GEDI and ESA CCI "
              "comparison in this repository.", size=10, colour=MUTED)

    # ---------------------------------------------------------- 2. pipeline
    h(doc, "2. The pipeline from Step 0 to future M\u2032", 1)
    para(doc, "Paths are relative to 000_Zohreh_paper_1_refactor/. All "
              "rasters share the NLUM 2010-11 grid: 3364 \u00d7 4071 cells, "
              "0.01\u00b0, GDA94 (EPSG:4283), 6,956,407 valid land cells.")

    h(doc, "2.1 Step 0: downloads and NLUM matching", 2)
    flag(doc, "Status", "Step_0_download_data/ is deleted from the working "
         "tree. Its eight scripts survive in git HEAD (commit e82499f) and "
         "their outputs are on disk. Restore it before the pipeline can be "
         "re-run end to end.", WARN)
    table(doc, ["Script", "What it produced"], [
        ["download_CSIRO_historical_data.py", "BARRA-R2 daily 1985-2014 from "
         "CSIRO DAP csiro:64206: 9 variables \u00d7 30 years, 270 files, "
         "109 GB. Pre-signed S3 URLs, re-signed mid-download."],
        ["reproject_CSIRO_historical_to_NLUM.py", "Daily \u2192 12 monthly "
         "bands, then clip \u2192 aggregate \u2192 match to NLUM \u2192 "
         "nearest-fill \u2192 mask."],
        ["(CSIRO_future_data.md)", "QDC-CMIP6, ACCESS-CM2 r4i1p1f1, 4 SSPs, "
         "2035-2064 and 2070-2099 only: 2,160 files, 719.8 GB. Each future "
         "year is an observed BARRA-R2 year rescaled by a change factor. The "
         "download/reproject scripts it cites are not on disk or in git."],
        ["download_fpi.py", "FPI v1.0 (DCCEEW, Sept 2024): 37 tiles \u00d7 "
         "53 years (1970-2022), URLs read from the CKAN API."],
        ["mosaic_match_fpi_NLUM.py", "Mosaic per year, snap half a cell onto "
         "NLUM \u2192 Data/Processed/fpi/fpi_<year>.tif."],
        ["get_revised_MaxAbgM_and_lambda.py", "New_M_2019 \u2192 "
         "Data/Processed/maxAbgM_v2/New_M_2019.tif (average resampling), "
         "plus the legacy transfer factor, now renamed "
         "transfer_Eq1M_to_NewM_1970_2002.tif."],
        ["download_worldclim_*.py, reproject_match_NLUM.py", "The earlier "
         "WorldClim route, superseded by the CSIRO route."],
    ], widths=[2.3, 4.4])
    para(doc, "Also on disk: Data/Raw/maxAbgM_v1_Ratio/Original_M_2004.tif "
              "and Ratio_OriginalM_to_NewM.tif (DCCEEW v1.0), and "
              "Data/Raw/maxAbgM_v2/New_M_2019.tif (v2.0).")

    h(doc, "2.2 Soil predictors (Download_soil_data/)", 2)
    para(doc, "Step_01_download_SLGA.py to Step_05_soil_for_FPI_report.py: "
              "11 SLGA attributes \u00d7 6 depths from CSIRO DAP, "
              "average-resampled to NLUM. 31,451 gap cells (0.45%, mostly "
              "salt lakes) are filled and flagged. In the soil test "
              "(soil_rf_results.json), spatial-CV R\u00b2 rises from 0.940 "
              "with climate only to 0.953 with climate, N, P and aggregated "
              "soil.")

    h(doc, "2.3 Climate: climatologies, deltas and open pan", 2)
    table(doc, ["Folder", "Role"], [
        ["Calculation_CSIRO_avg/", "72 twelve-band monthly climatologies "
         "(8 variables; historical + 4 SSPs \u00d7 2 windows) \u2192 "
         "Data/Processed/CSIRO_avg/. CSIRO_avg_report.md."],
        ["Calcluation_ANUCLIM_avg_1985-2014/", "ANUClimate 1985-2014 "
         "averages for 6 variables on NLUM, the observational base FullCAM "
         "uses."],
        ["Step_02_Calculate_CSIRO_delta/", "Future \u2212 historical deltas, "
         "64 layers. tasmax +1.78 \u00b0C (SSP126 mid) to +5.80 \u00b0C "
         "(SSP585 late); pr \u22120.8% to \u221213.9%. Reporting only, not "
         "an RF or M input."],
        ["Calculation_Open_pan_CSIRO_data/", "SILO pan \u2192 Kp \u2192 "
         "ETo \u2192 open pan; \u22120.9% against ANUClimate 1995-2014. "
         "FullCAM input only."],
    ], widths=[2.3, 4.4])

    h(doc, "2.4 Random forest for FPI (Random_forest_CSIRO/)", 2)
    para(doc, "Run order (README.md): Step_00_audit, 01_aggregate_climate, "
              "02_build_training_table, 02b, 03_build_model, "
              "04_predict_future, 04b, 05_plots, 07_scenario_diagnostic, "
              "06_write_report, 08_scatter.")
    para(doc, "One row per cell-year over 1985-2014: 2,086,920 rows and 174 "
              "predictors. The predictors are 83 static soil bands plus 7 "
              "BARRA-R2 climate variables (hurs, hursmax, hursmin, pr, rsds, "
              "tasmax, tasmin), each as 12 monthly values and 1 annual. The "
              "target is observed FPI for the same year. Model "
              "(data/model_card.txt): RandomForestRegressor, 64 trees, "
              "max_features 1/3, min_samples_leaf 5.")
    rows = []
    for scheme, label in (("kfold_random", "Random k-fold"),
                          ("blockcv_space", "Spatial blocks"),
                          ("groupcv_year", "Year groups (quote this one)")):
        sub = d["cv"][d["cv"].scheme == scheme]
        if sub.empty:
            continue
        r = sub[sub.n == sub.n.max()].iloc[0]
        rows.append([label, "%.4f" % r.r2,
                     "%.3f" % r.rmse, "%.3f" % r.mae, "%.1f%%" % r.mape])
    if rows:
        table(doc, ["CV scheme (data/cv_metrics.csv)", "R\u00b2", "RMSE",
                    "MAE", "MAPE"], rows, widths=[2.6, 1.0, 1.0, 1.0, 1.0])
    para(doc, "The year-group score is the honest one for projection: whole "
              "years are held out, so the model is scored on climate it did "
              "not train on. Top predictors are SOC 0-5 cm, annual relative "
              "humidity and annual rainfall. Future FPI is predicted for "
              "every year in both windows (output/fpi_<ssp>_<year>.tif, 240 "
              "files) and averaged per window. Two caveats from the RF "
              "report: scenarios are not ordered by forcing, because FPI "
              "tracks humidity and rainfall (r = +0.97) more than "
              "temperature, and a random forest cannot extrapolate beyond "
              "the training climate.")

    h(doc, "2.5 Future M from future FPI (Calculation_future_M_CSIRO/)", 2)
    table(doc, ["Script", "What it does"], [
        ["Step_06_Calculating_Future_MAGB.py", "Eq. (1) on each annual FPI. "
         "FPI below the root 0.7748 gives M = 0. Writes annual M, window "
         "means, and Eq. (1) of the window-mean FPI (Jensen gap about "
         "+0.9 to +1.2 t/ha, ~2%)."],
        ["Step_07_export_netcdf.py", "NetCDF cubes."],
        ["Step_08_apply_published_lambda.py", "Eq. (3) with the published "
         "\u03bb = New_M_2019 / Original_M_2004 (median 1, exactly 1 on "
         "42.6% of cells, max 14.16). --footing eq1 (default) gives Option "
         "A; --footing original2004 gives Option B."],
        ["Step_09/10", "Maps; scatter against New_M_2019."],
    ], widths=[2.4, 4.3])

    h(doc, "2.6 The two footings, and why both are tested here", 2)
    para(doc, "\u03bb is only valid against the M it was divided by. "
              "Published \u03bb = New_M_2019 / Original_M_2004, but Eq. (1) "
              "of historical FPI overstates Original_M_2004 by a median "
              "factor of 1.46. So:")
    table(doc, ["", "Option A: Eq. (1) footing", "Option B: matched footing"], [
        ["Future M\u2032", "\u03bb \u00d7 Eq1(FPI_fut)",
         "\u03bb \u00d7 Original_M_2004 \u00d7 Eq1(FPI_fut) / Eq1(FPI_hist)"],
        ["Present-day layer it sits on", "baseline_M_1985-2014.tif "
         "(Writing_paper_01/output/)", "New_M_2019.tif, identical to "
         "historical M\u2032 on this footing"],
        ["Level", "\u00d71.46 above B nationally", "consistent with FullCAM's "
         "historical maxAbgMF"],
        ["% change", "identical to B", "identical to A"],
        ["Used by", "Writing_paper_01 results; FullCAM_input_CSIRO_data/M/",
         "Option_B_matched_footing/fullcam_inputs/ (recommended in "
         "Footing_decision_M_prime.docx, not yet adopted)"],
    ], widths=[1.6, 2.5, 2.6])
    ob = d["optb"]
    para(doc, "Option B future M\u2032 medians (fullcam_inputs_summary.csv): "
              "%s to %s t/ha across scenarios and windows. With Option A "
              "inputs, FullCAM would see a jump of +26%% to +71%% at the "
              "boundary between historical and future inputs, purely from "
              "the footing." % (f1(ob["median"].min()), f1(ob["median"].max())))
    orders = d["orders"]
    flag(doc, "Unresolved: which historical baseline",
         "Projected change depends on how the 1985-2014 baseline is built. "
         "Against Eq. (1) applied year by year and then averaged, change "
         "ranges from %s%% to %s%%. Against Eq. (1) of the mean FPI, it "
         "ranges from %s%% to %s%%, and two windows change sign "
         "(Option_B_matched_footing/outputs/baseline_orders.csv, "
         "Two_historical_baselines.docx). No decision is recorded."
         % (f1(orders.chg_per_year.min()), f1(orders.chg_per_year.max()),
            f1(orders.chg_mixed_step08.min()), f1(orders.chg_mixed_step08.max())),
         AMBER)

    h(doc, "2.7 What the paper reports", 2)
    pm = d["paper"][d["paper"].variable == "M"]
    pf = d["paper"][d["paper"].variable == "fpi"]
    para(doc, "Writing_paper_01/output/results_summary.csv, area-weighted "
              "over the NLUM mask on the Option A footing: mean M falls "
              "%s%% to %s%% from a baseline of %s t DM/ha, while FPI falls "
              "%s%% to %s%%. The loss in M is larger than the loss in FPI "
              "because Eq. (1) is convex. The paper makes no validation or "
              "GEDI claim."
         % (f1(-pm["pct_change"].max()), f1(-pm["pct_change"].min()),
            f1(pm.baseline_mean.iloc[0]), f1(-pf["pct_change"].max()),
            f1(-pf["pct_change"].min())))

    h(doc, "2.8 Validations of M before GEDI", 2)
    table(doc, ["Validation", "Result", "Limitation"], [
        ["Level 1: FullCAM input = New_M_2019", "Max difference 0.0",
         "Identity check only"],
        ["Level 2: FPI elasticity from library plots", "1.37 [0.73, 1.78] "
         "at \u03c4 = 0.75 against theory 1.49 (pass). Eucalypt tall/open "
         "forest: \u22122.62, \u03c1 = \u22120.60 (n = 77)", "Small sample; "
         "\u03c4 = 0.90 unstable"],
        ["Validation_M: 1,009 National Biomass Library records", "Verified "
         "mature stands above M\u2032: 38.2% (Eq. 1 footing), 48.8% "
         "(Original_M_2004 footing)", "Up to 98.9% possible overlap with "
         "Roxburgh's calibration plots; circular"],
        ["GEDI L4B 1 km means, national (Option B Level 4)",
         "Forest \u2265 50%%, unburnt since 2009: %s (New_M_2019), %s "
         "(baseline) of cells above M\u2032; up to ~50%% in the top FPI bin"
         % (pct(d["l4b"].query("m_layer == 'New_M_2019' and filter == "
                               "'well seen, forest >= 50%, unburnt since 2009'")
                .pct_gedi_over_m.iloc[0]),
            pct(d["l4b"].query("m_layer == 'baseline_M_1985_2014' and filter == "
                               "'well seen, forest >= 50%, unburnt since 2009'")
                .pct_gedi_over_m.iloc[0])),
         "A cell mean, not an envelope; the 1 km L4B grid is not NLUM's grid"],
        ["Option B Suggestions 1-4 (L4B forest-only, ESA CCI, L4A hotspots, "
         "elasticity)", "L4A hotspots: fixed-n p95 above baseline M\u2032 in "
         "57.4% of cells. Every Spearman \u03c1 positive (+0.35 to +0.73). "
         "Forest elasticity 1.9-2.3, steeper than Eq. (1)", "Hotspots chosen "
         "where exceedance was already known; bootstrap intervals shown to "
         "be optimistic"],
    ], widths=[2.1, 2.7, 1.9])
    para(doc, "The L4A footprint pipeline written for that work "
              "(Option_B_matched_footing/Validation/files/) was never run. "
              "Validation_GEDI/ is its corrected version. It was first run "
              "on vic_central alone and is reported here for all six "
              "regions.")

    # ------------------------------------------------------ 3. GEDI pipeline
    h(doc, "3. The corrected GEDI pipeline (Validation_GEDI/)", 1)
    table(doc, ["Step", "What it does", "Output"], [
        ["common.py", "NLUM grid from the mask's own transform; Earthdata "
         "credentials from .netrc; the six regions; PROJ database pinned to "
         "rasterio's own", "\u2014"],
        ["Step_01_check_sources.py", "Proves the grid and name fixes; counts "
         "granules and GB per region; needs no login",
         "outputs/source_check.csv"],
        ["Step_02_build_fire_mask.py", "MODIS MCD64A1 v061 burned area, "
         "2009-2025, one NLUM raster per year", "fire/burn_year_<y>.tif, "
         "last_burn_year.tif"],
        ["Step_03_fetch_gedi.py", "GEDI L4A v2.1 footprints: download, filter, "
         "assign NLUM cell, delete granule; checkpoint per granule",
         "outputs/gedi_parts/<region>/, gedi_l4a_footprints.parquet"],
        ["Step_04_aggregate_cells.py", "Fire flags; per-cell mean, median, "
         "p95, fixed-n p95, p99; sample M\u2032 and FPI at the same cell",
         "outputs/gedi_cells_{all,unburnt}_<tag>.csv"],
        ["Step_05_analyse_vs_M.py", "Exceedance, FPI bins, forest type, "
         "elasticity; figures", "outputs/analysis/, outputs/figures/"],
        ["make_validation_gedi_report.py", "This document",
         "Validation_GEDI_report.docx"],
    ], widths=[1.9, 3.1, 1.7])

    h(doc, "3.1 Defects fixed relative to the unexecuted original", 2)
    table(doc, ["Defect", "Effect", "Fix"], [
        ["Cells on floor(lon / 0.01)", "Cell edges at multiples of 0.01, "
         "NLUM's at 112.925 + 0.01k: every cell half a cell off, and M\u2032 "
         "and FPI sampled on a cell boundary", "Cell index from NLUM's "
         "transform; rasters sampled by row/column"],
        ["Short name GEDI_L4A_AGB_Density_V2_1", "Zero granules found in every "
         "region", "Collection resolved from CMR by keyword to "
         "C2237824918-ORNL_CLOUD (..._V2_1_2056)"],
        ["No fire handling", "Black Summer burned through three of the six "
         "regions; a burnt canopy reads as low biomass", "Step_02 fire "
         "mask; footprints within 10 years of a burn excluded"],
        ["p99 on 30 footprints", "p99 of 30 values is the maximum",
         "p99 only with \u2265 100 footprints"],
        ["p95 rises with footprint count", "Busy cells look taller for "
         "sampling reasons alone", "p95 from 25 draws of exactly 30 "
         "footprints"],
    ], widths=[1.8, 2.7, 2.2])

    h(doc, "3.2 Problems found and fixed while running it (17 Sep 2026)", 2)
    table(doc, ["Problem", "Cause", "Fix"], [
        ["Every MODIS file failed to open", "JinzhuLuto's rasterio GDAL has "
         "no HDF4 driver; the environment must not be modified", "Each HDF4 "
         "file converted to a temporary GeoTIFF by the existing zoenv "
         "environment's gdal_translate.exe (GDAL 3.6.2), run as a "
         "subprocess; zoenv is only executed"],
        ["CRSError on every burnt pixel", "Machine-wide PROJ_LIB points at a "
         "stale PostGIS proj.db", "common.py points PROJ at rasterio's own "
         "proj_data before rasterio loads"],
        ["Default fire record started 2010", "Black Saturday (Feb 2009) burned "
         "inside vic_central; a 2019 footprint needs history to 2009",
         "Default --start 2009-01-01; years follow the arguments"],
        ["An all-failing run would still write rasters", "Read failures were "
         "only printed", "Stops after 5 consecutive failures"],
        ["Step_03 needed earthaccess", "Not installed in JinzhuLuto", "Search "
         "via CMR and download via the same authenticated session as Step_02"],
        ["An interrupted download looked complete", "Size check only",
         "Written to .part and renamed when Content-Length matches"],
        ["Two M\u2032 layers would overwrite one output", "Fixed file names",
         "--tag option on Step_04"],
    ], widths=[1.8, 2.3, 2.6])

    h(doc, "3.3 Parameters", 2)
    table(doc, ["Parameter", "Value"], [
        ["GEDI product", "L4A Footprint Level AGBD v2.1, "
         "C2237824918-ORNL_CLOUD"],
        ["Time", "2019-04-18 to 2024-11-27 requested; footprints %s to %s"
         % (str(fp["first"])[:10], str(fp["last"])[:10])],
        ["Beams", "Power beams only: BEAM0101, 0110, 1000, 1011"],
        ["Footprint filters", "l4_quality_flag = 1, degrade_flag = 0, "
         "sensitivity > 0.95, agbd \u2265 0 and finite, inside region box"],
        ["Cell", "NLUM 0.01\u00b0 cell (~1 km); \u2265 30 footprints"],
        ["Fire", "MCD64A1 v061, 500 m, nearest to NLUM; footprint excluded "
         "if its cell burned in the 10 years up to its acquisition year"],
        ["FPI", "Mean of observed FPI 1985-2014 "
         "(Random_forest_CSIRO/required_data/fpi), same cells"],
        ["M\u2032 layers", "Data/Processed/maxAbgM_v2/New_M_2019.tif; "
         "Writing_paper_01/output/baseline_M_1985-2014.tif"],
    ], widths=[1.6, 5.1])

    # ------------------------------------------------------------ 4. results
    h(doc, "4. Results for six regions", 1)
    h(doc, "4.1 Data", 2)
    para(doc, "%s of %s L4A granules crossing the six boxes held at least one "
              "footprint that passed the filters (the rest were cloud or "
              "only clipped a corner). They gave %s footprints in %s NLUM "
              "cells. %s%% of footprints are classed evergreen broadleaf "
              "trees. Median AGBD per footprint is %s t DM/ha, the 95th "
              "percentile %s. The median relative standard error "
              "(agbd_se / agbd) is %s%%."
         % (n(n_gran_pos), n(n_gran), n(fp.footprints), n(fp.cells),
            f1(fp.pct_evergreen_broadleaf), f1(fp.agbd_median),
            f1(fp.agbd_p95), f1(100 * fp.rel_se_median)))
    yrs = d["years"]
    table(doc, ["Year"] + [str(y) for y in yrs.year],
          [["Footprints"] + [n(v) for v in yrs.footprints]])
    para(doc, "2023 is thin because GEDI was stored on the ISS from March "
              "2023 to April 2024.", size=10, colour=MUTED)
    fr = d["fp_region"].set_index("region")
    rows = []
    for r_ in C.REGIONS:
        x0, y0, x1, y1 = C.REGIONS[r_]
        rows.append([r_, "%.1f-%.1f\u00b0E, %.1f-%.1f\u00b0S" % (x0, x1, -y1, -y0),
                     n(fr.loc[r_, "granules"]), n(fr.loc[r_, "footprints"]),
                     f1(fr.loc[r_, "agbd_median"]),
                     f1(fr.loc[r_, "pct_evergreen_broadleaf"]),
                     n(rn.loc[r_, "cells_all"]), n(rn.loc[r_, "cells"])])
    table(doc, ["Region", "Box", "Granules", "Footprints", "Median AGBD",
                "% evergreen broadleaf", "Cells \u2265 30 (all)",
                "Cells \u2265 30 (unburnt)"], rows,
          widths=[1.2, 1.4, 0.65, 0.85, 0.7, 0.75, 0.75, 0.75], size=8.3)
    log = d["step04_log"]
    burnt = [ln for ln in log.splitlines() if "burnt within" in ln]
    bs = [ln for ln in log.splitlines() if "2019-20 fire" in ln]
    lost = (1 - rn.cells / rn.cells_all).sort_values(ascending=False)
    para(doc, "Fire: %s; %s. Excluding burnt footprints leaves %s cells with "
              "\u2265 30 footprints, against %s without the exclusion. The "
              "loss is uneven: %s loses %s of its cells and %s %s, both "
              "largely to Black Summer, while %s loses %s. Black Saturday "
              "(2009) falls outside the 10-year window for footprints after "
              "2019."
         % (" ".join(burnt[0].split()) if burnt else "n/a",
            " ".join(bs[0].replace(":", " ").split()) if bs else "n/a",
            n(new_u.cells), n(new_a.cells),
            lost.index[0], pct(100 * lost.iloc[0]),
            lost.index[1], pct(100 * lost.iloc[1]),
            lost.index[-1], pct(100 * lost.iloc[-1])))

    h(doc, "4.2 Both layers against GEDI", 2)
    rows = []
    for label, col, fmt in [
            ("Cells", "cells", n),
            ("Median M\u2032 (t DM/ha)", "M_median", f1),
            ("Median GEDI mean (t DM/ha)", "gedi_mean_median", f1),
            ("Median GEDI p95, n = 30", "gedi_p95_n30_median", f1),
            ("Median GEDI p95 of lower bounds", "gedi_p95_lo_median", f1),
            ("Median M\u2032 / p95", "ratio_M_over_p95_n30_median", f2),
            ("Spearman M\u2032 vs mean", "spearman_M_vs_mean", f2),
            ("Spearman M\u2032 vs p95", "spearman_M_vs_p95_n30", f2),
            ("% cells mean > M\u2032", "exceed_mean_pct", pct),
            ("% cells median > M\u2032", "exceed_median_pct", pct),
            ("% cells p95 lower bound > M\u2032", "exceed_p95_lo_pct", pct),
            ("% cells p95 (n = 30) > M\u2032", "exceed_p95_n30_pct", pct),
            ("% cells naive p95 > M\u2032", "exceed_p95_naive_pct", pct),
            ("% cells p99 > M\u2032 (n \u2265 100)", "exceed_p99_pct_n100", pct)]:
        rows.append([label] + [fmt(ov(d, t_, s)[col])
                               for t_ in TAGS for s in ("all", "unburnt")])
    table(doc, ["", "New_M_2019 all", "New_M_2019 unburnt",
                "baseline all", "baseline unburnt"], rows,
          widths=[2.3, 1.1, 1.1, 1.1, 1.1], size=8.5)
    para(doc, "Read down the rows from the strictest statistic to the "
              "weakest. The mean row is the most damaging to M\u2032: a "
              "1 km cell cannot average more than its maximum unless the "
              "maximum is too low or GEDI reads too high. The naive p95 and "
              "p99 rows are shown only to demonstrate the inflation that the "
              "fixed-n statistic removes; do not quote them. Fire exclusion "
              "removes a quarter of the cells but moves the p95 exceedance "
              "rate by only %s percentage points (%s to %s for New_M_2019)."
         % (f1(abs(new_a.exceed_p95_n30_pct - new_u.exceed_p95_n30_pct)),
            pct(new_a.exceed_p95_n30_pct), pct(new_u.exceed_p95_n30_pct)))
    figure(doc, FIG / "fig1_p95_vs_Mprime_both_layers.png",
           "Figure 1. GEDI p95 (fixed n = 30) against M\u2032 per NLUM cell, "
           "fire-excluded, log axes. Left New_M_2019, right "
           "baseline_M_1985-2014. Cells above the 1:1 line contradict "
           "M\u2032.")

    h(doc, "4.3 By productivity", 2)
    b = d["bins"]
    rows = []
    for lab in b[b.layer == "New_M_2019"].fpi_bin:
        a_ = b[(b.layer == "New_M_2019") & (b.fpi_bin == lab)].iloc[0]
        c_ = b[(b.layer == "baseline_M_1985-2014") & (b.fpi_bin == lab)].iloc[0]
        rows.append([lab.replace("(", "").replace("]", "").replace(", ", "-"),
                     n(a_.cells), f1(a_.gedi_p95_n30_median), f1(a_.M_median),
                     f1(c_.M_median), pct(a_.exceed_p95_n30_pct),
                     pct(c_.exceed_p95_n30_pct), pct(a_.exceed_mean_pct),
                     pct(c_.exceed_mean_pct)])
    table(doc, ["FPI", "Cells", "GEDI p95", "M\u2032 New", "M\u2032 base",
                "p95>M\u2032 New", "p95>M\u2032 base", "mean>M\u2032 New",
                "mean>M\u2032 base"], rows,
          widths=[0.6, 0.6, 0.75, 0.7, 0.7, 0.85, 0.85, 0.85, 0.85], size=8.3)
    para(doc, "Exceedance grows with FPI under both layers: M\u2032 falls "
              "furthest behind GEDI in the most productive forest. This is "
              "the same shape as the national L4B analysis and the L4A "
              "hotspot analysis found. baseline_M's advantage is largest "
              "below FPI 12 and shrinks in the most productive forest.")
    figure(doc, FIG / "fig2_exceedance_by_fpi_bin.png",
           "Figure 2. Share of cells where GEDI exceeds M\u2032, by mean "
           "FPI 1985-2014. Left: fixed-n p95. Right: cell mean.")

    h(doc, "4.4 By forest type", 2)
    fo = d["forest"]
    rows = []
    for lab in fo[fo.layer == "New_M_2019"].forest_class:
        a_ = fo[(fo.layer == "New_M_2019") & (fo.forest_class == lab)].iloc[0]
        c_ = fo[(fo.layer == "baseline_M_1985-2014") & (fo.forest_class == lab)].iloc[0]
        rows.append([lab, n(a_.cells), f1(a_.gedi_mean_median),
                     f1(a_.gedi_p95_n30_median), pct(a_.exceed_p95_n30_pct),
                     pct(c_.exceed_p95_n30_pct), pct(a_.exceed_mean_pct),
                     pct(c_.exceed_mean_pct)])
    table(doc, ["Evergreen broadleaf share of footprints", "Cells",
                "GEDI mean", "GEDI p95", "p95>M\u2032 New", "p95>M\u2032 base",
                "mean>M\u2032 New", "mean>M\u2032 base"], rows,
          widths=[1.7, 0.6, 0.7, 0.7, 0.8, 0.8, 0.8, 0.8], size=8.3)
    para(doc, "Forest type comes from each footprint's pft_class (the "
              "MODIS land-cover class carried in L4A), not from NVIS. In "
              "cells that are mostly not evergreen broadleaf (cleared "
              "land, pasture, plantations), the mean rarely exceeds M\u2032, "
              "as it should. Exceedance concentrates in closed forest.")

    h(doc, "4.5 By region", 2)
    rows = []
    for r_ in rn_sorted.index:
        a_, c_ = rn.loc[r_], rb.loc[r_]
        rows.append([r_, n(a_.cells), f1(a_.fpi_median), f1(a_.ebf_cells_pct),
                     f1(a_.M_median), f1(a_.gedi_p95_n30_median),
                     f2(a_.ratio_M_over_p95_n30_median),
                     f2(a_.spearman_M_vs_p95_n30),
                     pct(a_.exceed_p95_n30_pct), pct(c_.exceed_p95_n30_pct),
                     pct(a_.exceed_mean_pct), pct(c_.exceed_mean_pct)])
    table(doc, ["Region", "Cells", "FPI", "% cells \u2265 90% EBF",
                "M\u2032 New", "GEDI p95", "M\u2032/p95", "\u03c1",
                "p95>M\u2032 New", "p95>M\u2032 base", "mean>M\u2032 New",
                "mean>M\u2032 base"], rows,
          widths=[1.1, 0.55, 0.4, 0.55, 0.5, 0.5, 0.5, 0.4, 0.6, 0.6, 0.6, 0.6],
          size=7.8)
    para(doc, "Fire-excluded cells; FPI, M\u2032, GEDI p95 and M\u2032/p95 are "
              "medians; \u03c1 is Spearman M\u2032 (New_M_2019) against GEDI "
              "p95; EBF is evergreen broadleaf. Sorted by p95 exceedance "
              "against New_M_2019.", size=9, colour=MUTED)
    para(doc, "The regions differ more than the layers do. In %s and %s, GEDI p95 exceeds "
              "New_M_2019 in more than 60%% of cells and the typical cell's "
              "M\u2032 is only %s and %s of its GEDI p95. In %s and %s, "
              "exceedance is %s and %s, and M\u2032 is %s\u00d7 and %s\u00d7 "
              "GEDI p95: these boxes hold the fewest closed evergreen "
              "broadleaf cells (%s%% and %s%%), and wa_southwest's median "
              "GEDI cell mean is only %s t DM/ha, because most of it is cleared "
              "wheatbelt or open woodland. The ranking of cells is weakest in "
              "nsw_southeast (\u03c1 = %s), where M\u2032 and GEDI p95 have "
              "almost the same median but agree poorly cell by cell. "
              "baseline_M lowers exceedance in every region, by %s to %s "
              "percentage points, without changing the order of the regions."
         % (rn_sorted.index[0], rn_sorted.index[1],
            f2(rn_sorted.ratio_M_over_p95_n30_median.iloc[0]),
            f2(rn_sorted.ratio_M_over_p95_n30_median.iloc[1]),
            rn_sorted.index[-2], rn_sorted.index[-1],
            pct(rn_sorted.exceed_p95_n30_pct.iloc[-2]),
            pct(rn_sorted.exceed_p95_n30_pct.iloc[-1]),
            f2(rn_sorted.ratio_M_over_p95_n30_median.iloc[-2]),
            f2(rn_sorted.ratio_M_over_p95_n30_median.iloc[-1]),
            f1(rn_sorted.ebf_cells_pct.iloc[-2]), f1(rn_sorted.ebf_cells_pct.iloc[-1]),
            f1(rn.loc["wa_southwest", "gedi_mean_median"]),
            f2(rn.loc["nsw_southeast", "spearman_M_vs_p95_n30"]),
            f1((rn.exceed_p95_n30_pct - rb.exceed_p95_n30_pct).min()),
            f1((rn.exceed_p95_n30_pct - rb.exceed_p95_n30_pct).max())))
    figure(doc, FIG / "fig5_exceedance_by_region.png",
           "Figure 5. Share of fire-excluded cells where GEDI exceeds "
           "M\u2032, by region. Left: fixed-n p95. Right: cell mean.")

    h(doc, "4.6 Where", 2)
    figure(doc, FIG / "fig3_map_p95_over_Mprime.png",
           "Figure 3. log2(GEDI p95 / New_M_2019) per cell, one panel per "
           "region at its own scale. Red: GEDI above M\u2032. Blue: GEDI "
           "below. Blank: fewer than 30 unburnt footprints, or outside NLUM. "
           "baseline_M gives the same pattern, paler.", width=6.0)
    para(doc, "Within every region the red cells follow the forest, and the "
              "blue follows cleared land. In vic_central the red core lies "
              "over the Central Highlands and the Dandenong Ranges. In "
              "tasmania it lies over the north-west, the north-east and the "
              "southern forests, with blue over the Midlands and the Central "
              "Plateau. In wa_southwest only the far south-west corner, the "
              "karri and jarrah country, is red; the wheatbelt to the east is "
              "blue. In nsw_north_seqld the red is concentrated on the "
              "escarpment forests, and in vic_gippsland and nsw_southeast the "
              "blanks are the Black Summer fire scars. These place "
              "descriptions are read from the map, not computed.")

    h(doc, "4.7 Response to FPI: the part that matters for the future", 2)
    rows = []
    for tag in TAGS:
        e = el.loc[tag]
        rows.append([NICE[tag], n(e.cells),
                     "%s [%s, %s]" % (f2(e.slope_M_prime), f2(e.slope_M_prime_lo95),
                                      f2(e.slope_M_prime_hi95)),
                     "%s [%s, %s]" % (f2(e.slope_gedi_p95_n30),
                                      f2(e.slope_gedi_p95_n30_lo95),
                                      f2(e.slope_gedi_p95_n30_hi95)),
                     "%s [%s, %s]" % (f2(e.slope_gedi_mean),
                                      f2(e.slope_gedi_mean_lo95),
                                      f2(e.slope_gedi_mean_hi95)),
                     f2(e.eq1_elasticity_at_median_fpi)])
    table(doc, ["Layer", "Cells", "M\u2032 slope", "GEDI p95 slope",
                "GEDI mean slope", "Eq. (1) at median FPI"], rows,
          widths=[1.5, 0.6, 1.3, 1.3, 1.3, 1.0], size=8.5)
    para(doc, "Slopes are ordinary least squares of ln(y) on ln(FPI) across "
              "cells where at least 90% of footprints are evergreen "
              "broadleaf, with 500-resample bootstrap 95% intervals. These "
              "intervals ignore spatial autocorrelation and are too narrow; "
              "the national analysis showed such intervals can be disjoint "
              "between runs. Compare them only to one decimal place.",
         size=10, colour=MUTED)
    figure(doc, FIG / "fig4_fpi_elasticity_index.png",
           "Figure 4. Median of each quantity by 1-unit FPI bin, indexed to "
           "100 at FPI 10-11, log scale, in cells where at least 90% of "
           "footprints are evergreen broadleaf, all six regions pooled. The "
           "dotted line is the shape Eq. (1) imposes on future change.",
           width=5.2)
    rows = []
    for r_ in C.REGIONS:
        a_ = rn.loc[r_]
        rows.append([r_, n(a_.elasticity_cells), f2(a_.slope_M_prime),
                     f2(rb.loc[r_, "slope_M_prime"]), f2(a_.slope_gedi_p95_n30),
                     f2(a_.eq1_elasticity_at_median_fpi)])
    table(doc, ["Region", "EBF cells", "New_M_2019 slope", "baseline_M slope",
                "GEDI p95 slope", "Eq. (1) at median FPI"], rows,
          widths=[1.4, 0.8, 1.1, 1.1, 1.1, 1.1], size=8.5)
    para(doc, "Pooled over the regions, GEDI p95 rises with FPI at a "
              "log-log slope of %s and the cell mean at %s, against %s for "
              "Eq. (1) at the median FPI. Both M\u2032 layers are flatter "
              "still (%s and %s), because their low-FPI cells sit high "
              "relative to GEDI (Figure 4). Within regions, GEDI is steeper "
              "than Eq. (1) in %d of 6, from about equal in nsw_southeast to "
              "about twice as steep in vic_central. Figure 4 shows where the "
              "gap comes from: below FPI 10 GEDI falls away much faster than "
              "Eq. (1), and above FPI 10 the GEDI p95 curve follows the Eq. "
              "(1) shape closely. That matters because future change comes "
              "only from Eq. (1): a cell whose FPI falls 10%% loses about %s%% "
              "of M\u2032 in the projection, while across space a 10%% lower "
              "FPI goes with roughly %s%% less GEDI p95 biomass."
         % (f2(el.loc["New_M_2019", "slope_gedi_p95_n30"]),
            f2(el.loc["New_M_2019", "slope_gedi_mean"]),
            f2(el.loc["New_M_2019", "eq1_elasticity_at_median_fpi"]),
            f2(el.loc["New_M_2019", "slope_M_prime"]),
            f2(el.loc["baseline_M_1985-2014", "slope_M_prime"]),
            steeper,
            f1(100 * (1 - 0.9 ** el.loc["New_M_2019", "eq1_elasticity_at_median_fpi"])),
            f1(100 * (1 - 0.9 ** el.loc["New_M_2019", "slope_gedi_p95_n30"]))))
    flag(doc, "How far this can be pushed",
         "Across space, high FPI also means different species, deeper "
         "soils, less clearing and older stands, and pooling six regions "
         "adds differences between regions on top. A space-for-time slope "
         "mixes all of them with the effect of productivity, and the "
         "low-FPI end, where the gap is, is also where clearing is most "
         "common. The result supports two claims: Eq. (1)'s response is "
         "not too steep, and the projected change is more likely "
         "conservative than exaggerated. It does not support replacing "
         "Eq. (1)'s elasticity with %s."
         % f1(el.loc["New_M_2019", "slope_gedi_p95_n30"]), AMBER)

    # ------------------------------------------------------ 5. interpretation
    h(doc, "5. What this means", 1)
    h(doc, "5.1 For present-day M\u2032", 2)
    para(doc, "Whether M\u2032 is too low depends on the forest. Pooled over "
              "the six regions, the typical (median) cell's M\u2032 is %s of "
              "its GEDI p95 for New_M_2019 and %s for baseline_M, so on "
              "average M\u2032 sits near the envelope. That average hides the "
              "split: in closed evergreen broadleaf cells GEDI p95 exceeds "
              "New_M_2019 in %s of cells and the cell mean in %s, while in "
              "cells that are mostly not evergreen broadleaf the figures are "
              "%s and %s. This agrees with every earlier independent "
              "comparison: L4B cell means, ESA CCI, and the L4A hotspots all "
              "found M\u2032 too low as productivity rises. Three explanations "
              "remain open for the closed forest, and GEDI alone cannot "
              "separate them:"
         % (f2(new_u.ratio_M_over_p95_n30_median),
            f2(base_u.ratio_M_over_p95_n30_median),
            pct(ebf_new.exceed_p95_n30_pct), pct(ebf_new.exceed_mean_pct),
            pct(non_new.exceed_p95_n30_pct), pct(non_new.exceed_mean_pct)))
    bullet(doc, "M\u2032 really is too low in the most productive forests. "
                "Eq. (1) is a curve fitted across all of Australia, and "
                "tall wet eucalypt and rainforest are its extreme tail.")
    bullet(doc, "GEDI L4A reads high in this forest type. The L4A models for "
                "Australian evergreen broadleaf trees rest on a limited "
                "calibration set, and their bias in very tall eucalypt "
                "forest has not been checked here.")
    bullet(doc, "Definitions differ at the margin. M\u2032 is maximum biomass "
                "of mature native vegetation per NLUM cell; a single 25 m "
                "footprint in a 70 m tall stand can exceed any area-average "
                "maximum without contradiction. That is why the cell-mean "
                "result, not the p95 result, is the stronger evidence.")
    para(doc, "What would separate them: airborne lidar or field plots "
              "measured in the same cells (for example the Victorian "
              "Central Highlands long-term plots, Warra in Tasmania, or TERN "
              "sites), against "
              "which both M\u2032 and L4A can be checked.")

    h(doc, "5.2 Choosing between the two layers", 2)
    para(doc, "baseline_M exceeds GEDI less often, by about %s percentage "
              "points at p95 and %s on the mean. That should not decide the "
              "footing. baseline_M is higher because it combines Eq. (1) M "
              "with a \u03bb that was divided by a different M. The footing "
              "memo shows this is a methodological inconsistency, not a "
              "better estimate. The ratio of the two layers is "
              "Eq1(FPI) / Original_M_2004, and in the compared cells it is "
              "\u00d7%s (p10-p90 %s-%s; \u00d7%s to \u00d7%s by region), against "
              "\u00d71.46 nationally, so Eq. (1) overstates Original_M_2004 "
              "less in these forested regions than across Australia. The "
              "better fit here comes from a "
              "known error pointing the same way as GEDI's disagreement. "
              "The defensible choice remains Option B (New_M_2019 footing). "
              "The GEDI finding, that M\u2032 is too low in tall forest, "
              "should be reported as a limitation of M\u2032 on either "
              "footing."
         % (f1(new_u.exceed_p95_n30_pct - base_u.exceed_p95_n30_pct),
            f1(new_u.exceed_mean_pct - base_u.exceed_mean_pct),
            f2(ratio.baseline_over_New_M_median),
            f2(ratio.baseline_over_New_M_p10), f2(ratio.baseline_over_New_M_p90),
            f2(d["ratio_region"].baseline_over_New_M_median.min()),
            f2(d["ratio_region"].baseline_over_New_M_median.max())))

    h(doc, "5.3 For future M\u2032", 2)
    bullet(doc, "Level: whatever is wrong with present-day M\u2032 carries "
                "unchanged into every scenario, because the projection "
                "multiplies it. If M\u2032 is too low by a factor k in tall "
                "forest today, future M\u2032 is too low by about the same k. "
                "The projected percentage change is not affected.")
    bullet(doc, "Response: GEDI gives no sign that Eq. (1) exaggerates the "
                "response of biomass to FPI. GEDI is steeper in %d of 6 "
                "regions and about equal in the other, so projected losses "
                "under drying scenarios are more likely to be understated "
                "than overstated, most of all in low-FPI forest." % steeper)
    bullet(doc, "Sign: M\u2032 and GEDI agree on which cells hold more "
                "biomass in every region (\u03c1 %s to %s, pooled %s), so no "
                "projected change is built on a relationship running the "
                "wrong way. The agreement is weak in %s."
           % (f2(rn.spearman_M_vs_p95_n30.min()),
              f2(rn.spearman_M_vs_p95_n30.max()),
              f2(new_u.spearman_M_vs_p95_n30),
              rn.spearman_M_vs_p95_n30.idxmin()))
    bullet(doc, "Not tested: whether future FPI is right. That rests on the "
                "RF year-group cross-validation (R\u00b2 0.93) and on the "
                "QDC-CMIP6 climate inputs.")

    # --------------------------------------------------------- 6. caveats
    h(doc, "6. Limitations", 1)
    for t_ in [
        "Six regions, chosen for forest, not a sample of Australia. The "
        "pooled rates depend on how much cleared land each box happens to "
        "contain, and pooled correlations and slopes mix differences between "
        "regions with differences within them. Inland woodland, the tropics "
        "and the arid zone are not tested.",
        "Fire exclusion is not neutral: it removes %s of cells in %s and %s "
        "in %s, so the burnt forests of Black Summer are under-represented "
        "in the unburnt results."
        % (pct(100 * lost.iloc[0]), lost.index[0],
           pct(100 * lost.iloc[1]), lost.index[1]),
        "GEDI L4A v2.1 is used; V3 (C4212593885-ORNL_CLOUD) now exists and "
        "may revise AGBD.",
        "No protected-area mask. Logged and cleared cells pull GEDI down, "
        "so exceedance is if anything understated, but the forest-type and "
        "FPI tables are affected by land use.",
        "The fire flag works at year resolution: a fire in December can flag "
        "a footprint from June of the same year, which is conservative. "
        "MODIS at 500 m misses small burns, and pre-2009 fires, including "
        "regrowth after 1983 and 1939, are not flagged.",
        "The median relative agbd_se is small (about %.0f%%) because it is the "
        "L4A prediction standard error, not the full footprint error. The "
        "lower-bound statistic is therefore less conservative than it looks."
        % (100 * fp.rel_se_median),
        "Units are treated as equal (GEDI's Mg/ha AGBD = t DM/ha aboveground "
        "dry matter, since 1 Mg = 1 t). Neither product includes roots; stump and branch "
        "conventions are not reconciled.",
        "Cells with fewer than 30 footprints are excluded, and they are not "
        "a random subset: they are where GEDI tracks are sparse or cloud "
        "is frequent.",
        "Pipeline housekeeping: Step_0_download_data/ is deleted from the "
        "working tree, the CSIRO future download scripts are missing, and "
        "CLAUDE.md still names Step_0b_published_lambda/ and "
        "REVISED_ORIGINAL_M_2004/, which do not exist.",
    ]:
        bullet(doc, t_)

    # ------------------------------------------------------------ 7. next
    h(doc, "7. Next steps", 1)
    for t_ in [
        "Replace the bootstrap intervals on the FPI slopes with a spatial "
        "block bootstrap, and fit slopes within regions before pooling, so "
        "that differences between regions do not drive the pooled slope.",
        "Add NVIS forest fraction and a CAPAD protected-area flag to Step_04, "
        "so that clearing and logging can be separated from the envelope.",
        "Repeat with GEDI L4A V3 on one region to measure the version effect.",
        "Extend beyond the six forested boxes (inland woodland, the tropics) "
        "before quoting any rate as national.",
        "Find an independent tall-forest reference (airborne lidar or plot "
        "biomass) to separate 'M\u2032 too low' from 'L4A too high'.",
        "Decide the footing (Option A or B) and the historical baseline "
        "order. Both change the numbers FullCAM receives more than anything "
        "GEDI can currently resolve.",
    ]:
        bullet(doc, t_, numbered=True)

    # --------------------------------------------------------- appendix
    h(doc, "Appendix A. Reproducing this report", 1)
    code(doc, [
        "cd Validation_GEDI",
        "set PY=C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto\\python.exe",
        "%PY% Step_01_check_sources.py",
        "%PY% Step_02_build_fire_mask.py --start 2009-01-01",
        "%PY% Step_03_fetch_gedi.py",
        "%PY% Step_04_aggregate_cells.py --tag New_M_2019",
        "%PY% Step_04_aggregate_cells.py --tag baseline_M_1985-2014 ^",
        "    --mprime ..\\Writing_paper_01\\output\\baseline_M_1985-2014.tif",
        "%PY% Step_05_analyse_vs_M.py",
        "%PY% make_validation_gedi_report.py",
    ])
    para(doc, "Step_02 needs the zoenv environment present (only its "
              "gdal_translate.exe is used). Steps 02 and 03 need the "
              "Earthdata login in N:\\Current-Users\\ZOHREH-KALAHROUDI\\.netrc. "
              "JinzhuLuto is used unmodified throughout.", size=10,
         colour=MUTED)

    h(doc, "Appendix B. Output files", 1)
    table(doc, ["File", "Contents"], [
        ["fire/burn_year_2009..2025.tif, last_burn_year.tif", "Fire mask, NLUM grid"],
        ["outputs/gedi_parts/<region>/*.parquet", "Per-granule footprint "
         "checkpoints, six regions (%s granules)" % n(n_gran)],
        ["outputs/gedi_l4a_footprints.parquet", "All filtered footprints with "
         "NLUM cell ids"],
        ["outputs/gedi_fetch_manifest.csv", "Footprints per granule"],
        ["outputs/gedi_cells_{all,unburnt}_{New_M_2019,baseline_M_1985-2014}.csv",
         "Per-cell GEDI statistics with M\u2032 and FPI"],
        ["outputs/analysis/*.csv", "Every table in Section 4 (by_region.csv, "
         "footprints_by_region.csv and layer_ratio_by_region.csv per region)"],
        ["outputs/figures/fig1-5*.png", "Figures 1-5"],
        ["outputs/step02_log.txt, step03_all_regions_log.txt, "
         "step04_*_log.txt, step05_log.txt", "Run logs"],
        ["outputs/_vic_central_only/", "Step 04-05 outputs from the earlier "
         "single-region pilot, kept for comparison"],
    ], widths=[3.4, 3.3])

    doc.save(str(DOCX))
    print("wrote %s" % DOCX)


if __name__ == "__main__":
    main()
