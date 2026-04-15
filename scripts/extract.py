#!/usr/bin/env python3
"""
Extract hospital data from 27 Brazilian state PESA PDFs.
Outputs hospitals_raw.json with structured data for each hospital.
"""

import json
import os
import re
import sys
import unicodedata

import pdfplumber

PDF_DIR = os.path.join(os.path.dirname(__file__), "..")

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí",
    "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul",
    "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}

KNOWN_ANTIVENOMS = [
    "Botrópico", "Crotálico", "Laquético", "Elapídico",
    "Escorpiônico", "Fonêutrico", "Loxoscélico", "Lonômico",
    "Aracnídico", "Araneídico",
]

# Abbreviated antivenom names used in some states (MA)
ANTIVENOM_ABBREVS = {
    "sab": "Botrópico", "sac": "Crotálico", "sabc": "Botrópico",
    "sabl": "Laquético", "sael": "Elapídico", "saesc": "Escorpiônico",
    "salon": "Lonômico", "saar": "Aracnídico", "safon": "Fonêutrico",
    "salox": "Loxoscélico",
}


def normalize_text(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def clean_cell(val):
    if val is None:
        return ""
    val = str(val).strip()
    val = re.sub(r"\n+", " ", val)
    val = re.sub(r"\s{2,}", " ", val)
    return val


def parse_source_date(filename):
    match = re.search(r"(\d{4})(\d{2})(\d{2})\.pdf", os.path.basename(filename))
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def expand_phones(raw):
    """
    Expand phone numbers with / notation.
    (84) 3315-3379/3414 -> ["(84) 3315-3379", "(84) 3315-3414"]
    Also handles space-separated multiple numbers.
    """
    if not raw:
        return []

    raw = re.sub(r"\s*\n\s*", " ", raw).strip()
    # Rejoin phone fragments split across rows: "(77) 98123- 6657" → "(77) 98123-6657"
    raw = re.sub(r"-\s+(\d)", r"-\1", raw)
    raw = re.sub(r"[-.\s]+$", "", raw)

    # First, split on patterns that indicate separate phone numbers
    # e.g., "(99)3541-2197 (98)3662-1151" — two separate numbers with area codes
    # But don't split "(99) 3541-2197" (one number with space after area code)
    phone_groups = re.split(r"(?<=\d)\s+(?=\()", raw)

    all_phones = []
    for group in phone_groups:
        group = group.strip()
        if not group:
            continue

        area_match = re.match(r"\((\d{2})\)", group)
        area_code = area_match.group(1) if area_match else None

        parts = group.split("/")
        base_number = parts[0].strip()
        base_digits = re.sub(r"\D", "", base_number)

        if len(base_digits) >= 10:
            all_phones.append(base_number)
        elif len(base_digits) >= 8 and not area_code:
            all_phones.append(base_number)

        for suffix in parts[1:]:
            suffix = suffix.strip()
            if not suffix:
                continue
            suffix_digits = re.sub(r"\D", "", suffix)
            if not suffix_digits:
                continue

            if len(suffix_digits) >= 8:
                if area_code:
                    if len(suffix_digits) == 8:
                        formatted = f"({area_code}) {suffix_digits[:4]}-{suffix_digits[4:]}"
                    elif len(suffix_digits) == 9:
                        formatted = f"({area_code}) {suffix_digits[:5]}-{suffix_digits[5:]}"
                    else:
                        formatted = f"({area_code}) {suffix_digits}"
                    all_phones.append(formatted)
                else:
                    all_phones.append(suffix)
            elif 3 <= len(suffix_digits) <= 4:
                if len(base_digits) >= 10 and area_code:
                    local_digits = base_digits[2:]
                    new_local = local_digits[:-len(suffix_digits)] + suffix_digits
                    if len(new_local) == 8:
                        formatted = f"({area_code}) {new_local[:4]}-{new_local[4:]}"
                    elif len(new_local) == 9:
                        formatted = f"({area_code}) {new_local[:5]}-{new_local[5:]}"
                    else:
                        formatted = f"({area_code}) {new_local}"
                    all_phones.append(formatted)

    # Filter out entries with too few digits
    return [p for p in all_phones if len(re.sub(r"\D", "", p)) >= 8]


def parse_antivenoms(raw):
    if not raw:
        return []

    text = re.sub(r"\s*\n\s*", " ", raw).strip()
    text = re.sub(r"\s+e\s+", ", ", text)
    # Remove trailing period
    text = re.sub(r"\.\s*$", "", text)

    parts = re.split(r",\s*", text)
    results = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check abbreviations first (MA uses SAB, SAC, etc.)
        norm_part = normalize_text(part)
        if norm_part in ANTIVENOM_ABBREVS:
            av = ANTIVENOM_ABBREVS[norm_part]
            if av not in results:
                results.append(av)
            continue

        # Strip "soro anti" prefix
        cleaned = re.sub(r"^soro\s+anti", "", part, flags=re.IGNORECASE).strip()
        norm = normalize_text(cleaned)

        # ONLY accept known antivenom names — reject everything else
        # This prevents garbage from BA's fragmented tables leaking through
        matched = False
        for known in KNOWN_ANTIVENOMS:
            known_norm = normalize_text(known)
            if len(norm) >= 4 and norm[:4] == known_norm[:4]:
                if known not in results:
                    results.append(known)
                matched = True
                break

        # Don't add unmatched entries — too much garbage in source data

    return results


def is_header_text(text):
    """Check if text looks like header content."""
    upper = text.upper()
    return any(kw in upper for kw in [
        "MUNICÍPIO", "MUNICIPIO", "MUNICÍPIOS", "UNIDADE DE",
        "SAÚDE", "DISPONÍVEIS", "DISPONIVEIS", "ENDEREÇO", "ENDERECO",
        "TELEFONE", "ANTIVENENO",
    ])


def is_state_name_text(text):
    norm = normalize_text(text)
    for name in STATE_NAMES.values():
        if normalize_text(name) == norm:
            return True
    return False


def densify_row(row):
    """
    Remove None/empty columns from a row, returning only filled values.
    This normalizes different column counts (6, 8, 12, 14, 15, 18)
    into a consistent dense format.
    """
    return [clean_cell(c) for c in row if c is not None and str(c).strip()]


def detect_field_count(table):
    """
    Detect how many logical fields this table has by analyzing header rows.
    Returns the expected number of dense fields per data row.
    """
    for row in table[:4]:
        text = " ".join(str(c) for c in row if c).upper()
        if "MUNICÍPIO" in text or "MUNICIPIO" in text or "MUNICÍPIOS" in text:
            dense = densify_row(row)
            # Count header fields
            return len(dense)
    return 6  # default


def has_atendimento_flag(table):
    """Check if table has the BA-style ATENDIMENTO (SIM/NAO) column."""
    for row in table[:4]:
        for cell in row:
            if cell and normalize_text(str(cell)) == "atendimento":
                return True
    return False


def extract_table_dense(table, state_code):
    """
    Extract hospital data using dense (None-stripped) rows.
    This handles varying column counts across pages within the same PDF.
    """
    records = []
    has_flag = has_atendimento_flag(table)

    for row in table:
        # Get full row text for header/state detection
        full_text = " ".join(str(c) for c in row if c).strip()
        if not full_text:
            continue
        if is_state_name_text(full_text):
            continue
        if is_header_text(full_text):
            continue

        dense = densify_row(row)
        if not dense:
            continue

        # Map dense values to fields
        # Standard order: municipio, unidade, endereco, telefone, cnes, atendimentos
        # BA adds: atendimento_flag between cnes and atendimentos

        # Determine which field each dense value corresponds to
        city = ""
        hospital = ""
        address = ""
        phone = ""
        cnes = ""
        antivenoms = ""

        if len(dense) >= 6:
            city = dense[0]
            hospital = dense[1]
            address = dense[2]
            phone = dense[3]
            cnes = dense[4]
            if has_flag and len(dense) >= 7:
                # BA: skip the SIM/NAO flag at position 5
                antivenoms = " ".join(dense[6:])
            else:
                antivenoms = " ".join(dense[5:])
        elif len(dense) == 5:
            # Might be missing city (continuation) or missing a field
            # Heuristic: if first value looks like a CNES (all digits), shift
            if re.match(r"^\d{5,}$", dense[0]):
                # This is likely: cnes, antivenoms...
                cnes = dense[0]
                antivenoms = " ".join(dense[1:])
            else:
                city = dense[0]
                hospital = dense[1]
                address = dense[2]
                phone = dense[3]
                antivenoms = " ".join(dense[4:])
        elif len(dense) == 4:
            city = dense[0]
            hospital = dense[1]
            address = dense[2]
            antivenoms = " ".join(dense[3:])
        elif len(dense) == 3:
            # Likely continuation: could be address, phone, antivenoms
            # or hospital, address, antivenoms
            hospital = dense[0]
            address = dense[1]
            antivenoms = " ".join(dense[2:])
        elif len(dense) == 2:
            antivenoms = " ".join(dense)
        elif len(dense) == 1:
            antivenoms = dense[0]

        records.append({
            "city": city,
            "hospital_name": hospital,
            "address": address,
            "_phone_raw": phone,
            "cnes": cnes,
            "_antivenom_raw": antivenoms,
        })

    return records


def merge_continuation_rows(records):
    """
    Merge continuation rows into previous record.
    A continuation row has no city AND either no hospital name,
    or no CNES (suggesting it's a partial row from multi-row cell).
    """
    merged = []
    current_city = ""

    for rec in records:
        if rec["city"]:
            current_city = rec["city"]

        is_continuation = False

        if not rec["hospital_name"]:
            is_continuation = True
        elif not rec["city"] and not rec["cnes"] and merged:
            is_continuation = True

        if is_continuation and merged:
            prev = merged[-1]
            if rec["hospital_name"]:
                prev["hospital_name"] = (prev["hospital_name"] + " " + rec["hospital_name"]).strip()
            if rec["address"]:
                prev["address"] = (prev["address"] + " " + rec["address"]).strip()
            if rec["_phone_raw"]:
                prev["_phone_raw"] = (prev["_phone_raw"] + " " + rec["_phone_raw"]).strip()
            if rec["_antivenom_raw"]:
                prev["_antivenom_raw"] = (prev["_antivenom_raw"] + " " + rec["_antivenom_raw"]).strip()
            if rec["cnes"] and not prev["cnes"]:
                prev["cnes"] = rec["cnes"]
            continue

        rec["city"] = current_city if not rec["city"] else rec["city"]
        merged.append(rec)

    return merged


def extract_table_fixed(table, mapping):
    """Extract hospital data using fixed column mapping."""
    records = []

    for row in table:
        full_text = " ".join(str(c) for c in row if c).strip()
        if not full_text:
            continue
        if is_state_name_text(full_text):
            continue
        if is_header_text(full_text):
            continue

        def get(field):
            spec = mapping.get(field)
            if spec is None:
                return ""
            # Support multi-column spans: spec can be int or list of ints
            if isinstance(spec, list):
                parts = []
                for idx in spec:
                    if idx < len(row) and row[idx] is not None:
                        parts.append(str(row[idx]).strip())
                return " ".join(parts).strip()
            idx = spec
            if idx >= len(row):
                return ""
            return clean_cell(row[idx])

        city = get("municipio")
        hospital = get("unidade")
        address = get("endereco")
        phone = get("telefone")
        cnes = get("cnes")
        antivenoms = get("atendimentos")

        records.append({
            "city": city,
            "hospital_name": hospital,
            "address": address,
            "_phone_raw": phone,
            "cnes": cnes,
            "_antivenom_raw": antivenoms,
        })

    return records


# Fixed column mappings for consistent formats
# Values can be int (single column) or list of ints (merge multiple columns)
FIXED_MAPPINGS = {
    18: {"municipio": 0, "unidade": 3, "endereco": 6, "telefone": 9, "cnes": 12, "atendimentos": 15},
    6: {"municipio": 0, "unidade": 1, "endereco": 2, "telefone": 3, "cnes": 4, "atendimentos": 5},
    8: {"municipio": 0, "unidade": 1, "endereco": [2, 3, 4], "telefone": 5, "cnes": 6, "atendimentos": 7},
    13: {"municipio": 0, "unidade": [1, 2, 3], "endereco": [4, 5, 6], "telefone": 7, "cnes": 8, "atendimentos": [10, 11, 12]},
    15: {"municipio": 0, "unidade": [1, 2, 3], "endereco": [4, 5, 6], "telefone": [7, 8, 9], "cnes": 10, "atendimentos": [12, 13, 14]},
}


def extract_pdf(filepath, state_code):
    """Extract all hospital records from a single PDF, page by page."""
    all_records = []

    with pdfplumber.open(filepath) as pdf:
        total_chars = sum(len(page.extract_text() or "") for page in pdf.pages)
        if total_chars == 0:
            return extract_pdf_ocr(filepath, state_code)

        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 1:
                    continue

                ncols = len(table[0])
                if ncols <= 1:
                    continue

                # Use fixed mapping for known consistent formats
                if ncols in FIXED_MAPPINGS:
                    rows = extract_table_fixed(table, FIXED_MAPPINGS[ncols])
                else:
                    # Use dense approach for variable-width formats
                    rows = extract_table_dense(table, state_code)

                all_records.extend(rows)

    return merge_continuation_rows(all_records)


def extract_pdf_ocr(filepath, state_code):
    """Extract from image-based PDF using OCR."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        print(f"  WARNING: {state_code} is image-based but pytesseract/pdf2image not available. Skipping.")
        return []

    print(f"  Using OCR for {state_code}...")

    try:
        images = convert_from_path(filepath, dpi=300)
    except Exception as e:
        print(f"  ERROR: Could not convert {state_code} PDF to images: {e}")
        return []

    all_text = ""
    for page_num, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img, lang="por")
            all_text += text + "\n"
        except Exception as e:
            print(f"  ERROR: OCR failed for {state_code} page {page_num + 1}: {e}")

    if not all_text.strip():
        print(f"  WARNING: OCR produced no text for {state_code}")
        return []

    print(f"  OCR produced {len(all_text)} chars — may need manual review")
    return []


def get_pi_manual_data():
    """
    PI (Piauí) PDF is image-based with garbled text extraction.
    These 15 hospitals were manually extracted from the PDF.
    """
    hospitals = [
        {"city": "Amarante", "hospital_name": "Hospital de Amarante", "address": "Praça Padre Virgilio, s/n - Centro", "_phone_raw": "(86) 3292-1121", "cnes": "2364883", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "Barras", "hospital_name": "Hospital Regional Leônidas Melo", "address": "Rua Santo Antônio, 210 - Centro", "_phone_raw": "(86) 3242-1336", "cnes": "2323915", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Escorpiônico"},
        {"city": "Bom Jesus", "hospital_name": "Hospital Regional de Bom Jesus", "address": "Avenida Dr. Raimundo dos Santos, 546 - Centro", "_phone_raw": "(89) 3562-1192/1404", "cnes": "2364816", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Campo Maior", "hospital_name": "Hospital Regional de Campo Maior", "address": "Avenida do Contorno, s/n - São Luís", "_phone_raw": "(89) 3252-1372", "cnes": "2777754", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Corrente", "hospital_name": "Hospital Regional Dr. João Pacheco Cavalcante", "address": "Rua Antonio Nogueira de Carvalho, s/n - Centro", "_phone_raw": "(89) 3573-1465/2699", "cnes": "", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Esperantina", "hospital_name": "Hospital Regional Deolino Couto", "address": "Avenida 7 de Setembro, 1150 - São Cristóvão", "_phone_raw": "(86) 3383-1353", "cnes": "2364484", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Floriano", "hospital_name": "Hospital Regional Tibério Nunes", "address": "Rua Manoel Neto, s/n - Centro", "_phone_raw": "(89) 3515-3150", "cnes": "2371316", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Oeiras", "hospital_name": "Hospital Regional Deolindo Couto", "address": "Rua Rui Barbosa, s/n - Centro", "_phone_raw": "(89) 3462-1160", "cnes": "2371677", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "Parnaíba", "hospital_name": "Hospital Regional Dirceu Arcoverde", "address": "Avenida São Sebastião, 2159 - Centro", "_phone_raw": "(86) 3321-2181", "cnes": "2561859", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Paulistana", "hospital_name": "Hospital Regional de Paulistana", "address": "BR 407, s/n - Centro", "_phone_raw": "(89) 3484-1189", "cnes": "2371855", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "Picos", "hospital_name": "Hospital Regional Justino Luz", "address": "Rua Sete de Setembro, 1020 - Centro", "_phone_raw": "(89) 3422-1314", "cnes": "4009622", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "Piripiri", "hospital_name": "Hospital Regional Chagas Rodrigues", "address": "Avenida Dr. Pádua Oliveira, 300 - Morro da Saudade", "_phone_raw": "(86) 3276-3362/1325", "cnes": "2777746", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "São João do Piauí", "hospital_name": "Hospital Regional Teresinha Nunes Barros", "address": "Avenida Cândido Coêlho, 1215 - Centro", "_phone_raw": "(89) 3483-1518", "cnes": "2365383", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Escorpiônico"},
        {"city": "São Raimundo Nonato", "hospital_name": "Hospital Regional Senador Cândido Ferraz", "address": "Praça Coronel José Neuton Rubem, 1351 - Aldeia", "_phone_raw": "(89) 3582-3663", "cnes": "2777649", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
        {"city": "Teresina", "hospital_name": "Instituto de Doenças Tropicais Natan Portela - IDTNP", "address": "Rua Gov. Raimundo Artur de Vasconcelos, 151 - Sul", "_phone_raw": "(86) 3221-3413", "cnes": "2323338", "_antivenom_raw": "Botrópico, Crotálico, Elapídico, Fonêutrico, Loxoscélico, Laquético, Escorpiônico"},
    ]
    return hospitals


def process_all_pdfs(pdf_dir):
    all_hospitals = []
    failed = []

    pdf_files = sorted(f for f in os.listdir(pdf_dir) if f.endswith(".pdf"))
    print(f"Found {len(pdf_files)} PDF files\n")

    for filename in pdf_files:
        # Handle V2_PI_20251110.pdf style filenames
        basename = filename.replace(".pdf", "")
        parts = basename.split("_")
        # Find the 2-letter state code (skip prefixes like "V2")
        state_code = None
        for p in parts:
            if len(p) == 2 and p.isalpha() and p.isupper() and p in STATE_NAMES:
                state_code = p
                break
        if not state_code:
            state_code = filename[:2]
        source_date = parse_source_date(filename)
        filepath = os.path.join(pdf_dir, filename)

        print(f"Processing {filename} ({STATE_NAMES.get(state_code, '?')})...")

        # Use manual data for PI (image-based PDF with garbled text)
        # Skip duplicate PI files (V2 version)
        if state_code == "PI" and "PI" in [h["state"] for h in all_hospitals]:
            print(f"  Skipping (PI already loaded)")
            continue
        if state_code == "PI":
            records = get_pi_manual_data()
            print(f"  -> {len(records)} hospitals (manual data)")
            for rec in records:
                phones = expand_phones(rec.pop("_phone_raw", ""))
                antivenoms = parse_antivenoms(rec.pop("_antivenom_raw", ""))
                hospital = {
                    "state": state_code,
                    "state_name": STATE_NAMES.get(state_code, ""),
                    "city": rec["city"],
                    "hospital_name": rec["hospital_name"],
                    "address": rec["address"],
                    "phones": phones,
                    "cnes": rec["cnes"],
                    "antivenoms": antivenoms,
                    "source_date": source_date,
                }
                all_hospitals.append(hospital)
            continue

        try:
            records = extract_pdf(filepath, state_code)
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed.append({"file": filename, "state": state_code, "error": str(e)})
            continue

        count = 0
        for rec in records:
            phones = expand_phones(rec.pop("_phone_raw", ""))
            antivenoms = parse_antivenoms(rec.pop("_antivenom_raw", ""))

            if not rec.get("hospital_name"):
                continue

            hospital = {
                "state": state_code,
                "state_name": STATE_NAMES.get(state_code, ""),
                "city": rec["city"],
                "hospital_name": rec["hospital_name"],
                "address": rec["address"],
                "phones": phones,
                "cnes": rec["cnes"],
                "antivenoms": antivenoms,
                "source_date": source_date,
            }
            all_hospitals.append(hospital)
            count += 1

        print(f"  -> {count} hospitals extracted")

        if count == 0:
            failed.append({"file": filename, "state": state_code, "error": "No hospitals extracted"})

    return all_hospitals, failed


def main():
    pdf_dir = PDF_DIR
    if len(sys.argv) > 1:
        pdf_dir = sys.argv[1]

    pdf_dir = os.path.abspath(pdf_dir)

    if not os.path.isdir(pdf_dir):
        print(f"Error: directory not found: {pdf_dir}")
        sys.exit(1)

    hospitals, failed = process_all_pdfs(pdf_dir)

    output_path = os.path.join(pdf_dir, "hospitals_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hospitals, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(hospitals)} hospitals to {output_path}")

    if failed:
        failed_path = os.path.join(pdf_dir, "hospitals_failed.json")
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(failed)} failures to {failed_path}")

    print("\n=== Summary by State ===")
    from collections import Counter
    state_counts = Counter(h["state"] for h in hospitals)
    for state in sorted(state_counts):
        print(f"  {state} ({STATE_NAMES[state]}): {state_counts[state]} hospitals")
    print(f"\n  TOTAL: {len(hospitals)} hospitals across {len(state_counts)} states")

    missing = set(STATE_NAMES.keys()) - set(state_counts.keys())
    if missing:
        print(f"  MISSING STATES: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
