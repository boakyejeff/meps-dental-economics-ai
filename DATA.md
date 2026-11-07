# DATA.md — MEPS dental visits + BRFSS/NOHSS dental economics

Every file, variable and number in this repo, with provenance. All sources are
public-use, no IRB, no login. Downloads live in `data/raw/` (gitignored) and
are listed in `results/download_log.json`, `results/download_log_brfss.json`
and `results/download_log_nohss.json`.

## 1. MEPS — Medical Expenditure Panel Survey (AHRQ)

Source: https://meps.ahrq.gov/ — Full Year Consolidated (FYC) Data Files and
Dental Visits event files, 2018–2022.

| Year | FYC file | Dental Visits file |
|------|----------|--------------------|
| 2018 | HC-209 | HC-206B |
| 2019 | HC-216 | HC-213B |
| 2020 | HC-224 | HC-220B |
| 2021 | HC-233 | HC-229B |
| 2022 | HC-243 | HC-239B |

Downloaded as Stata `.dta.zip` files (see the format gotcha below).
Analytic sample: adults 18+ with a positive full-year weight
(`PERWTyyF > 0`): **103,194 pooled** — 2018: 22,036; 2019: 21,080;
2020: 20,923; 2021: 21,768; 2022: 17,387.

### Variables used (verified against the MEPS HC-243 (2022) codebook)

| Variable | Meaning | Coding used |
|----------|---------|-------------|
| `DVTOTyy` | Number of dental visits in the year | `no_visit = (DVTOTyy == 0)` |
| `DVTEXPyy` | Total dental expenditure (all payers) | descriptive; event-file cross-check |
| `DVTSLFyy` | Dental out-of-pocket (self/family) amount | `high_oop = (DVTSLFyy >= $1,000)` |
| `AFRDDN42` | Could not afford dental care (Round 4/2) | descriptive only, not a model feature |
| `AGEyyX` | Age | numeric |
| `SEX` | Sex | Female / Male |
| `RACETHX` | Race/ethnicity | 1 Hispanic, 2 NH White, 3 NH Black, 4 NH Asian, 5 NH Other/multiple |
| `REGIONyy` | Census region | 1 Northeast, 2 Midwest, 3 South, 4 West |
| `INSCOVyy` | Insurance coverage | 1 Any private, 2 Public only, 3 Uninsured |
| `DENTIN42` | Dental insurance | 1 Yes / 2 No |
| `POVCATyy` | Poverty category | 1 Poor, 2 Near poor, 3 Low income, 4 Middle income, 5 High income |
| `POVLEVyy` | Poverty level (% of federal poverty line) | numeric |
| `EDUCYR` | Years of education | numeric |
| `HIDEG` | Highest degree | 1 no degree, 2 GED, 3 HS diploma, 4 Bachelor's, 5 Master's, 6 Doctorate, 7 other, 8 under-16; collapsed to No degree / GED / HS diploma / Bachelor's / Master's+ / Other |
| `EMPST53` | Employment status | 1 employed at interview date, 2 job to return to, 3 job during reference period, 4 not employed; collapsed to Employed (1/2/3) vs Not employed (4) |
| `RTHLTH53` / `MNHLTH53` | Perceived physical / mental health | 1–5, numeric |
| `PERWTyyF` | Full-year person weight | sample restriction only (`> 0`); **no survey weights in the models** (prediction, not population estimation) |

Reserved codes −1/−7/−8/−9/−15 were set to missing.

### What is NOT in these files (checked, not assumed)

- **`DNUNAB42` / `DNDLAY42` (unable to get / delayed needed dental care)
  are absent from every FYC file 2018–2022.** Checked in the HC-243 codebook
  and by column scan of all five files (`results/harmonisation.json`:
  `dnunab_present` / `dndlay_present` all `false`). They existed through
  ~2015 in the literature but were dropped from the public-use FYC before
  2018. `AFRDDN42` (could not afford dental care) is the surviving direct
  foregone-care item and is reported descriptively.
- **MEPS public-use files have NO state identifier.** State/County FIPS are
  restricted data (AHRQ Data Center / FSRDC only). Only census region
  (`REGIONyy`) is public. The state geospatial angle therefore comes from
  BRFSS/NOHSS (Section 2–3), not from MEPS.

### Format gotcha

The `.ssp.zip` "SAS transport" files on the MEPS site are **SAS CPORT, not
XPORT** — `pandas.read_sas` refuses them ("Header record indicates a CPORT
file"). The Stata `.dta.zip` files carry the same variables and read fine
with `pandas.read_stata(..., columns=[...], convert_categoricals=False)`.
Both formats are on disk under `data/raw/`; the pipeline uses the `.dta`
files. `src/download_meps.py` documents this.

### Outcome definitions

- **No dental visit** (`no_visit`): `DVTOTyy == 0` in the calendar year.
  Pooled prevalence 59.2%; by year 58.6% (2018), 57.5% (2019), **63.6%
  (2020 — COVID year)**, 59.4% (2021), 56.7% (2022).
- **High out-of-pocket dental spending** (`high_oop`): `DVTSLFyy >= $1,000`.
  Threshold rule (in `src/harmonise.py`): $1,000 if it gives ≥3% prevalence
  among adults, else the 90th percentile of OOP among adults with any dental
  expenditure, rounded to $50. Pooled prevalence at $1,000 was 4.4%, so the
  threshold is $1,000. By year: 4.2% (2018), 4.3% (2019), 3.7% (2020),
  4.9% (2021), 5.0% (2022). Median OOP among adults with any dental spending
  was $65–$80 across years; the 90th percentile among spenders was
  $1,001.60–$1,257.00.
- **Could not afford dental care** (`AFRDDN42`, descriptive): 12.4% (2018),
  12.5% (2019), 10.2% (2020), 8.7% (2021), 9.9% (2022).

### Event-file cross-check

Dental Visits event files were summed per person (event `DVXPyyX` total,
`DVSFyyX` self/family) and compared with the FYC totals
(`results/harmonisation.json`, `event_check`):

| Year | n-visits exact match | OOP exact match | Total-expenditure exact match | corr(event total, FYC) |
|------|---------------------|-----------------|------------------------------|------------------------|
| 2018 | 1.000 | 0.997 | 0.957 | 1.0000 |
| 2019 | 1.000 | 0.997 | 0.959 | 1.0000 |
| 2020 | 1.000 | 0.977 | 0.850 | 1.0000 |
| 2021 | 1.000 | 0.978 | 0.864 | 1.0000 |
| 2022 | 1.000 | 0.973 | 0.823 | 1.0000 |

Visit counts match exactly every year. Total-expenditure exact match is
lower in later years (flat-fee allocation differences, expected per MEPS
documentation); the correlation is ~1.0000 throughout, so the FYC totals
are used as-is.

## 2. BRFSS — Behavioral Risk Factor Surveillance System (CDC)

Source: https://www.cdc.gov/brfss/ — annual LLCP (combined landline +
cellular) XPT files. Oral-health items are asked in **even years only**;
target years 2020 + 2022.

| Year | File | Respondents in analytic sample | No-visit prevalence | States |
|------|------|-------------------------------|---------------------|--------|
| 2020 | `LLCP2020XPT.zip` (67,497,017 bytes) | 397,291 | 32.8% | 53 |
| 2022 | `LLCP2022XPT.zip` (84,614,105 bytes) | 438,111 | 33.3% | 54 |

Analytic sample: adults 18+ with a valid `LASTDEN4` response (1, 2, 3, 4
or 8). Pooled n = 835,402.

### Download workaround

A direct GET from CDC is **blocked from this box**: Akamai "Access Denied",
HTTP 403, even with full Chrome headers (HEAD returns 200). Files were
fetched from the Wayback Machine's archived copies of the exact official CDC
URLs (CDX-verified captures), byte-identical to the CDC Content-Length:
2022 via `web.archive.org/web/20240226215555id_/.../LLCP2022XPT.zip`,
2020 via `web.archive.org/web/20210923031354id_/.../LLCP2020XPT.zip`.
`src/download_brfss.py` tries CDC first, falls back to Wayback, and validates
the zip magic. The 2020 download needed 4 attempts (Wayback 429
rate-limiting on attempts 1–3).

### Variables used (verified against the actual XPT files, NOT assumed)

| Variable | Meaning | Notes |
|----------|---------|-------|
| `LASTDEN4` | Time since last dental visit | **1 within past year, 2 within past 2 years, 3 within past 5 years, 4 5+ years, 7 DK, 8 Never, 9 Refused.** This is `LASTDEN4` in 2020 and 2022, not `LASTDEN3` — renamed when the question was reworded (confirmed in the 2020 Utah and 2022 CDC questionnaires and the Wisconsin 2022 codebook). Outcome: `no_visit = (LASTDEN4 != 1)` among valid {1,2,3,4,8}. |
| `_DENVST3` | Calculated: visited dentist in past year (1 yes / 2 no) | Cross-check agreement with the `LASTDEN4` derivation: **1.0000 both years**. |
| `_RACE1` (2022) / `_RACE` (2020) | Race/ethnicity | 2022 `_RACE1`: 1 NH White, 2 NH Black, 3 AI/AN, 4 NH Asian, 5 NHPI, 6 Other, 7 Multiracial, 8 Hispanic, 9 Unknown. |
| `SEXVAR` | Sex | |
| `_AGEG5YR` | Age group (5-year bands) | Collapsed to 18–29 / 30–49 / 50–64 / 65+. |
| `EDUCA` | Education | Collapsed to Less than HS / HS grad / Some college / College grad. |
| `INCOME3` (2022) / **`INCOME2` (2020)** | Household income | Same 1–8 bands; the variable name differs by year. Collapsed to <$25k / $25–50k / $50–75k / $75k+. |
| `HLTHPLN1` (2020) / **`PRIMINSR` (2022)** | Health coverage | `HLTHPLN1` was dropped in 2022. `PRIMINSR`: 1–10 = insured (employer/union, private, Medicare, Medigap, Medicaid, CHIP, TRICARE/VA, Indian Health Service, state-sponsored, other government), **88 = no coverage of any type**, 77 DK, 99 refused. (An earlier assumption that 8 = none was wrong — 8 is Indian Health Service.) Collapsed to Insured / No coverage. |
| `EMPLOY1` | Employment | Collapsed to Employed / Unemployed / Not in labour force. |
| `_STATE` | State FIPS code | Mapped to abbreviations for the state figures. |

### Gotchas found during the build

- The XPT member name inside the 2022 zip is `LLCP2022.XPT ` **with a
  trailing space** — the extractor strips before matching `.XPT`.
- The label `"None"` is in pandas' default NA list, so `read_csv` silently
  turns it into NaN on read-back. The coverage label is therefore
  `"No coverage"`, not `"None"`.
- **No survey weights in the models** (prediction, not population
  estimation), matching the NHANES sibling.

### Mississippi 2022 anomaly — flagged, not deleted

BRFSS 2022 Mississippi shows a no-visit rate of **91.3%**, against 42.6% in
MS 2020 — while every other state moved ≤4.0 points between 2020 and 2022
(next largest move: Illinois +4.0 points). In the raw 2022 file, MS has
2,254 of 4,239 respondents at `LASTDEN4 = 2` ("within past 2 years") and
only 361 at `LASTDEN4 = 1` ("within past year"); in 2020 MS had 3,626 at
`LASTDEN4 = 1`. Within MS 2022 the `LASTDEN4 = 1` share is 1–5% in January
and May–December but 28–58% in February–April — a mid-year fielding /
processing artifact in the released file, not a real access collapse.
CDC's own `_DENVST3` agrees with `LASTDEN4`, so the anomaly is in the
source data, not in our derivation.

Handling: MS 2022 is **kept** in the BRFSS model test set (4,129 of
438,111 rows, ~0.9%; negligible effect on the metrics) but **excluded from
the state ranking and choropleth** (drawn grey), with the flag recorded in
`results/state_rates.csv` (`flag` column) and
`results/state_rates.json` (`flagged_excluded_from_ranking`).

## 3. NOHSS — National Oral Health Surveillance System (CDC)

Source: Socrata API, dataset `jz6n-v26y`,
`https://data.cdc.gov/resource/jz6n-v26y.json`. Indicator: "Adults aged 18+
who have visited a dentist or dental clinic in the past year"
(indicatorid `ADT1_1`), source BRFSS, crude prevalence.

- 12,682 rows fetched; "Overall" rows (missing `break_out_category`,
  returned by Socrata as the literal string `"None"` in-memory) kept:
  **266 state-year rows, years 2012, 2014, 2016, 2018, 2020 only** (no 2022
  in this dataset snapshot), 54 locations (50 states + DC + territories +
  US, US excluded from the analysis).
- `data_value` is a **percent (0–100)**; converted to a proportion (÷100)
  in `src/harmonise.py` so it is comparable with the BRFSS rates.
- Cross-check: BRFSS vs NOHSS state visit rates for 2020 (the one
  overlapping year), 53 states: **Pearson r = 0.955, mean absolute
  difference 1.7 percentage points** (`results/state_rates.json`). The two
  independent extractions of the same underlying survey agree closely.

## 4. US states GeoJSON (choropleth)

`data/raw/us-states.geojson`, from
`https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json`
(89,263 bytes, 52 features; properties carry `name` only — name →
abbreviation mapped in `src/figures.py`). Drawn as hand-plotted matplotlib
polygons; no geopandas on this box.

## 5. Harmonised files

| File | Rows | Content |
|------|------|---------|
| `data/harmonised/meps.csv` | 103,194 | Adults 18+, MEPS 2018–2022, all model features + outcomes |
| `data/harmonised/brfss.csv` | 835,402 | Adults 18+, BRFSS 2020 + 2022, collapsed features + outcome |
| `data/harmonised/nohss_state.csv` | 266 | State-year NOHSS visit rates, 2012–2020 |

## 6. The MEPS–BRFSS prevalence gap (a finding, not an error)

MEPS no-visit prevalence is 57–64% while BRFSS no-visit prevalence is
~33% — the same concept measured by different instruments. MEPS records
calendar-year dental **events** from a panel survey (a visit counts only if
it occurred in that calendar year and was recorded); BRFSS asks for
**12-month recall at interview** ("how long has it been since you last
visited a dentist?"), which is known to over-report recency
(telescoping). The two are not reconciled here; both are reported as-is and
the gap is discussed as a limitation in the manuscript. Do not mix the two
rates in one sentence without naming the source.

## 7. What was NOT used

- MEPS Dental Visits event files: used only for the cross-check in
  Section 1, not as model features (the FYC totals already contain the
  same information).
- `TOTEXPyy` (total medical expenditure): excluded as a predictor — it
  contains dental spending, so it would leak the expenditure outcome.
- `AFRDDN42`: descriptive only — near-tautological as a predictor of
  foregone care.
- `RMVTETH4` (teeth removed, BRFSS): present in the files, not used.
- MEPS state identifiers: do not exist in the public-use files (Section 1).
