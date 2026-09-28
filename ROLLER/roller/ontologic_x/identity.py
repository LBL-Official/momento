"""NBA schedule identity. Team id + start. Display names are not a join key."""

from __future__ import annotations

from datetime import datetime, timedelta

MATCH_WINDOW = timedelta(minutes=90)
SEASON_PREFIX = {
    "001": "preseason",
    "002": "regular",
    "003": "allstar",
    "004": "playoffs",
    "005": "playin",
}


def _parse_time(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed


def game_id_text(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit():
        return text.zfill(10)
    return text


def season_type_from_game_id(nba_game_id: str) -> str:
    return SEASON_PREFIX.get(game_id_text(nba_game_id)[:3], "UNKNOWN")


def current_nba_season(today: datetime) -> str:
    year = today.year if today.month >= 7 else today.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


def _status(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"live", "inprogress", "in_progress"}:
        return "live"
    if text in {"completed", "final", "closed"}:
        return "completed"
    if text in {"upcoming", "scheduled", "pregame"}:
        return "upcoming"
    if text.isdigit():
        code = int(text)
        if code == 2:
            return "live"
        if code == 3:
            return "completed"
        if code == 1:
            return "upcoming"
    return "upcoming"


def _team_full_name(city: object, name: object) -> str | None:
    city_text = str(city).strip() if city else ""
    name_text = str(name).strip() if name else ""
    if not name_text:
        return None
    if not city_text or name_text.casefold().startswith(f"{city_text.casefold()} "):
        return name_text
    return f"{city_text} {name_text}"


def normalize_nba_game(row: dict) -> dict:
    nba_game_id = game_id_text(row.get("nba_game_id") or row.get("gameId") or row.get("GAME_ID"))
    start = row.get("start_utc") or row.get("gameDateTimeUTC") or row.get("GAME_DATE_EST")
    return {
        "nba_game_id": nba_game_id,
        "season": row.get("season") or row.get("seasonYear"),
        "season_type": row.get("season_type") or season_type_from_game_id(nba_game_id),
        "status": _status(row.get("status") if row.get("status") is not None else row.get("gameStatus")),
        "neutral": bool(row.get("neutral") if "neutral" in row else row.get("isNeutral")),
        "start_utc": start,
        "home_team_id": _int_id(row.get("home_team_id") or row.get("homeTeam_teamId") or row.get("HOME_TEAM_ID")),
        "away_team_id": _int_id(row.get("away_team_id") or row.get("awayTeam_teamId") or row.get("VISITOR_TEAM_ID")),
        "home_tricode": row.get("home_tricode") or row.get("homeTeam_teamTricode"),
        "away_tricode": row.get("away_tricode") or row.get("awayTeam_teamTricode"),
        "home_name": row.get("home_name") or row.get("homeTeam_teamName"),
        "away_name": row.get("away_name") or row.get("awayTeam_teamName"),
        "home_full_name": _team_full_name(
            row.get("home_city") or row.get("homeTeam_teamCity"),
            row.get("home_full_name") or row.get("home_name") or row.get("homeTeam_teamName"),
        ),
        "away_full_name": _team_full_name(
            row.get("away_city") or row.get("awayTeam_teamCity"),
            row.get("away_full_name") or row.get("away_name") or row.get("awayTeam_teamName"),
        ),
        "home_score": row.get("home_score", row.get("homeTeam_score")),
        "away_score": row.get("away_score", row.get("awayTeam_score")),
        "period": row.get("period", row.get("LIVE_PERIOD")),
        "clock": row.get("clock", row.get("LIVE_PC_TIME")),
        "postponed": str(row.get("postponedStatus") or "").lower() not in {"", "0", "none", "false"},
    }


def _int_id(value: object) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if not text.lstrip("-").isdigit():
        return None
    return int(text)


def preseason_start(games: list[dict]) -> str | None:
    starts = [
        game["start_utc"]
        for game in games
        if game.get("season_type") == "preseason" and game.get("start_utc")
    ]
    if not starts:
        return None
    return min(starts)


def match_game(event: dict, games: list[dict]) -> tuple[dict | None, str]:
    """Join on team ids, home/away, and start. Never on display strings."""
    event_start = _parse_time(event.get("start_utc"))
    home = _int_id(event.get("home_team_id"))
    away = _int_id(event.get("away_team_id"))
    if event_start is None or home is None or away is None:
        return None, "UNMATCHED"
    hits: list[dict] = []
    for game in games:
        if game.get("neutral") or game.get("postponed"):
            continue
        if _int_id(game.get("home_team_id")) != home or _int_id(game.get("away_team_id")) != away:
            continue
        game_start = _parse_time(game.get("start_utc"))
        if game_start is None:
            continue
        if abs(game_start - event_start) <= MATCH_WINDOW:
            hits.append(game)
    if len(hits) == 1:
        return hits[0], "MATCHED"
    if len(hits) > 1:
        return None, "AMBIGUOUS"
    return None, "UNMATCHED"


def match_canonical(game: dict, canonical_games: list[dict]) -> tuple[str | None, str]:
    if game.get("neutral"):
        return None, "NEUTRAL_UNMATCHED"
    found, status = match_game(game, canonical_games)
    if status == "MATCHED" and found is not None:
        internal = found.get("internal_game_id")
        if internal:
            return str(internal), "MATCHED"
        return None, "UNMATCHED"
    if status == "AMBIGUOUS":
        return None, "AMBIGUOUS"
    return None, "UNMATCHED"


def rows_from_schedule_frame(frame) -> list[dict]:
    """Map a ScheduleLeagueV2 SeasonGames frame without inventing rows."""
    if frame is None or getattr(frame, "empty", True):
        return []
    records = frame.to_dict(orient="records")
    games = []
    for row in records:
        game_id = game_id_text(row.get("gameId"))
        if not game_id or game_id == "0000000000":
            continue
        games.append(normalize_nba_game(row))
    return games


def overlay_scoreboard(games: list[dict], header) -> list[dict]:
    if header is None or getattr(header, "empty", True):
        return games
    by_id = {game["nba_game_id"]: dict(game) for game in games}
    for row in header.to_dict(orient="records"):
        game_id = game_id_text(row.get("GAME_ID"))
        current = by_id.get(game_id)
        if current is None:
            continue
        current["status"] = _status(row.get("GAME_STATUS_ID"))
        current["period"] = row.get("LIVE_PERIOD")
        current["clock"] = row.get("LIVE_PC_TIME")
        by_id[game_id] = current
    return list(by_id.values())


def fetch_nba_catalog(today: datetime, timeout: int = 12) -> dict:
    """Read scheduleleaguev2 and today's scoreboard. Failures stay unavailable."""
    season = current_nba_season(today)
    try:
        from nba_api.stats.endpoints import scheduleleaguev2, scoreboardv2
    except ImportError as exc:
        return {
            "status": "NBA_API_NOT_INSTALLED",
            "season": season,
            "preseason_start": None,
            "games": [],
            "detail": type(exc).__name__,
        }
    try:
        schedule = scheduleleaguev2.ScheduleLeagueV2(season=season, timeout=timeout)
        frames = schedule.get_data_frames()
        season_games = next((frame for frame in frames if "gameId" in getattr(frame, "columns", [])), None)
        games = rows_from_schedule_frame(season_games)
        board = scoreboardv2.ScoreboardV2(game_date=today.date().isoformat(), timeout=timeout)
        header = next((frame for frame in board.get_data_frames() if "GAME_ID" in getattr(frame, "columns", [])), None)
        games = overlay_scoreboard(games, header)
    except Exception as exc:  # noqa: BLE001 — network and schema failures stay unavailable
        return {
            "status": "NBA_ENDPOINT_UNAVAILABLE",
            "season": season,
            "preseason_start": None,
            "games": [],
            "detail": type(exc).__name__,
        }
    start = preseason_start(games)
    return {
        "status": "OK" if games else "EMPTY_SCHEDULE",
        "season": season,
        "preseason_start": start,
        "games": games,
        "detail": None if games else "schedule returned no games",
    }
