"""STAX must not grow credentials or import frozen FIRST80 internals."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "roller" / "stax"


def test_no_first80_internal_import():
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "roller.research.first80" not in text
        assert "from roller.research import first80" not in text
        assert "roller.superasi" not in text
        assert "from roller.risk" not in text
        assert "from roller.execution" not in text


def test_no_order_or_live_execution():
    banned = (
        "create_order",
        "submit_order",
        "kalshi_live",
        "ENABLE_LIVE_TRADING",
        "place_order",
    )
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"


def test_no_rolling_timeframe_primitive():
    text = (ROOT / "compatibility.py").read_text(encoding="utf-8")
    assert "ROLLING" not in text
    assert "last_n_days" not in text
