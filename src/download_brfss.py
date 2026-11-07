#!/usr/bin/env python3
"""Download BRFSS annual survey files (CDC, https://www.cdc.gov/brfss/).

Oral-health items (LASTDEN3: time since last dental visit) are asked in
even-numbered years only, so we take the two most recent even years with
final data at build time: 2020 and 2022 (LLCP combined landline+cell
XPT zips). No login, public-use.

ACCESS NOTE (2026-11-07): a direct GET of the CDC file from this box is
refused by CDC's CDN (Akamai "Access Denied", HTTP 403, even with
browser headers; HEAD returns 200). The files were therefore fetched
from the Wayback Machine's archived copies of the exact official CDC
URLs (CDX-verified captures, same payload digests):
  2022: web.archive.org/web/20240226215555id_/.../LLCP2022XPT.zip
  2020: web.archive.org/web/20230323165332id_/.../LLCP2020XPT.zip
The script tries the CDC URL first and falls back to Wayback, logging
which source succeeded. Writes to data/raw/, logs to
results/download_log_brfss.json.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

FILES = {
    2020: ("https://www.cdc.gov/brfss/annual_data/2020/files/LLCP2020XPT.zip",
           "https://web.archive.org/web/20230323165332id_/"
           "https://www.cdc.gov/brfss/annual_data/2020/files/LLCP2020XPT.zip"),
    2022: ("https://www.cdc.gov/brfss/annual_data/2022/files/LLCP2022XPT.zip",
           "https://web.archive.org/web/20240226215555id_/"
           "https://www.cdc.gov/brfss/annual_data/2022/files/LLCP2022XPT.zip"),
}


def main():
    log = []
    for year, urls in FILES.items():
        fname = f"brfss_{year}_LLCPXPT.zip"
        dest = RAW / fname
        if dest.exists() and dest.stat().st_size > 1_000_000:
            log.append({"url": urls[0], "file": str(dest.relative_to(ROOT)),
                        "bytes": dest.stat().st_size,
                        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                        "status": "skipped-existing"})
            print(f"skip {fname} (exists, {dest.stat().st_size/1e6:.1f} MB)")
            continue
        ok = False
        for url in urls:
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = r.read()
                if len(data) < 1_000_000 or data[:2] != b"PK":
                    raise ValueError(f"not a zip ({len(data)} bytes)")
                dest.write_bytes(data)
                log.append({"url": url, "file": str(dest.relative_to(ROOT)),
                            "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "status": 200})
                print(f"ok   {fname} {len(data)/1e6:.1f} MB via {url[:60]}...")
                ok = True
                break
            except Exception as e:  # noqa: BLE001
                print(f"try {url[:60]}... failed: {e}")
        if not ok:
            log.append({"url": urls[0], "file": str(dest.relative_to(ROOT)),
                        "status": "FAILED all sources"})
            print(f"FAIL {fname}: all sources failed")
    out = ROOT / "results" / "download_log_brfss.json"
    out.write_text(json.dumps({"source": "CDC BRFSS annual data", "files": log}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
