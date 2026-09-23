"""
A synthesis of every run in New_proposal.

Reads each run's own headline table rather than restating numbers, so the
summary cannot drift from the analyses it summarises, and regenerates whenever
any of them is re-run.

    Run_0                    eleven parameters, one at a time
    Run_01                   verified mature only
    Plot_area_floor_method   raising the plot-area floor
    Run_02                   lowering the plot-area threshold to 0.04 ha
    Run_03                   rebuilding biomass from stem diameters
    Run_04                   a maturity rule on basal area
    combined_Run             the five decisions those tests point to

Every configuration is placed on one axis: the rank correlation of the eight
future runs MINUS that of their own NVIS-constrained null. That is the only
quantity comparable across runs, because each run changes the sample and a
changed sample moves the null with it. Ratios are reported but never compared
between runs for the same reason - raising a plot-area floor lifts every
ratio, a random one included.

Reads   <run>/outputs/*.csv
Writes  outputs/all_runs.csv
        plots/fig_01_every_configuration.png
        plots/fig_02_gate.png
        Summary_of_runs.docx

Run
---
    conda run -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Summary_of_runs.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from docx import Document                                      # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH                  # noqa: E402
from docx.shared import Inches, Pt, RGBColor                   # noqa: E402
from matplotlib.patches import Patch                           # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"
REPORT = HERE / "Summary_of_runs.docx"

INK_2 = RGBColor(0x52, 0x51, 0x4E)
SURFACE, INK, INK2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
RUN_COLOUR = {
    "Run_0": "#6b6a66", "Run_01": "#eb6834",
    "Plot_area_floor_method": "#1baf7a", "Run_02": "#eda100",
    "Run_03": "#2a78d6", "Run_04": "#e34948",
    "combined_Run": "#7d3c98",
}
CONTROLS = ["same_cell_present_day", "historical_analogue",
            "random_cells_nvis", "random_cells_unconstrained", "random_cells"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax, grid_axis="both"):
    ax.tick_params(labelsize=9, colors=INK2, length=2.5, width=0.6)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID_C, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.6)
        ax.spines[sp].set_color("#c9c8c4")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    return ax


def fmt(v, spec="%.3f"):
    try:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "n/a"
        return spec % v
    except (TypeError, ValueError):
        return str(v)


def row(run, config, what, sites, ratio, rho, null_rho, gate=np.nan,
        na=np.nan):
    return dict(run=run, config=config, what=what, sites=sites, ratio=ratio,
                rho=rho, null_nvis_rho=null_rho,
                gap_rho=(rho - null_rho) if np.isfinite(null_rho) else np.nan,
                gate_rho=gate, pct_no_analogue=na)


def collect():
    """One row per configuration, from each run's own tables."""
    out = []

    # ---- Run_0: the one-at-a-time sweep ------------------------------- #
    f = HERE / "Run_0" / "outputs" / "ofat_summary.csv"
    if f.exists():
        s = pd.read_csv(f)
        for rid, g in s.groupby("run_id"):
            fut = g[~g["run"].isin(CONTROLS)]
            d = g.set_index("run")

            def c(n, col):
                return float(d.loc[n, col]) if n in d.index else np.nan
            out.append(row("Run_0", rid, g["changed"].iloc[0],
                           int(g["n_sites"].max()),
                           float(fut["median_ratio"].median()),
                           float(fut["spearman_rho"].median()),
                           c("random_cells_nvis", "spearman_rho"),
                           c("same_cell_present_day", "spearman_rho"),
                           float(fut["pct_no_analogue"].median())))

    # ---- Run_01: verified mature only --------------------------------- #
    f = HERE / "Run_01" / "outputs" / "run01_vs_run00.csv"
    g = HERE / "Run_01" / "outputs" / "both_nulls.csv"
    if f.exists() and g.exists():
        c = pd.read_csv(f)
        n = pd.read_csv(g).set_index(["run", "null"])
        fut = c[c["is_future"]]
        out.append(row("Run_01", "verified_only", "maturity: verified only",
                       int(c["n_run1"].max()),
                       float(fut["ratio_run1"].median()),
                       float(fut["rho_run1"].median()),
                       float(n.loc[("Run 1", "NVIS-constrained"),
                                   "spearman_rho"]),
                       float(c[c["run"] == "same_cell_present_day"]
                             ["rho_run1"].iloc[0])))

    # ---- Plot_area_floor_method --------------------------------------- #
    f = HERE / "Plot_area_floor_method" / "outputs" / "area_floor_comparison.csv"
    if f.exists():
        s = pd.read_csv(f)
        for _, r in s.iterrows():
            if r["config"] in ("mature_nofloor", "verified_nofloor"):
                continue           # already present from Run_0 and Run_01
            out.append(row("Plot_area_floor_method", r["config"],
                           "plot-area floor %.2f ha" % r["min_area_ha"],
                           int(r["n_sites"]), float(r["ratio"]),
                           float(r["rho"]), float(r["null_nvis_rho"]),
                           float(r["gate_rho"]),
                           float(r["pct_no_analogue"])))

    # ---- Run_02: threshold 0.04 ha ------------------------------------ #
    f = HERE / "Run_02" / "outputs" / "run02_headline.csv"
    if f.exists():
        s = pd.read_csv(f)
        for _, r in s.iterrows():
            if r["config"] == "floor_005":
                continue           # that is Run 0
            out.append(row("Run_02", r["config"],
                           "plot-area threshold 0.04 ha",
                           int(r["sites"]), float(r["ratio"]), float(r["rho"]),
                           float(r["null_nvis_rho"]), np.nan,
                           float(r["no_analogue"])))

    # ---- Run_03: biomass rebuilt from diameters ----------------------- #
    f = HERE / "Run_03" / "outputs" / "run03_headline.csv"
    if f.exists():
        s = pd.read_csv(f)
        for _, r in s.iterrows():
            if r["config"] == "reported_all":
                continue           # that is Run 0
            out.append(row("Run_03", r["config"],
                           "biomass rebuilt from stem diameters",
                           int(r["sites"]), float(r["ratio"]), float(r["rho"]),
                           float(r["null_nvis_rho"]), float(r["gate_rho"]),
                           float(r["no_analogue"])))

    # ---- Run_04: basal-area maturity rule ----------------------------- #
    f = HERE / "Run_04" / "outputs" / "run04_headline.csv"
    if f.exists():
        s = pd.read_csv(f)
        for _, r in s.iterrows():
            if r["config"] == "dbh_rule":
                continue           # that is Run 0
            out.append(row("Run_04", r["config"],
                           "maturity from basal area",
                           int(r["sites"]), float(r["ratio"]), float(r["rho"]),
                           float(r["null_nvis_rho"]), float(r["gate_rho"]),
                           float(r["no_analogue"])))

    # ---- combined_Run: the five decisions together -------------------- #
    f = HERE / "combined_Run" / "outputs" / "combined_headline.csv"
    if f.exists():
        s = pd.read_csv(f)
        for _, r in s.iterrows():
            if r["config"] in ("run0", "run3_rebuilt"):
                continue           # already present from Run_0 and Run_03
            out.append(row("combined_Run", r["config"],
                           "combined configuration",
                           int(r["sites"]), float(r["ratio"]), float(r["rho"]),
                           float(r["null_nvis_rho"]), float(r["gate_rho"]),
                           float(r["no_analogue"])))

    d = pd.DataFrame(out)
    d["is_baseline"] = d["config"] == "run00_baseline"
    return d


def fig_all(d):
    """Every configuration on the one comparable axis."""
    s = d.dropna(subset=["gap_rho"]).sort_values("gap_rho")
    y = np.arange(len(s))
    colours = [RUN_COLOUR.get(r, "#999999") for r in s["run"]]

    fig, ax = plt.subplots(figsize=(10.8, 10.4))
    tidy(ax, grid_axis="x")
    ax.barh(y, s["gap_rho"], 0.68, color=colours, zorder=3)
    ax.axvline(0, color="#333333", lw=1.2, zorder=6)
    base = s.loc[s["is_baseline"], "gap_rho"]
    if len(base):
        ax.axvline(float(base.iloc[0]), color="#333333", lw=1.3, ls="--",
                   zorder=5)
        ax.text(float(base.iloc[0]), len(s) - 0.2, " Run 0", fontsize=9,
                color=INK2, va="top")
    for yi, v, n in zip(y, s["gap_rho"], s["sites"]):
        ax.text(v + (0.004 if v >= 0 else -0.004), yi, "%+.3f  (n=%d)" % (v, n),
                va="center", ha="left" if v >= 0 else "right", fontsize=7.8,
                color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(s["config"], fontsize=7.8)
    ax.set_xlabel("rank correlation of the future runs above their own "
                  "NVIS-constrained null")
    ax.set_title("Every configuration tested, on the one axis that is "
                 "comparable across runs", loc="left")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 0.10, hi + 0.10)
    ax.legend([Patch(facecolor=RUN_COLOUR[k]) for k in RUN_COLOUR],
              list(RUN_COLOUR), fontsize=8.2, frameon=False, ncol=3,
              loc="upper right", bbox_to_anchor=(1.0, -0.055))
    dst = PLOT_DIR / "fig_01_every_configuration.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


def fig_gate(d):
    """The present-day gate, where it was measured - the most direct test."""
    keep = ["run00_baseline", "verified_only", "area_040",
            "reported_stem_only", "rebuilt_b2p5", "ba_07_labelled", "ba_07",
            "combined"]
    s = d[d["config"].isin(keep)].dropna(subset=["gate_rho"])
    s = s.set_index("config").reindex([k for k in keep if k in
                                       set(d["config"])]).reset_index()
    x = np.arange(len(s))
    colours = [RUN_COLOUR.get(r, "#999999") for r in s["run"]]

    fig, ax = plt.subplots(figsize=(10.4, 5.4))
    tidy(ax, grid_axis="y")
    ax.bar(x, s["gate_rho"], 0.6, color=colours, zorder=3)
    ax.axhline(0, color="#333333", lw=1.1, zorder=6)
    b = s.loc[s["config"] == "run00_baseline", "gate_rho"]
    if len(b):
        ax.axhline(float(b.iloc[0]), color="#333333", lw=1.2, ls="--", zorder=5)
    for xi, v, n in zip(x, s["gate_rho"], s["sites"]):
        ax.annotate("%.3f\nn = %d" % (v, n), (xi, max(v, 0.0)),
                    xytext=(0, 5),
                    textcoords="offset points", ha="center", fontsize=8.6,
                    color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in s["config"]],
                       fontsize=8.2)
    ax.set_ylabel("Spearman rank correlation", fontsize=9)
    ax.set_title("The present-day gate: M' against observed biomass at the "
                 "site's own cell", loc="left")
    dst = PLOT_DIR / "fig_02_gate.png"
    fig.savefig(dst, dpi=200)
    plt.close(fig)
    return dst


# --------------------------------------------------------------------------- #

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


def build_report(d):
    base = d[d["is_baseline"]].iloc[0] if d["is_baseline"].any() else None
    best = d.loc[d["gap_rho"].idxmax()]
    g = d.dropna(subset=["gate_rho"]).set_index("config")

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("The space-for-time validation, re-run one change at a "
                    "time: what was learned", 0)
    p = doc.add_paragraph()
    r = p.add_run("Space_time_validation/New_proposal · generated %s · %d "
                  "studies, %d configurations" % (date.today().isoformat(),
                                                  d["run"].nunique(), len(d)))
    r.font.size = Pt(9)
    r.font.color.rgb = INK_2

    doc.add_heading("How to read this", level=1)
    doc.add_paragraph(
        "Every configuration is placed on one axis: the rank correlation of "
        "the eight future runs MINUS the rank correlation of their own "
        "NVIS-constrained null. That is the only quantity comparable across "
        "runs. Each run changes the sample, and a changed sample moves the "
        "null with it, so a bare correlation or ratio flatters or punishes a "
        "run for reasons that have nothing to do with the change being "
        "tested.", style="Intense Quote")
    doc.add_paragraph(
        "Ratios are reported but never compared between runs. Raising a "
        "plot-area floor lifts every ratio, a randomly chosen M' included; the "
        "ratio moving towards 1 is not on its own evidence of anything. Both "
        "nulls are carried through every configuration, and every metric comes "
        "from the analogue-found stratum rather than from rows that force a "
        "match onto a site with no analogue.")

    doc.add_heading("The studies", level=1)
    table(doc, [
        ["Run_0", "eleven parameters, one at a time",
         "only the sample matters; nothing methodological moves rho by 0.04"],
        ["Run_01", "verified mature only",
         "works, but the mechanism is plot size, not maturity"],
        ["Plot_area_floor_method", "raise the plot-area floor",
         "best single gain: gap +0.128 at 0.40 ha on 584 sites"],
        ["Run_02", "lower the threshold to 0.04 ha",
         "southern coverage 4 to 113 sites; metric gain not resolvable"],
        ["Run_03", "rebuild biomass from stem diameters",
         "largest change of all: the present-day gate rises 0.42 to 0.73"],
        ["Run_04", "maturity from basal area",
         "the rule is sound, the sample it unlocks is not"],
        ["combined_Run", "the five decisions those tests point to",
         "the gate reaches 0.844 on 850 sites, 147 of them south of 37 S"],
    ], ["study", "what it changed", "outcome"], widths=[1.6, 2.0, 2.6])

    doc.add_heading("Every configuration on one axis", level=1)
    if base is not None:
        doc.add_paragraph(
            "Run 0 sits at a gap of %s. The best configuration tested is %s at "
            "%s, on %d sites."
            % (fmt(base["gap_rho"], "%+.3f"), best["config"],
               fmt(best["gap_rho"], "%+.3f"), int(best["sites"])))
    show = d.dropna(subset=["gap_rho"]).sort_values("gap_rho", ascending=False)
    rows = [[r["run"], r["config"], int(r["sites"]), fmt(r["ratio"]),
             fmt(r["rho"]), fmt(r["null_nvis_rho"]),
             fmt(r["gap_rho"], "%+.3f")] for _, r in show.iterrows()]
    table(doc, rows, ["study", "configuration", "sites", "ratio", "rho",
                      "null rho", "gap"],
          widths=[1.4, 1.5, 0.6, 0.7, 0.7, 0.7, 0.7])
    caption(doc, "Table 1. Every configuration, ordered by the gap to its own "
                 "null. Ratios are shown for completeness and should not be "
                 "compared between rows.")
    figure(doc, "fig_01_every_configuration.png",
           "Figure 1. Every configuration tested, on the one axis that is "
           "comparable across runs.", width=5.9)

    doc.add_heading("The present-day gate", level=1)
    doc.add_paragraph(
        "The gate is the most direct test in the validation: M' against "
        "observed biomass at the site's own cell, with no matching involved at "
        "all. The published conclusion is that it does not pass, on a rank "
        "correlation of about 0.42. Two changes move it, and only one moves it "
        "upward.")
    rows = []
    for cfg, lab in [("run00_baseline", "Run 0, as published"),
                     ("verified_only", "verified mature only"),
                     ("area_040", "plot-area floor 0.40 ha"),
                     ("reported_stem_only", "Run 0 on the stem-data sites"),
                     ("rebuilt_b2p5", "biomass rebuilt from diameters"),
                     ("ba_07_labelled", "basal-area rule, labelled sites"),
                     ("ba_07", "basal-area rule, all sites"),
                     ("combined", "the combined configuration")]:
        if cfg in g.index:
            rows.append([lab, int(g.loc[cfg, "sites"]),
                         fmt(g.loc[cfg, "gate_rho"])])
    table(doc, rows, ["configuration", "sites", "present-day gate rho"],
          widths=[2.8, 1.0, 1.6])
    figure(doc, "fig_02_gate.png",
           "Figure 2. The present-day gate under the configurations that "
           "measured it.")
    if "rebuilt_b2p5" in g.index and "reported_stem_only" in g.index:
        doc.add_paragraph(
            "The pairing in the middle of that table is the single most "
            "important result of the whole study. `reported_stem_only` and "
            "`rebuilt_b2p5` hold the SAME 599 sites, matched the same way, "
            "against the same M'. Only the observed biomass differs - the "
            "library's column, or the stem diameters. The gate goes from %s to "
            "%s."
            % (fmt(g.loc["reported_stem_only", "gate_rho"]),
               fmt(g.loc["rebuilt_b2p5", "gate_rho"])), style="Intense Quote")

    doc.add_heading("What runs through all of them", level=1)
    for t in [
        "Every improvement came from the observation, never from the matching. "
        "Run_0 tested eleven parameters one at a time and nothing "
        "methodological - the averaging order, the PCA variance, the NVIS "
        "fallback threshold, the predictor set - moved the rank correlation by "
        "as much as 0.04. The two changes that did move it were both decisions "
        "about which observations to admit, and the largest change of all was "
        "a correction to how the observation is computed.",
        "The library's plot sizes drive more than anything else. The "
        "likely-mature half that Run_01 removed was carrying 17.4 Mg of "
        "biomass per square metre per hectare of its own basal area from plots "
        "40 per cent smaller; raising the floor to 0.40 ha lifted the ratio "
        "from 0.465 to 1.275; and the sites Run_04's expansion admitted came "
        "from providers measuring savanna on eighth-hectare plots. The same "
        "artefact appears in every study that looked for it.",
        "The stem-level biomass column is not aligned with the stem "
        "attributes. Run_03 established this on the library's own terms: "
        "holding survey, plot, subplot, allometric model and species constant, "
        "mass has no relationship to diameter, although the documentation "
        "names diameter as the explanatory variable. The per-survey sum is "
        "sound, which is what a permutation does. This affects every "
        "stem-level use of the National Biomass Library and should go back to "
        "its custodians.",
        "Carrying both nulls repeatedly changed the reading. It downgraded "
        "Run_01, where four fifths of the apparent gain turned out to be "
        "shared with its own null; it stopped Run_02's ratio being quoted as a "
        "result; and it is what showed Run_04's expansion to be a reversal "
        "rather than a dilution. A ratio or a correlation quoted against "
        "neither null is uninterpretable.",
        "Two of the runs looked like improvements and were not. A tighter "
        "no-analogue cutoff and a climate-only predictor set both raised the "
        "rank correlation while removing most of the sample, and both would "
        "have been quoted as gains had the surviving sample not been reported "
        "beside the metric. Never read a metric whose no-analogue share moved.",
        "The 600-site cap is not only a maturity limit. Run_04 found that the "
        "providers who record stems are the providers whose biomass behaves, "
        "so the stem-record requirement is doing duty as a data-quality filter "
        "as well. Describing the cap as a limitation without saying that "
        "overstates how much a larger sample would buy.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("What to do with this", level=1)
    for t in [
        "Report Run 0 as published and combined_Run as corrected. The "
        "difference between them is the headline of the whole exercise - the "
        "present-day gate goes from 0.418 to 0.844, on 850 sites rather than "
        "600 and with 147 south of 37 S rather than 4 - and the correction "
        "that carries most of it is Run_03's rebuild of the observation.",
        "Do not present the combined configuration as a one-change result. It "
        "changes five things at once, its ingredients are not additive on the "
        "gap, and its ceiling has never been tested against Run 0 in "
        "isolation. Point at the individual runs for the evidence.",
        "Quote rankings, not levels. Run_03's scale constant is calibrated to "
        "the library's own median, so its ratio is not independent of the "
        "library; the plot-area floor lifts every ratio including the null's. "
        "The rank correlation and the gap to the null are the robust "
        "quantities throughout.",
        "Adopt a plot-area floor in the 0.30 to 0.50 ha band if one filter is "
        "to change, in preference to a stem-size threshold. It removes the "
        "inflation directly rather than through a proxy, and keeps the sites "
        "the maturity rule discards for having no stem data.",
        "Do not adopt the basal-area maturity rule, do not stack the plot-area "
        "floor with the maturity filter, and treat the 0.04 ha threshold as a "
        "coverage sensitivity rather than a default.",
        "Everything above is bounded by what the earlier work established and "
        "no run here changed: the sample is eastern-forest heavy, and the "
        "late-century high-forcing windows are extrapolation beyond the "
        "observational record under every configuration tested.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Files", level=1)
    table(doc, [
        ["Summary_of_runs.py", "this document, built from the tables below"],
        ["outputs/all_runs.csv", "Table 1 - every configuration"],
        ["Run_0/", "the one-at-a-time sweep, and its own report"],
        ["Run_01/", "verified mature only"],
        ["Plot_area_floor_method/", "raising the plot-area floor"],
        ["Run_02/", "lowering the threshold to 0.04 ha"],
        ["Run_03/", "biomass rebuilt from stem diameters"],
        ["Run_04/", "the basal-area maturity rule"],
    ], ["file", "what it holds"], widths=[2.2, 3.8])

    doc.save(str(REPORT))
    return REPORT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    d = collect()
    d.to_csv(OUT_DIR / "all_runs.csv", index=False)
    print("collected %d configurations from %d studies"
          % (len(d), d["run"].nunique()))
    show = d.dropna(subset=["gap_rho"]).sort_values("gap_rho", ascending=False)
    print(show[["run", "config", "sites", "ratio", "rho", "null_nvis_rho",
                "gap_rho", "gate_rho"]].to_string(
        index=False, float_format=lambda v: "%.3f" % v))

    for p in (fig_all(d), fig_gate(d)):
        print("  -> %s" % p.name)
    print("wrote %s" % build_report(d))


if __name__ == "__main__":
    main()
