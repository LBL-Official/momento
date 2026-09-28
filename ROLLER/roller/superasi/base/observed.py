"""OBSERVED facts from Labs trade rows. Does not invent a second EV."""

from __future__ import annotations

from collections import Counter
from typing import Any

from roller.risk.formulas import RiskConfigError, wilson_interval
from roller.superasi.base.versions import WILSON_Z

WIN = "WIN"
LOSS = "LOSS"
HELD = "HELD_TO_SETTLEMENT"
BAD_CLASS = frozenset({"MISSING_SETTLEMENT", "INVALID_SETTLEMENT"})
BAD_SETTLE = frozenset({"MISSING", "INVALID"})

# Hold-YES / hold-NO have no path price. Same e4 domain as the warehouse contract.
SETTLEMENT_YES_E4 = 10000.0
SETTLEMENT_NO_E4 = 0.0


def is_win_hold(parsed: dict[str, Any] | None = None, *, win_exit_operation: object = "") -> bool:
    """Hold-YES is a trade win only when the compiled win exit is HOLD."""
    meta: dict[str, Any] = {}
    if isinstance(parsed, dict):
        raw = parsed.get("meta")
        if isinstance(raw, dict):
            meta = raw
    op = str(meta.get("win_exit_operation") or win_exit_operation or "").strip().upper()
    return op == "HOLD"


def trade_outcome(row: dict[str, Any], *, win_hold: bool = False) -> str | None:
    """ROLLER trade books: path WIN/LOSS, or hold-YES / hold-NO when win exit is HOLD.

    Official YES does not un-do a path LOSS. HELD+YES is not a path-only win.
    """
    klass = str(row.get("classification") or "").strip().upper()
    settle = str(row.get("settlement_status") or "").strip().upper()
    if klass == WIN:
        return WIN
    if klass == LOSS:
        return LOSS
    if win_hold and klass == HELD:
        if settle == "YES":
            return WIN
        if settle == "NO":
            return LOSS
    return None


def row_payoff_e4(
    row: dict[str, Any],
    *,
    entry: float,
    win_exit: float | None,
    loss_exit: float | None,
    win_hold: bool = False,
) -> float | None:
    klass = str(row.get("classification") or "").strip().upper()
    settle = str(row.get("settlement_status") or "").strip().upper()
    if klass == WIN:
        if win_exit is None:
            return None
        return float(win_exit) - float(entry)
    if klass == LOSS:
        if loss_exit is None:
            return None
        return -(float(entry) - float(loss_exit))
    if win_hold and klass == HELD:
        if settle == "YES":
            return SETTLEMENT_YES_E4 - float(entry)
        if settle == "NO":
            return -(float(entry) - SETTLEMENT_NO_E4)
    return None


def trade_ev_e4(
    trades: list[dict[str, Any]],
    *,
    entry: float | None,
    win_exit: float | None,
    loss_exit: float | None,
    win_hold: bool = False,
) -> float | None:
    if not trades or entry is None:
        return None
    total = 0.0
    counted = 0
    for row in trades:
        payoff = row_payoff_e4(
            row, entry=entry, win_exit=win_exit, loss_exit=loss_exit, win_hold=win_hold
        )
        if payoff is None:
            continue
        total += payoff
        counted += 1
    if not counted:
        return None
    return total / float(len(trades))


def _f(value: object) -> float | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _i(value: object) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def summarize_observed(parsed: dict[str, Any]) -> dict[str, Any]:
    from roller.superasi.debase.rr import plan_prices

    trades = list(parsed.get("trade_rows") or [])
    meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else {}
    n = len(trades)
    hist = Counter(str(row.get("classification") or "").strip() or "EMPTY" for row in trades)
    win_hold = is_win_hold(parsed)
    wins = losses = 0
    for row in trades:
        outcome = trade_outcome(row, win_hold=win_hold)
        if outcome == WIN:
            wins += 1
        elif outcome == LOSS:
            losses += 1
    decided = wins + losses
    bad = 0
    for row in trades:
        klass = str(row.get("classification") or "").strip()
        settle = str(row.get("settlement_status") or "").strip()
        if klass in BAD_CLASS or settle in BAD_SETTLE:
            bad += 1
    p_hat = (wins / decided) if decided else None
    lo = hi = width = None
    if decided:
        try:
            p_hat, lo, hi = wilson_interval(wins, decided, z=WILSON_Z)
            width = float(hi) - float(lo)
        except RiskConfigError:
            p_hat = wins / decided
            lo = hi = width = None
    header_n = _i(meta.get("population"))
    header_w = _i(meta.get("wins"))
    header_l = _i(meta.get("losses"))
    header_wr = _f(meta.get("win_rate"))
    gross_ev = _f(meta.get("gross_ev"))
    average_win = _f(meta.get("average_win"))
    average_loss = _f(meta.get("average_loss"))
    risk_reward = _f(meta.get("risk_reward"))
    prices = plan_prices(parsed)
    entry = prices.get("entry")
    win_exit = prices.get("win_exit")
    loss_exit = prices.get("loss_exit")
    if average_win is None and entry is not None and win_exit is not None:
        average_win = float(win_exit) - float(entry)
        if average_win <= 0:
            average_win = None
    if average_loss is None and entry is not None and loss_exit is not None:
        average_loss = float(entry) - float(loss_exit)
        if average_loss <= 0:
            average_loss = None
    if risk_reward is None and average_win and average_loss:
        risk_reward = float(average_win) / float(average_loss)
    if gross_ev is None:
        gross_ev = trade_ev_e4(
            trades, entry=entry, win_exit=win_exit, loss_exit=loss_exit, win_hold=win_hold
        )
    return {
        "layer": "OBSERVED",
        "population": n,
        "header_population": header_n,
        "wins": wins,
        "losses": losses,
        "decided": decided,
        "header_wins": header_w,
        "header_losses": header_l,
        "win_rate": p_hat,
        "header_win_rate": header_wr,
        "loss_rate": (losses / decided) if decided else None,
        "gross_ev": gross_ev,
        "average_win": average_win,
        "average_loss": average_loss,
        "risk_reward": risk_reward,
        "classification_histogram": dict(sorted(hist.items())),
        "decided_rate": (decided / n) if n else 0.0,
        "bad_settle_count": bad,
        "bad_settle_rate": (bad / n) if n else 1.0,
        "wilson_z": WILSON_Z,
        "wilson_lower": lo,
        "wilson_upper": hi,
        "wilson_width": width,
        "result_hash": str(meta.get("result_hash") or ""),
        "plan_hash": str(meta.get("plan_hash") or ""),
        "has_risk_record": bool(parsed.get("risk_rows")),
        "note": "Candle-path classifications are not fills. gross_ev is the Roller header EV.",
    }
