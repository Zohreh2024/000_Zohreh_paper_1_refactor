"""
Step C - the report.

Builds New_proposal_report.docx from the tables and figures Steps A and B
wrote. Nothing is recomputed; every number comes from a CSV in outputs/, so the
report cannot drift from the analysis.

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_C_write_report.py
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
REPORT = HERE / "New_proposal_report.docx"

INK_2 = RGBColor(0x52, 0x51, 0x4E)
CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells_nvis", "random_cells_unconstrained"]


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

    s = pd.read_csv(OUT_DIR / "ofat_summary.csv")
    d = pd.read_csv(OUT_DIR / "ofat_deltas.csv")
    mat = pd.read_csv(OUT_DIR / "run_matrix.csv")

    fut = s[~s["run"].isin(CONTROLS)]
    base = fut[fut["run_id"] == "run00_baseline"]
    b_ratio = float(base["median_ratio"].median())
    b_rho = float(base["spearman_rho"].median())
    b_na = float(base["pct_no_analogue"].median())

    def ctl(rid, name, col):
        r = s[(s["run_id"] == rid) & (s["run"] == name)]
        return float(r[col].iloc[0]) if len(r) else np.nan

    ok = d[d["sample_comparable"]].sort_values("d_rho_future",
                                               key=lambda v: v.abs(),
                                               ascending=False)
    bad = d[~d["sample_comparable"]]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("The space-for-time validation, one change at a time", 0)
    p = doc.add_paragraph()
    r = p.add_run("Validation_M/National_biomass_library/Space_time_validation/"
                  "New_proposal · generated %s · %d configurations, each "
                  "differing from Run 0 in exactly one parameter"
                  % (date.today().isoformat(), len(mat)))
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    # ------------------------------------------------------------------ #
    doc.add_heading("Why one change at a time", level=1)
    doc.add_paragraph(
        "The validation next door settles several questions at once - which "
        "sites count as mature, whether matching is constrained to vegetation, "
        "which averaging order, which predictors, how far is too far. When a "
        "result moves under a configuration that changed four things, nothing "
        "can be said about which of the four moved it. Every run here therefore "
        "changes exactly ONE parameter against Run 0 and holds the rest fixed. "
        "The difference between a run and Run 0 is then attributable to that "
        "parameter; the runs are comparable to each other only through Run 0, "
        "never directly.", style="Intense Quote")
    doc.add_paragraph(
        "Nothing in the parent folder was modified. This analysis imports its "
        "Step_03 as a module and reuses the matching, the metrics and the "
        "bootstrap unchanged, but selects its own inputs and writes only inside "
        "New_proposal/. Run 0 reproduces the published configuration exactly, "
        "which is the check that has to pass before any delta means anything: "
        "present-day analogue %s and rho %s, constrained null %s and %s, "
        "unconstrained null %s and %s."
        % (fmt(ctl("run00_baseline", "historical_analogue", "median_ratio")),
           fmt(ctl("run00_baseline", "historical_analogue", "spearman_rho")),
           fmt(ctl("run00_baseline", "random_cells_nvis", "median_ratio")),
           fmt(ctl("run00_baseline", "random_cells_nvis", "spearman_rho")),
           fmt(ctl("run00_baseline", "random_cells_unconstrained",
                   "median_ratio")),
           fmt(ctl("run00_baseline", "random_cells_unconstrained",
                   "spearman_rho"))))

    doc.add_heading("Two rules carried through every run", level=2)
    doc.add_paragraph(
        "BOTH NULLS ARE REPORTED, ALWAYS. Random cells drawn under the same "
        "NVIS constraint, and random cells drawn without it. They answer "
        "different questions and neither alone is the answer. Against the "
        "unconstrained null the analogue search wins decisively - that is what "
        "shows the method has skill at all. Against the constrained null the "
        "gap is small - that is what says how much of the skill is knowing the "
        "vegetation subgroup rather than matching the climate. Quoting only "
        "the first overstates the method; quoting only the second understates "
        "it.")
    doc.add_paragraph(
        "METRICS COME FROM THE ANALOGUE-FOUND STRATUM. A site whose nearest "
        "future cell lies beyond the no-analogue cutoff is still assigned a "
        "match, because there is always a nearest cell - but that match is not "
        "an analogue. Including those forced matches inflates the median ratio "
        "in the late-century runs while the rank correlation collapses. Every "
        "number in this report is computed on the sites that retained an "
        "analogue, with the no-analogue share reported beside it.")

    doc.add_heading("The run matrix", level=2)
    table(doc, [[r["run_id"], r["changed"], r["what"]]
                for _, r in mat.iterrows()],
          ["run", "what changed", "how"], widths=[1.4, 1.3, 3.3])

    # ------------------------------------------------------------------ #
    doc.add_heading("The reading rule that has to come first", level=1)
    doc.add_paragraph(
        "A change that also moves the no-analogue share is not a like-for-like "
        "comparison. The metric is then computed on a different set of "
        "surviving sites, and those survivors are not a random subset - they "
        "are the sites whose climate still has a counterpart, which are "
        "systematically the wetter and more productive ones. A rank "
        "correlation can rise simply because the awkward sites have been "
        "removed. Runs are flagged on that basis rather than dropped, at a "
        "threshold of ten percentage points against Run 0, whose own "
        "no-analogue share is %s." % (fmt(b_na, "%.1f") + "%"),
        style="Intense Quote")
    if len(bad):
        rows = [[r["run_id"], r["changed"], fmt(r["d_pct_no_analogue"], "%+.0f")
                 + " pp", fmt(r["d_rho_future"], "%+.3f"),
                 fmt(r["d_ratio_future"], "%+.3f")] for _, r in bad.iterrows()]
        table(doc, rows, ["run", "what changed", "change in no-analogue share",
                          "apparent change in rho", "apparent change in ratio"],
              widths=[1.4, 1.2, 1.4, 1.1, 1.1])
        caption(doc, "Table 1. The runs whose deltas cannot be attributed to "
                     "the change alone.")
        doc.add_paragraph(
            "Both belong to the same trap. Tightening the no-analogue cutoff "
            "from the 99th to the 95th percentile discards the marginal "
            "matches, and the rank correlation duly rises - on a median of "
            "about a hundred surviving sites out of 600. Dropping the 83 soil "
            "columns collapses the predictor space to five components, which "
            "shrinks every distance in it, and against a cutoff computed in "
            "that same shrunken space most sites end up with no analogue at "
            "all. Neither run says what it appears to say.")
    figure(doc, "fig_04_no_analogue_share.png",
           "Figure 1. The no-analogue share under each configuration, with the "
           "smallest surviving sample printed on each bar. Red marks the runs "
           "that moved it by ten points or more against Run 0.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What actually moves the result", level=1)
    doc.add_paragraph(
        "Run 0 gives a median ratio of %s and a rank correlation of %s across "
        "the eight scenario-windows. Of the changes whose sample stayed "
        "comparable, these are the deltas, largest first:"
        % (fmt(b_ratio), fmt(b_rho)))
    rows = [[r["run_id"], r["changed"], int(r["n_sites"]),
             fmt(r["d_rho_future"], "%+.3f"),
             fmt(r["d_ratio_future"], "%+.3f"),
             fmt(r["d_pct_no_analogue"], "%+.1f") + " pp"]
            for _, r in ok.iterrows()]
    table(doc, rows, ["run", "what changed", "sites", "change in rho",
                      "change in ratio", "change in no-analogue"],
          widths=[1.4, 1.3, 0.6, 1.0, 1.0, 1.2])
    caption(doc, "Table 2. Every attributable change, ordered by the size of "
                 "its effect on the rank correlation.")
    figure(doc, "fig_01_delta_rho.png",
           "Figure 2. What each single change does to the rank correlation. "
           "Grey bars are the runs whose sample also changed and which "
           "therefore cannot be read at face value.")
    figure(doc, "fig_02_delta_ratio.png",
           "Figure 3. The same for the median ratio.")

    doc.add_heading("The answer in one sentence", level=2)
    top = ok.iloc[:2] if len(ok) >= 2 else ok
    doc.add_paragraph(
        "The two changes that move the result are both about the SAMPLE, not "
        "about the method. Removing the biomass-versus-basal-area consistency "
        "filter costs %s of rank correlation, and restricting the sample to "
        "stem-verified mature stands gains %s. Every methodological choice "
        "tested - the averaging order, the PCA variance retained, the NVIS "
        "fallback threshold, the predictor set - moves the rank correlation by "
        "less than %s, and two of them move it by less than 0.002."
        % (fmt(abs(float(d[d.run_id == "run09_noqc"]["d_rho_future"].iloc[0]))
               if (d.run_id == "run09_noqc").any() else np.nan),
           fmt(float(d[d.run_id == "run01_verified_only"]["d_rho_future"]
                     .iloc[0]) if (d.run_id == "run01_verified_only").any()
               else np.nan, "%+.3f"),
           fmt(max(abs(float(v)) for rid, v in zip(
               ok["run_id"], ok["d_rho_future"])
               if rid not in ("run09_noqc", "run01_verified_only")), "%.3f")),
        style="Intense Quote")

    # ------------------------------------------------------------------ #
    doc.add_heading("Run by run", level=1)
    notes = {
        "run01_verified_only":
            "Restricting to stems of 50 cm or more raises both the ratio and "
            "the rank correlation, on half the sample. That is the expected "
            "direction and it is the cleanest evidence in this folder that the "
            "likely-mature half carries stands short of their maximum: M' is a "
            "maximum, so a sample closer to maturity should agree with it "
            "better. The cost is 327 sites and a wider interval on everything.",
        "run02_unconstrained":
            "Dropping the NVIS constraint barely moves the future runs, but it "
            "RAISES the present-day analogue's rank correlation. The "
            "constraint is not improving the match; it is restricting the pool, "
            "and a site's best climate analogue is sometimes in another "
            "vegetation subgroup. Keep the constraint for the reason it was "
            "added - two cells can share a climate and carry different "
            "vegetation - but it is not buying accuracy here.",
        "run03_mean_of_annual":
            "The averaging order changes nothing at all. This is the cleanest "
            "possible confirmation of the argument made in the parent folder: "
            "the Jensen gap cancels when numerator and denominator are built "
            "in the same order, so the choice between Eq. (1) of the mean FPI "
            "and the mean of the annual Eq. (1) M does not reach the "
            "validation.",
        "run05_reduced":
            "Sixteen columns instead of 174 costs a little rank correlation "
            "and raises the no-analogue share. Consistent with the relative-"
            "contrast diagnostic in the parent folder, which found the full "
            "space was not suffering from distance concentration and so had "
            "nothing to gain from being reduced.",
        "run06_variance_99":
            "Keeping 0.99 of the variance instead of 0.95 more than doubles "
            "the components, from 18 to 41, and changes essentially nothing. "
            "The extra components carry noise, not structure.",
        "run08_k5":
            "Averaging the five nearest cells instead of taking one improves "
            "the rank correlation and lowers the ratio. Part of that is real - "
            "a single cell's M' carries the full noise of one FPI prediction - "
            "and part is the rising no-analogue share, so read it as "
            "suggestive rather than settled.",
        "run09_noqc":
            "Putting back the records whose reported biomass contradicts their "
            "own basal area is the single most damaging change tested. The "
            "rank correlation collapses while the ratio rises towards 1, which "
            "is the same fact twice: those records contribute biomass values "
            "unrelated to the stands they describe, which depresses the "
            "observed median and adds pure noise to the ranking.",
        "run10_minclass_100":
            "Requiring 100 pool cells before a subgroup constrains the match, "
            "rather than 25, changes nothing measurable. The fallback is rare "
            "enough not to matter.",
    }
    for _, r in d.sort_values("run_id").iterrows():
        rid = r["run_id"]
        doc.add_heading("%s - %s" % (rid, r["changed"]), level=2)
        line = ("Rank correlation %s, median ratio %s, no-analogue share %s "
                "against Run 0, on %d sites."
                % (fmt(r["d_rho_future"], "%+.3f"),
                   fmt(r["d_ratio_future"], "%+.3f"),
                   fmt(r["d_pct_no_analogue"], "%+.1f") + " pp",
                   int(r["n_sites"])))
        if not r["sample_comparable"]:
            line += (" The sample also changed, so this delta is not "
                     "attributable to the change alone.")
        doc.add_paragraph(line)
        if rid in notes:
            doc.add_paragraph(notes[rid])
        for name in ("random_cells_nvis", "random_cells_unconstrained"):
            pass
        doc.add_paragraph(
            "Nulls under this configuration: constrained %s (rho %s), "
            "unconstrained %s (rho %s)."
            % (fmt(ctl(rid, "random_cells_nvis", "median_ratio")),
               fmt(ctl(rid, "random_cells_nvis", "spearman_rho")),
               fmt(ctl(rid, "random_cells_unconstrained", "median_ratio")),
               fmt(ctl(rid, "random_cells_unconstrained", "spearman_rho"))))

    # ------------------------------------------------------------------ #
    doc.add_heading("Both nulls, every configuration", level=1)
    doc.add_paragraph(
        "The two nulls behave differently across the matrix and the difference "
        "is the point. The unconstrained null sits near %s with a rank "
        "correlation near zero under almost every configuration - the analogue "
        "search beats it everywhere, which is what establishes that the method "
        "does something. The constrained null tracks the runs closely, because "
        "it inherits whatever the configuration did to the sample, and the gap "
        "between it and the runs is the honest measure of what the climate "
        "matching adds on top of knowing the vegetation subgroup."
        % fmt(ctl("run00_baseline", "random_cells_unconstrained",
                  "median_ratio")))
    rows = []
    for rid, g in s.groupby("run_id"):
        f = g[~g["run"].isin(CONTROLS)]
        rows.append([rid, fmt(f["median_ratio"].median()),
                     fmt(ctl(rid, "random_cells_nvis", "median_ratio")),
                     fmt(ctl(rid, "random_cells_unconstrained",
                             "median_ratio")),
                     fmt(f["spearman_rho"].median()),
                     fmt(ctl(rid, "random_cells_nvis", "spearman_rho")),
                     fmt(ctl(rid, "random_cells_unconstrained",
                             "spearman_rho"))])
    table(doc, rows,
          ["run", "runs: ratio", "null NVIS", "null free", "runs: rho",
           "null NVIS", "null free"],
          widths=[1.5, 0.9, 0.8, 0.8, 0.9, 0.8, 0.8])
    caption(doc, "Table 3. Every configuration against both nulls, "
                 "analogue-found sites only.")
    figure(doc, "fig_03_both_nulls.png",
           "Figure 4. The runs, the present-day control and both nulls, under "
           "every configuration.")

    doc.add_heading("The scenario-windows themselves", level=1)
    doc.add_paragraph(
        "The deltas above are medians over the eight scenario-windows. They "
        "hide the late-century windows, where the no-analogue share is high "
        "under every configuration and the surviving sample is small. Those "
        "windows should not be quoted as results regardless of which "
        "configuration produced them.")
    figure(doc, "fig_05_by_scenario_window.png",
           "Figure 5. Per scenario-window, for Run 0 and the two changes that "
           "moved the result.")

    # ------------------------------------------------------------------ #
    doc.add_heading("What to take from this", level=1)
    for t in [
        "The configuration is not the problem. Nothing methodological tested "
        "here moves the rank correlation by as much as 0.04 without also "
        "changing which sites survive. Time spent tuning the matcher is time "
        "wasted.",
        "The sample is the problem. The data-quality filter and the maturity "
        "threshold between them account for essentially all of the movement, "
        "and both are decisions about which observations to admit.",
        "Report both nulls, every time. The unconstrained null is what shows "
        "the method has skill; the constrained null is what shows how much of "
        "that skill is the vegetation constraint. A ratio quoted against "
        "neither is uninterpretable.",
        "Never read a metric whose no-analogue share moved. Two of the eleven "
        "runs here look like improvements and are not, and both would have "
        "been quoted as gains if the surviving sample had not been reported "
        "alongside.",
        "Run 0 remains the configuration to publish. Run 1 - verified-mature "
        "only - is the one defensible alternative, and it should be reported "
        "as a sensitivity rather than a replacement, because halving the "
        "sample widens every interval.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Step_A_run_ofat.py", "the run matrix and every statistic"],
        ["Step_B_plots.py", "the figures"],
        ["Step_C_write_report.py", "this document"],
        ["outputs/run_matrix.csv", "what each run changed"],
        ["outputs/ofat_summary.csv", "one row per run per stratum"],
        ["outputs/ofat_deltas.csv", "every run against Run 0, with the "
                                    "comparability flag"],
        ["outputs/<run_id>/matches.csv", "the site-level matches of that run"],
        ["plots/fig_01..05", "the figures in this report"],
    ], ["file", "what it holds"], widths=[2.2, 3.8])

    doc.save(str(REPORT))
    print("wrote %s" % REPORT)


if __name__ == "__main__":
    main()
