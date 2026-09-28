"""Later 80 cent labels. Not used by primary eligibility."""

from __future__ import annotations

from first78.extract import _quality

HIT80_E4 = 8000


def later_threshold_in_window(bars: list[dict], window_ok_fn, date_ok_fn) -> bool:
    had = False
    seen_below = False
    opened_above = False
    for bar in bars:
        if not _quality(bar.get("bid"), bar.get("ask"), bar.get("vol"), had):
            continue
        had = True
        if bar.get("bid") is None:
            continue
        if not seen_below and bar["bid"] >= HIT80_E4 and not opened_above:
            opened_above = True
            return False
        if bar["bid"] < HIT80_E4:
            seen_below = True
        elif seen_below and window_ok_fn(bar["ts"]) and date_ok_fn(bar["ts"]):
            return True
    return False
