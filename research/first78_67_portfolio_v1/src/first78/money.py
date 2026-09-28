"""Integer-cent accounting for the user fee scenario.

Headline prices are stylized assumed fills. A close at another price is not
relabeled as a 78¢ or 67¢ fill.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any

FEE_COEF = Decimal("0.0175")
CENT = Decimal("0.01")


def fee_raw(contracts: int, price_cents: int, coef: Decimal = FEE_COEF) -> Decimal:
    if contracts < 0:
        raise ValueError("contracts < 0")
    if price_cents <= 0 or price_cents >= 100:
        raise ValueError(f"price_cents out of (0, 100): {price_cents}")
    p = Decimal(int(price_cents)) / Decimal(100)
    return coef * Decimal(int(contracts)) * p * (Decimal(1) - p)


def fee_charged_cents(raw: Decimal) -> int:
    """ceil(100 × F_raw) / 100, once per aggregate order, in cents."""
    return int((raw * 100).to_integral_value(rounding=ROUND_CEILING))


def contracts_for_principal(balance_cents: int, entry_price_cents: int, allocation_bps: int = 600) -> int:
    """C = floor((allocation × B) / p). allocation_bps 600 = 6%."""
    if balance_cents < 0 or entry_price_cents <= 0:
        raise ValueError("bad sizing inputs")
    target = (int(balance_cents) * int(allocation_bps)) // 10_000
    return int(target // int(entry_price_cents))


def reference_unit(balance_cents: int = 2_000_000, entry_cents: int = 78, stop_cents: int = 67, coef: Decimal = FEE_COEF) -> dict[str, Any]:
    """Stylized one-entry economics. Settlement payout is 100¢ or 0¢, unshifted."""
    if entry_cents <= stop_cents:
        raise ValueError("planned stop is not below entry")
    contracts = contracts_for_principal(balance_cents, entry_cents)
    principal = contracts * entry_cents
    entry_raw = fee_raw(contracts, entry_cents, coef)
    stop_raw = fee_raw(contracts, stop_cents, coef)
    entry_fee = fee_charged_cents(entry_raw)
    stop_fee = fee_charged_cents(stop_raw)
    gross_win = contracts * (100 - entry_cents)
    net_win = gross_win - entry_fee
    gross_stop = contracts * (stop_cents - entry_cents)
    net_stop = gross_stop - entry_fee - stop_fee
    denom = net_win + abs(net_stop)
    breakeven = None if denom == 0 else Decimal(abs(net_stop)) / Decimal(denom)
    gross_denom = gross_win + abs(gross_stop)
    gross_be = None if gross_denom == 0 else Decimal(abs(gross_stop)) / Decimal(gross_denom)
    r0 = contracts * (entry_cents - stop_cents) + entry_fee + stop_fee
    return {
        "balance_cents": balance_cents,
        "entry_price_cents": entry_cents,
        "stop_price_cents": stop_cents,
        "settlement_win_cents": 100,
        "settlement_loss_cents": 0,
        "principal_target_cents": (balance_cents * 600) // 10_000,
        "contracts": contracts,
        "principal_cents": principal,
        "entry_fee_raw": format(entry_raw, "f"),
        "stop_fee_raw": format(stop_raw, "f"),
        "entry_fee_cents": entry_fee,
        "stop_fee_cents": stop_fee,
        "initial_debit_cents": principal + entry_fee,
        "gross_win_cents": gross_win,
        "net_win_cents": net_win,
        "gross_stop_cents": gross_stop,
        "net_stop_cents": net_stop,
        "gross_breakeven": None if gross_be is None else format(gross_be, "f"),
        "fee_adjusted_breakeven": None if breakeven is None else format(breakeven, "f"),
        "planned_stop_risk_cents": r0,
        "coef": format(coef, "f"),
    }


def net_r(net_pnl_cents: int, r0_cents: int) -> str | None:
    if r0_cents <= 0:
        return None
    return format(Decimal(int(net_pnl_cents)) / Decimal(int(r0_cents)), "f")
