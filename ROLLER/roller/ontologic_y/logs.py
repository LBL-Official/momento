"""Slow NBA game-log retrieval. Counting stats only."""

from __future__ import annotations

from datetime import datetime

from roller.ontologic_x.identity import current_nba_season, season_type_from_game_id

SEASON_TYPES = ("Pre Season", "Regular Season")
FIELDS = ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "TOV", "PTS")


def fetch_logs(today: datetime, timeout: int = 20) -> dict:
    season = current_nba_season(today)
    try:
        from nba_api.stats.endpoints import leaguegamelog
    except ImportError:
        return {"status": "NBA_API_NOT_INSTALLED", "season": season, "rows": []}
    rows = []
    errors = []
    for season_type in SEASON_TYPES:
        try:
            frame = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star=season_type,
                timeout=timeout,
            ).get_data_frames()[0]
        except Exception as exc:
            errors.append(f"{season_type}:{type(exc).__name__}")
            continue
        for record in frame.to_dict("records"):
            game_id = str(record.get("GAME_ID") or "").zfill(10)
            rows.append(
                {
                    "nba_game_id": game_id,
                    "season": season,
                    "season_type": season_type_from_game_id(game_id),
                    "team_id": str(record.get("TEAM_ID") or ""),
                    "team_abbreviation": record.get("TEAM_ABBREVIATION"),
                    "start_utc": record.get("GAME_DATE"),
                    "completed": True,
                    **{field: record.get(field) for field in FIELDS},
                }
            )
    status = "OK" if rows else ("SOURCE_UNAVAILABLE" if errors else "EMPTY")
    return {"status": status, "season": season, "rows": rows, "errors": errors}
