#!/usr/bin/env python3
"""Pre-geocode QA/QC on the normalized hospital dataset.

Read:   build/master_normalized.csv
Write:  build/review_missing_fields.csv
        build/review_possible_duplicates.csv
        reports/05_pre_geocode_qaqc.md

Flags:
- Rows missing critical fields (no unit/municipality/state, or no
  address AND no cnes together).
- Possible duplicates by three independent keys:
    (1) exact same cnes (non-empty)
    (2) exact same (health_unit_name_clean, municipality_clean, state_clean)
    (3) exact same geocode_query (non-empty)

Does not delete or modify rows. Review-only outputs.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"
INPUT = BUILD / "master_normalized.csv"
MISSING_OUT = BUILD / "review_missing_fields.csv"
DUP_OUT = BUILD / "review_possible_duplicates.csv"
REPORT = REPORTS / "05_pre_geocode_qaqc.md"

PASSTHROUGH_COLS = [
    "row_id",
    "source_state_abbr",
    "source_state_file",
    "state_clean",
    "municipality_clean",
    "health_unit_name_clean",
    "address_clean",
    "cnes",
    "geocode_query",
    "needs_review_pre_geocode",
]


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with INPUT.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    total = len(rows)

    # -- Missing critical fields ---------------------------------------------
    missing_rows = []
    count_unit = count_muni = count_state = count_addr_cnes = 0
    for r in rows:
        unit = (r.get("health_unit_name_clean") or "").strip()
        muni = (r.get("municipality_clean") or "").strip()
        state = (r.get("state_clean") or "").strip()
        addr = (r.get("address_clean") or "").strip()
        cnes = (r.get("cnes") or "").strip()

        missing = []
        if not unit:
            missing.append("health_unit_name")
            count_unit += 1
        if not muni:
            missing.append("municipality")
            count_muni += 1
        if not state:
            missing.append("state")
            count_state += 1
        if not addr and not cnes:
            missing.append("address_and_cnes")
            count_addr_cnes += 1

        if missing:
            out = {c: r.get(c, "") for c in PASSTHROUGH_COLS}
            out["missing_fields"] = ", ".join(missing)
            missing_rows.append(out)

    with MISSING_OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PASSTHROUGH_COLS + ["missing_fields"])
        writer.writeheader()
        writer.writerows(missing_rows)

    # -- Duplicate detection -------------------------------------------------
    by_cnes = defaultdict(list)
    by_nms = defaultdict(list)
    by_geoq = defaultdict(list)

    for r in rows:
        cnes = (r.get("cnes") or "").strip()
        if cnes:
            by_cnes[cnes].append(r)

        unit = (r.get("health_unit_name_clean") or "").strip()
        muni = (r.get("municipality_clean") or "").strip()
        state = (r.get("state_clean") or "").strip()
        if unit and muni and state:
            by_nms[(unit, muni, state)].append(r)

        gq = (r.get("geocode_query") or "").strip()
        if gq:
            by_geoq[gq].append(r)

    cnes_groups = {k: v for k, v in by_cnes.items() if len(v) >= 2}
    nms_groups = {k: v for k, v in by_nms.items() if len(v) >= 2}
    geoq_groups = {k: v for k, v in by_geoq.items() if len(v) >= 2}

    dup_cols = ["duplicate_type", "duplicate_key", "group_size"] + PASSTHROUGH_COLS
    with DUP_OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=dup_cols)
        writer.writeheader()
        for key in sorted(cnes_groups):
            members = cnes_groups[key]
            for r in members:
                row = {"duplicate_type": "cnes", "duplicate_key": key, "group_size": len(members)}
                for c in PASSTHROUGH_COLS:
                    row[c] = r.get(c, "")
                writer.writerow(row)
        for key in sorted(nms_groups):
            members = nms_groups[key]
            key_str = " | ".join(key)
            for r in members:
                row = {"duplicate_type": "name_muni_state", "duplicate_key": key_str, "group_size": len(members)}
                for c in PASSTHROUGH_COLS:
                    row[c] = r.get(c, "")
                writer.writerow(row)
        for key in sorted(geoq_groups):
            members = geoq_groups[key]
            for r in members:
                row = {"duplicate_type": "geocode_query", "duplicate_key": key, "group_size": len(members)}
                for c in PASSTHROUGH_COLS:
                    row[c] = r.get(c, "")
                writer.writerow(row)

    cnes_dup_rows = sum(len(v) for v in cnes_groups.values())
    nms_dup_rows = sum(len(v) for v in nms_groups.values())
    geoq_dup_rows = sum(len(v) for v in geoq_groups.values())

    # -- Report --------------------------------------------------------------
    lines: list[str] = []
    lines.append("# Pre-Geocode QA/QC Report")
    lines.append("")
    lines.append(f"**Input:** `{INPUT}`")
    lines.append(f"**Total rows inspected:** {total:,}")
    lines.append("")
    lines.append("**Review files written (no rows deleted or modified):**")
    lines.append(f"- `{MISSING_OUT}`")
    lines.append(f"- `{DUP_OUT}`")
    lines.append("")
    lines.append("## 1. Missing critical fields")
    lines.append("")
    lines.append(f"**Rows flagged:** {len(missing_rows):,}")
    lines.append("")
    lines.append("A row can match more than one condition below.")
    lines.append("")
    lines.append("| Missing condition | Rows |")
    lines.append("|-------------------|-----:|")
    lines.append(f"| `health_unit_name_clean` empty | {count_unit} |")
    lines.append(f"| `municipality_clean` empty | {count_muni} |")
    lines.append(f"| `state_clean` empty | {count_state} |")
    lines.append(f"| `address_clean` AND `cnes` both empty | {count_addr_cnes} |")
    lines.append("")
    lines.append("## 2. Possible duplicates")
    lines.append("")
    lines.append("Each key below is checked independently; a single row can appear in multiple groups.")
    lines.append("")
    lines.append("| Key | Duplicate groups | Rows involved |")
    lines.append("|-----|----------------:|--------------:|")
    lines.append(f"| `cnes` (non-empty) | {len(cnes_groups):,} | {cnes_dup_rows:,} |")
    lines.append(f"| `health_unit_name_clean + municipality_clean + state_clean` | {len(nms_groups):,} | {nms_dup_rows:,} |")
    lines.append(f"| `geocode_query` (non-empty) | {len(geoq_groups):,} | {geoq_dup_rows:,} |")
    lines.append("")

    def top_groups(groups, label_fn, n=20):
        out = []
        for k in sorted(groups, key=lambda x: -len(groups[x]))[:n]:
            out.append((k, len(groups[k]), groups[k]))
        return out

    lines.append("### Top `cnes` duplicate groups")
    lines.append("")
    if cnes_groups:
        lines.append("| cnes | Rows | States involved | Sample unit name |")
        lines.append("|------|-----:|-----------------|------------------|")
        for key, sz, members in top_groups(cnes_groups, lambda k: k):
            states = sorted({(m.get("source_state_abbr") or "") for m in members})
            sample = (members[0].get("health_unit_name_clean") or "")[:60]
            lines.append(f"| `{key}` | {sz} | {', '.join(states)} | {sample} |")
    else:
        lines.append("_No duplicate `cnes` clusters found._")
    lines.append("")

    lines.append("### Top `name + municipality + state` duplicate groups")
    lines.append("")
    if nms_groups:
        lines.append("| Key | Rows |")
        lines.append("|-----|-----:|")
        for key, sz, _members in top_groups(nms_groups, lambda k: " | ".join(k)):
            lines.append(f"| `{' | '.join(key)}` | {sz} |")
    else:
        lines.append("_No duplicate name+municipality+state clusters found._")
    lines.append("")

    lines.append("### Top `geocode_query` duplicate groups")
    lines.append("")
    if geoq_groups:
        lines.append("| Query | Rows |")
        lines.append("|-------|-----:|")
        for key, sz, _members in top_groups(geoq_groups, lambda k: k):
            preview = (key[:120] + "…") if len(key) > 120 else key
            lines.append(f"| `{preview}` | {sz} |")
    else:
        lines.append("_No duplicate `geocode_query` clusters found._")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Missing-field rows: {len(missing_rows)} -> {MISSING_OUT}")
    print(f"cnes duplicate groups: {len(cnes_groups)} ({cnes_dup_rows} rows)")
    print(f"name+muni+state duplicate groups: {len(nms_groups)} ({nms_dup_rows} rows)")
    print(f"geocode_query duplicate groups: {len(geoq_groups)} ({geoq_dup_rows} rows)")
    print(f"Duplicate review: {DUP_OUT}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
