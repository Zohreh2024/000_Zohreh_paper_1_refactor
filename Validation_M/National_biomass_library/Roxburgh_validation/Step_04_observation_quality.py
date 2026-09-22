"""
Step 04 - is the observation sound, and what else is it measuring?

Step_03 shows that New_M_2019 has no rank skill against these observations when
the sample is built the way Roxburgh built his (Spearman -0.14), and reaches
+0.42 only under the full stack of filters the rest of this repository applies.
Before reading anything into that, the observation itself has to be checked. Two
questions, in order.

1. IS THE BIOMASS FIELD RIGHT?
   The library reports `agb_drymass_ha` per plot, and separately lists every
   stem with its own `agb_drymass` in kg, the allometric model used, and the
   subplot area it was measured in. So the plot figure can be rebuilt from the
   stems and the two compared:

       AGB(t/ha) = sum of stem dry mass in a subplot / 1000 / subplot area,
                   averaged over the subplots of that survey

   This is not an independent estimate - both come from the same allometrics -
   but it does test the aggregation, the subplot areas and the per-hectare
   scaling, which is where this kind of table usually goes wrong. Covers the
   2,449 surveys that carry stem data.

2. WHAT ELSE IS THE PER-HECTARE FIGURE RESPONDING TO?
   A per-hectare figure from a small plot is one tree multiplied by a large
   number. The correlation of observed biomass with PLOT AREA measures how much
   of the spread is sampling geometry rather than vegetation, and the same
   correlation computed inside each provider separates the provider's choice of
   plot size from the provider's landscape.

Nothing here is a criticism of the library, which is a stem inventory and was
not assembled to be a wall-to-wall biomass map. It is a statement about what a
comparison against it can and cannot resolve.

Reads   outputs/records.csv
        ../NBL_download/biolib_treelist.csv        274,228 stems
        ../NBL_download/biolib_sitelist.csv
Writes  outputs/observation_quality.csv        the rebuild, per survey
        outputs/observation_quality_summary.csv
        outputs/provider_effects.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_04_observation_quality.py
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
NBL_DIR = HERE.parent / "NBL_download"
OUT_DIR = HERE / "outputs"

TREES = NBL_DIR / "biolib_treelist.csv"
SITES = NBL_DIR / "biolib_sitelist.csv"
KEY_LAYER = "M_revised_Roxburgh"


def rho(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    g = np.isfinite(a) & np.isfinite(b)
    if g.sum() < 10:
        return np.nan
    return float(sps.spearmanr(a[g], b[g]).correlation)


def rebuild_from_stems():
    """Plot biomass per hectare, rebuilt from the stem list.

    Aggregated subplot by subplot because the subplot is the unit that carries
    an area: summing every stem of a survey and dividing by one area would be
    wrong wherever a survey has subplots of different sizes.
    """
    t = pd.read_csv(TREES, low_memory=False,
                    usecols=["obs_key", "source", "plot", "subplot",
                             "subplotarea_ha", "subplotdmin", "diameter",
                             "agb_drymass", "agb_allometric_model"])
    t["agb_drymass"] = pd.to_numeric(t["agb_drymass"], errors="coerce")
    t["subplotarea_ha"] = pd.to_numeric(t["subplotarea_ha"], errors="coerce")
    t = t.dropna(subset=["agb_drymass", "subplotarea_ha"])
    t = t[t["subplotarea_ha"] > 0]

    per_subplot = t.groupby(["obs_key", "plot", "subplot"]).agg(
        agb_kg=("agb_drymass", "sum"),
        area_ha=("subplotarea_ha", "first"),
        stems=("diameter", "size"),
        dmin=("subplotdmin", "first")).reset_index()
    per_subplot["agb_t_ha"] = (per_subplot["agb_kg"] / 1000.0
                               / per_subplot["area_ha"])

    out = per_subplot.groupby("obs_key").agg(
        agb_rebuilt=("agb_t_ha", "mean"),
        subplots=("agb_t_ha", "size"),
        stems=("stems", "sum"),
        subplot_area_ha=("area_ha", "median"),
        dmin=("dmin", "median")).reset_index()
    models = (t.groupby("obs_key")["agb_allometric_model"]
              .agg(lambda v: v.value_counts().index[0]).rename("allometric"))
    return out.merge(models, on="obs_key", how="left")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-n", type=int, default=40,
                    help="providers with fewer records than this are pooled "
                         "into 'other'")
    args = ap.parse_args()

    d = pd.read_csv(OUT_DIR / "records.csv", low_memory=False)
    print("%s records under test" % format(len(d), ","))

    # ---- 1. the rebuild -------------------------------------------------- #
    rb = rebuild_from_stems()
    print("rebuilt %s surveys from %s stems"
          % (format(len(rb), ","), format(int(rb["stems"].sum()), ",")))

    site = pd.read_csv(SITES, low_memory=False,
                       usecols=["obs_key", "source", "agb_drymass_ha",
                                "live_basal_area_ha", "sampledarea_ha"])
    site["agb_drymass_ha"] = pd.to_numeric(site["agb_drymass_ha"],
                                           errors="coerce")
    m = rb.merge(site, on="obs_key", how="inner").dropna(
        subset=["agb_rebuilt", "agb_drymass_ha"])
    m["ratio"] = m["agb_rebuilt"] / m["agb_drymass_ha"].replace(0, np.nan)
    m.to_csv(OUT_DIR / "observation_quality.csv", index=False)

    r = rho(m["agb_rebuilt"], m["agb_drymass_ha"])
    print("\n--- 1. the library's plot figure against a rebuild from its own "
          "stems ---")
    print("  n = %s surveys" % format(len(m), ","))
    print("  Spearman                      %+.3f" % r)
    print("  median rebuilt / reported     %.3f" % float(m["ratio"].median()))
    print("  within 20%% of each other      %.1f%%"
          % float(100 * ((m["ratio"] > 0.8) & (m["ratio"] < 1.2)).mean()))
    print("  %s" % ("the plot figure IS the stem sum - the field is sound"
                    if r > 0.85 else
                    "the two DISAGREE - the plot figure is not the stem sum"))

    # ---- 2. what else the per-hectare figure responds to ----------------- #
    print("\n--- 2. what else the per-hectare figure is responding to ---")
    overall = {
        "observed AGB vs plot area": rho(d["agb"], d["area_ha"]),
        "observed AGB vs live basal area": rho(d["agb"], d["live_ba"]),
        "observed AGB vs %s" % KEY_LAYER: rho(d["agb"], d[KEY_LAYER]),
        "plot area vs %s" % KEY_LAYER: rho(d["area_ha"], d[KEY_LAYER]),
    }
    for k, v in overall.items():
        print("  %-38s %+.3f" % (k, v))

    rows = []
    for src, s in d.groupby("source"):
        if len(s) < args.min_n:
            continue
        rows.append(dict(
            source=src, n=len(s),
            plot_area_median=float(s["area_ha"].median()),
            obs_median=float(s["agb"].median()),
            M_median=float(s[KEY_LAYER].median()),
            rho_obs_vs_M=rho(s["agb"], s[KEY_LAYER]),
            rho_obs_vs_area=rho(s["agb"], s["area_ha"]),
            rho_obs_vs_basal=rho(s["agb"], s["live_ba"])))
    prov = pd.DataFrame(rows).sort_values("n", ascending=False)
    prov.to_csv(OUT_DIR / "provider_effects.csv", index=False)

    print("\n  by provider - rho of observed biomass against the layer, "
          "against plot area, and against its own basal area")
    print(prov[["source", "n", "plot_area_median", "obs_median",
                "rho_obs_vs_M", "rho_obs_vs_area"]]
          .to_string(index=False, float_format=lambda v: "%.3f" % v,
                     max_colwidth=38))

    # plot-area bands, since the area effect is the largest single term
    band = pd.cut(d["area_ha"], [0, 0.05, 0.15, 0.3, 0.45, 1e3])
    bands = d.groupby(band).apply(lambda s: pd.Series(dict(
        n=len(s), obs_median=float(s["agb"].median()),
        M_median=float(s[KEY_LAYER].median()),
        rho_obs_vs_M=rho(s["agb"], s[KEY_LAYER])))).reset_index()
    bands.columns = ["plot_area_band"] + list(bands.columns[1:])
    print("\n  by plot size")
    print(bands.to_string(index=False, float_format=lambda v: "%.3f" % v))

    summary = pd.DataFrame(
        [dict(quantity=k, spearman=v) for k, v in overall.items()]
        + [dict(quantity="rebuilt vs reported plot AGB", spearman=r)])
    summary.to_csv(OUT_DIR / "observation_quality_summary.csv", index=False)
    bands.to_csv(OUT_DIR / "plot_area_bands.csv", index=False)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
