"""
Step 01 - the record table, built the way Roxburgh et al. (2019) built theirs.

One row per National Biomass Library OBSERVATION, carrying the field biomass and
every M layer sampled at that point, plus the two strata the paper uses
throughout: the Forest/Woodland class from NVIS, and the state.

    obs_key | site | X, Y | state | Forest or Woodland | observed AGB
            | each M layer | each lambda

Why one row per observation
---------------------------
Roxburgh reports n = 5,739 *records*, not sites, and his Table 1 counts them by
state and vegetation class. Sites recur in that count. The space-time validation
next door collapses repeat visits to one row per site taking the MAXIMUM, which
is right for a question about a site's potential but wrong for reproducing his
statistics: a maximum taken over an unequal number of visits raises the observed
values and so manufactures apparent under-prediction in every M layer.
`--unit site` reproduces that behaviour for comparison; the default is his.

The filters, and which are his
------------------------------
  biomass recorded and positive        data quality
  live basal area recorded             a stand, not a bare plot
  dead basal area < 20% of total       his "no recent natural disturbance"
  production estates removed           his tenure filter - Forestry Corporation
                                       NSW and Forestry Tasmania are managed
                                       production forest
  planted projects removed             his "remnant, not planted"
  biomass <= 1500 t DM/ha              data error
  measured >= --min-year               ours, not his: he used the library as at
                                       December 2017 with no lower bound. The
                                       default of 0 reproduces him; 1985 aligns
                                       the sample with the climate baseline the
                                       future layers rest on
  sampled area >= --min-area           ours, not his. Measured on this library,
                                       median biomass falls from 276 t DM/ha on
                                       plots under 0.05 ha to 11 over 0.5 ha - a
                                       gradient produced by plot size alone.
                                       --min-area 0 reproduces him
  AGB >= --min-agb-per-ba per m2 BA    ours, not his. Drops records whose
                                       biomass contradicts their own basal area
                                       (TERN and CSIRO, median 0.08 and 0.21
                                       against a library median of 7.8)

What he had and we do not: the satellite forest-cover continuity check over
1972-2016, and the custodian-by-custodian disturbance metadata (his
Supplementary Appendix A). Those two removed most of the 14,453 records he
started from, leaving 5,739. We cannot reproduce them, so our sample retains
disturbed stands his did not - the first candidate explanation for any residual
difference in the fit statistics.

The layers sampled
------------------
  Original_M_2004      the layer FullCAM shipped before 2019 (Richards & Brack)
  New_M_2019           Roxburgh's revised M', the paper's own output
  Eq1_M_hist           Eq. (1) on the random forest's 1985-2014 FPI
  maxAbgMF_<ssp>_<win> the eight future M', every component from the RF

The first two let this folder REPRODUCE two rows of Roxburgh's Table 4 on our
sample, which is the check that the protocol has been transplanted correctly
before it is applied to anything new.

The Forest/Woodland split
-------------------------
Separate reporting for Forest (canopy > 50%) and Woodland (20-50%), classified
from the NVIS Major Vegetation Subgroups listed in his Table 2, reproduced
verbatim in FOREST_MVS and WOODLAND_MVS below, including the eastern-Australia
restriction he placed on MVS 20, 27 and 45.

What this table can and cannot support
--------------------------------------
Comparing a FUTURE M' against a PRESENT-DAY observation is not a validation of
the future. It asks a narrower and answerable question: does the projected layer
stay inside the envelope the observed maximum biomass defines, and where it
leaves that envelope, in which direction and by how much. A growing divergence
is the projected change, not an error. The present-day layers, which CAN be
validated, sit beside the future ones in every table for exactly that reason.

Reads   ../NBL_download/biolib_sitelist.csv, biolib_treelist.csv
        Step_02_published_lambda/output/original_M_2004.tif
        Data/Processed/maxAbgM_v2/New_M_2019_NLUM.tif
        Calculation_future_M_CSIRO/output/Eq1_M_hist_1985-2014.tif
        FPI_Accuracy_check/output_Mprime_rf/eq1_of_mean/maxAbgMF_*.tif
        Data/Processed/NVIS/nvis_mvs_pre1750_mode_NLUM.tif
        Data/NLUM_Mask/NLUM_2010-11_mask.tif
Writes  outputs/records<tag>.csv
        outputs/filter_trail<tag>.csv
        outputs/records_summary<tag>.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_01_build_records.py
    ... --min-year 1985 --min-area 0.05 --min-agb-per-ba 1.0 --unit site --tag _repo
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" \
    if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NBL_DIR = HERE.parent / "NBL_download"
OUT_DIR = HERE / "outputs"

SITES = NBL_DIR / "biolib_sitelist.csv"
TREES = NBL_DIR / "biolib_treelist.csv"
NVIS = ROOT / "Data" / "Processed" / "NVIS" / "nvis_mvs_pre1750_mode_NLUM.tif"
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
WINDOWS = ["2035-2064", "2070-2099"]
MPRIME_DIR = ROOT / "FPI_Accuracy_check" / "output_Mprime_rf" / "eq1_of_mean"

LAYERS = {
    "M_original_2004": ROOT / "Step_02_published_lambda" / "output"
                       / "original_M_2004.tif",
    "M_revised_Roxburgh": ROOT / "Data" / "Processed" / "maxAbgM_v2"
                          / "New_M_2019_NLUM.tif",
    "M_eq1_rf_hist": ROOT / "Calculation_future_M_CSIRO" / "output"
                     / "Eq1_M_hist_1985-2014.tif",
}
for _s in SSPS:
    for _w in WINDOWS:
        LAYERS["M_future_%s_%s" % (_s, _w)] = (
            MPRIME_DIR / ("maxAbgMF_from_mean_fpi_%s_%s.tif" % (_s, _w)))

# Roxburgh et al. (2019) Table 2, verbatim.
FOREST_MVS = [1, 2, 3, 4, 5, 6, 54, 60, 62]
WOODLAND_MVS = [7, 8, 9, 10, 12, 13, 14, 18, 20, 27, 45, 47, 48]
EAST_ONLY_MVS = [20, 27, 45]          # his own data limitation
EAST_LIMIT = 132.0

PRODUCTION = ["Forestry Corporation Commercial Estate (NSW)", "Forestry Tasmania"]
PLANTED_PROJECTS = ["Environmental Plantings"]
MAX_AGB = 1500.0


def state_of(lon, lat):
    """Crude boxes, adequate for a state-level split and labelled as such.

    The same function `Validation_M/circularity_check.py` uses, so the two
    folders cut the sample the same way. It is not a cadastral boundary and no
    conclusion here turns on a site near a border falling one side or the other.
    """
    if lat < -39.5:
        return "TAS"
    if lon < 129:
        return "WA"
    if lon < 141:
        return "NT" if lat > -26 else "SA"
    if lat > -29:
        return "QLD"
    return "NSW" if lat > -35.8 else "VIC"


def sample(path, rows, cols):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if s.nodata is not None and not np.isnan(s.nodata):
            a = np.where(a == s.nodata, np.nan, a)
    return a[rows, cols]


def veg_class(mvs, lon):
    """Forest / Woodland / Excluded, per Roxburgh's Table 2."""
    out = np.full(len(mvs), "Excluded", dtype=object)
    m = np.asarray(mvs)
    out[np.isin(m, FOREST_MVS)] = "Forest"
    out[np.isin(m, WOODLAND_MVS)] = "Woodland"
    out[np.isin(m, EAST_ONLY_MVS) & (np.asarray(lon) < EAST_LIMIT)] = "Excluded"
    return out


def load_records(args):
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
    keep &= agb <= MAX_AGB
    trail.append(("biomass at most %d t DM/ha" % MAX_AGB, int(keep.sum())))

    if args.min_year > 0:
        keep &= yr >= args.min_year
        trail.append(("measured %d or later" % args.min_year, int(keep.sum())))
    if args.max_year > 0:
        keep &= yr <= args.max_year
        trail.append(("measured %d or earlier" % args.max_year, int(keep.sum())))
    if args.min_area > 0:
        keep &= area.notna() & (area >= args.min_area)
        trail.append(("sampled area at least %.2f ha" % args.min_area,
                      int(keep.sum())))
    with np.errstate(invalid="ignore", divide="ignore"):
        per_ba = agb / ba
    if args.min_agb_per_ba > 0:
        keep &= per_ba >= args.min_agb_per_ba
        trail.append(("AGB at least %.1f t per m2 of basal area"
                      % args.min_agb_per_ba, int(keep.sum())))

    d = d[keep].copy()
    d["agb"] = agb[keep]
    d["year"] = yr[keep]
    d["area_ha"] = area[keep]
    d["live_ba"] = ba[keep]
    d["agb_per_ba"] = per_ba[keep]
    return d, trail


def add_maturity(d):
    """Largest stem of this survey, joined on obs_key - the survey event.

    Reported as a stratum, never used as a filter here: Roxburgh's criterion is
    minimal disturbance, not stem size, and filtering on stem size selects the
    upper tail of the biomass distribution.
    """
    if not TREES.exists():
        d["maturity"] = "unverified"
        return d
    t = pd.read_csv(TREES, low_memory=False, usecols=["obs_key", "diameter"])
    dia = pd.to_numeric(t["diameter"], errors="coerce")
    t = t.assign(diameter=dia).dropna(subset=["diameter"])
    g = t.groupby("obs_key")["diameter"].agg(
        max_dbh="max", n_stems="size",
        n_over50=lambda v: int((v >= 50).sum()))
    d = d.merge(g, on="obs_key", how="left")

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


def attach_grid(d):
    with rasterio.open(NLUM_MASK) as s:
        mask = s.read(1) == 1
        t, (h, w) = s.transform, s.shape
    col = np.floor((d["longitude"].values - t.c) / t.a).astype(int)
    row = np.floor((d["latitude"].values - t.f) / t.e).astype(int)
    ok = (row >= 0) & (row < h) & (col >= 0) & (col < w)
    on_land = np.zeros(len(d), bool)
    on_land[ok] = mask[row[ok], col[ok]]
    d = d.assign(row=row, col=col, on_land=on_land)
    return d[d["on_land"]].copy().reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--unit", choices=["record", "site"], default="record",
                    help="one row per observation (Roxburgh) or per site "
                         "taking the maximum (the space-time validation)")
    ap.add_argument("--min-year", type=int, default=0,
                    help="0 reproduces Roxburgh, who set no lower bound")
    ap.add_argument("--max-year", type=int, default=0,
                    help="2017 reproduces the library as he took it")
    ap.add_argument("--min-area", type=float, default=0.0,
                    help="0 reproduces Roxburgh; 0.05 is this repo's filter")
    ap.add_argument("--min-agb-per-ba", type=float, default=0.0,
                    help="0 reproduces Roxburgh; 1.0 is this repo's filter")
    ap.add_argument("--tag", default="",
                    help="suffix for the output files, e.g. _repo")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    d, trail = load_records(args)
    d = add_maturity(d)
    d = attach_grid(d)
    trail.append(("inside the NLUM mask", len(d)))

    if args.unit == "site":
        d = d.sort_values("agb", ascending=False)
        agg = {c: "first" for c in
               ["longitude", "latitude", "row", "col", "source", "project",
                "maturity", "max_dbh", "n_stems", "area_ha", "live_ba",
                "agb_per_ba", "obs_key"] if c in d.columns}
        agg["agb"] = "max"
        agg["year"] = "max"
        d = d.groupby("site").agg(agg).reset_index()
        trail.append(("one row per site (maximum measurement)", len(d)))

    rows, cols = d["row"].to_numpy(), d["col"].to_numpy()
    mvs = sample(NVIS, rows, cols)
    d["mvs"] = mvs.astype("float32")
    d["veg_class"] = veg_class(np.nan_to_num(mvs, nan=-1).astype(int),
                               d["longitude"].to_numpy())
    d["state"] = [state_of(a, b) for a, b in zip(d["longitude"], d["latitude"])]

    for name, path in LAYERS.items():
        if not path.exists():
            print("  MISSING %s - skipped" % path.name)
            continue
        d[name] = sample(path, rows, cols)

    layer_cols = [c for c in LAYERS if c in d.columns]
    # Roxburgh Eq. (2): lambda_i = M_i / O_i, one per layer per record.
    for c in layer_cols:
        d["lambda_" + c] = np.where(d["agb"] > 0, d[c] / d["agb"], np.nan)

    before = len(d)
    d = d.dropna(subset=["agb"] + layer_cols).reset_index(drop=True)
    if len(d) < before:
        trail.append(("every M layer present", len(d)))

    keep_cols = [c for c in
                 ["obs_key", "site", "source", "project", "longitude",
                  "latitude", "row", "col", "year", "area_ha", "agb",
                  "live_ba", "agb_per_ba", "maturity", "max_dbh", "n_stems",
                  "mvs", "veg_class", "state"] if c in d.columns]
    d = d[keep_cols + layer_cols + ["lambda_" + c for c in layer_cols]]

    dst = OUT_DIR / ("records%s.csv" % args.tag)
    d.to_csv(dst, index=False)
    pd.DataFrame(trail, columns=["step", "records"]).to_csv(
        OUT_DIR / ("filter_trail%s.csv" % args.tag), index=False)

    summary = d.groupby("veg_class").agg(
        records=("agb", "size"),
        obs_mean=("agb", "mean"), obs_median=("agb", "median"),
        M_original=("M_original_2004", "mean"),
        M_revised=("M_revised_Roxburgh", "mean"),
        M_future_ssp585_late=("M_future_ssp585_2070-2099", "mean"),
    ).reset_index()
    summary.to_csv(OUT_DIR / ("records_summary%s.csv" % args.tag), index=False)

    for step, n in trail:
        print("  %-46s %6d" % (step, n))
    print("\n%s\n%d records, %d columns" % (dst, len(d), d.shape[1]))
    print(summary.to_string(index=False, float_format=lambda v: "%.1f" % v))
    print("\nRoxburgh's own sample, for comparison: 5,739 records - "
          "Forest 2,543, Woodland 3,195")
    print("\nby state:")
    print(d.groupby(["state", "veg_class"]).size().unstack(fill_value=0)
          .to_string())


if __name__ == "__main__":
    main()
