"""SuperASI must not grow credentials or import frozen FIRST80 internals."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "roller" / "superasi"


def test_no_first80_internal_import():
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "roller.research.first80" not in text
        assert "from roller.research import first80" not in text


def test_no_rng_or_ml():
    banned = ("numpy.random", "sklearn", "random.Random", "bootstrap")
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"
