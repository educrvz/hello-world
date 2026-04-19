#!/usr/bin/env python3
"""Geocode the normalized hospital dataset using the Google Maps Geocoding API.

Inputs:  build/master_normalized.csv
Outputs: build/master_geocoded.csv
         build/geocode_raw_responses.jsonl  (appended, one record per attempt)
         reports/06_geocode_smoke_test.md   (when --limit is used)

API key lookup order:
    1. GOOGLE_MAPS_API_KEY environment variable
    2. macOS Keychain entry: service=google_maps_api_key, account=$USER
       (add with: security add-generic-password -s google_maps_api_key \
                    -a "$USER" -w '<your-key>')

Usage:
    python scripts/geocode_hospitals.py --limit 50      # smoke test
    python scripts/geocode_hospitals.py                 # full run
    python scripts/geocode_hospitals.py --no-resume     # re-hit every row

Resume behavior:
    If build/master_geocoded.csv already exists, rows with a terminal
    `geocode_status` (OK, ZERO_RESULTS, INVALID_REQUEST, NOT_ATTEMPTED_EMPTY_QUERY)
    are kept as-is. Rows with a transient error status or no status yet are
    retried. Use --no-resume to re-hit everything.

Never drops rows: every input row appears in the output CSV, even if it
could not be attempted in this run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"
INPUT = BUILD / "master_normalized.csv"
OUTPUT = BUILD / "master_geocoded.csv"
RAW_JSONL = BUILD / "geocode_raw_responses.jsonl"
SMOKE_REPORT = REPORTS / "06_geocode_smoke_test.md"

GEOCODE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
PROVIDER_ID = "google_maps_geocoding_v1"

NEW_COLUMNS = [
    "geocode_status",
    "formatted_address",
    "lat",
    "lng",
    "place_id",
    "partial_match",
    "location_type",
    "result_types",
    "geocode_provider",
    "geocode_attempted_at",
]

TERMINAL_STATUSES = {
    "OK",
    "ZERO_RESULTS",
    "INVALID_REQUEST",
    "NOT_ATTEMPTED_EMPTY_QUERY",
}

MAX_ATTEMPTS = 4
INITIAL_BACKOFF_SECONDS = 2
DEFAULT_INTER_REQUEST_DELAY = 0.05  # ~20 QPS, well under Google's quota

KEYCHAIN_SERVICE = "google_maps_api_key"


def read_api_key() -> str | None:
    """Env var wins; otherwise try macOS Keychain."""
    env = os.environ.get("GOOGLE_MAPS_API_KEY")
    if env:
        return env.strip()
    if sys.platform != "darwin":
        return None
    if shutil.which("security") is None:
        return None
    user = os.environ.get("USER") or ""
    cmd = ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"]
    if user:
        cmd.extend(["-a", user])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    key = result.stdout.strip()
    return key or None


def iso_now() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def fetch_geocode(query: str, api_key: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "address": query,
            "key": api_key,
            "region": "br",
            "language": "pt-BR",
        }
    )
    url = f"{GEOCODE_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "sos-antiveneno-geocoder/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read()
    return json.loads(payload)


def geocode_with_retry(query: str, api_key: str):
    """Returns (status, raw_response_or_None, error_message_or_None)."""
    if not query.strip():
        return "NOT_ATTEMPTED_EMPTY_QUERY", None, None

    backoff = INITIAL_BACKOFF_SECONDS
    last_status = "UNKNOWN_ERROR"
    last_err = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = fetch_geocode(query, api_key)
        except urllib.error.HTTPError as e:
            last_status = "NETWORK_ERROR"
            last_err = f"HTTPError {e.code}"
        except urllib.error.URLError as e:
            last_status = "NETWORK_ERROR"
            last_err = f"URLError {e.reason}"
        except Exception as e:  # noqa: BLE001
            last_status = "NETWORK_ERROR"
            last_err = f"{type(e).__name__}: {e}"
        else:
            last_status = data.get("status", "UNKNOWN_ERROR")
            last_err = data.get("error_message")
            if last_status in TERMINAL_STATUSES:
                return last_status, data, None
            if last_status == "REQUEST_DENIED":
                # API-key / auth problem — retrying won't help
                return last_status, data, last_err

        if attempt < MAX_ATTEMPTS:
            time.sleep(backoff)
            backoff *= 2

    return last_status, None, last_err


def load_prior_rows(path: Path) -> dict:
    """Return {row_id: dict(prior_row)} from a prior output file."""
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            rid = r.get("row_id")
            if rid:
                out[rid] = r
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Smoke test: only attempt the first N rows of the input.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_INTER_REQUEST_DELAY,
        help="Seconds between successive requests.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-attempt every row regardless of prior status.",
    )
    args = parser.parse_args()

    api_key = read_api_key()
    if not api_key:
        sys.stderr.write(
            "ERROR: Google Maps API key not found. Either export "
            "GOOGLE_MAPS_API_KEY or add a Keychain entry with:\n"
            '  security add-generic-password -s google_maps_api_key '
            '-a "$USER" -w \'<your-key>\'\n'
        )
        return 2

    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with INPUT.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        input_cols = list(reader.fieldnames or [])
        all_rows = list(reader)

    total_input_rows = len(all_rows)

    # Rows eligible for attempt in THIS run
    if args.limit is not None:
        attempt_ids = {r["row_id"] for r in all_rows[: args.limit]}
    else:
        attempt_ids = {r["row_id"] for r in all_rows}

    output_cols = input_cols + [c for c in NEW_COLUMNS if c not in input_cols]

    prior_rows = {} if args.no_resume else load_prior_rows(OUTPUT)

    attempted = 0
    succeeded = 0
    failed = 0
    skipped_prior = 0
    status_counts: dict[str, int] = {}
    sample_rows: list[dict] = []
    final_rows: list[dict] = []

    with RAW_JSONL.open("a", encoding="utf-8") as raw_out:
        for row in all_rows:
            out = {c: "" for c in output_cols}
            out.update(row)
            rid = row["row_id"]
            prior = prior_rows.get(rid)

            # Carry forward terminal prior results (resume)
            if prior and prior.get("geocode_status", "") in TERMINAL_STATUSES:
                for c in NEW_COLUMNS:
                    out[c] = prior.get(c, "")
                if rid in attempt_ids:
                    skipped_prior += 1
                final_rows.append(out)
                continue

            if rid not in attempt_ids:
                # Outside this run's attempt set — carry prior (even if transient) or leave blank
                if prior:
                    for c in NEW_COLUMNS:
                        out[c] = prior.get(c, "")
                final_rows.append(out)
                continue

            query = (row.get("geocode_query") or "").strip()
            status, data, err = geocode_with_retry(query, api_key)
            attempted_at = iso_now()
            attempted += 1
            status_counts[status] = status_counts.get(status, 0) + 1

            formatted = lat = lng = place_id = ""
            partial = loc_type = types_str = ""
            if status == "OK" and data and data.get("results"):
                first = data["results"][0]
                loc = first.get("geometry", {}).get("location", {})
                formatted = first.get("formatted_address", "")
                lat = loc.get("lat", "")
                lng = loc.get("lng", "")
                place_id = first.get("place_id", "")
                partial = str(first.get("partial_match", False)).lower()
                loc_type = first.get("geometry", {}).get("location_type", "")
                types_str = "|".join(first.get("types", []) or [])
                succeeded += 1
            else:
                failed += 1

            out["geocode_status"] = status
            out["formatted_address"] = formatted
            out["lat"] = lat
            out["lng"] = lng
            out["place_id"] = place_id
            out["partial_match"] = partial
            out["location_type"] = loc_type
            out["result_types"] = types_str
            out["geocode_provider"] = PROVIDER_ID
            out["geocode_attempted_at"] = attempted_at

            raw_out.write(
                json.dumps(
                    {
                        "row_id": rid,
                        "attempted_at": attempted_at,
                        "query": query,
                        "status": status,
                        "error": err,
                        "response": data,
                    },
                    ensure_ascii=False,
                )
            )
            raw_out.write("\n")

            if len(sample_rows) < 10:
                sample_rows.append(
                    {
                        "row_id": rid,
                        "query": query,
                        "formatted_address": formatted,
                        "status": status,
                    }
                )

            final_rows.append(out)
            time.sleep(args.sleep)

    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_cols, extrasaction="ignore")
        writer.writeheader()
        for row in final_rows:
            writer.writerow(row)

    if args.limit is not None:
        lines: list[str] = []
        lines.append("# Geocode Smoke Test")
        lines.append("")
        lines.append(f"**Input:** `{INPUT}`")
        lines.append(f"**Output:** `{OUTPUT}`")
        lines.append(f"**Raw responses:** `{RAW_JSONL}`")
        lines.append(f"**Provider:** `{PROVIDER_ID}`")
        lines.append(f"**Completed at:** {iso_now()}")
        lines.append("")
        lines.append(f"**Total rows in input:** {total_input_rows:,}")
        lines.append(f"**Row attempt limit:** {args.limit}")
        lines.append(f"**Attempted in this run:** {attempted}")
        lines.append(f"**Skipped (prior terminal status, resume):** {skipped_prior}")
        lines.append(f"**Succeeded (status OK):** {succeeded}")
        lines.append(f"**Failed (non-OK):** {failed}")
        lines.append("")
        lines.append("## Status breakdown")
        lines.append("")
        if status_counts:
            lines.append("| Status | Count |")
            lines.append("|--------|------:|")
            for s in sorted(status_counts, key=lambda k: -status_counts[k]):
                lines.append(f"| `{s}` | {status_counts[s]} |")
        else:
            lines.append("_No rows attempted in this run._")
        lines.append("")
        lines.append("## 10 sample attempted rows")
        lines.append("")
        if sample_rows:
            lines.append("| row_id | status | geocode_query | formatted_address |")
            lines.append("|--------|--------|---------------|-------------------|")
            for s in sample_rows:
                q = (s["query"] or "").replace("|", "\\|")[:110]
                fa = (s["formatted_address"] or "").replace("|", "\\|")[:110]
                lines.append(
                    f"| `{s['row_id']}` | `{s['status']}` | {q} | {fa} |"
                )
        else:
            lines.append("_No rows attempted._")
        lines.append("")
        SMOKE_REPORT.write_text("\n".join(lines), encoding="utf-8")
        print(f"Smoke-test report: {SMOKE_REPORT}")

    print(
        f"Attempted: {attempted} | OK: {succeeded} | Failed: {failed} | "
        f"Resumed: {skipped_prior}"
    )
    print(f"Output:    {OUTPUT}")
    print(f"Raw log:   {RAW_JSONL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
