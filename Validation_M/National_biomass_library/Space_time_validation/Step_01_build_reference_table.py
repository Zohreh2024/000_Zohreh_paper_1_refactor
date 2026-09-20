"""
Step 01 - Dataframe 1, the reference table.

One row per National Biomass Library SITE, restricted to mature vegetation with
good data, carrying X, Y and every predictor that feeds FPI at that location -
the same 174 columns the random forest itself was fitted on (83 soil + 91
climate), evaluated on the 1985-2014 climatology.

    X, Y | 83 soil | 91 climate (1985-2014 mean) | observed AGB | M'_hist | FPI_hist

Filtering, and why each step is there
-------------------------------------
The filters follow `Validation_M/fpi_bin_validation.py`, which established them
against this library; they are repeated here rather than imported so this folder
runs standalone, and every step's survivor count is written to
`outputs/filter_trail.csv`.

  biomass recorded and positive        nothing to compare otherwise
  live basal area recorded             a stand, not a bare plot
  dead basal area < 20% of total       recent fire or dieback excluded
  production estates dropped           Forestry Corporation NSW / Forestry
                                       Tasmania are managed production forest,
                                       not undisturbed remnant stands
  planted projects dropped             `Environmental Plantings` etc. are
                                       planted, not remnant
  measured 1985 or later               the climate baseline is 1985-2014; a
                                       stand measured in 1952 has no matching
                                       climate
  sampled area >= 0.05 ha              a per-hectare figure from a 0.04 ha plot
                                       multiplies one tree by 25. Median biomass
                                       on this library falls from 276 Mg/ha
                                       under 0.05 ha to 11 Mg/ha over 0.5 ha -
                                       a gradient produced by plot size alone
  biomass <= 1500 Mg/ha                the residue above that is small-plot
                                       artefact and data error

Maturity comes from the tree-level table, not from the site table, which carries
no age or disturbance field:

  verified mature    at least one stem >= 50 cm DBH
  likely mature      largest stem 30-50 cm
  young or shrubby   largest stem < 30 cm
  unverified         no stems listed for that site

The headline sample is verified + likely mature. `--maturity` changes it.

Repeat visits are collapsed to one row per site, taking the MAXIMUM biomass: M
is a maximum, so where a site was measured several times the largest measurement
is the best single estimate of it. Averaging would build in a downward bias on
top of the one immaturity already causes.

Reads   ../NBL_download/biolib_sitelist.csv, biolib_treelist.csv
        Random_forest_CSIRO/required_data/Soil_data/*.tif        83 bands
        Random_forest_CSIRO/data/monthly_climate/historical/*    7 vars x 30 yr
        Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif
        FPI_Accuracy_check/output/fpi_rf_1985-2014_mean.tif
Writes  outputs/reference_table.csv        the table itself
        outputs/filter_trail.csv           survivors after each filter
        outputs/reference_table_summary.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_build_reference_table.py
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402
import rioxarray as rxr                                        # noqa: E402

HERE = Path(__file__).resolve().parent
NBL_DIR = HERE.parent / "NBL_download"
ROOT = HERE.parents[2]                       # .../000_Zohreh_paper_1_refactor
RF_DIR = ROOT / "Random_forest_CSIRO"
sys.path.insert(0, str(RF_DIR))

from common import (HIST_YEARS, climate_features_at, feature_names,   # noqa: E402
                    nlum_template, soil_feature_names, soil_files)

OUT_DIR = HERE / "outputs"
SITES = NBL_DIR / "biolib_sitelist.csv"
TREES = NBL_DIR / "biolib_treelist.csv"
NEW_M = ROOT / "Data" / "Processed" / "maxAbgM_v2" / "New_M_2019_NLUM.tif"
FPI_HIST = ROOT / "FPI_Accuracy_check" / "output" / "fpi_rf_1985-2014_mean.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

PRODUCTION = ["Forestry Corporation Commercial Estate (NSW)", "Forestry Tasmania"]
PLANTED_PROJECTS = ["Environmental Plantings"]
MIN_AREA_HA = 0.05
MAX_AGB = 1500.0
MATURITY_SETS = {
    "mature": ["verified mature", "likely mature"],
    "verified": ["verified mature"],
    "all": ["verified mature", "likely mature", "young or shrubby", "unverified"],
}


def load_sites():
    d = pd.read_csv(SITES, low_memory=False)
    trail = [("all site visits", len(d))]

    agb = pd.to_numeric(d["agb_drymass_ha"], errors="coerce")
    ba = pd.to_numeric(d["live_basal_area_ha"], errors="coerce")
    dba = pd.to_numeric(d["dead_basal_area_ha"], errors="coerce")
    area = pd.to_numeric(d["sampledarea_ha"], errors="coerce")
    yr = pd.to_datetime(d["obs_time"], errors="coerce").dt.year

    keep = agb.notna() & (agb > 0)
    trail.append(("biomass recorded and positive", int(keep.sum())))
    keep &= ba.notna() & (ba > 0)
    trail.append(("live basal area recorded", int(keep.sum())))
    keep &= (dba / (ba + dba)).fillna(0) < 0.2
    trail.append(("dead basal area under 20% of total", int(keep.sum())))
    keep &= ~d["source"].isin(PRODUCTION)
    trail.append(("production estates removed", int(keep.sum())))
    keep &= ~d["project"].isin(PLANTED_PROJECTS)
    trail.append(("planted projects removed", int(keep.sum())))
    keep &= yr >= 1985
    trail.append(("measured 1985 or later", int(keep.sum())))
    keep &= area.notna() & (area >= MIN_AREA_HA)
    trail.append(("sampled area at least %.2f ha" % MIN_AREA_HA, int(keep.sum())))
    keep &= agb <= MAX_AGB
    trail.append(("biomass at most %d Mg/ha" % MAX_AGB, int(keep.sum())))

    d = d[keep].copy()
    d["agb"] = agb[keep]
    d["year"] = yr[keep]
    d["area_ha"] = area[keep]
    return d, trail


def add_maturity(d):
    """Largest stem at the site, from the tree-level table."""
    t = pd.read_csv(TREES, low_memory=False, usecols=["site", "diameter"])
    dia = pd.to_numeric(t["diameter"], errors="coerce")
    t = t.assign(diameter=dia).dropna(subset=["diameter"])
    g = t.groupby("site")["diameter"].agg(
        max_dbh="max", n_stems="size",
        n_over30=lambda v: int((v >= 30).sum()),
        n_over50=lambda v: int((v >= 50).sum()))
    d = d.merge(g, on="site", how="left")

    def klass(r):
        if not np.isfinite(r.max_dbh):
            return "unverified"
        if r.n_over50 > 0:
            return "verified mature"
        if r.max_dbh >= 30:
            return "likely mature"
        return "young or shrubby"

    d["maturity"] = d.apply(klass, axis=1)
    return d


def to_sites(d):
    """One row per site, the maximum measurement."""
    d = d.sort_values("agb", ascending=False)
    agg = dict(agb=("agb", "max"), longitude=("longitude", "first"),
               latitude=("latitude", "first"), year=("year", "max"),
               source=("source", "first"), project=("project", "first"),
               area_ha=("area_ha", "max"), maturity=("maturity", "first"),
               max_dbh=("max_dbh", "first"), n_stems=("n_stems", "first"),
               n_visits=("agb", "size"))
    return d.groupby("site").agg(**agg).reset_index()


def attach_grid(d):
    """Cell indices on NLUM, by the cell the point falls in - not bilinear.

    A plot sits inside one 0.01 deg cell and did not experience the average of
    its neighbours, so raster attributes are taken from that cell. The CLIMATE
    features are the exception: they come from the 0.11 deg CSIRO grid through
    the same bilinear interpolation the random forest itself uses, evaluated at
    that cell's centre, so the reference row is exactly what the model would
    have seen for that cell.
    """
    with rasterio.open(NLUM_MASK) as s:
        mask = s.read(1) == 1
        t, (h, w) = s.transform, s.shape

    col = np.floor((d["longitude"].values - t.c) / t.a).astype(int)
    row = np.floor((d["latitude"].values - t.f) / t.e).astype(int)
    ok = (row >= 0) & (row < h) & (col >= 0) & (col < w)
    on_land = np.zeros(len(d), bool)
    on_land[ok] = mask[row[ok], col[ok]]

    d = d.assign(row=row, col=col, on_land=on_land)
    d = d[d["on_land"]].copy()

    tpl = nlum_template()
    d["x"] = tpl.x.values[d["col"].values]
    d["y"] = tpl.y.values[d["row"].values]

    for name, path in [("M_hist", NEW_M), ("fpi_hist", FPI_HIST)]:
        with rasterio.open(path) as s:
            a = s.read(1).astype("float64")
            if s.nodata is not None and not np.isnan(s.nodata):
                a = np.where(a == s.nodata, np.nan, a)
        d[name] = a[d["row"].values, d["col"].values]

    return d.dropna(subset=["M_hist", "fpi_hist"]).reset_index(drop=True)


def attach_soil(d):
    rows, cols = d["row"].values, d["col"].values
    out = {}
    for name, path in zip(soil_feature_names(), soil_files()):
        v = rxr.open_rasterio(path, masked=True).squeeze(drop=True).values
        out[name] = v[rows, cols].astype("float32")
    return pd.DataFrame(out, index=d.index)


def attach_climate(d, years):
    """The 91 climate features, averaged over the baseline years."""
    lat = d["y"].values.astype("float64")
    lon = d["x"].values.astype("float64")
    acc = None
    for i, yr in enumerate(years, 1):
        f = climate_features_at(yr, None, lat, lon, pointwise=True)
        acc = f.astype("float64") if acc is None else acc + f
        print("    %d/%d  %d" % (i, len(years), yr), flush=True)
    acc /= len(years)
    names = feature_names()[-acc.shape[0]:]
    return pd.DataFrame(acc.T.astype("float32"), columns=names, index=d.index)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--maturity", choices=list(MATURITY_SETS), default="mature",
                    help="which maturity classes the reference table keeps")
    ap.add_argument("--keep-all-classes", action="store_true",
                    help="write every class, with a `maturity` column to filter on")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("filtering the library")
    d, trail = load_sites()
    d = add_maturity(d)
    d = to_sites(d)
    trail.append(("one row per site (maximum measurement)", len(d)))

    counts = d["maturity"].value_counts().to_dict()
    print("  maturity: " + ", ".join("%s %d" % (k, v) for k, v in counts.items()))

    if not args.keep_all_classes:
        d = d[d["maturity"].isin(MATURITY_SETS[args.maturity])].copy()
        trail.append(("maturity in %s" % MATURITY_SETS[args.maturity], len(d)))

    d = attach_grid(d)
    trail.append(("inside the NLUM mask with M' and FPI", len(d)))

    for step, n in trail:
        print("  %-46s %6d" % (step, n))
    pd.DataFrame(trail, columns=["step", "sites"]).to_csv(
        OUT_DIR / "filter_trail.csv", index=False)

    print("soil, 83 bands")
    soil = attach_soil(d)
    print("climate, 91 features over %d-%d" % (HIST_YEARS[0], HIST_YEARS[-1]))
    clim = attach_climate(d, HIST_YEARS)

    meta = d[["site", "x", "y", "longitude", "latitude", "row", "col", "agb",
              "M_hist", "fpi_hist", "maturity", "max_dbh", "n_stems", "year",
              "area_ha", "n_visits", "source", "project"]].reset_index(drop=True)
    table = pd.concat([meta, soil.reset_index(drop=True),
                       clim.reset_index(drop=True)], axis=1)

    before = len(table)
    table = table.dropna(subset=feature_names()).reset_index(drop=True)
    if len(table) < before:
        print("  dropped %d site(s) with an incomplete predictor row"
              % (before - len(table)))

    dst = OUT_DIR / "reference_table.csv"
    table.to_csv(dst, index=False)

    summary = table.groupby("maturity").agg(
        n=("agb", "size"), agb_median=("agb", "median"),
        agb_p05=("agb", lambda v: float(np.percentile(v, 5))),
        agb_p95=("agb", lambda v: float(np.percentile(v, 95))),
        M_hist_median=("M_hist", "median"),
        fpi_median=("fpi_hist", "median")).reset_index()
    summary.to_csv(OUT_DIR / "reference_table_summary.csv", index=False)

    print("\n%s\n%d sites, %d columns" % (dst, len(table), table.shape[1]))
    print(summary.to_string(index=False, float_format=lambda v: "%.2f" % v))


if __name__ == "__main__":
    main()
