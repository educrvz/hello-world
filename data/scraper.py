#!/usr/bin/env python3
"""
PESA Hospital PDF Scraper

Downloads and parses all 27 Brazilian state PDFs containing
anti-venom hospital (PESA) data from the Ministry of Health.

Usage:
    python3 scraper.py                    # Parse PDFs from data/pdfs/
    python3 scraper.py --download         # Download PDFs first, then parse
    python3 scraper.py --pdf-dir /path    # Use custom PDF directory
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip3 install pdfplumber")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None  # Optional — only needed for --download

# ─── State definitions ───────────────────────────────────────────────────────

STATES = {
    "acre":              ("AC", "Acre"),
    "alagoas":           ("AL", "Alagoas"),
    "amapa":             ("AP", "Amapá"),
    "amazonas":          ("AM", "Amazonas"),
    "bahia":             ("BA", "Bahia"),
    "ceara":             ("CE", "Ceará"),
    "distrito-federal":  ("DF", "Distrito Federal"),
    "espirito-santo":    ("ES", "Espírito Santo"),
    "goias":             ("GO", "Goiás"),
    "maranhao":          ("MA", "Maranhão"),
    "mato-grosso":       ("MT", "Mato Grosso"),
    "mato-grosso-do-sul":("MS", "Mato Grosso do Sul"),
    "minas-gerais":      ("MG", "Minas Gerais"),
    "para":              ("PA", "Pará"),
    "paraiba":           ("PB", "Paraíba"),
    "parana":            ("PR", "Paraná"),
    "pernambuco":        ("PE", "Pernambuco"),
    "piaui":             ("PI", "Piauí"),
    "rio-de-janeiro":    ("RJ", "Rio de Janeiro"),
    "rio-grande-do-norte":("RN", "Rio Grande do Norte"),
    "rio-grande-do-sul": ("RS", "Rio Grande do Sul"),
    "rondonia":          ("RO", "Rondônia"),
    "roraima":           ("RR", "Roraima"),
    "santa-catarina":    ("SC", "Santa Catarina"),
    "sao-paulo":         ("SP", "São Paulo"),
    "sergipe":           ("SE", "Sergipe"),
    "tocantins":         ("TO", "Tocantins"),
}

BASE_URL = (
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/"
    "animais-peconhentos/hospitais-de-referencia"
)

# ─── Known antivenom types ───────────────────────────────────────────────────

KNOWN_ANTIVENOMS = [
    "Botrópico", "Crotálico", "Laquético", "Elapídico",
    "Escorpiônico", "Fonêutrico", "Loxoscélico", "Lonômico",
    "Botrópico-Crotálico", "Botrópico-Laquético",
    "Antiaracnídico", "Antibotrópico", "Anticrotálico",
    "Antilaquético", "Antielapídico", "Antiescorpiônico",
]

# ─── Column detection patterns ───────────────────────────────────────────────

COLUMN_PATTERNS = {
    "city": [
        "município", "municipio", "cidade", "munic",
    ],
    "hospital_name": [
        "unidade de saúde", "unidade de saude", "unidade", "hospital",
        "estabelecimento", "nome da unidade", "nome",
    ],
    "address": [
        "endereço", "endereco", "logradouro", "end.",
    ],
    "phone": [
        "telefone", "telefones", "fone", "contato", "tel",
    ],
    "cnes": [
        "cnes", "código cnes", "codigo cnes", "cód. cnes",
    ],
    "antivenoms": [
        "antiveneno", "antivenenos", "soro", "soros",
        "antivenenos disponíveis", "antivenenos disponiveis",
        "tipo de soro", "tipos de soro",
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_columns(headers: list) -> dict:
    """
    Map raw column headers to normalized field names.
    Returns {column_index: field_name}.
    """
    mapping = {}
    for idx, raw in enumerate(headers):
        if not raw:
            continue
        norm = normalize_text(str(raw))
        if not norm:
            continue

        best_match = None
        best_score = 0

        for field, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                pat_norm = normalize_text(pattern)
                # Exact match
                if norm == pat_norm:
                    best_match = field
                    best_score = 100
                    break
                # Contains match
                if pat_norm in norm:
                    score = len(pat_norm)
                    if score > best_score:
                        best_match = field
                        best_score = score
                # Starts-with match
                if norm.startswith(pat_norm[:4]) and len(pat_norm) >= 4:
                    score = len(pat_norm) - 1
                    if score > best_score:
                        best_match = field
                        best_score = score
            if best_score == 100:
                break

        if best_match and best_match not in mapping.values():
            mapping[idx] = best_match

    return mapping


def is_header_row(row: list, header_map: dict) -> bool:
    """Check if a row is a repeated header (common in multi-page PDFs)."""
    if not row:
        return False
    non_empty = [str(c).strip() for c in row if c and str(c).strip()]
    if not non_empty:
        return True  # Empty row
    # A row is a header if multiple cells match column pattern names
    matches = 0
    for cell in non_empty:
        norm = normalize_text(cell)
        if len(norm) > 30:
            return False  # Data cells tend to be long; headers are short
        for patterns in COLUMN_PATTERNS.values():
            for pat in patterns:
                pat_norm = normalize_text(pat)
                if norm == pat_norm or (len(pat_norm) >= 5 and norm == pat_norm):
                    matches += 1
                    break
            else:
                continue
            break
    return matches >= 2  # Need at least 2 column-name matches to be a header


def is_empty_row(row: list) -> bool:
    """Check if a row is essentially empty."""
    if not row:
        return True
    non_empty = [c for c in row if c and str(c).strip()]
    return len(non_empty) <= 1


def parse_antivenoms(text: str) -> list:
    """Parse antivenom types from a cell value."""
    if not text or not text.strip():
        return []

    antivenoms = []
    # Try splitting by common delimiters
    parts = re.split(r"[;,/\n]+", text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Clean up common prefixes
        part = re.sub(r"^(soro\s+anti|anti)", "", part, flags=re.IGNORECASE).strip()
        if not part:
            continue

        # Try to match known types
        part_norm = normalize_text(part)
        matched = False
        for known in KNOWN_ANTIVENOMS:
            known_norm = normalize_text(known)
            if part_norm in known_norm or known_norm in part_norm:
                antivenoms.append(known)
                matched = True
                break

        if not matched and len(part) > 2:
            # Keep as-is with title case
            antivenoms.append(part.strip().title())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for a in antivenoms:
        a_norm = normalize_text(a)
        if a_norm not in seen:
            seen.add(a_norm)
            unique.append(a)

    return unique


def clean_phone(phone: str) -> str:
    """Clean and normalize a phone number string."""
    if not phone:
        return ""
    # Keep the original formatting but clean up
    phone = phone.strip()
    phone = re.sub(r"\s+", " ", phone)
    # Remove common noise
    phone = re.sub(r"(?i)(ramal|ext|r\.).*$", "", phone).strip()
    return phone


def parse_phones(text: str) -> list:
    """Parse multiple phone numbers from a cell value."""
    if not text or not text.strip():
        return []

    phones = []
    # Split by common delimiters
    parts = re.split(r"[;/\n]+", text)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Check if it looks like a phone number (has digits)
        digits = re.sub(r"\D", "", part)
        if len(digits) >= 8:
            phones.append(clean_phone(part))

    return phones


def extract_tables_from_pdf(pdf_path: str, state_slug: str) -> list:
    """
    Extract hospital data from a single state PDF using pdfplumber.
    Returns a list of hospital dicts.
    """
    state_code, state_name = STATES[state_slug]
    results = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            header_map = None
            current_city = None

            for page_num, page in enumerate(pdf.pages):
                # Try extracting table with default settings
                table = page.extract_table()

                if table is None:
                    # Try with explicit line-based settings
                    table = page.extract_table({
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 5,
                    })

                if table is None:
                    # Try text-based strategy
                    table = page.extract_table({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "snap_tolerance": 5,
                    })

                if table is None:
                    # Try extracting multiple tables
                    tables = page.extract_tables()
                    if tables:
                        table = tables[0]  # Use the first/largest table

                if table is None:
                    print(f"  WARNING: No table found on page {page_num + 1} of {state_slug}")
                    continue

                for row_idx, row in enumerate(table):
                    if not row:
                        continue

                    # Detect headers — keep trying rows until we find one
                    if not header_map:
                        candidate = normalize_columns(row)
                        if candidate:
                            header_map = candidate
                        # Either way, skip this row (it's a header or title)
                        continue

                    # Skip repeated headers and empty rows
                    if is_header_row(row, header_map) or is_empty_row(row):
                        continue

                    # Build record from row
                    record = {}
                    for col_idx, field_name in header_map.items():
                        if col_idx < len(row):
                            val = row[col_idx]
                            record[field_name] = str(val).strip() if val else ""

                    # Track city — some PDFs have city in a merged cell
                    # that only appears once for multiple hospitals
                    city = record.get("city", "").strip()
                    if city:
                        current_city = city
                    elif current_city:
                        record["city"] = current_city

                    # Skip rows without a hospital name
                    hospital_name = record.get("hospital_name", "").strip()
                    if not hospital_name or len(hospital_name) < 3:
                        continue

                    # Parse antivenoms
                    raw_antivenoms = record.get("antivenoms", "")
                    parsed_antivenoms = parse_antivenoms(raw_antivenoms)

                    # Parse phones
                    raw_phone = record.get("phone", "")
                    parsed_phones = parse_phones(raw_phone)
                    phone_str = " / ".join(parsed_phones) if parsed_phones else raw_phone.strip()

                    # Build final hospital entry
                    hospital = {
                        "state": state_code,
                        "state_name": state_name,
                        "city": record.get("city", "").strip(),
                        "hospital_name": hospital_name,
                        "address": record.get("address", "").strip(),
                        "phone": phone_str,
                        "cnes": record.get("cnes", "").strip(),
                        "antivenoms": parsed_antivenoms,
                        "lat": None,
                        "lng": None,
                    }

                    results.append(hospital)

    except Exception as e:
        print(f"  ERROR parsing {pdf_path}: {e}")

    return results


def download_pdf(state_slug: str, output_dir: str) -> str:
    """Download a state PDF from gov.br. Returns local path or None."""
    if requests is None:
        print("ERROR: requests library not available. Install with: pip3 install requests")
        return None

    url = f"{BASE_URL}/{state_slug}/@@download/file"
    output_path = os.path.join(output_dir, f"{state_slug}.pdf")

    if os.path.exists(output_path):
        print(f"  Already downloaded: {output_path}")
        return output_path

    for attempt in range(3):
        try:
            print(f"  Downloading {state_slug} (attempt {attempt + 1})...")
            resp = requests.get(url, timeout=30, allow_redirects=True)
            resp.raise_for_status()

            # Verify it's a PDF
            if not resp.content[:5].startswith(b"%PDF"):
                print(f"  WARNING: {state_slug} response is not a PDF (got HTML?)")
                return None

            with open(output_path, "wb") as f:
                f.write(resp.content)

            print(f"  Saved: {output_path} ({len(resp.content)} bytes)")
            return output_path

        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))

    print(f"  FAILED to download {state_slug} after 3 attempts")
    return None


def find_pdf_for_state(pdf_dir: str, slug: str, code: str) -> str:
    """
    Find a PDF file for a given state. Supports multiple naming conventions:
      - {slug}.pdf           (e.g., acre.pdf)
      - {CODE}_*.pdf         (e.g., AC_20260315.pdf)
      - {CODE}.pdf           (e.g., AC.pdf)
    Returns the file path or None.
    """
    # Try slug-based name first
    slug_path = os.path.join(pdf_dir, f"{slug}.pdf")
    if os.path.exists(slug_path):
        return slug_path

    # Try exact state code
    code_path = os.path.join(pdf_dir, f"{code}.pdf")
    if os.path.exists(code_path):
        return code_path

    # Try state code with date suffix (XX_YYYYMMDD.pdf pattern)
    import glob
    pattern = os.path.join(pdf_dir, f"{code}_*.pdf")
    matches = sorted(glob.glob(pattern))
    if matches:
        return matches[-1]  # Use the most recent by filename

    # Case-insensitive search for any of the above
    try:
        for f in os.listdir(pdf_dir):
            f_upper = f.upper()
            if f_upper == f"{code}.PDF" or f_upper.startswith(f"{code}_") and f_upper.endswith(".PDF"):
                return os.path.join(pdf_dir, f)
    except OSError:
        pass

    return None


def scrape_all(pdf_dir: str, download: bool = False) -> tuple:
    """
    Parse all state PDFs. Returns (hospitals, failures).

    Args:
        pdf_dir: Directory containing PDF files (supports multiple naming conventions:
                 {slug}.pdf, {STATE_CODE}.pdf, or {STATE_CODE}_YYYYMMDD.pdf)
        download: If True, download missing PDFs first
    """
    all_hospitals = []
    all_failures = []
    stats = {}

    if download:
        os.makedirs(pdf_dir, exist_ok=True)

    for slug, (code, name) in sorted(STATES.items()):
        # Download if requested and no PDF found
        if download and not find_pdf_for_state(pdf_dir, slug, code):
            downloaded = download_pdf(slug, pdf_dir)
            if not downloaded:
                all_failures.append({
                    "state": code,
                    "state_name": name,
                    "error": "Download failed",
                    "slug": slug,
                })
                stats[code] = 0
                continue

        # Find the PDF using flexible naming
        pdf_path = find_pdf_for_state(pdf_dir, slug, code)

        # Check if PDF exists
        if not pdf_path:
            print(f"[{code}] {name}: No PDF found in {pdf_dir} (tried {slug}.pdf, {code}.pdf, {code}_*.pdf)")
            all_failures.append({
                "state": code,
                "state_name": name,
                "error": f"PDF not found in {pdf_dir}",
                "slug": slug,
            })
            stats[code] = 0
            continue

        # Parse the PDF
        print(f"[{code}] {name}: Parsing {pdf_path}...")
        hospitals = extract_tables_from_pdf(pdf_path, slug)
        count = len(hospitals)
        stats[code] = count

        if count == 0:
            print(f"  WARNING: No hospitals extracted from {slug}")
            all_failures.append({
                "state": code,
                "state_name": name,
                "error": "No hospitals extracted from PDF",
                "slug": slug,
            })
        else:
            print(f"  Extracted {count} hospitals")
            all_hospitals.extend(hospitals)

    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    total = sum(stats.values())
    for code in sorted(stats.keys()):
        count = stats[code]
        status = "OK" if count > 0 else "FAILED"
        print(f"  {code}: {count} hospitals [{status}]")
    print(f"\n  Total: {total} hospitals from {sum(1 for c in stats.values() if c > 0)}/{len(STATES)} states")
    print(f"  Failures: {len(all_failures)}")

    return all_hospitals, all_failures


def main():
    import argparse

    parser = argparse.ArgumentParser(description="PESA Hospital PDF Scraper")
    parser.add_argument("--download", action="store_true",
                        help="Download PDFs from gov.br before parsing")
    parser.add_argument("--pdf-dir", default=None,
                        help="Directory containing PDFs (default: data/pdfs)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file (default: data/hospitals_raw.json)")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    pdf_dir = args.pdf_dir or str(script_dir / "pdfs")
    output_path = args.output or str(script_dir / "hospitals_raw.json")

    print(f"PDF directory: {pdf_dir}")
    print(f"Output: {output_path}")
    print()

    hospitals, failures = scrape_all(pdf_dir, download=args.download)

    # Write hospitals_raw.json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hospitals, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(hospitals)} hospitals to {output_path}")

    # Write failures
    if failures:
        fail_path = str(Path(output_path).parent / "hospitals_failed_scrape.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failures, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(failures)} failures to {fail_path}")


if __name__ == "__main__":
    main()
