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

say "Stage 09f: re-apply committed manual-triage decisions"
# data/manual_triage/*.csv holds every operator decision ever made (muni-mismatch
# unhides, state-only pins, etc.). Re-applying them here makes them survive the
# from-scratch CSV rebuild that a new state PDF triggers. apply_manual_triage.py
# is idempotent: it only archives original_* on first touch.
shopt -s nullglob
triage_files=(data/manual_triage/*.csv)
shopt -u nullglob
if [ ${#triage_files[@]} -eq 0 ]; then
  echo "  (no manual-triage decision files committed — skipping)"
else
  for f in "${triage_files[@]}"; do
    echo "  applying $f"
    $PY scripts/apply_manual_triage.py "$f"
  done
fi

say "Stage 10: rebuild final queues and google sheets exports"
$PY scripts/rebuild_final_artifacts.py

say "Stage 11: build app/hospitals.json (production contract)"
$PY scripts/build_app_hospitals_json.py

say "Stage 12: validate final artifacts"
$PY scripts/rebuild_final_artifacts.py --check

say "Refresh complete. Ready to commit:"
echo "   app/hospitals.json"
echo "   hospitals.json"
echo "   reports/*"
echo "   build/*"
echo
echo "See docs/PROCESS.md §5 for the ship-to-prod checklist."
