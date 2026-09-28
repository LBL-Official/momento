"""$20,000 3/4/5% bands. Do not reserve the 40¢ hedge against entry capital."""

from __future__ import annotations

from typing import Any

from roller.austin.config import DEFAULT, AustinConfig, band_contracts, band_dollars, hedge_capital_cents


def band_payload(pct: int, *, cfg: AustinConfig = DEFAULT) -> dict[str, Any]:
    dollars = band_dollars(pct, bankroll_cents=cfg.starting_bankroll_cents)
    contracts = band_contracts(pct, entry_cents=cfg.entry_cents)
    primary = contracts * cfg.entry_cents
    hedge = hedge_capital_cents(contracts, hedge_cents=cfg.hedge_price_cents)
    return {
        "allocation_pct": pct,
        "bankroll_cents": cfg.starting_bankroll_cents,
        "bankroll_dollars": cfg.starting_bankroll_cents / 100.0,
        "dollar_allocation": dollars,
        "entry_price_cents": cfg.entry_cents,
        "contracts": contracts,
        "primary_capital_cents": primary,
        "potential_hedge_capital_cents": hedge,
        "potential_hedge_label": "POTENTIAL HEDGE CAPITAL",
        "reserved_120": False,
    }


def all_bands(*, cfg: AustinConfig = DEFAULT) -> dict[str, Any]:
    return {str(pct): band_payload(pct, cfg=cfg) for pct in cfg.bands}


def recommend_band(
    match: dict[str, Any],
    calibration: dict[str, Any],
    *,
    cfg: AustinConfig = DEFAULT,
) -> dict[str, Any]:
    default = band_payload(3, cfg=cfg)
    status = str(calibration.get("status") or "INSUFFICIENT_SAMPLE")
    if status != "SEPARATED":
        return {
            "recommended_allocation_band": 3,
            "status": status,
            "reason": calibration.get("reason") or "OOS bands do not separate; default 3%",
            **default,
        }
    ev = match.get("weighted_mean_EV")
    t5 = calibration.get("threshold_5")
    t4 = calibration.get("threshold_4")
    band = 3
    if ev is not None and t5 is not None and float(ev) >= float(t5):
        band = 5
    elif ev is not None and t4 is not None and float(ev) >= float(t4):
        band = 4
    payload = band_payload(band, cfg=cfg)
    return {
        "recommended_allocation_band": band,
        "status": "CALIBRATED",
        "reason": "walk-forward EV thresholds",
        "weighted_mean_EV": ev,
        **payload,
    }


def simulate_sleeve(
    pnls_cents: list[float],
    contracts: int,
    *,
    start_cents: int = DEFAULT.starting_bankroll_cents,
) -> dict[str, Any]:
    bank = float(start_cents)
    peak = bank
    max_dd = 0.0
    path = []
    for pnl in pnls_cents:
        bank += float(pnl) * float(contracts)
        peak = max(peak, bank)
        max_dd = max(max_dd, peak - bank)
        path.append(bank)
    n = len(pnls_cents)
    arr = list(pnls_cents)
    wins = sum(1 for x in arr if x > 0)
    return {
        "ending_bankroll_cents": bank,
        "total_PNL_cents": bank - start_cents,
        "max_drawdown_cents": max_dd,
        "trade_count": n,
        "win_rate": None if n == 0 else wins / n,
        "mean_trade_PNL_cents": None if n == 0 else sum(arr) / n * contracts,
        "median_trade_PNL_cents": None if n == 0 else sorted(arr)[n // 2] * contracts,
        "EV_per_trade_cents": None if n == 0 else sum(arr) / n * contracts,
        "EV_per_contract_cents": None if n == 0 else sum(arr) / n,
        "volatility_trade_cents": None
        if n < 2
        else (sum((x * contracts - (sum(arr) / n) * contracts) ** 2 for x in arr) / n) ** 0.5,
    }
