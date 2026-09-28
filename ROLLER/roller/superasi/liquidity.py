"""Research liquidity classification. Not an execution engine."""

from __future__ import annotations

from typing import Any


def classify_sell(*, bid: int | None, sell_limit: int | None) -> dict[str, Any]:
    """Maker only if the candle bid is strictly below the sell limit (could rest)."""
    if bid is None or sell_limit is None:
        return {
            "classification": "UNAVAILABLE",
            "is_stop": False,
            "status": "UNAVAILABLE",
            "note": "quote or limit UNAVAILABLE — not inferred.",
        }
    if bid >= sell_limit:
        return {
            "classification": "TAKER",
            "is_stop": False,
            "status": "DERIVED",
            "note": (
                f"bid={bid} >= sell limit={sell_limit}: immediately executable. "
                "NOT A STOP. A 40/45 sell while the bid is 50–60 is a TAKE."
            ),
        }
    return {
        "classification": "MAKER",
        "is_stop": False,
        "status": "DERIVED",
        "note": "Candle bid is below the sell limit so a rest is plausible. NOT A FILL.",
    }


def classify_path_loss(trade: dict[str, Any], *, barrier: int = 40) -> dict[str, Any]:
    derived = trade.get("window_derived") or {}
    t40 = derived.get("t40_close")
    prior = derived.get("prior_close")
    fast = bool(derived.get("fast_gap"))
    through = t40 is not None and int(t40) < barrier
    if fast or through:
        return {
            "classification": "TAKER",
            "is_stop": False,
            "fast_gap": fast,
            "first_close_through_barrier": through,
            "status": "DERIVED",
            "note": "FAST_GAP or first close already through the barrier is TAKER. NOT A FILL.",
        }
    bid = t40 if t40 is not None else prior
    return classify_sell(bid=None if bid is None else int(bid), sell_limit=barrier)
