"""
M' = lambda * M, Eq. (3), with DCCEEW's PUBLISHED lambda.

Roxburgh et al. (2019), Forest Ecology and Management 432, 264-275:

        M' = lambda * M                                                  (Eq. 3)

Multiplies every MAGB layer written by Step_06 by

    Step_02_published_lambda/output/lambda_published.tif

writing, per layer,

    output_Mprime_original2004/maxAbgMF_<ssp>_<year>.tif                 240
    output_Mprime_original2004/maxAbgMF_<ssp>_<period>_mean.tif            8
    output_Mprime_original2004/maxAbgMF_from_mean_fpi_<ssp>_<period>.tif   8
    output_Mprime_original2004/Mprime_summary.csv

Units: t DM ha-1. `maxAbgMF` is FullCAM's own name for this variable, as read by
`RUN_FullCAM2024.py`.

Lambda is time-invariant, so `lambda * mean_y(M_y)` and `mean_y(lambda * M_y)`
are the same number; the window layers therefore stay consistent with the annual
ones however they are recombined downstream.

The footing - READ THIS
-----------------------
Eq. (3) is only valid when lambda is paired with the exact M it was divided by.
`lambda_published.tif` is `New_M_2019 / Original_M_2004`, so its denominator is
FullCAM's `Original_M_2004` layer.

Step_06's M is Eq. (1) M, which is NOT that layer: Eq. (1) overstates
`Original_M_2004` by a median factor of 1.46 (31.44 vs 18.65 t DM ha-1). So M is
rescaled onto the Original_M_2004 footing before lambda is applied:

    M' = lambda_published * Original_M_2004 * Eq1(FPI_future) / Eq1(FPI_hist)

Every factor then sits on one footing, Eq. (1) cancels out of the ratio, and
only the *relative* change in productivity comes from the projection while the
absolute level comes from the layer FullCAM ships. Output goes to
`output_Mprime_original2004/`.

The unrescaled route - lambda applied directly to Eq. (1) M, which mixed the two
footings and inflated M' by roughly 1.46 wherever lambda != 1 - was retired in
September 2026. `--footing` survives for backwards compatibility with callers
that pass it explicitly, but `original2004` is now its only value.

The `original2004` route needs the historical Eq. (1) baseline, which it builds
once from the same observed FPI the model was trained on
(`Random_forest_CSIRO/required_data/fpi/fpi_<year>.tif`, 1985-2014) and caches as
`output/Eq1_M_hist_1985-2014.tif` alongside the scale factor actually applied.

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_08_apply_published_lambda.py --jobs 10
    ... --footing original2004

`--hist-m PATH` swaps the ratio denominator for a ready-made historical Eq. (1)
M raster, and `--out-dir` says where to write. `FPI_Accuracy_check/Step_04` uses
both to rebuild M' with a denominator modelled by the same random forest that
produced the numerator, so the forest's bias cancels out of the ratio instead of
being read as climate change. `--layers` keeps the averaging order of numerator
and denominator matched. Omit all three and the behaviour is unchanged.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np
import rasterio
from joblib import Parallel, delayed
from tqdm.auto import tqdm

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(r"N:\Current-Users\ZOHREH-KALAHROUDI\000_Zohreh_paper_1_refactor")
STEP_DIR = Path(__file__).resolve().parent

M_DIR = STEP_DIR / "output"                      # Step_06 output
LAMBDA_PATH = PROJECT_ROOT / "Step_02_published_lambda" / "output" / "lambda_published.tif"
ORIGINAL_M_PATH = PROJECT_ROOT / "Step_02_published_lambda" / "output" / "original_M_2004.tif"
HIST_FPI_DIR = PROJECT_ROOT / "Random_forest_CSIRO" / "required_data" / "fpi"
NLUM_MASK = PROJECT_ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"

HIST_YEARS = list(range(1985, 2015))             # the model's training years

VAR_OUT = "maxAbgMF"                             # FullCAM's name for M'

# Eq. (1) coefficients, as in Step_06
M_A, M_B = 6.011, 5.291
M_ROOT = (M_B / M_A) ** 2                        # 0.774787

LAMBDA_REPORT_ABOVE = 3.0                        # Roxburgh Fig. 7b ramp tops out here
MIN_HIST_M = 1.0                                 # t DM ha-1, floor on the ratio denominator

_ref = {}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def reference():
    if not _ref:
        with rasterio.open(NLUM_MASK) as t:
            _ref["valid"] = t.read(1) == 1
            _ref["shape"] = (t.height, t.width)
            _ref["crs"] = t.crs
            _ref["transform"] = t.transform
    return _ref


def read_on_grid(path):
    """Read a single-band raster, checked against the NLUM grid."""
    ref = reference()
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        if (s.height, s.width) != ref["shape"]:
            raise ValueError(f"{path.name}: shape {(s.height, s.width)} != NLUM {ref['shape']}")
        if s.transform != ref["transform"]:
            raise ValueError(f"{path.name}: transform differs from the NLUM template")
        if s.nodata is not None and not np.isnan(s.nodata):
            a[a == s.nodata] = np.nan
    return a


def write_gtiff(arr2d, dst_path, description, tags):
    ref = reference()
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_suffix(".tif.tmp")
    with rasterio.open(
        tmp, "w",
        driver="GTiff",
        height=ref["shape"][0], width=ref["shape"][1], count=1,
        dtype="float32", nodata=np.nan,
        crs=ref["crs"], transform=ref["transform"],
        compress="LZW", tiled=True, blockxsize=256, blockysize=256,
        BIGTIFF="IF_SAFER",
    ) as dst:
        dst.write(arr2d.astype("float32"), 1)
        dst.set_band_description(1, description)
        dst.update_tags(**tags)
    tmp.replace(dst_path)
    return dst_path


def eq1(fpi):
    """Eq. (1) with the parabola cut at its root, exactly as Step_06 applies it."""
    x = np.clip(fpi, M_ROOT, None)
    with np.errstate(invalid="ignore"):
        return (M_A * np.sqrt(x) - M_B) ** 2


def historical_eq1_baseline():
    """Eq. (1) M from the mean observed FPI over the 30 training years.

    The denominator of the delta-change ratio. A climatology, not a single year,
    matching how REVISED_ORIGINAL_M_2004/Step_06 used the 1970-2002 mean.
    Cached, since it never changes.
    """
    ref = reference()
    cached = M_DIR / "Eq1_M_hist_1985-2014.tif"
    if cached.exists():
        return read_on_grid(cached)

    acc = np.zeros(ref["shape"], dtype="float64")
    for y in tqdm(HIST_YEARS, desc="historical FPI", unit="yr"):
        src = HIST_FPI_DIR / f"fpi_{y}.tif"
        if not src.exists():
            raise FileNotFoundError(src)
        acc += read_on_grid(src)
    fpi_hist = acc / len(HIST_YEARS)

    m_hist = np.where(ref["valid"], eq1(fpi_hist), np.nan)
    write_gtiff(
        m_hist, cached, "Eq1_M_hist_1985-2014",
        dict(units="t DM ha-1",
             long_name="Eq. (1) M from mean observed FPI 1985-2014",
             equation="M = (6.011 * sqrt(FPI) - 5.291) ** 2",
             source=f"mean of {HIST_FPI_DIR}\\fpi_1985..2014.tif"),
    )
    print(f"  built {cached.name}: mean {np.nanmean(m_hist[ref['valid']]):.2f} t DM ha-1")
    return m_hist


def build_scale(footing, hist_m_path=None, out_dir=None):
    """The per-cell factor applied to Step_06's M before lambda.

    eq1           -> 1 everywhere (M is used as written)
    original2004  -> Original_M_2004 / Eq1(FPI 1985-2014), which converts an
                     Eq. (1) M into the same *relative* change expressed on the
                     Original_M_2004 footing.

    `hist_m_path` replaces that denominator with a ready-made historical Eq. (1)
    M raster. `FPI_Accuracy_check/Step_03` supplies one built from the random
    forest's OWN historical FPI, so that both sides of the ratio come from the
    same model and its bias cancels instead of being read as climate change.
    The default (None) keeps the previous behaviour exactly: the denominator is
    built from the observed DCCEEW FPI and cached in `output/`.
    """
    ref = reference()
    if hist_m_path is not None:
        m_hist = read_on_grid(Path(hist_m_path))
        print(f"  historical denominator: {Path(hist_m_path).name} (supplied)")
    else:
        m_hist = historical_eq1_baseline()
    orig = read_on_grid(ORIGINAL_M_PATH)

    # Clamp the denominator rather than nulling it: a cell whose historical
    # Eq. (1) M is a fraction of a tonne would otherwise divide the ratio into
    # the hundreds. Flooring at MIN_HIST_M bounds the scale at
    # Original_M_2004 / MIN_HIST_M instead of producing a hole.
    n_floored = int((m_hist[ref["valid"]] < MIN_HIST_M).sum())
    denom = np.maximum(m_hist, MIN_HIST_M)
    with np.errstate(invalid="ignore", divide="ignore"):
        scale = orig / denom

    # A supplied denominator writes its scale next to its own output, so the
    # cached observed-FPI scale in output/ is never overwritten by a variant.
    dst = (M_DIR if hist_m_path is None else Path(out_dir or M_DIR)) \
        / "scale_Eq1_to_original2004.tif"
    write_gtiff(
        np.where(ref["valid"], scale, np.nan), dst, "scale_Eq1_to_original2004",
        dict(units="1",
             long_name="Original_M_2004 / Eq1(FPI 1985-2014)",
             denominator=("observed DCCEEW FPI" if hist_m_path is None
                          else str(hist_m_path)),
             note=f"denominator floored at {MIN_HIST_M} t DM ha-1 in "
                  f"{n_floored:,} cell(s)"),
    )
    v = scale[ref["valid"]]
    print(f"  scale Eq1 -> Original_M_2004: median {np.nanmedian(v):.4f}, "
          f"mean {np.nanmean(v):.4f}, {n_floored:,} cell(s) below the "
          f"{MIN_HIST_M} t DM ha-1 denominator floor")
    return scale


def classify(name):
    """(kind, ssp, period/year) from a Step_06 file name."""
    stem = name[:-4]
    if stem.startswith("M_from_mean_fpi_"):
        ssp, period = stem[len("M_from_mean_fpi_"):].split("_")
        return "window_Eq1_of_mean_FPI", ssp, period, ""
    parts = stem.split("_")                       # M, ssp, tail...
    ssp = parts[1]
    if stem.endswith("_mean"):
        return "window_mean_of_annual_M", ssp, parts[2], ""
    year = parts[2]
    period = "2035-2064" if int(year) < 2070 else "2070-2099"
    return "annual", ssp, period, year


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description="M' = lambda * M with the published lambda")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--footing", choices=["original2004"],
                    default="original2004",
                    help="kept for backwards compatibility; the Eq.(1) footing "
                         "was retired, so original2004 is the only choice")
    ap.add_argument("--hist-m", default=None,
                    help="historical Eq.(1) M raster to use as the ratio "
                         "denominator, instead of building one from the observed "
                         "DCCEEW FPI. Only meaningful with --footing original2004")
    ap.add_argument("--out-dir", default=None,
                    help="where to write; default output_Mprime/ or "
                         "output_Mprime_original2004/ per --footing")
    ap.add_argument("--layers", choices=["all", "mean_of_annual", "eq1_of_mean"],
                    default="all",
                    help="which Step_06 layers to convert. The averaging order "
                         "of the numerator and of --hist-m must match: "
                         "mean_of_annual selects the annual and <window>_mean "
                         "layers, eq1_of_mean selects the from_mean_fpi ones")
    args = ap.parse_args()

    ref = reference()
    valid = ref["valid"]
    out_dir = (Path(args.out_dir) if args.out_dir
               else STEP_DIR / "output_Mprime_original2004")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = out_dir / "Mprime_summary.csv"

    lam = read_on_grid(LAMBDA_PATH)
    n_lam_gap = int(np.isnan(lam[valid]).sum())
    if n_lam_gap:
        raise ValueError(f"{LAMBDA_PATH.name}: {n_lam_gap:,} NaN inside the NLUM mask")
    lv = lam[valid]

    layers = sorted(p for p in M_DIR.glob("M_*.tif")
                    if p.name not in ("M_summary.csv",)
                    and not p.name.startswith("M_hist")
                    and not p.name.startswith("Eq1_M_hist"))
    if args.layers == "mean_of_annual":
        layers = [p for p in layers if not p.name.startswith("M_from_mean_fpi_")]
    elif args.layers == "eq1_of_mean":
        layers = [p for p in layers if p.name.startswith("M_from_mean_fpi_")]
    if not layers:
        raise FileNotFoundError(f"no M_*.tif under {M_DIR} - run Step_06 first")

    print(f"M input   : {M_DIR}  ({len(layers)} layers)")
    print(f"lambda    : {LAMBDA_PATH}")
    print(f"          median {np.median(lv):.4f}, mean {lv.mean():.4f}, "
          f"max {lv.max():.4f}, exactly 1.0 in {(lv == 1).mean():.4f} of cells, "
          f">{LAMBDA_REPORT_ABOVE} in {(lv > LAMBDA_REPORT_ABOVE).mean():.4f}")
    print(f"footing   : {args.footing}")
    print(f"output    : {out_dir}\n")

    scale = build_scale(args.footing, args.hist_m, out_dir)
    factor = lam if scale is None else lam * scale       # one multiply per layer
    common_tags = dict(
        units="t DM ha-1",
        long_name="Future revised maximum above-ground biomass (M')",
        equation="M' = lambda * M",
        reference="Roxburgh et al. 2019, For. Ecol. Manage. 432:264-275, Eq. 3",
        lambda_source=str(LAMBDA_PATH),
        lambda_definition="New_M_2019 / Original_M_2004 (DCCEEW Ratio_OriginalM_to_NewM)",
        footing=args.footing,
    )
    common_tags["m_footing"] = ("Original_M_2004 x Eq1(FPI_future) / "
                                "Eq1(FPI_1985-2014)")
    common_tags["hist_denominator"] = (
        str(args.hist_m) if args.hist_m
        else "Eq1(mean observed DCCEEW FPI 1985-2014)")

    def one(src):
        m = read_on_grid(src)
        mp = np.where(valid, m * factor, np.nan)
        kind, ssp, period, year = classify(src.name)
        dst = out_dir / src.name.replace("M_", f"{VAR_OUT}_", 1)
        write_gtiff(mp, dst, dst.stem, dict(common_tags, source_M=src.name))
        m_v, mp_v = m[valid], mp[valid]
        return dict(layer=dst.name, source_M=src.name, kind=kind, ssp=ssp,
                    period=period, year=year, n_cells=int(mp_v.size),
                    M_mean=float(np.nanmean(m_v)),
                    Mprime_min=float(np.nanmin(mp_v)),
                    Mprime_mean=float(np.nanmean(mp_v)),
                    Mprime_median=float(np.nanmedian(mp_v)),
                    Mprime_max=float(np.nanmax(mp_v)),
                    mean_ratio_Mprime_over_M=float(np.nanmean(mp_v) / np.nanmean(m_v)))

    rows = Parallel(n_jobs=args.jobs, backend="threading")(
        delayed(one)(p) for p in tqdm(layers, desc=VAR_OUT, unit="file")
    )

    cols = ["layer", "source_M", "kind", "ssp", "period", "year", "n_cells",
            "M_mean", "Mprime_min", "Mprime_mean", "Mprime_median",
            "Mprime_max", "mean_ratio_Mprime_over_M"]
    with open(summary_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    print(f"\nwrote {summary_csv}  ({len(rows)} layers)")

    # --- verify ---------------------------------------------------------------
    print("\nverifying:")
    problems = []
    written = sorted(out_dir.glob(f"{VAR_OUT}_*.tif"))
    for p in tqdm(written, desc="verify", unit="file"):
        try:
            with rasterio.open(p) as s:
                if (s.height, s.width) != ref["shape"]:
                    problems.append(f"{p.name}: shape {(s.height, s.width)}")
                    continue
                a = s.read(1)
            if not np.isfinite(a[valid]).all():
                problems.append(f"{p.name}: non-finite inside the NLUM mask")
            if np.isfinite(a[~valid]).any():
                problems.append(f"{p.name}: data outside the NLUM mask")
            if np.nanmin(a[valid]) < 0:
                problems.append(f"{p.name}: negative M'")
        except Exception as exc:                       # noqa: BLE001
            problems.append(f"{p.name}: {exc}")
    print(f"  {len(written) - len(problems)} of {len(written)} valid")
    for p in problems:
        print("   ", p)

    print(f"\n{'scenario':9s} {'window':11s} {'layer':26s} "
          f"{'M mean':>9s} {chr(77)+chr(39)+' mean':>9s} {'ratio':>7s} {chr(77)+chr(39)+' max':>9s}")
    for r in rows:
        if r["kind"] == "annual":
            continue
        print(f"{r['ssp']:9s} {r['period']:11s} {r['kind']:26s} "
              f"{r['M_mean']:9.2f} {r['Mprime_mean']:9.2f} "
              f"{r['mean_ratio_Mprime_over_M']:7.3f} {r['Mprime_max']:9.2f}")

    ann = [r for r in rows if r["kind"] == "annual"]
    if ann:                                   # --layers eq1_of_mean selects none
        means = [r["Mprime_mean"] for r in ann]
        print(f"\n{len(ann)} annual layers: M' mean {np.mean(means):.2f} t DM ha-1 "
              f"(range {min(means):.2f}..{max(means):.2f})")
    else:
        print("\nno annual layers in this run")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
