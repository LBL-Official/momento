"""Sport-family helpers. Clock grammar stays family-native.

Basketball = NBA / WNBA / NCAAB.
Baseball = MLB.
Do not scatter `if sport == "baseball"` through generic query / TE.
"""

from __future__ import annotations

import re
from typing import Iterable

BASKETBALL_SPORTS = frozenset({"NBA", "WNBA", "NCAAB"})
BASKETBALL_UI = frozenset({"basketball"})
BASEBALL_SPORTS = frozenset({"MLB"})
BASEBALL_UI = frozenset({"baseball"})
TENNIS_SPORTS = frozenset({"ATP", "WTA", "TENNIS"})
TENNIS_UI = frozenset({"tennis"})

FAMILY_BASKETBALL = "basketball"
FAMILY_BASEBALL = "baseball"
FAMILY_TENNIS = "tennis"
FAMILY_UNKNOWN = "unknown"

MIXED_CLOCK_REASON = (
    "Tennis, basketball, and baseball do not share a clock or state grammar. "
    "A joint mixed-family universe is OPERATION_REQUIRED. Select one sport family."
)


def family_of(sport_or_league: str | None) -> str:
    raw = str(sport_or_league or "").strip()
    key = raw.upper()
    if raw in BASKETBALL_SPORTS or raw in BASKETBALL_UI or key in BASKETBALL_SPORTS:
        return FAMILY_BASKETBALL
    if raw in BASEBALL_SPORTS or raw in BASEBALL_UI or key in BASEBALL_SPORTS:
        return FAMILY_BASEBALL
    if raw in TENNIS_SPORTS or raw in TENNIS_UI or key in TENNIS_SPORTS or raw.lower() == "tennis":
        return FAMILY_TENNIS
    return FAMILY_UNKNOWN


def is_basketball(sport_or_league: str | None) -> bool:
    return family_of(sport_or_league) == FAMILY_BASKETBALL


def is_baseball(sport_or_league: str | None) -> bool:
    return family_of(sport_or_league) == FAMILY_BASEBALL


def is_tennis(sport_or_league: str | None) -> bool:
    return family_of(sport_or_league) == FAMILY_TENNIS


def families_in(*groups: Iterable[str] | None) -> set[str]:
    found: set[str] = set()
    for group in groups:
        for item in group or ():
            fam = family_of(item)
            if fam != FAMILY_UNKNOWN:
                found.add(fam)
    return found


def mixed_clock_families(
    sports: Iterable[str] | None = None,
    leagues: Iterable[str] | None = None,
) -> bool:
    return len(families_in(sports, leagues)) > 1


# UI period chips. A foreign-family period is not a silent N=0 filter.
_BASKETBALL_PERIOD = re.compile(r"^(Q[1-4]|OT|P5|H[12](?:_[12])?)$")
_BASEBALL_PERIOD = re.compile(r"^(T[1-9X]|B[1-9X]|I7)$")
_TENNIS_PERIOD = re.compile(r"^(S[1-5]|G(?:1-3|4-6|7-9|10\+))$")

PBP_PRODUCER_FAMILY = {
    "espn": FAMILY_BASKETBALL,
    "nba_api": FAMILY_BASKETBALL,
    "mlb_statsapi": FAMILY_BASEBALL,
    "mcp": FAMILY_TENNIS,
}


def period_family(period: str | None) -> str:
    raw = str(period or "").strip()
    if not raw:
        return FAMILY_UNKNOWN
    if _BASKETBALL_PERIOD.match(raw):
        return FAMILY_BASKETBALL
    if _BASEBALL_PERIOD.match(raw):
        return FAMILY_BASEBALL
    if _TENNIS_PERIOD.match(raw):
        return FAMILY_TENNIS
    return FAMILY_UNKNOWN


def period_belongs_to_family(period: str | None, family: str | None) -> bool:
    if not period:
        return True
    got = period_family(period)
    if got == FAMILY_UNKNOWN:
        return False
    return got == family


def remaining_clock_legal(family: str | None) -> bool:
    """Basketball remaining-clock chips only. MLB/tennis have no MM:SS clock."""
    return family == FAMILY_BASKETBALL
