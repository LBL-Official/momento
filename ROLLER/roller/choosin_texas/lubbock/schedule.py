"""Rank warehouse-covered games before any FIRST80 filter."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from roller.choosin_texas.lubbock.stats import equal_count_bounds, progress

NY = ZoneInfo("America/New_York")
UTC = timezone.utc

REGULAR = {"REGULAR_SEASON"}
PRESEASON = {"PRESEASON"}
POSTSEASON = {"PLAYOFFS", "PLAY_IN", "FINALS", "NCAA_TOURNAMENT", "OTHER_POSTSEASON"}

WAREHOUSE = {
    "NBA": "NBA/2025-2026/warehouse/normalized/nba/games/nba_games.json",
    "NCAAB": "NCAAB/2025-2026/warehouse/normalized/ncaab/games/ncaab_games.json",
    "WNBA": "WNBA/2025-2026/warehouse/normalized/wnba/games/wnba_games.json",
    "MLB": "MLB/2025-2026/warehouse/normalized/mlb/games/mlb_games.json",
}

CANONICAL = {
    "NBA": ("data/nba/2025_2026/canonical/games.csv",),
    "NCAAB": ("data/ncaab/2025_2026/canonical/games.csv",),
    "WNBA": ("data/wnba/2025/canonical/games.csv", "data/wnba/2026/canonical/games.csv"),
    "MLB": ("data/mlb/2025_2026/canonical/games.csv",),
}


@dataclass
class RankedGame:
    sport: str
    season_id: str
    source_season: str
    phase: str
    raw_phase: str
    event_ticker: str
    internal_game_id: str
    game_date: str
    league_local_date: str
    start_basis: str
    event_status: str
    game_rank: int
    g: int
    season_progress: str
    decile: int
    quintile: int
    p5_vs_p5: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def roller_root() -> Path:
    return Path(__file__).resolve().parents[3]


def phase_of(raw: str) -> str:
    if raw in REGULAR:
        return "REGULAR_SEASON"
    if raw in PRESEASON:
        return "PRESEASON"
    if raw in POSTSEASON:
        return "POSTSEASON"
    return f"OTHER_{raw or 'BLANK'}"


def season_of(sport: str, source_season: str, game_date: str) -> str:
    if sport in {"WNBA", "MLB"}:
        return (game_date or "")[:4]
    return source_season or "UNAVAILABLE"


def _is_real_clock(stamp: datetime | None, game_date: str) -> bool:
    """Midnight on the stored game date is the date fallback, not a tip time."""
    if stamp is None or not game_date:
        return False
    as_utc = stamp.astimezone(UTC)
    if as_utc.hour or as_utc.minute or as_utc.second:
        return True
    return as_utc.date().isoformat() != game_date


def _parse_utc(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _load_canonical(sport: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for relative in CANONICAL[sport]:
        path = roller_root() / relative
        if not path.exists():
            continue
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = (row.get("event_ticker") or "").strip()
                if not ticker:
                    continue
                found[ticker] = row
    return found


def _load_warehouse(sport: str) -> list[dict]:
    path = repo_root() / "Backtesting Suite" / "Data" / WAREHOUSE[sport]
    return json.loads(path.read_text())


def rank_sport(sport: str) -> tuple[list[RankedGame], dict[str, int]]:
    canonical = _load_canonical(sport)
    warehouse = _load_warehouse(sport)
    notes = {
        "warehouse_rows": len(warehouse),
        "canonical_tickers": len(canonical),
        "collapsed_duplicates": 0,
        "excluded_not_p5": 0,
        "p5_unverified": 0,
        "missing_internal_game_id": 0,
        "start_actual": 0,
        "start_scheduled": 0,
        "start_game_date": 0,
    }
    prepared: list[dict] = []
    for row in warehouse:
        ticker = (row.get("event_ticker") or "").strip()
        if not ticker:
            continue
        canon = canonical.get(ticker) or {}
        p5 = (canon.get("p5_vs_p5") or "").strip()
        if sport == "NCAAB":
            if not canon:
                notes["p5_unverified"] += 1
                continue
            if p5 != "1":
                notes["excluded_not_p5"] += 1
                continue
        game_date = (row.get("game_date") or canon.get("game_date") or "").strip()
        actual = _parse_utc(canon.get("actual_start") or "")
        scheduled = _parse_utc(row.get("scheduled_start") or "") or _parse_utc(canon.get("scheduled_start") or "")
        if not _is_real_clock(actual, game_date):
            actual = None
        if not _is_real_clock(scheduled, game_date):
            scheduled = None
        if actual is not None:
            basis = "actual_start"
            stamp = actual
            notes["start_actual"] += 1
        elif scheduled is not None:
            basis = "scheduled_start"
            stamp = scheduled
            notes["start_scheduled"] += 1
        else:
            basis = "game_date"
            stamp = _parse_utc(f"{game_date}T00:00:00Z") if game_date else None
            notes["start_game_date"] += 1
        internal = (canon.get("internal_game_id") or "").strip()
        if not internal:
            notes["missing_internal_game_id"] += 1
            internal = ticker
        if basis == "game_date" or stamp is None:
            local_date = game_date
        else:
            local_date = stamp.astimezone(NY).date().isoformat()
        sort_stamp = stamp.isoformat() if stamp is not None else f"{game_date}T00:00:00+00:00"
        prepared.append(
            {
                "sport": sport,
                "season_id": season_of(sport, str(row.get("season") or ""), game_date),
                "source_season": str(row.get("season") or ""),
                "phase": phase_of(str(row.get("season_phase") or "")),
                "raw_phase": str(row.get("season_phase") or ""),
                "event_ticker": ticker,
                "internal_game_id": internal,
                "game_date": game_date,
                "league_local_date": local_date,
                "start_basis": basis,
                "event_status": str(row.get("event_status") or ""),
                "sort_stamp": sort_stamp,
                "p5_vs_p5": p5 if sport == "NCAAB" else "",
            }
        )
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in prepared:
        grouped[(row["season_id"], row["phase"])].append(row)
    ranked: list[RankedGame] = []
    for (season_id, phase), rows in grouped.items():
        rows.sort(key=lambda item: (item["sort_stamp"], item["internal_game_id"].encode("utf-8")))
        kept: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            key = row["internal_game_id"]
            if key in seen:
                notes["collapsed_duplicates"] += 1
                continue
            seen.add(key)
            kept.append(row)
        total = len(kept)
        deciles = {rank: bucket for bucket, lo, hi in equal_count_bounds(total, 10) for rank in range(lo, hi + 1)}
        quintiles = {rank: bucket for bucket, lo, hi in equal_count_bounds(total, 5) for rank in range(lo, hi + 1)}
        for index, row in enumerate(kept, start=1):
            ranked.append(
                RankedGame(
                    sport=sport,
                    season_id=season_id,
                    source_season=row["source_season"],
                    phase=phase,
                    raw_phase=row["raw_phase"],
                    event_ticker=row["event_ticker"],
                    internal_game_id=row["internal_game_id"],
                    game_date=row["game_date"],
                    league_local_date=row["league_local_date"],
                    start_basis=row["start_basis"],
                    event_status=row["event_status"],
                    game_rank=index,
                    g=total,
                    season_progress=progress(index, total),
                    decile=deciles[index],
                    quintile=quintiles[index],
                    p5_vs_p5=row["p5_vs_p5"],
                )
            )
    return ranked, notes


def rank_all() -> tuple[list[RankedGame], dict[str, dict[str, int]]]:
    games: list[RankedGame] = []
    notes: dict[str, dict[str, int]] = {}
    for sport in ("NBA", "NCAAB", "WNBA", "MLB"):
        sport_games, sport_notes = rank_sport(sport)
        games.extend(sport_games)
        notes[sport] = sport_notes
    return games, notes
