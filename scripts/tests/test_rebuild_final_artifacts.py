"""Unit checks for final artifact reconciliation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rebuild_final_artifacts as rfa  # noqa: E402


def test_partition_rows_uses_final_status_from_master():
    rows = [
        {"row_id": "A", "final_status": "publish_ready"},
        {"row_id": "B", "final_status": "watchlist"},
        {"row_id": "C", "final_status": "retry_queue"},
        {"row_id": "D", "final_status": "manual_review_pending_external"},
        {"row_id": "E", "final_status": "ignored"},
    ]

    publish, review = rfa.partition_rows(rows)

    assert [row["row_id"] for row in publish] == ["A"]
    assert [row["row_id"] for row in review] == ["B", "C", "D"]


def test_to_sheets_row_cleans_and_adds_review_metadata():
    row = {
        "row_id": "BA_0001",
        "source_state_abbr": "BA",
        "antivenoms_raw": "Botrópico| Escorpiônico |",
        "formatted_address": "null",
        "final_status": "watchlist",
    }

    out = rfa.to_sheets_row(row, {"BA_0001": ("watchlist", "municipality fuzzy")})

    assert out["antivenoms_raw"] == "Botrópico, Escorpiônico"
    assert out["formatted_address"] == ""
    assert out["review_status"] == "watchlist"
    assert out["review_reasons"] == "municipality fuzzy"


def test_validate_artifacts_detects_queue_divergence(tmp_path, monkeypatch):
    master_rows = [
        {"row_id": "A", "final_status": "publish_ready"},
        {"row_id": "B", "final_status": "watchlist"},
    ]
    publish = tmp_path / "publish_ready_v1.csv"
    review = tmp_path / "review_queue_v1.csv"
    sheets_publish = tmp_path / "google_sheets_publish_ready_v1.csv"
    sheets_review = tmp_path / "google_sheets_review_queue_v1.csv"
    missing_json = tmp_path / "missing.json"

    rfa.write_csv(publish, ["row_id", "final_status"], [])
    rfa.write_csv(review, ["row_id", "final_status"], [master_rows[1]])
    rfa.write_csv(sheets_publish, ["row_id"], [])
    rfa.write_csv(sheets_review, ["row_id"], [{"row_id": "B"}])

    monkeypatch.setattr(rfa, "OUT_PUBLISH", publish)
    monkeypatch.setattr(rfa, "OUT_REVIEW", review)
    monkeypatch.setattr(rfa, "OUT_SHEETS_PUBLISH", sheets_publish)
    monkeypatch.setattr(rfa, "OUT_SHEETS_REVIEW", sheets_review)
    monkeypatch.setattr(rfa, "OUT_APP", missing_json)
    monkeypatch.setattr(rfa, "OUT_ROOT", missing_json)

    errors = rfa.validate_artifacts(master_rows)

    assert "build/publish_ready_v1.csv does not match final_status=publish_ready" in errors
