"""
Step 5 - compare GEDI cell statistics against both present-day M' layers.

Reads the four Step 4 tables

    outputs/gedi_cells_{all,unburnt}_New_M_2019.csv
    outputs/gedi_cells_{all,unburnt}_baseline_M_1985-2014.csv

plus outputs/gedi_l4a_footprints.parquet (for forest type and footprint
error), and writes the tables and figures the report is built from:

    outputs/analysis/*.csv
    outputs/figures/*.png

## What is being tested, and why an envelope

M' is a MAXIMUM: the aboveground biomass a site can reach at maturity. GEDI
measures what stands there now, 2019-2024, after clearing, logging and fire.
GEDI below M' is therefore expected and proves nothing. GEDI above M' is the
only direct evidence against M', so every headline number here is an
exceedance rate, never an R2.

Three GEDI statistics are compared, from least to most demanding of M':

  mean     cell mean AGBD. Exceeding M' means the whole 1 km cell, on average,
           already carries more than its supposed maximum. Strongest evidence.
  p95_n30  95th percentile from 25 random draws of exactly 30 footprints. The
           upper envelope, with the footprint-count effect removed.
  p95_lo   p95_n30 recomputed on each footprint's lower bound
           (agbd - 1.645 * agbd_se, floored at 0). Single-footprint L4A
           predictions carry a large model error, and noise alone inflates an
           upper percentile; p95_lo is what survives if every footprint is
           pushed to the bottom of its 90% interval.

## Why FPI elasticity matters for FUTURE M'

Future M' is present M' scaled by Eq1(FPI_future) / Eq1(FPI_hist). GEDI cannot
see 2035-2100, but it can test the mechanism: across space, does biomass rise
with FPI as steeply as Eq. (1) says? The log-log slope of GEDI against FPI is
compared with the slope of each M' layer and with Eq. (1)'s own elasticity.
This is a space-for-time substitution and is reported as such.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import common as C

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ANA = OUT / "analysis"
FIG = OUT / "figures"

LAYERS = {
    "New_M_2019": "New_M_2019 (matched footing, Option B)",
    "baseline_M_1985-2014": "baseline_M_1985-2014 (Eq. 1 footing, Option A)",
}
SHORT = {"New_M_2019": "New_M_2019", "baseline_M_1985-2014": "baseline_M"}
COLOUR = {"New_M_2019": "#2a78d6", "baseline_M_1985-2014": "#eb6834"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

FPI_BINS = [0, 8, 10, 12, 14, 20]
N_FIXED, DRAWS = 30, 25


def eq1(fpi):
    return (6.011 * np.sqrt(fpi) - 5.291) ** 2


def eq1_elasticity(fpi):
    """d ln M / d ln FPI for M = (a sqrt(FPI) - b)^2."""
    s = 6.011 * np.sqrt(fpi)
    return s / (s - 5.291)


def spearman(a, b):
    from scipy.stats import spearmanr
    ok = np.isfinite(a) & np.isfinite(b)
    return float(spearmanr(a[ok], b[ok])[0])


def cell_extras(fp):
    """Per cell: evergreen-broadleaf share and the fixed-n lower-bound p95."""
    fp = fp.assign(lo=np.clip(fp.agbd - 1.645 * fp.agbd_se, 0, None),
                   ebf=(fp.pft_class == 2).astype(float),
                   rel_se=fp.agbd_se / np.maximum(fp.agbd, 1))
    g = fp.groupby("cell_id")
    out = pd.DataFrame({"ebf_frac": g.ebf.mean(),
                        "rel_se_median": g.rel_se.median()})
    # Draws only where the cell can supply N_FIXED footprints; the rest are
    # dropped by Step 4 anyway, and looping over them dominated the run time.
    big = out.index[g.size() >= N_FIXED]
    rng = np.random.default_rng(1)
    p95_lo = {}
    for cid, lo in fp[fp.cell_id.isin(big)].groupby("cell_id").lo:
        lo = lo.values
        draws = np.stack([rng.choice(lo, N_FIXED, replace=False)
                          for _ in range(DRAWS)])
        p95_lo[cid] = float(np.quantile(draws, 0.95, axis=1).mean())
    out["agbd_p95_lo"] = pd.Series(p95_lo)
    return out.reset_index()[["cell_id", "ebf_frac", "agbd_p95_lo",
                              "rel_se_median"]]


def load(tag, subset, extras):
    c = pd.read_csv(OUT / ("gedi_cells_%s_%s.csv" % (subset, tag)))
    return c.merge(extras, on="cell_id", how="left")


def overall_row(c, tag, subset):
    n30 = "agbd_p95_n%d" % N_FIXED
    p99 = c.agbd_p99.notna()
    return {
        "layer": tag, "footprints": subset, "cells": len(c),
        "M_median": c.m_prime.median(),
        "gedi_mean_median": c.agbd_mean.median(),
        "gedi_p95_n30_median": c[n30].median(),
        "gedi_p95_lo_median": c.agbd_p95_lo.median(),
        "ratio_M_over_p95_n30_median": (c.m_prime / c[n30]).median(),
        "spearman_M_vs_mean": spearman(c.m_prime.values, c.agbd_mean.values),
        "spearman_M_vs_p95_n30": spearman(c.m_prime.values, c[n30].values),
        "exceed_mean_pct": 100 * (c.agbd_mean > c.m_prime).mean(),
        "exceed_median_pct": 100 * (c.agbd_median > c.m_prime).mean(),
        "exceed_p95_lo_pct": 100 * (c.agbd_p95_lo > c.m_prime).mean(),
        "exceed_p95_n30_pct": 100 * (c[n30] > c.m_prime).mean(),
        "exceed_p95_naive_pct": 100 * (c.agbd_p95 > c.m_prime).mean(),
        "exceed_p99_pct_n100": (100 * (c.agbd_p99 > c.m_prime)[p99].mean()
                                if p99.any() else np.nan),
        "cells_with_p99": int(p99.sum()),
    }


def grouped(c, tag, by, label):
    n30 = "agbd_p95_n%d" % N_FIXED
    g = c.groupby(by, observed=True)
    t = pd.DataFrame({
        "cells": g.size(),
        "fpi_median": g.fpi_mean.median(),
        "M_median": g.m_prime.median(),
        "gedi_mean_median": g.agbd_mean.median(),
        "gedi_p95_n30_median": g[n30].median(),
        "exceed_mean_pct": 100 * g.apply(lambda d: (d.agbd_mean > d.m_prime).mean()),
        "exceed_p95_lo_pct": 100 * g.apply(lambda d: (d.agbd_p95_lo > d.m_prime).mean()),
        "exceed_p95_n30_pct": 100 * g.apply(lambda d: (d[n30] > d.m_prime).mean()),
    }).reset_index().rename(columns={by: label})
    t.insert(0, "layer", tag)
    t[label] = t[label].astype(str)
    return t


def by_region(c, tag):
    """Headline statistics per region, so no rate is read as national."""
    n30 = "agbd_p95_n%d" % N_FIXED
    rows = []
    for reg, g in c.groupby("region"):
        e = elasticity(g, tag, min_cells=100)
        rows.append({
            "layer": tag, "region": reg, "cells": len(g),
            "fpi_median": g.fpi_mean.median(),
            "ebf_cells_pct": 100 * (g.ebf_frac >= 0.9).mean(),
            "M_median": g.m_prime.median(),
            "gedi_mean_median": g.agbd_mean.median(),
            "gedi_p95_n30_median": g[n30].median(),
            "ratio_M_over_p95_n30_median": (g.m_prime / g[n30]).median(),
            "spearman_M_vs_p95_n30": spearman(g.m_prime.values, g[n30].values),
            "exceed_mean_pct": 100 * (g.agbd_mean > g.m_prime).mean(),
            "exceed_p95_lo_pct": 100 * (g.agbd_p95_lo > g.m_prime).mean(),
            "exceed_p95_n30_pct": 100 * (g[n30] > g.m_prime).mean(),
            "slope_M_prime": e.get("slope_M_prime", np.nan),
            "slope_gedi_p95_n30": e.get("slope_gedi_p95_n30", np.nan),
            "eq1_elasticity_at_median_fpi": e.get("eq1_elasticity_at_median_fpi",
                                                  np.nan),
            "elasticity_cells": e["cells"],
        })
    return pd.DataFrame(rows)


def elasticity(c, tag, min_cells=0):
    """OLS slope of ln(y) on ln(FPI), closed evergreen-broadleaf cells only."""
    n30 = "agbd_p95_n%d" % N_FIXED
    f = c[(c.ebf_frac >= 0.9) & (c.agbd_mean > 0) & (c.m_prime > 0)]
    if len(f) < max(min_cells, 3):
        return {"layer": tag, "cells": len(f)}
    x = np.log(f.fpi_mean.values)
    out = {"layer": tag, "cells": len(f),
           "fpi_median": float(np.median(f.fpi_mean)),
           "eq1_elasticity_at_median_fpi": float(eq1_elasticity(np.median(f.fpi_mean)))}
    for name, y in (("M_prime", f.m_prime), ("gedi_p95_n30", f[n30]),
                    ("gedi_mean", f.agbd_mean)):
        yy = np.log(y.values)
        b, a = np.polyfit(x, yy, 1)
        boots = []
        rng = np.random.default_rng(2)
        for _ in range(500):
            i = rng.integers(0, len(x), len(x))
            boots.append(np.polyfit(x[i], yy[i], 1)[0])
        out["slope_%s" % name] = float(b)
        out["slope_%s_lo95" % name] = float(np.percentile(boots, 2.5))
        out["slope_%s_hi95" % name] = float(np.percentile(boots, 97.5))
    return out


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def fig_scatter(data):
    import matplotlib.pyplot as plt
    n30 = "agbd_p95_n%d" % N_FIXED
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    for ax, tag in zip(axes, LAYERS):
        c = data[tag]
        ok = (c.m_prime > 0) & (c[n30] > 0)
        hb = ax.hexbin(c.m_prime[ok], c[n30][ok], gridsize=55, bins="log",
                       xscale="log", yscale="log", cmap="Blues", mincnt=1,
                       linewidths=0)
        lim = [10, 3000]
        ax.plot(lim, lim, color=INK, lw=1.2)
        ax.text(1900, 2500, "1:1", color=INK, fontsize=8.5, ha="right")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        style(ax)
        ax.set_title(SHORT[tag], fontsize=10, color=INK, loc="left")
        ax.set_xlabel("M' (t DM ha$^{-1}$)", fontsize=9, color=INK2)
        pct = 100 * (c[n30] > c.m_prime).mean()
        ax.text(12, 1500, "above 1:1: %.1f%% of cells" % pct, fontsize=8.5,
                color=INK)
    axes[0].set_ylabel("GEDI p95, fixed n = 30 (t DM ha$^{-1}$)", fontsize=9,
                       color=INK2)
    cb = fig.colorbar(hb, ax=axes, shrink=0.85, pad=0.02)
    cb.set_label("cells per hexagon (log)", fontsize=8.5, color=INK2)
    fig.savefig(FIG / "fig1_p95_vs_Mprime_both_layers.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def fig_bins(bins):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharey=False)
    stats = [("exceed_p95_n30_pct", "GEDI p95 (n = 30) above M'"),
             ("exceed_mean_pct", "GEDI cell mean above M'")]
    for ax, (col, title) in zip(axes, stats):
        labels = bins[bins.layer == "New_M_2019"].fpi_bin.tolist()
        x = np.arange(len(labels))
        wbar = 0.38
        for k, tag in enumerate(LAYERS):
            v = bins[bins.layer == tag][col].values
            ax.bar(x + (k - 0.5) * (wbar + 0.02), v, wbar, color=COLOUR[tag],
                   label=SHORT[tag])
        ax.set_xticks(x)
        ax.set_xticklabels([l.replace("(", "").replace("]", "").replace(", ", "-")
                            for l in labels], fontsize=8.5)
        style(ax)
        ax.grid(False, axis="x")
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("mean FPI 1985-2014", fontsize=9, color=INK2)
        ax.set_ylabel("% of cells", fontsize=9, color=INK2)
    axes[0].legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_exceedance_by_fpi_bin.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def fig_map(data, tag="New_M_2019"):
    """One panel per region, each at its own extent and aspect."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    n30 = "agbd_p95_n%d" % N_FIXED
    c = data[tag]
    fig, axes = plt.subplots(2, 3, figsize=(12, 9.4),
                             gridspec_kw={"wspace": 0.35, "hspace": 0.3})
    for ax, (reg, (x0, y0, x1, y1)) in zip(axes.flat, C.REGIONS.items()):
        g = c[c.region == reg]
        r = np.log2(g[n30] / g.m_prime).clip(-2, 2)
        size = 40.0 / max(x1 - x0, y1 - y0) ** 2
        sc = ax.scatter(g.cell_lon, g.cell_lat, c=r, s=size, marker="s",
                        cmap="RdBu_r", norm=TwoSlopeNorm(0, -2, 2),
                        linewidths=0)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / np.cos(np.deg2rad(0.5 * (y0 + y1))))
        style(ax)
        ax.grid(False)
        ax.set_title("%s\np95 > M' in %.0f%% of %s cells"
                     % (reg, 100 * (g[n30] > g.m_prime).mean(),
                        "{:,}".format(len(g))), fontsize=9, color=INK,
                     loc="left")
        ax.tick_params(labelsize=7.5)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    cb = fig.colorbar(sc, ax=axes, shrink=0.6, pad=0.02,
                      ticks=[-2, -1, 0, 1, 2])
    cb.ax.set_yticklabels(["M' 4x GEDI", "2x", "equal", "2x", "GEDI 4x M'"])
    cb.ax.tick_params(labelsize=8)
    fig.savefig(FIG / "fig3_map_p95_over_Mprime.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def fig_regions(reg):
    import matplotlib.pyplot as plt
    order = (reg[reg.layer == "New_M_2019"]
             .sort_values("exceed_p95_n30_pct").region.tolist())
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharey=True)
    stats = [("exceed_p95_n30_pct", "GEDI p95 (n = 30) above M'"),
             ("exceed_mean_pct", "GEDI cell mean above M'")]
    y = np.arange(len(order))
    h_ = 0.38
    for ax, (col, title) in zip(axes, stats):
        for k, tag in enumerate(LAYERS):
            v = reg[reg.layer == tag].set_index("region").loc[order, col]
            ax.barh(y + (k - 0.5) * (h_ + 0.02), v.values, h_,
                    color=COLOUR[tag], label=SHORT[tag])
        ax.set_yticks(y)
        ax.set_yticklabels(order, fontsize=8.5)
        style(ax)
        ax.grid(False, axis="y")
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("% of cells", fontsize=9, color=INK2)
    axes[0].legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "fig5_exceedance_by_region.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def fig_elasticity(data):
    import matplotlib.pyplot as plt
    n30 = "agbd_p95_n%d" % N_FIXED
    c0 = data["New_M_2019"]
    f0 = c0[c0.ebf_frac >= 0.9]
    edges = np.arange(6, 17.5, 1.0)
    mid = 0.5 * (edges[:-1] + edges[1:])
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    def binned(f, col, min_cells=30):
        b = pd.cut(f.fpi_mean, edges)
        g = f.groupby(b, observed=False)[col]
        v = g.median().values
        v[g.size().values < min_cells] = np.nan
        return v

    series = [("M' New_M_2019", binned(f0, "m_prime"), COLOUR["New_M_2019"], "-"),
              ("M' baseline_M", binned(data["baseline_M_1985-2014"].pipe(
                  lambda d: d[d.ebf_frac >= 0.9]), "m_prime"),
               COLOUR["baseline_M_1985-2014"], "-"),
              ("GEDI p95 (n = 30)", binned(f0, n30), INK, "-"),
              ("GEDI mean", binned(f0, "agbd_mean"), INK2, "--")]
    ref = np.argmin(np.abs(mid - 10.5))
    for name, v, col, ls in series:
        ax.plot(mid, 100 * v / v[ref], color=col, lw=2, ls=ls, marker="o",
                ms=4, label=name)
    e = eq1(mid)
    ax.plot(mid, 100 * e / e[ref], color="#1baf7a", lw=2, ls=":",
            label="Eq. (1) shape")
    ax.set_yscale("log")
    style(ax)
    ax.set_xlabel("mean FPI 1985-2014", fontsize=9, color=INK2)
    ax.set_ylabel("index, FPI 10-11 = 100 (log scale)", fontsize=9,
                  color=INK2)
    ax.set_title("How steeply biomass rises with FPI (evergreen broadleaf "
                 "cells; bins < 30 cells hidden)", fontsize=10, color=INK,
                 loc="left")
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_fpi_elasticity_index.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def main():
    ANA.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    fp = pd.read_parquet(OUT / "gedi_l4a_footprints.parquet")
    print("%d footprints" % len(fp))
    extras = cell_extras(fp)

    fp_summary = pd.DataFrame({
        "footprints": [len(fp)], "cells": [fp.cell_id.nunique()],
        "granules_with_footprints": [fp.granule.nunique()],
        "first": [str(fp.acq_time.min())], "last": [str(fp.acq_time.max())],
        "agbd_median": [fp.agbd.median()], "agbd_p95": [fp.agbd.quantile(.95)],
        "rel_se_median": [float(np.median(fp.agbd_se / np.maximum(fp.agbd, 1)))],
        "pct_evergreen_broadleaf": [100 * (fp.pft_class == 2).mean()],
    })
    fp_summary.to_csv(ANA / "footprint_summary.csv", index=False)
    fp.acq_time.dt.year.value_counts().sort_index().rename_axis("year") \
        .rename("footprints").to_csv(ANA / "footprints_by_year.csv")
    fp.groupby("pft_class").agbd.agg(
        footprints="size", agbd_median="median",
        agbd_p95=lambda s: s.quantile(.95)).to_csv(ANA / "footprints_by_pft.csv")
    fp.groupby("region").agg(
        footprints=("agbd", "size"), cells=("cell_id", "nunique"),
        granules=("granule", "nunique"), agbd_median=("agbd", "median"),
        pct_evergreen_broadleaf=("pft_class", lambda s: 100 * (s == 2).mean())
    ).to_csv(ANA / "footprints_by_region.csv")

    rows, bins, forest, elast, regions, data = [], [], [], [], [], {}
    for tag in LAYERS:
        for subset in ("all", "unburnt"):
            rows.append(overall_row(load(tag, subset, extras), tag, subset))
        c = load(tag, "unburnt", extras)
        data[tag] = c
        c["fpi_bin"] = pd.cut(c.fpi_mean, FPI_BINS)
        c["forest_class"] = pd.cut(c.ebf_frac, [-0.01, 0.5, 0.9, 1.0],
                                   labels=["<50% evergreen broadleaf",
                                           "50-90%", ">=90%"])
        bins.append(grouped(c, tag, "fpi_bin", "fpi_bin"))
        forest.append(grouped(c, tag, "forest_class", "forest_class"))
        elast.append(elasticity(c, tag))
        regions.append(by_region(c, tag))

    regions = pd.concat(regions, ignore_index=True)
    burnt = []
    for tag in LAYERS:
        a = load(tag, "all", extras).groupby("region").size().rename("cells_all")
        burnt.append(a.reset_index().assign(layer=tag))
    regions = regions.merge(pd.concat(burnt), on=["layer", "region"], how="left")
    regions.to_csv(ANA / "by_region.csv", index=False)
    overall = pd.DataFrame(rows)
    bins = pd.concat(bins, ignore_index=True)
    forest = pd.concat(forest, ignore_index=True)
    elast = pd.DataFrame(elast)
    overall.to_csv(ANA / "overall_by_layer.csv", index=False)
    bins.to_csv(ANA / "by_fpi_bin.csv", index=False)
    forest.to_csv(ANA / "by_forest_class.csv", index=False)
    elast.to_csv(ANA / "fpi_elasticity.csv", index=False)

    pair = data["New_M_2019"][["cell_id", "m_prime"]].merge(
        data["baseline_M_1985-2014"][["cell_id", "m_prime"]], on="cell_id",
        suffixes=("_new", "_base"))
    r = (pair.m_prime_base / pair.m_prime_new).replace([np.inf, -np.inf], np.nan)
    ratio = pd.DataFrame({"cells": [len(pair)],
                          "baseline_over_New_M_median": [r.median()],
                          "baseline_over_New_M_p10": [r.quantile(.1)],
                          "baseline_over_New_M_p90": [r.quantile(.9)]})
    ratio.to_csv(ANA / "layer_ratio_in_region.csv", index=False)
    pair = pair.assign(ratio=r).merge(
        data["New_M_2019"][["cell_id", "region"]], on="cell_id")
    pair.groupby("region").ratio.agg(
        baseline_over_New_M_median="median",
        baseline_over_New_M_p10=lambda s: s.quantile(.1),
        baseline_over_New_M_p90=lambda s: s.quantile(.9)
    ).to_csv(ANA / "layer_ratio_by_region.csv")

    fig_scatter(data)
    fig_bins(bins)
    fig_map(data)
    fig_elasticity(data)
    fig_regions(regions)

    pd.set_option("display.width", 200)
    print(overall.round(2).T)
    print(bins.round(1))
    print(forest.round(1))
    print(elast.round(3).T)
    print(ratio)
    print(regions.round(2).to_string())
    print("wrote %s and %s" % (ANA, FIG))


if __name__ == "__main__":
    main()
