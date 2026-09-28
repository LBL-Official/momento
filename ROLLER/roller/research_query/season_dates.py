"""Sport+league season calendars for date autofill.

2025-26 bounds match warehouse games.game_date min/max.
Other seasons use the published calendar. Missing warehouse years
are not substituted with a different season.
"""

from __future__ import annotations

from datetime import date

# A published "full season" shorter than this is a stub (e.g. the old MLB
# June 18–30 Kalshi-complete slice). Collapsing it would unbind the universe
# and admit every warehouse month. Custom windows must stay on the question.
MIN_FULL_SEASON_DAYS = 60

NBA = {
    "2023-24": ("2023-10-05", "2024-06-17"),
    "2024-25": ("2024-10-04", "2025-06-22"),
    "2025-26": ("2025-10-10", "2026-06-13"),
    "2026-27": ("2026-10-06", "2027-06-20"),
}
NCAAB = {
    "2023-24": ("2023-11-06", "2024-04-08"),
    "2024-25": ("2024-11-04", "2025-04-07"),
    "2025-26": ("2025-11-03", "2026-04-04"),
    "2026-27": ("2026-11-03", "2027-04-06"),
}
WNBA = {
    "2025": ("2025-05-16", "2025-10-10"),
}
MLB = {
    "2025-26": ("2025-03-18", "2026-09-04"),
    "2025-2026": ("2025-03-18", "2026-09-04"),
}
ATP = {
    "2025-26": ("2025-06-18", "2026-09-12"),
    "2025-2026": ("2025-06-18", "2026-09-12"),
}
WTA = {
    "2025-26": ("2025-06-18", "2026-09-12"),
    "2025-2026": ("2025-06-18", "2026-09-12"),
}
BY_LEAGUE = {"NBA": NBA, "NCAAB": NCAAB, "WNBA": WNBA, "MLB": MLB, "ATP": ATP, "WTA": WTA}


def normalize_season_id(season_id: str) -> str:
    text = str(season_id or "")
    parts = text.split("-")
    if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
        return f"{parts[0]}-{parts[1][2:]}"
    return text


def bounds_for_season(league: str, season_id: str) -> tuple[str, str] | None:
    table = BY_LEAGUE.get(str(league or ""))
    if not table:
        return None
    return table.get(season_id) or table.get(normalize_season_id(season_id))


def date_range_for_selections(
    leagues: tuple[str, ...] | list[str],
    seasons: tuple[str, ...] | list[str],
) -> tuple[str, str] | None:
    if not seasons:
        return None
    use_leagues = list(leagues) if leagues else list(BY_LEAGUE)
    starts: list[str] = []
    ends: list[str] = []
    for league in use_leagues:
        for season in seasons:
            bounds = bounds_for_season(league, season)
            if bounds:
                starts.append(bounds[0])
                ends.append(bounds[1])
    if not starts:
        return None
    return min(starts), max(ends)


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def collapse_full_season_dates(
    leagues: tuple[str, ...] | list[str],
    seasons: tuple[str, ...] | list[str],
    date_from: str | None,
    date_to: str | None,
) -> tuple[str | None, str | None]:
    """If the UI filled the exact selected-season union, treat as no date filter.

    Stub calendars (span < MIN_FULL_SEASON_DAYS) are never collapsed. The old
    MLB June 18–30 table would otherwise drop 2026-06-18→2026-06-30 and scan
    every last-trade month, including 2025.
    """
    if not date_from and not date_to:
        return None, None
    filled = date_range_for_selections(leagues, seasons)
    if not filled or date_from != filled[0] or date_to != filled[1]:
        return date_from, date_to
    lo = _parse_day(filled[0])
    hi = _parse_day(filled[1])
    if lo is None or hi is None or (hi - lo).days < MIN_FULL_SEASON_DAYS:
        return date_from, date_to
    return None, None
