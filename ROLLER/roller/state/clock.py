"""Game clock helpers. Not used for money.

NBA regulation is 4×12:00. WNBA is 4×10:00. NCAAB is 2×20:00.
OT is 5:00 in all three. Do not convert tip+clock into a wall time.
"""

from __future__ import annotations

import re
from typing import Any

_ISO_CLOCK = re.compile(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")
_MMSS_CLOCK = re.compile(r"^(\d+):(\d+(?:\.\d+)?)$")

# regulation_periods, regulation_seconds, ot_seconds
SPORT_CLOCK = {
    "NBA": (4, 720, 300),
    "WNBA": (4, 600, 300),
    "NCAAB": (2, 1200, 300),
}

ASKED_SIX = frozenset({"Q2", "Q3", "H1_2", "H2_1"})


def clock_remaining_seconds(clock: Any) -> float | None:
    if isinstance(clock, (int, float)) and not isinstance(clock, bool):
        return float(clock)
    text = str(clock or "").strip()
    if not text:
        return None
    m = _ISO_CLOCK.fullmatch(text)
    if m:
        mins = int(m.group(1) or 0)
        secs = float(m.group(2) or 0)
        return mins * 60 + secs
    m = _MMSS_CLOCK.fullmatch(text)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return None


def sport_clock_spec(sport: str | None) -> tuple[int, int, int]:
    return SPORT_CLOCK.get(str(sport or "NBA").upper(), SPORT_CLOCK["NBA"])


def elapsed_game_seconds(
    period: Any,
    clock: Any,
    *,
    sport: str = "NBA",
    regulation_period: int | None = None,
) -> int | None:
    rem = clock_remaining_seconds(clock)
    if rem is None or period in (None, ""):
        return None
    try:
        p = int(period)
    except (TypeError, ValueError):
        return None
    n_reg, reg, ot = sport_clock_spec(sport)
    if regulation_period is not None:
        reg = int(regulation_period)
    if p <= n_reg:
        return int((p - 1) * reg + (reg - rem))
    return int(n_reg * reg + (p - n_reg - 1) * ot + (ot - rem))


def entry_slice(sport: str | None, period: Any, remaining_s: float | None) -> str:
    """Q1–Q4 / H1_1–H2_2 / OT. Missing period or remaining → UNALIGNED."""
    if period in (None, ""):
        return "UNALIGNED"
    try:
        p = int(period)
    except (TypeError, ValueError):
        return "UNALIGNED"
    sp = str(sport or "").upper()
    if sp == "NCAAB":
        if p >= 3:
            return "OT"
        if remaining_s is None:
            return "UNALIGNED"
        if p == 1:
            return "H1_1" if remaining_s > 600 else "H1_2"
        if p == 2:
            return "H2_1" if remaining_s > 600 else "H2_2"
        return "UNALIGNED"
    if p >= 5:
        return "OT"
    if p in (1, 2, 3, 4):
        return f"Q{p}"
    return "UNALIGNED"
