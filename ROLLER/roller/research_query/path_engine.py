"""Post-entry path observations. Entry bar cannot satisfy a path condition.

REACH P is directional from the entry-close side:
  entry_close > P → DROP_TO P
  entry_close < P → RISE_TO P
  entry_close == P → no immediate hit; wait until price leaves P, then cross back.

A non-positive close is not a tradable print. It does not satisfy REACH
and does not become the prior close.

RECOVER P is always RISE_TO P (used after a lower barrier).

Sequential conditions are a state machine. Forbidden: any(A) and any(B).
"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime
from typing import Any, Callable

from roller.research_query.entry_engine import TradableBar
from roller.research_query.models import HORIZON_WIN_E4, PathCondition, PathOp
from roller.research_query.operations import (
    path_bounce,
    path_maximum_move,
    path_minimum_move,
    path_never_reach,
    path_revert,
)
from roller.state.clock import elapsed_game_seconds


SnapFn = Callable[[datetime], dict[str, Any]]


def _period_index(period: Any, sport: str) -> int | None:
    if period in (None, ""):
        return None
    try:
        return int(period)
    except (TypeError, ValueError):
        pass
    key = str(period).upper()
    named = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "H1": 1, "H2": 2, "OT": 5 if sport.upper() != "NCAAB" else 3}
    return named.get(key)


def _elapsed_from_snap(snap: dict[str, Any], sport: str) -> int | None:
    rem = snap.get("period_remaining_s")
    period = _period_index(snap.get("period"), sport)
    if rem is not None and period is not None:
        try:
            rs = int(float(rem))
        except (TypeError, ValueError):
            rs = None
        if rs is not None:
            mins, secs = divmod(max(rs, 0), 60)
            return elapsed_game_seconds(period, f"{mins}:{secs:02d}", sport=sport)
    return elapsed_game_seconds(period, snap.get("clock"), sport=sport)


def find_horizon_bar(
    bars_after_entry: list[TradableBar],
    *,
    kind: str,
    minutes: int,
    entry_ts: datetime,
    entry_elapsed_s: int | None,
    snap_fn: SnapFn | None,
    sport: str,
) -> TradableBar | None:
    """First strictly-later bar at or after T minutes of market or game clock."""
    need = int(minutes) * 60
    if need < 60:
        return None
    for bar in bars_after_entry:
        if kind == "market":
            if (bar.ts - entry_ts).total_seconds() >= need:
                return bar
            continue
        if snap_fn is None or entry_elapsed_s is None:
            return None
        snap = snap_fn(bar.ts)
        el = _elapsed_from_snap(snap, sport)
        if el is None:
            continue
        if el >= entry_elapsed_s + need:
            return bar
    return None


@dataclass(frozen=True)
class PathHit:
    op: PathOp
    price_e4: int
    bar: TradableBar
    step: int


def drop_to(prior: int, current: int, price_e4: int) -> bool:
    return prior > price_e4 and current <= price_e4


def rise_to(prior: int, current: int, price_e4: int) -> bool:
    return prior < price_e4 and current >= price_e4


def reach_from_side(prior: int, current: int, price_e4: int) -> bool:
    """Crossing of P from the side implied by prior close. Not any(>=P)."""
    if prior > price_e4:
        return drop_to(prior, current, price_e4)
    if prior < price_e4:
        return rise_to(prior, current, price_e4)
    return False


def is_tradable_path_close(price_e4: int) -> bool:
    """Kalshi yes bid is a positive integer. 0 is empty/settlement, not REACH."""
    return int(price_e4) > 0


def _matches(op: PathOp, prior: int, current: int, price_e4: int) -> bool:
    if op is PathOp.DROP_TO:
        return drop_to(prior, current, price_e4)
    if op is PathOp.RISE_TO or op is PathOp.RECOVER:
        return rise_to(prior, current, price_e4)
    if op is PathOp.REACH:
        return reach_from_side(prior, current, price_e4)
    return False


def first_later(
    bars_after_entry: list[TradableBar],
    *,
    entry_close: int,
    op: PathOp,
    price_e4: int,
    resolve_bar: TradableBar | None = None,
) -> TradableBar | None:
    """First strictly-later tradable bar that satisfies op. Entry bar excluded."""
    if op is PathOp.BOUNCE:
        return path_bounce(bars_after_entry, price_e4, entry_close=entry_close)
    if op is PathOp.REVERT:
        return path_revert(bars_after_entry, price_e4, entry_close=entry_close)
    if op is PathOp.MAXIMUM_MOVE:
        return path_maximum_move(bars_after_entry, price_e4)
    if op is PathOp.MINIMUM_MOVE:
        return path_minimum_move(bars_after_entry, price_e4)
    if op is PathOp.NEVER_REACH:
        return path_never_reach(
            bars_after_entry,
            price_e4,
            entry_close=entry_close,
            resolve_bar=resolve_bar,
        )
    prior = entry_close
    for bar in bars_after_entry:
        if not is_tradable_path_close(bar.bid):
            continue
        if _matches(op, prior, bar.bid, price_e4):
            return bar
        prior = bar.bid
    return None


def _horizon_satisfies(op: PathOp, bar: TradableBar) -> bool:
    if op is PathOp.HORIZON_WIN:
        return bar.bid >= HORIZON_WIN_E4
    if op is PathOp.HORIZON_LOSS:
        return bar.bid < HORIZON_WIN_E4
    return False


def evaluate_step(
    remaining: list[TradableBar],
    step: PathCondition,
    *,
    close: int,
    entry_ts: datetime | None = None,
    entry_elapsed_s: int | None = None,
    snap_fn: SnapFn | None = None,
    sport: str = "NBA",
    resolve_bar: TradableBar | None = None,
) -> TradableBar | None:
    if step.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS):
        if entry_ts is None or step.horizon_kind is None or step.horizon_minutes is None:
            return None
        found = find_horizon_bar(
            remaining,
            kind=step.horizon_kind,
            minutes=int(step.horizon_minutes),
            entry_ts=entry_ts,
            entry_elapsed_s=entry_elapsed_s,
            snap_fn=snap_fn,
            sport=sport,
        )
        if found is None or not _horizon_satisfies(step.op, found):
            return None
        return found
    return first_later(
        remaining,
        entry_close=close,
        op=step.op,
        price_e4=step.price_e4,
        resolve_bar=resolve_bar,
    )


def _step_observation(
    remaining: list[TradableBar],
    step: PathCondition,
    *,
    close: int,
    entry_ts: datetime | None,
    entry_elapsed_s: int | None,
    snap_fn: SnapFn | None,
    sport: str,
    resolve_bar: TradableBar | None = None,
) -> tuple[TradableBar | None, bool]:
    """(observed_bar, path_step_ok). Horizon records the clock bar even on WIN/LOSS fail."""
    if step.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS):
        if entry_ts is None or step.horizon_kind is None or step.horizon_minutes is None:
            return None, False
        found = find_horizon_bar(
            remaining,
            kind=step.horizon_kind,
            minutes=int(step.horizon_minutes),
            entry_ts=entry_ts,
            entry_elapsed_s=entry_elapsed_s,
            snap_fn=snap_fn,
            sport=sport,
        )
        if found is None:
            return None, False
        return found, _horizon_satisfies(step.op, found)
    found = first_later(
        remaining,
        entry_close=close,
        op=step.op,
        price_e4=step.price_e4,
        resolve_bar=resolve_bar,
    )
    return found, found is not None


def run_path(
    bars_after_entry: list[TradableBar],
    entry_close: int,
    steps: list[PathCondition],
    *,
    sequential: bool | None = None,
    entry_ts: datetime | None = None,
    entry_elapsed_s: int | None = None,
    snap_fn: SnapFn | None = None,
    sport: str = "NBA",
    resolve_bar: TradableBar | None = None,
) -> tuple[list[PathHit], bool, TradableBar | None]:
    """
    sequential=True (or any step.sequential / len>1): state machine in order.
    sequential=False and a single step: that step only.
    Unordered conjunction of multiple non-sequential steps: each must hit
    independently on the post-entry series (NOT a substitute for THEN).

    Third value is the last observed exit bar (horizon clock bar, or last hit).
    Horizon WIN/LOSS can fail and still return that clock bar for P&L.
    """
    if not steps:
        return [], True, None
    ordered = sequential if sequential is not None else (
        len(steps) > 1 or any(s.sequential for s in steps)
    )
    if ordered:
        hits: list[PathHit] = []
        remaining = list(bars_after_entry)
        close = entry_close
        exit_bar: TradableBar | None = None
        for i, step in enumerate(steps):
            found, ok = _step_observation(
                remaining,
                step,
                close=close,
                entry_ts=entry_ts,
                entry_elapsed_s=entry_elapsed_s,
                snap_fn=snap_fn,
                sport=sport,
                resolve_bar=resolve_bar,
            )
            if found is None:
                return hits, False, exit_bar
            exit_bar = found
            if not ok:
                return hits, False, found
            hits.append(PathHit(op=step.op, price_e4=step.price_e4, bar=found, step=i))
            remaining = [b for b in remaining if b.ts > found.ts]
            close = found.bid
        return hits, True, exit_bar

    hits = []
    exit_bar = None
    for i, step in enumerate(steps):
        found, ok = _step_observation(
            bars_after_entry,
            step,
            close=entry_close,
            entry_ts=entry_ts,
            entry_elapsed_s=entry_elapsed_s,
            snap_fn=snap_fn,
            sport=sport,
            resolve_bar=resolve_bar,
        )
        if found is None:
            return hits, False, exit_bar
        exit_bar = found
        if not ok:
            return hits, False, found
        hits.append(PathHit(op=step.op, price_e4=step.price_e4, bar=found, step=i))
    return hits, True, exit_bar
