#!/usr/bin/env python3
"""Merge every per-state JSON file in extracted/ into one master dataset.

- Reads every *.json file from extracted/
- Preserves original record fields exactly as they appear
- Adds three provenance fields to every row:
    row_id              stable positional ID, e.g. "SP_0042"
    source_state_file   filename, e.g. "SP.json"
    source_state_abbr   2-letter UF code derived from the filename stem
- Writes build/master_raw.jsonl (one record per line, full fidelity)
- Writes build/master_raw.csv   (antivenoms_raw serialized as "A|B|C")
- Writes reports/03_merge_summary.md
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "extracted"
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"

EXPECTED_UFS = {
    "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
    "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
}

CANONICAL_FIELDS = [
    "state","municipality","health_unit_name","address",
    "phones_raw","cnes","antivenoms_raw","source_notes",
]
ADDED_FIELDS = ["row_id","source_state_file","source_state_abbr"]
CSV_COLUMNS = ADDED_FIELDS + CANONICAL_FIELDS


def serialize_antivenoms_for_csv(value):
    if isinstance(value, list):
        return "|".join(value)
    if value is None:
        return ""
    return str(value)


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    files = sorted(EXTRACTED.glob("*.json"))
    merged_rows: list[dict] = []
    per_state_count: dict[str, int] = {}
    skipped: list[tuple[str, str]] = []
    parse_errors: list[tuple[str, str]] = []

    for path in files:
        abbr = path.stem.upper()
        if abbr not in EXPECTED_UFS:
            skipped.append((path.name, f"stem '{path.stem}' is not a recognized UF code"))
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as e:
            parse_errors.append((path.name, f"JSON decode error: {e}"))
            continue
        if not isinstance(data, list):
            parse_errors.append((path.name, f"top-level is {type(data).__name__}, expected list"))
            continue

        file_rows = 0
        for i, rec in enumerate(data, start=1):
            if not isinstance(rec, dict):
                parse_errors.append((path.name, f"record index {i} is not a dict ({type(rec).__name__})"))
                continue
            row = dict(rec)
            row["row_id"] = f"{abbr}_{i:04d}"
            row["source_state_file"] = path.name
            row["source_state_abbr"] = abbr
            merged_rows.append(row)
            file_rows += 1
        per_state_count[abbr] = file_rows

    jsonl_path = BUILD / "master_raw.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in merged_rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")

    csv_path = BUILD / "master_raw.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in merged_rows:
            out = dict(row)
            out["antivenoms_raw"] = serialize_antivenoms_for_csv(out.get("antivenoms_raw"))
            for k in CSV_COLUMNS:
                if out.get(k) is None:
                    out[k] = ""
            writer.writerow(out)

    missing_ufs = sorted(EXPECTED_UFS - set(per_state_count.keys()))
    unique_ids = {r["row_id"] for r in merged_rows}

    lines: list[str] = []
    lines.append("# Merge Run Summary")
    lines.append("")
    lines.append(f"**Source folder:** `{EXTRACTED}`")
    lines.append(f"**Output JSONL:** `{jsonl_path}`")
    lines.append(f"**Output CSV:**   `{csv_path}`")
    lines.append("")
    lines.append(f"**Files merged:** {len(per_state_count)}")
    lines.append(f"**Files skipped:** {len(skipped)}")
    lines.append(f"**Files with parse errors:** {len({n for n,_ in parse_errors})}")
    lines.append(f"**Total rows merged:** {len(merged_rows):,}")
    lines.append(f"**Unique row_ids:** {len(unique_ids):,} " +
                 ("(all rows have distinct IDs)" if len(unique_ids) == len(merged_rows) else "WARNING: duplicate IDs detected"))
    lines.append("")
    lines.append("## Rows per state")
    lines.append("")
    lines.append("| State | Rows |")
    lines.append("|-------|-----:|")
    for abbr in sorted(per_state_count):
        lines.append(f"| {abbr} | {per_state_count[abbr]:,} |")
    lines.append(f"| **Total** | **{len(merged_rows):,}** |")
    lines.append("")
    lines.append("## Missing UF codes")
    lines.append("")
    lines.append(f"_{'None — all 27 Brazilian states present.' if not missing_ufs else 'Missing: ' + ', '.join(missing_ufs)}_")
    lines.append("")
    lines.append("## Skipped files")
    lines.append("")
    if skipped:
        for name, reason in skipped:
            lines.append(f"- `{name}` — {reason}")
    else:
        lines.append("_None._")
    lines.append("")
    lines.append("## Rows / files that failed to parse")
    lines.append("")
    if parse_errors:
        for name, reason in parse_errors:
            lines.append(f"- `{name}` — {reason}")
    else:
        lines.append("_None._")
    lines.append("")

    summary_path = REPORTS / "03_merge_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Merged {len(merged_rows):,} rows from {len(per_state_count)} files")
    print(f"  -> {jsonl_path}")
    print(f"  -> {csv_path}")
    print(f"  -> {summary_path}")
    if skipped:
        print(f"  ({len(skipped)} file(s) skipped)")
    if parse_errors:
        print(f"  ({len(parse_errors)} parse error(s) — see summary)")


if __name__ == "__main__":
    main()
