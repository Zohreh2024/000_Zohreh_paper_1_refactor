"""
Step 00 - put NVIS on the NLUM grid, as a class per cell.

Source: NVIS 4.1 Major Vegetation Subgroups, **pre-1750 extent**, 100 m on GDA94
Albers (`Data/Raw/NVIS/extracted/pre1750_mvs_soe2016/`).

Pre-1750 rather than present extent, deliberately. M is the biomass a site
*could* carry, so the vegetation that belongs there is the relevant attribute,
not what clearing has left behind. A cleared paddock that was wet sclerophyll
forest in 1750 still has the climate and soil of wet sclerophyll forest, and
that is what the analogue match is trying to hold constant.

One layer is written on the NLUM grid:

    nvis_mvs_pre1750_mode_NLUM.tif    the majority MVS class in each 1 km cell

Majority, not nearest neighbour: about 120 NVIS pixels fall inside one NLUM
cell, and nearest neighbour would hand the whole cell to whichever pixel happens
to sit under its centre.

A per-cell purity layer (the share of the cell holding the winning class) would
be a useful caveat to carry, but an exact one needs a separate warp per class -
about an hour for 79 classes - and nothing downstream reads it, so it is left
out rather than approximated badly.

Reads   Data/Raw/NVIS/extracted/pre1750_mvs_soe2016/NVIS4_1_AUST_MVS_PRE1750_ALB_LAN1a.tif
        Data/NLUM_Mask/NLUM_2010-11_mask.tif
Writes  Data/Processed/NVIS/nvis_mvs_pre1750_mode_NLUM.tif
        outputs/nvis_class_counts.csv

Run
---
    conda run --no-capture-output -p "C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto" ^
        python Step_00_prepare_nvis.py
"""

import argparse
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

_proj = Path(os.environ["CONDA_PREFIX"]) / "Library" / "share" / "proj" if "CONDA_PREFIX" in os.environ else None
if _proj and _proj.exists():
    os.environ["PROJ_LIB"] = str(_proj)
    os.environ["PROJ_DATA"] = str(_proj)

import rasterio                                                # noqa: E402
from rasterio.enums import Resampling                          # noqa: E402
from rasterio.warp import reproject                            # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NVIS = (ROOT / "Data" / "Raw" / "NVIS" / "extracted" / "pre1750_mvs_soe2016"
        / "NVIS4_1_AUST_MVS_PRE1750_ALB_LAN1a.tif")
NLUM_MASK = ROOT / "Data" / "NLUM_Mask" / "NLUM_2010-11_mask.tif"
OUT = ROOT / "Data" / "Processed" / "NVIS"
MODE_PATH = OUT / "nvis_mvs_pre1750_mode_NLUM.tif"

UNCLASSIFIED = {0, 99, 255}        # outside coverage / unknown / nodata


def target():
    with rasterio.open(NLUM_MASK) as t:
        return dict(crs=t.crs, transform=t.transform, shape=t.shape,
                    valid=t.read(1) == 1)



def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    (HERE / "outputs").mkdir(parents=True, exist_ok=True)
    tgt = target()

    if MODE_PATH.exists() and not args.overwrite:
        print("NVIS layers already on the NLUM grid, kept (--overwrite to redo)")
    else:
        with rasterio.open(NVIS) as src:
            print("source: %d x %d at %.0f m, %s"
                  % (src.width, src.height, src.res[0], src.crs.to_string()[:40]))

            mode = np.zeros(tgt["shape"], dtype="uint8")
            reproject(source=rasterio.band(src, 1), destination=mode,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=tgt["transform"], dst_crs=tgt["crs"],
                      src_nodata=src.nodata, dst_nodata=0,
                      resampling=Resampling.mode, num_threads=4)

        prof = dict(driver="GTiff", height=tgt["shape"][0],
                    width=tgt["shape"][1], count=1, dtype="uint8",
                    nodata=0, crs=tgt["crs"], transform=tgt["transform"],
                    compress="LZW", tiled=True, blockxsize=256, blockysize=256)
        with rasterio.open(MODE_PATH, "w", **prof) as dst:
            dst.write(mode, 1)
            dst.set_band_description(1, "NVIS4.1 MVS pre-1750, majority class")
            dst.update_tags(
                source=NVIS.name, resampling="mode (majority of ~120 pixels)",
                note="0 = outside NVIS coverage or unclassified")
        print("wrote %s" % MODE_PATH.name)

    with rasterio.open(MODE_PATH) as s:
        mode = s.read(1)
    inside = mode[tgt["valid"]]
    counts = Counter(int(v) for v in inside)
    rows = [{"mvs_code": k, "cells": v,
             "pct_of_mask": 100 * v / inside.size,
             "unclassified": k in UNCLASSIFIED}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "outputs" / "nvis_class_counts.csv", index=False)

    good = df[~df["unclassified"]]
    print("\n%d MVS classes inside the NLUM mask, %.1f%% of cells classified"
          % (len(good), good["pct_of_mask"].sum()))
    print(good.head(12).to_string(index=False, float_format=lambda v: "%.2f" % v))


if __name__ == "__main__":
    main()
