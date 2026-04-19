#!/usr/bin/env python3
"""Classify geocoded hospital rows into review buckets using combined evidence.

Unlike the v1 heuristic, `partial_match = true` alone does NOT trigger manual
review; Google sets it for most fuzzy lookups even when the result is fine.

Input:   build/master_geocoded.csv
Outputs: build/geocode_auto_accept.csv
         build/geocode_watchlist.csv
         build/geocode_retry_queue.csv
         build/geocode_manual_review_high_risk.csv
         reports/08_geocode_review_summary_v2.md

Buckets (evaluated top-down; a row lands in the first bucket it matches):

    manual_review_high_risk
        - status != OK
        - lat/lng missing or outside Brazil bounding box
        - formatted_address indicates a non-Brazil country
        - formatted_address indicates a Brazilian UF different from source
        - place_id is reused by >=3 distinct (municipality, state) source pairs

    retry_queue
        - location_type == APPROXIMATE
        - municipality missing from formatted_address
        - formatted_address is generic (<4 comma segments, or highway-only,
          or city/state only)
        - partial_match == true AND location_type != ROOFTOP

    watchlist
        - location_type in {GEOMETRIC_CENTER, RANGE_INTERPOLATED}
          (by elimination: nothing worse was found)

    auto_accept
        - location_type == ROOFTOP and all other checks clean
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"

INPUT = BUILD / "master_geocoded.csv"
OUT_ACCEPT = BUILD / "geocode_auto_accept.csv"
OUT_WATCH = BUILD / "geocode_watchlist.csv"
OUT_RETRY = BUILD / "geocode_retry_queue.csv"
OUT_HIGH = BUILD / "geocode_manual_review_high_risk.csv"
REPORT = REPORTS / "08_geocode_review_summary_v2.md"

BR_LAT = (-34.0, 6.0)
BR_LNG = (-74.0, -34.0)

BR_STATES = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAZONAS": "AM", "AMAPÁ": "AP",
    "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
    "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA",
    "MINAS GERAIS": "MG", "MATO GROSSO DO SUL": "MS", "MATO GROSSO": "MT",
    "PARÁ": "PA", "PARAÍBA": "PB", "PERNAMBUCO": "PE", "PIAUÍ": "PI",
    "PARANÁ": "PR", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RONDÔNIA": "RO", "RORAIMA": "RR", "RIO GRANDE DO SUL": "RS",
    "SANTA CATARINA": "SC", "SERGIPE": "SE", "SÃO PAULO": "SP",
    "TOCANTINS": "TO",
}
UF_CODES = set(BR_STATES.values())

UF_IN_FA_RE = re.compile(r"-\s*([A-Z]{2})(?:,|\s|$)")
HIGHWAY_FIRST_SEG_RE = re.compile(
    r"^\s*(?:BR[-–]\d+|SP[-–]\d+|MG[-–]\d+|Rodovia\b|Estrada\b|Av\.?\s+[A-Z][A-Z]\b)",
    re.IGNORECASE,
)

PLACE_ID_REUSE_THRESHOLD = 3  # >=3 distinct (municipality, state) origins


def strip_accents_lower(s: str) -> str:
    s = s or ""
    nkfd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nkfd if not unicodedata.combining(c)).lower()


def detect_formatted_uf(formatted_address: str) -> str | None:
    """Return a Brazilian UF code mentioned in the formatted_address, or None."""
    if not formatted_address:
        return None
    m = UF_IN_FA_RE.search(formatted_address)
    if m:
        uf = m.group(1)
        if uf in UF_CODES:
            return uf
    # fallback: full state name
    folded = strip_accents_lower(formatted_address)
    for name, code in BR_STATES.items():
        if strip_accents_lower(name) in folded:
            return code
    return None


def has_non_brazil_country(formatted_address: str) -> bool:
    if not formatted_address:
        return False
    last = formatted_address.rsplit(",", 1)[-1].strip().lower()
    if not last:
        return False
    # Common Google country strings for Brazil
    return last not in {"brasil", "brazil"}


def in_brazil(lat_str: str, lng_str: str) -> bool:
    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except (TypeError, ValueError):
        return False
    return BR_LAT[0] <= lat <= BR_LAT[1] and BR_LNG[0] <= lng <= BR_LNG[1]


def coords_present(row: dict) -> bool:
    return bool((row.get("lat") or "").strip()) and bool((row.get("lng") or "").strip())


def formatted_is_generic(formatted_address: str) -> bool:
    if not formatted_address:
        return True
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if len(parts) < 4:
        return True
    if HIGHWAY_FIRST_SEG_RE.match(parts[0]):
        # highway/road as the primary locator — generic unless paired with a number
        if not re.search(r"\d", parts[0]):
            return True
    return False


def municipality_in_fa(municipality: str, formatted_address: str) -> bool:
    if not municipality or not formatted_address:
        return False
    return strip_accents_lower(municipality) in strip_accents_lower(formatted_address)


def classify_row(row: dict, suspicious_place_ids: set[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    status = (row.get("geocode_status") or "").strip()
    source_state = (row.get("state_clean") or "").strip().upper()
    source_uf = BR_STATES.get(source_state, "")
    fa = (row.get("formatted_address") or "").strip()
    loc_type = (row.get("location_type") or "").strip()
    partial = (row.get("partial_match") or "").strip().lower() == "true"
    muni = (row.get("municipality_clean") or "").strip()
    place_id = (row.get("place_id") or "").strip()

    # --- manual_review_high_risk ------------------------------------------
    if status != "OK":
        return "manual_review_high_risk", [f"status={status or 'blank'}"]
    if not coords_present(row):
        return "manual_review_high_risk", ["lat/lng missing"]
    if not in_brazil(row["lat"], row["lng"]):
        return "manual_review_high_risk", ["coordinates outside Brazil"]
    if has_non_brazil_country(fa):
        return "manual_review_high_risk", [
            f"formatted_address ends with non-Brazil country ({fa.rsplit(',',1)[-1].strip()})"
        ]
    fa_uf = detect_formatted_uf(fa)
    if source_uf and fa_uf and fa_uf != source_uf:
        return "manual_review_high_risk", [
            f"formatted_address state ({fa_uf}) differs from source state ({source_uf})"
        ]
    if place_id and place_id in suspicious_place_ids:
        return "manual_review_high_risk", [
            "place_id reused across multiple unrelated municipalities"
        ]

    # --- retry_queue ------------------------------------------------------
    retry_reasons: list[str] = []
    if loc_type == "APPROXIMATE":
        retry_reasons.append("location_type=APPROXIMATE")
    if muni and not municipality_in_fa(muni, fa):
        retry_reasons.append("municipality not in formatted_address")
    if formatted_is_generic(fa):
        retry_reasons.append("formatted_address is generic (<4 segments or highway-only)")
    if partial and loc_type != "ROOFTOP":
        retry_reasons.append(f"partial_match with location_type={loc_type}")
    if retry_reasons:
        return "retry_queue", retry_reasons

    # --- watchlist --------------------------------------------------------
    if loc_type in {"GEOMETRIC_CENTER", "RANGE_INTERPOLATED"}:
        wl_reasons = [f"location_type={loc_type}"]
        if partial:
            wl_reasons.append("partial_match (accepted — other signals clean)")
        return "watchlist", wl_reasons

    # --- auto_accept ------------------------------------------------------
    if loc_type == "ROOFTOP":
        accept_reasons = ["ROOFTOP + in Brazil + state-consistent"]
        if partial:
            accept_reasons.append("partial_match tolerated (other signals clean)")
        return "auto_accept", accept_reasons

    # Unknown location_type — send to retry for safety
    return "retry_queue", [f"unhandled location_type={loc_type or 'blank'}"]


def main() -> None:
    with INPUT.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        input_cols = list(reader.fieldnames or [])
        rows = list(reader)

    # Pass 1: find place_ids reused across >=N distinct (municipality, state) pairs
    place_id_origins: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for r in rows:
        pid = (r.get("place_id") or "").strip()
        if not pid:
            continue
        origin = (
            strip_accents_lower(r.get("municipality_clean") or ""),
            (r.get("state_clean") or "").upper(),
        )
        place_id_origins[pid].add(origin)
    suspicious_place_ids = {
        pid for pid, origins in place_id_origins.items()
        if len(origins) >= PLACE_ID_REUSE_THRESHOLD
    }

    # Pass 2: classify
    out_cols = input_cols + [c for c in ("review_status", "review_reasons") if c not in input_cols]
    buckets: dict[str, list[dict]] = {
        "auto_accept": [],
        "watchlist": [],
        "retry_queue": [],
        "manual_review_high_risk": [],
    }
    bucket_loc_counts: dict[str, Counter] = {k: Counter() for k in buckets}
    for r in rows:
        bucket, reasons = classify_row(r, suspicious_place_ids)
        out_row = dict(r)
        out_row["review_status"] = bucket
        out_row["review_reasons"] = "; ".join(reasons)
        buckets[bucket].append(out_row)
        bucket_loc_counts[bucket][(r.get("location_type") or "").strip() or "(empty)"] += 1

    outputs = {
        "auto_accept": OUT_ACCEPT,
        "watchlist": OUT_WATCH,
        "retry_queue": OUT_RETRY,
        "manual_review_high_risk": OUT_HIGH,
    }
    for bucket, rows_out in buckets.items():
        path = outputs[bucket]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_cols, extrasaction="ignore")
            writer.writeheader()
            for r in rows_out:
                writer.writerow(r)

    total = len(rows)
    lines: list[str] = []
    lines.append("# Geocode Review Classification (v2)")
    lines.append("")
    lines.append(f"**Input:** `{INPUT}`")
    lines.append(f"**Total rows classified:** {total:,}")
    lines.append("")
    lines.append("`partial_match` alone is **no longer** a trigger for manual review. "
                 "Classification uses combined evidence from `location_type`, coordinate "
                 "validity, state consistency, `formatted_address` structure, and place_id reuse.")
    lines.append("")
    lines.append("## Bucket counts")
    lines.append("")
    lines.append("| Bucket | Count | % | Output file |")
    lines.append("|--------|------:|--:|-------------|")
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        n = len(buckets[bucket])
        pct = (n / total * 100) if total else 0
        lines.append(f"| `{bucket}` | {n:,} | {pct:.1f}% | `{outputs[bucket].relative_to(ROOT)}` |")
    lines.append(f"| **Total** | **{total:,}** | **100.0%** |  |")
    lines.append("")
    lines.append("## Location type breakdown per bucket")
    lines.append("")
    loc_types_seen = sorted({lt for c in bucket_loc_counts.values() for lt in c})
    header = "| Bucket | " + " | ".join(f"`{lt}`" for lt in loc_types_seen) + " |"
    sep = "|--------|" + "|".join(["-----:"] * len(loc_types_seen)) + "|"
    lines.append(header)
    lines.append(sep)
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        cells = [str(bucket_loc_counts[bucket].get(lt, 0)) for lt in loc_types_seen]
        lines.append(f"| `{bucket}` | " + " | ".join(cells) + " |")
    lines.append("")

    def sample_table(rows_sample, title, n=25):
        lines.append(f"## {title} (top {n})")
        lines.append("")
        if not rows_sample:
            lines.append("_No rows in this bucket._")
            lines.append("")
            return
        lines.append("| row_id | Source muni, UF | formatted_address | loc_type | reasons |")
        lines.append("|--------|-----------------|-------------------|----------|---------|")
        for r in rows_sample[:n]:
            state_abbr = BR_STATES.get((r.get("state_clean") or "").upper(), r.get("source_state_abbr", ""))
            muni = (r.get("municipality_clean") or "")
            fa = (r.get("formatted_address") or "").replace("|", "\\|")[:70]
            lt = r.get("location_type") or ""
            reasons = (r.get("review_reasons") or "").replace("|", "\\|")
            lines.append(f"| `{r['row_id']}` | {muni}, {state_abbr} | {fa} | `{lt}` | {reasons} |")
        lines.append("")

    sample_table(buckets["manual_review_high_risk"], "High-risk rows for manual review")
    sample_table(buckets["retry_queue"], "Retry queue rows")
    sample_table(buckets["watchlist"], "Watchlist samples")

    lines.append("## Rules applied")
    lines.append("")
    lines.append("- **Manual-review-high-risk triggers:** status != OK, lat/lng missing, "
                 "coords outside Brazil, non-Brazil country string, UF mismatch between "
                 "source and formatted_address, or place_id reused across "
                 f">= {PLACE_ID_REUSE_THRESHOLD} distinct (municipality, state) pairs.")
    lines.append("- **Retry-queue triggers:** location_type=APPROXIMATE, municipality not "
                 "present in formatted_address, formatted_address with <4 comma segments "
                 "or a highway-only first segment, or `partial_match=true` paired with "
                 "non-ROOFTOP location_type.")
    lines.append("- **Watchlist:** status OK, in Brazil, correct state, "
                 "location_type=GEOMETRIC_CENTER or RANGE_INTERPOLATED, no other flag fired. "
                 "`partial_match` is tolerated here.")
    lines.append("- **Auto-accept:** location_type=ROOFTOP and every check above is clean. "
                 "`partial_match` by itself does not disqualify the row.")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Classified {total:,} rows:")
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        print(f"  {bucket}: {len(buckets[bucket]):,}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
