#!/usr/bin/env python3
"""Rebuild and validate final pipeline artifacts from the patched master CSV.

This stage intentionally runs *after* committed manual-triage decisions have
been reapplied. `apply_manual_triage.py` mutates
`build/master_geocoded_patched_v1.csv`; this script then derives every
downstream queue/export from that final master so stale pre-triage artifacts
cannot survive a refresh.

Outputs:
    build/publish_ready_v1.csv
    build/review_queue_v1.csv
    build/google_sheets_publish_ready_v1.csv
    build/google_sheets_review_queue_v1.csv
    reports/10_google_sheets_export_summary.md

Use `--check` to validate already-written artifacts without rewriting them.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"
DATA = ROOT / "data"

MASTER = BUILD / "master_geocoded_patched_v1.csv"
OUT_PUBLISH = BUILD / "publish_ready_v1.csv"
OUT_REVIEW = BUILD / "review_queue_v1.csv"
OUT_SHEETS_PUBLISH = BUILD / "google_sheets_publish_ready_v1.csv"
OUT_SHEETS_REVIEW = BUILD / "google_sheets_review_queue_v1.csv"
OUT_APP = ROOT / "app" / "hospitals.json"
OUT_ROOT = ROOT / "hospitals.json"
OVERRIDES = DATA / "location_overrides.json"
REPORT = REPORTS / "10_google_sheets_export_summary.md"

REVIEW_STATUSES = {"watchlist", "retry_queue", "manual_review_pending_external"}

V3_BUCKETS = {
    "geocode_auto_accept_v3.csv": "auto_accept",
    "geocode_watchlist_v3.csv": "watchlist",
    "geocode_retry_queue_v3.csv": "retry_queue",
    "geocode_manual_review_high_risk_v3.csv": "manual_review_high_risk",
}

SHEETS_COLS = [
    "row_id", "source_state_abbr", "state", "municipality", "health_unit_name",
    "address", "phones_raw", "cnes", "antivenoms_raw", "geocode_query",
    "formatted_address", "lat", "lng", "place_id", "partial_match",
    "location_type", "geocode_status", "final_status",
    "repair_applied", "repair_source", "repair_outcome",
    "review_status", "review_reasons",
]
NULL_LITS = {"null", "None", "NULL", "nan", "NaN"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def partition_rows(master_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    publish = [r for r in master_rows if r.get("final_status") == "publish_ready"]
    review = [r for r in master_rows if r.get("final_status") in REVIEW_STATUSES]
    return publish, review


def load_review_metadata() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for filename, bucket in V3_BUCKETS.items():
        path = BUILD / filename
        if not path.exists():
            continue
        _, rows = read_csv(path)
        for row in rows:
            rid = row.get("row_id")
            if rid:
                out[rid] = (bucket, row.get("review_reasons", ""))
    return out


def clean(value: object) -> str:
    s = "" if value is None else str(value).strip()
    return "" if s in NULL_LITS else s


def to_sheets_row(row: dict[str, str], review_metadata: dict[str, tuple[str, str]]) -> dict[str, str]:
    rid = row["row_id"]
    bucket, reasons = review_metadata.get(rid, ("", ""))
    out = {col: clean(row.get(col, "")) for col in SHEETS_COLS}
    antivenoms = out.get("antivenoms_raw", "")
    if antivenoms:
        out["antivenoms_raw"] = ", ".join(
            part.strip() for part in antivenoms.split("|") if part.strip()
        )
    out["review_status"] = bucket
    out["review_reasons"] = reasons
    return out


def load_hidden_override_cnes() -> set[str]:
    if not OVERRIDES.exists():
        return set()
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()
    return {str(cnes) for cnes, value in data.items() if isinstance(value, dict) and value.get("hide")}


def row_has_coords(row: dict[str, str]) -> bool:
    try:
        float(row.get("lat", ""))
        float(row.get("lng", ""))
        return True
    except (TypeError, ValueError):
        return False


def validate_artifacts(master_rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    expected_publish, expected_review = partition_rows(master_rows)
    required_csvs = [OUT_PUBLISH, OUT_REVIEW, OUT_SHEETS_PUBLISH, OUT_SHEETS_REVIEW]
    missing = [path for path in required_csvs if not path.exists()]
    if missing:
        return [f"{path.relative_to(ROOT)} is missing" for path in missing]

    _, publish_rows = read_csv(OUT_PUBLISH)
    _, review_rows = read_csv(OUT_REVIEW)
    _, sheets_publish_rows = read_csv(OUT_SHEETS_PUBLISH)
    _, sheets_review_rows = read_csv(OUT_SHEETS_REVIEW)

    def ids(rows: list[dict[str, str]]) -> set[str]:
        return {r.get("row_id", "") for r in rows}

    if ids(publish_rows) != ids(expected_publish):
        errors.append("build/publish_ready_v1.csv does not match final_status=publish_ready")
    if ids(review_rows) != ids(expected_review):
        errors.append("build/review_queue_v1.csv does not match final review statuses")
    if ids(sheets_publish_rows) != ids(publish_rows):
        errors.append("google_sheets_publish_ready_v1.csv does not match publish_ready_v1.csv")
    if ids(sheets_review_rows) != ids(review_rows):
        errors.append("google_sheets_review_queue_v1.csv does not match review_queue_v1.csv")

    unknown = [r["row_id"] for r in master_rows if r.get("final_status") not in REVIEW_STATUSES | {"publish_ready"}]
    if unknown:
        errors.append(f"{len(unknown)} master row(s) have unexpected final_status")

    if OUT_APP.exists() and OUT_ROOT.exists():
        app_data = json.loads(OUT_APP.read_text(encoding="utf-8"))
        root_data = json.loads(OUT_ROOT.read_text(encoding="utf-8"))
        if app_data != root_data:
            errors.append("app/hospitals.json and hospitals.json differ")
        hidden_cnes = load_hidden_override_cnes()
        expected_app_rows = [
            r for r in master_rows
            if r.get("publish_policy") == "publish"
            and row_has_coords(r)
            and str(r.get("cnes", "")) not in hidden_cnes
        ]
        if len(app_data) != len(expected_app_rows):
            errors.append(
                "app/hospitals.json row count does not match publish_policy=publish "
                "minus hidden overrides"
            )
        app_cnes = Counter(str(row.get("cnes", "")) for row in app_data)
        expected_cnes = Counter(str(row.get("cnes", "")) for row in expected_app_rows)
        if app_cnes != expected_cnes:
            errors.append(
                "app/hospitals.json CNES multiset does not match published master rows"
            )

    return errors


def write_report(publish_rows: list[dict[str, str]], review_rows: list[dict[str, str]]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    review_counts: dict[str, int] = {}
    for row in review_rows:
        status = row.get("final_status", "")
        review_counts[status] = review_counts.get(status, 0) + 1

    lines = [
        "# Google Sheets Export Summary",
        "",
        "Generated from the final patched master after committed manual-triage decisions.",
        "",
        "## Files produced",
        "",
        "| Tab | CSV path | Rows |",
        "|-----|----------|-----:|",
        f"| `publish_ready` | [`build/google_sheets_publish_ready_v1.csv`](../build/google_sheets_publish_ready_v1.csv) | {len(publish_rows):,} |",
        f"| `review_queue`  | [`build/google_sheets_review_queue_v1.csv`](../build/google_sheets_review_queue_v1.csv)   | {len(review_rows):,} |",
        "",
        "Both files:",
        "- UTF-8 encoded, CRLF line endings via Python's `csv` module.",
        "- Accents preserved.",
        "- `antivenoms_raw` flattened from pipe-joined (`A|B|C`) to comma-joined (`A, B, C`) for readability.",
        "- Empty/null-like values exported as blank cells.",
        "",
        "## Row-level invariants verified",
        "",
        "- `publish_ready_v1.csv` is derived from `final_status = publish_ready` in the final master.",
        "- `review_queue_v1.csv` is derived from watchlist, retry_queue, and manual external-review rows in the final master.",
        "- Google Sheets exports have the same `row_id` sets as their source queues.",
        "",
        "## Review queue composition",
        "",
        "| final_status | Rows |",
        "|--------------|-----:|",
    ]
    for status in ("retry_queue", "watchlist", "manual_review_pending_external"):
        lines.append(f"| `{status}` | {review_counts.get(status, 0):,} |")
    lines.append(f"| **Total** | **{len(review_rows):,}** |")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def rebuild() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fieldnames, master_rows = read_csv(MASTER)
    publish_rows, review_rows = partition_rows(master_rows)
    review_metadata = load_review_metadata()

    write_csv(OUT_PUBLISH, fieldnames, publish_rows)
    write_csv(OUT_REVIEW, fieldnames, review_rows)
    write_csv(
        OUT_SHEETS_PUBLISH,
        SHEETS_COLS,
        [to_sheets_row(row, review_metadata) for row in publish_rows],
    )
    write_csv(
        OUT_SHEETS_REVIEW,
        SHEETS_COLS,
        [to_sheets_row(row, review_metadata) for row in review_rows],
    )
    write_report(publish_rows, review_rows)
    return master_rows, publish_rows, review_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate existing artifacts without rewriting")
    args = parser.parse_args(argv)

    if args.check:
        _, master_rows = read_csv(MASTER)
        publish_rows = []
        review_rows = []
    else:
        master_rows, publish_rows, review_rows = rebuild()

    errors = validate_artifacts(master_rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.check:
        print("Final artifact invariants OK.")
    else:
        print(f"Wrote {len(publish_rows):,} publish rows and {len(review_rows):,} review rows.")
        print("Final artifact invariants OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
