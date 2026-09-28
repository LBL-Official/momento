"""Last-trade Results helpers. Canonical contract lives in results_contract."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import INCOMPLETE, UNAVAILABLE
from roller.results_math.results_contract import (
    HOLD_VALID,
    LAST_TRADE_UNAVAILABLE,
    PRINT_DIAGNOSTIC,
    collect_rate_counts,
    is_last_trade_print,
    print_displacement,
    results_contract,
)

__all__ = [
    "HOLD_VALID",
    "LAST_TRADE_UNAVAILABLE",
    "PRINT_DIAGNOSTIC",
    "is_last_trade_print",
    "last_trade_analysis_overlay",
    "last_trade_rates",
    "last_trade_results_contract",
    "print_displacement",
]


def last_trade_rates(result: dict[str, Any]) -> dict[str, Any]:
    return collect_rate_counts(result)


def last_trade_analysis_overlay(
    rows: list[dict[str, Any]] | None,
    metrics: dict[str, Any] | None,
    identity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extra Results-envelope fields for last-trade. Does not invent executable P&L."""
    reason = f"{LAST_TRADE_UNAVAILABLE}. No P&L / EV / Sharpe on this basis."
    yes = (identity or {}).get("terminal_yes")
    no = (identity or {}).get("terminal_no")
    missing = (identity or {}).get("terminal_missing")
    if yes is None and metrics:
        yes = metrics.get("terminal_yes")
        missing = metrics.get("terminal_missing")
        avail = metrics.get("terminal_available")
        if no is None and yes is not None and avail is not None:
            no = int(avail) - int(yes)
    return {
        "observed_ev": {"status": UNAVAILABLE, "reason": reason},
        "observed_path_ev": {"status": UNAVAILABLE, "reason": reason},
        "economic_hurdle": {
            "status": UNAVAILABLE,
            "reason": reason,
            "break_even_total_cost_cents": None,
        },
        "settlement_payoff": {
            "status": INCOMPLETE,
            "reason": "TERMINAL DATA INCOMPLETE · missing is not NO · PATH WIN ≠ SETTLEMENT YES",
            "terminal_yes": yes,
            "terminal_no": no,
            "terminal_missing": missing,
        },
        "print_displacement": print_displacement(rows),
        "capitalization": {
            "status": UNAVAILABLE,
            "reason": reason,
        },
    }


def last_trade_results_contract(result: dict[str, Any]) -> dict[str, Any]:
    """Authoritative last-trade Results view. Reconstructing candle EV is forbidden."""
    contract = results_contract(result)
    rates = contract["rates"]["counts"]
    eco = contract["economics"]
    observed = (result.get("analysis") or {}).get("observed_returns") or (result.get("analysis") or {}).get(
        "observed_path"
    ) or {}
    observed_ev = (result.get("analysis") or {}).get("observed_ev") or (result.get("analysis") or {}).get(
        "observed_path_ev"
    ) or observed
    return {
        "last_trade": True,
        "yes_bid_forbidden": True,
        "candle_substitution_forbidden": True,
        "tradable_bar_bid_is_not_yes_bid": True,
        "rates": rates,
        "observed_path_ev": {
            "status": UNAVAILABLE,
            "reason": LAST_TRADE_UNAVAILABLE,
            "server_status": observed_ev.get("status") or observed.get("status"),
        },
        "capitalized_path": {"status": UNAVAILABLE, "reason": LAST_TRADE_UNAVAILABLE},
        "sharpe": {"status": UNAVAILABLE, "reason": LAST_TRADE_UNAVAILABLE},
        "break_even_cost": {"status": UNAVAILABLE, "reason": LAST_TRADE_UNAVAILABLE},
        "trade_breakeven": eco.get("trade_breakeven")
        or {"status": UNAVAILABLE, "reason": "Need wins, N, and an entry chip."},
        "book_price_ev": eco.get("book_price_ev")
        or {"status": UNAVAILABLE, "reason": "Tagged WIN and LOSS path prices required."},
        "settlement_ev": eco["settlement_ev"],
        "print_displacement": contract.get("print_displacement"),
        "invariants": contract["invariants"],
        "results_contract": contract,
    }
