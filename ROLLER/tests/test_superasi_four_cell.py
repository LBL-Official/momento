"""Asked-six four-cell locks. S ≠ terminal p."""

from __future__ import annotations

from fractions import Fraction

from roller.superasi.four_cell import as_fractions, cells_from_counts


def test_path_only_s_without_terminal():
    from roller.superasi.four_cell import cells_from_trades

    trades = [
        {"ticker": "A", "path_true": True, "loss_exit": False, "win_exit": True},
        {"ticker": "B", "path_true": True, "loss_exit": False, "win_exit": True},
        {"ticker": "C", "path_true": False, "loss_exit": True, "win_exit": False},
    ]
    cell = cells_from_trades(trades)
    assert cell["status"] == "PATH_ONLY"
    assert cell["S"]["numer"] == 2
    assert cell["S"]["denom"] == 3
    assert cell["p"]["status"] == "UNAVAILABLE"
    fr = as_fractions(cell)
    assert "p" not in fr
    assert "s_W" not in fr
    assert fr["S"] == Fraction(2, 3)


def test_asked_six_four_cell():
    cell = cells_from_counts(883, 108, 0, 191)
    assert cell["n"] == 1182
    assert cell["cells"] == {
        "W_and_not_T40": 883,
        "W_and_T40": 108,
        "L_and_not_T40": 0,
        "L_and_T40": 191,
    }
    fr = as_fractions(cell)
    assert fr["S"] == Fraction(883, 1182)
    assert fr["p"] == Fraction(991, 1182)
    assert fr["s_W"] == Fraction(883, 991)
    assert fr["s_L"] == Fraction(0, 1)
    assert fr["p"] != fr["S"]
