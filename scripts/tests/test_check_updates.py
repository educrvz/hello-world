from __future__ import annotations

from datetime import date
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_updates  # noqa: E402


def test_source_dates_json_is_primary_without_pdfs(tmp_path: Path):
    source_dates = tmp_path / "source_dates.json"
    source_dates.write_text(
        json.dumps({"AC": "2025-10-15", "AL": "2026-04-09"}),
        encoding="utf-8",
    )

    got = check_updates.get_local_dates(
        source_dates_path=source_dates,
        pdf_dir=tmp_path / "Docs Estado",
    )

    assert got["AC"] == date(2025, 10, 15)
    assert got["AL"] == date(2026, 4, 9)


def test_pdf_scan_fills_gaps_and_can_advance_dates(tmp_path: Path):
    source_dates = tmp_path / "source_dates.json"
    source_dates.write_text(json.dumps({"AC": "2025-10-15"}), encoding="utf-8")
    pdf_dir = tmp_path / "Docs Estado"
    pdf_dir.mkdir()
    (pdf_dir / "AC_20251020.pdf").write_text("", encoding="utf-8")
    (pdf_dir / "V2_PI_20251110.pdf").write_text("", encoding="utf-8")

    got = check_updates.get_local_dates(source_dates_path=source_dates, pdf_dir=pdf_dir)

    assert got["AC"] == date(2025, 10, 20)
    assert got["PI"] == date(2025, 11, 10)


def test_parse_online_dates_from_html_without_network():
    html = """
    <h2>Acre</h2>
    <p>Hospitais de Referência para Atendimento</p>
    <p>publicado 15/10/2025 17h12 Arquivo</p>
    <h2>Alagoas</h2>
    <p>Hospitais de Referência para Atendimento</p>
    <p>publicado 09/04/2026 17h18 Arquivo</p>
    """

    got = check_updates.parse_online_dates_from_html(html)

    assert got["AC"] == date(2025, 10, 15)
    assert got["AL"] == date(2026, 4, 9)


def test_missing_local_dates_are_actionable():
    updates, up_to_date, missing_local, missing_online = check_updates.compare_dates(
        local={},
        online={"AC": date(2025, 10, 15)},
    )

    assert updates == []
    assert up_to_date == []
    assert missing_local == [("AC", "Acre", date(2025, 10, 15))]
    assert ("AL", "Alagoas") in missing_online
