"""
Why is the scenario ordering not monotonic in forcing?

Reads   data/monthly_climate/**, plots/future_change_summary.csv
Writes  data/scenario_climate_diagnostic.csv
        plots/scenario_climate_diagnostic.png

Step_05 found that projected FPI does not fall monotonically with forcing:
ssp245 in 2070-2099 shows the smallest decline of any scenario-window (-1.3%),
smaller than ssp126 over the same years (-5.8%) and smaller than its own early
window (-3.9%). That is either a property of the forcing data or a fault in the
model, and the two have very different consequences, so it is worth measuring
rather than inferring.

The test is direct: compute what the climate actually does in each
scenario-window, in the same variables the model keys on, over the same cells,
and see whether projected FPI tracks it. If ssp245 late-century is genuinely
wetter and more humid than ssp126 late-century, the FPI result is the model
faithfully reporting its input and the non-monotonicity belongs to the forcing.
If the climate is ordered by forcing and FPI is not, the fault is in the model.

Domain means are weighted by how many NLUM land cells fall in each coarse cell,
rather than taken flat over the coarse grid. A flat mean would weight the
tropical ocean and the Southern Ocean equally with the continent, and those are
precisely the cells the projection never uses.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CLIM_VARS, DATA_DIR, HIST_YEARS, PLOTS_DIR, SSPS,
                    annual_from_monthly, load_monthly, nlum_template)
import Step_04_predict_future as S4

WINDOWS = {"2035-2064": list(range(2035, 2065)),
           "2070-2099": list(range(2070, 2100))}
N_JOBS = 12


def land_weights():
    """How many NLUM land cells fall in each coarse (0.11 deg) cell.

    Uses nearest assignment rather than the bilinear stencil: for a domain mean
    the two agree to well within the differences being measured here, and the
    nearest map is a clean integer count.
    """
    rows, cols, _ = S4.land_and_soil()
    tpl = nlum_template()
    lat, lon = tpl.y.values[rows], tpl.x.values[cols]

    ref = load_monthly("pr", HIST_YEARS[0], None)
    slat, slon = ref.lat.values, ref.lon.values
    j = np.clip(np.round((lat - slat[0]) / (slat[1] - slat[0])).astype(int),
                0, slat.size - 1)
    i = np.clip(np.round((lon - slon[0]) / (slon[1] - slon[0])).astype(int),
                0, slon.size - 1)
    w = np.zeros((slat.size, slon.size), dtype=np.float64)
    np.add.at(w, (j, i), 1.0)
    print(f"{rows.size:,} land cells over {int((w > 0).sum()):,} coarse cells")
    return w / w.sum()


def year_means(var, year, ssp, w):
    da = load_monthly(var, year, ssp)
    ann = annual_from_monthly(da, CLIM_VARS[var]).values.astype(np.float64)
    return float((ann * w).sum())


def window_mean(var, years, ssp, w):
    vals = Parallel(n_jobs=N_JOBS, backend="loky")(
        delayed(year_means)(var, y, ssp, w) for y in years
    )
    return float(np.mean(vals))


def main():
    t0 = time.time()
    w = land_weights()

    rows = []
    print("\nhistorical baseline 1985-2014")
    base = {}
    for var in CLIM_VARS:
        base[var] = window_mean(var, HIST_YEARS, None, w)
        print(f"  {var:8s} {base[var]:10.3f}")
        rows.append({"scenario": "historical", "window": "1985-2014",
                     "variable": var, "mean": base[var], "delta": 0.0,
                     "pct_delta": 0.0})

    for ssp in SSPS:
        for wname, years in WINDOWS.items():
            line = []
            for var in CLIM_VARS:
                m = window_mean(var, years, ssp, w)
                rows.append({"scenario": ssp, "window": wname, "variable": var,
                             "mean": m, "delta": m - base[var],
                             "pct_delta": 100 * (m - base[var]) / base[var]})
                line.append(f"{var}={m:.2f}({100*(m-base[var])/base[var]:+.1f}%)")
            print(f"{ssp} {wname}: " + "  ".join(line))

    df = pd.DataFrame(rows)
    df.to_csv(DATA_DIR / "scenario_climate_diagnostic.csv", index=False)

    # Join against the projected FPI change so the two can be compared directly.
    fpi = None
    p = PLOTS_DIR / "future_change_summary.csv"
    if p.exists():
        fpi = pd.read_csv(p).rename(columns={"ssp": "scenario", "period": "window"})
        wide = df[df.scenario != "historical"].pivot_table(
            index=["scenario", "window"], columns="variable", values="pct_delta")
        merged = wide.join(fpi.set_index(["scenario", "window"])["pct_change"])
        merged = merged.rename(columns={"pct_change": "fpi_pct_change"}).reset_index()
        merged.to_csv(DATA_DIR / "scenario_climate_vs_fpi.csv", index=False)
        print("\nclimate change (%) vs projected FPI change (%)")
        print(merged.round(3).to_string(index=False))

        for v in ("hurs", "pr", "tasmax"):
            if v in merged:
                r = np.corrcoef(merged[v], merged["fpi_pct_change"])[0, 1]
                print(f"  corr({v} %delta, FPI %delta) over the 8 "
                      f"scenario-windows = {r:+.3f}")

    # ------------------------------------------------------------------ plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sub = df[df.scenario != "historical"].copy()
    sub["label"] = sub["scenario"] + "\n" + sub["window"]
    order = [f"{s}\n{w_}" for w_ in WINDOWS for s in SSPS]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, var in zip(axes.ravel(), ["hurs", "pr", "tasmax", "hursmin"]):
        d = sub[sub.variable == var].set_index("label").reindex(order)
        colours = ["#B04A4A" if v < 0 else "#3B7EA1" for v in d["pct_delta"]]
        ax.bar(range(len(d)), d["pct_delta"], color=colours)
        ax.set_xticks(range(len(d)))
        ax.set_xticklabels(d.index, fontsize=7)
        ax.axhline(0, color="0.4", lw=0.8)
        ax.set(ylabel="% change vs 1985-2014", title=var)
    fig.suptitle("Projected climate change over the NLUM land cells, "
                 "by scenario and window", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "scenario_climate_diagnostic.png", dpi=160)
    plt.close(fig)

    if fpi is not None:
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
        for a, v in zip(ax, ["hurs", "pr"]):
            a.scatter(merged[v], merged["fpi_pct_change"], s=60,
                      c=["#3B7EA1", "#5B8C5A", "#C77B30", "#B04A4A"] * 2)
            for _, r in merged.iterrows():
                a.annotate(f"{r['scenario'][-3:]} {r['window'][:4]}",
                           (r[v], r["fpi_pct_change"]), fontsize=7,
                           xytext=(4, 3), textcoords="offset points")
            a.axhline(0, color="0.7", lw=0.8); a.axvline(0, color="0.7", lw=0.8)
            a.set(xlabel=f"{v} change (%)", ylabel="FPI change (%)",
                  title=f"FPI response vs {v}")
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / "scenario_fpi_vs_climate.png", dpi=160)
        plt.close(fig)

    print(f"\n{time.time() - t0:.0f}s -> {DATA_DIR / 'scenario_climate_diagnostic.csv'}")


if __name__ == "__main__":
    main()
