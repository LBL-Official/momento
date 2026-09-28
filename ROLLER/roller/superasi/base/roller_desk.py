"""Roller-dynamic Theoretical desk for SuperASI A. Mode A +20/−40 stays the instrument."""

from __future__ import annotations

from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.risk.formulas import required_win_probability, trade_ev, weekly_ev
from roller.superasi.base.composition import run_roller_risk_profile
from roller.superasi.base.versions import DESK_PATHS, RISK_PROFILE_WEEKS
from roller.superasi.debase.rr import plan_prices
from roller.superasi.debase.valuation import payoff_from_roller
from roller.superasi.debase.versions import TARGET_WEEKLY_EV, TRADES_PER_WEEK
from roller.superasi.models import SuperasiError

UNAVAILABLE = "UNAVAILABLE"
DATA_REQUIRED = "DATA_REQUIRED"
ROLLER_NOTE = "This Roller's entry/exit + observed win rate. Not BASE_GRADE."
ROLLER_MC_NOTE = "This Roller's R:R + observed win rate. Not BASE_GRADE."
INSTRUMENT_NOTE = "Frozen +20/−40 / p=0.70. Comparison only. Not the Theoretical desk panel."


def extract_entry(parsed_roller: dict[str, Any]) -> float | None:
    prices = plan_prices(parsed_roller)
    if prices.get("entry") is not None:
        return float(prices["entry"])
    for row in parsed_roller.get("trade_rows") or []:
        if not isinstance(row, dict):
            continue
        value = _row_entry(row)
        if value is not None:
            return value
    return None


def _row_entry(row: dict[str, Any]) -> float | None:
    text = str(row.get("entry_value") or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value != 0 else None


def instrument_from_composition(composition: dict[str, Any] | None) -> dict[str, Any]:
    packed = composition if isinstance(composition, dict) else {}
    det = packed.get("deterministic") if isinstance(packed.get("deterministic"), dict) else {}
    return {
        "mode": packed.get("mode"),
        "seed": packed.get("seed"),
        "break_even_probability": det.get("break_even_probability"),
        "trade_ev": det.get("trade_ev"),
        "weekly_ev": det.get("weekly_ev"),
        "required_win_probability": det.get("required_win_probability"),
        "source": "mode_a_instrument",
        "note": INSTRUMENT_NOTE,
    }


def _blank_desk(*, reason: str, p_used: float | None = None) -> dict[str, Any]:
    return {
        "status": DATA_REQUIRED if reason == DATA_REQUIRED else UNAVAILABLE,
        "reason": reason,
        "break_even_probability": None,
        "trade_ev": None,
        "weekly_ev": None,
        "required_win_probability": None,
        "p_used": p_used,
        "source": "roller_payoff",
        "note": ROLLER_NOTE,
        "trades_per_week": TRADES_PER_WEEK,
        "target_weekly_ev": TARGET_WEEKLY_EV,
        "rows_data_required": 0,
        "entry_n": 0,
        "win_return_on_capital": None,
        "loss_return_on_capital": None,
    }


def compute_roller_desk(
    parsed: dict[str, Any],
    observed: dict[str, Any],
    *,
    cfg: RollerConfig | None = None,
    p_used: float | None = None,
) -> dict[str, Any]:
    levels = desk_settings.scaled_levels(cfg=cfg)
    allocation = float(levels["trade_allocation"])
    average_win = observed.get("average_win")
    average_loss = observed.get("average_loss")
    if p_used is None:
        p_used = observed.get("win_rate")
    entry = extract_entry(parsed)
    if average_win is None or average_loss is None or entry is None:
        return _blank_desk(reason=DATA_REQUIRED, p_used=float(p_used) if p_used is not None else None)
    try:
        payoff = payoff_from_roller(
            average_win=float(average_win),
            average_loss=float(average_loss),
            entry=float(entry),
            allocation=allocation,
        )
    except SuperasiError:
        return _blank_desk(reason=DATA_REQUIRED, p_used=float(p_used) if p_used is not None else None)

    prices = plan_prices(parsed)
    win_exit = prices.get("win_exit")
    loss_exit = prices.get("loss_exit")
    trades = list(parsed.get("trade_rows") or [])
    entries: list[float] = []
    row_evs: list[float] = []
    missing = 0
    for row in trades:
        if not isinstance(row, dict):
            continue
        row_entry = _row_entry(row)
        if row_entry is None:
            missing += 1
            continue
        entries.append(row_entry)
        if p_used is None:
            continue
        use_row = (
            win_exit is not None
            and loss_exit is not None
            and row_entry != float(entry)
        )
        if use_row:
            avg_win = float(win_exit) - row_entry
            avg_loss = row_entry - float(loss_exit)
            try:
                row_payoff = payoff_from_roller(
                    average_win=avg_win,
                    average_loss=avg_loss,
                    entry=row_entry,
                    allocation=allocation,
                )
            except SuperasiError:
                missing += 1
                continue
            row_evs.append(trade_ev(float(p_used), row_payoff["R_w"], row_payoff["R_l"]))
        else:
            row_evs.append(trade_ev(float(p_used), payoff["R_w"], payoff["R_l"]))

    unique = {round(value, 10) for value in entries}
    if p_used is None:
        ev_t = None
    elif len(unique) > 1 and row_evs:
        ev_t = sum(row_evs) / float(len(row_evs))
    else:
        ev_t = trade_ev(float(p_used), payoff["R_w"], payoff["R_l"])
    ev_w = weekly_ev(TRADES_PER_WEEK, ev_t) if ev_t is not None else None
    target_trade = TARGET_WEEKLY_EV / float(TRADES_PER_WEEK)
    return {
        "status": "CONFIRMED",
        "reason": None,
        "break_even_probability": payoff["p_be"],
        "trade_ev": ev_t,
        "weekly_ev": ev_w,
        "required_win_probability": required_win_probability(target_trade, payoff["R_w"], payoff["R_l"]),
        "p_used": float(p_used) if p_used is not None else None,
        "R_w": payoff["R_w"],
        "R_l": payoff["R_l"],
        "entry": payoff["entry"],
        "average_win": payoff["average_win"],
        "average_loss": payoff["average_loss"],
        "source": "roller_payoff",
        "note": ROLLER_NOTE,
        "trades_per_week": TRADES_PER_WEEK,
        "target_weekly_ev": TARGET_WEEKLY_EV,
        "rows_data_required": missing,
        "entry_n": len(unique),
        "win_return_on_capital": payoff["win_return_on_capital"],
        "loss_return_on_capital": payoff["loss_return_on_capital"],
    }


def blank_risk_inspect(*, public: dict[str, Any] | None = None, p_used: float | None = None) -> dict[str, Any]:
    packed = public if isinstance(public, dict) else {}
    return {
        "status": DATA_REQUIRED,
        "weeks": None,
        "paths": None,
        "P_min_bankroll_le_floor": None,
        "P_final_ge_target": None,
        "mean_terminal_bankroll": None,
        "p_used": p_used,
        "note": ROLLER_MC_NOTE,
        "source": "roller_payoff",
        "bankroll_dollars": packed.get("bankroll_dollars"),
        "allocation_pct": packed.get("allocation_pct"),
        "floor_dollars": packed.get("floor_dollars"),
        "target_dollars": packed.get("target_dollars"),
    }


def pack_risk_inspect(
    profile: dict[str, Any] | None,
    *,
    public: dict[str, Any] | None = None,
    p_used: float | None = None,
) -> dict[str, Any]:
    packed = public if isinstance(public, dict) else {}
    raw = profile if isinstance(profile, dict) else {}
    mc = raw.get("monte_carlo") if isinstance(raw.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    term = mc.get("terminal_bankroll") if isinstance(mc.get("terminal_bankroll"), dict) else {}
    if not mc:
        return blank_risk_inspect(public=packed, p_used=p_used)
    return {
        "status": "CONFIRMED",
        "weeks": (raw.get("config") or {}).get("weeks_per_year")
        if isinstance(raw.get("config"), dict)
        else RISK_PROFILE_WEEKS,
        "paths": mc.get("paths"),
        "P_min_bankroll_le_floor": probs.get("P_min_bankroll_le_floor"),
        "P_final_ge_target": probs.get("P_final_ge_target"),
        "mean_terminal_bankroll": term.get("mean"),
        "p_used": p_used,
        "note": ROLLER_MC_NOTE,
        "source": "roller_payoff",
        "bankroll_dollars": packed.get("bankroll_dollars"),
        "allocation_pct": packed.get("allocation_pct"),
        "floor_dollars": packed.get("floor_dollars"),
        "target_dollars": packed.get("target_dollars"),
    }


def inspect_risk_profile_from_desk(
    desk: dict[str, Any],
    *,
    research_result_hash: str = "",
    monte_carlo_paths: int = DESK_PATHS,
    cfg: RollerConfig | None = None,
    public: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p_used = desk.get("p_used")
    win_roc = desk.get("win_return_on_capital")
    loss_roc = desk.get("loss_return_on_capital")
    if desk.get("status") != "CONFIRMED" or p_used is None or win_roc is None or loss_roc is None:
        return blank_risk_inspect(public=public, p_used=float(p_used) if p_used is not None else None)
    raw = run_roller_risk_profile(
        payoff={
            "win_return_on_capital": float(win_roc),
            "loss_return_on_capital": float(loss_roc),
        },
        p=float(p_used),
        research_result_hash=research_result_hash,
        monte_carlo_paths=monte_carlo_paths,
        cfg=cfg,
    )
    return pack_risk_inspect(raw, public=public, p_used=float(p_used))


def risk_inspect_from_stored(metrics: dict[str, Any], *, public: dict[str, Any] | None = None) -> dict[str, Any]:
    packed = public if isinstance(public, dict) else {}
    floor = metrics.get("roller_P_min_bankroll_le_floor")
    target = metrics.get("roller_P_final_ge_target")
    mean = metrics.get("roller_mean_terminal_bankroll")
    if floor is None and target is None and mean is None:
        return blank_risk_inspect(public=packed, p_used=metrics.get("roller_p_used"))
    return {
        "status": "CONFIRMED",
        "weeks": metrics.get("roller_horizon_weeks") or RISK_PROFILE_WEEKS,
        "paths": metrics.get("roller_paths"),
        "P_min_bankroll_le_floor": floor,
        "P_final_ge_target": target,
        "mean_terminal_bankroll": mean,
        "p_used": metrics.get("roller_p_used"),
        "note": ROLLER_MC_NOTE,
        "source": "roller_payoff",
        "bankroll_dollars": packed.get("bankroll_dollars"),
        "allocation_pct": packed.get("allocation_pct"),
        "floor_dollars": packed.get("floor_dollars"),
        "target_dollars": packed.get("target_dollars"),
    }


def attach_desk(
    inspect: dict[str, Any],
    *,
    composition: dict[str, Any] | None,
    parsed: dict[str, Any] | None = None,
    observed: dict[str, Any] | None = None,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    inspect["instrument"] = instrument_from_composition(composition)
    if parsed is not None and observed is not None:
        inspect["desk"] = compute_roller_desk(parsed, observed, cfg=cfg)
    return inspect
