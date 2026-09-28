"""TK Ultra's own Austin adapter. persist=False. Not Ballhog's."""

from __future__ import annotations

from typing import Any

from roller.dre.adapters import austin as dre_austin

get_trade = dre_austin.get_trade
list_trades = dre_austin.list_trades
get_replay = dre_austin.get_replay
replay_clipped = dre_austin.replay_clipped
last_observed_by_trade = dre_austin.last_observed_by_trade
list_row = dre_austin.list_row

AUSTIN_ADAPTER = "roller.tk_ultra.adapters.austin.query_at persist=False"


def query_at(trade: dict[str, Any], as_of, persist: bool = False) -> dict[str, Any]:
    """Always persist=False. TK Ultra does not write Austin artifacts."""
    if persist:
        raise ValueError("TK Ultra Austin queries must use persist=False")
    return dre_austin.query_at(trade, as_of)


def extract_context(query: dict[str, Any] | None) -> dict[str, Any]:
    """TK Ultra normalization. Independent of Ballhog alpha extraction."""
    if not query:
        return {
            "availability": "UNAVAILABLE",
            "conditional_ev_cents": None,
            "ci_lower_cents": None,
            "ci_upper_cents": None,
            "ci_level": None,
            "support": None,
            "effective_sample_size": None,
            "weighted_t40_rate": None,
            "weighted_survival_rate": None,
            "ev_change": None,
            "dataset_version": None,
            "model_version": None,
            "query_status": None,
            "market_price_cents": None,
        }
    cond = query.get("conditional_ev") if isinstance(query.get("conditional_ev"), dict) else {}
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    match = query.get("match") if isinstance(query.get("match"), dict) else {}
    change = query.get("state_change") if isinstance(query.get("state_change"), dict) else {}
    form = query.get("form") if isinstance(query.get("form"), dict) else {}
    a_t = cond.get("conditional_ev_cents")
    status = str(query.get("status") or "")
    availability = "OBSERVED" if a_t is not None and status in {"OBSERVED", "QUERY_PARTIAL"} else "UNAVAILABLE"
    price = form.get("current_price_cents")
    return {
        "availability": availability,
        "conditional_ev_cents": None if a_t is None else float(a_t),
        "ci_lower_cents": cond.get("ci_lower_cents"),
        "ci_upper_cents": cond.get("ci_upper_cents"),
        "ci_level": cond.get("ci_level"),
        "ci_method": cond.get("method"),
        "support": support.get("support") or match.get("support"),
        "effective_sample_size": support.get("effective_sample_size") or match.get("effective_sample_size"),
        "weighted_t40_rate": match.get("weighted_T40_rate"),
        "weighted_survival_rate": match.get("weighted_survival_rate"),
        "ev_change": change.get("ev_change"),
        "ev_at_entry": change.get("ev_at_entry"),
        "ev_now": change.get("ev_now"),
        "dataset_version": query.get("dataset_version"),
        "model_version": query.get("model_version"),
        "query_status": query.get("status"),
        "market_price_cents": price,
        "price_basis": "AUSTIN_QUERY_PRICE",
        "inference_timestamp": query.get("inference_timestamp"),
        "source_timestamp": query.get("source_timestamp"),
    }
