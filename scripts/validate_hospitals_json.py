#!/usr/bin/env python3
"""Validate the shape and contents of app/hospitals.json.

Runs in CI on every PR to catch silent regressions in the pipeline — missing
fields, out-of-range coordinates, or antivenom strings that slipped past the
canonicalizer. Exits non-zero on any violation; prints a summary on success.

Usage:
    python3 scripts/validate_hospitals_json.py app/hospitals.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 27 UFs (26 states + DF).
VALID_UF = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Brazil bounding box (approx): 5.27N–33.75S, -73.98W–-34.79W.
LAT_MIN, LAT_MAX = -34.0, 5.5
LNG_MIN, LNG_MAX = -74.5, -34.5

CANONICAL_ANTIVENOMS = {
    "Botrópico", "Crotálico", "Laquético", "Elapídico",
    "Escorpiônico", "Aracnídico", "Loxoscélico", "Fonêutrico", "Lonômico",
}

REQUIRED_FIELDS = ("state", "city", "hospital_name", "lat", "lng")


def validate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(f"ERROR: {path} must be a JSON array", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    def err(i: int, cnes: str, msg: str) -> None:
        errors.append(f"  [{i}] cnes={cnes or '?'}: {msg}")

    def warn(i: int, cnes: str, msg: str) -> None:
        warnings.append(f"  [{i}] cnes={cnes or '?'}: {msg}")

    for i, h in enumerate(data):
        cnes = h.get("cnes") or ""

        for f in REQUIRED_FIELDS:
            if h.get(f) in (None, ""):
                err(i, cnes, f"missing required field '{f}'")

        uf = (h.get("state") or "").strip().upper()
        if uf and uf not in VALID_UF:
            err(i, cnes, f"invalid UF {uf!r}")

        try:
            lat = float(h.get("lat"))
            lng = float(h.get("lng"))
        except (TypeError, ValueError):
            err(i, cnes, "lat/lng not numeric")
            continue

        if not (LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX):
            err(i, cnes, f"lat/lng ({lat}, {lng}) outside Brazil bbox")

        phones = h.get("phones") or []
        if not isinstance(phones, list):
            err(i, cnes, "phones must be an array")
        else:
            for p in phones:
                digits = "".join(ch for ch in str(p) if ch.isdigit())
                if p and len(digits) < 8:
                    warn(i, cnes, f"phone {p!r} has <8 digits")

        antivenoms = h.get("antivenoms") or []
        if not isinstance(antivenoms, list):
            err(i, cnes, "antivenoms must be an array")
        else:
            for a in antivenoms:
                if a not in CANONICAL_ANTIVENOMS:
                    err(i, cnes, f"antivenom {a!r} not in canonical set")

    if errors:
        print(f"FAIL: {len(errors)} error(s) in {path}", file=sys.stderr)
        for e in errors[:50]:
            print(e, file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1

    print(f"OK: {len(data):,} records validated in {path}")
    if warnings:
        print(f"  ({len(warnings)} warnings — phones under 8 digits)")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_hospitals_json.py <path-to-hospitals.json>", file=sys.stderr)
        return 2
    return validate(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
