"""Austin adapter. persist=False. No CSV from the frontend."""

from __future__ import annotations

from typing import Any

from roller.dre.adapters import austin as dre_austin

query_at = dre_austin.query_at
get_trade = dre_austin.get_trade
list_trades = dre_austin.list_trades
get_replay = dre_austin.get_replay
replay_clipped = dre_austin.replay_clipped
last_observed_by_trade = dre_austin.last_observed_by_trade
list_row = dre_austin.list_row
normalize_live_state = dre_austin.normalize_live_state


def extract_alpha(query: dict[str, Any] | None) -> dict[str, Any]:
    if not query:
        return {
            "availability": "UNAVAILABLE",
            "a_t": None,
            "a_l": None,
            "ci_upper": None,
            "ci_level": None,
            "ci_method": None,
            "support": None,
            "effective_sample_size": None,
            "weighted_t40_rate": None,
            "weighted_survival_rate": None,
            "alpha_delta_from_entry": None,
            "dataset_version": None,
            "model_version": None,
        }
    cond = query.get("conditional_ev") if isinstance(query.get("conditional_ev"), dict) else {}
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    match = query.get("match") if isinstance(query.get("match"), dict) else {}
    change = query.get("state_change") if isinstance(query.get("state_change"), dict) else {}
    a_t = cond.get("conditional_ev_cents")
    a_l = cond.get("ci_lower_cents")
    status = str(query.get("status") or "")
    availability = "OBSERVED" if a_t is not None and status in {"OBSERVED", "QUERY_PARTIAL"} else "UNAVAILABLE"
    return {
        "availability": availability,
        "a_t": None if a_t is None else float(a_t),
        "a_l": None if a_l is None else float(a_l),
        "ci_upper": cond.get("ci_upper_cents"),
        "ci_level": cond.get("ci_level"),
        "ci_method": cond.get("method"),
        "support": support.get("support") or match.get("support"),
        "effective_sample_size": support.get("effective_sample_size") or match.get("effective_sample_size"),
        "k": support.get("k") or match.get("k"),
        "weighted_t40_rate": match.get("weighted_T40_rate"),
        "weighted_survival_rate": match.get("weighted_survival_rate"),
        "alpha_delta_from_entry": change.get("ev_change"),
        "ev_at_entry": change.get("ev_at_entry"),
        "ev_now": change.get("ev_now"),
        "dataset_version": query.get("dataset_version"),
        "model_version": query.get("model_version"),
        "query_status": query.get("status"),
        "secondary_8040_after_t": cond.get("secondary_8040_after_t"),
        "secondary_ev_definition": cond.get("secondary_ev_definition"),
    }
