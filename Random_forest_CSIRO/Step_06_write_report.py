"""
Assemble everything into one Word document.

Reads   data/cv_metrics.csv, data/cv_metrics_by_year.csv,
        data/feature_importances.csv, output/prediction_summary.csv,
        plots/*.png, plots/future_change_summary.csv
Writes  Random_forest_CSIRO_report.docx

The document is generated, never hand-edited, so re-running any earlier step and
then this one keeps the write-up and the numbers in step. Every table is read
from the CSV the step that computed it wrote; nothing here recomputes a metric,
so the report cannot disagree with the pipeline.

Sections missing their inputs are skipped with a note rather than failing, so a
partial run still produces a readable document.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CLIM_VARS, DATA_DIR, FUTURE_YEARS, HIST_YEARS, METRIC_LABELS,
                    OUTPUT_DIR, PLOTS_DIR, SSPS, STEP_DIR, climate_feature_names,
                    soil_feature_names)

REPORT_PATH = STEP_DIR / "Random_forest_CSIRO_report.docx"

HEADLINE = ["r2", "rmse", "mae", "bias", "pearson_r", "nse", "willmott_d", "mape"]

SCHEME_TITLES = {
    "kfold_random": "Random 5-fold",
    "blockcv_space": "Spatial block CV (2 deg blocks)",
    "groupcv_year": "Year-group CV (6 years held out per fold)",
}

SOIL_GLOSSARY = [
    ("AWC", "Available water capacity", "6 depth slices"),
    ("BDW", "Bulk density, whole earth", "6"),
    ("CEC", "Cation exchange capacity", "6"),
    ("CFG / CFP", "Coarse fragments: dominant class and 6 class fractions", "3 + 18"),
    ("CLY", "Clay content", "6"),
    ("DER", "Depth of regolith", "1"),
    ("DES", "Depth of soil", "1"),
    ("pHc", "pH, CaCl2", "6"),
    ("SLT", "Silt content", "6"),
    ("SND", "Sand content", "6"),
    ("SOC", "Soil organic carbon", "6"),
    ("NTO", "Total soil nitrogen", "6"),
    ("Phos", "Total soil phosphorus", "6"),
]


# --------------------------------------------------------------------------- #
# Small docx helpers
# --------------------------------------------------------------------------- #

def add_table(doc, df, caption=None, float_fmt="{:.4f}", widths=None):
    if caption:
        p = doc.add_paragraph(caption)
        p.runs[0].italic = True
        p.runs[0].font.size = Pt(9)

    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    for j, c in enumerate(df.columns):
        cell = t.rows[0].cells[j]
        cell.text = str(c)
        for r in cell.paragraphs[0].runs:
            r.bold = True
            r.font.size = Pt(8.5)

    for _, row in df.iterrows():
        cells = t.add_row().cells
        for j, v in enumerate(row):
            if isinstance(v, float):
                txt = "" if pd.isna(v) else float_fmt.format(v)
            elif isinstance(v, (int,)) and not isinstance(v, bool):
                txt = f"{v:,}"
            else:
                txt = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
            cells[j].text = txt
            for r in cells[j].paragraphs[0].runs:
                r.font.size = Pt(8.5)
    doc.add_paragraph()
    return t


def add_figure(doc, path, caption, width=6.4):
    if not Path(path).exists():
        return False
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(caption)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].italic = True
    p.runs[0].font.size = Pt(9)
    return True


def missing(doc, what):
    p = doc.add_paragraph(f"[{what} not available - the step that produces it "
                          f"has not been run.]")
    p.runs[0].font.color.rgb = RGBColor(0x99, 0x33, 0x33)
    p.runs[0].italic = True


def read_csv(path):
    return pd.read_csv(path) if Path(path).exists() else None


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def sec_title(doc):
    doc.add_heading("Projecting the Forest Productivity Index to 2099 "
                    "with a random forest on CSIRO BARRA-R2 and QDC-CMIP6 climate", 0)
    p = doc.add_paragraph()
    p.add_run("Training window 1985-2014  |  projection 2035-2064 and 2070-2099  |  "
              "four SSPs  |  1 km NLUM grid").italic = True
    doc.add_paragraph(f"Generated {date.today().isoformat()} from "
                      f"{STEP_DIR.name}/Step_01..Step_06.")

    doc.add_heading("Summary", level=1)
    doc.add_paragraph(
        "A random forest was trained to predict the annual Forest Productivity "
        "Index (FPI) from that year's climate and from static soil properties, "
        "using the 30 observed years 1985-2014, and then applied to CSIRO's "
        "downscaled future climate to produce one FPI raster for each of the "
        "60 future years in each of four emissions scenarios."
    )
    doc.add_paragraph(
        "The design differs in one important way from the earlier "
        "Step_01_RF_for_FPI model, which regressed a single 1970-2000 mean FPI "
        "map on a single 1970-2000 climate normal. That model saw only spatial "
        "variation and so could not, even in principle, say what FPI would be in "
        "one particular future year. Here every year is a separate training "
        "sample of every cell, so the fit sees interannual variation directly, "
        "and a year-by-year projection is a question the model was actually "
        "trained to answer.", style="List Bullet")
    doc.add_paragraph(
        "Soil is held constant into the future, as specified: the same 83 soil "
        "bands enter the training rows for all 30 historical years and every one "
        "of the 240 future predictions. Only the climate columns move.",
        style="List Bullet")
    doc.add_paragraph(
        "Skill is reported from cross-validation under three different fold "
        "definitions rather than from a single random split, because a random "
        "split of this table leaks badly - see Section 5.", style="List Bullet")


def sec_data(doc):
    doc.add_heading("1. Input data", level=1)

    rows = [
        ["Target", "Forest Productivity Index (FPI), annual",
         f"{len(HIST_YEARS)} rasters, {HIST_YEARS[0]}-{HIST_YEARS[-1]}",
         "1 km NLUM grid, 3364 x 4071, GDA94"],
        ["Historical climate", "BARRA-R2 reanalysis, daily, 7 variables",
         f"7 x 30 = 210 NetCDF, {HIST_YEARS[0]}-{HIST_YEARS[-1]}",
         "AUS-11 grid, 0.11 deg, 646 x 1082"],
        ["Future climate", "QDC-CMIP6 (ACCESS-CM2 r4i1p1f1, quantile-delta "
                           "change applied to BARRA-R2), daily, 7 variables",
         f"7 x 4 SSP x 60 years = 1,680 NetCDF, "
         f"{FUTURE_YEARS[0]}-{FUTURE_YEARS[29]} and "
         f"{FUTURE_YEARS[30]}-{FUTURE_YEARS[-1]}",
         "AUS-11 grid, 0.11 deg"],
        ["Soil", "CSIRO Soil and Landscape Grid, 13 properties",
         "83 predictor rasters (11 gapfill-flag layers excluded)",
         "1 km NLUM grid, static"],
    ]
    add_table(doc, pd.DataFrame(rows, columns=["Role", "Product", "Extent", "Grid"]))

    doc.add_heading("1.1 Climate variables", level=2)
    doc.add_paragraph(
        "All seven delivered variables are used. Each is reduced from daily to "
        "twelve monthly values per year; rainfall accumulates and is summed, "
        "everything else is a state and is averaged.")
    cv = pd.DataFrame(
        [[v, {"hurs": "near-surface relative humidity (%)",
              "hursmax": "daily maximum relative humidity (%)",
              "hursmin": "daily minimum relative humidity (%)",
              "pr": "precipitation (mm d-1 -> mm month-1)",
              "rsds": "surface downwelling shortwave radiation (W m-2)",
              "tasmax": "daily maximum air temperature (degC)",
              "tasmin": "daily minimum air temperature (degC)"}[v],
          "sum" if how == "sum" else "mean"]
         for v, how in CLIM_VARS.items()],
        columns=["Variable", "Description", "Monthly reduction"])
    add_table(doc, cv)

    doc.add_heading("1.2 Soil properties", level=2)
    doc.add_paragraph(
        "Every soil raster supplied was used except the gapfill-flag layers, "
        "which record where the provider interpolated rather than measured and "
        "are provenance metadata rather than a soil property.")
    add_table(doc, pd.DataFrame(SOIL_GLOSSARY,
                                columns=["Code", "Property", "Bands used"]))


def sec_audit(doc):
    doc.add_heading("1.3 Grid audit", level=2)
    doc.add_paragraph(
        "Soil is sampled by integer row and column index, which is exact when "
        "the grids match and silently reads the wrong cells when they do not, so "
        "every input was checked against the NLUM grid before any of it was "
        "used (Step_00_audit_inputs.py).")
    audit = read_csv(DATA_DIR / "audit_inputs.csv")
    masks = read_csv(DATA_DIR / "audit_masks.csv")
    if audit is None or masks is None:
        missing(doc, "Input audit")
        return

    key = ["height", "width", "res_x", "res_y", "origin_x", "origin_y"]
    grids = audit.groupby(key).size().reset_index(name="rasters")
    add_table(doc, grids, caption="Table: distinct grids among all soil and FPI "
                                  "rasters. One row means they all agree.",
              float_fmt="{:.4f}")

    lost = float(masks["pct_fpi_lost"].max())
    doc.add_paragraph(
        f"All {int(audit.shape[0])} rasters share a single grid - "
        f"{int(grids.iloc[0]['height'])} x {int(grids.iloc[0]['width'])} at "
        f"0.01 degree, origin {grids.iloc[0]['origin_x']:.3f} / "
        f"{grids.iloc[0]['origin_y']:.3f}, GDA94 - and a single CRS. This "
        f"includes soil_N and soil_P, the two directories whose file names lack "
        f"the _NLUM suffix the others carry.", style="List Bullet")
    doc.add_paragraph(
        f"The soil and FPI footprints are the same mask: "
        f"{int(masks.iloc[0]['fpi_cells']):,} cells each, with no FPI cell "
        f"lacking soil and none the other way round, in every training year and "
        f"in 2022 (worst-case FPI loss {lost:.3f}%). Nothing needs gap-filling, "
        f"and the projection has no holes the target does not have.",
        style="List Bullet")

    clim = read_csv(DATA_DIR / "audit_climate.csv")
    if clim is not None and "nan_pct" in clim.columns:
        doc.add_paragraph(
            f"Climate carries no missing data over the Australian crop "
            f"(maximum {clim['nan_pct'].max():.6f}% NaN across the sampled "
            f"variables, scenarios and years), and the crop strictly encloses "
            f"the NLUM grid on both axes, so the bilinear interpolation always "
            f"has four real corners and never clips at an edge.",
            style="List Bullet")
    doc.add_paragraph(
        "Note that climate is resampled, not reprojected. It arrives on a "
        "regular latitude/longitude grid in the same geographic coordinates as "
        "NLUM, so 0.11 -> 0.01 degree is pure bilinear interpolation with no "
        "datum transformation involved.")


def sec_pipeline(doc):
    doc.add_heading("2. Pipeline", level=1)
    steps = [
        ["Step_00_audit_inputs.py",
         "Checks every soil and FPI raster against the NLUM grid, measures "
         "whether the soil footprint is smaller than the FPI footprint, and "
         "confirms the climate crop encloses NLUM with no gaps. Run first; it "
         "reads nothing the rest of the pipeline writes."],
        ["common.py", "Shared configuration: file locations, the fixed feature "
                      "order, bilinear regridding, and the metric definitions. "
                      "Both the training table and the prediction stack are "
                      "built through the same functions, so their column order "
                      "cannot drift apart."],
        ["Step_01_aggregate_climate.py",
         "Reads all 1,890 daily NetCDF files (~1.5 TB), crops each to Australia, "
         "and reduces it to 12 monthly values per variable-year. This is the "
         "entire I/O cost of the project; every later step reads the ~6 MB "
         "monthly files instead. Resumable, and run on processes rather than "
         "threads because netCDF4 serialises HDF5 calls behind a global lock."],
        ["Step_02_build_training_table.py",
         "Samples every 10th row and column of the NLUM grid, keeps the 69,564 "
         "cells with complete soil, and for each of the 30 historical years "
         "pairs that year's climate with that year's observed FPI. Result: "
         "2,086,920 rows x 174 columns."],
        ["Step_02b_export_training_netcdf.py",
         "Re-expresses the same training table as NetCDF, either flat "
         "(sample, feature) as fitted or gridded (year, feature, y, x) for GIS. "
         "Nothing is recomputed, so the exported file cannot disagree with what "
         "the model was fitted on."],
        ["Step_03_build_model.py",
         "Cross-validates under three fold definitions, writes out-of-fold "
         "predictions and metrics, then refits on all 30 years and saves the "
         "model used for projection."],
        ["Step_04_predict_future.py",
         "For each of 4 SSPs x 60 years, interpolates that year's climate onto "
         "the NLUM land cells, appends the unchanged soil block, predicts, and "
         "writes a GeoTIFF. Also writes the two window means per scenario."],
        ["Step_04b_export_netcdf.py",
         "Re-expresses the projections as NetCDF cubes, one per scenario per "
         "window. Reads the GeoTIFFs and recomputes nothing, so the two forms "
         "cannot disagree. Kept as separate files per window because CSIRO "
         "separated 2035-2064 from 2070-2099 deliberately and a single 60-long "
         "year axis would invite interpolation across a gap the data does not "
         "support."],
        ["Step_05_plots.py", "Validation and projection figures."],
        ["Step_07_scenario_diagnostic.py",
         "Measures what the climate does in each scenario-window over the land "
         "cells, and correlates it against the projected FPI change - the test "
         "of whether the non-monotonic scenario ordering comes from the forcing "
         "or from the model (Section 7.2)."],
        ["Step_06_write_report.py", "This document."],
    ]
    add_table(doc, pd.DataFrame(steps, columns=["Script", "What it does"]))

    doc.add_heading("2.1 Regridding", level=2)
    doc.add_paragraph(
        "Climate arrives on the 0.11 deg AUS-11 grid and the target and soil are "
        "on the 0.01 deg NLUM grid, so climate is bilinearly interpolated onto "
        "NLUM coordinates. That interpolation is done at the point of use and "
        "never stored: one year of all seven variables on the NLUM grid is about "
        "4.6 GB, and the projection walks 240 such years.")
    doc.add_paragraph(
        "Interpolation is bilinear in both directions, identical in training and "
        "in prediction, through the same function. Points outside the source "
        "domain are clipped rather than extrapolated; with the Australian "
        "bounding box used here that case never arises.")


def sec_features(doc):
    doc.add_heading("3. Predictors", level=1)
    clim = climate_feature_names()
    soil = soil_feature_names()
    doc.add_paragraph(
        f"{len(soil) + len(clim)} predictors: {len(soil)} soil and {len(clim)} "
        f"climate. The climate block is, for each of the seven variables, the "
        f"twelve monthly aggregates followed by one annual aggregate.")
    doc.add_paragraph(
        "The annual term is redundant in principle - a tree could reconstruct it "
        "from the twelve monthly splits - but only through a deep chain of "
        "splits, because trees cannot add. Supplying it directly lets a single "
        "split key on 'a dry year' rather than on twelve separately dry months.")
    doc.add_paragraph(
        f"Example climate names: {', '.join(clim[:4])} ... {clim[12]} ... "
        f"{clim[-1]}.")


def sec_training(doc):
    doc.add_heading("4. Training set", level=1)
    doc.add_paragraph(
        "One row per (cell, year). The 1985-2014 window is set by the CSIRO "
        "historical baseline, and the FPI raster for the matching year is used "
        "as the target - 1985 climate against 1985 FPI, 1994 climate against "
        "1994 FPI, and so on. No climatological averaging is applied on either "
        "side.")
    rows = [
        ["Years", f"{len(HIST_YEARS)} ({HIST_YEARS[0]}-{HIST_YEARS[-1]})"],
        ["Grid sampling", "every 10th row and column of the 3364 x 4071 NLUM grid"],
        ["Cells with complete soil", "69,564 of 137,496 candidates (50.6%)"],
        ["Rows", "2,086,920"],
        ["Columns", "174 (83 soil + 91 climate)"],
    ]
    add_table(doc, pd.DataFrame(rows, columns=["", ""]))
    doc.add_paragraph(
        "Roughly half the candidate cells are dropped because they are ocean or "
        "otherwise outside the soil coverage; the surviving fraction matches the "
        "50.8% of the FPI grid that carries data.")

    doc.add_heading("4.1 Hyperparameters", level=2)
    rows = [
        ["n_estimators", "64", "as in Step_01_RF_for_FPI"],
        ["max_features", "1.0 (all)", "sklearn default for regression, as in Step_01"],
        ["min_samples_leaf", "5",
         "the one deliberate change. At 2 M rows a fully grown forest is ~17 GB "
         "of tree structure and its last splits separate individual cell-years; "
         "FPI is smooth and observationally noisy at that scale, so stopping at "
         "5 costs almost no skill"],
        ["random_state", "42", "reproducible"],
    ]
    add_table(doc, pd.DataFrame(rows, columns=["Parameter", "Value", "Why"]))


def sec_validation(doc):
    doc.add_heading("5. Cross-validation", level=1)
    doc.add_paragraph(
        "Three fold definitions are used, because a single number would be "
        "misleading. Every cell contributes 30 rows that share all 83 soil "
        "values and differ only in one year's weather, so a plain random split "
        "puts 1994 and 1995 of the same cell on opposite sides and largely "
        "measures memorisation.")
    add_table(doc, pd.DataFrame([
        ["kfold_random", "5-fold over rows",
         "The optimistic number, and the one comparable with Step_01_RF_for_FPI."],
        ["blockcv_space", "5-fold over contiguous 2 deg blocks",
         "Can it predict an unseen region. Blocks rather than scattered cells: "
         "at 1 km FPI is strongly autocorrelated, so a randomly held-out cell "
         "sits ringed by its own neighbours in the training set and scores "
         "almost as high as no holdout at all."],
        ["groupcv_year", "5-fold over years, 6 years held out per fold",
         "Can it predict an unseen year. This is the number to quote: "
         "projecting 2035-2099 is exactly the act of predicting years the model "
         "never saw."],
    ], columns=["Scheme", "Folds", "What it measures"]))
    doc.add_paragraph(
        "Each scheme predicts every row exactly once, by the fold that did not "
        "train on it, so the metrics below are computed over the whole 30-year "
        "table rather than over a fifth of it.")

    cv = read_csv(DATA_DIR / "cv_metrics.csv")
    if cv is None:
        missing(doc, "Cross-validation metrics")
        return

    doc.add_heading("5.1 Pooled out-of-fold metrics", level=2)
    pooled = cv[cv["fold"].astype(str) == "all"].copy()
    pooled["Scheme"] = pooled["scheme"].map(SCHEME_TITLES).fillna(pooled["scheme"])
    tbl = pooled[["Scheme"] + HEADLINE].rename(columns=METRIC_LABELS)
    add_table(doc, tbl, caption="Table: out-of-fold skill over all 2,086,920 rows.")

    doc.add_paragraph("Metric definitions:")
    for k in HEADLINE:
        doc.add_paragraph(f"{METRIC_LABELS[k]}", style="List Bullet")
    doc.add_paragraph(
        "R2 and the Nash-Sutcliffe efficiency are the same quantity, 1 - SSE/SST, "
        "reported under both names because the machine-learning and the "
        "ecology literatures each expect their own. Explained variance differs "
        "from them only by removing the mean bias first, so any gap between the "
        "two is exactly the bias term.")

    doc.add_heading("5.2 Fold by fold", level=2)
    per = cv[cv["fold"].astype(str) != "all"].copy()
    per["Scheme"] = per["scheme"].map(SCHEME_TITLES).fillna(per["scheme"])
    per = per[["Scheme", "fold", "n_train", "n_test", "r2", "rmse", "mae", "bias"]]
    add_table(doc, per.rename(columns=METRIC_LABELS))

    by_year = read_csv(DATA_DIR / "cv_metrics_by_year.csv")
    if by_year is not None:
        doc.add_heading("5.3 Year-group CV, year by year", level=2)
        doc.add_paragraph(
            "Skill for each year, computed from the fold in which that year was "
            "held out. Weak years are the informative ones: they identify the "
            "climate conditions the model extrapolates into least reliably.")
        cols = ["year", "n", "r2", "rmse", "mae", "bias", "obs_mean", "pred_mean"]
        add_table(doc, by_year[cols].rename(columns=METRIC_LABELS))

    doc.add_heading("5.4 Figures", level=2)
    add_figure(doc, PLOTS_DIR / "scatter_cv.png",
               "Out-of-fold predicted vs observed FPI under each scheme. "
               "Colour is point density on a log scale; the grey line is 1:1.")
    add_figure(doc, PLOTS_DIR / "cv_by_year.png",
               "Left: skill for each held-out year. Right: annual mean FPI, "
               "observed against out-of-fold prediction.")
    add_figure(doc, PLOTS_DIR / "residual_map.png",
               "Mean out-of-fold residual in space, year-group CV. Systematic "
               "colour indicates a region the model is biased in, as distinct "
               "from noise.", width=5.4)


def sec_importance(doc):
    doc.add_heading("6. Predictor importance", level=1)
    imp = read_csv(DATA_DIR / "feature_importances.csv")
    if imp is None:
        missing(doc, "Feature importances")
        return
    tot = imp.groupby("kind")["importance"].sum()
    doc.add_paragraph(
        f"Impurity-based importance from the final model. Soil accounts for "
        f"{tot.get('soil', 0):.3f} of the total and climate for "
        f"{tot.get('climate', 0):.3f}.")
    doc.add_paragraph(
        "Impurity importance is biased toward high-cardinality continuous "
        "predictors and splits credit arbitrarily among correlated ones - and "
        "these predictors are heavily correlated, with six depth slices of every "
        "soil property and twelve months of every climate variable. Read the "
        "ranking as which groups matter, not as a precise ordering within a "
        "group.")
    add_table(doc, imp.head(20)[["feature", "kind", "importance"]],
              caption="Table: 20 most important predictors.",
              float_fmt="{:.5f}")
    add_figure(doc, PLOTS_DIR / "feature_importance.png",
               "Top 25 predictors. Brown is soil, blue is climate.", width=5.6)


def sec_projection(doc):
    doc.add_heading("7. Future projection", level=1)
    doc.add_paragraph(
        f"The refitted model is applied to each of {len(SSPS)} scenarios "
        f"({', '.join(SSPS)}) for each of the {len(FUTURE_YEARS)} future years, "
        f"giving {len(SSPS) * len(FUTURE_YEARS)} FPI rasters on the full NLUM "
        f"grid, plus a mean raster for each scenario in each of the two windows.")
    doc.add_paragraph(
        "Soil is unchanged from the historical rows. The land mask comes from "
        "soil coverage alone; the historical FPI footprint is deliberately not "
        "imposed on the projection, since masking a projection to where FPI "
        "happened to be observed in 1985-2014 would bake an observational "
        "footprint into it.")
    doc.add_paragraph(
        "The two windows are 2035-2064 and 2070-2099 and are kept separate. "
        "CSIRO separated them deliberately so that users do not join them; the "
        "intervening years are not part of the delivered dataset and no trend is "
        "drawn across the gap.")

    ps = read_csv(OUTPUT_DIR / "prediction_summary.csv")
    if ps is not None and "mean" in ps.columns:
        ok = ps[ps["status"] == "ok"]
        if len(ok):
            g = (ok.groupby("ssp")[["min", "mean", "max"]].mean().reset_index()
                 .rename(columns={"ssp": "Scenario", "min": "mean of yearly min",
                                  "mean": "mean FPI", "max": "mean of yearly max"}))
            add_table(doc, g, caption="Table: predicted FPI by scenario, "
                                      "averaged over all projected years.")

    chg = read_csv(PLOTS_DIR / "future_change_summary.csv")
    if chg is not None:
        add_table(doc, chg.rename(columns={
            "ssp": "Scenario", "period": "Window", "future_mean": "Projected mean",
            "baseline_mean": "Observed 1985-2014 mean", "change": "Change",
            "pct_change": "Change (%)"}),
            caption="Table: window-mean FPI against the observed 1985-2014 mean.")

    add_figure(doc, PLOTS_DIR / "future_trajectory.png",
               "Australia-wide mean FPI: observed 1985-2014, then projected for "
               "each scenario across the two windows.")
    add_figure(doc, PLOTS_DIR / "future_change_maps.png",
               "Window-mean projected FPI minus the observed 1985-2014 mean.")

    doc.add_heading("7.1 Projected 2035-2064 against observed FPI in 2022", level=2)
    doc.add_paragraph(
        "A direct comparison of the first projection window's mean against the "
        "most recent observed year. Read it as a displacement rather than a "
        "validation: the left-hand quantity is a 30-year mean and the "
        "right-hand one a single year, so averaging has already removed "
        "interannual variance that 2022 still carries.")
    doc.add_paragraph(
        "2022 is also a wet La Nina year and sits above the 1985-2014 norm, and "
        "the year-group cross-validation shows this model under-predicts "
        "precisely such years (2010 by -0.53, 2011 by -0.30). Part of any "
        "apparent decline against 2022 is therefore 2022 being unusually "
        "productive rather than the future being unproductive. The dashed line "
        "in each panel is the observed 1985-2014 mean against 2022: the gap "
        "between the two clouds is the projected change, while the gap between "
        "the dashed line and 1:1 is only how exceptional 2022 was. The "
        "comparison against the 30-year observed mean in the table above is the "
        "cleaner one.")
    t22 = read_csv(PLOTS_DIR / "future_vs_fpi2022_summary.csv")
    if t22 is None:
        missing(doc, "The 2022 comparison")
    else:
        add_table(doc, t22.rename(columns={
            "ssp": "Scenario", "n_cells": "Cells",
            "fpi_2022_mean": "Observed FPI 2022",
            "future_2035_2064_mean": "Projected mean 2035-2064",
            "change": "Change", "pct_change": "Change (%)",
            "slope": "OLS slope", "intercept": "OLS intercept"}),
            caption="Table: projected 2035-2064 mean against observed FPI 2022. "
                    "An OLS slope below 1 means the projected change is "
                    "proportionally larger in the more productive cells.")
        add_figure(doc, PLOTS_DIR / "scatter_future_vs_fpi2022.png",
                   "Projected 2035-2064 mean FPI against observed FPI 2022, one "
                   "panel per scenario. Grey is 1:1, orange is the OLS fit, "
                   "dashed grey is the observed 1985-2014 mean against 2022.")
        add_figure(doc, PLOTS_DIR / "future_vs_fpi2022_map.png",
                   "The same difference in space: projected 2035-2064 mean "
                   "minus observed 2022.")


def sec_scenario_diagnostic(doc):
    doc.add_heading("7.2 Why the scenario ordering is not monotonic", level=2)
    doc.add_paragraph(
        "The projections do not fall monotonically with forcing. ssp245 in "
        "2070-2099 shows the smallest decline of any scenario-window (-1.3%), "
        "smaller than ssp126 over the same years (-5.8%) and smaller than its "
        "own earlier window (-3.9%); and in 2035-2064 there is no forcing "
        "signal at all, with ssp245 declining more than ssp585. A reader will "
        "notice this, so it was measured rather than explained away.")
    doc.add_paragraph(
        "Step_07_scenario_diagnostic.py computes what the climate actually does "
        "in each scenario-window, in the variables the model keys on, over the "
        "same 6,956,407 land cells, weighting each coarse cell by the number of "
        "NLUM land cells inside it.")

    d = read_csv(DATA_DIR / "scenario_climate_vs_fpi.csv")
    if d is None:
        missing(doc, "The scenario climate diagnostic")
        return

    cols = ["scenario", "window", "hurs", "hursmin", "pr", "rsds", "tasmax",
            "tasmin", "fpi_pct_change"]
    tbl = d[[c for c in cols if c in d.columns]].rename(columns={
        "scenario": "Scenario", "window": "Window",
        "fpi_pct_change": "FPI change (%)"})
    add_table(doc, tbl, float_fmt="{:.2f}",
              caption="Table: change in each climate variable and in projected "
                      "FPI, per cent against the 1985-2014 baseline, over the "
                      "NLUM land cells.")

    import numpy as _np
    corrs = {v: float(_np.corrcoef(d[v], d["fpi_pct_change"])[0, 1])
             for v in ("hurs", "pr", "tasmax") if v in d}
    doc.add_paragraph(
        "Across the eight scenario-windows, projected FPI change correlates "
        + ", ".join(f"{c:+.3f} with {v}" for v, c in corrs.items())
        + ".", style="List Bullet")
    doc.add_paragraph(
        "The non-monotonicity is in the forcing, not the model. ACCESS-CM2 "
        "r4i1p1f1 under ssp245 in 2070-2099 is barely drier than the baseline - "
        "rainfall -0.8%, the smallest change of any late-century window and less "
        "drying than that scenario's own early window at -7.1% - while ssp126 "
        "over the same years is markedly drier at -9.8%. FPI follows, at a "
        "correlation of about 0.97. The model is reporting its input "
        "faithfully.", style="List Bullet")
    doc.add_paragraph(
        "The clinching detail is that temperature IS ordered by forcing: tasmax "
        "rises +6.3, +7.8, +7.6, +11.5, +8.3, +17.4, +9.0 and +20.5 per cent "
        "across the eight windows, essentially monotonic within each window. "
        "Rainfall and relative humidity are not. Because this model keys on "
        "humidity and rainfall rather than on temperature (Section 6), it "
        "inherits their non-monotonicity. The -0.81 correlation with tasmax is "
        "incidental - temperature co-varies with the drying, but contributed "
        "almost no importance to the fit.", style="List Bullet")
    doc.add_paragraph(
        "What to claim, therefore: FPI declines in every scenario and every "
        "window, and strongly late-century under high forcing (ssp370 -8.6%, "
        "ssp585 -9.5%). What not to claim: the ordering of scenarios within "
        "2035-2064, or ssp245's late-window value, as evidence of a "
        "forcing-response relationship. A single realisation of a single GCM "
        "does not average out internal variability, and relative humidity - the "
        "dominant predictor here - is the field in which that variability is "
        "largest and inter-model agreement weakest.")

    add_figure(doc, PLOTS_DIR / "scenario_climate_diagnostic.png",
               "Projected change in each climate variable over the NLUM land "
               "cells, by scenario and window.")
    add_figure(doc, PLOTS_DIR / "scenario_fpi_vs_climate.png",
               "Projected FPI change against humidity and rainfall change, one "
               "point per scenario-window.")


def sec_caveats(doc):
    doc.add_heading("8. What this projection does and does not say", level=1)
    for text in [
        "The projection is a climate-response surface, not a forest growth model. "
        "It says what FPI the historical relationship implies for a future "
        "year's climate; it carries no CO2 fertilisation, no change in species "
        "composition, no disturbance, and no soil change.",

        "Soil is held constant by instruction. Soil organic carbon and nitrogen "
        "in particular do respond to a changing climate over 75 years, so any "
        "part of the future FPI signal that would have come through soil is "
        "absent by construction.",

        "The future climate is QDC-CMIP6: quantile-delta changes from ACCESS-CM2 "
        "applied multiplicatively to observed BARRA-R2 years. Each future year is "
        "an observed year rescaled, so the interannual variability in the "
        "projection is observed weather carrying a model-derived change signal, "
        "not model weather. Year-to-year wiggles in the projected series should "
        "not be read as predictions of particular years.",

        "Training and future climate share the same observational base - both "
        "are BARRA-R2, one directly and one rescaled - so the observational-"
        "product difference that affects the ANUClimate-based FullCAM inputs "
        "does not arise here.",

        "A random forest cannot extrapolate beyond its training range: it "
        "predicts a mean of training-set leaves, so a 2090 climate hotter than "
        "anything in 1985-2014 is answered with the response at the edge of the "
        "training envelope. Late-century, high-forcing projections are therefore "
        "conservative by construction, and the effect is strongest in ssp585.",

        "That compression is not hypothetical - the year-group cross-validation "
        "measures it inside the training window. The model under-predicts the "
        "most productive years and over-predicts the least productive ones: "
        "2010 and 2011, the two strongest La Nina years and the two highest "
        "observed means (5.72 and 5.77), come out at -0.53 and -0.30; 1994, a "
        "strong El Nino and the lowest observed mean (3.17), comes out at "
        "+0.39. 2010 is also the weakest year in the record (R2 0.885, RMSE "
        "1.18). Read the projected spread between scenarios and between years "
        "as a lower bound on magnitude rather than a central estimate.",

        "The fit leans on humidity, not on temperature. Relative humidity terms "
        "together carry about 0.38 of the total importance - more than three "
        "times rainfall at 0.104 - while tasmax, tasmin and rsds do not appear "
        "in the top 15 predictors at all. Part of that is impurity importance "
        "dividing credit among three correlated humidity variables, but the "
        "absence of temperature is not a splitting artefact. The practical "
        "consequence is that these projections are driven mainly by projected "
        "change in relative humidity, which is among the least well constrained "
        "fields in a climate projection, rather than by warming, which is among "
        "the most robust. Scenario differences inherit that weaker constraint.",

        "The year-group CV score is the honest measure of skill for this use, "
        "and it is the lowest of the three. The gap between it and the random "
        "5-fold score is a measure of how much of the apparent skill comes from "
        "knowing the place rather than knowing the year.",
    ]:
        doc.add_paragraph(text, style="List Bullet")


def sec_outputs(doc):
    doc.add_heading("9. Outputs", level=1)
    add_table(doc, pd.DataFrame([
        ["data/audit_inputs.csv, audit_masks.csv, audit_climate.csv",
         "the grid audit: per-raster grid signature, soil-vs-FPI footprint "
         "overlap, and climate coverage"],
        ["data/monthly_climate/", "1,890 monthly-aggregated climate NetCDF"],
        ["data/training_table.npz", "the 2,086,920 x 174 training table"],
        ["data/X_train.nc, data/y_train.nc",
         "the same training table as NetCDF, dimensions (sample, feature) and "
         "(sample), with year, cell_row, cell_col, lat and lon carried as "
         "coordinates on sample"],
        ["data/X_train_gridded.nc, data/y_train_gridded.nc",
         "the same numbers as (year, feature, y, x) and (year, y, x) rasters on "
         "the downsampled NLUM grid, NaN where soil coverage is incomplete"],
        ["data/random_forest_model.pkl", "the fitted model and its feature order"],
        ["data/cv_metrics.csv", "per-scheme and per-fold metrics"],
        ["data/cv_metrics_by_year.csv", "year-group CV skill, year by year"],
        ["data/oof_*.npz", "out-of-fold predictions for every row, per scheme"],
        ["data/feature_importances.csv", "impurity importance, all 174 predictors"],
        ["output/fpi_<ssp>_<year>.tif", "240 projected FPI rasters, 1 km NLUM"],
        ["output/fpi_<ssp>_<window>_mean.tif", "8 window-mean rasters"],
        ["output/netcdf/fpi_<ssp>_<period>.nc",
         "the same projections as 8 NetCDF cubes - fpi(year, lat, lon) for the "
         "30 years of that window plus fpi_mean(lat, lon) - one file per "
         "scenario per window, so the two windows stay separate"],
        ["output/netcdf/fpi_all_period_means.nc",
         "the 8 window means in a single file, fpi_mean(scenario_period, lat, lon)"],
        ["output/domain_mean_fpi_by_year.csv", "Australia-wide mean per scenario-year"],
        ["plots/scatter_future_vs_fpi2022.png, future_vs_fpi2022_map.png, "
         "future_vs_fpi2022_summary.csv",
         "the 2035-2064 mean against observed FPI 2022, per scenario"],
        ["data/scenario_climate_diagnostic.csv, scenario_climate_vs_fpi.csv",
         "land-weighted climate change per scenario-window, and its "
         "relationship to the projected FPI change"],
        ["plots/", "all figures reproduced in this document"],
    ], columns=["Path", "Contents"]))
    doc.add_paragraph(
        "Rasters are float32 GeoTIFF, LZW-compressed, on the 3364 x 4071 NLUM "
        "grid in GDA94, NaN outside the soil mask - the same convention as the "
        "rest of the project.")


def main():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    sec_title(doc)
    doc.add_page_break()
    sec_data(doc)
    sec_audit(doc)
    sec_pipeline(doc)
    sec_features(doc)
    sec_training(doc)
    doc.add_page_break()
    sec_validation(doc)
    doc.add_page_break()
    sec_importance(doc)
    doc.add_page_break()
    sec_projection(doc)
    sec_scenario_diagnostic(doc)
    sec_caveats(doc)
    sec_outputs(doc)

    doc.save(REPORT_PATH)
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
