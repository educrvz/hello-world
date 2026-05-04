#!/usr/bin/env python3
"""
Check for updated PESA PDFs on the Ministry of Health website.
Compares online dates against local PDF file dates.

Usage:
    python3 scripts/check_updates.py

Source pages:
    Page 1: https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia
    Page 2: https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia?b_start:int=15
"""

import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "Docs Estado"
SOURCE_DATES = ROOT / "data" / "source_dates.json"

PAGES = [
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia",
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia?b_start:int=15",
]

STATE_CODES = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso do Sul": "MS", "Mato Grosso": "MT", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
    "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
    "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO",
}


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _load_source_dates(source_dates_path: Path = SOURCE_DATES) -> dict[str, date]:
    """Read committed source dates from data/source_dates.json."""
    if not source_dates_path.exists():
        return {}
    try:
        import json

        data = json.loads(source_dates_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ERROR reading {source_dates_path}: {e}")
        return {}
    if not isinstance(data, dict):
        print(f"  ERROR: {source_dates_path} must be a JSON object")
        return {}
    out: dict[str, date] = {}
    for code, value in data.items():
        code = str(code).upper()
        if code not in STATE_CODES.values():
            continue
        parsed = _parse_iso_date(str(value))
        if parsed:
            out[code] = parsed
        else:
            print(f"  WARN: ignoring invalid source date for {code}: {value!r}")
    return out


def _scan_pdf_dates(pdf_dir: Path = PDF_DIR) -> dict[str, date]:
    """Read dates from local PDF filenames ({STATE}_{YYYYMMDD}.pdf)."""
    local: dict[str, date] = {}
    if not pdf_dir.exists():
        return local
    for p in pdf_dir.iterdir():
        f = p.name
        if not f.endswith(".pdf"):
            continue
        # Handle V2_PI_20251110.pdf style
        parts = f.replace(".pdf", "").split("_")
        state_code = None
        date_str = None
        for p in parts:
            if len(p) == 2 and p.isalpha() and p.isupper() and p in STATE_CODES.values():
                state_code = p
            if len(p) == 8 and p.isdigit():
                date_str = p
        if state_code and date_str:
            try:
                local[state_code] = datetime.strptime(date_str, "%Y%m%d").date()
            except ValueError:
                pass
    return local


def get_local_dates(
    source_dates_path: Path = SOURCE_DATES,
    pdf_dir: Path = PDF_DIR,
) -> dict[str, date]:
    """Return baseline source dates.

    CI checkouts do not contain `Docs Estado/` because PDFs are ignored by git,
    so the committed `data/source_dates.json` is the primary source. Local PDF
    filenames remain a fallback and fill gaps when a maintainer has just
    downloaded a new PDF before updating `source_dates.json`.
    """
    local = _load_source_dates(source_dates_path)
    pdf_dates = _scan_pdf_dates(pdf_dir)
    for code, pdf_date in pdf_dates.items():
        if code not in local or pdf_date > local[code]:
            local[code] = pdf_date
    return local


def parse_online_dates_from_html(text: str) -> dict[str, date]:
    """Parse gov.br page text for per-state PDF publication dates."""
    online: dict[str, date] = {}

    # The page structure has: StateName ... publicado DD/MM/YYYY
    # We need the "publicado" date that follows each state name.
    for state_name, code in STATE_CODES.items():
        pattern = re.compile(
            re.escape(state_name) + r".{1,200}?publicado\s+(\d{2}/\d{2}/\d{4})",
            re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            try:
                online[code] = datetime.strptime(match.group(1), "%d/%m/%Y").date()
            except ValueError:
                pass
    return online


def scrape_online_dates():
    """Scrape the gov.br pages for current PDF dates."""
    online: dict[str, date] = {}
    for url in PAGES:
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "SoroJa-Update-Checker/1.0"
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"  ERROR fetching {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()
        online.update(parse_online_dates_from_html(text))

    return online


def compare_dates(local: dict[str, date], online: dict[str, date]):
    updates_needed = []
    up_to_date = []
    missing_local = []
    missing_online = []

    for code in sorted(STATE_CODES.values()):
        online_date = online.get(code)
        local_date = local.get(code)
        state_name = [k for k, v in STATE_CODES.items() if v == code][0]

        if not online_date:
            missing_online.append((code, state_name))
            continue

        if not local_date:
            missing_local.append((code, state_name, online_date))
        elif online_date > local_date:
            updates_needed.append((code, state_name, local_date, online_date))
        else:
            up_to_date.append((code, state_name, local_date))

    return updates_needed, up_to_date, missing_local, missing_online


def main():
    print("=" * 60)
    print("  SoroJá — Verificador de Atualizações PESA")
    print("=" * 60)
    print()

    # Get local dates
    local = get_local_dates()
    print(f"Datas locais encontradas: {len(local)}/27")
    if SOURCE_DATES.exists():
        print(f"Base local: {SOURCE_DATES.relative_to(ROOT)} (+ PDFs locais se existirem)")
    else:
        print(f"Base local: PDFs em {PDF_DIR}")
    print()

    # Try to get online dates
    if HAS_WEB:
        print("Verificando datas online no gov.br...")
        online = scrape_online_dates()
        print(f"Estados encontrados online: {len(online)}/27")
    else:
        print("AVISO: 'requests' e 'beautifulsoup4' não instalados.")
        print("       Instale com: pip3 install requests beautifulsoup4")
        print()
        print("Usando datas conhecidas da última verificação (14/04/2026):")
        # Fallback: hardcoded dates from last live check (14/04/2026)
        online = {}
        last_check = {
            "AC": "15/10/2025", "AL": "09/04/2026", "AP": "10/11/2025",
            "AM": "10/11/2025", "BA": "05/01/2026", "CE": "10/11/2025",
            "DF": "05/01/2026", "ES": "05/01/2026", "GO": "15/10/2025",
            "MA": "05/01/2026", "MS": "05/01/2026", "MT": "05/01/2026",
            "MG": "18/12/2025", "PA": "18/12/2025", "PB": "05/01/2026",
            "PR": "05/01/2026", "PE": "05/01/2026", "PI": "10/11/2025",
            "RJ": "05/01/2026", "RN": "05/01/2026", "RS": "14/11/2025",
            "RO": "05/01/2026", "RR": "18/12/2025", "SC": "05/01/2026",
            "SP": "10/02/2026", "SE": "05/01/2026", "TO": "05/01/2026",
        }
        for code, d in last_check.items():
            online[code] = datetime.strptime(d, "%d/%m/%Y").date()

    print()

    # Compare
    updates_needed, up_to_date, missing_local, missing_online = compare_dates(local, online)

    # Report
    if updates_needed:
        print("🔴 ATUALIZAÇÕES DISPONÍVEIS:")
        print("-" * 50)
        for code, name, local_d, online_d in updates_needed:
            print(f"  {code} ({name})")
            print(f"     Local:  {local_d.strftime('%d/%m/%Y')}")
            print(f"     Online: {online_d.strftime('%d/%m/%Y')} ← NOVO!")
            print(f"     Baixar: acesse gov.br e baixe o PDF atualizado")
            print()
    else:
        print("✅ Nenhuma atualização disponível!")
        print()

    if missing_local:
        print("⚠️  DATAS LOCAIS NÃO ENCONTRADAS:")
        for code, name, online_d in missing_local:
            print(f"  {code} ({name}) — online: {online_d.strftime('%d/%m/%Y')}")
        print("  Atualize data/source_dates.json ou baixe o PDF correspondente em Docs Estado/.")
        print()

    if missing_online:
        print("⚠️  ESTADOS NÃO ENCONTRADOS ONLINE:")
        for code, name in missing_online:
            print(f"  {code} ({name})")
        print("  A página do gov.br pode ter mudado de formato; confira o parser.")
        print()

    print(f"✅ {len(up_to_date)} estados atualizados")
    print()
    print("Fonte: https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia")
    print()

    if updates_needed:
        print("PRÓXIMOS PASSOS:")
        print("  1. Baixe os PDFs atualizados do gov.br")
        print(f"  2. Salve como {{UF}}_{{YYYYMMDD}}.pdf em {PDF_DIR}")
        print("  3. Re-extraia o(s) estado(s) afetado(s) para extracted/{UF}.json")
        print("  4. Execute: ./scripts/refresh_dataset.sh")
        print("  5. Valide, revise o diff e abra PR")

    return len(updates_needed) + len(missing_local) + len(missing_online)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
