"""Close-trigger scan. An intrabar low is a flag, not a rejection."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from first78.extract import _quality

HIT_E4 = 7800
STOP_E4 = 6700


def dollars_to_e4(value) -> int | None:
    if value is None or value == "":
        return None
    return int((Decimal(str(value)) * Decimal(10000)).to_integral_value(rounding=ROUND_HALF_UP))


def scan_close_cross(bars: list[dict]) -> dict:
    quality = []
    had = False
    seen_below = False
    entry_i = None
    timestamps = []
    for bar in bars:
        if not _quality(bar.get("bid"), bar.get("ask"), bar.get("vol"), had):
            continue
        had = True
        quality.append(bar)
        timestamps.append(int(bar["ts"]))
        if not seen_below and entry_i is None and bar.get("bid") is not None and bar["bid"] >= HIT_E4 and not any(
            earlier.get("bid") is not None and earlier["bid"] < HIT_E4 for earlier in quality[:-1]
        ):
            if len(quality) == 1:
                return {
                    "cross_found": False,
                    "tradable": False,
                    "reason": "UNPROVEN_FIRST",
                    "quality_bars": quality,
                    "duplicate_timestamp": len(timestamps) != len(set(timestamps)),
                }
        if entry_i is None:
            if bar.get("bid") is not None and bar["bid"] < HIT_E4:
                seen_below = True
            elif seen_below and bar.get("bid") is not None and bar["bid"] >= HIT_E4:
                entry_i = len(quality) - 1
    duplicate = len(timestamps) != len(set(timestamps))
    if duplicate:
        return {
            "cross_found": False,
            "tradable": False,
            "reason": "CHRONOLOGY_UNRESOLVED",
            "duplicate_timestamp": True,
            "quality_bars": quality,
        }
    if entry_i is None:
        reason = "NO_CROSS" if quality else "NO_QUALITY_BARS"
        return {"cross_found": False, "tradable": False, "reason": reason, "quality_bars": quality, "duplicate_timestamp": False}
    entry = quality[entry_i]
    ambiguous = entry.get("low") is not None and entry["low"] <= STOP_E4
    stop = None
    for later in quality[entry_i + 1 :]:
        if later.get("bid") is not None and later["bid"] <= STOP_E4 and int(later["ts"]) > int(entry["ts"]):
            stop = later
            break
    return {
        "cross_found": True,
        "tradable": True,
        "reason": None,
        "signal_ts": int(entry["ts"]),
        "action_ts": int(entry["ts"]),
        "bar_end_ts": int(entry["ts"]),
        "observed_close_cents": entry["bid"] // 100,
        "intrabar_ambiguity": ambiguous,
        "stop_ts": None if stop is None else int(stop["ts"]),
        "stop_close_cents": None if stop is None else stop["bid"] // 100,
        "quality_bars": quality,
        "duplicate_timestamp": False,
        "availability": "MODELED_BAR_END",
    }


def delayed_entry(bars: list[dict], signal_ts: int, delay: int, grace: int = 60) -> dict:
    start = int(signal_ts) + int(delay)
    limit = start + int(grace)
    window = [bar for bar in bars if start <= int(bar["ts"]) <= limit and bar.get("bid") is not None]
    if not window:
        return {"status": "LATENCY_GAP_UNRESOLVED"}
    entry = window[0]
    if any(int(signal_ts) < int(bar["ts"]) <= int(entry["ts"]) and bar.get("bid") is not None and bar["bid"] <= STOP_E4 for bar in bars):
        return {"status": "STOP_ALREADY_TRUE"}
    price = int(entry["bid"]) // 100
    later = next((bar for bar in bars if int(bar["ts"]) > int(entry["ts"]) and bar.get("bid") is not None and bar["bid"] <= STOP_E4), None)
    return {
        "status": "NEXT_BAR_PRICE_PROXY",
        "action_ts": int(entry["ts"]),
        "entry_price_cents": price,
        "stop_ts": None if later is None else int(later["ts"]),
        "availability": "MODELED_BAR_END",
    }
