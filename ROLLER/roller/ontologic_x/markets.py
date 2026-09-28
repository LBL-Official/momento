"""Provider market catalog. A key in this schema is not evidence that a book posted it."""

from __future__ import annotations

FULL_GAME = ("h2h", "spreads", "totals")
FULL_GAME_ALTERNATES = ("alternate_spreads", "alternate_totals")

QUARTER_MAIN = tuple(
    f"{family}_q{quarter}"
    for quarter in range(1, 5)
    for family in ("h2h", "spreads", "totals")
)
QUARTER_ALTERNATES = tuple(
    f"{family}_q{quarter}"
    for quarter in range(1, 5)
    for family in ("alternate_spreads", "alternate_totals")
)
HALVES = (
    "h2h_h1",
    "h2h_h2",
    "spreads_h1",
    "spreads_h2",
    "totals_h1",
    "totals_h2",
    "alternate_spreads_h1",
    "alternate_spreads_h2",
    "alternate_totals_h1",
    "alternate_totals_h2",
)
PERIODS = (
    "h2h_p1",
    "h2h_p2",
    "h2h_p3",
    "spreads_p1",
    "spreads_p2",
    "spreads_p3",
    "totals_p1",
    "totals_p2",
    "totals_p3",
)
INNINGS = (
    "h2h_1st_1_innings",
    "h2h_1st_5_innings",
    "spreads_1st_1_innings",
    "spreads_1st_5_innings",
    "totals_1st_1_innings",
    "totals_1st_5_innings",
)
SETS = ("h2h_s1", "h2h_s2", "spreads_s1", "totals_s1", "alternate_set_spreads", "alternate_set_totals")

# Keys documented by The Odds API. Presence here does not mean William Hill posts them.
CATALOG: dict[str, tuple[str, ...]] = {
    "basketball_nba": FULL_GAME + FULL_GAME_ALTERNATES + QUARTER_MAIN + QUARTER_ALTERNATES,
    "basketball_nba_preseason": FULL_GAME,
    "basketball_wnba": FULL_GAME + FULL_GAME_ALTERNATES + QUARTER_MAIN + QUARTER_ALTERNATES,
    "basketball_ncaab": FULL_GAME + HALVES,
    "baseball_mlb": FULL_GAME + INNINGS,
    "icehockey_nhl": FULL_GAME + PERIODS,
    "tennis": FULL_GAME + SETS,
}

PRIMARY_BOOK = "williamhill"
REHEARSAL_SPORT = "basketball_nba"
PRESEASON_SPORT = "basketball_nba_preseason"
DISCOVERY_SPORTS = (PRESEASON_SPORT, REHEARSAL_SPORT)


def requested_keys(sport_key: str) -> tuple[str, ...]:
    return CATALOG.get(sport_key, ())


def scenario_cost(market_keys: int, snapshots: int, games: int) -> int:
    """Credits if every requested key is returned, for one bookmaker group.

    The provider bills unique returned market keys, not each alternate line.
    """
    return market_keys * snapshots * games
