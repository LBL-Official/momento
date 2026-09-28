"""Roller-dynamic trade / week / 20-week valuation. Desk +20/−40 is comparison only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.risk.formulas import (
    bankroll_loss_return,
    bankroll_win_return,
    break_even_probability,
    compound_if_constant,
    required_win_probability,
    trade_ev,
    weekly_distribution,
    weekly_ev,
    weekly_rate_for_growth,
    weekly_return_from_wins,
)
from roller import desk_settings
from roller.superasi.debase.versions import (
    EV_TOLERANCE,
    SENSITIVITY_P,
    TARGET_WEEKLY_EV,
    TRADES_PER_WEEK,
    RISK_PROFILE_WEEKS,
)
from roller.superasi.models import SuperasiError


def _close(a: float, b: float, tol: float = EV_TOLERANCE) -> bool:
    return abs(float(a) - float(b)) <= max(tol, tol * max(abs(float(a)), abs(float(b)), 1.0))


def payoff_from_roller(
    *,
    average_win: float | None,
    average_loss: float | None,
    entry: float | None,
    allocation: float | None = None,
) -> dict[str, float]:
    if allocation is None:
        allocation = desk_settings.allocation_rate(desk_settings.load_desk_settings())
    if average_win is None or average_loss is None or entry is None:
        raise SuperasiError("PAYOFF_REQUIRED", "average_win, average_loss, and entry are required")
    if average_win <= 0 or average_loss <= 0 or entry <= 0:
        raise SuperasiError("PAYOFF_REQUIRED", "average_win, average_loss, and entry must be positive")
    win_roc = float(average_win) / float(entry)
    loss_roc = -float(average_loss) / float(entry)
    r_w = bankroll_win_return(allocation, win_roc)
    r_l = bankroll_loss_return(allocation, loss_roc)
    p_be = float(average_loss) / (float(average_win) + float(average_loss))
    return {
        "average_win": float(average_win),
        "average_loss": float(average_loss),
        "entry": float(entry),
        "risk_reward": float(average_win) / float(average_loss),
        "p_be": p_be,
        "win_return_on_capital": win_roc,
        "loss_return_on_capital": loss_roc,
        "allocation_rate": float(allocation),
        "R_w": r_w,
        "R_l": r_l,
    }


def observed_ev(
    *,
    wins: int,
    losses: int,
    population: int,
    average_win: float,
    average_loss: float,
    trades: list[dict[str, Any]] | None = None,
    entry: float | None = None,
    win_exit: float | None = None,
    loss_exit: float | None = None,
    win_hold: bool = False,
) -> float:
    if population <= 0:
        raise SuperasiError("PAYOFF_REQUIRED", "population must be positive to recompute EV")
    if trades:
        from roller.superasi.base.observed import trade_ev_e4

        reconstructed = trade_ev_e4(
            trades, entry=entry, win_exit=win_exit, loss_exit=loss_exit, win_hold=win_hold
        )
        if reconstructed is not None:
            return reconstructed
    return (wins * average_win - losses * average_loss) / float(population)


def ev_at_p(*, p: float, average_win: float, average_loss: float) -> float:
    return float(p) * float(average_win) - (1.0 - float(p)) * float(average_loss)


def reconcile_header_ev(
    *,
    header_ev: float | None,
    recomputed: float,
) -> None:
    if header_ev is None:
        raise SuperasiError("EV_RECONCILE_FAILED", "Roller header gross_ev is missing")
    if not _close(float(header_ev), float(recomputed)):
        raise SuperasiError(
            "EV_RECONCILE_FAILED",
            f"recomputed EV {recomputed} does not match header gross_ev {header_ev}",
        )


def theoretical_at_p(
    payoff: dict[str, float],
    p: float,
    *,
    desk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    levels = desk if desk is not None else desk_settings.scaled_levels()
    bankroll = float(levels.get("initial_bankroll") or desk_settings.bankroll_dollars(desk_settings.load_desk_settings()))
    target = float(levels.get("target_bankroll") or desk_settings.target_cents(desk_settings.load_desk_settings()) / 100.0)
    r_w = float(payoff["R_w"])
    r_l = float(payoff["R_l"])
    ev_t = trade_ev(p, r_w, r_l)
    ev_w = weekly_ev(TRADES_PER_WEEK, ev_t)
    table = weekly_distribution(TRADES_PER_WEEK, p, r_w, r_l)
    target_trade = TARGET_WEEKLY_EV / float(TRADES_PER_WEEK)
    return {
        "p": p,
        "trade_ev_bankroll": ev_t,
        "weekly_ev": ev_w,
        "p_be": break_even_probability(r_w, r_l),
        "required_p_for_target_week": required_win_probability(target_trade, r_w, r_l),
        "weekly_table": table,
        "arithmetic_20_week": 20.0 * ev_w,
        "compounded_20_week": (1.0 + ev_w) ** RISK_PROFILE_WEEKS - 1.0,
        "compounded_terminal": compound_if_constant(bankroll, ev_w, RISK_PROFILE_WEEKS),
        "weekly_rate_for_50pct": weekly_rate_for_growth(target / bankroll, RISK_PROFILE_WEEKS),
    }


def desk_identity_checks() -> list[dict[str, Any]]:
    r_w = 0.01
    r_l = -0.02
    ev70 = trade_ev(0.70, r_w, r_l)
    ev_be = trade_ev(2.0 / 3.0, r_w, r_l)
    week7 = weekly_return_from_wins(7, 10, r_w, r_l)
    week10 = weekly_return_from_wins(10, 10, r_w, r_l)
    week0 = weekly_return_from_wins(0, 10, r_w, r_l)
    terminal = compound_if_constant(20_000.0, 0.01, 20)
    return [
        {"id": "desk_break_even", "ok": _close(break_even_probability(r_w, r_l), 2.0 / 3.0), "detail": "p_BE=2/3"},
        {"id": "desk_ev_at_70", "ok": _close(ev70, 0.001), "detail": "70% → +0.10% trade EV"},
        {"id": "desk_ev_at_be", "ok": _close(ev_be, 0.0), "detail": "p=2/3 → EV=0"},
        {"id": "desk_week_7", "ok": _close(week7, 0.01), "detail": "7 wins → +1%"},
        {"id": "desk_week_10", "ok": _close(week10, 0.10), "detail": "10 wins → +10%"},
        {"id": "desk_week_0", "ok": _close(week0, -0.20), "detail": "0 wins → -20%"},
        {"id": "desk_compound_20", "ok": _close(terminal, 20_000.0 * (1.01**20), 1e-6), "detail": "$20k×1.01^20"},
        {"id": "desk_target_30k", "ok": _close(20_000.0 * 1.50, 30_000.0), "detail": "$20k×1.50=$30k"},
        {"id": "desk_floor_14999", "ok": 14_999.0 <= 15_000.0, "detail": "$14,999 is a floor breach"},
    ]


def observed_weeks(
    trades: list[dict[str, str]], payoff: dict[str, float], *, win_hold: bool = False
) -> dict[str, Any]:
    buckets: dict[tuple[int, int], dict[str, int]] = {}
    parsed = 0
    for row in trades:
        raw = str(row.get("entry_timestamp") or "").strip()
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = (ts.isocalendar().year, ts.isocalendar().week)
        bucket = buckets.setdefault(key, {"wins": 0, "losses": 0, "other": 0})
        from roller.superasi.base.observed import trade_outcome

        outcome = trade_outcome(row, win_hold=win_hold)
        if outcome == "WIN":
            bucket["wins"] += 1
        elif outcome == "LOSS":
            bucket["losses"] += 1
        else:
            bucket["other"] += 1
        parsed += 1
    if parsed <= 0:
        return {"status": "DATA_REQUIRED", "weeks": [], "reason": "no_entry_timestamps"}
    rows = []
    r_w = float(payoff["R_w"])
    r_l = float(payoff["R_l"])
    for (year, week), counts in sorted(buckets.items()):
        wins = int(counts["wins"])
        losses = int(counts["losses"])
        decided = wins + losses
        weekly_return = wins * r_w + losses * r_l if decided else None
        rows.append(
            {
                "week_id": f"{year}-W{week:02d}",
                "wins": wins,
                "losses": losses,
                "trade_count": decided + int(counts["other"]),
                "decided": decided,
                "weekly_return": weekly_return,
                "net_pnl": "UNAVAILABLE",
            }
        )
    returns = [float(r["weekly_return"]) for r in rows if r.get("weekly_return") is not None]
    return {
        "status": "OBSERVED" if len(rows) >= 2 else "DATA_REQUIRED",
        "reason": "" if len(rows) >= 2 else "fewer_than_two_weeks",
        "weeks": rows,
        "weekly_returns": returns,
        "observed_weekly_return_mean": (sum(returns) / len(returns)) if returns else None,
        "observed_positive_week_probability": (
            sum(1 for x in returns if x > 0) / len(returns) if returns else None
        ),
        "observed_negative_week_probability": (
            sum(1 for x in returns if x < 0) / len(returns) if returns else None
        ),
    }


def sensitivity_theoretical(payoff: dict[str, float], *, desk: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    out = []
    for p in SENSITIVITY_P:
        block = theoretical_at_p(payoff, p, desk=desk)
        out.append(
            {
                "p": p,
                "trade_ev_bankroll": block["trade_ev_bankroll"],
                "weekly_ev": block["weekly_ev"],
                "expected_20_week_compounded": block["compounded_20_week"],
                "median_terminal_theoretical": block["compounded_terminal"],
            }
        )
    return out
