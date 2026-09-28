"""FIRST78 eligibility. Stop is an argument. The 67-cent reference scan is not edited."""

from __future__ import annotations

HIT_E4 = 7800
MAX_SPREAD_E4 = 1000
SPLIT_S = 600


def quality(bid: int | None, ask: int | None, vol: int | None, had: bool) -> bool:
    if bid is None or ask is None:
        return False
    if bid > ask:
        return False
    if ask - bid > MAX_SPREAD_E4:
        return False
    if vol is not None and vol > 0:
        return True
    return had


def ncaab_bucket(period: int, remaining_s: float) -> str:
    if int(period) == 1:
        return "H1_1" if float(remaining_s) > SPLIT_S else "H1_2"
    if int(period) == 2:
        return "H2_1" if float(remaining_s) > SPLIT_S else "H2_2"
    return "OUT"


def window_bucket(sport: str, bucket: str | None) -> bool:
    if sport == "NBA":
        return bucket in {"Q2", "Q3"}
    if sport == "NCAAB":
        return bucket in {"H1_2", "H2_1"}
    return False


def _quality_bars(bars: list[dict]) -> tuple[list[dict], bool]:
    kept: list[dict] = []
    had = False
    timestamps: list[int] = []
    for bar in bars:
        if not quality(bar.get("bid"), bar.get("ask"), bar.get("vol"), had):
            continue
        had = True
        kept.append(bar)
        timestamps.append(int(bar["ts"]))
    return kept, len(timestamps) != len(set(timestamps))


def find_entry(bars: list[dict], hit_cents: int = 78) -> dict:
    """Contract-wise close up-cross. Does not look for a later 80-cent print."""
    hit_e4 = int(hit_cents) * 100
    quality, duplicate = _quality_bars(bars)
    if duplicate:
        return {
            "cross_found": False,
            "tradable": False,
            "reason": "CHRONOLOGY_UNRESOLVED",
            "quality_bars": quality,
        }
    seen_below = False
    entry_i = None
    for index, bar in enumerate(quality):
        bid = bar.get("bid")
        if not seen_below and entry_i is None and bid is not None and bid >= hit_e4:
            if index == 0:
                return {
                    "cross_found": False,
                    "tradable": False,
                    "reason": "UNPROVEN_FIRST",
                    "quality_bars": quality,
                }
        if entry_i is None:
            if bid is not None and bid < hit_e4:
                seen_below = True
            elif seen_below and bid is not None and bid >= hit_e4:
                entry_i = index
    if entry_i is None:
        reason = "NO_CROSS" if quality else "NO_QUALITY_BARS"
        return {"cross_found": False, "tradable": False, "reason": reason, "quality_bars": quality}
    entry = quality[entry_i]
    return {
        "cross_found": True,
        "tradable": True,
        "reason": None,
        "entry_i": entry_i,
        "signal_ts": int(entry["ts"]),
        "observed_close_cents": int(entry["bid"]) // 100,
        "quality_bars": quality,
    }


def stop_after(entry: dict, stop_cents: int) -> dict:
    if not entry.get("cross_found"):
        return {"stop_ts": None, "stop_close_cents": None, "intrabar_ambiguity": False}
    quality = entry["quality_bars"]
    bar = quality[int(entry["entry_i"])]
    stop_e4 = int(stop_cents) * 100
    ambiguous = bar.get("low") is not None and int(bar["low"]) <= stop_e4
    stop = None
    for later in quality[int(entry["entry_i"]) + 1 :]:
        if later.get("bid") is not None and int(later["bid"]) <= stop_e4 and int(later["ts"]) > int(bar["ts"]):
            stop = later
            break
    return {
        "stop_ts": None if stop is None else int(stop["ts"]),
        "stop_close_cents": None if stop is None else int(stop["bid"]) // 100,
        "intrabar_ambiguity": ambiguous,
    }


def scan_variants(bars: list[dict], stops: tuple[int, ...] = (67, 65, 60)) -> dict:
    entry = find_entry(bars)
    variants = {int(stop): stop_after(entry, int(stop)) for stop in stops}
    return {"entry": entry, "variants": variants}
