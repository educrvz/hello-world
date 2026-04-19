#!/usr/bin/env python3
"""Apply the repair outcomes from `high_risk_repair_best_attempts.csv` on top
of `master_geocoded.csv`.

Rules:

- For rows with `repair_outcome == improved_confidently`: overwrite the active
  geocode fields with the repaired best values, archive the pre-repair values
  into `original_*` audit columns, and mark `final_status = publish_ready`.
- For rows with any other outcome (or high-risk rows not in the repair queue):
  preserve the current geocode fields verbatim and set
  `final_status = manual_review_pending_external`.
- `auto_accept_v3` rows become `publish_ready`.
- `watchlist_v3` rows become `watchlist`.
- `retry_queue_v3` rows become `retry_queue`.

Outputs:
    build/master_geocoded_patched_v1.csv   (full 2,271 rows with audit columns)
    build/publish_ready_v1.csv             (final_status == publish_ready)
    build/review_queue_v1.csv              (watchlist + retry_queue + manual_review_pending_external)
    reports/09c_apply_repairs_summary.md

Idempotent; safe to re-run.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"

MASTER = BUILD / "master_geocoded.csv"
REPAIRS = BUILD / "high_risk_repair_best_attempts.csv"
V3_ACCEPT = BUILD / "geocode_auto_accept_v3.csv"
V3_WATCH = BUILD / "geocode_watchlist_v3.csv"
V3_RETRY = BUILD / "geocode_retry_queue_v3.csv"
V3_HIGH = BUILD / "geocode_manual_review_high_risk_v3.csv"

OUT_PATCHED = BUILD / "master_geocoded_patched_v1.csv"
OUT_PUBLISH = BUILD / "publish_ready_v1.csv"
OUT_REVIEW = BUILD / "review_queue_v1.csv"
REPORT = REPORTS / "09c_apply_repairs_summary.md"

AUDIT_COLS = [
    "original_formatted_address", "original_lat", "original_lng",
    "original_place_id", "original_partial_match", "original_location_type",
    "original_review_reasons",
]
PATCH_COLS = ["repair_applied", "repair_source", "repair_outcome",
              "final_status", "publish_policy"]


def _strip_accents_lower(s: str) -> str:
    nkfd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nkfd if not unicodedata.combining(c)).lower()


def _muni_in_fa(municipality: str, fa: str) -> bool:
    return bool(municipality and fa) and (
        _strip_accents_lower(municipality) in _strip_accents_lower(fa)
    )


def _fa_segment_count(fa: str) -> int:
    if not fa:
        return 0
    return len([p for p in fa.split(",") if p.strip()])


def compute_publish_policy(row: dict) -> str:
    """Decide whether a row should be included in the production
    `hospitals.json`, and tag the reason.

    Returns one of:
      publish               — include in app (tier set by build_app_hospitals_json.py)
      hide_state_only       — formatted_address is just "State, Brasil" (pin would land in middle of state)
      hide_muni_mismatch    — municipality missing from FA AND we haven't confirmed a UF match; pin likely in wrong city
      hide_external_review  — manual_review_pending_external (external lookup required)
      hide_unknown          — no final_status assigned yet (should not happen)
    """
    final_status = (row.get("final_status") or "").strip()
    if final_status == "publish_ready":
        return "publish"
    if final_status == "manual_review_pending_external":
        return "hide_external_review"

    fa = (row.get("formatted_address") or "").strip()
    muni = (row.get("municipality") or "").strip()

    # Only bucket watchlist + retry_queue through the safety heuristic
    if final_status in ("watchlist", "retry_queue"):
        segments = _fa_segment_count(fa)
        if segments <= 2:
            return "hide_state_only"
        if _muni_in_fa(muni, fa):
            return "publish"
        return "hide_muni_mismatch"

    return "hide_unknown"


def load_bucket_assignments() -> tuple[dict[str, str], dict[str, str]]:
    """Return (v3_bucket_by_row_id, v3_reasons_by_row_id)."""
    bucket_by_id: dict[str, str] = {}
    reasons_by_id: dict[str, str] = {}
    for path, label in [
        (V3_ACCEPT, "auto_accept"),
        (V3_WATCH, "watchlist"),
        (V3_RETRY, "retry_queue"),
        (V3_HIGH, "manual_review_high_risk"),
    ]:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                rid = r.get("row_id")
                if not rid:
                    continue
                bucket_by_id[rid] = label
                reasons_by_id[rid] = r.get("review_reasons", "")
    return bucket_by_id, reasons_by_id


def load_repairs() -> dict[str, dict]:
    if not REPAIRS.exists():
        return {}
    with REPAIRS.open(encoding="utf-8", newline="") as fh:
        return {r["row_id"]: r for r in csv.DictReader(fh)}


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    if not MASTER.exists():
        raise SystemExit(f"missing input: {MASTER}")

    v3_bucket, v3_reasons = load_bucket_assignments()
    repairs = load_repairs()

    with MASTER.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        input_cols = list(reader.fieldnames or [])
        master_rows = list(reader)

    out_cols = input_cols + [c for c in AUDIT_COLS + PATCH_COLS if c not in input_cols]

    patched_rows: list[dict] = []
    applied_log: list[dict] = []
    final_status_counts: Counter = Counter()

    for row in master_rows:
        rid = row["row_id"]
        bucket = v3_bucket.get(rid, "unknown")
        out = dict(row)
        for c in AUDIT_COLS:
            out[c] = ""
        out["repair_applied"] = "false"
        out["repair_source"] = ""
        out["repair_outcome"] = ""

        rep = repairs.get(rid)
        applied = rep is not None and rep.get("repair_outcome") == "improved_confidently"

        if applied:
            out["original_formatted_address"] = row.get("formatted_address", "")
            out["original_lat"] = row.get("lat", "")
            out["original_lng"] = row.get("lng", "")
            out["original_place_id"] = row.get("place_id", "")
            out["original_partial_match"] = row.get("partial_match", "")
            out["original_location_type"] = row.get("location_type", "")
            out["original_review_reasons"] = v3_reasons.get(rid, "")
            out["formatted_address"] = rep["best_formatted_address"]
            out["lat"] = rep["best_lat"]
            out["lng"] = rep["best_lng"]
            out["place_id"] = rep["best_place_id"]
            out["partial_match"] = rep["best_partial_match"]
            out["location_type"] = rep["best_location_type"]
            out["repair_applied"] = "true"
            out["repair_source"] = "high_risk_repair_v1"
            out["repair_outcome"] = "improved_confidently"
            out["final_status"] = "publish_ready"
            applied_log.append({
                "row_id": rid,
                "old_fa": row.get("formatted_address", ""),
                "new_fa": rep["best_formatted_address"],
                "old_lt": row.get("location_type", ""),
                "new_lt": rep["best_location_type"],
            })
        elif bucket == "manual_review_high_risk":
            out["final_status"] = "manual_review_pending_external"
            if rep:
                out["repair_outcome"] = rep.get("repair_outcome", "")
        elif bucket == "auto_accept":
            out["final_status"] = "publish_ready"
        elif bucket == "watchlist":
            out["final_status"] = "watchlist"
        elif bucket == "retry_queue":
            out["final_status"] = "retry_queue"
        else:
            out["final_status"] = "unknown"

        out["publish_policy"] = compute_publish_policy(out)
        final_status_counts[out["final_status"]] += 1
        patched_rows.append(out)

    _write_csv(OUT_PATCHED, out_cols, patched_rows)
    _write_csv(
        OUT_PUBLISH, out_cols,
        [r for r in patched_rows if r["final_status"] == "publish_ready"],
    )
    _write_csv(
        OUT_REVIEW, out_cols,
        [r for r in patched_rows if r["final_status"] in
         ("watchlist", "retry_queue", "manual_review_pending_external")],
    )

    publish_policy_counts = Counter(r["publish_policy"] for r in patched_rows)
    _write_report(patched_rows, applied_log, final_status_counts,
                  publish_policy_counts, v3_bucket)

    print(f"Patched master: {len(patched_rows):,} rows")
    for k in ("publish_ready", "watchlist", "retry_queue", "manual_review_pending_external"):
        print(f"  {k}: {final_status_counts.get(k, 0):,}")
    print(f"Repairs applied: {len(applied_log)}")
    print("Publish policy:")
    for k in ("publish", "hide_state_only", "hide_muni_mismatch",
              "hide_external_review", "hide_unknown"):
        print(f"  {k}: {publish_policy_counts.get(k, 0):,}")
    return 0


def _write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_report(patched_rows, applied_log, status_counts,
                  publish_policy_counts, v3_bucket) -> None:
    lines: list[str] = []
    lines.append("# Apply Repairs — Summary")
    lines.append("")
    lines.append(f"**Patched master:** `{OUT_PATCHED.relative_to(ROOT)}`")
    lines.append(f"**Publish-ready:** `{OUT_PUBLISH.relative_to(ROOT)}`")
    lines.append(f"**Review queue:**  `{OUT_REVIEW.relative_to(ROOT)}`")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- **Rows in patched master:** {len(patched_rows):,}")
    lines.append(f"- **Repairs applied:** {sum(1 for r in patched_rows if r['repair_applied'] == 'true'):,}")
    lines.append("")
    lines.append("## `final_status` distribution")
    lines.append("")
    lines.append("| final_status | Rows |")
    lines.append("|--------------|-----:|")
    for k in ("publish_ready", "watchlist", "retry_queue", "manual_review_pending_external"):
        lines.append(f"| `{k}` | {status_counts.get(k, 0):,} |")
    other = {k: v for k, v in status_counts.items()
             if k not in ("publish_ready", "watchlist", "retry_queue", "manual_review_pending_external")}
    for k, v in other.items():
        lines.append(f"| `{k}` | {v} |")
    lines.append(f"| **Total** | **{sum(status_counts.values()):,}** |")
    lines.append("")
    lines.append("## `publish_policy` distribution")
    lines.append("")
    lines.append("| publish_policy | Rows |")
    lines.append("|----------------|-----:|")
    for k in ("publish", "hide_state_only", "hide_muni_mismatch",
              "hide_external_review", "hide_unknown"):
        lines.append(f"| `{k}` | {publish_policy_counts.get(k, 0):,} |")
    lines.append(
        f"| **Total ready for hospitals.json** | **{publish_policy_counts.get('publish', 0):,}** |"
    )
    lines.append("")
    lines.append("## PR_0031 status")
    lines.append("")
    pr = next((r for r in patched_rows if r["row_id"] == "PR_0031"), None)
    if pr:
        lines.append(f"- `repair_applied = {pr['repair_applied']}`")
        lines.append(f"- `final_status = {pr['final_status']}`")
        lines.append(f"- `repair_outcome = {pr['repair_outcome'] or '—'}`")
    lines.append("")
    lines.append(f"## 13 repaired rows — old vs new ({len(applied_log)} applied)")
    lines.append("")
    lines.append("| row_id | old formatted_address | new formatted_address | old location_type | new location_type |")
    lines.append("|--------|-----------------------|-----------------------|-------------------|-------------------|")
    for e in applied_log:
        old_fa = (e["old_fa"] or "").replace("|", "\\|")[:55]
        new_fa = (e["new_fa"] or "").replace("|", "\\|")[:55]
        lines.append(f"| `{e['row_id']}` | {old_fa} | {new_fa} | `{e['old_lt']}` | `{e['new_lt']}` |")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
