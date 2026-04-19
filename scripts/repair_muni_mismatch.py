#!/usr/bin/env python3
"""Repair retry_queue rows where the municipality is missing from the
Google formatted_address.

These are the `publish_policy == hide_muni_mismatch` rows: Google's pin
landed in a different city from the one the source says. Some are
legitimately wrong (Google placed the pin in a different municipality).
Some are abbreviation false-positives ("Marechal" vs "Mal."). A repair
pass with deterministic candidate queries salvages both kinds where
possible.

Input:  build/master_geocoded_patched_v1.csv (filter: publish_policy == hide_muni_mismatch)
Output: build/muni_mismatch_repair_best_attempts.csv
        build/master_geocoded.csv  (in-place overwrite of `improved_confidently` rows)

After this runs, re-execute:
    python3 scripts/apply_repairs.py
    python3 scripts/build_app_hospitals_json.py

and the improved rows will flow into the publish set automatically.

Same scoring rubric as scripts/repair_high_risk_geocodes.py.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Reuse the battle-tested helpers from the high-risk repair script
from repair_high_risk_geocodes import (  # noqa: E402
    read_api_key,
    generate_candidates,
    fetch_geocode,
    score_result,
    classify_outcome,
    strip_accents_lower,
    iso_now,
    INTER_REQUEST_DELAY,
    PLACE_ID_REUSE_THRESHOLD,
)
import time  # noqa: E402

BUILD = ROOT / "build"
MASTER = BUILD / "master_geocoded.csv"
PATCHED = BUILD / "master_geocoded_patched_v1.csv"
OUT_BEST = BUILD / "muni_mismatch_repair_best_attempts.csv"
RAW_LOG = BUILD / "muni_mismatch_repair_raw_responses.jsonl"


def compute_suspicious_place_ids() -> set[str]:
    origins: dict[str, set[tuple[str, str]]] = defaultdict(set)
    with MASTER.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("place_id") or "").strip()
            if not pid:
                continue
            origins[pid].add((
                strip_accents_lower(r.get("municipality_clean") or ""),
                (r.get("state_clean") or "").upper(),
            ))
    return {p for p, o in origins.items() if len(o) >= PLACE_ID_REUSE_THRESHOLD}


def main() -> int:
    api_key = read_api_key()
    if not api_key:
        sys.stderr.write("ERROR: no Google Maps API key available.\n")
        return 2

    suspicious = compute_suspicious_place_ids()

    with PATCHED.open(encoding="utf-8", newline="") as fh:
        all_rows = list(csv.DictReader(fh))
    targets = [r for r in all_rows if (r.get("publish_policy") or "") == "hide_muni_mismatch"]
    print(f"Repair candidates (hide_muni_mismatch): {len(targets):,}")
    if not targets:
        return 0

    # Each target needs: health_unit_name, address, municipality, state, source_state_abbr
    # The patched master has these under their original (non-*_clean) column names.

    best_cols = [
        "row_id", "source_state_abbr", "municipality", "health_unit_name",
        "old_formatted_address", "old_lat", "old_lng", "old_place_id",
        "old_score", "old_review_reasons",
        "best_candidate_pattern", "best_candidate_query",
        "best_formatted_address", "best_lat", "best_lng", "best_place_id",
        "best_partial_match", "best_location_type", "best_candidate_score",
        "best_candidate_reasons", "score_delta", "repair_outcome",
    ]

    best_rows = []
    improved_ids = []

    with RAW_LOG.open("a", encoding="utf-8") as raw_out:
        for src in targets:
            rid = src["row_id"]

            # Score the current (old) result as baseline
            synthetic_old_data = None
            if src.get("formatted_address"):
                try:
                    lat = float(src["lat"]) if src.get("lat") else None
                    lng = float(src["lng"]) if src.get("lng") else None
                except ValueError:
                    lat = lng = None
                synthetic_old_data = {
                    "results": [{
                        "formatted_address": src.get("formatted_address", ""),
                        "geometry": {
                            "location": {"lat": lat, "lng": lng},
                            "location_type": src.get("location_type", ""),
                        },
                        "place_id": src.get("place_id", ""),
                        "partial_match": src.get("partial_match", "") == "true",
                    }]
                }
            old_score, _, _ = score_result(src, "OK", synthetic_old_data, suspicious)

            candidates = generate_candidates(src)
            attempts = []
            for i, c in enumerate(candidates, start=1):
                status, data, err = fetch_geocode(c["query"], api_key)
                score, reasons, extract = score_result(src, status, data, suspicious)
                raw_out.write(json.dumps({
                    "row_id": rid,
                    "candidate_number": i,
                    "pattern": c["pattern"],
                    "query": c["query"],
                    "status": status,
                    "error": err,
                    "score": score,
                    "attempted_at": iso_now(),
                    "response": data,
                }, ensure_ascii=False))
                raw_out.write("\n")
                attempts.append((score, reasons, extract, c))
                time.sleep(INTER_REQUEST_DELAY)

            if attempts:
                best_score, best_reasons, best_extract, best_cand = max(
                    attempts, key=lambda x: x[0]
                )
            else:
                best_score, best_reasons, best_extract, best_cand = old_score, [], {}, {"pattern": "", "query": ""}

            outcome = classify_outcome(old_score, best_score, best_reasons)
            if outcome == "improved_confidently":
                improved_ids.append(rid)

            best_rows.append({
                "row_id": rid,
                "source_state_abbr": src.get("source_state_abbr", ""),
                "municipality": src.get("municipality", ""),
                "health_unit_name": src.get("health_unit_name", ""),
                "old_formatted_address": src.get("formatted_address", ""),
                "old_lat": src.get("lat", ""),
                "old_lng": src.get("lng", ""),
                "old_place_id": src.get("place_id", ""),
                "old_score": old_score,
                "old_review_reasons": src.get("original_review_reasons", ""),
                "best_candidate_pattern": best_cand.get("pattern", ""),
                "best_candidate_query": best_cand.get("query", ""),
                "best_formatted_address": best_extract.get("formatted_address", ""),
                "best_lat": best_extract.get("lat", ""),
                "best_lng": best_extract.get("lng", ""),
                "best_place_id": best_extract.get("place_id", ""),
                "best_partial_match": best_extract.get("partial_match", ""),
                "best_location_type": best_extract.get("location_type", ""),
                "best_candidate_score": best_score,
                "best_candidate_reasons": "; ".join(best_reasons),
                "score_delta": best_score - old_score,
                "repair_outcome": outcome,
            })

    with OUT_BEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=best_cols, extrasaction="ignore")
        w.writeheader()
        for r in best_rows:
            w.writerow(r)

    # Patch master_geocoded.csv in place so apply_repairs.py picks them up.
    # We apply ONLY improved_confidently outcomes.
    with MASTER.open(encoding="utf-8", newline="") as fh:
        master_reader = csv.DictReader(fh)
        master_cols = list(master_reader.fieldnames or [])
        master_rows = list(master_reader)

    best_by_id = {r["row_id"]: r for r in best_rows if r["repair_outcome"] == "improved_confidently"}
    patched_count = 0
    for row in master_rows:
        rid = row["row_id"]
        if rid in best_by_id:
            b = best_by_id[rid]
            row["formatted_address"] = b["best_formatted_address"]
            row["lat"] = b["best_lat"]
            row["lng"] = b["best_lng"]
            row["place_id"] = b["best_place_id"]
            row["partial_match"] = b["best_partial_match"]
            row["location_type"] = b["best_location_type"]
            patched_count += 1

    with MASTER.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=master_cols, extrasaction="ignore")
        w.writeheader()
        for row in master_rows:
            w.writerow(row)

    from collections import Counter
    outcome_counts = Counter(r["repair_outcome"] for r in best_rows)
    print("Outcomes:")
    for k, v in sorted(outcome_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    print(f"Patched into master_geocoded.csv: {patched_count} rows")
    print(f"Best-attempts CSV: {OUT_BEST}")
    print(f"Raw responses: {RAW_LOG}")
    print("")
    print("Next: re-run apply_repairs.py and build_app_hospitals_json.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
