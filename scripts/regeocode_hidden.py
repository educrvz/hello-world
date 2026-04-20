"""Ad-hoc geocode pass for a list of row_ids.

For each row in master_geocoded_patched_v1.csv whose row_id is on the CLI,
try a handful of candidate queries against Google Maps and print the best
result (by a simple signal: has street number > has street > contains muni).

Usage:  python3 scripts/regeocode_hidden.py PA_0007 PA_0029 PA_0054 ...
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"


def api_key() -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", "google_maps_api_key", "-a",
         subprocess.check_output(["whoami"]).decode().strip(), "-w"]
    ).decode().strip()


KEY = api_key()


def geocode(query: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(
        {"address": query, "region": "br", "components": "country:BR", "key": KEY}
    )
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def score(result: dict, muni: str) -> int:
    """Quick heuristic: more specific = higher score."""
    if not result:
        return 0
    loc_type = result.get("geometry", {}).get("location_type", "")
    tier = {"ROOFTOP": 100, "RANGE_INTERPOLATED": 70, "GEOMETRIC_CENTER": 40, "APPROXIMATE": 10}.get(loc_type, 0)
    fa = result.get("formatted_address", "")
    if muni and muni.lower()[:5] in fa.lower():
        tier += 20
    # Penalize if FA is just "City, State, Brasil" (3 commas or fewer)
    if fa.count(",") < 3:
        tier -= 20
    return tier


def build_queries(row: dict) -> list[tuple[str, str]]:
    name = row["health_unit_name"]
    muni = row["municipality"]
    uf = row["source_state_abbr"]
    addr = row.get("address", "").strip()
    cnes = row.get("cnes", "").strip()

    queries = []
    if addr:
        queries.append(("addr+muni+uf", f"{addr}, {muni}, {uf}, Brasil"))
    queries.append(("name+muni+uf", f"{name}, {muni}, {uf}, Brasil"))
    if addr:
        queries.append(("name+addr+muni+uf", f"{name}, {addr}, {muni}, {uf}, Brasil"))
    if cnes:
        queries.append(("cnes+name", f"CNES {cnes} {name}, {muni}, {uf}, Brasil"))
    queries.append(("name+uf", f"{name}, {uf}, Brasil"))
    return queries


def main(row_ids: list[str]) -> int:
    with MASTER.open() as f:
        rows = {r["row_id"]: r for r in csv.DictReader(f)}

    out = []
    for rid in row_ids:
        row = rows.get(rid)
        if not row:
            print(f"WARN: {rid} not found", file=sys.stderr)
            continue
        print(f"\n=== {rid}: {row['health_unit_name']} ({row['municipality']}) ===")
        print(f"    old pin: {row['lat']}, {row['lng']}  ({row['formatted_address']})")

        best = None
        best_score = -999
        best_label = ""
        for label, q in build_queries(row):
            resp = geocode(q)
            if resp.get("status") != "OK" or not resp.get("results"):
                print(f"    {label:22s}  [{resp.get('status')}] {q[:80]}")
                continue
            r0 = resp["results"][0]
            s = score(r0, row["municipality"])
            fa = r0.get("formatted_address", "")
            lt = r0.get("geometry", {}).get("location_type", "")
            print(f"    {label:22s}  score={s:3d} [{lt}] {fa[:90]}")
            if s > best_score:
                best_score = s
                best = r0
                best_label = label

        if best:
            loc = best["geometry"]["location"]
            out.append({
                "row_id": rid,
                "name": row["health_unit_name"],
                "municipality": row["municipality"],
                "old_lat": row["lat"],
                "old_lng": row["lng"],
                "old_fa": row["formatted_address"],
                "best_lat": loc["lat"],
                "best_lng": loc["lng"],
                "best_fa": best.get("formatted_address", ""),
                "best_location_type": best.get("geometry", {}).get("location_type", ""),
                "best_place_id": best.get("place_id", ""),
                "best_query_label": best_label,
                "best_score": best_score,
            })

    out_path = ROOT / "build" / "pa_regeocode_candidates.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
