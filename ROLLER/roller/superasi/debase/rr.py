"""Price-path R:R. reward = win − entry, risk = entry − loss. Display as X.XX:1."""

from __future__ import annotations

import json
from typing import Any

from roller.superasi.models import SuperasiError

RR_METHODS_TOL = 1e-9


def format_rr(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}:1"


def ratio(*, entry: float, win_exit: float, loss_exit: float) -> float:
    risk = float(entry) - float(loss_exit)
    if risk <= 0:
        raise SuperasiError("RR_REQUIRED", "entry − loss_exit must be positive")
    return (float(win_exit) - float(entry)) / risk


def _price_from_obj(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and raw == raw and raw != 0:
        return float(raw)
    if not isinstance(raw, dict):
        return None
    for key in ("price_e4", "price", "entry"):
        value = raw.get(key)
        if value in (None, ""):
            continue
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out != 0:
            return out
    return None


def _parse_params(text: object) -> float | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list) and data:
        data = data[0]
    return _price_from_obj(data)


def plan_prices(parsed_roller: dict[str, Any]) -> dict[str, float | None]:
    from roller.superasi.base.observed import SETTLEMENT_NO_E4, SETTLEMENT_YES_E4

    meta = parsed_roller.get("meta") if isinstance(parsed_roller.get("meta"), dict) else {}
    entry = _parse_params(meta.get("entry_parameters"))
    win_exit = _parse_params(meta.get("win_exit_parameters"))
    loss_exit = _parse_params(meta.get("loss_exit_parameters"))
    win_op = str(meta.get("win_exit_operation") or "").strip().upper()
    loss_op = str(meta.get("loss_exit_operation") or "").strip().upper()
    if win_exit is None and win_op == "HOLD":
        win_exit = SETTLEMENT_YES_E4
    if loss_exit is None and loss_op == "HOLD":
        loss_exit = SETTLEMENT_NO_E4
    return {
        "entry": entry,
        "win_exit": win_exit,
        "loss_exit": loss_exit,
    }


def _entry_from_row(row: dict[str, Any]) -> float | None:
    text = str(row.get("entry_value") or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value == 0:
        return None
    return value


def plan_rr(*, entry: float | None, win_exit: float | None, loss_exit: float | None) -> float:
    if entry is None or win_exit is None or loss_exit is None:
        raise SuperasiError("RR_REQUIRED", "compiled entry, win exit, and loss exit are required")
    return ratio(entry=float(entry), win_exit=float(win_exit), loss_exit=float(loss_exit))


def trade_mean_rr(
    trades: list[dict[str, Any]],
    *,
    win_exit: float,
    loss_exit: float,
) -> dict[str, Any]:
    ratios: list[float] = []
    rewards: list[float] = []
    risks: list[float] = []
    excluded = 0
    for row in trades:
        entry = _entry_from_row(row)
        if entry is None:
            excluded += 1
            continue
        risk = float(entry) - float(loss_exit)
        if risk <= 0:
            excluded += 1
            continue
        reward = float(win_exit) - float(entry)
        ratios.append(reward / risk)
        rewards.append(reward)
        risks.append(risk)
    if not ratios:
        raise SuperasiError("RR_REQUIRED", "no valid per-trade R:R rows")
    mean_ratio = sum(ratios) / len(ratios)
    mean_reward = sum(rewards) / len(rewards)
    mean_risk = sum(risks) / len(risks)
    ratio_of_means = mean_reward / mean_risk
    disagree = abs(mean_ratio - ratio_of_means) > RR_METHODS_TOL
    return {
        "rr": mean_ratio,
        "n": len(ratios),
        "excluded": excluded,
        "mean_reward": mean_reward,
        "mean_risk": mean_risk,
        "ratio_of_means": ratio_of_means,
        "methods_disagree": disagree,
    }


def report_rr(
    parsed_roller: dict[str, Any],
    *,
    plan_entry: float | None = None,
    plan_win: float | None = None,
    plan_loss: float | None = None,
) -> dict[str, Any]:
    prices = plan_prices(parsed_roller)
    entry = plan_entry if plan_entry is not None else prices["entry"]
    win_exit = plan_win if plan_win is not None else prices["win_exit"]
    loss_exit = plan_loss if plan_loss is not None else prices["loss_exit"]
    planned = plan_rr(entry=entry, win_exit=win_exit, loss_exit=loss_exit)
    trades = [row for row in (parsed_roller.get("trade_rows") or []) if isinstance(row, dict)]
    trade_block: dict[str, Any] | None = None
    if trades:
        try:
            trade_block = trade_mean_rr(trades, win_exit=float(win_exit), loss_exit=float(loss_exit))
        except SuperasiError:
            trade_block = None
    entries = [_entry_from_row(row) for row in trades]
    present = [item for item in entries if item is not None]
    variable = len({round(item, 8) for item in present}) > 1
    if trade_block is not None and variable:
        reported = float(trade_block["rr"])
        basis = "trade_mean"
    else:
        reported = planned
        basis = "plan"
    ratio_of_means = trade_block.get("ratio_of_means") if trade_block else None
    methods_disagree = bool(trade_block and trade_block.get("methods_disagree"))
    return {
        "risk_reward": reported,
        "risk_reward_plan": planned,
        "risk_reward_trade_mean": trade_block.get("rr") if trade_block else None,
        "risk_reward_ratio_of_means": ratio_of_means,
        "risk_reward_display": format_rr(reported),
        "risk_reward_basis": basis,
        "risk_reward_n": trade_block.get("n") if trade_block else 0,
        "risk_reward_excluded": trade_block.get("excluded") if trade_block else 0,
        "risk_reward_variable": variable,
        "risk_reward_methods_disagree": methods_disagree,
        "entry": float(entry) if entry is not None else None,
        "win_exit": float(win_exit) if win_exit is not None else None,
        "loss_exit": float(loss_exit) if loss_exit is not None else None,
    }
