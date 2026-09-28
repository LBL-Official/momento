"""Deterministic MLB state derived from a PIT PBP row.

Scores, outs, count, and runners come from the event row.
3 outs is a half-inning transition, not a live state.
Missing is not 0, 0-0, or empty.
"""

from __future__ import annotations

from typing import Any

HALF_TOP = "top"
HALF_BOTTOM = "bottom"
VALID_HALVES = frozenset({HALF_TOP, HALF_BOTTOM})
VALID_OUTS = frozenset({0, 1, 2})
VALID_BALLS = frozenset({0, 1, 2, 3})
VALID_STRIKES = frozenset({0, 1, 2})

RUNNER_CATEGORIES = (
    "empty",
    "1st",
    "2nd",
    "3rd",
    "1st+2nd",
    "1st+3rd",
    "2nd+3rd",
    "loaded",
    "risp",
    "any_on",
)

COUNT_PITCHER_AHEAD = "pitcher_ahead"
COUNT_HITTER_AHEAD = "hitter_ahead"
COUNT_EVEN = "even"


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if value in (True, 1, "1", "true", "True", "yes"):
        return True
    if value in (False, 0, "0", "false", "False", "no"):
        return False
    return None


def normalize_half(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if raw in ("top", "t"):
        return HALF_TOP
    if raw in ("bottom", "bot", "b"):
        return HALF_BOTTOM
    return None


def live_outs(value: Any) -> int | None:
    outs = _int(value)
    if outs in VALID_OUTS:
        return outs
    return None


def live_balls(value: Any) -> int | None:
    balls = _int(value)
    if balls in VALID_BALLS:
        return balls
    return None


def live_strikes(value: Any) -> int | None:
    strikes = _int(value)
    if strikes in VALID_STRIKES:
        return strikes
    return None


def count_display(balls: int | None, strikes: int | None) -> str | None:
    if balls is None or strikes is None:
        return None
    return f"{balls}-{strikes}"


def count_leverage(balls: int | None, strikes: int | None) -> str | None:
    """Deterministic from count. Not predictive."""
    if balls is None or strikes is None:
        return None
    if strikes > balls:
        return COUNT_PITCHER_AHEAD
    if balls > strikes:
        return COUNT_HITTER_AHEAD
    return COUNT_EVEN


def runner_flags(row: dict[str, Any] | None) -> tuple[bool | None, bool | None, bool | None]:
    if not row:
        return None, None, None
    r1 = _bool(row.get("runner_on_1"))
    r2 = _bool(row.get("runner_on_2"))
    r3 = _bool(row.get("runner_on_3"))
    return r1, r2, r3


def runner_category(
    on1: bool | None,
    on2: bool | None,
    on3: bool | None,
) -> str | None:
    if on1 is None or on2 is None or on3 is None:
        return None
    if on1 and on2 and on3:
        return "loaded"
    if on1 and on2:
        return "1st+2nd"
    if on1 and on3:
        return "1st+3rd"
    if on2 and on3:
        return "2nd+3rd"
    if on1:
        return "1st"
    if on2:
        return "2nd"
    if on3:
        return "3rd"
    return "empty"


def runner_matches(category: str | None, want: str | None) -> bool:
    if not want or want == "any":
        return True
    if category is None:
        return False
    if want == category:
        return True
    if want == "risp":
        return category in {"2nd", "3rd", "1st+2nd", "1st+3rd", "2nd+3rd", "loaded"}
    if want == "any_on":
        return category != "empty"
    return False


def inning_slice(inning: int | None, half: str | None) -> str:
    if inning is None or half not in VALID_HALVES:
        return "UNALIGNED"
    prefix = "T" if half == HALF_TOP else "B"
    if int(inning) >= 10:
        return f"{prefix}X"
    if int(inning) < 1:
        return "UNALIGNED"
    return f"{prefix}{int(inning)}"


def slice_matches(have: str | None, want: str | None) -> bool:
    if not want:
        return True
    have_s = str(have or "")
    want_s = str(want)
    if have_s == want_s:
        return True
    if want_s.startswith("I") and len(want_s) >= 2:
        token = want_s[1:]
        if token == "X":
            return have_s in {"TX", "BX"}
        return have_s in {f"T{token}", f"B{token}"}
    return False


def batting_team(half: str | None) -> str | None:
    if half == HALF_TOP:
        return "away"
    if half == HALF_BOTTOM:
        return "home"
    return None


def yes_batting(
    *,
    half: str | None,
    batting: str | None,
    team_side: str | None,
) -> bool | None:
    """(YES home AND bottom) OR (YES away AND top). Fail closed if any input missing."""
    half_n = normalize_half(half)
    bat = str(batting or "").strip().lower() or batting_team(half_n)
    side = str(team_side or "").strip().lower()
    if half_n not in VALID_HALVES or bat not in {"home", "away"} or side not in {"home", "away"}:
        return None
    if side == "home":
        return bat == "home" and half_n == HALF_BOTTOM
    return bat == "away" and half_n == HALF_TOP


def yes_pitching(yes_bat: bool | None) -> bool | None:
    if yes_bat is None:
        return None
    return not yes_bat
