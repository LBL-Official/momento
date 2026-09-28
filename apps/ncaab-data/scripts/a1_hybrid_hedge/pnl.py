"""Hybrid P&L. Fees default to 0 (UNRESOLVED in warehouse).

Π = 100 − E − H − C if hedge modeled, else fallback.
Nominal E = 80. Actual candle close at entry is not on the V4 ledger;
report nominal_entry=80 and actual_entry=UNAVAILABLE unless joined later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    enabled: bool = True
    cents_per_hedge_leg: float = 0.0
    cents_per_fallback_exit: float = 0.0
    cents_per_entry: float = 0.0
    label: str = "GROSS_FEES_UNRESOLVED"


def lock_pnl(entry: float, hedge: float, costs: CostModel, hedged: bool) -> float:
    if not hedged:
        raise ValueError("lock_pnl requires a modeled hedge")
    c = costs.cents_per_entry + costs.cents_per_hedge_leg if costs.enabled else 0.0
    return 100.0 - entry - hedge - c


def fallback_pnl(row: dict, model: str, costs: CostModel) -> float:
    """A = Model A 80→40. D = hold. C = do not book the 40 fill.

    B is identical to A until an A1 stop-candle rescan exists.
    """
    c_entry = costs.cents_per_entry if costs.enabled else 0.0
    c_exit = costs.cents_per_fallback_exit if costs.enabled else 0.0
    stop = float(row["pnl_stop_80_40"])
    hold = float(row["pnl_hold"])
    triggered = bool(row.get("stop_close_triggered"))
    if model == "legacy_80_40":
        return stop - (c_entry + (c_exit if triggered else 0.0))
    if model == "realistic_band_exit":
        return stop - (c_entry + (c_exit if triggered else 0.0))
    if model == "conservative_next_observation":
        # No stop-minute next close on V4. Refuse the fictional −40 fill.
        return hold - c_entry
    if model == "settlement_only":
        return hold - c_entry
    raise ValueError(model)


def hybrid_pnl(
    fallback: float,
    entry: float,
    hedge_px: float | None,
    fill_q: float,
    partial: float,
    costs: CostModel,
) -> float:
    """q is modeled fill probability. partial is hedge completion.

    Residual directional exposure uses the fallback book.
    """
    if hedge_px is None or fill_q <= 0 or partial <= 0:
        return fallback
    locked = lock_pnl(entry, hedge_px, costs, True)
    filled = fill_q * partial
    return filled * locked + (1.0 - filled) * fallback
