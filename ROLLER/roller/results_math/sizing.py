"""Integer contract sizing. Never round up. Allocation ≠ maximum loss. Not Kelly. Not Risk."""

from __future__ import annotations

from typing import Any

from roller import desk_settings
from roller.results_math.models import MODEL_ASSUMED, UNAVAILABLE

DEFAULT_BANKROLL_CENTS = desk_settings.DEFAULT_BANKROLL_CENTS
DEFAULT_ALLOCATION_BPS = desk_settings.DEFAULT_ALLOCATION_BPS
DEFAULT_ALLOCATION_CENTS = (DEFAULT_BANKROLL_CENTS * DEFAULT_ALLOCATION_BPS) // 10_000


def size_allocation(
    *,
    bankroll_cents: int | None = None,
    allocation_cents: int | None = None,
    allocation_bps: int | None = None,
    entry_cents: int | None,
) -> dict[str, Any]:
    desk = desk_settings.load_desk_settings()
    if bankroll_cents is None:
        bankroll_cents = int(desk["bankroll_cents"])
    if allocation_bps is None:
        allocation_bps = int(desk["allocation_bps"])
    if entry_cents is None or entry_cents <= 0:
        return {"status": UNAVAILABLE, "reason": "Entry reference required for contract count."}
    alloc = allocation_cents if allocation_cents is not None else (bankroll_cents * allocation_bps) // 10_000
    if alloc <= 0:
        return {"status": UNAVAILABLE, "reason": "Allocation capital must be positive."}
    contracts = alloc // int(entry_cents)
    deployed = contracts * int(entry_cents)
    residual = alloc - deployed
    return {
        "status": MODEL_ASSUMED,
        "label": "ALLOCATION CAPITAL · not maximum risk · not a fill · not Risk Decision Engine",
        "bankroll_cents": int(bankroll_cents),
        "allocation_bps": int(allocation_bps),
        "allocation_cents": int(alloc),
        "entry_cents": int(entry_cents),
        "contracts": int(contracts),
        "deployed_cents": int(deployed),
        "residual_cents": int(residual),
        "note": f"sized at entry reference {entry_cents}¢ (band floor or chip) · floor division · not a fill",
    }


def dollars_from_cents(cents: float | int | None) -> float | None:
    if cents is None:
        return None
    return float(cents) / 100.0
