"""Quote-relation diagnostics. A relation is not a fill."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.models import ChoosinTexasError


def e4_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    iv = int(value)
    if iv % 100 != 0:
        raise ChoosinTexasError("DATA_REQUIRED", f"price {iv} is not an integer cent")
    return iv // 100


def require_causal_arrival(signal_ts: int, arrival_ts: int) -> None:
    if int(arrival_ts) < int(signal_ts):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            "order arrival is before the signal is observable",
        )


def classify_buy_limit(
    *,
    limit_cents: int,
    bid_cents: int | None,
    ask_cents: int | None,
    depth_available: bool,
    sequence_known: bool,
    queue_position: int | None,
) -> dict[str, Any]:
    """Post-only buy. Marketable orders are rejections, not maker fills."""
    if bid_cents is None or ask_cents is None:
        return _unresolved("QUOTE_UNAVAILABLE", "entry quote missing")
    marketable = int(ask_cents) <= int(limit_cents)
    if marketable:
        return {
            "evidence_level": "OBSERVED_MARKET_DATA",
            "quote_relation": "MARKETABLE_AT_CANDLE_CLOSE",
            "post_only_result": "REJECTED_NOT_A_RESTING_MAKER_FILL",
            "role_if_matched_immediately": "TAKER",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "A post-only buy at or above the ask crosses. It is not a resting maker fill.",
        }
    if int(bid_cents) > int(limit_cents):
        relation = "LIMIT_BELOW_DISPLAYED_BID"
    elif int(bid_cents) == int(limit_cents):
        relation = "AT_TOUCH_QUEUE_UNKNOWN"
    else:
        relation = "WOULD_IMPROVE_DISPLAYED_BID"
    return _resting(
        relation,
        depth_available=depth_available,
        sequence_known=sequence_known,
        queue_position=queue_position,
    )


def classify_sell_limit(
    *,
    limit_cents: int,
    bid_cents: int | None,
    ask_cents: int | None,
    depth_available: bool,
    sequence_known: bool,
    queue_position: int | None,
    taker_fallback: str,
) -> dict[str, Any]:
    """Post-only sell placed at or after stop detection.

    A sell crosses when the displayed bid is at or above the limit. A standing
    sell at 65 while the bid is near 80 is marketable. After a through-stop,
    a sell at the stop can sit above a lower bid. That is still not a fill.
    """
    if taker_fallback != "NOT_AUTHORIZED":
        raise ChoosinTexasError("LOCK_MISMATCH", "taker fallback is not authorized")
    if bid_cents is None or ask_cents is None:
        return _unresolved("QUOTE_UNAVAILABLE", "exit quote missing")
    if int(bid_cents) >= int(limit_cents):
        return {
            "evidence_level": "OBSERVED_MARKET_DATA",
            "quote_relation": "MARKETABLE_AT_CANDLE_CLOSE",
            "post_only_result": "REJECTED_NOT_A_RESTING_MAKER_FILL",
            "role_if_matched_immediately": "TAKER",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "taker_fallback": "NOT_AUTHORIZED",
            "reason": "The displayed bid is at or above the sell limit. Post-only does not rest, and no taker exit is authorized.",
        }
    return _resting(
        "SELL_LIMIT_ABOVE_DISPLAYED_BID",
        depth_available=depth_available,
        sequence_known=sequence_known,
        queue_position=queue_position,
        extra={"taker_fallback": "NOT_AUTHORIZED"},
    )


def trades_are_not_our_fill(
    *,
    trades_at_limit_after_arrival: int,
    queue_position: int | None,
) -> dict[str, Any]:
    if queue_position is None:
        return {
            "evidence_level": "OBSERVED_MARKET_DATA",
            "trades_at_limit_after_arrival": int(trades_at_limit_after_arrival),
            "modeled_filled_contracts": None,
            "reason": "A public trade at our price does not identify our queue position.",
        }
    return {
        "evidence_level": "OBSERVED_MARKET_DATA",
        "trades_at_limit_after_arrival": int(trades_at_limit_after_arrival),
        "queue_position": int(queue_position),
        "modeled_filled_contracts": None,
        "reason": "Queue progress is not inferred from prints alone.",
    }


def _resting(
    relation: str,
    *,
    depth_available: bool,
    sequence_known: bool,
    queue_position: int | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not depth_available:
        reasons.append("DEPTH_UNAVAILABLE")
    if not sequence_known:
        reasons.append("SEQUENCE_NUMBERS_UNAVAILABLE")
    if queue_position is None:
        reasons.append("QUEUE_POSITION_UNKNOWN")
    body = {
        "evidence_level": "OBSERVED_MARKET_DATA",
        "quote_relation": relation,
        "post_only_result": "WOULD_REST_RELATIVE_TO_CANDLE_CLOSE",
        "role_if_matched_immediately": None,
        "modeled_filled_contracts": None,
        "fill_label": None,
        "reason": "Resting relative to the minute close is not a fill. " + ",".join(reasons),
    }
    if extra:
        body.update(extra)
    return body


def _unresolved(relation: str, reason: str) -> dict[str, Any]:
    return {
        "evidence_level": "OBSERVED_MARKET_DATA",
        "quote_relation": relation,
        "post_only_result": "NOT_EVALUATED",
        "modeled_filled_contracts": None,
        "fill_label": None,
        "reason": reason,
    }
