#!/usr/bin/env python3
"""Normalize the merged hospital dataset for geocoding preparation.

Reads:  build/master_raw.csv
Writes: build/master_normalized.csv
        reports/04_normalization_summary.md

Adds derived columns without overwriting any of the original raw columns.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"
INPUT = BUILD / "master_raw.csv"
OUTPUT = BUILD / "master_normalized.csv"
REPORT = REPORTS / "04_normalization_summary.md"

WHITESPACE = re.compile(r"\s+")

NEW_COLUMNS = [
    "state_clean",
    "municipality_clean",
    "health_unit_name_clean",
    "address_clean",
    "phones_clean",
    "antivenoms_joined",
    "geocode_query",
    "normalization_notes",
    "needs_review_pre_geocode",
]


def clean_text(value):
    """Trim, collapse internal whitespace (including newlines) to a single space.

    Returns "" for None or purely-blank input. Accents are preserved; case is
    preserved.
    """
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = WHITESPACE.sub(" ", s).strip()
    return s


def clean_antivenoms_joined(raw_pipe_joined):
    """Rebuild the antivenoms field as a comma-joined, source-order list.

    Input comes from the CSV where `antivenoms_raw` is pipe-joined. Each entry
    is trimmed; empty entries are dropped; duplicates are preserved so source
    fidelity is not altered.
    """
    if raw_pipe_joined is None:
        return ""
    items = [clean_text(p) for p in str(raw_pipe_joined).split("|")]
    items = [p for p in items if p]
    return ", ".join(items)


def build_geocode_query(unit, address, municipality, state):
    parts = [unit, address, municipality, state, "Brasil"]
    parts = [p for p in parts if p]
    return ", ".join(parts)


def row_notes(unit, municipality, state, address, cnes, phones, antivenoms):
    notes = []
    if not unit:
        notes.append("health_unit_name empty")
    if not municipality:
        notes.append("municipality empty")
    if not state:
        notes.append("state empty")
    if not address and not cnes:
        notes.append("address and cnes both empty")
    elif not address:
        notes.append("address empty")
    if not phones:
        notes.append("phones empty")
    if not antivenoms:
        notes.append("antivenoms empty")
    return notes


def needs_review(unit, municipality, state, address, cnes):
    if not unit or not municipality or not state:
        return True
    if not address and not cnes:
        return True
    return False


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with INPUT.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        original_cols = list(reader.fieldnames or [])
        input_rows = list(reader)

    output_cols = original_cols + [c for c in NEW_COLUMNS if c not in original_cols]

    total = 0
    flagged = 0
    per_state_total = {}
    per_state_flagged = {}
    reason_counts = {
        "health_unit_name empty": 0,
        "municipality empty": 0,
        "state empty": 0,
        "address and cnes both empty": 0,
    }
    note_counts = {}

    normalized_rows = []
    for raw in input_rows:
        total += 1
        state_clean = clean_text(raw.get("state"))
        municipality_clean = clean_text(raw.get("municipality"))
        unit_clean = clean_text(raw.get("health_unit_name"))
        address_clean = clean_text(raw.get("address"))
        phones_clean = clean_text(raw.get("phones_raw"))
        cnes_present = bool(clean_text(raw.get("cnes")))
        antivenoms_joined = clean_antivenoms_joined(raw.get("antivenoms_raw"))

        notes = row_notes(
            unit_clean, municipality_clean, state_clean,
            address_clean, cnes_present, phones_clean, antivenoms_joined,
        )
        review_flag = needs_review(
            unit_clean, municipality_clean, state_clean,
            address_clean, cnes_present,
        )

        abbr = raw.get("source_state_abbr", "") or ""
        per_state_total[abbr] = per_state_total.get(abbr, 0) + 1
        if review_flag:
            flagged += 1
            per_state_flagged[abbr] = per_state_flagged.get(abbr, 0) + 1
            if not unit_clean:
                reason_counts["health_unit_name empty"] += 1
            if not municipality_clean:
                reason_counts["municipality empty"] += 1
            if not state_clean:
                reason_counts["state empty"] += 1
            if not address_clean and not cnes_present:
                reason_counts["address and cnes both empty"] += 1

        for n in notes:
            note_counts[n] = note_counts.get(n, 0) + 1

        out = dict(raw)
        out["state_clean"] = state_clean
        out["municipality_clean"] = municipality_clean
        out["health_unit_name_clean"] = unit_clean
        out["address_clean"] = address_clean
        out["phones_clean"] = phones_clean
        out["antivenoms_joined"] = antivenoms_joined
        out["geocode_query"] = build_geocode_query(
            unit_clean, address_clean, municipality_clean, state_clean,
        )
        out["normalization_notes"] = "; ".join(notes)
        out["needs_review_pre_geocode"] = "true" if review_flag else "false"
        normalized_rows.append(out)

    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_cols, extrasaction="ignore")
        writer.writeheader()
        for row in normalized_rows:
            writer.writerow(row)

    lines = []
    lines.append("# Normalization Summary")
    lines.append("")
    lines.append(f"**Input:**  `{INPUT}`")
    lines.append(f"**Output:** `{OUTPUT}`")
    lines.append("")
    lines.append(f"**Total rows processed:** {total:,}")
    lines.append(f"**Rows flagged `needs_review_pre_geocode = true`:** {flagged:,}")
    pct = (flagged / total * 100) if total else 0
    lines.append(f"**Flag rate:** {pct:.2f}%")
    lines.append("")
    lines.append("## Flag reasons")
    lines.append("")
    lines.append("A row can match multiple reasons; each reason counts once per matching row.")
    lines.append("")
    lines.append("| Reason | Rows |")
    lines.append("|--------|-----:|")
    for reason in [
        "health_unit_name empty",
        "municipality empty",
        "state empty",
        "address and cnes both empty",
    ]:
        lines.append(f"| `{reason}` | {reason_counts[reason]} |")
    lines.append("")
    lines.append("## Flagged rows by state")
    lines.append("")
    if per_state_flagged:
        lines.append("| State | Flagged / Total |")
        lines.append("|-------|----------------:|")
        for abbr in sorted(per_state_flagged):
            lines.append(f"| {abbr} | {per_state_flagged[abbr]} / {per_state_total.get(abbr,0)} |")
    else:
        lines.append("_No rows flagged._")
    lines.append("")
    lines.append("## All normalization notes (informational)")
    lines.append("")
    lines.append("Not every note is a blocker — e.g. `phones empty` is common and acceptable.")
    lines.append("")
    lines.append("| Note | Rows |")
    lines.append("|------|-----:|")
    for note in sorted(note_counts, key=lambda k: -note_counts[k]):
        lines.append(f"| {note} | {note_counts[note]:,} |")
    lines.append("")
    lines.append("## Rules applied")
    lines.append("")
    lines.append("- Trim leading/trailing whitespace; collapse all internal whitespace "
                 "(spaces, tabs, newlines) to a single space.")
    lines.append("- Preserve accents; no case transformations.")
    lines.append("- Keep `cnes` as string in original column; no `cnes_clean` is created.")
    lines.append("- Original raw columns are never overwritten; only new `*_clean` and "
                 "derived columns are added.")
    lines.append("- `phones_clean`: whitespace-cleaned copy of `phones_raw`; all punctuation preserved.")
    lines.append("- `antivenoms_joined`: pipe-split the CSV `antivenoms_raw`, trim each, drop blanks, "
                 "rejoin with `, `. Source order and duplicates are preserved.")
    lines.append("- `geocode_query`: `health_unit_name_clean, address_clean, municipality_clean, "
                 "state_clean, Brasil` joined by `, `, with empty parts skipped to avoid doubled commas.")
    lines.append("- `needs_review_pre_geocode = true` when `health_unit_name`, `municipality`, or "
                 "`state` is empty, or when `address` AND `cnes` are both empty.")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Normalized {total:,} rows -> {OUTPUT}")
    print(f"Flagged {flagged:,} row(s) for pre-geocode review ({pct:.2f}%)")
    print(f"Summary: {REPORT}")


if __name__ == "__main__":
    main()
