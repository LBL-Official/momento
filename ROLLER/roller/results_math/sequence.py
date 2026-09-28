"""Sequence / equity. Fixed allocation. Do not silently compound."""

from __future__ import annotations

from typing import Any

from roller.results_math.drawdown import max_drawdown
from roller.results_math.means import median
from roller.results_math.models import HYPOTHETICAL, OBSERVED, UNAVAILABLE


def _signed_streaks(values: list[float]) -> dict[str, Any]:
    pos_runs: list[int] = []
    neg_runs: list[int] = []
    cur = 0
    sign = 0
    for p in values:
        s = 1 if p > 0 else -1 if p < 0 else 0
        if s == 0:
            if sign > 0 and cur:
                pos_runs.append(cur)
            elif sign < 0 and cur:
                neg_runs.append(cur)
            cur = 0
            sign = 0
            continue
        if s == sign:
            cur += 1
        else:
            if sign > 0 and cur:
                pos_runs.append(cur)
            elif sign < 0 and cur:
                neg_runs.append(cur)
            sign = s
            cur = 1
    if sign > 0 and cur:
        pos_runs.append(cur)
    elif sign < 0 and cur:
        neg_runs.append(cur)
    return {
        "longest_positive_streak": max(pos_runs) if pos_runs else 0,
        "longest_negative_streak": max(neg_runs) if neg_runs else 0,
        "n_positive_streaks": len(pos_runs),
        "n_negative_streaks": len(neg_runs),
        "median_positive_streak": median(pos_runs) if pos_runs else None,
        "median_negative_streak": median(neg_runs) if neg_runs else None,
    }


def streaks(pnls: list[float] | list[int]) -> dict[str, Any]:
    if not pnls:
        return {"status": UNAVAILABLE, "reason": "No sequence."}
    floats = [float(p) for p in pnls]
    signed = _signed_streaks(floats)
    n_win = sum(1 for p in floats if p > 0)
    n_loss = sum(1 for p in floats if p < 0)
    return {
        "status": OBSERVED,
        "label": "HISTORICAL SEQUENCE DESCRIPTIVE · not a future streak probability",
        "wins": n_win,
        "losses": n_loss,
        "zeros": len(floats) - n_win - n_loss,
        "longest_winning_streak": signed["longest_positive_streak"],
        "longest_losing_streak": signed["longest_negative_streak"],
        **signed,
    }


def classification_streaks(flags: list[bool | None]) -> dict[str, Any]:
    known = [1.0 if f is True else -1.0 if f is False else 0.0 for f in flags]
    if not any(v != 0 for v in known):
        return {"status": UNAVAILABLE, "reason": "No WIN/LOSS classification."}
    signed = _signed_streaks(known)
    return {
        "status": OBSERVED,
        "label": "HISTORICAL WIN/LOSS STREAKS · not a future probability",
        "longest_win_streak": signed["longest_positive_streak"],
        "longest_loss_streak": signed["longest_negative_streak"],
        "n_win_streaks": signed["n_positive_streaks"],
        "n_loss_streaks": signed["n_negative_streaks"],
        "median_win_streak": signed["median_positive_streak"],
        "median_loss_streak": signed["median_negative_streak"],
    }


def recovery_trades(pnls: list[float] | list[int]) -> int | None:
    """Trades from max-DD trough back to prior peak. None if never recovered."""
    if not pnls:
        return None
    peak = 0
    equity = 0
    max_dd = 0
    trough_i = 0
    peak_equity = 0
    for i, pnl in enumerate(pnls):
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            trough_i = i
            peak_equity = peak
    if max_dd == 0:
        return 0
    eq = sum(pnls[: trough_i + 1])
    for j in range(trough_i + 1, len(pnls)):
        eq += pnls[j]
        if eq >= peak_equity:
            return j - trough_i
    return None


def sequence_report(pnls: list[float] | list[int]) -> dict[str, Any]:
    if not pnls:
        return {"status": UNAVAILABLE, "reason": "No observed return sequence."}
    floats = [float(p) for p in pnls]
    cum: list[float] = []
    s = 0.0
    for p in floats:
        s += p
        cum.append(s)
    dd = max_drawdown(floats)
    st = streaks(floats)
    rec = recovery_trades(floats)
    return {
        "status": OBSERVED,
        "label": "OBSERVED PATH SEQUENCE · chronological · not backtested account equity",
        "n": len(pnls),
        "cumulative_end_cents": cum[-1] if cum else 0,
        "cumulative_path_cents": cum,
        "drawdown": dd,
        "streaks": st,
        "recovery_trades": rec,
        "recovery_status": "recovered" if rec is not None else "not_recovered_in_sample",
    }


def capitalized_equity(
    pnls: list[float] | list[int],
    *,
    contracts: int,
    bankroll_cents: int,
    allocation_cents: int,
) -> dict[str, Any]:
    if not pnls or contracts <= 0:
        return {"status": UNAVAILABLE, "reason": "Need returns and contracts."}
    scaled = [float(p) * int(contracts) for p in pnls]
    seq = sequence_report(scaled)
    end = seq.get("cumulative_end_cents")
    dd = (seq.get("drawdown") or {}).get("max_drawdown_cents")
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL SEQUENCE ANALYSIS · FIXED ALLOCATION · not compounded · not account equity",
        "starting_bankroll_cents": bankroll_cents,
        "fixed_allocation_cents": allocation_cents,
        "contracts": contracts,
        "ending_bankroll_cents": bankroll_cents + float(end or 0),
        "label_note": "HYPOTHETICAL FIXED-ALLOCATION HISTORICAL SEQUENCE · NOT EXECUTED ACCOUNT EQUITY · NOT COMPOUNDED · NOT FUTURE FORECAST",
        "cumulative_pnl_cents": end,
        "max_drawdown_cents": dd,
        "max_drawdown_pct_bankroll": (dd / bankroll_cents) if dd is not None and bankroll_cents else None,
        "max_drawdown_pct_allocation": (dd / allocation_cents) if dd is not None and allocation_cents else None,
        "streaks": seq.get("streaks"),
        "recovery_trades": seq.get("recovery_trades"),
        "ordering": "entry_ts ascending",
    }
