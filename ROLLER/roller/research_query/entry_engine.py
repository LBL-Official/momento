"""Ordinal tradable-close crossings. Copy-adapted FIRST80 quality(), not first80.py.

Touch = prior tradable yes_bid_close < P and current tradable yes_bid_close >= P.
Untradable bars do not create crossings and do not reset seen_below.
Period/clock are filters applied AFTER the game-level ordinal is identified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from roller.research.quality import quality
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    EntryCondition,
    EntryOp,
    PeriodWindow,
    TouchOrdinal,
)
from roller.research_query.operations import (
    RecoveryInvalid,
    first_above,
    first_below,
    first_bounce,
    first_break,
    first_cross,
    first_maximum_touch,
    first_minimum_touch,
    first_recovery,
    first_reversion,
)
from roller.state.clock import clock_remaining_seconds, entry_slice
from roller.timeutil import parse_utc

SnapFn = Callable[[datetime], dict[str, Any]]


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class TradableBar:
    """One observation minute on a single basis.

    On BASIS_TRADABLE, `bid`/`ask` are Kalshi top-of-book and quality() has
    already passed. On BASIS_LAST_TRADE, `bid` holds the last-trade print and
    `ask` is None because no quote exists at all — never read `ask` without
    checking `basis` first.
    """

    ts: datetime
    bid: int
    ask: int | None
    volume: int | None
    ticker: str
    game_id: str
    raw: dict[str, Any]
    basis: str = BASIS_TRADABLE

    @property
    def tradable(self) -> bool:
        return self.basis == BASIS_TRADABLE


@dataclass(frozen=True)
class TouchEvent:
    ordinal: TouchOrdinal
    touch_index: int
    price_e4: int
    bar: TradableBar
    snap: dict[str, Any]
    alignment: str
    operation: EntryOp | None = None
    direction: str | None = None


def tradable_sequence(candles: list[dict[str, Any]]) -> tuple[list[TradableBar], int]:
    """Quality-filter in timestamp order. Returns (bars, skipped_untradable)."""
    staged: list[tuple[datetime, dict[str, Any]]] = []
    for c in candles:
        valid = c.get("is_valid")
        if valid in (False, 0, "0", "false", "False"):
            continue
        ts = parse_utc(c.get("available_at") or c.get("candle_timestamp") or c.get("event_timestamp"))
        if ts is None:
            continue
        staged.append((ts, c))
    staged.sort(key=lambda item: (item[0], str(item[1].get("ticker") or "")))
    out: list[TradableBar] = []
    skipped = 0
    had_q = False
    for ts, c in staged:
        bid = _int(c.get("yes_bid_close"))
        ask = _int(c.get("yes_ask_close"))
        vol = _int(c.get("volume"))
        if not quality(bid, ask, vol, had_q) or bid is None or ask is None:
            skipped += 1
            continue
        had_q = True
        out.append(
            TradableBar(
                ts=ts,
                bid=bid,
                ask=ask,
                volume=vol,
                ticker=str(c.get("ticker") or ""),
                game_id=str(c.get("internal_game_id") or ""),
                raw=c,
                basis=BASIS_TRADABLE,
            )
        )
    return out, skipped


def last_trade_sequence(candles: list[dict[str, Any]]) -> tuple[list[TradableBar], int]:
    """Last-trade prints in timestamp order. Returns (bars, skipped_no_price).

    There is no spread to test, so quality() does not apply. A minute with no
    print is simply absent: it is never forward-filled, because an absent trade
    is not evidence that the price held.
    """
    staged: list[tuple[datetime, dict[str, Any]]] = []
    for c in candles:
        valid = c.get("is_valid")
        if valid in (False, 0, "0", "false", "False"):
            continue
        ts = parse_utc(c.get("available_at") or c.get("candle_timestamp") or c.get("event_timestamp"))
        if ts is None:
            continue
        staged.append((ts, c))
    staged.sort(key=lambda item: (item[0], str(item[1].get("ticker") or "")))
    out: list[TradableBar] = []
    skipped = 0
    for ts, c in staged:
        last = _int(c.get("last_close_e4"))
        if last is None:
            skipped += 1
            continue
        out.append(
            TradableBar(
                ts=ts,
                bid=last,
                ask=None,
                volume=_int(c.get("volume")),
                ticker=str(c.get("ticker") or ""),
                game_id=str(c.get("internal_game_id") or ""),
                raw=c,
                basis=BASIS_LAST_TRADE,
            )
        )
    return out, skipped


def observation_sequence(
    candles: list[dict[str, Any]],
    *,
    basis: str = BASIS_TRADABLE,
) -> tuple[list[TradableBar], int]:
    if basis == BASIS_LAST_TRADE:
        return last_trade_sequence(candles)
    return tradable_sequence(candles)


def crossings(bars: list[TradableBar], price_e4: int) -> list[TradableBar]:
    """All upward close-crossings of price_e4 on the tradable sequence."""
    seen_below = False
    hits: list[TradableBar] = []
    for bar in bars:
        if bar.bid < price_e4:
            seen_below = True
            continue
        if bar.bid >= price_e4 and seen_below:
            hits.append(bar)
            seen_below = False
    return hits


def crossings_band(bars: list[TradableBar], lo_e4: int, hi_e4: int) -> list[TradableBar]:
    """Enter [lo, hi] from outside. Stay inside = one touch. Already-inside at open is not a touch."""
    lo, hi = (lo_e4, hi_e4) if lo_e4 <= hi_e4 else (hi_e4, lo_e4)
    seen_outside = False
    hits: list[TradableBar] = []
    for bar in bars:
        inside = lo <= bar.bid <= hi
        if inside and seen_outside:
            hits.append(bar)
            seen_outside = False
        elif not inside:
            seen_outside = True
    return hits


def order_pbp_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Stable PIT order: event clock, then event/point number. Missing clocks last."""

    if not events:
        return []
    from roller.state.clock_snap import pbp_event_ts

    def key(ev: dict[str, Any]) -> tuple[bool, datetime, int]:
        clock = pbp_event_ts(ev)
        try:
            n = int(ev.get("event_number") or ev.get("point_number") or 0)
        except (TypeError, ValueError):
            n = 0
        return (clock is None, clock or datetime.min.replace(tzinfo=timezone.utc), n)

    return sorted(events, key=key)


def default_snap(
    ts: datetime,
    events: list[dict[str, Any]] | None,
    sport: str,
    team_side: str | None = None,
) -> dict[str, Any]:
    from roller.research_query.sport_family import is_baseball, is_tennis
    from roller.state.clock_snap import snap_events

    if not events:
        return {"status": "UNALIGNED", "slice": "UNALIGNED"}
    ordered = order_pbp_events(events)
    if is_baseball(sport):
        from roller.mlb.snap import snap_mlb

        return snap_mlb(ordered, ts, team_side=team_side)
    if is_tennis(sport):
        from roller.tennis.snap import snap_tennis

        return snap_tennis(ordered, ts, team_side=team_side)
    # Basketball I(t): available_at < snap. Equality is invisible.
    # MLB/tennis keep their own event_timestamp <= snap contracts.
    from roller.base_terminal_efficiency.pit import filter_visible

    return snap_events(filter_visible(ordered, ts), ts, sport=sport)


def _alignment(snap: dict[str, Any]) -> str:
    status = str(snap.get("status") or "")
    sl = str(snap.get("slice") or "")
    if sl == "UNALIGNED" or status == "UNALIGNED":
        return "unaligned"
    if status == "MODELED":
        return "modeled"
    if status in ("AMBIGUOUS", "AMBIGUOUS_SNAP"):
        return "ambiguous"
    if status in ("REAL", "ALIGNED", "") and sl and sl != "UNALIGNED":
        return "aligned"
    if sl and sl != "UNALIGNED":
        return "aligned"
    return "unaligned"


def apply_period_clock(
    event: TouchEvent,
    condition: EntryCondition,
    *,
    sport: str,
) -> bool:
    """True if period/clock filters pass. Missing snap fails a requested filter.

    Multiple period_windows are OR: the game-level touch must fall in any
    selected window. Two entry conditions remain AND.
    """
    windows = condition.period_filters()
    if not windows:
        return True
    if event.alignment == "unaligned":
        return False
    return any(_window_matches(event, window, sport=sport) for window in windows)


def _window_matches(event: TouchEvent, window: PeriodWindow, *, sport: str = "NBA") -> bool:
    from roller.research_query.sport_family import is_baseball

    if window.period and not _period_name_ok(event, window.period, sport=sport):
        return False
    if window.clock:
        from roller.research_query.sport_family import is_tennis

        if is_baseball(sport) or is_tennis(sport):
            return False
        rem = event.snap.get("period_remaining_s")
        if rem is None:
            rem = clock_remaining_seconds(event.snap.get("clock"))
        if not window.clock.contains(None if rem is None else float(rem)):
            return False
    return True


def _period_name_ok(event: TouchEvent, want: str, sport: str = "NBA") -> bool:
    from roller.mlb.state import slice_matches
    from roller.research_query.sport_family import is_baseball

    if is_baseball(sport):
        return slice_matches(str(event.snap.get("slice") or ""), want)
    from roller.research_query.sport_family import is_tennis

    if is_tennis(sport):
        from roller.tennis.windows import window_matches

        return window_matches(event.snap or {}, want)
    sl = str(event.snap.get("slice") or "")
    if want == "P5":
        return sl.startswith("H") or sl == "OT"
    if want == "H1":
        return sl in ("H1_1", "H1_2")
    if want == "H2":
        return sl in ("H2_1", "H2_2")
    return sl == want


def _max_entry_exceeded(condition: EntryCondition, bar: TradableBar, diag: dict[str, Any]) -> bool:
    """Reject an already-identified crossing whose observed close is above the ceiling.

    First Touch is still prior < P and current >= P. The recorded entry is bar.bid,
    never rewritten to P. This is not crossings_band / price_to_e4.
    """
    ceiling = condition.max_entry_e4
    if ceiling is None:
        return False
    if int(bar.bid) > int(ceiling):
        diag["reject_reason"] = "max_entry_exceeded"
        return True
    return False


def _period_reject_reason(event: TouchEvent, condition: EntryCondition, *, sport: str = "NBA") -> str:
    windows = condition.period_filters()
    if event.alignment == "unaligned":
        return "period_unaligned" if any(w.period for w in windows) else "clock_unaligned"
    if any(_period_name_ok(event, w.period, sport=sport) for w in windows if w.period):
        return "clock_filter"
    if any(w.period for w in windows):
        return "period_filter"
    return "clock_filter"


def nth_touch(
    candles: list[dict[str, Any]],
    condition: EntryCondition,
    *,
    sport: str = "NBA",
    snap_fn: SnapFn | None = None,
    pbp_events: list[dict[str, Any]] | None = None,
    precomputed: tuple[list[TradableBar], int] | None = None,
    basis: str | None = None,
) -> tuple[TouchEvent | None, dict[str, int]]:
    """Game-level ordinal crossing, then period/clock filter (Interpretation A)."""
    resolved_basis = basis or condition.basis()
    if precomputed is not None:
        bars, skipped = precomputed
    elif not candles:
        return None, {
            "skipped_untradable": 0,
            "crossings_found": 0,
            "aligned": 0,
            "unaligned": 0,
            "ambiguous": 0,
            "modeled": 0,
            "reject_reason": "empty_ticker",
        }
    else:
        bars, skipped = observation_sequence(candles, basis=resolved_basis)
    if condition.price_to_e4 is not None:
        hits = crossings_band(bars, condition.price_e4, condition.price_to_e4)
    else:
        hits = crossings(bars, condition.price_e4)
    idx = condition.touch_index()
    diag = {
        "skipped_untradable": skipped,
        "crossings_found": len(hits),
        "aligned": 0,
        "unaligned": 0,
        "ambiguous": 0,
        "modeled": 0,
        "reject_reason": None,
    }
    if not bars:
        diag["reject_reason"] = "untradable_only"
        return None, diag
    if idx > len(hits):
        diag["reject_reason"] = "no_nth_touch"
        return None, diag
    bar = hits[idx - 1]
    if _max_entry_exceeded(condition, bar, diag):
        return None, diag
    if snap_fn is not None:
        snap = snap_fn(bar.ts)
    else:
        snap = default_snap(bar.ts, pbp_events, sport, team_side=(bar.raw or {}).get("team_side"))
    if "slice" not in snap or not snap.get("slice"):
        period = snap.get("period")
        rem = snap.get("period_remaining_s")
        if rem is None:
            rem = clock_remaining_seconds(snap.get("clock"))
        snap = {**snap, "slice": entry_slice(sport, period, rem)}
    align = _alignment(snap)
    diag[align] = diag.get(align, 0) + 1
    event = TouchEvent(
        ordinal=condition.ordinal,
        touch_index=idx,
        price_e4=condition.price_e4,
        bar=bar,
        snap=snap,
        alignment=align,
        operation=condition.resolved_operation(),
        direction=condition.direction,
    )
    if not apply_period_clock(event, condition, sport=sport):
        diag["reject_reason"] = _period_reject_reason(event, condition, sport=sport)
        return None, diag
    return event, diag


def _snap_event(
    condition: EntryCondition,
    bar: TradableBar,
    *,
    sport: str,
    snap_fn: SnapFn | None,
    pbp_events: list[dict[str, Any]] | None,
    idx: int,
    diag: dict[str, int],
) -> tuple[TouchEvent | None, dict[str, int]]:
    if snap_fn is not None:
        snap = snap_fn(bar.ts)
    else:
        snap = default_snap(bar.ts, pbp_events, sport, team_side=(bar.raw or {}).get("team_side"))
    if "slice" not in snap or not snap.get("slice"):
        period = snap.get("period")
        rem = snap.get("period_remaining_s")
        if rem is None:
            rem = clock_remaining_seconds(snap.get("clock"))
        snap = {**snap, "slice": entry_slice(sport, period, rem)}
    align = _alignment(snap)
    diag[align] = diag.get(align, 0) + 1
    event = TouchEvent(
        ordinal=condition.ordinal,
        touch_index=idx,
        price_e4=condition.price_e4,
        bar=bar,
        snap=snap,
        alignment=align,
        operation=condition.resolved_operation(),
        direction=condition.direction,
    )
    if not apply_period_clock(event, condition, sport=sport):
        diag["reject_reason"] = _period_reject_reason(event, condition, sport=sport)
        return None, diag
    return event, diag


def observe_entry(
    candles: list[dict[str, Any]],
    condition: EntryCondition,
    *,
    sport: str = "NBA",
    snap_fn: SnapFn | None = None,
    pbp_events: list[dict[str, Any]] | None = None,
    precomputed: tuple[list[TradableBar], int] | None = None,
    prior_event: TouchEvent | None = None,
    basis: str | None = None,
) -> tuple[TouchEvent | None, dict[str, int]]:
    """Dispatch Phase 1 detectors. Touch stays on nth_touch. Full-scan reference."""
    resolved_basis = basis or condition.basis()
    if condition.is_touch_op():
        return nth_touch(
            candles,
            condition,
            sport=sport,
            snap_fn=snap_fn,
            pbp_events=pbp_events,
            precomputed=precomputed,
            basis=resolved_basis,
        )
    if precomputed is not None:
        bars, skipped = precomputed
    elif not candles:
        return None, {
            "skipped_untradable": 0,
            "crossings_found": 0,
            "aligned": 0,
            "unaligned": 0,
            "ambiguous": 0,
            "modeled": 0,
            "reject_reason": "empty_ticker",
        }
    else:
        bars, skipped = observation_sequence(candles, basis=resolved_basis)
    diag = {
        "skipped_untradable": skipped,
        "crossings_found": 0,
        "aligned": 0,
        "unaligned": 0,
        "ambiguous": 0,
        "modeled": 0,
        "reject_reason": None,
    }
    if not bars:
        diag["reject_reason"] = "untradable_only"
        return None, diag
    op = condition.resolved_operation()
    price = condition.price_e4
    direction = condition.direction
    try:
        if op is EntryOp.CROSS:
            bar = first_cross(bars, price, direction)
        elif op is EntryOp.BREAK:
            bar = first_break(bars, price, direction)
        elif op is EntryOp.REVERSION:
            bar = first_reversion(bars, price, direction)
        elif op is EntryOp.BOUNCE:
            bar = first_bounce(bars, price, direction)
        elif op is EntryOp.RECOVERY:
            if prior_event is not None:
                later = [b for b in bars if b.ts > prior_event.bar.ts]
                bar = first_recovery(
                    later,
                    price,
                    anchor_close=prior_event.bar.bid,
                    direction=direction,
                )
            else:
                bar = first_recovery(bars, price, direction=direction)
        elif op is EntryOp.ABOVE:
            bar = first_above(bars, price)
        elif op is EntryOp.BELOW:
            bar = first_below(bars, price)
        elif op is EntryOp.MAXIMUM_TOUCH:
            bar = first_maximum_touch(bars, price)
        elif op is EntryOp.MINIMUM_TOUCH:
            bar = first_minimum_touch(bars, price)
        else:
            diag["reject_reason"] = "unknown_operation"
            return None, diag
    except RecoveryInvalid:
        diag["reject_reason"] = "recovery_invalid"
        return None, diag
    if bar is None:
        if op is EntryOp.BOUNCE:
            diag["reject_reason"] = "unconfirmed"
        else:
            diag["reject_reason"] = "no_event"
        return None, diag
    if _max_entry_exceeded(condition, bar, diag):
        return None, diag
    diag["crossings_found"] = 1
    return _snap_event(
        condition,
        bar,
        sport=sport,
        snap_fn=snap_fn,
        pbp_events=pbp_events,
        idx=1,
        diag=diag,
    )


def same_minute_ties(events: list[TouchEvent]) -> tuple[list[TouchEvent], int]:
    """Exclude same-game same-minute multi-ticker entries. No silent tie-break."""
    buckets: dict[tuple[str, str], list[TouchEvent]] = {}
    for ev in events:
        key = (ev.bar.game_id, ev.bar.ts.strftime("%Y-%m-%dT%H:%M"))
        buckets.setdefault(key, []).append(ev)
    kept: list[TouchEvent] = []
    excluded = 0
    for group in buckets.values():
        tickers = {e.bar.ticker for e in group}
        if len(tickers) > 1:
            excluded += len(group)
            continue
        kept.extend(group)
    return kept, excluded
