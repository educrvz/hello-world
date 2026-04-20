"""Apply manual_triage decisions from the muni_mismatch triage HTML.

Input CSV columns: row_id, uf, name, municipality, outcome, decision, best_lat, best_lng, note.
Decisions handled:
  - accept_best  -> adopt the repair pass's best candidate (lat/lng/FA/place_id/type)
  - manual       -> parse "lat, lng" from the note column; mark location_type ROOFTOP
  - keep_hidden  -> no-op

For each applied row we:
  - archive the current pin into original_* columns if not already populated
  - overwrite lat, lng, formatted_address, place_id, partial_match, location_type
  - set final_status=publish_ready, publish_policy=publish
  - set repair_applied=true, repair_source=manual_triage
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"
REPAIRS = ROOT / "build" / "muni_mismatch_repair_best_attempts.csv"

COORD_RE = re.compile(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)")


def parse_coords(text: str) -> tuple[str, str] | None:
    if not text:
        return None
    m = COORD_RE.search(text)
    return (m.group(1), m.group(2)) if m else None


def main(decisions_csv: Path) -> int:
    with REPAIRS.open() as f:
        repair = {r["row_id"]: r for r in csv.DictReader(f)}

    with decisions_csv.open() as f:
        decisions = list(csv.DictReader(f))

    with MASTER.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    by_id = {r["row_id"]: r for r in rows}

    applied = 0
    for d in decisions:
        row_id = d["row_id"]
        decision = d["decision"]
        if decision == "keep_hidden" or not decision:
            continue
        row = by_id.get(row_id)
        if row is None:
            print(f"WARN: {row_id} not found in master CSV", file=sys.stderr)
            continue

        rep = repair.get(row_id, {})
        # Prefer best_* columns baked into the decisions CSV (from ad-hoc regeocode
        # passes like build_pa_triage.py); fall back to the muni_mismatch repair CSV.
        best_fa = d.get("best_formatted_address") or rep.get("best_formatted_address", "")
        best_place_id = d.get("best_place_id") or rep.get("best_place_id", "")
        best_loc_type = d.get("best_location_type") or rep.get("best_location_type", "")
        best_partial = d.get("best_partial_match") or rep.get("best_partial_match", "")

        if decision == "manual":
            coords = parse_coords(d.get("note", ""))
            if not coords:
                print(f"WARN: {row_id} manual decision without lat,lng in note — skipped", file=sys.stderr)
                continue
            new_lat, new_lng = coords
            new_fa = best_fa or row["formatted_address"]
            new_place_id = best_place_id or row["place_id"]
            new_location_type = "ROOFTOP"
            new_partial = ""
        elif decision == "accept_best":
            new_lat = d.get("best_lat") or rep.get("best_lat", "")
            new_lng = d.get("best_lng") or rep.get("best_lng", "")
            new_fa = best_fa
            new_place_id = best_place_id
            new_location_type = best_loc_type
            new_partial = best_partial
        else:
            print(f"WARN: {row_id} unknown decision {decision!r} — skipped", file=sys.stderr)
            continue

        if not row.get("original_lat"):
            row["original_lat"] = row["lat"]
            row["original_lng"] = row["lng"]
            row["original_formatted_address"] = row["formatted_address"]
            row["original_place_id"] = row["place_id"]
            row["original_partial_match"] = row["partial_match"]
            row["original_location_type"] = row["location_type"]

        row["lat"] = new_lat
        row["lng"] = new_lng
        row["formatted_address"] = new_fa
        row["place_id"] = new_place_id
        row["location_type"] = new_location_type
        row["partial_match"] = new_partial
        row["final_status"] = "publish_ready"
        row["publish_policy"] = "publish"
        row["repair_applied"] = "true"
        row["repair_source"] = "manual_triage"
        if decision == "manual":
            row["repair_outcome"] = "manual_override"
        applied += 1
        print(f"applied {decision:12s} {row_id}  ->  {new_lat}, {new_lng}")

    with MASTER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{applied} row(s) applied, master CSV rewritten.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: apply_manual_triage.py <decisions.csv>", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1])))
