#!/usr/bin/env python3
"""Harmonise MEPS FYC 2018-2022 (+ dental-visits event files), BRFSS
2020/2022 and NOHSS state rates into analysis-ready CSVs.

MEPS source: AHRQ MEPS Full Year Consolidated PUFs, Stata .dta files in
data/raw/meps_dta/ (see src/download_meps.py). Read with
pandas.read_stata(convert_categoricals=False) so value-labelled variables
come back as raw numeric codes; mappings below are from the MEPS HC-243
(2022) codebook and the per-year codebooks (same coding across years;
verified by the column-presence scan in DATA.md).

Outcomes (adults 18+, in-scope PERWTyyF > 0):
  no_visit   = DVTOTyy == 0   (no dental visit in the calendar year)
  high_oop   = DVTSLFyy >= HIGH_OOP_USD (threshold set from the pooled
               distribution in this script and recorded in
               results/harmonisation.json; $1,000 if it gives >=3%
               prevalence among adults, else the 90th pct of DVTSLF among
               adults with any dental expenditure, rounded to $50)
  afford     = AFRDDN42 == 1 (could not afford dental care, R4/2) —
               descriptive only; it is an access item, not a model feature.
Predictors: age, sex, race/ethnicity (RACETHX), census region (REGIONyy),
insurance (INSCOVyy), poverty category (POVCATyy), poverty level
(POVLEVyy), dental insurance (DENTIN42), education years (EDUCYR),
highest degree (HIDEG), employment (EMPST53), self-rated health
(RTHLTH53), mental health (MNHLTH53).
NOT used: DNUNAB42/DNDLAY42 (absent from every FYC file 2018-2022 —
the "unable/delayed dental care" items were dropped from the public-use
FYC before 2018; see DATA.md); TOTEXPyy (contains dental spending, so
using it as a predictor would leak the expenditure outcome); AFRDDN42
(near-tautological for the foregone-care outcome).

BRFSS source: CDC LLCP XPT files (see src/download_brfss.py). Outcome:
no dental visit in past year. Variable names verified against the 2022
file itself (2026-11-07): the oral-health item is LASTDEN4 in 2020 and
2022 (LASTDEN3 in 2016 and earlier; the question was reworded and the
variable renamed), with calculated _DENVST3 (visited dentist in past
year) as a cross-check; race is _RACE1; sex is SEXVAR; health coverage
is PRIMINSR (HLTHPLN1 was dropped from the 2022 core). PRIMINSR 2022
coding (Wisconsin 2022 codebook, national instrument): 1 employer/union,
2 private, 3 Medicare, 4 Medigap, 5 Medicaid, 6 CHIP, 7 TRICARE/VA,
8 Indian Health Service, 9 state-sponsored, 10 other government program,
88 no coverage of any type. Income is INCOME3 in 2022 but INCOME2 in
2020 (same 1-8 bands). State from _STATE (FIPS).
NOHSS: state overall crude % with a dental visit in the past year,
from data/raw/nohss_adult_dental_visit.csv.

Outputs: data/harmonised/meps.csv, brfss.csv, nohss_state.csv,
results/harmonisation.json (n's, prevalences, threshold, event-file
cross-check, BRFSS column availability).
"""
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "harmonised"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = [2018, 2019, 2020, 2021, 2022]
FYC = {2018: "h209", 2019: "h216", 2020: "h224", 2021: "h233", 2022: "h243"}
DV = {2018: "h206b", 2019: "h213b", 2020: "h220b", 2021: "h229b", 2022: "h239b"}

RACE = {1: "Hispanic", 2: "NH White", 3: "NH Black", 4: "NH Asian",
        5: "NH Other/multiple"}
REGION = {1: "Northeast", 2: "Midwest", 3: "South", 4: "West"}
INSCOV = {1: "Any private", 2: "Public only", 3: "Uninsured"}
POVCAT = {1: "Poor", 2: "Near poor", 3: "Low income", 4: "Middle income",
          5: "High income"}
YESNO = {1: "Yes", 2: "No"}
EMPST = {1: "Employed", 2: "Employed (job to return to)",
         3: "Employed (job during ref period)", 4: "Not employed"}
HEALTH = {1: "Excellent", 2: "Very good", 3: "Good", 4: "Fair", 5: "Poor"}
HIDEG = {1: "No degree", 2: "GED", 3: "High school diploma",
         4: "Bachelor's", 5: "Master's", 6: "Doctorate", 7: "Other degree",
         8: "Under 16 - inapplicable"}
SEX = {1: "Male", 2: "Female"}


def _clean_code(s: pd.Series) -> pd.Series:
    """MEPS reserved codes: -1 inapplicable, -7 refused, -8 don't know,
    -9 not ascertained, -15 cannot be computed -> NaN."""
    return s.where(~s.isin([-1, -7, -8, -9, -15]))


def harmonise_meps() -> tuple[pd.DataFrame, dict]:
    frames, info = [], {"years": {}, "dnunab_present": {}, "dndlay_present": {}}
    for y in YEARS:
        yy = str(y)[2:]
        cols = ["DUPERSID", f"AGE{yy}X", "SEX", "RACETHX", f"REGION{yy}",
                f"INSCOV{yy}", f"POVCAT{yy}", f"POVLEV{yy}", "DENTIN42",
                "AFRDDN42", "EDUCYR", "HIDEG", "EMPST53", "RTHLTH53",
                "MNHLTH53", f"DVTOT{yy}", f"DVTEXP{yy}", f"DVTSLF{yy}",
                f"DVTPRV{yy}", f"DVTMCD{yy}", f"DVTMCR{yy}", f"PERWT{yy}F"]
        df = pd.read_stata(RAW / "meps_dta" / f"{FYC[y]}.dta",
                           columns=cols, convert_categoricals=False)
        # DNUNAB/DNDLAY presence check (read header only via a second
        # StataReader call is expensive; instead check the file's
        # variable list with a zero-row read).
        from pandas.io.stata import StataReader
        labels = StataReader(RAW / "meps_dta" / f"{FYC[y]}.dta").variable_labels()
        info["dnunab_present"][str(y)] = "DNUNAB42" in labels
        info["dndlay_present"][str(y)] = "DNDLAY42" in labels

        df["year"] = y
        df["age"] = pd.to_numeric(df[f"AGE{yy}X"], errors="coerce")
        df["sex"] = _clean_code(df["SEX"]).map(SEX)
        df["race"] = _clean_code(df["RACETHX"]).map(RACE)
        df["region"] = _clean_code(df[f"REGION{yy}"]).map(REGION)
        df["inscov"] = _clean_code(df[f"INSCOV{yy}"]).map(INSCOV)
        df["povcat"] = _clean_code(df[f"POVCAT{yy}"]).map(POVCAT)
        df["povlev"] = pd.to_numeric(df[f"POVLEV{yy}"], errors="coerce")
        df["dental_ins"] = _clean_code(df["DENTIN42"]).map(YESNO)
        df["afford_no"] = (_clean_code(df["AFRDDN42"]) == 1).astype("float")
        df["educyr"] = pd.to_numeric(_clean_code(df["EDUCYR"]), errors="coerce")
        df["hideg"] = _clean_code(df["HIDEG"]).map(HIDEG)
        df["empst"] = _clean_code(df["EMPST53"]).map(EMPST)
        df["health"] = _clean_code(df["RTHLTH53"]).map(HEALTH)
        df["mhealth"] = _clean_code(df["MNHLTH53"]).map(HEALTH)
        nvis = pd.to_numeric(df[f"DVTOT{yy}"], errors="coerce")
        df["n_dental_visits"] = nvis.where(nvis >= 0)
        df["dental_exp"] = pd.to_numeric(df[f"DVTEXP{yy}"], errors="coerce")
        df["dental_exp"] = df["dental_exp"].where(df["dental_exp"] >= 0)
        df["dental_oop"] = pd.to_numeric(df[f"DVTSLF{yy}"], errors="coerce")
        df["dental_oop"] = df["dental_oop"].where(df["dental_oop"] >= 0)
        df["dental_priv"] = pd.to_numeric(df[f"DVTPRV{yy}"], errors="coerce")
        df["dental_mcd"] = pd.to_numeric(df[f"DVTMCD{yy}"], errors="coerce")
        df["dental_mcr"] = pd.to_numeric(df[f"DVTMCR{yy}"], errors="coerce")
        df["perwt"] = pd.to_numeric(df[f"PERWT{yy}F"], errors="coerce")
        keep = ["DUPERSID", "year", "age", "sex", "race", "region", "inscov",
                "povcat", "povlev", "dental_ins", "afford_no", "educyr",
                "hideg", "empst", "health", "mhealth", "n_dental_visits",
                "dental_exp", "dental_oop", "dental_priv", "dental_mcd",
                "dental_mcr", "perwt"]
        df = df[keep]
        # Adults 18+, in-scope (positive full-year weight).
        n0 = len(df)
        df = df[(df["age"] >= 18) & (df["perwt"] > 0)].copy()
        info["years"][str(y)] = {
            "fyc_rows": int(n0), "adults_18plus": int(len(df)),
            "no_visit_prev": float((df["n_dental_visits"] == 0).mean()),
            "any_dental_exp_prev": float((df["dental_exp"] > 0).mean()),
            "afford_prev": float(df["afford_no"].mean()),
            "median_oop_spenders": float(
                df.loc[df["dental_exp"] > 0, "dental_oop"].median()),
            "p90_oop_spenders": float(
                df.loc[df["dental_exp"] > 0, "dental_oop"].quantile(0.90)),
            "p90_oop_all": float(df["dental_oop"].quantile(0.90)),
            "prev_oop_ge_1000": float((df["dental_oop"] >= 1000).mean()),
        }
        frames.append(df)
        print(f"MEPS {y}: {len(df)} adults 18+; no-visit "
              f"{info['years'][str(y)]['no_visit_prev']:.3f}; "
              f"afford {info['years'][str(y)]['afford_prev']:.3f}")
    meps = pd.concat(frames, ignore_index=True)
    meps["no_visit"] = (meps["n_dental_visits"] == 0).astype(int)
    meps["any_dental_exp"] = (meps["dental_exp"] > 0).astype(int)
    # High-OOP threshold: $1,000 if it gives >=3% prevalence among adults,
    # else the 90th percentile of OOP among adults with any dental
    # expenditure, rounded to the nearest $50.
    prev1000 = float((meps["dental_oop"] >= 1000).mean())
    if prev1000 >= 0.03:
        thresh = 1000
    else:
        thresh = int(round(
            meps.loc[meps["dental_exp"] > 0, "dental_oop"].quantile(0.90) / 50.0) * 50)
    meps["high_oop"] = (meps["dental_oop"] >= thresh).astype(int)
    info["high_oop_threshold_usd"] = int(thresh)
    info["high_oop_prev_pooled"] = float(meps["high_oop"].mean())
    info["no_visit_prev_pooled"] = float(meps["no_visit"].mean())
    info["n_pooled"] = int(len(meps))
    print(f"pooled n={len(meps)}; no-visit {info['no_visit_prev_pooled']:.3f}; "
          f"high-OOP>={thresh} {info['high_oop_prev_pooled']:.3f}")
    return meps, info


def check_event_files(meps: pd.DataFrame) -> dict:
    """Cross-check FYC dental aggregates against the Dental Visits event
    files: sum event DVXPyyX (total payment) and DVSFyyX (self/family)
    by person and compare with FYC DVTEXPyy / DVTSLFyy."""
    out = {}
    for y in YEARS:
        yy = str(y)[2:]
        ev = pd.read_stata(RAW / "meps_dta" / f"{DV[y]}.dta",
                           columns=["DUPERSID", f"DVXP{yy}X", f"DVSF{yy}X"],
                           convert_categoricals=False)
        agg = ev.groupby("DUPERSID").agg(
            ev_total=(f"DVXP{yy}X", "sum"),
            ev_oop=(f"DVSF{yy}X", "sum"),
            ev_n=("DUPERSID", "size")).reset_index()
        sub = meps[meps["year"] == y][["DUPERSID", "dental_exp", "dental_oop",
                                       "n_dental_visits"]].merge(
            agg, on="DUPERSID", how="left")
        sub["ev_total"] = sub["ev_total"].fillna(0)
        sub["ev_oop"] = sub["ev_oop"].fillna(0)
        sub["ev_n"] = sub["ev_n"].fillna(0)
        exact_tot = float((sub["ev_total"] == sub["dental_exp"]).mean())
        exact_oop = float((sub["ev_oop"] == sub["dental_oop"]).mean())
        exact_n = float((sub["ev_n"] == sub["n_dental_visits"]).mean())
        corr = float(np.corrcoef(sub["ev_total"], sub["dental_exp"])[0, 1])
        out[str(y)] = {"event_rows": int(len(ev)),
                       "persons_with_events": int((sub["ev_n"] > 0).sum()),
                       "exact_match_total_exp": exact_tot,
                       "exact_match_oop": exact_oop,
                       "exact_match_n_visits": exact_n,
                       "corr_event_total_vs_fyc": corr}
        print(f"event check {y}: exact total {exact_tot:.3f}, oop {exact_oop:.3f}, "
              f"n-visits {exact_n:.3f}, corr {corr:.4f}")
    return out


STATE_FIPS = {1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT",
              10: "DE", 11: "DC", 12: "FL", 13: "GA", 15: "HI", 16: "ID",
              17: "IL", 18: "IN", 19: "IA", 20: "KS", 21: "KY", 22: "LA",
              23: "ME", 24: "MD", 25: "MA", 26: "MI", 27: "MN", 28: "MS",
              29: "MO", 30: "MT", 31: "NE", 32: "NV", 33: "NH", 34: "NJ",
              35: "NM", 36: "NY", 37: "NC", 38: "ND", 39: "OH", 40: "OK",
              41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD", 47: "TN",
              48: "TX", 49: "UT", 50: "VT", 51: "VA", 53: "WA", 54: "WV",
              55: "WI", 56: "WY", 66: "GU", 72: "PR", 78: "VI"}


def harmonise_brfss() -> tuple[pd.DataFrame | None, dict]:
    info = {"years": {}, "columns": {}, "status": "ok"}
    frames = []
    for y in (2020, 2022):
        zpath = RAW / f"brfss_{y}_LLCPXPT.zip"
        if not zpath.exists() or zpath.stat().st_size < 1_000_000 \
                or zpath.read_bytes()[:2] != b"PK":
            info["status"] = f"missing/invalid file brfss_{y}_LLCPXPT.zip"
            info["years"][str(y)] = "MISSING-or-INVALID"
            print(f"BRFSS {y}: MISSING or INVALID {zpath} "
                  f"({zpath.stat().st_size if zpath.exists() else 0} bytes)")
            continue
        with zipfile.ZipFile(zpath) as z:
            # NB: the 2022 member name is "LLCP2022.XPT " with a trailing
            # space — strip before matching the extension.
            names = [n for n in z.namelist() if n.strip().upper().endswith(".XPT")]
            xpt = z.extract(names[0], RAW / "brfss_xpt")
        df = pd.read_sas(xpt, format="xport", chunksize=100000)
        # read_sas with chunksize returns an iterator; collect only
        # needed columns (usecols is not supported for XPORT in this
        # pandas version, so filter per chunk).
        keep = ["_STATE", "LASTDEN4", "LASTDEN3", "_DENVST3", "SEXVAR",
                "SEX1", "_RACE1", "_RACE", "EDUCA", "INCOME3", "INCOME2",
                "EMPLOY1", "PRIMINSR", "HLTHPLN1", "_AGEG5YR", "_AGE80",
                "RMVTETH4", "RMVTETH3", "_LLCPWT", "DISPCODE"]
        chunks = []
        for ch in df:
            cols = [c for c in keep if c in ch.columns]
            chunks.append(ch[cols])
        df = pd.concat(chunks, ignore_index=True)
        info["columns"][str(y)] = sorted(df.columns.tolist())
        df["year"] = y
        df["state"] = df["_STATE"].map(STATE_FIPS)
        lastden_col = "LASTDEN4" if "LASTDEN4" in df.columns else "LASTDEN3"
        df["lastden"] = pd.to_numeric(df[lastden_col], errors="coerce")
        df = df[df["lastden"].isin([1, 2, 3, 4, 8])].copy()
        df["no_visit"] = (df["lastden"] != 1).astype(int)
        # Cross-check against the calculated variable when present:
        # _DENVST3 1 = visited in past year, 2 = did not.
        if "_DENVST3" in df.columns:
            chk = df[df["_DENVST3"].isin([1, 2])]
            agree = float((((chk["_DENVST3"] == 1) & (chk["no_visit"] == 0))
                           | ((chk["_DENVST3"] == 2) & (chk["no_visit"] == 1))).mean())
            info.setdefault("denvs_check", {})[str(y)] = agree
            print(f"BRFSS {y}: _DENVST3 cross-check agreement {agree:.4f}")
        sexcol = "SEXVAR" if "SEXVAR" in df.columns else "SEX1"
        df["sex"] = df[sexcol].map({1: "Male", 2: "Female"})
        racecol = "_RACE1" if "_RACE1" in df.columns else "_RACE"
        df["race"] = df[racecol].map({1: "NH White", 2: "NH Black",
                                       3: "AI/AN", 4: "NH Asian",
                                       5: "NHPI", 6: "Other", 7: "Multiracial",
                                       8: "Hispanic", 9: "Unknown"}) \
            if racecol in df.columns else np.nan
        df["educa"] = df["EDUCA"] if "EDUCA" in df.columns else np.nan
        # Income is INCOME3 in 2022, INCOME2 in 2020 (same 1-8 bands).
        if "INCOME3" in df.columns:
            df["income"] = df["INCOME3"]
        elif "INCOME2" in df.columns:
            df["income"] = df["INCOME2"]
        else:
            df["income"] = np.nan
        df["employ"] = df["EMPLOY1"] if "EMPLOY1" in df.columns else np.nan
        # Health coverage: PRIMINSR (2022 core) 1-10 = a named source,
        # 88 = no coverage of any type; HLTHPLN1 (2020) 1 = yes, 2 = no.
        # Label is "No coverage", not "None": pandas' default NA list
        # parses the literal string "None" as missing on read-back.
        if "PRIMINSR" in df.columns:
            df["hlthpln"] = df["PRIMINSR"].map(
                {**{k: "Insured" for k in range(1, 11)}, 88: "No coverage"})
        elif "HLTHPLN1" in df.columns:
            df["hlthpln"] = df["HLTHPLN1"].map(
                {1: "Insured", 2: "No coverage"})
        else:
            df["hlthpln"] = np.nan
        agecol = "_AGEG5YR" if "_AGEG5YR" in df.columns else "_AGE80"
        df["agegrp"] = df[agecol] if agecol in df.columns else np.nan
        out = df[["year", "state", "no_visit", "sex", "race", "educa",
                  "income", "employ", "hlthpln", "agegrp"]]
        info["years"][str(y)] = {"n": int(len(out)),
                                  "no_visit_prev": float(out["no_visit"].mean()),
                                  "states": int(out["state"].nunique())}
        frames.append(out)
        print(f"BRFSS {y}: n={len(out)} no-visit {out['no_visit'].mean():.3f} "
              f"states={out['state'].nunique()}")
    if not frames:
        return None, info
    return pd.concat(frames, ignore_index=True), info


def harmonise_nohss() -> pd.DataFrame:
    df = pd.read_csv(RAW / "nohss_adult_dental_visit.csv", dtype=str)
    ov = df[(df["break_out_category"].isna())
            & (df["data_value_type"] == "Crude Prevalence")
            & (df["response"] == "Yes")].copy()
    ov["year"] = ov["year"].astype(int)
    # NOHSS data_value is a PERCENT (0-100); convert to a proportion
    # so it is comparable with the BRFSS rates computed here (0-1).
    ov["visit_rate"] = pd.to_numeric(ov["data_value"], errors="coerce") / 100.0
    ov = ov[ov["locationabbr"] != "US"]
    out = ov[["year", "locationabbr", "visit_rate"]].rename(
        columns={"locationabbr": "state"})
    print(f"NOHSS overall state rows: {len(out)}; years "
          f"{sorted(out['year'].unique())}; states {out['state'].nunique()}")
    return out


def main():
    meps, info = harmonise_meps()
    meps.to_csv(OUT / "meps.csv", index=False)
    info["event_check"] = check_event_files(meps)
    brfss, binfo = harmonise_brfss()
    info["brfss"] = binfo
    if brfss is not None:
        brfss.to_csv(OUT / "brfss.csv", index=False)
    nohss = harmonise_nohss()
    nohss.to_csv(OUT / "nohss_state.csv", index=False)
    info["nohss"] = {"rows": int(len(nohss)),
                     "years": sorted(nohss["year"].unique().tolist()),
                     "states": int(nohss["state"].nunique())}
    (ROOT / "results" / "harmonisation.json").write_text(
        json.dumps(info, indent=2, default=str))
    print(f"wrote {OUT/'meps.csv'} ({len(meps)}), "
          f"{OUT/'nohss_state.csv'} ({len(nohss)})")


if __name__ == "__main__":
    main()
