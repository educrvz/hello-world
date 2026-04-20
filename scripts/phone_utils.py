#!/usr/bin/env python3
"""Brazilian phone-number normalization shared by the pipeline scripts.

The source PDFs compress related phone numbers with `/`, and the compression
comes in three flavors:

    1. shared exchange, different last-N digits:
       "(97) 3471-1413/1475"           -> ["(97) 3471-1413", "(97) 3471-1475"]
       "(11) 4656-8150/8151/8152"      -> ["(11) 4656-8150", "(11) 4656-8151", "(11) 4656-8152"]
       "(16) 3761-9474 / 9499"         -> ["(16) 3761-9474", "(16) 3761-9499"]

    2. shared area code, different exchange (each piece has its own ABCD-WXYZ):
       "(79) 3254-8074/3279-1125"      -> ["(79) 3254-8074", "(79) 3279-1125"]
       "(18) 3322-3553/3302-6069"      -> ["(18) 3322-3553", "(18) 3302-6069"]

    3. fully independent phones (each piece starts with its own area code):
       "(11) 3394-8770/(11) 3394-6980" -> ["(11) 3394-8770", "(11) 3394-6980"]
       "(61) 99981-9012, (61) 33426789" -> ["(61) 99981-9012", "(61) 33426789"]

Earlier pipeline versions split naively on `/` and left tokens like "1475"
standing alone — which rendered as nonsense in the app. `expand_phones`
handles all three flavors and returns clean full-formed phone strings.

Also filters placeholder entries (`sem contato`, `****`, `não disponível`, …).
"""

from __future__ import annotations

import re

PLACEHOLDERS = {
    "",
    "-",
    "--",
    "***",
    "****",
    "*****",
    "n/a",
    "nd",
    "não disponível",
    "nao disponivel",
    "não informado",
    "nao informado",
    "sem contato",
    "sem telefone",
    "indisponível",
    "indisponivel",
}

_AREA_CODE_RE = re.compile(r"^\s*\(\s*(\d{2,3})\s*\)\s*")
# Accept dash-with-optional-spaces OR whitespace as the exchange/number
# separator. Source PDFs are inconsistent: "3415-8700", "3415 8700",
# "3620 - 0155" all appear.
_SEPARATOR_IN_NUMBER = r"(?:\s*-\s*|\s+)"
_EXCHANGE_NUMBER_RE = re.compile(
    r"^(\d{3,5})" + _SEPARATOR_IN_NUMBER + r"(\d{3,5})\b"
)
_FULL_EXCHANGE_NUMBER_RE = re.compile(
    r"^\d{3,5}" + _SEPARATOR_IN_NUMBER + r"\d{3,5}$"
)

# Separators that group related phones. `/` is the canonical shared-prefix
# separator; `,` is often used the same way (especially in MG extractions);
# " e " / " E " is the Portuguese "and" between two numbers in the same row.
_SEPARATOR_RE = re.compile(r"\s*(?:/|,|\s+[eE]\s+)\s*")


def _parse_reference(ref: str) -> tuple[str, str | None]:
    """Return (area_prefix, prefix_for_short_suffix).

    area_prefix         — e.g. "(97) " — what to prepend to a bare "NNNN-NNNN"
    prefix_for_suffix   — e.g. "(97) 3471-" — what to prepend to a bare "NNNN"

    Either may be empty/None if the reference phone doesn't have that piece
    (e.g. local numbers without an area code, or numbers that aren't shaped
    like "NNNN-NNNN").
    """
    area_match = _AREA_CODE_RE.match(ref)
    if area_match:
        area_prefix = ref[: area_match.end()]
        rest = ref[area_match.end():].lstrip()
    else:
        area_prefix = ""
        rest = ref.strip()

    en_match = _EXCHANGE_NUMBER_RE.match(rest)
    if en_match:
        exchange = en_match.group(1)
        prefix_for_suffix = f"{area_prefix}{exchange}-"
    else:
        prefix_for_suffix = None

    return area_prefix, prefix_for_suffix


_MISSING_OPEN_PAREN = re.compile(r"^(\d{2,3})\)\s*(.+)$")
_BARE_AREA_PREFIX = re.compile(r"^(\d{2})\s+(\d{3,}.*)$")


def _format_phone(p: str) -> str:
    """Light cosmetic pass: rescue `38) 3614-1252` and `75 92051989` shapes
    into `(38) 3614-1252` and `(75) 92051989`. Leaves 0800 toll-free,
    already-parenthesized, and free-form values alone.
    """
    m = _MISSING_OPEN_PAREN.match(p)
    if m:
        return f"({m.group(1)}) {m.group(2)}"
    m = _BARE_AREA_PREFIX.match(p)
    if m:
        return f"({m.group(1)}) {m.group(2)}"
    return p


def expand_phones(raw: str | None) -> list[str]:
    """Parse a raw `phones_raw` value into a list of complete phone strings.

    Splits on `/`, `,` and the Portuguese `e`/`E` separator, then carries
    the most-recently-seen area code (and exchange) forward so that bare
    fragments like ``1475`` or ``3239-9308`` get reconstructed as
    ``(97) 3471-1475`` and ``(31) 3239-9308``.

    Drops placeholder tokens. Dedupes while preserving source order.
    """
    if not raw:
        return []

    parts = [p.strip() for p in _SEPARATOR_RE.split(raw.strip()) if p.strip()]
    if not parts:
        return []

    out: list[str] = []
    seen: set[str] = set()
    current_area: str = ""
    current_exchange_prefix: str | None = None

    def emit(phone: str) -> None:
        p = phone.strip()
        if not p:
            return
        if p.lower() in PLACEHOLDERS:
            return
        if sum(ch.isdigit() for ch in p) < 4:
            return
        p = _format_phone(p)
        if p in seen:
            return
        seen.add(p)
        out.append(p)

    for p in parts:
        if _AREA_CODE_RE.match(p):
            emit(p)
            current_area, current_exchange_prefix = _parse_reference(p)
            continue

        if _FULL_EXCHANGE_NUMBER_RE.match(p):
            # Bare "NNNN-NNNN" — belongs to the most recent area code.
            emit(f"{current_area}{p}" if current_area else p)
            continue

        if p.isdigit() and len(p) <= 5:
            # Bare numeric suffix — reuse the latest exchange prefix if any.
            if current_exchange_prefix:
                emit(f"{current_exchange_prefix}{p}")
            else:
                emit(p)
            continue

        # Unknown shape (e.g. "Ramal 2030"). Prefer to emit it qualified
        # with the current area code if one exists and the fragment
        # contains digits; otherwise keep whatever the source had.
        digits_only = re.sub(r"\D", "", p)
        if current_area and digits_only and len(digits_only) >= 4:
            emit(f"{current_area}{p}")
        else:
            emit(p)

    return out


# ---------------------------------------------------------------------------
# Quick self-test (run with `python3 scripts/phone_utils.py`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cases: list[tuple[str, list[str]]] = [
        ("(97) 3471-1413/1475",
         ["(97) 3471-1413", "(97) 3471-1475"]),
        ("(11) 4656-8150/8151/8152",
         ["(11) 4656-8150", "(11) 4656-8151", "(11) 4656-8152"]),
        ("(16) 3761-9474 / 9499",
         ["(16) 3761-9474", "(16) 3761-9499"]),
        ("(79) 3254-8074/3279-1125",
         ["(79) 3254-8074", "(79) 3279-1125"]),
        ("(18) 3322-3553/3302-6069",
         ["(18) 3322-3553", "(18) 3302-6069"]),
        ("(79) 3611-1321/1194",
         ["(79) 3611-1321", "(79) 3611-1194"]),
        ("(84) 3522-1314/2354/5888",
         ["(84) 3522-1314", "(84) 3522-2354", "(84) 3522-5888"]),
        ("(97) 3412-2403",
         ["(97) 3412-2403"]),
        ("",
         []),
        (None,
         []),
        ("sem contato",
         []),
        ("(61) 99981-9012, (61) 33426789",
         ["(61) 99981-9012", "(61) 33426789"]),
        ("(84) 3315-3379/3414",
         ["(84) 3315-3379", "(84) 3315-3414"]),
        # Dedupe: same suffix twice becomes one entry
        ("(97) 3471-1413/1413",
         ["(97) 3471-1413"]),
        # Real-world MG case: commas carry shared area code, " e " too
        ("(31)3224-4000, 3239-9308, 3239-9223 e 3239-9224",
         ["(31)3224-4000", "(31)3239-9308", "(31)3239-9223", "(31)3239-9224"]),
        # Two independent phones with full area codes — each must carry its own
        ("(84) 9999-1111, (85) 8888-2222",
         ["(84) 9999-1111", "(85) 8888-2222"]),
        # Exchange uses SPACE instead of dash (MG/Iturama)
        ("(34) 3415 8700 /8715 /8735",
         ["(34) 3415 8700", "(34) 3415-8715", "(34) 3415-8735"]),
        # Space between digits and dash, then suffix (GO/Luziania)
        ("(61) 3620 - 0155/0111",
         ["(61) 3620 - 0155", "(61) 3620-0111"]),
        # RS/Alegrete — space exchange + suffix
        ("(55) 3422 2888/4266",
         ["(55) 3422 2888", "(55) 3422-4266"]),
        # Cosmetic: missing opening paren
        ("38) 3614-1252",
         ["(38) 3614-1252"]),
        # Cosmetic: bare area-code prefix without parens
        ("75 92051989",
         ["(75) 92051989"]),
        ("14 997103613",
         ["(14) 997103613"]),
        # 0800 toll-free must NOT be rewrapped
        ("0800 722 6001",
         ["0800 722 6001"]),
        ("0800-7226001",
         ["0800-7226001"]),
    ]

    failed = 0
    for raw, expected in cases:
        got = expand_phones(raw)
        ok = got == expected
        flag = "ok " if ok else "FAIL"
        print(f"{flag}  raw={raw!r}")
        if not ok:
            print(f"        expected={expected}")
            print(f"        got     ={got}")
            failed += 1
    print()
    if failed:
        print(f"{failed} FAILED")
        raise SystemExit(1)
    print(f"All {len(cases)} cases passed.")
