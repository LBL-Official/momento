"""Family E — market state at first-80 candle (1m TOB, not L2)."""

from __future__ import annotations

from common import e4_to_cents


def market_state_features(obs: dict, overlay: dict | None) -> dict:
    bid = obs.get("entry_bid_close_e4")
    ask = obs.get("entry_ask_close_e4")
    mid = None if bid is None or ask is None else (bid + ask) / 2.0
    spread = None if bid is None or ask is None else ask - bid
    return {
        "mkt_yes_bid_cents": e4_to_cents(bid),
        "mkt_yes_ask_cents": e4_to_cents(ask),
        "mkt_mid_cents_estimated": e4_to_cents(mid),
        "mkt_spread_cents": e4_to_cents(spread),
        "mkt_distance_from_80_cents": None if bid is None else e4_to_cents(bid - 8000),
        "mkt_alignment_quality": None if overlay is None else overlay.get("alignment_quality"),
        "mkt_l2_available": False,
        "mkt_observed_or_derived": "OBSERVED",
    }
