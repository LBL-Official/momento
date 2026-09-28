"""Liquidity classification. Not a stop engine."""

from __future__ import annotations

from roller.superasi.liquidity import classify_path_loss, classify_sell


def test_bid_50_limit_40_is_not_a_stop():
    rec = classify_sell(bid=50, sell_limit=40)
    assert rec["classification"] == "TAKER"
    assert rec["is_stop"] is False
    assert "NOT A STOP" in rec["note"]


def test_fast_gap_is_taker():
    rec = classify_path_loss(
        {"window_derived": {"t40_close": 31, "prior_close": 52, "fast_gap": True}}
    )
    assert rec["classification"] == "TAKER"
    assert rec["fast_gap"] is True
