#!/usr/bin/env python3
"""Download NOHSS adult indicators (CDC, National Oral Health Surveillance
System) via the data.cdc.gov Socrata API (dataset jz6n-v26y).

Indicator used: "Adults aged 18+ who have visited a dentist or dental
clinic in the past year" (indicatorid ADT1_1), source BRFSS, crude
prevalence, response Yes/No, overall break-out (all ages/races), by state
and year. No login. Writes data/raw/nohss_adult_dental_visit.csv and
results/download_log_nohss.json.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

ENDPOINT = "https://data.cdc.gov/resource/jz6n-v26y.json"
INDICATOR = "Adults aged 18+ who have visited a dentist or dental clinic in the past year"


def fetch_all() -> list:
    rows, offset = [], 0
    while True:
        params = {
            "$limit": 50000,
            "$offset": offset,
            "$where": f"indicator='{INDICATOR}'",
        }
        url = ENDPOINT + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            batch = json.loads(r.read())
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < 50000:
            break
    return rows


def main():
    rows = fetch_all()
    print(f"fetched {len(rows)} NOHSS rows for indicator: {INDICATOR}")
    import pandas as pd

    df = pd.DataFrame(rows)
    keep = ["year", "locationabbr", "locationdesc", "locationid", "category",
            "indicator", "indicatorid", "response", "datasource",
            "data_value", "data_value_unit", "data_value_type",
            "low_confidence_interval", "high_confidence_interval",
            "samplesize", "break_out", "break_out_category"]
    df = df[[c for c in keep if c in df.columns]]
    out = RAW / "nohss_adult_dental_visit.csv"
    df.to_csv(out, index=False)
    # "Overall" rows carry a missing break_out_category (Socrata returns
    # it as the literal string "None" in-memory; it round-trips to empty
    # in CSV) and both a crude and an age-adjusted copy in some years —
    # keep crude only.
    overall_mask = ((df["break_out_category"].isna())
                    | (df["break_out_category"].astype(str) == "None"))
    overall = df[overall_mask
                 & (df["data_value_type"] == "Crude Prevalence")
                 & (df["response"] == "Yes")]
    print(f"overall/Yes/crude rows: {len(overall)}; years {sorted(overall['year'].unique())}; "
          f"locations {overall['locationabbr'].nunique()}")
    log = {"source": "CDC NOHSS via data.cdc.gov Socrata API jz6n-v26y",
           "indicator": INDICATOR, "rows": len(df),
           "overall_yes_rows": int(len(overall)),
           "years": sorted(df["year"].unique().tolist()),
           "file": str(out.relative_to(ROOT)),
           "accessed": "2026-11-07"}
    (ROOT / "results" / "download_log_nohss.json").write_text(json.dumps(log, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
