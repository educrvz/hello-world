#!/usr/bin/env bash
# Orchestrator for the SoroJ data refresh pipeline.
#
# End-to-end: extracted/{UF}.json -> app/hospitals.json
#
# Idempotent and resume-safe:
#   - stage 07 (geocoding) reuses already-OK rows from master_geocoded.csv
#   - every other stage just overwrites its outputs
#
# PDF re-extraction (gov.br PESA -> Docs Estado/ -> extracted/{UF}.json) is
# still human-in-the-loop. Run ./scripts/check_updates.py first; for any UF
# that changed, drop the new PDF into Docs Estado/ and re-extract that state
# with Claude Code multimodal. See docs/PROCESS.md §2–§3.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="python3"

say() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }

say "Stage 04: merge per-state JSONs"
$PY scripts/merge_state_jsons.py

say "Stage 05: normalize"
$PY scripts/normalize_hospital_rows.py

say "Stage 06: pre-geocode QA"
$PY scripts/pre_geocode_qaqc.py

say "Stage 07: geocode (resume-safe, uses Keychain / GOOGLE_MAPS_API_KEY)"
$PY scripts/geocode_hospitals.py

say "Stage 08: classify v3"
$PY scripts/classify_geocode_quality_v3.py

say "Stage 09a: package high-risk exception queue"
$PY - <<'PY'
import subprocess, os
# The exception-queue builder from stage 09a is inline; redo it here so the
# pipeline exits with artefacts up to date. It's cheap (<1 s).
# If you later promote that logic to scripts/package_high_risk_queue.py,
# switch this to a subprocess call.
import csv, json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path.cwd()
PDF_DIR = ROOT / "Docs Estado"
JSON_DIR = ROOT / "extracted"
HIGH_RISK = ROOT / "build/geocode_manual_review_high_risk_v3.csv"
MASTER = ROOT / "build/master_geocoded.csv"
OUT_CSV = ROOT / "build/high_risk_exception_queue_v1.csv"

if not HIGH_RISK.exists():
    raise SystemExit(f"missing {HIGH_RISK}")

pdf_map = defaultdict(list)
pdf_re = re.compile(r"^(?:V\d+_)?([A-Z]{2})_\d+\.pdf$")
if PDF_DIR.exists():
    for p in sorted(PDF_DIR.iterdir()):
        m = pdf_re.match(p.name)
        if m:
            pdf_map[m.group(1)].append(p.name)

master_by_id = {r["row_id"]: r for r in csv.DictReader(MASTER.open())}
with HIGH_RISK.open() as f:
    hr_rows = list(csv.DictReader(f))

cols = [
    "row_id","source_state_abbr","source_state_file","source_pdf_filename",
    "state","municipality","health_unit_name","address","cnes","geocode_query",
    "formatted_address","lat","lng","place_id","partial_match","location_type",
    "review_status","review_reasons",
]

enriched = []
for row in hr_rows:
    uf = row["source_state_abbr"]
    pdfs = pdf_map.get(uf, [])
    master = master_by_id.get(row["row_id"], {})
    enriched.append({
        "row_id": row["row_id"],
        "source_state_abbr": uf,
        "source_state_file": row.get("source_state_file", ""),
        "source_pdf_filename": pdfs[0] if pdfs else "",
        "state": master.get("state", ""),
        "municipality": master.get("municipality", ""),
        "health_unit_name": master.get("health_unit_name", ""),
        "address": master.get("address", ""),
        "cnes": master.get("cnes", ""),
        "geocode_query": master.get("geocode_query", ""),
        "formatted_address": row.get("formatted_address", ""),
        "lat": row.get("lat", ""),
        "lng": row.get("lng", ""),
        "place_id": row.get("place_id", ""),
        "partial_match": row.get("partial_match", ""),
        "location_type": row.get("location_type", ""),
        "review_status": row.get("review_status", ""),
        "review_reasons": row.get("review_reasons", ""),
    })

with OUT_CSV.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in enriched:
        w.writerow(r)
print(f"  wrote {len(enriched)} rows to {OUT_CSV.relative_to(ROOT)}")
PY

say "Stage 09b: repair high-risk geocodes (Google lookups per candidate)"
$PY scripts/repair_high_risk_geocodes.py

say "Stage 09c: apply repairs (first pass)"
$PY scripts/apply_repairs.py

say "Stage 09d: salvage retry_queue muni-mismatch rows (Google lookups)"
$PY scripts/repair_muni_mismatch.py

say "Stage 09e: re-classify + re-apply (picks up 09d salvages)"
$PY scripts/classify_geocode_quality_v3.py
$PY scripts/apply_repairs.py

say "Stage 10: google sheets exports"
$PY - <<'PY'
import csv
from pathlib import Path
ROOT = Path.cwd()
BUILD = ROOT / "build"
IN_PUB = BUILD / "publish_ready_v1.csv"
IN_REV = BUILD / "review_queue_v1.csv"
OUT_PUB = BUILD / "google_sheets_publish_ready_v1.csv"
OUT_REV = BUILD / "google_sheets_review_queue_v1.csv"

V3_BUCKETS = {
    "geocode_auto_accept_v3.csv": "auto_accept",
    "geocode_watchlist_v3.csv": "watchlist",
    "geocode_retry_queue_v3.csv": "retry_queue",
    "geocode_manual_review_high_risk_v3.csv": "manual_review_high_risk",
}
v3 = {}
for fn, bucket in V3_BUCKETS.items():
    p = BUILD / fn
    if p.exists():
        for r in csv.DictReader(p.open()):
            v3[r["row_id"]] = (bucket, r.get("review_reasons", ""))

COLS = [
    "row_id","source_state_abbr","state","municipality","health_unit_name",
    "address","phones_raw","cnes","antivenoms_raw","geocode_query",
    "formatted_address","lat","lng","place_id","partial_match",
    "location_type","geocode_status","final_status",
    "repair_applied","repair_source","repair_outcome",
    "review_status","review_reasons",
]
NULL_LITS = {"null","None","NULL","nan","NaN"}

def clean(v):
    s = "" if v is None else str(v).strip()
    return "" if s in NULL_LITS else s

def prep(row):
    rid = row["row_id"]
    bucket, reasons = v3.get(rid, ("", ""))
    out = {c: clean(row.get(c, "")) for c in COLS}
    ant = out.get("antivenoms_raw", "")
    if ant:
        out["antivenoms_raw"] = ", ".join(p.strip() for p in ant.split("|") if p.strip())
    out["review_status"] = bucket
    out["review_reasons"] = reasons
    return out

for src, dst in [(IN_PUB, OUT_PUB), (IN_REV, OUT_REV)]:
    rows = [prep(r) for r in csv.DictReader(src.open())]
    with dst.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  wrote {len(rows)} rows to {dst.relative_to(ROOT)}")
PY

say "Stage 11: build app/hospitals.json (production contract)"
$PY scripts/build_app_hospitals_json.py

say "Refresh complete. Ready to commit:"
echo "   app/hospitals.json"
echo "   hospitals.json"
echo "   reports/*"
echo "   build/*"
echo
echo "See docs/PROCESS.md §5 for the ship-to-prod checklist."
