"""Fill-algorithm EV locks. Changing mix must not change S."""

from __future__ import annotations

from fractions import Fraction

from roller.superasi.exit_mixes import ev_from_s, implied_loss, summarize_mix
from roller.superasi.four_cell import as_fractions, cells_from_counts


def test_asked_six_ledger_and_planning():
    cell = cells_from_counts(883, 108, 0, 191)
    s = as_fractions(cell)["S"]
    assert ev_from_s(s, 20, Fraction(40)) == Fraction(5700, 1182)
    assert implied_loss(s, 20, Fraction(5, 2)) == Fraction(14705, 299)


def test_mix_switch_preserves_s():
    cell = cells_from_counts(883, 108, 0, 191)
    s = as_fractions(cell)["S"]
    trades = [
        {
            "ticker": "L1",
            "loss_exit": True,
            "T40": True,
            "path_true": False,
            "window_derived": {"t40_close": 34, "printed_at_barrier": False, "fast_gap": True},
        }
    ]
    a = summarize_mix(trades, s, "LEDGER_RULE")
    b = summarize_mix(trades, s, "FIRST_BARRIER_CLOSE")
    assert a["S"] == b["S"]
    assert a["EV"] != b["EV"]
