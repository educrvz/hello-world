#!/usr/bin/env python3
"""Targeted repair workflow for v3 high-risk rows.

For each of the 14 rows in build/high_risk_exception_queue_v1.csv:
  1. Generate up to 5 deterministic candidate geocode queries (no invented data).
  2. Re-run Google geocoding on each candidate.
  3. Score each candidate using a transparent rubric.
  4. Pick the best-scoring candidate per original row.
  5. Emit per-candidate CSV, best-per-row CSV, and summary report.

Main dataset is not modified. Requires GOOGLE_MAPS_API_KEY in env or
macOS Keychain (service=google_maps_api_key, account=$USER).
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"
QUEUE = BUILD / "high_risk_exception_queue_v1.csv"
MASTER = BUILD / "master_geocoded.csv"
OUT_CAND = BUILD / "high_risk_repair_candidates.csv"
OUT_BEST = BUILD / "high_risk_repair_best_attempts.csv"
RAW_LOG = BUILD / "high_risk_repair_raw_responses.jsonl"
REPORT = REPORTS / "09b_high_risk_repair_summary.md"

GEOCODE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
PROVIDER_ID = "google_maps_geocoding_v1"
INTER_REQUEST_DELAY = 0.15

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
UF_END_RE = re.compile(r"-\s*([A-Z]{2})(?=\s*(?:,|$))")
HIGHWAY_FIRST_SEG_RE = re.compile(
    r"^\s*(?:BR[-–]\d+|SP[-–]\d+|MG[-–]\d+|Rodovia\b|Estrada\b|Via\s+\w+\b)",
    re.IGNORECASE,
)
SPECIAL_UNIT_PATTERNS = re.compile(
    r"(?:\bpolo\s*base\b|\bubsi\b|\bmiss[ãa]o\b|\bpelot[ãa]o\b|\bfronteira\b"
    r"|\bbase\s*ind[ií]gena\b|\bind[ií]gena\b|\byanomami\b|\bianomami\b"
    r"|\bdsei\b|\bpef\b|\bcasai\b|\baldeia\b)",
    re.IGNORECASE,
)

PLACE_ID_REUSE_THRESHOLD = 3
KEYCHAIN_SERVICE = "google_maps_api_key"


# ----- API key ---------------------------------------------------------------
def read_api_key() -> str | None:
    env = os.environ.get("GOOGLE_MAPS_API_KEY")
    if env:
        return env.strip()
    if sys.platform != "darwin" or shutil.which("security") is None:
        return None
    user = os.environ.get("USER") or ""
    cmd = ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"]
    if user:
        cmd.extend(["-a", user])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


# ----- Helpers ---------------------------------------------------------------
def iso_now() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def strip_accents_lower(s: str) -> str:
    s = s or ""
    nkfd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nkfd if not unicodedata.combining(c)).lower()


def parse_geocoded_uf_strict(fa: str) -> str | None:
    if not fa:
        return None
    matches = UF_END_RE.findall(fa)
    for uf in reversed(matches):
        if uf in UF_CODES:
            return uf
    return None


def coords_in_brazil(lat, lng) -> bool:
    try:
        lat_f = float(lat); lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return BR_LAT[0] <= lat_f <= BR_LAT[1] and BR_LNG[0] <= lng_f <= BR_LNG[1]


def has_non_brazil_country(fa: str) -> bool:
    if not fa:
        return False
    last = fa.rsplit(",", 1)[-1].strip().lower()
    return bool(last) and last not in {"brasil", "brazil"}


def formatted_is_generic(fa: str) -> bool:
    if not fa:
        return True
    parts = [p.strip() for p in fa.split(",") if p.strip()]
    if len(parts) < 4:
        return True
    if HIGHWAY_FIRST_SEG_RE.match(parts[0]) and not re.search(r"\d+", parts[0]):
        return True
    return False


def is_special_unit(name: str) -> bool:
    return bool(SPECIAL_UNIT_PATTERNS.search(name or ""))


def municipality_in_fa(muni: str, fa: str) -> bool:
    return bool(muni and fa) and strip_accents_lower(muni) in strip_accents_lower(fa)


# ----- Query generation -----------------------------------------------------
def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def normalize_unit_name(name: str) -> str:
    """Drop parenthetical content and honorific-triggered tails.

    Examples:
      "Hospital Geral do Grajaú Prof. Liber John Alphonse Di Dio"
        -> "Hospital Geral do Grajaú"
      "UPA Dr. Pedro T. F. Reis" -> "UPA"
      "Hospital São Camilo (Unidade 2)" -> "Hospital São Camilo"
    """
    if not name:
        return ""
    s = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    # Truncate before honorific/person-name tokens
    s = re.split(
        r"\s+(?:Dr\.?|Dra\.?|Prof\.?|Professora?|Mons\.?|Pref\.?|Pe\.?|Sr\.?|Sra\.?|Gov\.?|Desembargador|Maestro)\b",
        s, maxsplit=1,
    )[0]
    # Strip trailing punctuation/dash patterns
    s = re.sub(r"[\-–—]\s*$", "", s).strip()
    return clean_ws(s)


def join_query(*parts: str) -> str:
    clean = [clean_ws(p) for p in parts if p and clean_ws(p)]
    # dedupe consecutive duplicates (e.g. municipality already inside address)
    out = []
    for p in clean:
        if not out or strip_accents_lower(out[-1]) != strip_accents_lower(p):
            out.append(p)
    return ", ".join(out)


def generate_candidates(row: dict) -> list[dict]:
    """Deterministic candidate queries. Never invents new facts — uses only
    fields present on the row."""
    unit = clean_ws(row.get("health_unit_name", ""))
    addr = clean_ws(row.get("address", ""))
    muni = clean_ws(row.get("municipality", ""))
    state_name = clean_ws(row.get("state", ""))
    state_uf = clean_ws(row.get("source_state_abbr", ""))
    special = is_special_unit(unit)
    norm_unit = normalize_unit_name(unit)

    candidates: list[dict] = []
    seen: set[str] = set()

    def add(pattern: str, query: str):
        q = clean_ws(query)
        if not q:
            return
        key = strip_accents_lower(q)
        if key in seen:
            return
        seen.add(key)
        candidates.append({"pattern": pattern, "query": q})

    # Pattern A: unit + muni + state name (no address) — often wins when
    # the source address is sparse or ambiguous.
    if unit and muni and state_name:
        add("unit_muni_state", join_query(unit, muni, state_name, "Brasil"))

    # Pattern B: unit + muni - UF form — useful when state_name form is
    # unusual or spelled differently from Google's expectation.
    if unit and muni and state_uf:
        add("unit_muni_uf", join_query(unit, f"{muni} - {state_uf}", "Brasil"))

    # Pattern C: normalized unit + muni + state — strips honorifics/person
    # tails that may drag Google toward a different place.
    if norm_unit and norm_unit != unit and muni and state_name:
        add(
            "normalized_unit_muni_state",
            join_query(norm_unit, muni, state_name, "Brasil"),
        )

    # Pattern D: address + muni + state (no unit) — helps when the unit
    # name itself is what's confusing the geocoder. For special units we
    # prefer this ordering.
    if addr and muni and state_name:
        add("addr_muni_state", join_query(addr, muni, state_name, "Brasil"))

    # Pattern E: unit + full address + muni + state (baseline-like)
    if unit and addr and muni and state_name:
        add(
            "unit_addr_muni_state",
            join_query(unit, addr, muni, state_name, "Brasil"),
        )

    # For special remote/indigenous/military units, bias toward locality
    # only (address + muni + state) if we haven't already promoted it.
    if special and addr and muni and state_name:
        promoted = {"pattern": "locality_only_special", "query": join_query(addr, muni, state_name, "Brasil")}
        pk = strip_accents_lower(promoted["query"])
        if pk not in seen:
            seen.add(pk)
            candidates.insert(0, promoted)

    return candidates[:5]


# ----- Geocoding ------------------------------------------------------------
def fetch_geocode(query: str, api_key: str) -> tuple[str, dict | None, str | None]:
    if not clean_ws(query):
        return "NOT_ATTEMPTED_EMPTY_QUERY", None, None
    params = urllib.parse.urlencode({
        "address": query,
        "key": api_key,
        "region": "br",
        "language": "pt-BR",
    })
    url = f"{GEOCODE_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "sos-antiveneno-geocoder/1.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = resp.read()
            data = json.loads(payload)
            status = data.get("status", "UNKNOWN_ERROR")
            if status in {"OK", "ZERO_RESULTS", "INVALID_REQUEST"}:
                return status, data, data.get("error_message")
            if status == "REQUEST_DENIED":
                return status, data, data.get("error_message")
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            time.sleep(2 ** attempt)
            last_err = f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001
            return "NETWORK_ERROR", None, f"{type(e).__name__}: {e}"
    return "UNKNOWN_ERROR", None, "exhausted retries"


# ----- Scoring --------------------------------------------------------------
def score_result(
    source_row: dict,
    status: str,
    data: dict | None,
    suspicious_place_ids: set[str],
) -> tuple[int, list[str], dict]:
    """Returns (score, reasons, extract) where extract has the usable fields
    (formatted_address, lat, lng, place_id, partial_match, location_type)."""
    extract = {
        "formatted_address": "", "lat": "", "lng": "",
        "place_id": "", "partial_match": "", "location_type": "",
        "status": status,
    }
    reasons: list[str] = []

    if status != "OK" or not data or not data.get("results"):
        return -1000, [f"no_result ({status})"], extract

    first = data["results"][0]
    fa = first.get("formatted_address", "") or ""
    loc = first.get("geometry", {}).get("location", {}) or {}
    lat = loc.get("lat")
    lng = loc.get("lng")
    lt = first.get("geometry", {}).get("location_type", "") or ""
    pid = first.get("place_id", "") or ""
    pm = bool(first.get("partial_match", False))

    extract.update({
        "formatted_address": fa,
        "lat": lat if lat is not None else "",
        "lng": lng if lng is not None else "",
        "place_id": pid,
        "partial_match": "true" if pm else "false",
        "location_type": lt,
    })

    score = 0

    # Country / in-Brazil
    if has_non_brazil_country(fa):
        score -= 200
        reasons.append(f"non_brazil_country({fa.rsplit(',',1)[-1].strip()}) -200")
    if coords_in_brazil(lat, lng):
        score += 50; reasons.append("in_brazil +50")
    else:
        score -= 200; reasons.append("out_of_brazil -200")

    # State
    expected_uf = (source_row.get("source_state_abbr") or "").strip().upper()
    geo_uf = parse_geocoded_uf_strict(fa)
    if geo_uf and expected_uf:
        if geo_uf == expected_uf:
            score += 40; reasons.append(f"state_match({geo_uf}) +40")
        else:
            score -= 80; reasons.append(f"state_mismatch({geo_uf}!={expected_uf}) -80")
    else:
        reasons.append("state_unknown")

    # Municipality
    muni = (source_row.get("municipality") or "").strip()
    if muni:
        if municipality_in_fa(muni, fa):
            score += 30; reasons.append("muni_in_fa +30")
        else:
            score -= 30; reasons.append("muni_not_in_fa -30")

    # Location type
    lt_score = {"ROOFTOP": 40, "RANGE_INTERPOLATED": 25, "GEOMETRIC_CENTER": 20, "APPROXIMATE": 5}
    score += lt_score.get(lt, 0)
    reasons.append(f"loc_type={lt or 'blank'} +{lt_score.get(lt, 0)}")

    # Generic FA
    if formatted_is_generic(fa):
        score -= 15; reasons.append("generic_fa -15")
    else:
        score += 15; reasons.append("specific_fa +15")

    # place_id reuse
    if pid and pid in suspicious_place_ids:
        score -= 50; reasons.append("reused_place_id -50")

    # partial_match is informational, tiny penalty only when combined with
    # non-ROOFTOP
    if pm and lt != "ROOFTOP":
        score -= 5; reasons.append("partial+non_rooftop -5")

    return score, reasons, extract


# ----- Main -----------------------------------------------------------------
def compute_suspicious_place_ids() -> set[str]:
    origins: dict[str, set[tuple[str, str]]] = defaultdict(set)
    with MASTER.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("place_id") or "").strip()
            if not pid:
                continue
            origins[pid].add((
                strip_accents_lower(r.get("municipality_clean") or ""),
                (r.get("state_clean") or "").upper(),
            ))
    return {p for p, o in origins.items() if len(o) >= PLACE_ID_REUSE_THRESHOLD}


def classify_outcome(old_score: int, best_score: int, best_reasons: list[str]) -> str:
    """Translate score delta into a repair_outcome string."""
    has_severe = any(
        tag in r for r in best_reasons
        for tag in ("non_brazil_country", "out_of_brazil", "state_mismatch", "reused_place_id")
    )
    if best_score <= -500:
        return "inconclusive"
    if best_score <= old_score:
        return "unchanged_bad"
    if best_score > old_score + 40 and best_score >= 80 and not has_severe:
        return "improved_confidently"
    if best_score > old_score:
        return "improved_but_still_review"
    return "unchanged_bad"


def main() -> int:
    api_key = read_api_key()
    if not api_key:
        sys.stderr.write("ERROR: no Google Maps API key available.\n")
        return 2

    BUILD.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    suspicious_pids = compute_suspicious_place_ids()

    with QUEUE.open(encoding="utf-8", newline="") as fh:
        queue_rows = list(csv.DictReader(fh))

    cand_cols = [
        "row_id", "candidate_number", "candidate_pattern", "candidate_query",
        "status", "formatted_address", "lat", "lng", "place_id",
        "partial_match", "location_type", "candidate_score", "candidate_reasons",
    ]
    best_cols = [
        "row_id", "source_state_abbr", "municipality", "health_unit_name",
        "old_formatted_address", "old_lat", "old_lng", "old_place_id",
        "old_score", "old_review_reasons",
        "best_candidate_pattern", "best_candidate_query",
        "best_formatted_address", "best_lat", "best_lng", "best_place_id",
        "best_partial_match", "best_location_type", "best_candidate_score",
        "best_candidate_reasons", "score_delta", "repair_outcome",
    ]

    all_candidates: list[dict] = []
    best_rows: list[dict] = []

    with RAW_LOG.open("a", encoding="utf-8") as raw_out:
        for src in queue_rows:
            rid = src["row_id"]
            # Score the current (old) result to get a baseline
            old_status = "OK" if src.get("formatted_address") else "NOT_OK"
            synthetic_old_data = None
            if src.get("formatted_address"):
                synthetic_old_data = {
                    "results": [{
                        "formatted_address": src.get("formatted_address", ""),
                        "geometry": {
                            "location": {
                                "lat": float(src["lat"]) if src.get("lat") else None,
                                "lng": float(src["lng"]) if src.get("lng") else None,
                            },
                            "location_type": src.get("location_type", ""),
                        },
                        "place_id": src.get("place_id", ""),
                        "partial_match": src.get("partial_match", "") == "true",
                    }]
                }
            old_score, old_reasons, _ = score_result(
                src, old_status, synthetic_old_data, suspicious_pids
            )

            candidates = generate_candidates(src)
            attempts = []
            for i, c in enumerate(candidates, start=1):
                status, data, err = fetch_geocode(c["query"], api_key)
                score, reasons, extract = score_result(src, status, data, suspicious_pids)
                raw_out.write(json.dumps({
                    "row_id": rid,
                    "candidate_number": i,
                    "pattern": c["pattern"],
                    "query": c["query"],
                    "status": status,
                    "error": err,
                    "score": score,
                    "attempted_at": iso_now(),
                    "response": data,
                }, ensure_ascii=False))
                raw_out.write("\n")
                row = {
                    "row_id": rid,
                    "candidate_number": i,
                    "candidate_pattern": c["pattern"],
                    "candidate_query": c["query"],
                    "status": status,
                    "formatted_address": extract["formatted_address"],
                    "lat": extract["lat"],
                    "lng": extract["lng"],
                    "place_id": extract["place_id"],
                    "partial_match": extract["partial_match"],
                    "location_type": extract["location_type"],
                    "candidate_score": score,
                    "candidate_reasons": "; ".join(reasons),
                }
                attempts.append((score, reasons, extract, c, row))
                all_candidates.append(row)
                time.sleep(INTER_REQUEST_DELAY)

            if attempts:
                best_score, best_reasons, best_extract, best_cand, best_row = max(
                    attempts, key=lambda x: x[0]
                )
            else:
                best_score, best_reasons, best_extract, best_cand = old_score, [], {}, {"pattern": "", "query": ""}
                best_row = {}

            outcome = classify_outcome(old_score, best_score, best_reasons)

            best_rows.append({
                "row_id": rid,
                "source_state_abbr": src.get("source_state_abbr", ""),
                "municipality": src.get("municipality", ""),
                "health_unit_name": src.get("health_unit_name", ""),
                "old_formatted_address": src.get("formatted_address", ""),
                "old_lat": src.get("lat", ""),
                "old_lng": src.get("lng", ""),
                "old_place_id": src.get("place_id", ""),
                "old_score": old_score,
                "old_review_reasons": src.get("review_reasons", ""),
                "best_candidate_pattern": best_cand.get("pattern", ""),
                "best_candidate_query": best_cand.get("query", ""),
                "best_formatted_address": best_extract.get("formatted_address", "") if best_extract else "",
                "best_lat": best_extract.get("lat", "") if best_extract else "",
                "best_lng": best_extract.get("lng", "") if best_extract else "",
                "best_place_id": best_extract.get("place_id", "") if best_extract else "",
                "best_partial_match": best_extract.get("partial_match", "") if best_extract else "",
                "best_location_type": best_extract.get("location_type", "") if best_extract else "",
                "best_candidate_score": best_score,
                "best_candidate_reasons": "; ".join(best_reasons),
                "score_delta": best_score - old_score,
                "repair_outcome": outcome,
            })

    with OUT_CAND.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cand_cols, extrasaction="ignore")
        w.writeheader()
        for r in all_candidates:
            w.writerow(r)

    with OUT_BEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=best_cols, extrasaction="ignore")
        w.writeheader()
        for r in best_rows:
            w.writerow(r)

    # ---------------- summary report ----------------
    from collections import Counter
    outcome_counts = Counter(r["repair_outcome"] for r in best_rows)

    lines: list[str] = []
    lines.append("# High-Risk Repair Summary")
    lines.append("")
    lines.append(f"**Input queue:** `{QUEUE.relative_to(ROOT)}`")
    lines.append(f"**Candidates CSV:** `{OUT_CAND.relative_to(ROOT)}`")
    lines.append(f"**Best attempts CSV:** `{OUT_BEST.relative_to(ROOT)}`")
    lines.append(f"**Raw API responses:** `{RAW_LOG.relative_to(ROOT)}`")
    lines.append("")
    lines.append(f"**Rows processed:** {len(best_rows)}")
    lines.append(f"**Candidate queries attempted:** {len(all_candidates)}")
    lines.append("")
    lines.append("## Counts by `repair_outcome`")
    lines.append("")
    lines.append("| Outcome | Count |")
    lines.append("|---------|------:|")
    for k in ("improved_confidently", "improved_but_still_review", "unchanged_bad", "inconclusive"):
        lines.append(f"| `{k}` | {outcome_counts.get(k, 0)} |")
    lines.append("")

    lines.append("## All 14 rows — old vs new")
    lines.append("")
    lines.append("| row_id | UF | Muni | Outcome | Δscore | Old FA | Best FA | Best loc_type |")
    lines.append("|--------|----|------|---------|-------:|--------|---------|---------------|")
    for r in best_rows:
        old_fa = (r["old_formatted_address"] or "").replace("|", "\\|")[:55]
        new_fa = (r["best_formatted_address"] or "").replace("|", "\\|")[:55]
        lines.append(
            f"| `{r['row_id']}` | {r['source_state_abbr']} | "
            f"{r['municipality']} | `{r['repair_outcome']}` | "
            f"{r['score_delta']:+d} | {old_fa} | {new_fa} | "
            f"`{r['best_location_type']}` |"
        )
    lines.append("")

    unresolved = [
        r for r in best_rows
        if r["repair_outcome"] in ("unchanged_bad", "inconclusive", "improved_but_still_review")
    ]
    lines.append(f"## Rows still unresolved ({len(unresolved)})")
    lines.append("")
    if unresolved:
        lines.append("| row_id | Outcome | Best score | Best reasons |")
        lines.append("|--------|---------|-----------:|--------------|")
        for r in unresolved:
            reasons = (r["best_candidate_reasons"] or "").replace("|", "\\|")
            lines.append(
                f"| `{r['row_id']}` | `{r['repair_outcome']}` | "
                f"{r['best_candidate_score']} | {reasons} |"
            )
    else:
        lines.append("_None — every high-risk row was repaired confidently._")
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    n_confident = outcome_counts.get("improved_confidently", 0)
    n_unresolved = len(unresolved)
    lines.append(f"- **{n_confident}** row(s) are good candidates for a targeted "
                 "patch of the main dataset (write-through in a follow-up step).")
    if n_unresolved:
        lines.append(f"- **{n_unresolved}** row(s) remain unresolved by deterministic candidate "
                     "queries. Recommendation: move them to a tiny external-review batch "
                     "(CNES DATASUS lookup or state health-department portal) rather than "
                     "burning more geocode budget — the upside is small and the "
                     "signal-to-noise is now low.")
    else:
        lines.append("- No external review batch needed.")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Rows processed: {len(best_rows)}")
    print(f"Outcomes: {dict(outcome_counts)}")
    print(f"-> {OUT_CAND}")
    print(f"-> {OUT_BEST}")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
