"""Phase 1 reference detectors. Full-scan, candle-close only. CANDLE ≠ FILL.

These functions are the semantic authority. Indexes must reproduce them, not redefine them.
next always means the next tradable bar from tradable_sequence(), never the next raw CSV row.
"""

from __future__ import annotations

from typing import Any

from roller.research_query.models import OPERATION_SEMANTICS_VERSION

__all__ = (
    "OPERATION_SEMANTICS_VERSION",
    "RecoveryInvalid",
    "first_above",
    "first_below",
    "first_bounce",
    "first_break",
    "first_cross",
    "first_maximum_touch",
    "first_minimum_touch",
    "first_recovery",
    "first_reversion",
    "path_bounce",
    "path_maximum_move",
    "path_minimum_move",
    "path_never_reach",
    "path_reach",
    "path_revert",
)


def first_cross(
    bars: list[Any],
    price_e4: int,
    direction: str | None = None,
) -> Any | None:
    """First directional close-cross. Equality on current counts. 80→80 is not a cross."""
    if len(bars) < 2:
        return None
    prior = bars[0].bid
    for bar in bars[1:]:
        up = prior < price_e4 and bar.bid >= price_e4
        down = prior > price_e4 and bar.bid <= price_e4
        if direction == "up" and up:
            return bar
        if direction == "down" and down:
            return bar
        if direction not in ("up", "down") and (up or down):
            return bar
        prior = bar.bid
    return None


def first_break(
    bars: list[Any],
    price_e4: int,
    direction: str | None = None,
) -> Any | None:
    """Cross that finishes strictly beyond P. 79→80 is Cross, not Break."""
    if len(bars) < 2:
        return None
    prior = bars[0].bid
    for bar in bars[1:]:
        up = prior < price_e4 and bar.bid > price_e4
        down = prior > price_e4 and bar.bid < price_e4
        if direction == "up" and up:
            return bar
        if direction == "down" and down:
            return bar
        if direction not in ("up", "down") and (up or down):
            return bar
        prior = bar.bid
    return None


def first_reversion(
    bars: list[Any],
    price_e4: int,
    direction: str | None = None,
) -> Any | None:
    """Cross P, then later cross back to the original side. Ordered. 79→81→80 is not complete."""
    if not bars:
        return None
    i = 0
    while i < len(bars) and bars[i].bid == price_e4:
        i += 1
    if i >= len(bars):
        return None
    start_below = bars[i].bid < price_e4
    if direction == "up" and not start_below:
        return None
    if direction == "down" and start_below:
        return None
    crossed = False
    prior = bars[i].bid
    for bar in bars[i + 1 :]:
        if not crossed:
            if start_below and prior < price_e4 and bar.bid >= price_e4:
                crossed = True
            elif (not start_below) and prior > price_e4 and bar.bid <= price_e4:
                crossed = True
        elif start_below and prior > price_e4 and bar.bid < price_e4:
            return bar
        elif (not start_below) and prior < price_e4 and bar.bid > price_e4:
            return bar
        prior = bar.bid
    return None


def first_bounce(
    bars: list[Any],
    price_e4: int,
    direction: str | None = None,
) -> Any | None:
    """Touch then reverse through P on the next tradable candle. Timestamp = confirmation bar."""
    if len(bars) < 3:
        return None
    for i in range(len(bars) - 2):
        prior, cur, nxt = bars[i], bars[i + 1], bars[i + 2]
        up = prior.bid < price_e4 and cur.bid >= price_e4 and nxt.bid < price_e4
        down = prior.bid > price_e4 and cur.bid <= price_e4 and nxt.bid > price_e4
        if direction == "up" and up:
            return nxt
        if direction == "down" and down:
            return nxt
        if direction not in ("up", "down") and (up or down):
            return nxt
    return None


class RecoveryInvalid(ValueError):
    """Standalone Recovery with anchor_close == P and no direction. Not an empty population."""


def first_recovery(
    bars: list[Any],
    price_e4: int,
    *,
    anchor_close: int | None = None,
    direction: str | None = None,
) -> Any | None:
    """Adverse excursion away from P, then return cross. Equality at P does not invent a side."""
    if not bars:
        return None
    anchor = int(anchor_close if anchor_close is not None else bars[0].bid)
    if anchor > price_e4:
        want_below = True
    elif anchor < price_e4:
        want_below = False
    elif direction == "down":
        want_below = True
    elif direction == "up":
        want_below = False
    else:
        raise RecoveryInvalid("RECOVERY requires an explicit direction when anchor_close == P")
    start = 0
    if anchor_close is None:
        start = 1
    adverse = False
    prior = anchor
    for bar in bars[start:]:
        if not adverse:
            if want_below and bar.bid < price_e4:
                adverse = True
            elif (not want_below) and bar.bid > price_e4:
                adverse = True
        elif want_below and prior < price_e4 and bar.bid >= price_e4:
            return bar
        elif (not want_below) and prior > price_e4 and bar.bid <= price_e4:
            return bar
        prior = bar.bid
    return None


def first_above(bars: list[Any], price_e4: int) -> Any | None:
    for bar in bars:
        if bar.bid > price_e4:
            return bar
    return None


def first_below(bars: list[Any], price_e4: int) -> Any | None:
    for bar in bars:
        if bar.bid < price_e4:
            return bar
    return None


def first_maximum_touch(bars: list[Any], price_e4: int) -> Any | None:
    """First bar at which running max of tradable close reaches P. Full series, then period filter."""
    running: int | None = None
    for bar in bars:
        running = bar.bid if running is None else max(running, bar.bid)
        if running >= price_e4:
            return bar
    return None


def first_minimum_touch(bars: list[Any], price_e4: int) -> Any | None:
    running: int | None = None
    for bar in bars:
        running = bar.bid if running is None else min(running, bar.bid)
        if running <= price_e4:
            return bar
    return None


class _AnchorClose:
    """Virtual prior close so post-entry detectors reuse entry Bounce / Reversion."""

    def __init__(self, bid: int) -> None:
        self.bid = int(bid)


def path_bounce(
    bars_after_entry: list[Any],
    price_e4: int,
    *,
    entry_close: int,
    direction: str | None = None,
) -> Any | None:
    """Post-entry Bounce. Missing next tradable bar does not fire. Timestamp = next."""
    if not bars_after_entry:
        return None
    return first_bounce([_AnchorClose(entry_close), *bars_after_entry], price_e4, direction)


def path_revert(
    bars_after_entry: list[Any],
    price_e4: int,
    *,
    entry_close: int,
    direction: str | None = None,
) -> Any | None:
    """Post-entry Reversion. Event-2 timestamp. 79→81→80 is not complete."""
    hit = first_reversion([_AnchorClose(entry_close), *bars_after_entry], price_e4, direction)
    if hit is None or isinstance(hit, _AnchorClose):
        return None
    return hit


def path_maximum_move(bars_after_entry: list[Any], price_e4: int) -> Any | None:
    """First post-entry bar where running max(close) ≥ P."""
    return first_maximum_touch(bars_after_entry, price_e4)


def path_minimum_move(bars_after_entry: list[Any], price_e4: int) -> Any | None:
    """First post-entry bar where running min(close) ≤ P."""
    return first_minimum_touch(bars_after_entry, price_e4)


def path_reach(
    bars_after_entry: list[Any],
    price_e4: int,
    *,
    entry_close: int,
) -> Any | None:
    """Complement basis for Never Reach. Same crossing as path REACH."""
    prior = int(entry_close)
    for bar in bars_after_entry:
        current = int(bar.bid)
        if current <= 0:
            continue
        if prior > price_e4 and current <= price_e4:
            return bar
        if prior < price_e4 and current >= price_e4:
            return bar
        prior = current
    return None


def path_never_reach(
    bars_after_entry: list[Any],
    price_e4: int,
    *,
    entry_close: int,
    resolve_bar: Any | None = None,
) -> Any | None:
    """Complement of Reach. Does not fire mid-path. Resolve bar or last post-entry close."""
    if path_reach(bars_after_entry, price_e4, entry_close=entry_close) is not None:
        return None
    if resolve_bar is not None:
        return resolve_bar
    if bars_after_entry:
        return bars_after_entry[-1]
    return None
