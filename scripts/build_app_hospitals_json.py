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
    address        <- address                   (unless overridden via data/location_overrides.json)
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
OVERRIDES = ROOT / "data" / "location_overrides.json"
SOURCE_DATES = ROOT / "data" / "source_dates.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phone_utils import expand_phones  # noqa: E402

PDF_DATE_RE = re.compile(r"[A-Z]{2}_(\d{4})(\d{2})(\d{2})\.pdf$", re.IGNORECASE)

TIER_MAP = {
    "ROOFTOP": 1,
    "RANGE_INTERPOLATED": 2,
    "GEOMETRIC_CENTER": 3,
    "APPROXIMATE": 3,
}


def load_pdf_date_map() -> dict[str, str]:
    """Map UF -> ISO date of the source PDF.

    Prefers data/source_dates.json (committed to git, used by CI and fresh
    checkouts). Falls back to scanning Docs Estado/ so the local refresh
    workflow still works after a new PDF is downloaded.
    """
    if SOURCE_DATES.exists():
        data = json.loads(SOURCE_DATES.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k.upper(): str(v) for k, v in data.items()}
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
    """Expand Brazilian shared-prefix phone notation into full numbers.

    Delegates to `phone_utils.expand_phones`, which handles
    `(XX) YYYY-ABCD/EFGH` (shared exchange), `(XX) YYYY-ABCD/WWWW-QRST`
    (shared area code), and fully independent phones — the three real-world
    patterns seen in the PESA PDFs.
    """
    return expand_phones(raw)


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


def load_overrides() -> dict[str, dict]:
    """Load manual overrides keyed by CNES.

    Each value is a dict with any subset of: `lat`, `lng`, `address`, `note`.
    lat/lng must appear together; supplying either one alone is ignored.
    address and note may each appear alone. `note` renders as a short
    warning below the address in the app (e.g. "campus does not attend;
    go to the emergency unit"). Managed via the SoroJá overrides Google
    Sheet (see docs/PROCESS.md). Returns {} if the file is missing so
    this script stays runnable in a fresh checkout.
    """
    if not OVERRIDES.exists():
        return {}
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        sys.stderr.write(f"WARN: {OVERRIDES} is not a JSON object; ignoring.\n")
        return {}
    return data


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
    overrides = load_overrides()
    overrides_applied: list[str] = []
    overrides_unknown: list[str] = []

    with INPUT.open(encoding="utf-8", newline="") as fh:
        all_rows = list(csv.DictReader(fh))

    # Filter by publish_policy (set by apply_repairs.py)
    rows = [r for r in all_rows if (r.get("publish_policy") or "").strip() == "publish"]
    hidden = len(all_rows) - len(rows)

    published_cnes: set[str] = set()
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

        cnes = (r.get("cnes") or "").strip()
        record = {
            "state": uf,
            "state_name": state_name,
            "city": (r.get("municipality") or "").strip(),
            "hospital_name": (r.get("health_unit_name") or "").strip(),
            "address": (r.get("address") or "").strip(),
            "phones": clean_phones(r.get("phones_raw") or ""),
            "cnes": cnes,
            "antivenoms": split_antivenoms(r.get("antivenoms_raw") or ""),
            "source_date": source_date,
            "lat": lat,
            "lng": lng,
            "geocode_tier": TIER_MAP.get((r.get("location_type") or "").strip(), 3),
        }

        override = overrides.get(cnes) if cnes else None
        if override:
            applied_any = False
            if "lat" in override and "lng" in override:
                try:
                    record["lat"] = float(override["lat"])
                    record["lng"] = float(override["lng"])
                    record["geocode_tier"] = 1
                    applied_any = True
                except (TypeError, ValueError):
                    sys.stderr.write(
                        f"WARN: override for cnes {cnes} has invalid lat/lng; ignored.\n"
                    )
            address_override = str(override.get("address") or "").strip()
            if address_override:
                record["address"] = address_override
                applied_any = True
            note_override = str(override.get("note") or "").strip()
            if note_override:
                record["note"] = note_override
                applied_any = True
            if applied_any:
                overrides_applied.append(cnes)
            else:
                sys.stderr.write(
                    f"WARN: override for cnes {cnes} has no applicable fields; ignored.\n"
                )

        if cnes:
            published_cnes.add(cnes)
        out_records.append(record)

    for cnes in overrides:
        if cnes not in published_cnes:
            overrides_unknown.append(cnes)

    # Match key order of the current prod file for minimal git diff churn
    canonical_order = [
        "state", "state_name", "city", "hospital_name", "address",
        "phones", "cnes", "antivenoms", "source_date", "lat", "lng",
        "geocode_tier",
    ]
    # `note` is an optional field (override-driven only); emit it right after
    # `address` when present so the display grouping stays together.
    def _order(rec):
        out = {k: rec[k] for k in canonical_order}
        if "note" in rec:
            rebuilt = {}
            for k in canonical_order:
                rebuilt[k] = out[k]
                if k == "address":
                    rebuilt["note"] = rec["note"]
            return rebuilt
        return out
    ordered = [_order(rec) for rec in out_records]

    OUT_APP.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ordered, ensure_ascii=False, indent=2)
    OUT_APP.write_text(payload, encoding="utf-8")
    OUT_ROOT.write_text(payload, encoding="utf-8")

    print(f"Source rows (master_geocoded_patched_v1): {len(all_rows):,}")
    print(f"Published (publish_policy == publish):   {len(rows):,}")
    print(f"Hidden (state-only / muni-mismatch / external-review): {hidden:,}")
    print(f"Overrides applied: {len(overrides_applied)}")
    if overrides_unknown:
        print(
            f"WARN: {len(overrides_unknown)} override cnes not found in published set: "
            f"{', '.join(overrides_unknown[:5])}"
            + (" …" if len(overrides_unknown) > 5 else "")
        )
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
