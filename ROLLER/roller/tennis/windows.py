"""Tennis structural entry windows. OR within a group. Not a basketball clock."""

from __future__ import annotations

from typing import Any

SET_ANY = frozenset({"SET_ANY", "S", "SET"})
GAME_RANGES: dict[str, tuple[int, int | None]] = {
    "G1-3": (1, 3),
    "G4-6": (4, 6),
    "G7-9": (7, 9),
    "G10+": (10, None),
}


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_window(want: str) -> str:
    return str(want or "").strip().upper().replace(" ", "")


def set_matches(set_number: int | None, want: str) -> bool:
    token = normalize_window(want)
    if token in SET_ANY:
        return set_number is not None
    if token.startswith("S") and token[1:].isdigit():
        return set_number is not None and set_number == int(token[1:])
    return False


def game_matches(game_number: int | None, want: str) -> bool:
    token = normalize_window(want)
    bounds = GAME_RANGES.get(token)
    if bounds is None:
        if token.startswith("G") and token[1:].isdigit():
            return game_number is not None and game_number == int(token[1:])
        return False
    if game_number is None:
        return False
    lo, hi = bounds
    if hi is None:
        return game_number >= lo
    return lo <= game_number <= hi


def window_matches(snap: dict[str, Any], want: str) -> bool:
    """True when the snapped tennis state falls in the named window.

    Missing set/game on the snap fails closed (False), never assumed.
    """
    token = normalize_window(want)
    if not token:
        return True
    set_n = _int(snap.get("set_number"))
    game_n = _int(snap.get("game_number"))
    if token in SET_ANY or (token.startswith("S") and token[1:].isdigit()):
        return set_matches(set_n, token)
    if token in GAME_RANGES or (token.startswith("G") and token[1:].isdigit()):
        return game_matches(game_n, token)
    return False
