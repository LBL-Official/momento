"""Adverse p holds s_W and s_L."""

from __future__ import annotations

from fractions import Fraction

from roller.superasi.adverse_terminal import stress
from roller.superasi.four_cell import as_fractions, cells_from_counts


def test_path_only_adverse_is_data_required():
    from roller.superasi.four_cell import cells_from_trades

    cell = cells_from_trades(
        [
            {"ticker": "A", "path_true": True, "loss_exit": False},
            {"ticker": "B", "path_true": False, "loss_exit": True},
        ]
    )
    out = stress(cell, "73")
    assert out["status"] == "DATA_REQUIRED"
    assert out["held_s_W"] is False


def test_p73_holds_path_terms():
    cell = cells_from_counts(883, 108, 0, 191)
    fr = as_fractions(cell)
    out = stress(cell, "73")
    assert out["held_s_W"] is True
    assert out["held_s_L"] is True
    assert Fraction(out["s_W"]["numer"], out["s_W"]["denom"]) == fr["s_W"]
    assert Fraction(out["s_L"]["numer"], out["s_L"]["denom"]) == fr["s_L"]
    p = Fraction(73, 100)
    expect_s = p * fr["s_W"] + (1 - p) * fr["s_L"]
    assert Fraction(out["S_stressed"]["numer"], out["S_stressed"]["denom"]) == expect_s
    assert Fraction(out["p"]["numer"], out["p"]["denom"]) != fr["p"]
