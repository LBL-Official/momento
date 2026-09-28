"""MLB1 must not edit frozen FIRST80 modules."""

from pathlib import Path

import roller.research.first80 as first80


def test_first80_module_untouched_by_mlb_adapter():
    path = Path(first80.__file__)
    text = path.read_text(encoding="utf-8")
    assert "KXMLBGAME" not in text
    assert "yes_batting" not in text


def test_frozen_test_files_exist():
    root = Path(__file__).resolve().parent
    assert (root / "test_research_executor_phase4.py").is_file()
    assert (root / "test_population_expansion_phase6.py").is_file()
    assert (root / "test_official_settlement.py").is_file()
