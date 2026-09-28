"""Ex-ante FIRST78 eligibility. This module does not read an 80 cent field."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from first78.extract import _quality
from first78.select import select_game

LA = ZoneInfo("America/Los_Angeles")
HIT_E4 = 7800
STOP_E4 = 6700
E4 = Decimal(10000)

WINDOWS = {
    "OCT_2025": (
        datetime(2025, 10, 15, 0, 0, tzinfo=LA),
        datetime(2025, 11, 1, 0, 0, tzinfo=LA),
    ),
    "APR_2025": (
        datetime(2025, 4, 1, 0, 0, tzinfo=LA),
        datetime(2025, 5, 1, 0, 0, tzinfo=LA),
    ),
}


def in_window(ts: int, test_id: str) -> bool:
    start, end = WINDOWS[test_id]
    local = datetime.fromtimestamp(int(ts), tz=LA)
    return start <= local < end


def local_day(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=LA).date().isoformat()


def dollars_to_e4(value) -> int | None:
    if value is None or value == "":
        return None
    return int((Decimal(str(value)) * E4).to_integral_value(rounding=ROUND_HALF_UP))


def scan_bars(bars: list[dict]) -> dict:
    """First proven up-cross. An opening print already above 78¢ is not a cross."""
    had = False
    seen_below = False
    quality: list[dict] = []
    entry_i = None
    for bar in bars:
        if not _quality(bar.get("bid"), bar.get("ask"), bar.get("vol"), had):
            continue
        had = True
        if not quality and bar["bid"] is not None and bar["bid"] >= HIT_E4:
            return {
                "cross_found": False,
                "tradable": False,
                "reason": "UNPROVEN_FIRST",
                "quality_bars": [],
            }
        quality.append(bar)
        if entry_i is None:
            if bar["bid"] is not None and bar["bid"] < HIT_E4:
                seen_below = True
            elif seen_below and bar["bid"] is not None and bar["bid"] >= HIT_E4:
                entry_i = len(quality) - 1
    if entry_i is None:
        reason = "NO_CROSS" if quality else "NO_QUALITY_BARS"
        return {"cross_found": False, "tradable": False, "reason": reason, "quality_bars": quality}
    entry = quality[entry_i]
    if entry.get("low") is not None and entry["low"] <= STOP_E4:
        return {
            "cross_found": False,
            "tradable": False,
            "reason": "CHRONOLOGY_UNRESOLVED",
            "signal_ts": entry["ts"],
            "quality_bars": quality,
        }
    stop = None
    for later in quality[entry_i + 1 :]:
        if later.get("bid") is not None and later["bid"] <= STOP_E4:
            stop = later
            break
    return {
        "cross_found": True,
        "tradable": True,
        "reason": None,
        "signal_ts": entry["ts"],
        "observed_close_cents": entry["bid"] // 100,
        "overshoot_cents": entry["bid"] // 100 - 78,
        "spread_cents": (entry["ask"] - entry["bid"]) // 100,
        "stop_ts": None if stop is None else stop["ts"],
        "stop_close_cents": None if stop is None else stop["bid"] // 100,
        "quality_bars": quality,
    }


def choose_contract(contracts: list[dict]) -> dict:
    result = select_game(contracts, "CONTRACT_WISE_FIRST")
    if result["chosen"] is not None:
        return result
    reasons = [c.get("reason") for c in contracts]
    if reasons and all(r == "UNPROVEN_FIRST" for r in reasons):
        result["rejection_reason"] = "UNPROVEN_FIRST"
    elif "CHRONOLOGY_UNRESOLVED" in reasons and result["rejection_reason"] == "NO_CROSS":
        result["rejection_reason"] = "CHRONOLOGY_UNRESOLVED"
    elif result["rejection_reason"] == "FIRST_OUTSIDE_WINDOW":
        buckets = [c.get("clock_bucket") for c in contracts if c.get("cross_found")]
        if buckets and all(b in (None, "", "UNALIGNED") for b in buckets):
            result["rejection_reason"] = "CLOCK_UNAVAILABLE"
    return result
