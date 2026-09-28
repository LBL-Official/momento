"""Two first-crossing rules. They are not interchangeable.

CONTRACT_WISE_FIRST matches the reference per-ticker scanner: each contract
has its own first up-cross, and that cross must land in the window. One
position per game goes to the earliest eligible contract.

GAME_WIDE_FIRST takes the earliest cross across both contracts. If that
cross is outside the window, the game is rejected.
"""

from __future__ import annotations

from typing import Any


def _sort_key(row: dict[str, Any]) -> tuple:
    return (int(row["signal_ts"]), str(row["contract_id"]))


def select_game(contracts: list[dict[str, Any]], rule: str) -> dict[str, Any]:
    found = [c for c in contracts if c.get("cross_found")]
    if rule == "CONTRACT_WISE_FIRST":
        eligible = [
            c
            for c in found
            if c.get("window_eligible") and c.get("date_eligible") and c.get("tradable")
        ]
        eligible.sort(key=_sort_key)
        chosen = eligible[0] if eligible else None
        reason = None
        if chosen is None:
            if not found:
                reason = "NO_CROSS"
            elif not any(c.get("tradable") for c in found):
                reason = "NOT_TRADABLE"
            elif not any(c.get("window_eligible") for c in found):
                reason = "FIRST_OUTSIDE_WINDOW"
            elif not any(c.get("date_eligible") and c.get("window_eligible") for c in found):
                reason = "DATE_WINDOW"
            else:
                reason = "NO_ELIGIBLE_CONTRACT"
        return {
            "rule": rule,
            "chosen": chosen,
            "rejection_reason": reason,
            "eligible_count": len(eligible),
        }
    if rule != "GAME_WIDE_FIRST":
        raise ValueError(rule)
    if not found:
        return {"rule": rule, "chosen": None, "rejection_reason": "NO_CROSS", "eligible_count": 0}
    found_sorted = sorted(found, key=_sort_key)
    first = found_sorted[0]
    if not first.get("tradable"):
        reason = "NOT_TRADABLE"
    elif not first.get("window_eligible"):
        reason = "GAME_WIDE_OUTSIDE_WINDOW"
    elif not first.get("date_eligible"):
        reason = "DATE_WINDOW"
    else:
        reason = None
    return {
        "rule": rule,
        "chosen": None if reason else first,
        "rejection_reason": reason,
        "eligible_count": 0 if reason else 1,
        "earliest_contract_id": first.get("contract_id"),
    }
