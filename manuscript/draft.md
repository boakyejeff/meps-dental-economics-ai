# Who skips the dentist, and who pays $1,000+ out of pocket? Predicting foregone dental care and high out-of-pocket dental spending from socioeconomic status, insurance and geography in the United States, 2018–2022

**Draft, parked, not submitted.** All numbers below are read back from the
result files in `results/` (run 2026-11-07 on this box). No placeholders, no
invented numbers.

## Abstract

**Objectives.** To test whether foregone dental care and high out-of-pocket (OOP) spending can be predicted from socioeconomic status, insurance and geography, and whether it holds years later and equally across groups.

**Methods.** MEPS 2018–2022 (n=103,194) and BRFSS 2020 + 2022 (n=835,402), with NOHSS state indicators as a cross-check. Outcomes: no dental visit (MEPS); high OOP spending ≥$1,000 (MEPS); no dental visit in the past year (BRFSS). Logistic regression and gradient boosting trained on earlier years were tested on the latest year. Evaluation used AUC, sensitivity, specificity and calibration (ECE), with a fairness audit by income, insurance and race/ethnicity.

**Results.** MEPS no-visit prevalence was 59.2% pooled (63.6% in 2020); the could-not-afford share fell from 12.4% to 8.7% (2021) and 9.9% (2022). On the 2022 test set (n=17,387), no-visit models reached AUC 0.747 (logistic, 95% CI 0.739–0.754) and 0.753 (boosting, 0.746–0.760); high-OOP models reached 0.697 (0.680–0.714) and 0.711 (0.693–0.728) but were severely miscalibrated (ECE 0.393 and 0.370). BRFSS no-visit models on the 2022 test set (n=438,111) reached 0.692 (0.690–0.693) and 0.699 (0.697–0.700). BRFSS 2022 state rates ranged from 25.5% (Connecticut) to 41.9% (Arkansas).

**Conclusions.** Foregone dental care is predictable from economics alone (AUC ~0.69–0.75), but one threshold cannot serve all groups: sensitivity at 0.5 ranged from 0.19 to 0.96 across income groups in BRFSS. High OOP spending marks receipt of expensive care, not burden. The two surveys disagree by 24 to 31 points on foregone care, so any policy number must name its source.

**Keywords:** dental care utilization; health care costs; socioeconomic factors; health equity; Medicaid.

## Introduction

Dental care is the most commonly forgone type of health care in the United States, and it is the service most often paid for out of pocket [1]. Unlike
most medical care, adult dental coverage is frequently absent from health
insurance: Medicare does not cover routine dental care [2], Medicaid adult dental benefits vary by state and are often minimal [3], and about one in four adults lacks dental benefits [4]. The result is a service where
access is rationed by ability to pay, and where the financial consequences
of getting care can themselves be large, a single crown or implant can cost thousands of dollars out of pocket [2].

This paper asks an economics question, not a clinical one. It asks three
questions. First, can we predict who will have no dental visit in a year
from SES, insurance, employment, education and geography alone, that is,
from the variables a payer, a state Medicaid program or a safety-net clinic
already has? Second, can we predict who will spend $1,000 or more out of
pocket on dental care, and what does that outcome actually mark, burden,
or access to expensive care? Third, how much does foregone care vary by
state, and do two independent extractions of the same underlying survey
agree on that variation?

We use two national surveys because they measure the same concept differently. MEPS is a panel survey that
records dental **events** in a calendar year; BRFSS is a cross-sectional
telephone survey that asks for **12-month recall** of the last dental
visit. If both are used naively, they give different answers, and this
paper reports that difference as a finding rather than averaging it away.

## Methods

### Data sources

**MEPS (AHRQ).** Full Year Consolidated Data Files 2018–2022 (HC-209, HC-216, HC-224, HC-233, HC-243) [5,6] and Dental Visits event files (HC-206B, HC-213B, HC-220B, HC-229B, HC-239B) [5], public-use, no login. Analytic sample:
adults 18+ with a positive full-year weight (`PERWTyyF > 0`), n = 103,194
pooled (22,036 in 2018; 21,080 in 2019; 20,923 in 2020; 21,768 in 2021;
17,387 in 2022). Full variable provenance, including the codebook-verified
variable names, is in DATA.md.

**BRFSS (CDC).** Annual LLCP (combined landline + cellular) XPT files [7,8], 2020 and 2022 (oral-health items are asked in even years only). Analytic
sample: adults 18+ with a valid `LASTDEN4` response, n = 397,291 (2020,
53 states) and n = 438,111 (2022, 54 states). Direct CDC downloads are
403-blocked from our environment, so the files were fetched from the
Wayback Machine's archived copies of the exact official CDC URLs
(byte-identical to the CDC Content-Length); see DATA.md.

**NOHSS (CDC).** National Oral Health Surveillance System [9,10] state indicators via the Socrata API (dataset `jz6n-v26y`), indicator "Adults aged 18+ who
have visited a dentist or dental clinic in the past year" (ADT1_1, crude
prevalence, BRFSS source): 266 state-year rows, years 2012, 2014, 2016,
2018, 2020 (no 2022 in this dataset snapshot), 54 locations.

**US states GeoJSON** (PublicaMundi/MappingAPI) for the choropleth,
drawn as hand-plotted matplotlib polygons (no geopandas available).

### Outcome definitions

- **No dental visit (MEPS):** `DVTOTyy == 0` in the calendar year.
  Pooled prevalence 59.2%.
- **High out-of-pocket dental spending (MEPS):** `DVTSLFyy >= $1,000`.
  Threshold rule: $1,000 if it gives ≥3% prevalence among adults, else the
  90th percentile of OOP among adults with any dental expenditure, rounded
  to $50. Pooled prevalence at $1,000 was 4.4%, so the threshold is $1,000
  (by year: 4.2%, 4.3%, 3.7%, 4.9%, 5.0%).
- **No dental visit in the past year (BRFSS):** `LASTDEN4 != 1` among
  valid responses {1, 2, 3, 4, 8}. Prevalence 32.8% (2020), 33.3% (2022).
  CDC's own calculated variable `_DENVST3` agrees with this derivation at
  1.0000 in both years.
- **Could not afford dental care (MEPS, `AFRDDN42`):** descriptive only,
  not a model feature (near-tautological as a predictor of foregone care).

A note on what is not available: the direct MEPS items for being unable to
get or delaying needed dental care (`DNUNAB42` / `DNDLAY42`) are **absent
from every FYC file 2018–2022** (checked in the HC-243 codebook and by
column scan of all five files), so "no visit in the year" is the
foregone-care proxy. MEPS public-use files also have **no state
identifier** (restricted data only); the state angle is BRFSS/NOHSS only,
and MEPS contributes census region. Total medical expenditure
(`TOTEXPyy`) was excluded as a predictor because it contains dental
spending and would leak the expenditure outcome.

### Predictors

MEPS: age, sex, race/ethnicity (`RACETHX`), census region, insurance
coverage (`INSCOVyy`), dental insurance (`DENTIN42`), poverty category and
poverty level (`POVCATyy`, `POVLEVyy`), years of education and highest
degree (`EDUCYR`, `HIDEG`, collapsed), employment (`EMPST53`, collapsed to
Employed / Not employed), perceived physical and mental health
(`RTHLTH53`, `MNHLTH53`). BRFSS: age band, sex, race/ethnicity, education
band, income band, employment band, coverage (Insured / No coverage) and
state. All categorical variables are one-hot encoded; one-hot encoding retained all levels (no reference level dropped), so each coefficient is a level indicator rather than a contrast against a reference category. Numeric variables are standardized for the logistic model only. MEPS models use 5 numeric features (age, educyr, povlev, health_num, mhealth_num) and 8 categorical features (sex, race, region, inscov, povcat, dental_ins, hideg_collapsed, employed); BRFSS models use 8 categorical features (age_band, sex, race, edu_band, income_band, employ_band, hlthpln, state). Missing values are imputed with
the training-set median (numeric) or most frequent category
(categorical); a missing-indicator column is added for any feature with
>1% missing in training.

### Models and validation

Two models per outcome: logistic regression (interpretable baseline; balanced class weights, C = 1.0) and HistGradientBoostingClassifier [11] (300 iterations, learning rate 0.06, balanced class weights). Validation
is **temporal**: MEPS models train on 2018–2020 (n = 64,039), validate on
2021 (n = 21,768) and test on 2022 (n = 17,387); BRFSS models train on
2020 (subsampled to 150,000 rows for CPU time) and test on the full 2022
file (n = 438,111), with a 50,000-row hold-out from 2020 as the
validation set. The decision threshold is chosen on the validation set by Youden's J [12] and reported alongside the conventional 0.5 threshold. No survey weights are used (prediction, not population estimation) [13], so all rates reported are unweighted sample rates.

### Evaluation and fairness audit

Test-set AUC [14], accuracy, sensitivity, specificity, Brier score [15] and ECE [16] (10 equal-width bins) at the 0.5 and validation-Youden thresholds. Permutation importance was computed on a random 5,000-row subsample of the test set with 3 repeats (ROC AUC scoring). The fairness audit reports AUC, sensitivity, specificity and outcome prevalence on the test set, stratified by poverty/income band, insurance status and race/ethnicity [17]. State rates are unweighted BRFSS proportions
with NOHSS as an independent cross-check (Pearson r and mean absolute
difference for the overlapping year, 2020, 53 states). All code is in
`src/`; all metrics in `results/metrics_*.json`.

## Results

### Sample description

MEPS adults 18+ (n = 103,194 pooled) had a no-visit prevalence of 59.2%
and a high-OOP (≥$1,000) prevalence of 4.4%. No-visit prevalence rose from 58.6% (2018) and 57.5% (2019) to 63.6% in the COVID year 2020 [18], then fell to 59.4% (2021) and 56.7% (2022) (Figure 1). The share saying they could not
afford dental care fell over the same period, from 12.4% (2018) and 12.5%
(2019) to 10.2% (2020), 8.7% (2021) and 9.9% (2022). Median OOP spending
among adults with any dental spending was $65–$80 across years; the 90th
percentile among spenders was $1,001.60–$1,257.00. BRFSS adults 18+ (n = 835,402 pooled) had a no-visit prevalence of 32.8% (2020) and 33.3% (2022). Affordability and visiting moved in opposite directions: the could-not-afford share fell to 8.7% in 2021 while no-visit prevalence rose to 63.6% in 2020.

The MEPS Dental Visits event files corroborate the FYC totals: per-person
event sums match the FYC visit counts exactly in every year (1.000), OOP amounts match in 97.3–99.7% of cases, and total expenditure in 82.3–95.9% (lower in later years, consistent with flat-fee allocation differences documented by MEPS [5]); the correlation between event-file and FYC total expenditure is approximately 1.000 in all five years.

**Figure 1.** Yearly prevalence, MEPS 2018–2022: no dental visit, high out-of-pocket spending ≥$1,000, and the share saying they could not afford dental care (n=103,194 pooled).

### No dental visit, MEPS (test 2022, n = 17,387, prevalence 56.7%)

**Table 1.** No dental visit, MEPS, test 2022 (n=17,387, prevalence 56.7%). AUC with 95% percentile-bootstrap confidence interval (2,000 resamples); sensitivity/specificity at 0.5.

| Model | AUC (95% CI) | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.747 (0.739-0.754) | 0.656 / 0.717 | 0.683 | 0.062 | 0.206 |
| HistGradientBoosting | 0.753 (0.746-0.760) | 0.671 / 0.711 | 0.688 | 0.058 | 0.202 |

Validation (2021) AUC was 0.745 (logistic) and 0.756 (boosting) (Table 1, Figure 2), so ranking transfers across time with almost no loss, and both models are reasonably calibrated (ECE 0.058–0.062) (Figure 3). At the validation-Youden threshold (0.507
logistic, 0.495 boosting) sensitivity/specificity were 0.646/0.728 and
0.676/0.705, barely different from 0.5, so the 0.5 threshold is
near-optimal for this outcome. The largest logistic coefficients: being
uninsured (+0.59), GED (+0.30) and no degree (+0.17) vs Master's+ (−0.32),
NH White (−0.36), high income (−0.29), any private insurance (−0.30),
South region (+0.19), male sex (+0.24), no dental insurance (+0.22).
Boosting permutation importance is led by years of education (0.037 AUC
drop), poverty level (0.025) and age (0.022).

**Figure 2.** ROC curves, MEPS no-visit model, test 2022 (n=17,387, prevalence 56.7%). Logistic regression AUC 0.747 (95% CI 0.739–0.754); gradient boosting AUC 0.753 (0.746–0.760).

**Figure 3.** Calibration curves, MEPS no-visit model, test 2022 (n=17,387, prevalence 56.7%). Both models are reasonably calibrated (ECE 0.062 logistic, 0.058 boosting).

### High out-of-pocket dental spending, MEPS (test 2022, n = 17,387, prevalence 5.0%)

**Table 2.** High out-of-pocket dental spending (≥$1,000), MEPS, test 2022 (n=17,387, prevalence 5.0%). AUC with 95% percentile-bootstrap confidence interval (2,000 resamples); sensitivity/specificity at 0.5.

| Model | AUC (95% CI) | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.697 (0.680-0.714) | 0.680 / 0.617 | 0.620 | 0.393 | 0.226 |
| HistGradientBoosting | 0.711 (0.693-0.728) | 0.628 / 0.677 | 0.674 | 0.370 | 0.210 |

Validation (2021) AUC was 0.712 (logistic) and 0.718 (boosting) (Table 2, Figure 4), ranking transfers, but both models are **severely miscalibrated** (ECE 0.370–0.393 on test, 0.366–0.391 on validation) (Figure 5): balanced class weights against a 5.0% prevalence are consistent with predicted risks running far above observed frequencies. No unweighted control run was fitted, so this mechanism is inferred, not tested. As
probability tools these models are not usable without recalibration; as
ranking tools (AUC ~0.70–0.71) they are modest. The coefficients run in
the opposite direction to the no-visit model: high OOP is concentrated
among older (+0.50 for age), higher-income (+0.28), NH White (+0.38),
privately insured (+0.18) adults, and away from Poor (−0.41), NH Black
(−0.35) and public-only (−0.28) adults. Age dominates boosting importance
(0.102 AUC drop), then poverty level (0.024) and education (0.019).

**Figure 4.** ROC curves, MEPS high-OOP model, test 2022 (n=17,387, prevalence 5.0%). Logistic regression AUC 0.697 (95% CI 0.680–0.714); gradient boosting AUC 0.711 (0.693–0.728).

**Figure 5.** Calibration curves, MEPS high-OOP model, test 2022 (n=17,387, prevalence 5.0%). Both models severely overestimate risk (ECE 0.393 logistic, 0.370 boosting).

### No dental visit, BRFSS (test 2022, n = 438,111, prevalence 33.3%)

**Table 3.** No dental visit, BRFSS, test 2022 (n=438,111, prevalence 33.3%). AUC with 95% percentile-bootstrap confidence interval (500 resamples); sensitivity/specificity at 0.5.

| Model | AUC (95% CI) | Sens / spec @0.5 | Accuracy | ECE | Brier |
|---|---|---|---|---|---|
| Logistic regression | 0.692 (0.690-0.693) | 0.542 / 0.730 | 0.667 | 0.124 | 0.215 |
| HistGradientBoosting | 0.699 (0.697-0.700) | 0.577 / 0.706 | 0.663 | 0.121 | 0.213 |

Validation (50k held out of 2020) AUC was 0.693 (logistic) and 0.704 (boosting) (Table 3, Figure 6). Both models are moderately miscalibrated (ECE ~0.12) (Figure 7), again consistent with the balanced class weights on coarse categorical features. No unweighted control run was fitted, so this mechanism is inferred, not tested. The
largest logistic coefficients: less than high-school education (+0.68),
income <$25k (+0.58), no coverage (+0.47), college graduation (−0.56),
income $75k+ (−0.32), male sex (+0.27). State effects are visible in the
coefficients (Hawaii −0.51, Kentucky +0.39, Rhode Island −0.37, Texas
+0.34). Boosting importance is led by age 65+ (0.059) and female sex
(0.057).

**Figure 6.** ROC curves, BRFSS no-visit model, test 2022 (n=438,111, prevalence 33.3%). Logistic regression AUC 0.692 (95% CI 0.690–0.693); gradient boosting AUC 0.699 (0.697–0.700).

**Figure 7.** Calibration curves, BRFSS no-visit model, test 2022 (n=438,111, prevalence 33.3%). Both models are moderately miscalibrated (ECE 0.124 logistic, 0.121 boosting).

### State variation

In BRFSS 2022 (unweighted), the lowest no-visit rates were Connecticut
25.5%, Rhode Island 26.0%, Vermont 26.6%, Massachusetts 26.9% and New
Hampshire 27.1%; the highest were Arkansas 41.9%, U.S. Virgin Islands
41.0%, West Virginia 40.7%, Texas 40.7% and Kentucky 40.4%, a 16.4-point
spread from best to worst state, with the Northeast lightest and the
South/Appalachia darkest (Figures 8 and 9). The BRFSS state rates are corroborated by
NOHSS: for 2020, the one overlapping year, the two sources agree at
Pearson r = 0.955 with a mean absolute difference of 1.7 percentage points
across 53 states.

**Figure 8.** BRFSS 2022 no-visit rate by state (unweighted, n=438,111). Mississippi excluded (91.3% reading, documented source-data anomaly). Darker shades mean higher foregone-care rates.

**Figure 9.** States ranked by BRFSS 2022 no-visit rate (unweighted). Mississippi excluded (91.3% reading, documented source-data anomaly).

Mississippi 2022 reads 91.3% in BRFSS, against 42.6% in MS 2020, while
every other state moved ≤4.0 points between 2020 and 2022. In the raw 2022
file, 2,254 of 4,239 Mississippi respondents are coded `LASTDEN4 = 2`
("within past 2 years") and only 361 `LASTDEN4 = 1`; within the year the
`LASTDEN4 = 1` share is 1–5% in January and May–December but 28–58% in
February–April. This is a fielding/processing artifact in the released
file, not a real access collapse (CDC's own `_DENVST3` reproduces the same values, so the anomaly sits in the released file, not in our derivation). Mississippi 2022 is therefore flagged in `results/state_rates.csv` and excluded from the state ranking and choropleth, but kept in the BRFSS model test set, where it makes up 4,129 of 438,111 rows (0.9%).

### Fairness audit (test set, 0.5 threshold)

**MEPS no-visit.** Prevalence is itself the gradient: Poor 76.1% vs High
income 40.4%; Uninsured 88.8% vs Any private 47.9%; Hispanic 73.7% and NH
Black 70.8% vs NH White 46.9%. Ranking is near-equal across groups (logistic AUC 0.657–0.729; Poor lowest at 0.657), but the fixed 0.5 threshold is not: sensitivity is 0.939 for Poor vs 0.247 for High income,
and 0.992 for Uninsured vs 0.457 for Any private. The same threshold flags the poorest and uninsured far more often than the richest, mostly tracking prevalence.

**MEPS high-OOP.** The model fails a group outright. At 0.5, logistic
sensitivity collapses to 0.157 for NH Black, 0.220 for Hispanic, 0.071 for
NH Other/multiple and 0.103 for Uninsured, against 0.828 for NH White and
0.802 for High income, because high-OOP prevalence in those groups is
only 2.1–3.3% (vs 6.5% NH White, 7.2% High income) and the model has
almost nothing to learn from. AUC ranges 0.607–0.751 (boosting). This is
a finding about the outcome definition, not just the model: $1,000 OOP is
a marker of receiving expensive care, which is itself unequally
distributed.

**BRFSS no-visit.** The same threshold pattern at larger scale:
sensitivity 0.956 for income <$25k vs 0.192 for $75k+ (logistic), and
0.961 for No coverage vs 0.492 for Insured. Ranking gaps are modest
(logistic AUC 0.594 for No coverage vs 0.679 Insured; 0.602 for <$25k vs
0.634 for $75k+; 0.627 AI/AN vs 0.696 NH White). A single threshold cannot
serve all groups here.

## Discussion

Three findings stand out. **First, foregone dental care is predictable
from economics alone, but only modestly.** AUC 0.69–0.75 from SES,
insurance and geography is well above chance and stable across years, but
it is not a screening tool: at the MEPS no-visit Youden threshold (0.507), 35% of non-visitors are missed and 27% of visitors are flagged. The value is descriptive, not operational: it quantifies how much of the access gap is already encoded in variables a payer or a state holds. **Second, the two surveys disagree on the level, and that
disagreement is itself the most policy-relevant number in the paper.**
MEPS says 57–64% of adults had no dental visit; BRFSS says ~33%. The instruments differ (calendar-year event records vs 12-month recall, which is subject to recall bias [19]), and neither is "the truth". Any intervention target or budget built on one of these numbers without naming the source will be wrong by 24 to 31 points. **Third, high out-of-pocket
spending is not a burden measure.** The adults most likely to spend
$1,000+ out of pocket are older, richer, privately insured and NH White, the people who receive expensive care and can pay for it. The poorest and
uninsured rarely reach $1,000 OOP because they do not get care at all
(their no-visit prevalence is 76.1% and 88.8%). Treating high OOP as a
proxy for financial hardship would invert the equity story.

The state pattern follows the income and coverage gradient: the Northeast, with
higher incomes and broader coverage, has the lowest foregone-care rates;
the South and Appalachia, with lower incomes and thinner adult dental benefits, have the highest [1,3], a 16-point spread that survives an independent cross-check against NOHSS (r = 0.955).

In all three outcomes, a
single decision threshold produces wildly unequal sensitivity across
income and insurance groups, 0.19 vs 0.96 in BRFSS, because sensitivity
at a fixed threshold tracks prevalence. Any deployment that scores adults for dental outreach on a single threshold would systematically over-flag the poor and under-flag the affluent [17], and in the high-OOP case would
essentially fail to detect cases in Black, Hispanic and uninsured adults
at all. Group-specific thresholds, or a ranking-only use with human review,
would be required; we do not recommend deployment of any of these models as a probability tool without recalibration [20], and the high-OOP models not at all in their current form (ECE 0.37–0.39). No prior machine-learning study predicting dental-visit attendance or high out-of-pocket dental spending was identified in our literature search.

## Conclusion
Foregone care is modestly predictable from economics alone. High out-of-pocket spending marks receipt of expensive care, not burden. The two surveys disagree by 24 to 31 points, so any policy number must name its source.

## Limitations

- **Unweighted throughout** (prediction, not population estimation) [13]; all rates are sample rates, not population estimates.
- **MEPS has no public state identifier**, the state angle is
  BRFSS/NOHSS only; MEPS contributes census region, not state.
- **The MEPS–BRFSS prevalence gap** (57–64% vs ~33%) is a measurement
  difference (event records vs 12-month recall), not a contradiction to be
  averaged away; we do not pool the two surveys.
- **The foregone-care proxy is imperfect**: `DNUNAB42`/`DNDLAY42` (unable
  to get / delayed needed dental care) do not exist in the 2018–2022 FYC
  files, so "no visit" conflates people who needed care and could not get
  it with people who did not need or want a visit.
- **High-OOP models are severely miscalibrated** (ECE 0.37–0.39) and the
  outcome is a marker of receiving expensive care, not a pure burden
  measure.
- **BRFSS training is a 150k subsample of 2020** (CPU time); the test set
  is the full 2022 file. NOHSS has no 2022 in this dataset snapshot, so
  the BRFSS–NOHSS cross-check is for 2020 only.
- **Mississippi 2022** is a documented source-data anomaly (see Results);
  it is flagged, not silently corrected.
- All models are associative, not causal: coefficients describe who is predicted to forgo care, not what would happen if insurance or income changed.
- BRFSS is a telephone survey; non-response and coverage bias can shift state rates and model inputs.
- MEPS follows a panel over two years; attrition can bias the pooled sample toward stably housed, reachable respondents.

## Acknowledgments

**Funding.** None.

**Conflicts of interest.** The author declares no conflicts of interest.

**Ethics approval.** This study used de-identified public-use MEPS, BRFSS and NOHSS data; no ethics approval was required.

**Consent to participate.** Not applicable (de-identified public-use data).

**Authors' contributions.** Jeffrey Appiagyei is the sole author of this draft; the byline is to be confirmed before submission.

## Data availability

MEPS public-use data: AHRQ (https://meps.ahrq.gov/mepsweb/); BRFSS public-use data: CDC (https://www.cdc.gov/brfss/); NOHSS indicators: CDC Socrata API (dataset jz6n-v26y). Analysis code, metrics and figures: this repository (`src/`, `results/`, `results/figures/`). Reproduce with the four commands in the README (download, harmonize, train, figures), CPU only, Python 3.12, pandas 3.0.6, scikit-learn 1.9.1; see `requirements.txt` for the exact environment.

## References
1. Vujicic M, Buchmueller T, Klein R. Dental care presents the highest level of financial barriers, compared with other types of health care services. Health Aff. 2016;35(12):2176-2182. doi:10.1377/hlthaff.2016.0800
2. Freed M, Ochieng N, Sroczynski N, Amin K, Damico A. Medicare and dental coverage: a closer look. KFF; 2021. https://www.kff.org/medicare/issue-brief/medicare-and-dental-coverage-a-closer-look/
3. Medicaid and CHIP Payment and Access Commission. Chapter 2: Medicaid coverage of dental benefits for adults. In: Report to Congress on Medicaid and CHIP. Washington, DC: MACPAC; June 2015. https://www.macpac.gov/wp-content/uploads/2015/06/MedicaidCoverageof-Dental-Benefitsfor-Adults.pdf
4. American Dental Association, Health Policy Institute. National trends in dental care use, dental insurance coverage, and cost barriers. Chicago: ADA; 2026. https://www.ada.org/resources/research/health-policy-institute/coverage-access-outcomes
5. Agency for Healthcare Research and Quality. Medical Expenditure Panel Survey: Full Year Consolidated Data Files and Dental Visits event files, 2018-2022. https://meps.ahrq.gov/mepsweb/
6. Cohen JW, Cohen SB, Banthin JS. The Medical Expenditure Panel Survey: a national information resource to support healthcare cost research and inform policy and practice. Med Care. 2009;47(7 Suppl 1):S44-S50. doi:10.1097/MLR.0b013e3181a23e3a
7. Centers for Disease Control and Prevention. Behavioral Risk Factor Surveillance System: annual data, 2020 and 2022. https://www.cdc.gov/brfss/
8. Mokdad AH. The Behavioral Risk Factor Surveillance System: past, present, and future. Annu Rev Public Health. 2009;30:43-54. doi:10.1146/annurev.publhealth.031308.100226
9. Centers for Disease Control and Prevention. National Oral Health Surveillance System: adult indicators, 2012-2020. https://data.cdc.gov/d/jz6n-v26y
10. Beltran-Aguilar ED, Barker LK, Canto MT, Dye BA, et al. Surveillance for dental caries, dental sealants, tooth retention, edentulism, and enamel fluorosis: United States, 1988-1994 and 1999-2002. MMWR Surveill Summ. 2005;54(3):1-43.
11. Pedregosa F, Varoquaux G, Gramfort A, Michel V, Thirion B, Grisel O, et al. Scikit-learn: machine learning in Python. J Mach Learn Res. 2011;12:2825-2830. doi:10.5555/1953048.2078195
12. Youden WJ. Index for rating diagnostic tests. Cancer. 1950;3(1):32-35. doi:10.1002/1097-0142(1950)3:1<32::AID-CNCR2820030106>3.0.CO;2-3
13. Pfeffermann D. The role of sampling weights when modeling survey data. Int Stat Rev. 1993;61(2):317-337. doi:10.2307/1403631
14. Hanley JA, McNeil BJ. The meaning and use of the area under a receiver operating characteristic (ROC) curve. Radiology. 1982;143(1):29-36. doi:10.1148/radiology.143.1.7063747
15. Brier GW. Verification of forecasts expressed in terms of probability. Mon Weather Rev. 1950;78(1):1-3. doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
16. Guo C, Pleiss G, Sun Y, Weinberger KQ. On calibration of modern neural networks. In: Proceedings of the 34th International Conference on Machine Learning. Proceedings of Machine Learning Research. 2017;70:1321-1330. arXiv:1706.04599.
17. Obermeyer Z, Powers B, Vogeli C, Mullainathan S. Dissecting racial bias in an algorithm used to manage the health of populations. Science. 2019;366(6464):447-453. doi:10.1126/science.aax2342
18. Brian Z, Weintraub JA. Oral health and COVID-19: increasing the need for prevention and access. Prev Chronic Dis. 2020;17:E82. doi:10.5888/pcd17.200266
19. Coughlin SS. Recall bias in epidemiologic studies. J Clin Epidemiol. 1990;43(1):87-91. doi:10.1016/0895-4356(90)90060-3
20. Niculescu-Mizil A, Caruana R. Predicting good probabilities with supervised learning. In: Proceedings of the 22nd International Conference on Machine Learning. New York: ACM; 2005:625-632. doi:10.1145/1102351.1102430

## Target journal

**Journal of Public Health Dentistry** (Wiley, journal of the American
Association of Public Health Dentistry), the best topical fit: dental
access, affordability and state variation, with an economics framing, is
squarely in its scope, and it publishes health-services and policy
analyses of this kind. **$0-APC status: likely covered, to confirm at
acceptance.** The Mizzou GWLA/Springer deal is hybrid-journals-only and
would not cover a Wiley title, but Wiley has a separate agreement
with the University of Missouri System: corresponding authors
affiliated with a participating UM System institution may publish open
access at no charge in a Wiley hybrid journal, for articles accepted
on or after 1 January 2026 (Wiley institutional-payments page,
checked 2026-11-08). This journal is a Wiley hybrid title, so it
should qualify if you are the corresponding author and funds remain
available at acceptance, the funding request must be approved and
sufficient funds must be available at that point. The Mizzou Open
Journal Finder (https://mizzoulibraries.openjournalfinder.com/) could
not be used to verify this title, its journal list and search render
no journal names in text form (JS-driven shell). The subscription route
carries no author fee in any case. A Springer-hybrid alternative in
scope is the *Journal of Public Health* (Springer), also unverified
in the Open Journal Finder, to be checked at acceptance. **This
manuscript is a draft and is parked; it is never submitted without the
author's explicit word.**

