"""Places API (New) rescue pass for hidden hospital rows.

For every row in build/master_geocoded_patched_v1.csv where
`publish_policy != 'publish'`, call Places Text Search with queries anchored on
the hospital *name* (not the address, which is what the Geocoding API already
tried). Auto-grade the best hit into HIGH / MEDIUM / LOW; auto-apply HIGH hits
to the master CSV; route MEDIUM/LOW into a candidates JSON for the existing
triage HTML viewer.

Outputs:
  build/places_candidates.json              (MEDIUM/LOW, for triage HTML)
  build/places_raw_responses.jsonl          (audit trail; one JSON per call)
  data/manual_triage/{UF}_{DATE}_places_auto.csv
                                             (HIGH rows; applied via apply_manual_triage.py)

Durable path policy: HIGH auto-apply CSVs go under data/manual_triage/ so they
survive a from-scratch pipeline refresh (see apply_manual_triage.py docstring
§15-20 and refresh_dataset.sh stage 09f).

Usage:
  python3 scripts/places_lookup_hidden.py                   # all 122 hidden rows
  python3 scripts/places_lookup_hidden.py --ufs MG,PR,BA    # filter by state
  python3 scripts/places_lookup_hidden.py --only PA_0007,PA_0029,PA_0054 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"
RAW_LOG = ROOT / "build" / "places_raw_responses.jsonl"
CANDIDATES = ROOT / "build" / "places_candidates.json"
TRIAGE_DIR = ROOT / "data" / "manual_triage"

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.location,places.types,places.primaryType"
)
HEALTH_TYPES = {"hospital", "doctor", "health", "medical_lab", "physiotherapist"}
DEFAULT_BIAS_RADIUS_M = 25_000
SLEEP_S = 0.05  # ~20 QPS, well under Places 600 QPM default


def read_api_key() -> str:
    if os.environ.get("GOOGLE_MAPS_API_KEY"):
        return os.environ["GOOGLE_MAPS_API_KEY"]
    user = subprocess.check_output(["whoami"]).decode().strip()
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", "google_maps_api_key",
         "-a", user, "-w"]
    ).decode().strip()


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def places_search(key: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        PLACES_URL, method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes)
        except json.JSONDecodeError:
            return e.code, {"error": body_bytes.decode("utf-8", errors="replace")}


def build_queries(row: dict) -> list[tuple[str, dict]]:
    """Return (label, request_body) pairs, ordered by preference."""
    name = row["health_unit_name"].strip()
    muni = row["municipality"].strip()
    uf = row["source_state_abbr"].strip()
    cnes = (row.get("cnes") or "").strip()
    try:
        old_lat = float(row["lat"])
        old_lng = float(row["lng"])
        has_pin = True
    except (TypeError, ValueError):
        has_pin = False

    def body(text: str, *, include_hospital: bool, with_bias: bool) -> dict:
        b: dict = {
            "textQuery": text,
            "languageCode": "pt-BR",
            "regionCode": "BR",
            "maxResultCount": 5,
        }
        if include_hospital:
            b["includedType"] = "hospital"
            b["strictTypeFiltering"] = False
        if with_bias and has_pin:
            b["locationBias"] = {"circle": {
                "center": {"latitude": old_lat, "longitude": old_lng},
                "radius": float(DEFAULT_BIAS_RADIUS_M),
            }}
        return b

    base = f"{name}, {muni}, {uf}, Brasil"
    queries: list[tuple[str, dict]] = [
        ("places:name+muni+uf:hospital+bias", body(base, include_hospital=True, with_bias=True)),
        ("places:name+muni+uf:any+bias", body(base, include_hospital=False, with_bias=True)),
        ("places:name+muni+uf:any+nobias", body(base, include_hospital=False, with_bias=False)),
    ]
    if cnes:
        cnes_q = f"CNES {cnes} {name}, {muni}, {uf}"
        queries.append(("places:cnes+name+muni+uf:any+nobias",
                        body(cnes_q, include_hospital=False, with_bias=False)))
    return queries


def pick_best(places: list[dict], muni: str, uf: str,
              old_lat: float | None, old_lng: float | None) -> dict | None:
    """Score each place and return the best (with attached score metadata)."""
    best = None
    best_score = -999
    for p in places:
        loc = p.get("location") or {}
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        if lat is None or lng is None:
            continue
        fa = p.get("formattedAddress", "")
        primary = p.get("primaryType", "")
        types = p.get("types") or []

        score = 0
        reasons = []
        if primary == "hospital" or "hospital" in types:
            score += 2
            reasons.append("hospital type")
        elif HEALTH_TYPES.intersection(types):
            score += 1
            reasons.append(f"{next(iter(HEALTH_TYPES.intersection(types)))} type")
        if muni and muni.lower()[:5] in fa.lower():
            score += 2
            reasons.append("muni match")
        if uf and (f" - {uf}," in fa or f", {uf}," in fa or f" {uf} " in fa or fa.endswith(f" {uf}")):
            score += 1
            reasons.append("UF in FA")
        dist_km = None
        if old_lat is not None and old_lng is not None:
            dist_km = haversine_km(old_lat, old_lng, float(lat), float(lng))
            if dist_km <= 10:
                score += 1
                reasons.append(f"{dist_km:.1f}km from old")
            elif dist_km > 50:
                score -= 3
                reasons.append(f"{dist_km:.0f}km away (penalty)")

        if score > best_score:
            best_score = score
            best = {
                "place": p,
                "lat": lat,
                "lng": lng,
                "fa": fa,
                "primary_type": primary,
                "types": types,
                "score": score,
                "dist_km": dist_km,
                "reasons": ", ".join(reasons) or "no signals",
            }
    return best


def grade(best: dict | None, muni: str) -> tuple[str, str]:
    if best is None:
        return "low", "no Places hit"
    score = best["score"]
    dist = best["dist_km"]
    muni_match = muni and muni.lower()[:5] in best["fa"].lower()
    if score >= 5 and muni_match and (dist is None or dist <= 15):
        return "high", best["reasons"]
    if score >= 3:
        return "medium", best["reasons"]
    return "low", best["reasons"]


def synth_location_type(best: dict | None) -> str:
    if best is None:
        return ""
    if best["primary_type"] == "hospital" or HEALTH_TYPES.intersection(best.get("types") or []):
        return "ROOFTOP"
    return "GEOMETRIC_CENTER"


def process_row(key: str, row: dict, raw_log) -> dict:
    name = row["health_unit_name"]
    muni = row["municipality"]
    uf = row["source_state_abbr"]
    try:
        old_lat = float(row["lat"])
        old_lng = float(row["lng"])
    except (TypeError, ValueError):
        old_lat = old_lng = None

    out_best = None
    best_label = ""
    for label, body in build_queries(row):
        status, resp = places_search(key, body)
        raw_log.write(json.dumps({
            "row_id": row["row_id"], "label": label,
            "status": status, "query": body.get("textQuery"),
            "response": resp,
        }, ensure_ascii=False) + "\n")
        raw_log.flush()
        time.sleep(SLEEP_S)

        if status == 403:
            raise SystemExit(
                "Places API returned 403. Enable it on the key's GCP project:\n"
                "  gcloud services enable places-backend.googleapis.com\n"
                "or in the Cloud Console: APIs & Services → Library → 'Places API (New)'."
            )
        if status != 200:
            continue
        places = resp.get("places") or []
        if not places:
            continue
        cand = pick_best(places, muni, uf, old_lat, old_lng)
        if cand is None:
            continue
        cand["label"] = label
        if out_best is None or cand["score"] > out_best["score"]:
            out_best = cand
            best_label = label
        if out_best and out_best["score"] >= 5:
            break  # short-circuit: HIGH-quality hit

    g, rationale = grade(out_best, muni)
    return {
        "row_id": row["row_id"],
        "uf": uf,
        "name": name,
        "municipality": muni,
        "old_lat": row.get("lat", ""),
        "old_lng": row.get("lng", ""),
        "old_fa": row.get("formatted_address", ""),
        "best_lat": str(out_best["lat"]) if out_best else "",
        "best_lng": str(out_best["lng"]) if out_best else "",
        "best_fa": out_best["fa"] if out_best else "",
        "best_location_type": synth_location_type(out_best),
        "best_place_id": out_best["place"].get("id", "") if out_best else "",
        "best_query_label": best_label,
        "best_score": out_best["score"] if out_best else 0,
        "best_types": (out_best.get("types") if out_best else []) or [],
        "distance_km": out_best.get("dist_km") if out_best else None,
        "grade": g,
        "grade_rationale": rationale,
    }


def write_auto_apply(by_uf: dict[str, list[dict]]) -> list[Path]:
    """Write one CSV per UF containing HIGH rows as accept_best decisions."""
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    paths = []
    cols = ["row_id", "uf", "name", "municipality", "outcome", "decision",
            "best_lat", "best_lng", "note",
            "best_formatted_address", "best_place_id", "best_location_type"]
    for uf, rows in sorted(by_uf.items()):
        if not rows:
            continue
        path = TRIAGE_DIR / f"{uf}_{today}_places_auto.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({
                    "row_id": r["row_id"], "uf": r["uf"],
                    "name": r["name"], "municipality": r["municipality"],
                    "outcome": f"places_high:{r['grade_rationale']}",
                    "decision": "accept_best",
                    "best_lat": r["best_lat"], "best_lng": r["best_lng"],
                    "note": "",
                    "best_formatted_address": r["best_fa"],
                    "best_place_id": r["best_place_id"],
                    "best_location_type": r["best_location_type"],
                })
        paths.append(path)
    return paths


def apply_csvs(paths: list[Path]) -> None:
    applier = ROOT / "scripts" / "apply_manual_triage.py"
    for p in paths:
        print(f"\n--> applying {p.relative_to(ROOT)}")
        subprocess.check_call(["python3", str(applier), str(p)])


def load_hidden(only: set[str] | None, ufs: set[str] | None,
                include_published: bool) -> list[dict]:
    with MASTER.open() as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if not include_published and r.get("publish_policy", "") == "publish":
            continue
        if only and r["row_id"] not in only:
            continue
        if ufs and r["source_state_abbr"] not in ufs:
            continue
        out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated row_ids; overrides --ufs")
    ap.add_argument("--ufs", help="comma-separated UFs to include")
    ap.add_argument("--dry-run", action="store_true",
                    help="write candidates JSON only; skip auto-apply")
    ap.add_argument("--output", default=str(CANDIDATES),
                    help="candidates JSON path (default: build/places_candidates.json)")
    ap.add_argument("--include-published", action="store_true",
                    help="include rows with publish_policy=publish "
                         "(dry-run against ground-truth rows)")
    args = ap.parse_args()

    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    ufs = set(s.strip().upper() for s in args.ufs.split(",")) if args.ufs else None

    key = read_api_key()
    hidden = load_hidden(only, ufs, args.include_published)
    print(f"Processing {len(hidden)} hidden rows ({'dry-run' if args.dry_run else 'live'})...")

    RAW_LOG.parent.mkdir(parents=True, exist_ok=True)
    all_candidates = []
    with RAW_LOG.open("a") as raw_log:
        raw_log.write(json.dumps({"_batch_start": dt.datetime.utcnow().isoformat(),
                                   "n_rows": len(hidden),
                                   "dry_run": args.dry_run}) + "\n")
        for i, row in enumerate(hidden, 1):
            c = process_row(key, row, raw_log)
            all_candidates.append(c)
            dist = f"{c['distance_km']:.1f}km" if c.get("distance_km") is not None else "—"
            print(f"  [{i:3d}/{len(hidden)}] {c['row_id']:<9} {c['grade']:<6} "
                  f"score={c['best_score']:2d} dist={dist:<8} {c['best_fa'][:60]}")

    Path(args.output).write_text(json.dumps(all_candidates, indent=2, ensure_ascii=False))
    print(f"\nWrote {args.output} ({len(all_candidates)} rows)")

    from collections import Counter
    grade_counts = Counter(c["grade"] for c in all_candidates)
    print(f"Grades: {dict(grade_counts)}")

    if args.dry_run:
        print("(dry-run: skipping auto-apply)")
        return 0

    by_uf: dict[str, list[dict]] = {}
    for c in all_candidates:
        if c["grade"] == "high":
            by_uf.setdefault(c["uf"], []).append(c)
    if not by_uf:
        print("No HIGH-grade hits to auto-apply.")
        return 0

    paths = write_auto_apply(by_uf)
    total_high = sum(len(v) for v in by_uf.values())
    print(f"\nAuto-applying {total_high} HIGH rows across {len(by_uf)} UF(s)...")
    apply_csvs(paths)
    print(f"\nAuto-applied: {total_high} rows. Routed to manual triage: "
          f"{sum(grade_counts[g] for g in ('medium', 'low'))} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
