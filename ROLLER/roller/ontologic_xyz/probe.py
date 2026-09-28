"""Date probe for The Odds API. Events are free. Odds are requested only when a game is listed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from roller.ontologic_x.collector import LiveTransport
from roller.ontologic_x.markets import PRIMARY_BOOK
from roller.ontologic_x.sources import parse_odds_api

PRESEASON_SPORT = "basketball_nba_preseason"
REGULAR_SPORT = "basketball_nba"
EASTERN = ZoneInfo("America/New_York")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def probe_path(day: str) -> Path:
    return repo_root() / "research" / "ontologic_x" / "probes" / f"{day}.json"


def eastern_window(day: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(day).replace(tzinfo=EASTERN)
    return start, start + timedelta(days=1)


def _on_day(commence: object, start: datetime, end: datetime) -> bool:
    text = str(commence or "")
    if not text:
        return False
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return start <= stamp.astimezone(EASTERN) < end


def _sports_active(transport: LiveTransport) -> dict[str, bool | None]:
    payload, _headers = transport._get("https://api.the-odds-api.com/v4/sports", {"all": "true"})
    flags: dict[str, bool | None] = {PRESEASON_SPORT: None, REGULAR_SPORT: None}
    if not isinstance(payload, list):
        return flags
    for row in payload:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        if key in flags:
            flags[key] = bool(row.get("active"))
    return flags


def _events_on_day(transport: LiveTransport, sport: str, start: datetime, end: datetime) -> list[dict]:
    events, _headers = transport.events(sport)
    kept = []
    for event in events:
        if isinstance(event, dict) and _on_day(event.get("commence_time"), start, end):
            kept.append(
                {
                    "id": event.get("id"),
                    "home_team": event.get("home_team"),
                    "away_team": event.get("away_team"),
                    "commence_time": event.get("commence_time"),
                }
            )
    return kept


def _quotes(transport: LiveTransport, sport: str, start: datetime, end: datetime) -> tuple[list[dict], dict]:
    payload, headers = transport._get(
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
        {
            "bookmakers": PRIMARY_BOOK,
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "commenceTimeFrom": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commenceTimeTo": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    quotes, rejected = parse_odds_api(payload)
    return quotes, {"headers": headers, "rejected": rejected}


def probe_day(day: str, transport: LiveTransport | None = None) -> dict[str, Any]:
    """Look up one Eastern date. Skip the paid odds call when no event is listed."""
    client = transport or LiveTransport()
    start, end = eastern_window(day)
    active = _sports_active(client)
    sports: dict[str, Any] = {}
    quotes: list[dict] = []
    for sport in (PRESEASON_SPORT, REGULAR_SPORT):
        listed = _events_on_day(client, sport, start, end)
        row: dict[str, Any] = {
            "active": active.get(sport),
            "events": listed,
            "odds": "NOT_REQUESTED",
        }
        if listed:
            found, meta = _quotes(client, sport, start, end)
            row["odds"] = "OBSERVED" if found else "SOURCE_UNAVAILABLE"
            row["quota"] = meta["headers"]
            row["rejected"] = meta["rejected"]
            quotes.extend(found)
        sports[sport] = row
    status = "OBSERVED" if quotes else "SOURCE_UNAVAILABLE"
    body = {
        "date": day,
        "timezone": "America/New_York",
        "provider": "the_odds_api",
        "bookmaker": PRIMARY_BOOK,
        "other_books": "NOT_REQUESTED",
        "status": status,
        "sports": sports,
        "quotes": quotes,
        "live_execution": False,
        "submits": False,
        "note": "Empty boards are not priced. A missing quote is SOURCE_UNAVAILABLE.",
    }
    dest = probe_path(day)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return body
