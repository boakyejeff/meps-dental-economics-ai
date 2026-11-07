#!/usr/bin/env python3
"""Download MEPS public-use files (AHRQ, https://meps.ahrq.gov/).

Files (all Stata format, *.dta.zip, HTTP 200 verified 2026-11-07):
  Full Year Consolidated (FYC) 2018-2022:
    2018 HC-209, 2019 HC-216, 2020 HC-224, 2021 HC-233, 2022 HC-243
  Dental Visits event files 2018-2022:
    2018 HC-206B, 2019 HC-213B, 2020 HC-220B, 2021 HC-229B, 2022 HC-239B
NOTE: the SAS transport (*.ssp.zip) files are SAS CPORT, not XPORT, and
pandas.read_sas cannot read them ("Header record indicates a CPORT file").
The Stata .dta files carry the same variables and are read with
pandas.read_stata(..., columns=[...]).
No login, no IRB (public-use, de-identified). Writes to data/raw/,
writes results/download_log.json. Skips files already present.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

BASE = "https://meps.ahrq.gov/data_files/pufs"

FILES = {
    # year: (fyc_puf, dental_puf)
    2018: ("h209", "h206b"),
    2019: ("h216", "h213b"),
    2020: ("h224", "h220b"),
    2021: ("h233", "h229b"),
    2022: ("h243", "h239b"),
}


def fetch(url: str, dest: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.write_bytes(data)
    return {
        "url": url,
        "file": str(dest.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": 200,
    }


def main():
    log = []
    for year, (fyc, dv) in FILES.items():
        for kind, puf in (("fyc", fyc), ("dental_visits", dv)):
            fname = f"meps_{year}_{kind}_{puf}dta.zip"
            dest = RAW / fname
            url = f"{BASE}/{puf}/{puf}dta.zip"
            if dest.exists() and dest.stat().st_size > 0:
                log.append({"url": url, "file": str(dest.relative_to(ROOT)),
                            "bytes": dest.stat().st_size, "status": "skipped-existing"})
                print(f"skip {fname} (exists)")
                continue
            try:
                entry = fetch(url, dest)
                log.append(entry)
                print(f"ok   {fname} {entry['bytes']/1e6:.1f} MB")
            except Exception as e:  # noqa: BLE001 - record and continue
                log.append({"url": url, "file": str(dest.relative_to(ROOT)),
                            "status": f"FAILED: {e}"})
                print(f"FAIL {fname}: {e}")
    out = ROOT / "results" / "download_log.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"source": "MEPS AHRQ public-use files",
                               "files": log}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
