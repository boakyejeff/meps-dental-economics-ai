# Who skips the dentist, and who pays $1,000+ out of pocket? MEPS + BRFSS dental economics, 2018–2022

Can foregone dental care and high out-of-pocket dental spending be predicted
from socioeconomic status, insurance and geography — with no clinical data at
all — and does the prediction hold up years later, equally across groups, and
across two different national surveys? MEPS (panel, event-recorded) + BRFSS
(cross-sectional, recall) + NOHSS state rates, temporal validation, fairness
audit, state choropleth.

## Question

Three outcomes, SES/insurance/geography predictors only:

1. **No dental visit in the year** (MEPS, adults 18+, 2018–2022) — `DVTOTyy == 0`.
2. **High out-of-pocket dental spending** (MEPS, adults 18+, 2018–2022) —
   `DVTSLFyy >= $1,000` (4.4% pooled; the $1,000 threshold was chosen by the
   rule in `src/harmonise.py`: $1,000 if it gives ≥3% prevalence, else the
   90th percentile of OOP among spenders).
3. **No dental visit in the past year** (BRFSS, adults 18+, 2020 → 2022) —
   `LASTDEN4 != 1`, with a state-level geospatial angle anchored to NOHSS.

Note on what "foregone care" means here: the direct MEPS items for being
unable to get / delaying needed dental care (`DNUNAB42` / `DNDLAY42`) are
**absent from every FYC file 2018–2022** (checked in the codebook and by
column scan), so "no visit in the year" is the foregone-care proxy, with
`AFRDDN42` (could not afford dental care) reported descriptively. See
[DATA.md](DATA.md).

## Datasets

See [DATA.md](DATA.md). In short: AHRQ MEPS Full Year Consolidated files
2018–2022 (HC-209/216/224/233/243) plus Dental Visits event files, as Stata
`.dta.zip` (the `.ssp.zip` files are SAS CPORT, not XPT — see DATA.md);
CDC BRFSS LLCP XPT files 2020 + 2022 (fetched via the Wayback Machine's
archived copies of the official CDC URLs, because direct CDC access is
403-blocked from this box); CDC NOHSS state indicators via the Socrata API
(`jz6n-v26y`). Raw files in `data/raw/` (gitignored).

Analytic samples actually achieved: **103,194** MEPS adults 18+ (no-visit
59.2% pooled; high-OOP 4.4%); **835,402** BRFSS adults 18+ (no-visit 32.8%
in 2020, 33.3% in 2022); **266** NOHSS state-year rows (2012–2020).
MEPS no-visit prevalence by year: 58.6% (2018), 57.5% (2019), **63.6%
(2020, COVID year)**, 59.4% (2021), 56.7% (2022). Could not afford dental
care: 12.4%, 12.5%, 10.2%, 8.7%, 9.9% over the same years.

## What is novel here

1. **Temporal validation as the headline**, not a random split: MEPS models
   train on 2018–2020, validate on 2021, test on 2022; BRFSS models train on
   2020 and test on 2022.
2. **Economics, not diagnosis** — the predictors are SES, insurance,
   employment, education and geography; the outcomes are utilisation and
   spending. The manuscript is framed around access and affordability, not
   clinical disease.
3. **Two surveys, one concept, different answers**: MEPS says 57–64% of
   adults had no dental visit; BRFSS says ~33%. The gap (event records vs
   12-month recall) is reported as a finding, not hidden.
4. **State geospatial angle with an independent cross-check**: BRFSS state
   rates vs NOHSS state rates for 2020 agree at r = 0.955 (mean absolute
   difference 1.7 pp, 53 states). Mississippi 2022 (91.3%) is a documented
   source-data anomaly, flagged and excluded from the ranking — not silently
   dropped, not silently kept.
5. **Fairness audit** on the test set by poverty/income band, insurance and
   race/ethnicity — reported as findings, including where the models fail a
   group.
6. **Calibration reported honestly** (ECE + curves), including a severely
   miscalibrated model — not hidden behind AUC.

## Pipeline

```
src/download_meps.py    MEPS FYC + Dental Visits .dta.zip -> data/raw/, results/download_log.json
src/download_brfss.py   BRFSS LLCP XPT (CDC -> Wayback fallback) -> data/raw/, results/download_log_brfss.json
src/download_nohss.py   NOHSS Socrata API jz6n-v26y -> data/raw/nohss_adult_dental_visit.csv
src/harmonise.py        harmonisation, outcome definitions, event-file cross-check
                        -> data/harmonised/{meps,brfss,nohss_state}.csv, results/harmonisation.json
src/train.py            logistic regression + HistGradientBoosting, temporal splits,
                        validation-split Youden thresholds, fairness audit, state rates
                        -> results/metrics_{meps_no_visit,meps_high_oop,brfss_no_visit}.json,
                           lr_coefficients_*.json, hgb_importance_*.json,
                           test_predictions_*.csv, results/state_rates.{csv,json}
src/figures.py          ROC + calibration curves, state choropleth + ranked bars,
                        MEPS yearly prevalence -> results/figures/*.png
```

## Reproduce

```bash
# 1. Download (public-use, no login; MEPS ~10 zips, BRFSS ~152 MB, NOHSS API)
python3 src/download_meps.py
python3 src/download_brfss.py
python3 src/download_nohss.py
# 2. Harmonise (CPU, ~1.5 min — BRFSS XPT reads are the slow part)
~/workspace/venvs/crop-disease/bin/python src/harmonise.py
# 3. Train + evaluate (CPU-only box, ~2.5 min; BRFSS HGB on a 150k subsample)
~/workspace/venvs/crop-disease/bin/python src/train.py
# 4. Figures
~/workspace/venvs/crop-disease/bin/python src/figures.py
```

Environment: Python 3.12, pandas 3.0.6, scikit-learn 1.9.1
(`~/workspace/venvs/crop-disease`). No GPU needed; no GPU used. No survey
weights (prediction, not population estimation — see DATA.md). BRFSS
training rows are subsampled to 150,000 (documented in
`results/metrics_brfss_no_visit.json`); the test set is the full 2022 file
(438,111 rows).

## Results (actual runs on this box, 2026-11-07 — no invented metrics)

### No dental visit — MEPS, temporal test 2022 (n=17,387, prev 56.7%)

Full files: `results/metrics_meps_no_visit.json`,
`results/figures/roc_meps_no_visit.png`,
`results/figures/calibration_meps_no_visit.png`.

| Model | AUC | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.747 | 0.656 / 0.717 | 0.683 | 0.062 | 0.206 |
| HistGradientBoosting | **0.753** | 0.671 / 0.711 | 0.688 | 0.058 | 0.202 |

Validation (2021): LR AUC 0.745, HGB 0.756 — ranking transfers across time
with almost no loss, and both models are reasonably calibrated (ECE
0.058–0.062). At the validation-Youden threshold (LR 0.507, HGB 0.495) the
numbers barely move (LR 0.646/0.728, HGB 0.676/0.705), so the 0.5 threshold
is near-optimal here. Top drivers: being uninsured (LR coef +0.59), lower
education (GED +0.30, no degree +0.17; Master's+ −0.32), NH White −0.36,
high income −0.29, South region +0.19. HGB permutation importance is led by
years of education (0.037 AUC drop), poverty level (0.025) and age (0.022).

### High out-of-pocket dental spending (≥$1,000) — MEPS, temporal test 2022 (n=17,387, prev 5.0%)

Full files: `results/metrics_meps_high_oop.json`,
`results/figures/roc_meps_high_oop.png`,
`results/figures/calibration_meps_high_oop.png`.

| Model | AUC | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.697 | 0.680 / 0.617 | 0.620 | **0.393** | 0.226 |
| HistGradientBoosting | **0.711** | 0.628 / 0.677 | 0.674 | **0.370** | 0.210 |

Validation (2021): LR AUC 0.712, HGB 0.718 — ranking transfers, but both
models are **severely miscalibrated** (ECE 0.370–0.393 on test, 0.366–0.391
on validation): balanced class weights against a 5.0% prevalence push
predicted risks far above observed frequencies. As probability tools these
are not usable without recalibration; as ranking tools (AUC ~0.70–0.71)
they are modest. The economics is in the direction of the coefficients:
high OOP is concentrated among **older, higher-income, NH White, privately
insured** adults (age +0.50, high income +0.28, NH White +0.38, any private
+0.18; Poor −0.41, NH Black −0.35, public only −0.28) — i.e. high OOP marks
people who actually receive expensive care and can pay for it, while poor
and uninsured adults rarely reach $1,000 OOP because they do not get care
at all. Age dominates HGB importance (0.102 AUC drop), then poverty level
(0.024) and education (0.019).

### No dental visit — BRFSS, temporal test 2022 (n=438,111, prev 33.3%)

Full files: `results/metrics_brfss_no_visit.json`,
`results/figures/roc_brfss_no_visit.png`,
`results/figures/calibration_brfss_no_visit.png`.

| Model | AUC | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.692 | 0.542 / 0.730 | 0.667 | 0.124 | 0.215 |
| HistGradientBoosting | **0.699** | 0.577 / 0.706 | 0.663 | 0.121 | 0.213 |

Validation (50k held out of 2020): LR AUC 0.693, HGB 0.704 — ranking
transfers across years. Both models are moderately miscalibrated
(ECE ~0.12), again a cost of the balanced class weights on coarse
categorical features. Top drivers: less than high-school education (+0.68),
income <$25k (+0.58), no coverage (+0.47), college graduation (−0.56),
income $75k+ (−0.32); state effects are visible in the coefficients
(Hawaii −0.51, Kentucky +0.39, Rhode Island −0.37, Texas +0.34).
HGB importance is led by age 65+ (0.059) and female sex (0.057).

### State variation (BRFSS 2022, unweighted; Mississippi excluded — see DATA.md)

Full files: `results/state_rates.csv`, `results/state_rates.json`,
`results/figures/state_choropleth_brfss.png`,
`results/figures/state_ranked_brfss.png`.

Lowest no-visit rates: Connecticut 25.5%, Rhode Island 26.0%, Vermont
26.6%, Massachusetts 26.9%, New Hampshire 27.1%. Highest: Arkansas 41.9%,
U.S. Virgin Islands 41.0%, West Virginia 40.7%, Texas 40.7%, Kentucky
40.4% — a 16.4-point spread from best to worst state. The pattern is
geographic: the Northeast is lightest, the South/Appalachia darkest.
BRFSS vs NOHSS state visit rates for 2020 agree at r = 0.955 (mean absolute
difference 1.7 pp, 53 states). Mississippi 2022 reads 91.3% — a documented
source-data anomaly (42.6% in MS 2020; every other state moved ≤4 points),
flagged and excluded from the ranking and choropleth.

### Fairness audit (test set, @0.5 threshold)

- **MEPS no-visit:** prevalence itself is the gradient — Poor 76.1% vs
  High income 40.4%; Uninsured 88.8% vs Any private 47.9%; Hispanic 73.7%
  and NH Black 70.8% vs NH White 46.9%. Ranking is near-equal (LR AUC
  0.657–0.729 across groups) but the fixed 0.5 threshold is not:
  sensitivity is 0.939 for Poor vs 0.247 for High income (LR), and 0.992
  for Uninsured vs 0.457 for Any private — the same threshold screens the
  poorest and uninsured aggressively and the richest weakly, mostly tracking
  prevalence. NH Asian has the lowest AUC (0.660 LR / 0.656 HGB).
- **MEPS high-OOP:** the model fails a group outright. At 0.5, LR
  sensitivity collapses to 0.157 for NH Black, 0.220 for Hispanic, 0.071
  for NH Other/multiple and 0.103 for Uninsured, against 0.828 for NH
  White and 0.802 for High income — because high-OOP prevalence in those
  groups is only 2.1–3.3% (vs 6.5% NH White, 7.2% High income) and the
  model has almost nothing to learn from. AUC ranges 0.607–0.751 (HGB).
  This is a finding about the outcome definition, not just the model:
  $1,000 OOP is a marker of receiving expensive care, which is itself
  unequally distributed.
- **BRFSS no-visit:** same threshold pattern at larger scale — sensitivity
  0.956 for income <$25k vs 0.192 for $75k+ (LR), and 0.961 for No coverage
  vs 0.492 for Insured. Ranking gaps are modest (LR AUC 0.594 for No
  coverage vs 0.679 Insured; 0.602 for <$25k vs 0.634 for $75k+;
  0.627 AI/AN vs 0.696 NH White). A single threshold cannot serve all
  groups here.

## Run notes (what went wrong, fixed or documented)

- MEPS `.ssp.zip` files are SAS CPORT, not XPORT — switched to `.dta.zip`.
- Direct CDC BRFSS downloads are 403-blocked from this box — fetched via
  Wayback Machine copies of the exact CDC URLs (byte-identical sizes);
  2020 needed 4 attempts (Wayback 429s).
- BRFSS variable names differ by year and from common assumptions:
  `LASTDEN4` (not `LASTDEN3`); income is `INCOME2` in 2020, `INCOME3` in
  2022; coverage is `HLTHPLN1` in 2020, `PRIMINSR` in 2022, where 88 (not
  8) means no coverage; race is `_RACE` in 2020, `_RACE1` in 2022. Each was
  verified against the actual files/codebooks, not assumed.
- The pandas `"None"` NA trap: the string `"None"` is a default NA value,
  so the coverage label is `"No coverage"` and the NOHSS "Overall" filter
  accepts both NaN and the literal `"None"`.
- The 2022 XPT member name has a trailing space (`LLCP2022.XPT `).
- ECE was 0.000 for every model in the first run because of a bin-edge bug
  (`edges[i]` used as both bounds); fixed and sanity-checked on synthetic
  miscalibrated data (ECE 0.2209).
- `OneHotEncoder` default sparse output is rejected by
  HistGradientBoosting — fixed with `sparse_output=False`.
- NOHSS `data_value` is a percent (0–100); an early state-rates run compared
  it directly with BRFSS proportions (mean abs diff 64.7) — fixed by
  dividing by 100 (now 1.7 pp).
- Mississippi 2022 BRFSS (91.3% no-visit) is a source-data anomaly —
  documented in DATA.md, flagged in `state_rates.csv`, excluded from the
  ranking/choropleth, kept in the model test set.

## Limitations

- Unweighted throughout (prediction, not population estimation); rates are
  sample rates, not population estimates.
- MEPS has no public state identifier — the state angle is BRFSS/NOHSS
  only; MEPS contributes region, not state.
- The MEPS–BRFSS prevalence gap (57–64% vs ~33%) is a measurement
  difference (event records vs 12-month recall), not a contradiction to be
  averaged away.
- High-OOP models are severely miscalibrated (ECE 0.37–0.39) and the
  high-OOP outcome is itself a marker of receiving expensive care, so it
  should not be read as a pure "burden" measure.
- BRFSS training is a 150k subsample of 2020 (CPU time); the test set is
  the full 2022 file.
- NOHSS has no 2022 in this dataset snapshot, so the BRFSS–NOHSS
  cross-check is for 2020 only.
