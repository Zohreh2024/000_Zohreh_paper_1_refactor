"""
Run 3, step 1 - what is actually wrong with the stem-level biomass.

The run was proposed as: 12,505 Eucalyptus stems in 199 survey events carry the
"single stemmed acacia trees" allometry, their masses do not scale with
diameter, so recompute those records with a eucalypt allometry.

The first half checks out almost exactly. The second half does not survive
testing, and the reason matters more than the original proposal.

WHAT IS CONFIRMED
-----------------
Eucalyptus stems carrying the acacia model: 12,471 stems in 199 survey events -
the event count is exact, the stem count within 0.3 per cent of the proposal
(the small difference is how the species string is matched). TERN Australia
supplies 8,985 and CSIRO 2,857. Their masses do not scale with diameter:
Spearman between diameter and mass is -0.169, the largest stem in the group
(479 cm) is assigned 0 kg, and a 160 cm stem is assigned 11 kg.

WHAT DOES NOT SURVIVE
---------------------
The mis-assignment cannot be the cause, because the correctly assigned stems
behave exactly the same way.

  Regressing ln(mass) on ln(diameter) for the 166,565 stems carrying the
  "Eucalypt trees" model gives R2 = 0.013 and a NEGATIVE slope.

  It is not a mixing artefact. Holding the survey event, the plot, the subplot,
  the allometric model AND the species all constant, across 2,133 such groups
  the median Spearman between diameter and mass is -0.004. None exceeds 0.9.

  In the largest single subplot - 4,796 stems on one hectare - a 0.89 cm stem
  is assigned 486 kg and a 98 cm stem 48 kg.

The library's own documentation says `diameter` is "the explanatory variable in
the allometric model" and `agb_drymass` is the "above-ground dry standing
biomass of tree/shrub (kg)". Within one model and one species, mass is
therefore a deterministic increasing function of diameter. In the delivered
file it is not a function of diameter at all.

The per-event SUM is nevertheless sound: summed by survey and divided by the
sampled area it reproduces the site table's reported biomass at Spearman 0.915.
A permutation of a column preserves its sum, and that is what this looks like -
the mass column is not aligned, row for row, with the stem attributes beside
it.

WHAT THAT MEANS FOR THE PROPOSED FIX
------------------------------------
It cannot be carried out as specified. Identifying "the mis-allometried
records" requires the model label to correspond to the species, and it does
not: the same file assigns "Eucalypt trees" to Myrsine, Zanthoxylum and Ficus.
The label travels with the mass column, not with the stem. So there is no
subset that can be recomputed and merged back, because no record's mass, model
and diameter can be assumed to belong together.

What CAN be done is stronger, and Step_02 does it: discard the mass column
entirely and rebuild plot biomass from the diameters alone, for every survey
that has stem data. The diameters are a direct measurement and are internally
consistent - they are what the basal area agrees with.

Reads   ../../../NBL_download/biolib_treelist.csv, biolib_sitelist.csv
Writes  outputs/allometry_diagnosis.csv
        outputs/mis_assigned_by_source.csv
        outputs/within_group_scaling.csv
        plots/fig_01_mass_vs_diameter.png

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_diagnose_allometry.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt                                # noqa: E402
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402
from scipy import stats                                        # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"
PLOT_DIR = HERE / "plots"

SURFACE, INK, INK_2, GRID_C = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_OK, C_BAD = "#2a78d6", "#e34948"

ACACIA = "Single stemmed acacia trees"
EUCALYPT = "Eucalypt trees"


def nbl_dir():
    for d in [HERE] + list(HERE.parents):
        p = d / "National_biomass_library" / "NBL_download"
        if p.exists():
            return p
        if (d / "NBL_download").exists():
            return d / "NBL_download"
    raise SystemExit("NBL_download not found above %s" % HERE)


plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.titlesize": 11.5,
    "axes.labelsize": 10, "font.size": 10,
    "axes.edgecolor": "#c9c8c4", "savefig.bbox": "tight",
})


def tidy(ax):
    ax.tick_params(labelsize=9, colors=INK_2, length=2.5, width=0.6)
    ax.grid(color=GRID_C, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.6)
        ax.spines[sp].set_color("#c9c8c4")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    return ax


def load():
    NBL = nbl_dir()
    t = pd.read_csv(NBL / "biolib_treelist.csv", low_memory=False,
                    usecols=["obs_key", "source", "species", "plot", "subplot",
                             "subplotarea_ha", "diameter", "agb_drymass",
                             "agb_allometric_model"])
    for c in ("diameter", "agb_drymass", "subplotarea_ha"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["diameter", "agb_drymass"])
    t = t[t["diameter"] > 0].reset_index(drop=True)
    s = pd.read_csv(NBL / "biolib_sitelist.csv", low_memory=False,
                    usecols=["obs_key", "agb_drymass_ha", "sampledarea_ha"])
    for c in ("agb_drymass_ha", "sampledarea_ha"):
        s[c] = pd.to_numeric(s[c], errors="coerce")
    return t, s


def within_group_scaling(t, keys, min_n):
    """Spearman(diameter, mass) inside each group - the decisive test."""
    out = []
    for _, g in t.groupby(keys, sort=False):
        if len(g) < min_n:
            continue
        r = stats.spearmanr(g["diameter"].values,
                            g["agb_drymass"].values).correlation
        if np.isfinite(r):
            out.append(r)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-group", type=int, default=25)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    t, s = load()
    euc = t["species"].fillna("").str.strip().str.lower().str.startswith(
        "eucalyptus")
    mis = euc & (t["agb_allometric_model"] == ACACIA)

    # ---- 1. the claim, checked --------------------------------------- #
    by_src = t[mis].groupby("source").agg(
        stems=("diameter", "size"), events=("obs_key", "nunique"),
        diameter_max=("diameter", "max"),
        mass_median=("agb_drymass", "median")).reset_index().sort_values(
        "stems", ascending=False)
    by_src.to_csv(OUT_DIR / "mis_assigned_by_source.csv", index=False)
    print("Eucalyptus stems carrying the acacia model: %s stems, %d events"
          % (format(int(mis.sum()), ","), t.loc[mis, "obs_key"].nunique()))
    print(by_src.to_string(index=False, float_format=lambda v: "%.1f" % v))

    m = t[mis]
    rho_mis = stats.spearmanr(m["diameter"], m["agb_drymass"]).correlation

    # ---- 2. the same test on the CORRECTLY assigned stems ------------ #
    ok = t[t["agb_allometric_model"] == EUCALYPT]
    x, y = np.log(ok["diameter"].values), np.log(
        ok["agb_drymass"].clip(lower=1e-6).values)
    slope, inter = np.polyfit(x, y, 1)
    r2 = 1 - ((y - (inter + slope * x)) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    subplot_rs = within_group_scaling(
        t, ["obs_key", "plot", "subplot"], args.min_group)
    strict_rs = within_group_scaling(
        t, ["obs_key", "plot", "subplot", "agb_allometric_model", "species"],
        args.min_group)

    # ---- 3. is the SUM still right? ---------------------------------- #
    agg = t.groupby("obs_key")["agb_drymass"].sum().rename("kg").reset_index()
    j = agg.merge(s, on="obs_key").dropna()
    j = j[(j["sampledarea_ha"] > 0) & (j["agb_drymass_ha"] > 0)]
    implied = j["kg"] / 1000 / j["sampledarea_ha"]
    rho_sum = stats.spearmanr(implied, j["agb_drymass_ha"]).correlation

    diag = pd.DataFrame([
        dict(test="Eucalyptus stems on the acacia model",
             value=int(mis.sum()), note="%d survey events"
             % t.loc[mis, "obs_key"].nunique()),
        dict(test="spearman(diameter, mass), those stems",
             value=round(float(rho_mis), 3),
             note="largest stem %.0f cm assigned %.0f kg"
             % (m["diameter"].max(),
                m.loc[m["diameter"].idxmax(), "agb_drymass"])),
        dict(test="R2 of ln(mass) on ln(diameter), CORRECT eucalypt stems",
             value=round(float(r2), 4),
             note="slope %+.3f on %s stems" % (slope, format(len(ok), ","))),
        dict(test="median spearman within subplot",
             value=round(float(np.median(subplot_rs)), 4),
             note="%d subplots, %.1f%% above 0.9"
             % (len(subplot_rs), 100 * np.mean(subplot_rs > 0.9))),
        dict(test="median spearman within subplot+model+species",
             value=round(float(np.median(strict_rs)), 4),
             note="%d groups, %.1f%% above 0.9"
             % (len(strict_rs), 100 * np.mean(strict_rs > 0.9))),
        dict(test="spearman(sum of stems / area, reported plot AGB)",
             value=round(float(rho_sum), 3),
             note="a permutation preserves a sum"),
    ])
    diag.to_csv(OUT_DIR / "allometry_diagnosis.csv", index=False)
    pd.DataFrame({"within_subplot": pd.Series(subplot_rs),
                  "within_subplot_model_species": pd.Series(strict_rs)}).to_csv(
        OUT_DIR / "within_group_scaling.csv", index=False)

    print("\n=== diagnosis ===")
    print(diag.to_string(index=False))
    print("\nThe correctly assigned stems fail the same test as the "
          "mis-assigned ones,\nso the model label is not the cause. The mass "
          "column is not aligned with\nthe stem attributes. Step_02 rebuilds "
          "biomass from the diameters instead.")

    # ---- 4. the figure ------------------------------------------------ #
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.2))
    ax = tidy(axes[0])
    samp = ok.sample(min(20000, len(ok)), random_state=0)
    ax.scatter(samp["diameter"], samp["agb_drymass"], s=5, alpha=0.18,
               color=C_BAD, linewidths=0)
    ax.set(xlim=(0, np.percentile(ok["diameter"], 99)),
           ylim=(0, np.percentile(ok["agb_drymass"], 99)))
    ax.set_xlabel("stem diameter (cm)")
    ax.set_ylabel("reported stem dry mass (kg)")
    ax.set_title("a) Correctly assigned eucalypt stems, R$^2$ = %.3f" % r2,
                 loc="left")
    ax.text(0.97, 0.95, "mass should be a rising\nfunction of diameter.\n"
            "It is not.", transform=ax.transAxes, ha="right", va="top",
            fontsize=9, color=INK_2)

    ax = tidy(axes[1])
    bins = np.linspace(-1, 1, 41)
    ax.hist(subplot_rs, bins=bins, color=C_BAD, alpha=0.65,
            label="within a subplot (%d)" % len(subplot_rs), zorder=3)
    ax.hist(strict_rs, bins=bins, histtype="step", lw=2.2, color=INK,
            label="within subplot, model and species (%d)" % len(strict_rs),
            zorder=4)
    ax.axvline(0, color=INK_2, lw=1.1, ls="--", zorder=5)
    ax.set_xlabel("Spearman correlation of diameter with mass, within group")
    ax.set_ylabel("groups")
    ax.set_title("b) Holding everything constant changes nothing", loc="left")
    ax.legend(fontsize=8.6, frameon=False)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "fig_01_mass_vs_diameter.png", dpi=200)
    plt.close(fig)
    print("\ntables in %s" % OUT_DIR)


if __name__ == "__main__":
    main()
