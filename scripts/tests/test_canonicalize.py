"""Pytest wrapper around the canonicalizer's built-in self-test.

The main regression assertions live in `canonicalize_antivenoms._self_test`. This file
wires them into pytest so CI catches regressions, plus adds a handful of
inline checks on the public API shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canonicalize_antivenoms import (  # noqa: E402
    CANONICAL_TYPES,
    canonicalize_list,
    canonicalize_one,
    _self_test,
)


def test_self_test_suite_passes():
    """Run the 32 built-in assertions bundled with the module."""
    _self_test()


def test_canonical_types_count_is_nine():
    assert len(CANONICAL_TYPES) == 9


def test_empty_input_returns_empty_result():
    result = canonicalize_list([])
    assert result.canonical == []
    assert result.leaks == []
    assert result.other_soros == []
    assert result.unknown == []


def test_leak_example_from_ba_pdf():
    raw = "É suprido pela rede de frio quando do atendimento de ocorrência, dada a proximidade"
    canon, category = canonicalize_one(raw)
    assert category == "leak"
    assert canon == []


def test_canonical_deduplicates_across_variants():
    result = canonicalize_list(["Botrópico", "Botrópico.", "BOTRÓPICO", "Botropico"])
    assert result.canonical == ["Botrópico"]


def test_mixed_escorpionico_notes_keep_antivenom_and_note():
    raw_values = [
        "Antiescorpiônico. Os demais, são supridos pela rede de frio quando do atendimento de ocorrência, dada a proximidade",
        "Escorpiônico. (Os demais são supridos pela Rede de Frio quando atendimento de ocorrência).",
        "Escorpiônico. Os demais são supridos pela rede de frio quando do atendimento de ocorrência.",
    ]

    for raw in raw_values:
        result = canonicalize_list([raw])
        assert result.canonical == ["Escorpiônico"]
        assert result.leaks == [raw]


def test_judicial_note_remains_note_only():
    result = canonicalize_list(["Elapídico (judicial)"])
    assert result.canonical == []
    assert result.leaks == ["Elapídico (judicial)"]
