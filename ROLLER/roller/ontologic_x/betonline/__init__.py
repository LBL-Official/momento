"""BetOnline sportsbook adapter for Ontologic X. Research only."""

LIVE_EXECUTION = False
BOOKMAKER = "betonline"
SOURCE_URL = "https://www.betonline.ag/sportsbook/basketball/nba"


def event_url(game_id: object) -> str:
    return f"https://www.betonline.ag/sportsbook/basketball/nba/game/{game_id}"
