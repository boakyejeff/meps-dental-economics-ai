#!/usr/bin/env python3
"""Figures for the MEPS/BRFSS dental-economics project.

Reads results/test_predictions_*.csv, results/state_rates.csv and
results/harmonisation.json. Writes results/figures/*.png:
  roc_meps_no_visit.png, roc_meps_high_oop.png, roc_brfss_no_visit.png
  calibration_meps_no_visit.png, calibration_meps_high_oop.png,
  calibration_brfss_no_visit.png
  state_choropleth_brfss.png (BRFSS latest year, % no dental visit)
  state_ranked_brfss.png (ranked state bars, latest year)
  meps_yearly_prevalence.png (no-visit + could-not-afford, 2018-2022)
Choropleth uses data/raw/us-states.geojson (PublicaMundi, 52 features);
if it is absent, the choropleth is skipped and the ranked chart still
runs. No geopandas (not installed); polygons are drawn by hand.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
from sklearn.metrics import auc, roc_curve

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = RES / "figures"
FIG.mkdir(parents=True, exist_ok=True)

NAME2ABBR = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ",
             "Arkansas": "AR", "California": "CA", "Colorado": "CO",
             "Connecticut": "CT", "Delaware": "DE", "Florida": "FL",
             "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
             "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
             "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
             "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
             "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
             "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
             "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
             "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
             "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
             "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
             "South Carolina": "SC", "South Dakota": "SD",
             "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
             "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
             "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
             "District of Columbia": "DC", "Puerto Rico": "PR"}


def roc_fig(csv, outcome, title, outname):
    df = pd.read_csv(RES / csv)
    y = df[outcome].values
    fig, ax = plt.subplots(figsize=(6, 5))
    for col, label in (("p_logistic", "Logistic regression"),
                       ("p_hgb", "HistGradientBoosting")):
        fpr, tpr, _ = roc_curve(y, df[col].values)
        ax.plot(fpr, tpr, label=f"{label} (AUC {auc(fpr, tpr):.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(FIG / outname, dpi=150)
    plt.close(fig)
    print("wrote", outname)


def calib_fig(csv, outcome, title, outname):
    df = pd.read_csv(RES / csv)
    y = df[outcome].values
    fig, ax = plt.subplots(figsize=(6, 5))
    edges = np.linspace(0, 1, 11)
    for col, label in (("p_logistic", "Logistic regression"),
                       ("p_hgb", "HistGradientBoosting")):
        p = df[col].values
        xs, ys = [], []
        for i in range(10):
            lo, hi = edges[i], edges[i + 1]
            m = (p > lo) & (p <= hi) if i > 0 else (p >= lo) & (p <= hi)
            if m.sum() > 0:
                xs.append(p[m].mean())
                ys.append(y[m].mean())
        ax.plot(xs, ys, "o-", label=label, ms=4)
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(FIG / outname, dpi=150)
    plt.close(fig)
    print("wrote", outname)


def state_figs():
    rates = pd.read_csv(RES / "state_rates.csv")
    brf = rates.dropna(subset=["brfss_no_visit_rate"])
    year = int(brf["year"].max())
    latest = brf[brf["year"] == year].copy()
    # Flagged state-years (MS 2022 anomaly) are drawn grey, not ranked.
    flagged_states = set(latest.loc[latest["flag"].fillna("") != "", "state"])
    latest_clean = latest[~latest["state"].isin(flagged_states)]
    # Ranked bars: 15 highest + 15 lowest (flagged states excluded).
    srt = latest_clean.sort_values("brfss_no_visit_rate")
    sel = pd.concat([srt.head(15), srt.tail(15)])
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(sel["state"], sel["brfss_no_visit_rate"] * 100,
            color=["#c0392b" if v in set(srt.tail(15)["state"]) else "#2e86c1"
                   for v in sel["state"]])
    ax.set_xlabel(f"% adults with no dental visit in past year, BRFSS {year} (unweighted)")
    ax.set_title(f"State variation in no dental visit, BRFSS {year}\n"
                 f"(15 lowest in blue, 15 highest in red; "
                 f"{', '.join(sorted(flagged_states))} excluded — see DATA.md)"
                 if flagged_states else
                 f"State variation in no dental visit, BRFSS {year}\n"
                 f"(15 lowest in blue, 15 highest in red)")
    fig.tight_layout()
    fig.savefig(FIG / "state_ranked_brfss.png", dpi=150)
    plt.close(fig)
    print("wrote state_ranked_brfss.png")
    # Choropleth.
    gj = ROOT / "data" / "raw" / "us-states.geojson"
    if not gj.exists():
        print("us-states.geojson missing — choropleth skipped")
        return
    geo = json.loads(gj.read_text())
    vals = dict(zip(latest_clean["state"],
                    latest_clean["brfss_no_visit_rate"] * 100))
    vmin, vmax = min(vals.values()), max(vals.values())
    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.YlOrRd
    fig, ax = plt.subplots(figsize=(10, 6))
    polys, cols = [], []
    for feat in geo["features"]:
        abbr = NAME2ABBR.get(feat["properties"]["name"])
        if abbr is None:
            continue
        geom = feat["geometry"]
        rings = geom["coordinates"] if geom["type"] == "Polygon" else \
            [p for poly in geom["coordinates"] for p in poly]
        for ring in rings:
            polys.append(np.array(ring))
            if abbr in vals:
                cols.append(cmap(norm(vals[abbr])))
            else:
                # Flagged (MS 2022) or missing: light grey.
                cols.append((0.85, 0.85, 0.85, 1.0))
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="white",
                                     linewidths=0.4))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    plt.colorbar(sm, ax=ax, shrink=0.6,
                 label=f"% no dental visit in past year, BRFSS {year}")
    ax.set_title(f"No dental visit in the past year by state, BRFSS {year}\n"
                 f"(unweighted; range {vmin:.1f}%-{vmax:.1f}%; "
                 f"grey = {', '.join(sorted(flagged_states))} excluded, see DATA.md)"
                 if flagged_states else
                 f"No dental visit in the past year by state, BRFSS {year}\n"
                 f"(unweighted; range {vmin:.1f}%-{vmax:.1f}%)")
    fig.tight_layout()
    fig.savefig(FIG / "state_choropleth_brfss.png", dpi=150)
    plt.close(fig)
    print("wrote state_choropleth_brfss.png")


def yearly_fig():
    h = json.loads((RES / "harmonisation.json").read_text())
    yrs = sorted(h["years"], key=int)
    nv = [h["years"][y]["no_visit_prev"] * 100 for y in yrs]
    af = [h["years"][y]["afford_prev"] * 100 for y in yrs]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot([int(y) for y in yrs], nv, "o-", label="No dental visit (DVTOT=0)")
    ax.plot([int(y) for y in yrs], af, "s-",
            label="Could not afford dental care (AFRDDN42=1)")
    ax.set_xlabel("Year")
    ax.set_ylabel("% of adults 18+ (unweighted)")
    ax.set_title("MEPS dental access, 2018-2022 (note the 2020 COVID rise)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "meps_yearly_prevalence.png", dpi=150)
    plt.close(fig)
    print("wrote meps_yearly_prevalence.png")


def main():
    if (RES / "test_predictions_meps_no_visit.csv").exists():
        roc_fig("test_predictions_meps_no_visit.csv", "no_visit",
                "ROC — no dental visit, MEPS test 2022",
                "roc_meps_no_visit.png")
        calib_fig("test_predictions_meps_no_visit.csv", "no_visit",
                  "Calibration — no dental visit, MEPS test 2022",
                  "calibration_meps_no_visit.png")
    if (RES / "test_predictions_meps_high_oop.csv").exists():
        roc_fig("test_predictions_meps_high_oop.csv", "high_oop",
                "ROC — high out-of-pocket dental spending, MEPS test 2022",
                "roc_meps_high_oop.png")
        calib_fig("test_predictions_meps_high_oop.csv", "high_oop",
                  "Calibration — high OOP dental spending, MEPS test 2022",
                  "calibration_meps_high_oop.png")
    if (RES / "test_predictions_brfss_no_visit.csv").exists():
        roc_fig("test_predictions_brfss_no_visit.csv", "no_visit",
                "ROC — no dental visit, BRFSS test",
                "roc_brfss_no_visit.png")
        calib_fig("test_predictions_brfss_no_visit.csv", "no_visit",
                  "Calibration — no dental visit, BRFSS test",
                  "calibration_brfss_no_visit.png")
    if (RES / "state_rates.csv").exists():
        state_figs()
    if (RES / "harmonisation.json").exists():
        yearly_fig()
    print("figures done.")


if __name__ == "__main__":
    main()
