#!/usr/bin/env python3
"""Classify geocoded hospital rows — v3.

Improvements over v2:
1. Uses the PDF/filename UF (`source_state_abbr`) as the source-of-truth
   context for the row.
2. Parses the geocoded UF from `formatted_address` using only strict
   end-of-address patterns (no substring matching against street names,
   municipality names, neighborhood names, or hospital names).
3. UF mismatch is not automatically catastrophic. For special remote /
   indigenous / military / support units (Polo Base, UBSI, Pelotão,
   Missão, Fronteira, Base Indígena, DSEI, PEF, etc.) a mismatch is
   downgraded to retry_queue because those units often sit physically
   across a state border from the health secretariat that lists them.

Inputs:
    build/master_geocoded.csv

Outputs:
    build/geocode_auto_accept_v3.csv
    build/geocode_watchlist_v3.csv
    build/geocode_retry_queue_v3.csv
    build/geocode_manual_review_high_risk_v3.csv
    reports/08_geocode_review_summary_v3.md
    reports/08_geocode_review_diff_v2_to_v3.md  (compared against v2 buckets)
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
OUT_ACCEPT = BUILD / "geocode_auto_accept_v3.csv"
OUT_WATCH = BUILD / "geocode_watchlist_v3.csv"
OUT_RETRY = BUILD / "geocode_retry_queue_v3.csv"
OUT_HIGH = BUILD / "geocode_manual_review_high_risk_v3.csv"
REPORT_V3 = REPORTS / "08_geocode_review_summary_v3.md"
REPORT_DIFF = REPORTS / "08_geocode_review_diff_v2_to_v3.md"

# v2 bucket CSVs for the diff
V2_ACCEPT = BUILD / "geocode_auto_accept.csv"
V2_WATCH = BUILD / "geocode_watchlist.csv"
V2_RETRY = BUILD / "geocode_retry_queue.csv"
V2_HIGH = BUILD / "geocode_manual_review_high_risk.csv"

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

# Strict end-of-address UF: "- UF" immediately followed by comma or end.
# Match is taken from the rightmost occurrence so earlier "-" hyphens in
# street names are ignored.
UF_END_RE = re.compile(r"-\s*([A-Z]{2})(?=\s*(?:,|$))")

# v2's buggy fallback — plain substring `in` check without word boundaries.
# This is why strings like "morpará" matched "pará" (PA) and "paranaíba"
# matched "paraná" (PR) in v2. Reproduced here only to identify which rows
# v2 would have flagged so the diff can categorize them.
_V2_NAME_LIST = [
    (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower(),
        code,
    )
    for name, code in BR_STATES.items()
]

SPECIAL_UNIT_PATTERNS = re.compile(
    r"(?:\bpolo\s*base\b"
    r"|\bubsi\b"
    r"|\bmiss[ãa]o\b"
    r"|\bpelot[ãa]o\b"
    r"|\bfronteira\b"
    r"|\bbase\s*ind[ií]gena\b"
    r"|\bind[ií]gena\b"
    r"|\byanomami\b|\bianomami\b"
    r"|\bdsei\b"
    r"|\bpef\b"
    r"|\bcasai\b"
    r"|\bcasa\s*de\s*sa[uú]de\s*ind[ií]gena\b"
    r"|\bpost[oa]\s*ind[ií]gena\b"
    r"|\baldeia\b)",
    re.IGNORECASE,
)

HIGHWAY_FIRST_SEG_RE = re.compile(
    r"^\s*(?:BR[-–]\d+|SP[-–]\d+|MG[-–]\d+|Rodovia\b|Estrada\b|Via\s+\w+\b)",
    re.IGNORECASE,
)

PLACE_ID_REUSE_THRESHOLD = 3


def strip_accents_lower(s: str) -> str:
    s = s or ""
    nkfd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nkfd if not unicodedata.combining(c)).lower()


def parse_geocoded_uf_strict(fa: str) -> str | None:
    """v3 UF parser — ONLY the strict '- UF, <rest>' end pattern.

    No fallback to substring matching against state names anywhere in the
    string. Returns None when we can't be confident.
    """
    if not fa:
        return None
    matches = UF_END_RE.findall(fa)
    for uf in reversed(matches):
        if uf in UF_CODES:
            return uf
    return None


def parse_geocoded_uf_v2_style(fa: str) -> str | None:
    """Reproduces v2's UF detection exactly. v2 used re.search (first match)
    on the '- UF' pattern, then fell back to a substring match against full
    state names. This helper is used only to reconstruct v2's decision for
    the diff report — it is NOT used in v3 classification."""
    if not fa:
        return None
    # v2 took the FIRST '- UF' match, not the last. This is part of why v2
    # incorrectly fingered earlier "- XX" hyphen patterns inside street
    # names as the geocoded state.
    m = UF_END_RE.search(fa)
    if m:
        uf = m.group(1)
        if uf in UF_CODES:
            return uf
    folded = strip_accents_lower(fa)
    for name_ascii, code in _V2_NAME_LIST:
        if name_ascii in folded:
            return code
    return None


def has_non_brazil_country(fa: str) -> bool:
    if not fa:
        return False
    last = fa.rsplit(",", 1)[-1].strip().lower()
    if not last:
        return False
    return last not in {"brasil", "brazil"}


def coords_in_brazil(row: dict) -> bool:
    try:
        lat = float(row.get("lat") or "")
        lng = float(row.get("lng") or "")
    except ValueError:
        return False
    return BR_LAT[0] <= lat <= BR_LAT[1] and BR_LNG[0] <= lng <= BR_LNG[1]


def coords_present(row: dict) -> bool:
    return bool((row.get("lat") or "").strip()) and bool((row.get("lng") or "").strip())


def municipality_in_fa(municipality: str, fa: str) -> bool:
    if not municipality or not fa:
        return False
    return strip_accents_lower(municipality) in strip_accents_lower(fa)


def formatted_is_generic(fa: str) -> bool:
    if not fa:
        return True
    parts = [p.strip() for p in fa.split(",") if p.strip()]
    if len(parts) < 4:
        return True
    if HIGHWAY_FIRST_SEG_RE.match(parts[0]) and not re.search(r"\d+", parts[0]):
        return True
    return False


def is_special_unit(unit_name: str, source_notes: str = "") -> bool:
    hay = f"{unit_name or ''} {source_notes or ''}"
    return bool(SPECIAL_UNIT_PATTERNS.search(hay))


def classify_v3(row: dict, suspicious_place_ids: set[str]) -> tuple[str, list[str], dict]:
    """Returns (bucket, reasons, diag) where diag carries extra fields for
    the diff report (geocoded_state_abbr, special_unit flag, etc.)."""
    status = (row.get("geocode_status") or "").strip()
    source_uf = (row.get("source_state_abbr") or "").strip().upper()
    source_state_name = (row.get("state_clean") or "").strip()
    fa = (row.get("formatted_address") or "").strip()
    unit = (row.get("health_unit_name_clean") or row.get("health_unit_name") or "")
    muni = (row.get("municipality_clean") or "").strip()
    loc_type = (row.get("location_type") or "").strip()
    partial = (row.get("partial_match") or "").strip().lower() == "true"
    place_id = (row.get("place_id") or "").strip()
    notes = (row.get("source_notes") or "")

    geocoded_uf = parse_geocoded_uf_strict(fa)
    v2_uf = parse_geocoded_uf_v2_style(fa)
    special = is_special_unit(unit, notes)

    diag = {
        "source_pdf_file": row.get("source_state_file", ""),  # provenance pointer
        "source_state_abbr": source_uf,
        "source_state_name": source_state_name,
        "geocoded_state_abbr": geocoded_uf or "",
        "v2_inferred_uf_with_substring_fallback": v2_uf or "",
        "is_special_unit": special,
    }

    reasons: list[str] = []

    # ---- hard catastrophic triggers (unchanged from v2 except UF rule) ----
    if status != "OK":
        return "manual_review_high_risk", [f"status={status or 'blank'}"], diag
    if not coords_present(row):
        return "manual_review_high_risk", ["lat/lng missing"], diag
    if not coords_in_brazil(row):
        return "manual_review_high_risk", ["coordinates outside Brazil"], diag
    if has_non_brazil_country(fa):
        return "manual_review_high_risk", [
            f"formatted_address ends with non-Brazil country "
            f"({fa.rsplit(',',1)[-1].strip()})"
        ], diag

    # ---- state mismatch with unit-type-aware severity --------------------
    state_mismatch = bool(source_uf and geocoded_uf and geocoded_uf != source_uf)
    if state_mismatch:
        msg = (
            f"geocoded_state_abbr={geocoded_uf} differs from "
            f"source_state_abbr={source_uf}"
        )
        if special:
            # Downgrade: remote/indigenous/military/support units often
            # straddle or cross state lines (e.g. AP UBSIs physically in PA;
            # RR Polo Base units serving DSEI Yanomami). Only retry unless
            # combined with another severe signal.
            reasons.append(msg + " (special unit — downgraded)")
        else:
            reasons.append(msg + " (standard hospital-type unit)")
            return "manual_review_high_risk", reasons, diag

    # ---- place_id reused across many unrelated municipalities ------------
    if place_id and place_id in suspicious_place_ids:
        return "manual_review_high_risk", reasons + [
            "place_id reused across multiple unrelated (municipality, state) pairs"
        ], diag

    # ---- retry_queue signals --------------------------------------------
    if loc_type == "APPROXIMATE":
        reasons.append("location_type=APPROXIMATE")
    if muni and not municipality_in_fa(muni, fa):
        reasons.append("municipality not in formatted_address")
    if formatted_is_generic(fa):
        reasons.append("formatted_address is generic (<4 segments or highway-only)")
    if partial and loc_type != "ROOFTOP":
        reasons.append(f"partial_match with location_type={loc_type}")
    if reasons:
        return "retry_queue", reasons, diag

    # ---- watchlist / auto_accept ----------------------------------------
    if loc_type in {"GEOMETRIC_CENTER", "RANGE_INTERPOLATED"}:
        wl = [f"location_type={loc_type}"]
        if partial:
            wl.append("partial_match (tolerated — other signals clean)")
        return "watchlist", wl, diag

    if loc_type == "ROOFTOP":
        acc = ["ROOFTOP + in Brazil + state-consistent"]
        if partial:
            acc.append("partial_match tolerated")
        return "auto_accept", acc, diag

    return "retry_queue", [f"unhandled location_type={loc_type or 'blank'}"], diag


def load_bucket_assignments(path: Path) -> dict[str, str]:
    """Return {row_id: bucket} for a v2 CSV, where bucket == file base."""
    if not path.exists():
        return {}
    bucket = path.stem.replace("geocode_", "").replace("_v3", "")
    out = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            rid = r.get("row_id", "").strip()
            if rid:
                out[rid] = bucket
    return out


def main() -> None:
    with INPUT.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        input_cols = list(reader.fieldnames or [])
        rows = list(reader)

    # place_id reuse pass
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

    extra_cols = [
        "review_status", "review_reasons",
        "source_pdf_file", "source_state_abbr_checked",
        "source_state_name", "geocoded_state_abbr",
        "is_special_unit",
    ]
    out_cols = input_cols + [c for c in extra_cols if c not in input_cols]

    buckets: dict[str, list[dict]] = {
        "auto_accept": [],
        "watchlist": [],
        "retry_queue": [],
        "manual_review_high_risk": [],
    }
    bucket_loc = {k: Counter() for k in buckets}
    v3_rows: dict[str, dict] = {}
    v3_diag: dict[str, dict] = {}
    v3_reasons_by_row: dict[str, list[str]] = {}
    v3_bucket_by_row: dict[str, str] = {}

    for r in rows:
        bucket, reasons, diag = classify_v3(r, suspicious_place_ids)
        out_row = dict(r)
        out_row["review_status"] = bucket
        out_row["review_reasons"] = "; ".join(reasons)
        out_row["source_pdf_file"] = diag["source_pdf_file"]
        out_row["source_state_abbr_checked"] = diag["source_state_abbr"]
        out_row["source_state_name"] = diag["source_state_name"]
        out_row["geocoded_state_abbr"] = diag["geocoded_state_abbr"]
        out_row["is_special_unit"] = "true" if diag["is_special_unit"] else "false"
        buckets[bucket].append(out_row)
        bucket_loc[bucket][(r.get("location_type") or "").strip() or "(empty)"] += 1
        rid = r["row_id"]
        v3_rows[rid] = out_row
        v3_diag[rid] = diag
        v3_reasons_by_row[rid] = reasons
        v3_bucket_by_row[rid] = bucket

    outputs = {
        "auto_accept": OUT_ACCEPT,
        "watchlist": OUT_WATCH,
        "retry_queue": OUT_RETRY,
        "manual_review_high_risk": OUT_HIGH,
    }
    for bucket, rows_out in buckets.items():
        with outputs[bucket].open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_cols, extrasaction="ignore")
            writer.writeheader()
            for out_row in rows_out:
                writer.writerow(out_row)

    # ---------------- v3 summary report ----------------
    total = len(rows)
    lines: list[str] = []
    lines.append("# Geocode Review Classification (v3)")
    lines.append("")
    lines.append(f"**Input:** `{INPUT}`")
    lines.append(f"**Total rows classified:** {total:,}")
    lines.append("")
    lines.append("### Changes from v2")
    lines.append("")
    lines.append("- `geocoded_state_abbr` is now parsed **only** from the strict "
                 "`- UF` end-pattern in `formatted_address`. Substring matching "
                 "against full state names (which false-matched street names, "
                 "municipality names, and unit names in v2) has been **removed**.")
    lines.append("- `source_state_abbr` from the extracted JSON filename "
                 "(e.g. `BA.json` → `BA`) is treated as the expected state context.")
    lines.append("- UF mismatch is **no longer automatically catastrophic**. "
                 "For special remote / indigenous / military / support units "
                 "(Polo Base, UBSI, Pelotão, Missão, Fronteira, Base Indígena, "
                 "DSEI, PEF, CASAI, Aldeia, Yanomami), a mismatch is downgraded "
                 "to `retry_queue` unless combined with another severe signal.")
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
    loc_types_seen = sorted({lt for c in bucket_loc.values() for lt in c})
    header = "| Bucket | " + " | ".join(f"`{lt}`" for lt in loc_types_seen) + " |"
    sep = "|--------|" + "|".join(["-----:"] * len(loc_types_seen)) + "|"
    lines.append(header)
    lines.append(sep)
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        cells = [str(bucket_loc[bucket].get(lt, 0)) for lt in loc_types_seen]
        lines.append(f"| `{bucket}` | " + " | ".join(cells) + " |")
    lines.append("")

    def sample(rows_sample, title, n=25):
        lines.append(f"## {title} (top {n})")
        lines.append("")
        if not rows_sample:
            lines.append("_No rows in this bucket._")
            lines.append("")
            return
        lines.append("| row_id | Source muni, UF | FA | geocoded_uf | special | reasons |")
        lines.append("|--------|-----------------|----|-------------|---------|---------|")
        for r in rows_sample[:n]:
            muni = r.get("municipality_clean", "")
            src_uf = r.get("source_state_abbr_checked", "")
            geo_uf = r.get("geocoded_state_abbr", "") or "—"
            special = "yes" if r.get("is_special_unit", "") == "true" else ""
            fa = (r.get("formatted_address") or "").replace("|", "\\|")[:55]
            reasons = (r.get("review_reasons") or "").replace("|", "\\|")
            lines.append(f"| `{r['row_id']}` | {muni}, {src_uf} | {fa} | `{geo_uf}` | {special} | {reasons} |")
        lines.append("")

    sample(buckets["manual_review_high_risk"], "High-risk rows")
    sample(buckets["retry_queue"], "Retry queue rows")
    sample(buckets["watchlist"], "Watchlist samples")

    lines.append("## Parser confirmation")
    lines.append("")
    lines.append("- UF-from-FA regex: ``-\\s*([A-Z]{2})(?=\\s*(?:,|$))`` (rightmost match only).")
    lines.append("- **No substring matching against full state names** anywhere inside `formatted_address`.")
    lines.append(f"- Special-unit regex: `{SPECIAL_UNIT_PATTERNS.pattern}`")
    lines.append(f"- Place-id reuse threshold: >= {PLACE_ID_REUSE_THRESHOLD} distinct (municipality, state) origins.")
    lines.append("")
    REPORT_V3.write_text("\n".join(lines), encoding="utf-8")

    # ---------------- v2 vs v3 diff report ----------------
    v2_map: dict[str, str] = {}
    for path in (V2_ACCEPT, V2_WATCH, V2_RETRY, V2_HIGH):
        v2_map.update(load_bucket_assignments(path))

    transitions: Counter = Counter()
    per_trans_examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    false_positive_uf_rows: list[dict] = []
    special_downgrade_rows: list[dict] = []
    still_high_risk_rows: list[dict] = []
    new_high_risk_rows: list[dict] = []

    for rid, v3_bucket in v3_bucket_by_row.items():
        v2_bucket = v2_map.get(rid, "unseen")
        transitions[(v2_bucket, v3_bucket)] += 1
        if len(per_trans_examples[(v2_bucket, v3_bucket)]) < 10:
            per_trans_examples[(v2_bucket, v3_bucket)].append(rid)

        diag = v3_diag[rid]
        v3_row = v3_rows[rid]

        was_high = v2_bucket == "manual_review_high_risk"
        now_high = v3_bucket == "manual_review_high_risk"

        if was_high and not now_high:
            v2_uf = diag["v2_inferred_uf_with_substring_fallback"]
            strict_uf = diag["geocoded_state_abbr"]
            source_uf = diag["source_state_abbr"]
            v2_would_have_flagged_mismatch = bool(
                v2_uf and source_uf and v2_uf != source_uf
            )
            strict_agrees_mismatch = bool(
                strict_uf and source_uf and strict_uf != source_uf
            )
            if v2_would_have_flagged_mismatch and not strict_agrees_mismatch:
                false_positive_uf_rows.append(v3_row)
            elif strict_agrees_mismatch and diag["is_special_unit"]:
                special_downgrade_rows.append(v3_row)
            # else: some other downgrade path (place_id, coords, etc.) — rare
        elif now_high:
            still_high_risk_rows.append(v3_row)
            if not was_high:
                new_high_risk_rows.append(v3_row)

    dlines: list[str] = []
    dlines.append("# Diff — v2 → v3 Geocode Classification")
    dlines.append("")
    dlines.append("## Bucket counts (v2 vs v3)")
    dlines.append("")
    v2_counter = Counter(v2_map.values())
    v3_counter = Counter(v3_bucket_by_row.values())
    dlines.append("| Bucket | v2 | v3 | Δ |")
    dlines.append("|--------|---:|---:|--:|")
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        v2n = v2_counter.get(bucket, 0)
        v3n = v3_counter.get(bucket, 0)
        delta = v3n - v2n
        sign = "+" if delta > 0 else ""
        dlines.append(f"| `{bucket}` | {v2n:,} | {v3n:,} | {sign}{delta} |")
    dlines.append("")
    dlines.append("## Transition matrix")
    dlines.append("")
    dlines.append("Rows = v2 bucket; columns = v3 bucket.")
    dlines.append("")
    bucket_order = ["auto_accept", "watchlist", "retry_queue", "manual_review_high_risk", "unseen"]
    header = "| v2 \\ v3 | " + " | ".join(f"`{b}`" for b in bucket_order[:-1]) + " |"
    sep = "|---------|" + "|".join(["----:"] * (len(bucket_order) - 1)) + "|"
    dlines.append(header)
    dlines.append(sep)
    for v2b in bucket_order:
        cells = [str(transitions.get((v2b, v3b), 0)) for v3b in bucket_order[:-1]]
        dlines.append(f"| `{v2b}` | " + " | ".join(cells) + " |")
    dlines.append("")

    dlines.append(f"## Rows removed from high-risk — false-positive UF parsing ({len(false_positive_uf_rows)})")
    dlines.append("")
    dlines.append("These rows were high-risk in v2 because v2's UF detection matched a "
                  "state name inside a street/municipality/unit substring. v3's strict "
                  "end-pattern parser no longer infers a UF for these, so the mismatch "
                  "signal does not fire.")
    dlines.append("")
    if false_positive_uf_rows:
        dlines.append("| row_id | Source UF | v2 inferred UF (substring) | v3 strict UF | formatted_address |")
        dlines.append("|--------|-----------|---------------------------|--------------|-------------------|")
        for r in false_positive_uf_rows[:25]:
            d = v3_diag[r["row_id"]]
            fa = (r.get("formatted_address") or "").replace("|", "\\|")[:70]
            dlines.append(
                f"| `{r['row_id']}` | {d['source_state_abbr']} | "
                f"`{d['v2_inferred_uf_with_substring_fallback'] or '—'}` | "
                f"`{d['geocoded_state_abbr'] or '—'}` | {fa} |"
            )
    else:
        dlines.append("_None._")
    dlines.append("")

    dlines.append(f"## Rows downgraded — special remote/indigenous/military/support units ({len(special_downgrade_rows)})")
    dlines.append("")
    dlines.append("These rows genuinely have a geocoded UF different from the source UF, "
                  "but the unit type (UBSI, Polo Base, Pelotão, Missão, DSEI, etc.) means "
                  "a cross-border placement is expected, so they are demoted to `retry_queue` "
                  "or `watchlist` rather than high-risk.")
    dlines.append("")
    if special_downgrade_rows:
        dlines.append("| row_id | Unit | Source UF → Geocoded UF | v3 bucket |")
        dlines.append("|--------|------|-------------------------|-----------|")
        for r in special_downgrade_rows[:50]:
            d = v3_diag[r["row_id"]]
            unit = (r.get("health_unit_name_clean") or "")[:55]
            dlines.append(
                f"| `{r['row_id']}` | {unit} | "
                f"{d['source_state_abbr']} → `{d['geocoded_state_abbr']}` | "
                f"`{r['review_status']}` |"
            )
    else:
        dlines.append("_None._")
    dlines.append("")

    dlines.append(f"## Rows still truly high-risk in v3 ({len(still_high_risk_rows)})")
    dlines.append("")
    if still_high_risk_rows:
        dlines.append("| row_id | Source UF → Geocoded UF | special | reasons |")
        dlines.append("|--------|-------------------------|---------|---------|")
        for r in still_high_risk_rows[:50]:
            d = v3_diag[r["row_id"]]
            special = "yes" if d["is_special_unit"] else ""
            reasons = (r.get("review_reasons") or "").replace("|", "\\|")
            dlines.append(
                f"| `{r['row_id']}` | {d['source_state_abbr']} → "
                f"`{d['geocoded_state_abbr'] or '—'}` | {special} | {reasons} |"
            )
    else:
        dlines.append("_None._")
    dlines.append("")

    if new_high_risk_rows:
        dlines.append(f"## New high-risk rows that were NOT high-risk in v2 ({len(new_high_risk_rows)})")
        dlines.append("")
        dlines.append("| row_id | v2 bucket | v3 reasons |")
        dlines.append("|--------|-----------|------------|")
        for r in new_high_risk_rows[:25]:
            v2b = v2_map.get(r["row_id"], "unseen")
            reasons = (r.get("review_reasons") or "").replace("|", "\\|")
            dlines.append(f"| `{r['row_id']}` | `{v2b}` | {reasons} |")
        dlines.append("")

    dlines.append("## Parser confirmation")
    dlines.append("")
    dlines.append("- v3 uses the regex ``-\\s*([A-Z]{2})(?=\\s*(?:,|$))`` (rightmost match) "
                  "to extract `geocoded_state_abbr` from `formatted_address`.")
    dlines.append("- **Substring-based UF parsing has been removed.** Street names, "
                  "municipality names, neighborhood names, and hospital names are no "
                  "longer searched for full state names; the v2 substring-fallback branch "
                  "is kept in the codebase only to reconstruct v2's decision for this diff.")
    dlines.append("- `source_state_abbr` (derived from the PDF/JSON filename stem) remains "
                  "the ground-truth context for every row.")
    dlines.append("")
    REPORT_DIFF.write_text("\n".join(dlines), encoding="utf-8")

    print(f"Classified {total:,} rows (v3):")
    for bucket in ("auto_accept", "watchlist", "retry_queue", "manual_review_high_risk"):
        print(f"  {bucket}: {len(buckets[bucket]):,}")
    print(f"Removed from high-risk (false-positive UF): {len(false_positive_uf_rows)}")
    print(f"Downgraded (special units): {len(special_downgrade_rows)}")
    print(f"Still truly high-risk in v3: {len(still_high_risk_rows)}")
    print(f"Reports: {REPORT_V3}, {REPORT_DIFF}")


if __name__ == "__main__":
    main()
