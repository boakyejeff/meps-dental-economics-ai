#!/usr/bin/env python3
"""Train + evaluate the MEPS and BRFSS dental-economics models.

MEPS (primary): adults 18+, outcomes no_visit (DVTOT==0) and high_oop
(DVTSLF >= $1,000; threshold + prevalence in results/harmonisation.json).
Temporal split: train 2018-2020, validation 2021 (Youden threshold),
test 2022. Models: logistic regression (balanced) + HistGradientBoosting
(balanced). Metrics @0.5 and @validation-Youden: AUC, accuracy,
sensitivity, specificity, ECE (10 bins), Brier. Fairness audit on the
test set by poverty band, insurance status and race/ethnicity.

BRFSS (state angle): outcome no dental visit in past year (LASTDEN4).
Train 2020 -> test 2022 when both years are present; otherwise a
stratified 80/20 split of the available year, labelled as such.
Training rows are subsampled to 150k (documented) for CPU time; the
test set is used in full. Same models, metrics and audit (by income
band, coverage, race).

Unweighted throughout (prediction, not population estimation), matching
the NHANES sibling. CPU only.
Outputs: results/metrics_meps_{no_visit,high_oop}.json,
results/metrics_brfss_no_visit.json, results/*_coefficients.json,
results/*_importance.json, results/test_predictions_*.csv,
results/state_rates.csv, results/state_rates.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss,
                             confusion_matrix, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
HARM = ROOT / "data" / "harmonised"
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)

RNG = np.random.RandomState(7)


def ece(y, p, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    out = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (p > lo) & (p <= hi) if i > 0 else (p >= lo) & (p <= hi)
        if m.sum() > 0:
            out += abs(y[m].mean() - p[m].mean()) * m.mean()
    return float(out)


def youden_threshold(y, p):
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def eval_at(y, p, thr):
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"threshold": float(thr), "accuracy": float(accuracy_score(y, pred)),
            "sensitivity": float(tp / (tp + fn)) if tp + fn else float("nan"),
            "specificity": float(tn / (tn + fp)) if tn + fp else float("nan"),
            "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)}


def evaluate(y_true, proba, y_val=None, p_val=None):
    out = {"n": int(len(y_true)), "prevalence": float(np.mean(y_true)),
           "auc": float(roc_auc_score(y_true, proba)),
           "ece": ece(y_true, proba),
           "brier": float(brier_score_loss(y_true, proba))}
    out["at_0.5"] = eval_at(y_true, proba, 0.5)
    if y_val is not None and p_val is not None:
        thr = youden_threshold(y_val, p_val)
        out["youden_threshold_from_validation"] = thr
        out["at_youden"] = eval_at(y_true, proba, thr)
    return out


def audit(y_true, proba, strata: pd.Series, name: str):
    rows = []
    strata = strata.reset_index(drop=True)
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    for val in pd.unique(strata.dropna()):
        m = (strata == val).values
        if m.sum() < 50:
            continue
        yt, pt = y_true[m], proba[m]
        if len(np.unique(yt)) < 2:
            auc = float("nan")
        else:
            auc = float(roc_auc_score(yt, pt))
        e = eval_at(yt, pt, 0.5)
        rows.append({"stratum": name, "group": str(val), "n": int(m.sum()),
                     "prevalence": float(yt.mean()), "auc": auc,
                     "sensitivity_at_0.5": e["sensitivity"],
                     "specificity_at_0.5": e["specificity"]})
    return rows


def build_prep(num, cat):
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore",
                                               sparse_output=False))]), cat),
    ])


def fit_models(Xtr, ytr, Xva, yva, Xte, yte, num, cat, tag, strata_te):
    prep = build_prep(num, cat)
    lr = Pipeline([("prep", prep),
                   ("clf", LogisticRegression(max_iter=1000, C=1.0,
                                              class_weight="balanced"))])
    hgb = Pipeline([("prep", prep),
                    ("clf", HistGradientBoostingClassifier(
                        max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                        class_weight="balanced", random_state=7))])
    out = {"model_tag": tag}
    preds = {}
    for name, mdl in (("logistic", lr), ("hgb", hgb)):
        mdl.fit(Xtr, ytr)
        p_tr = mdl.predict_proba(Xtr)[:, 1]
        p_va = mdl.predict_proba(Xva)[:, 1]
        p_te = mdl.predict_proba(Xte)[:, 1]
        preds[name] = (p_va, p_te)
        res = {"train_auc": float(roc_auc_score(ytr, p_tr)),
               "validation": evaluate(yva, p_va),
               "test": evaluate(yte, p_te, yva, p_va)}
        res["test"]["fairness_audit"] = []
        for sname, scol in strata_te.items():
            res["test"]["fairness_audit"].extend(
                audit(yte, p_te, scol, sname))
        out[name] = res
        print(f"{tag} {name}: val AUC {res['validation']['auc']:.3f}, "
              f"test AUC {res['test']['auc']:.3f}, test ECE "
              f"{res['test']['ece']:.3f}")
        # Interpretability: LR coefficients (on the one-hot design) and
        # HGB permutation importance on a 5k test subsample.
        try:
            feats = mdl.named_steps["prep"].get_feature_names_out()
        except Exception:  # noqa: BLE001
            feats = [f"f{i}" for i in range(Xte.shape[1])]
        if name == "logistic":
            coefs = mdl.named_steps["clf"].coef_[0]
            order = np.argsort(-np.abs(coefs))[:25]
            (RES / f"lr_coefficients_{tag}.json").write_text(json.dumps(
                [{"feature": str(feats[i]), "coef": float(coefs[i])}
                 for i in order], indent=2))
        else:
            idx = RNG.choice(len(Xte), size=min(5000, len(Xte)),
                             replace=False)
            pi = permutation_importance(mdl, Xte.iloc[idx], yte[idx],
                                        n_repeats=3, random_state=7,
                                        scoring="roc_auc")
            order = np.argsort(-pi.importances_mean)[:25]
            (RES / f"hgb_importance_{tag}.json").write_text(json.dumps(
                [{"feature": str(feats[i]),
                  "importance_auc_drop": float(pi.importances_mean[i])}
                 for i in order], indent=2))
    return out, preds


# ---------------------------------------------------------------- MEPS
def run_meps():
    df = pd.read_csv(HARM / "meps.csv")
    df["employed"] = df["empst"].map(
        {"Employed": "Employed",
         "Employed (job to return to)": "Employed",
         "Employed (job during ref period)": "Employed",
         "Not employed": "Not employed"})
    df["hideg_collapsed"] = df["hideg"].map(
        {"No degree": "No degree", "GED": "GED",
         "High school diploma": "High school diploma",
         "Bachelor's": "Bachelor's", "Master's": "Master's+",
         "Doctorate": "Master's+", "Other degree": "Other degree"})
    df["health_num"] = df["health"].map(
        {"Excellent": 1, "Very good": 2, "Good": 3, "Fair": 4, "Poor": 5})
    df["mhealth_num"] = df["mhealth"].map(
        {"Excellent": 1, "Very good": 2, "Good": 3, "Fair": 4, "Poor": 5})
    num = ["age", "educyr", "povlev", "health_num", "mhealth_num"]
    cat = ["sex", "race", "region", "inscov", "povcat", "dental_ins",
           "hideg_collapsed", "employed"]
    tr = df[df["year"] <= 2020]
    va = df[df["year"] == 2021]
    te = df[df["year"] == 2022]
    all_preds = {}
    for outcome in ("no_visit", "high_oop"):
        sub_tr, sub_va, sub_te = tr, va, te
        out, preds = fit_models(
            sub_tr[num + cat], sub_tr[outcome].values,
            sub_va[num + cat], sub_va[outcome].values,
            sub_te[num + cat], sub_te[outcome].values,
            num, cat, f"meps_{outcome}",
            {"poverty_band": sub_te["povcat"],
             "insurance": sub_te["inscov"], "race_ethnicity": sub_te["race"]})
        out["design"] = {"train_years": "2018-2020", "validation_year": 2021,
                         "test_year": 2022, "n_train": int(len(sub_tr)),
                         "n_validation": int(len(sub_va)),
                         "n_test": int(len(sub_te)),
                         "features_numeric": num, "features_categorical": cat}
        (RES / f"metrics_meps_{outcome}.json").write_text(
            json.dumps(out, indent=2, default=str))
        all_preds[outcome] = preds
        te_out = sub_te[["year", "age", "sex", "race", "povcat", "inscov",
                         "region", outcome]].copy()
        te_out["p_logistic"] = preds["logistic"][1]
        te_out["p_hgb"] = preds["hgb"][1]
        te_out.to_csv(RES / f"test_predictions_meps_{outcome}.csv",
                      index=False)
    return df


# ---------------------------------------------------------------- BRFSS
def run_brfss():
    path = HARM / "brfss.csv"
    if not path.exists():
        print("BRFSS harmonised file missing — skipping BRFSS model.")
        return None
    df = pd.read_csv(path)
    df["age_band"] = pd.cut(df["agegrp"], bins=[0, 2, 6, 9, 14],
                            labels=["18-29", "30-49", "50-64", "65+"],
                            include_lowest=True)
    df["edu_band"] = df["educa"].map(
        {1: "Less than HS", 2: "Less than HS", 3: "Less than HS",
         4: "HS grad", 5: "Some college", 6: "College grad"})
    df["income_band"] = df["income"].map(
        {1: "<$25k", 2: "<$25k", 3: "<$25k", 4: "<$25k",
         5: "$25-50k", 6: "$25-50k", 7: "$50-75k",
         8: "$75k+", 9: "$75k+", 10: "$75k+", 11: "$75k+"})
    df["employ_band"] = df["employ"].map(
        {1: "Employed", 2: "Employed", 3: "Unemployed", 4: "Unemployed",
         5: "Not in labour force", 6: "Not in labour force",
         7: "Not in labour force", 8: "Not in labour force"})
    num: list[str] = []
    cat = ["age_band", "sex", "race", "edu_band", "income_band",
           "employ_band", "hlthpln", "state"]
    years = sorted(df["year"].unique())
    if len(years) >= 2:
        tr_all, va_all, te = df[df["year"] == years[0]], None, df[df["year"] == years[-1]]
        design = {"train_year": int(years[0]), "test_year": int(years[-1]),
                  "split": "temporal"}
        # Validation = 20% of the training year (for the Youden threshold).
        rng = np.random.RandomState(7)
        idx = rng.permutation(len(tr_all))
        n_va = int(0.2 * len(tr_all))
        va_all, tr_all = tr_all.iloc[idx[:n_va]], tr_all.iloc[idx[n_va:]]
    else:
        rng = np.random.RandomState(7)
        idx = rng.permutation(len(df))
        n_te = int(0.2 * len(df))
        te, rest = df.iloc[idx[:n_te]], df.iloc[idx[n_te:]]
        idx2 = rng.permutation(len(rest))
        n_va = int(0.2 * len(rest))
        va_all, tr_all = rest.iloc[idx2[:n_va]], rest.iloc[idx2[n_va:]]
        design = {"train_year": int(years[0]), "test_year": int(years[0]),
                  "split": "pooled 80/20 (only one BRFSS year available)"}
    # Subsample training rows for CPU time (documented).
    if len(tr_all) > 150_000:
        tr_all = tr_all.sample(150_000, random_state=7)
    if len(va_all) > 50_000:
        va_all = va_all.sample(50_000, random_state=7)
    out, preds = fit_models(
        tr_all[cat], tr_all["no_visit"].values,
        va_all[cat], va_all["no_visit"].values,
        te[cat], te["no_visit"].values,
        num, cat, "brfss_no_visit",
        {"income_band": te["income_band"], "coverage": te["hlthpln"],
         "race_ethnicity": te["race"]})
    out["design"] = {**design, "n_train_subsampled": int(len(tr_all)),
                     "n_validation": int(len(va_all)),
                     "n_test": int(len(te)),
                     "features_numeric": num, "features_categorical": cat}
    (RES / "metrics_brfss_no_visit.json").write_text(
        json.dumps(out, indent=2, default=str))
    te_out = te[["year", "state", "sex", "race", "income_band", "hlthpln",
                 "no_visit"]].copy()
    te_out["p_logistic"] = preds["logistic"][1]
    te_out["p_hgb"] = preds["hgb"][1]
    te_out.to_csv(RES / "test_predictions_brfss_no_visit.csv", index=False)
    return df


# ---------------------------------------------------------------- state rates
def state_rates():
    nohss = pd.read_csv(HARM / "nohss_state.csv")
    rows = []
    brfss_path = HARM / "brfss.csv"
    brfss_state = None
    if brfss_path.exists():
        b = pd.read_csv(brfss_path)
        brfss_state = (b.groupby(["year", "state"])["no_visit"]
                       .agg(["mean", "size"]).reset_index()
                       .rename(columns={"mean": "brfss_no_visit_rate",
                                        "size": "brfss_n"}))
        brfss_state["brfss_visit_rate"] = 1 - brfss_state["brfss_no_visit_rate"]
    noh = nohss.rename(columns={"visit_rate": "nohss_visit_rate"})
    if brfss_state is not None:
        merged = brfss_state.merge(noh, on=["year", "state"], how="outer")
    else:
        merged = noh
    # Mississippi 2022 flag: BRFSS no-visit 91.3% vs 42.6% in MS 2020,
    # while every other state moved <=4 points 2020->2022, and within
    # MS 2022 the LASTDEN4=1 share is 1-5% in Jan and May-Dec but
    # 28-58% in Feb-Apr — a source-file fielding/processing artifact,
    # not a real access collapse (CDC's own _DENVST3 agrees with
    # LASTDEN4, so it is in the released file). Flagged, not deleted:
    # kept in the BRFSS model test set (4,129 of 438,111 rows) but
    # excluded from the state ranking/choropleth.
    merged["flag"] = ""
    ms = (merged["state"] == "MS") & (merged["year"] == 2022)
    merged.loc[ms, "flag"] = ("MS-2022 LASTDEN4 anomaly: no-visit 91.3% "
                              "vs 42.6% in 2020; see DATA.md")
    merged.to_csv(RES / "state_rates.csv", index=False)
    info = {"n_state_years": int(len(merged)),
            "nohss_years": sorted(noh["year"].unique().tolist())}
    common = merged.dropna(subset=["brfss_visit_rate", "nohss_visit_rate"])
    if len(common) >= 10:
        info["brfss_vs_nohss_corr"] = float(
            np.corrcoef(common["brfss_visit_rate"],
                        common["nohss_visit_rate"])[0, 1])
        info["brfss_vs_nohss_n_states"] = int(len(common))
        info["brfss_vs_nohss_years"] = sorted(common["year"].unique().tolist())
        info["mean_abs_diff"] = float(
            (common["brfss_visit_rate"] - common["nohss_visit_rate"]).abs().mean())
    if brfss_state is not None:
        latest = brfss_state[brfss_state["year"] == brfss_state["year"].max()]
        # Flagged state-years (MS 2022 anomaly) are excluded from the
        # ranking; the flag and the raw value stay in state_rates.csv.
        flagged = merged[(merged["year"] == latest["year"].iloc[0])
                         & (merged["flag"] != "")]
        latest = latest[~latest["state"].isin(flagged["state"])]
        srt = latest.sort_values("brfss_no_visit_rate")
        info["brfss_latest_year"] = int(latest["year"].iloc[0])
        info["lowest_no_visit_states"] = [
            (r.state, round(float(r.brfss_no_visit_rate), 3))
            for r in srt.head(5).itertuples()]
        info["highest_no_visit_states"] = [
            (r.state, round(float(r.brfss_no_visit_rate), 3))
            for r in srt.tail(5).itertuples()]
        info["flagged_excluded_from_ranking"] = [
            (r.state, int(r.year), round(float(r.brfss_no_visit_rate), 3),
             r.flag) for r in flagged.itertuples()]
    (RES / "state_rates.json").write_text(json.dumps(info, indent=2))
    print("state rates:", json.dumps(info, indent=2))


def main():
    run_meps()
    run_brfss()
    state_rates()
    print("done.")


if __name__ == "__main__":
    main()
