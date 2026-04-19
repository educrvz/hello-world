#!/usr/bin/env python3
"""Build the production `hospitals.json` from `build/master_geocoded_patched_v1.csv`.

Includes every row where `publish_policy == publish` (set by apply_repairs.py).
That covers:
  - all `publish_ready` rows (auto_accept_v3 + improved_confidently repairs)
  - `watchlist` and `retry_queue` rows that pass the safety filter
    (municipality is present in formatted_address AND FA has >2 segments)

Outputs:
    app/hospitals.json          (served by Vercel)
    hospitals.json              (repo-root mirror — legacy path, same content)

Schema mapping (see docs/PROCESS.md §11):

    hospital_name  <- health_unit_name
    state          <- source_state_abbr         (2-letter UF)
    state_name     <- state                     (title-cased)
    city           <- municipality
    address        <- address
    cnes           <- cnes
    phones         <- phones_raw                 (split on / and ,, placeholders dropped)
    antivenoms     <- antivenoms_raw             (split on |)
    lat, lng       <- lat, lng                   (floats)
    source_date    <- source_state_file          (parsed from Docs Estado/{UF}_YYYYMMDD.pdf)
    geocode_tier   <- location_type              (ROOFTOP=1, RANGE_INTERPOLATED=2, else 3)

Rows with blank lat or lng are dropped and logged to stderr.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DOCS_ESTADO = ROOT / "Docs Estado"
INPUT = BUILD / "master_geocoded_patched_v1.csv"
OUT_APP = ROOT / "app" / "hospitals.json"
OUT_ROOT = ROOT / "hospitals.json"

PHONE_PLACEHOLDERS = {
    "", "-", "--", "****", "***", "não disponível",
    "nao disponivel", "sem contato", "n/a", "nd", "indisponível",
}

PDF_DATE_RE = re.compile(r"[A-Z]{2}_(\d{4})(\d{2})(\d{2})\.pdf$", re.IGNORECASE)

TIER_MAP = {
    "ROOFTOP": 1,
    "RANGE_INTERPOLATED": 2,
    "GEOMETRIC_CENTER": 3,
    "APPROXIMATE": 3,
}


def load_pdf_date_map() -> dict[str, str]:
    """Map UF -> ISO date from the most recent matching PDF in Docs Estado/."""
    out: dict[str, str] = {}
    if not DOCS_ESTADO.exists():
        return out
    for p in DOCS_ESTADO.iterdir():
        m = PDF_DATE_RE.match(p.name)
        if not m:
            continue
        uf = p.name[:2].upper()
        # Strip "V2_" etc. prefixes if present (match on trailing UF_DATE.pdf)
        tail = PDF_DATE_RE.search(p.name)
        if tail:
            y, mo, d = tail.group(1), tail.group(2), tail.group(3)
            iso = f"{y}-{mo}-{d}"
            # Prefer the newest PDF per UF if multiple
            existing = out.get(uf)
            if not existing or iso > existing:
                out[uf] = iso
    return out


def clean_phones(raw: str) -> list[str]:
    if not raw:
        return []
    # Split on / or comma, trim, dedupe, drop placeholders
    parts = re.split(r"\s*[/,]\s*", raw)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        s = p.strip()
        if not s:
            continue
        if s.lower() in PHONE_PLACEHOLDERS:
            continue
        if len(s) < 4:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def split_antivenoms(raw: str) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for p in raw.split("|"):
        s = p.strip()
        if s:
            out.append(s)
    return out


def title_case_state(name: str) -> str:
    """ACRE -> Acre; SÃO PAULO -> São Paulo; RIO DE JANEIRO -> Rio de Janeiro."""
    if not name:
        return ""
    small = {"de", "da", "do", "das", "dos", "e"}
    words = name.lower().split()
    return " ".join(w if w in small and i > 0 else w.capitalize() for i, w in enumerate(words))


def parse_latlng(row: dict) -> tuple[float | None, float | None]:
    try:
        lat = float(row["lat"])
        lng = float(row["lng"])
    except (KeyError, ValueError, TypeError):
        return None, None
    return lat, lng


def main() -> int:
    if not INPUT.exists():
        sys.stderr.write(f"ERROR: {INPUT} does not exist. Run the pipeline first.\n")
        return 2

    pdf_dates = load_pdf_date_map()

    with INPUT.open(encoding="utf-8", newline="") as fh:
        all_rows = list(csv.DictReader(fh))

    # Filter by publish_policy (set by apply_repairs.py)
    rows = [r for r in all_rows if (r.get("publish_policy") or "").strip() == "publish"]
    hidden = len(all_rows) - len(rows)

    out_records: list[dict] = []
    dropped_missing_coords: list[str] = []

    for r in rows:
        lat, lng = parse_latlng(r)
        if lat is None or lng is None:
            dropped_missing_coords.append(r.get("row_id", "?"))
            continue

        uf = (r.get("source_state_abbr") or "").strip().upper()
        state_name = title_case_state((r.get("state") or "").strip())
        source_date = pdf_dates.get(uf, "")

        record = {
            "state": uf,
            "state_name": state_name,
            "city": (r.get("municipality") or "").strip(),
            "hospital_name": (r.get("health_unit_name") or "").strip(),
            "address": (r.get("address") or "").strip(),
            "phones": clean_phones(r.get("phones_raw") or ""),
            "cnes": (r.get("cnes") or "").strip(),
            "antivenoms": split_antivenoms(r.get("antivenoms_raw") or ""),
            "source_date": source_date,
            "lat": lat,
            "lng": lng,
            "geocode_tier": TIER_MAP.get((r.get("location_type") or "").strip(), 3),
        }
        out_records.append(record)

    # Match key order of the current prod file for minimal git diff churn
    canonical_order = [
        "state", "state_name", "city", "hospital_name", "address",
        "phones", "cnes", "antivenoms", "source_date", "lat", "lng",
        "geocode_tier",
    ]
    ordered = [{k: rec[k] for k in canonical_order} for rec in out_records]

    OUT_APP.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ordered, ensure_ascii=False, indent=2)
    OUT_APP.write_text(payload, encoding="utf-8")
    OUT_ROOT.write_text(payload, encoding="utf-8")

    print(f"Source rows (master_geocoded_patched_v1): {len(all_rows):,}")
    print(f"Published (publish_policy == publish):   {len(rows):,}")
    print(f"Hidden (state-only / muni-mismatch / external-review): {hidden:,}")
    print(f"Wrote {len(ordered):,} records to {OUT_APP}")
    print(f"Wrote {len(ordered):,} records to {OUT_ROOT}")
    if dropped_missing_coords:
        print(
            f"WARN: dropped {len(dropped_missing_coords)} row(s) with missing lat/lng: "
            f"{', '.join(dropped_missing_coords[:5])}"
            + (" …" if len(dropped_missing_coords) > 5 else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
