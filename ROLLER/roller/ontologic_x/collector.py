"""One shared Odds API collector. Dashboards read the cache. William Hill only."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from roller.ontologic_x import LIVE_EXECUTION, METHOD
from roller.ontologic_x.governor import (
    PRIOR_PROBE,
    active_policy,
    authorize,
    illustrative_costs,
    latest_measurement,
    next_detailed_interval,
    spent_by_bucket,
    stamp,
)
from roller.ontologic_x.identity import MATCH_WINDOW, _parse_time
from roller.ontologic_x.markets import DISCOVERY_SPORTS, PRIMARY_BOOK, REHEARSAL_SPORT, requested_keys
from roller.ontologic_x.sources import DecimalAmerican, load_local_secrets
from roller.ontologic_x.store import Store

MOMENTS = ("pregame", "q2_open", "q2_mid", "halftime", "q3_open", "q3_mid")
SECRET_FILE = Path(__file__).resolve().parents[3] / ".env.ontologic"


def load_secrets() -> None:
    load_local_secrets(SECRET_FILE)


def plan_name() -> str:
    return os.environ.get("ONTOLOGIC_ODDS_PLAN") or "starter"


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def match_event(event: dict, games: list[dict]) -> tuple[dict | None, str]:
    """Match on schedule full name plus start. A different spelling stays unmatched."""
    home = _norm(event.get("home_team"))
    away = _norm(event.get("away_team"))
    start = _parse_time(event.get("commence_time"))
    if not home or not away or start is None:
        return None, "UNMATCHED"
    hits = []
    for game in games:
        if _norm(game.get("home_full_name")) != home or _norm(game.get("away_full_name")) != away:
            continue
        game_start = _parse_time(game.get("start_utc"))
        if game_start is None or abs(game_start - start) > MATCH_WINDOW:
            continue
        hits.append(game)
    if len(hits) == 1:
        return hits[0], "MATCHED"
    if len(hits) > 1:
        return None, "AMBIGUOUS"
    return None, "UNMATCHED"


def clock_seconds(clock: object) -> int | None:
    text = str(clock or "").strip()
    if ":" not in text:
        return None
    minutes, seconds = text.split(":", 1)
    if not minutes.isdigit() or not seconds.isdigit():
        return None
    return int(minutes) * 60 + int(seconds)


def due_moments(game_state: dict) -> list[str]:
    """Quarter moments require a period and clock. Tipoff time does not imply Q2 or Q3."""
    status = str(game_state.get("status") or "").lower()
    due: list[str] = []
    if status == "upcoming":
        due.append("pregame")
    period = game_state.get("period")
    seconds = clock_seconds(game_state.get("clock"))
    if period in {None, ""} or seconds is None:
        return due
    period_n = int(period)
    if period_n == 2 and seconds >= 11 * 60:
        due.append("q2_open")
    if period_n == 2 and 5 * 60 <= seconds <= 7 * 60:
        due.append("q2_mid")
    if status == "halftime" or (period_n == 2 and seconds == 0):
        due.append("halftime")
    if period_n == 3 and seconds >= 11 * 60:
        due.append("q3_open")
    if period_n == 3 and 5 * 60 <= seconds <= 7 * 60:
        due.append("q3_mid")
    return due


def william_hill_markets(payload: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for book in payload.get("bookmakers") or []:
        if str(book.get("key") or "") != PRIMARY_BOOK:
            continue
        for market in book.get("markets") or []:
            key = str(market.get("key") or "")
            if key:
                found[key] = market
    return found


def observed_lines_from_odds(payload: dict, *, event_id: str, nba_game_id: str | None, season_phase: str, retrieved_at: str) -> list[dict]:
    lines = []
    markets = william_hill_markets(payload)
    for key, market in markets.items():
        source_time = market.get("last_update")
        for outcome in market.get("outcomes") or []:
            lines.append(
                {
                    "recorded_at": retrieved_at,
                    "event_id": event_id,
                    "nba_game_id": nba_game_id,
                    "season_phase": season_phase,
                    "bookmaker": PRIMARY_BOOK,
                    "market_key": key,
                    "side": outcome.get("name"),
                    "line": outcome.get("point"),
                    "american": None if outcome.get("price") is None else DecimalAmerican(outcome.get("price")),
                    "source_updated_at": None if source_time is None else str(source_time),
                    "retrieved_at": retrieved_at,
                    "derivation": "OBSERVED",
                }
            )
    return lines


def _header_int(headers: dict, name: str) -> int | None:
    value = headers.get(name)
    if value is None or value == "":
        return None
    return int(value)


def _record_headers(store: Store, headers: dict, *, bucket: str, purpose: str, endpoint: str, season_phase: str, at: str) -> int:
    last = _header_int(headers, "x-requests-last") or 0
    store.add_credit(
        {
            "recorded_at": at,
            "bucket": bucket,
            "purpose": purpose,
            "endpoint": endpoint,
            "credits_last": last,
            "credits_used": _header_int(headers, "x-requests-used"),
            "credits_remaining": _header_int(headers, "x-requests-remaining"),
            "season_phase": season_phase,
        }
    )
    return last


def ensure_baseline(store: Store) -> None:
    if store.ledger():
        return
    store.add_credit({"recorded_at": stamp(), **PRIOR_PROBE})


def _coverage_rows(keys: tuple[str, ...], present: set[str], *, sport: str, event_id: str | None, nba_game_id: str | None, phase: str, at: str) -> list[dict]:
    return [
        {
            "recorded_at": at,
            "sport_key": sport,
            "event_id": event_id,
            "nba_game_id": nba_game_id,
            "season_phase": phase,
            "bookmaker": PRIMARY_BOOK,
            "market_key": key,
            "status": "AVAILABLE" if key in present else "UNAVAILABLE",
            "line_count": None,
        }
        for key in keys
    ]


def _discover_events(store: Store, transport, at: str) -> list[dict]:
    """Read both NBA sport keys. /events does not spend credits."""
    events: list[dict] = []
    for sport in DISCOVERY_SPORTS:
        sport_events, headers = transport.events(sport)
        store.save_raw(
            {
                "recorded_at": at,
                "endpoint": "events",
                "sport_key": sport,
                "event_id": None,
                "season_phase": "discovery",
                "body": sport_events,
            }
        )
        _record_headers(
            store,
            headers,
            bucket="coverage_debug",
            purpose="event_discovery",
            endpoint="events",
            season_phase="discovery",
            at=at,
        )
        for event in sport_events:
            events.append({**event, "sport_key": sport})
    return events


def rehearse(store: Store, transport, nba_games: list[dict], now: datetime) -> dict:
    """Free event discovery, then at most a few paid William Hill coverage calls."""
    if store.meta_get("rehearsal") == "done":
        return coverage_view(store, now)
    ensure_baseline(store)
    at = stamp(now)
    policy = active_policy(now.date(), plan_name())
    events = _discover_events(store, transport, at)
    matched = []
    for event in events:
        game, mapping = match_event(event, nba_games)
        phase = str(game.get("season_type")) if game is not None else "unmatched"
        matched.append(
            {
                "event_id": event.get("id"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "commence_time": event.get("commence_time"),
                "mapping": mapping,
                "nba_game_id": None if game is None else game.get("nba_game_id"),
                "season_phase": phase,
                "sport_key": event.get("sport_key") or REHEARSAL_SPORT,
                "game": game,
            }
        )
    preseason = [row for row in matched if row["season_phase"] == "preseason" and row["mapping"] == "MATCHED"]
    regular = [row for row in matched if row["season_phase"] == "regular" and row["mapping"] == "MATCHED"]
    keys = requested_keys(REHEARSAL_SPORT)
    if preseason:
        _cover_events(store, transport, preseason[:3], keys, "preseason", policy, now)
        for row in preseason[:3]:
            for moment in MOMENTS:
                store.save_plan(
                    {
                        "event_id": row["event_id"],
                        "moment": moment,
                        "nba_game_id": row["nba_game_id"],
                        "season_phase": "preseason",
                        "status": "PLANNED",
                    }
                )
    else:
        for cell in _coverage_rows(keys, set(), sport=REHEARSAL_SPORT, event_id=None, nba_game_id=None, phase="preseason", at=at):
            store.add_coverage(cell)
        if regular:
            _cover_events(store, transport, regular[:1], keys, "regular", policy, now)
    store.meta_set("rehearsal", "done")
    store.meta_set("preseason_listed", "true" if preseason else "false")
    _write_board(store, matched, nba_games, now)
    return coverage_view(store, now)


def _cover_events(store: Store, transport, rows: list[dict], keys: tuple[str, ...], phase: str, policy: dict, now: datetime) -> None:
    for row in rows:
        allowed, _reason = authorize(store.ledger(), "coverage_debug", 1, policy)
        if not allowed:
            return
        at = stamp(now)
        sport_key = str(row.get("sport_key") or REHEARSAL_SPORT)
        payload, headers = transport.event_markets(sport_key, str(row["event_id"]))
        store.save_raw(
            {
                "recorded_at": at,
                "endpoint": "event_markets",
                "sport_key": sport_key,
                "event_id": row["event_id"],
                "season_phase": phase,
                "body": payload,
            }
        )
        _record_headers(
            store,
            headers,
            bucket="coverage_debug",
            purpose="market_discovery",
            endpoint="event_markets",
            season_phase=phase,
            at=at,
        )
        present = set(william_hill_markets(payload if isinstance(payload, dict) else {}))
        for cell in _coverage_rows(
            keys,
            present,
            sport=REHEARSAL_SPORT,
            event_id=row["event_id"],
            nba_game_id=row.get("nba_game_id"),
            phase=phase,
            at=at,
        ):
            store.add_coverage(cell)
        if phase != "preseason" or not present:
            continue
        estimate = len(("h2h", "spreads", "totals"))
        allowed, _reason = authorize(store.ledger(), "preseason_snapshots", estimate, policy)
        if not allowed:
            continue
        odds, odds_headers = transport.event_odds(sport_key, str(row["event_id"]), ("h2h", "spreads", "totals"))
        odds_at = stamp(now)
        store.save_raw(
            {
                "recorded_at": odds_at,
                "endpoint": "event_odds",
                "sport_key": sport_key,
                "event_id": row["event_id"],
                "season_phase": phase,
                "body": odds,
            }
        )
        _record_headers(
            store,
            odds_headers,
            bucket="preseason_snapshots",
            purpose="pregame_featured",
            endpoint="event_odds",
            season_phase=phase,
            at=odds_at,
        )
        for line in observed_lines_from_odds(
            odds if isinstance(odds, dict) else {},
            event_id=str(row["event_id"]),
            nba_game_id=row.get("nba_game_id"),
            season_phase=phase,
            retrieved_at=odds_at,
        ):
            store.add_observed_line(line)


def refresh_listing(store: Store, transport, nba_games: list[dict], now: datetime) -> dict:
    """Re-read the free event list until preseason is actually listed. Paid calls stay inside the governor."""
    if store.meta_get("preseason_listed") == "true":
        return {"checked": False, "found": 0}
    if not any(game.get("home_full_name") for game in nba_games):
        return {"checked": False, "found": 0, "reason": "NBA_NAMES_UNAVAILABLE"}
    at = stamp(now)
    events = _discover_events(store, transport, at)
    covered = {cell.get("event_id") for cell in store.coverage_cells() if cell.get("event_id")}
    found = []
    for event in events:
        game, mapping = match_event(event, nba_games)
        if mapping != "MATCHED" or game is None or game.get("season_type") != "preseason":
            continue
        if event.get("id") in covered:
            continue
        found.append(
            {
                "event_id": event.get("id"),
                "nba_game_id": game.get("nba_game_id"),
                "season_phase": "preseason",
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "commence_time": event.get("commence_time"),
                "mapping": mapping,
                "sport_key": event.get("sport_key") or REHEARSAL_SPORT,
            }
        )
    if not found:
        return {"checked": True, "found": 0}
    policy = active_policy(now.date(), plan_name())
    _cover_events(store, transport, found[:3], requested_keys(REHEARSAL_SPORT), "preseason", policy, now)
    for row in found[:3]:
        for moment in MOMENTS:
            store.save_plan(
                {
                    "event_id": row["event_id"],
                    "moment": moment,
                    "nba_game_id": row["nba_game_id"],
                    "season_phase": "preseason",
                    "status": "PLANNED",
                }
            )
    store.meta_set("preseason_listed", "true")
    return {"checked": True, "found": len(found[:3])}


def consider_moments(store: Store, states: list[dict], transport, now: datetime) -> dict:
    """Spend snapshot credits only for a due preseason moment that was planned."""
    policy = active_policy(now.date(), plan_name())
    if os.environ.get("ONTOLOGIC_COLLECT_SNAPSHOTS") != "1":
        return {"collected": [], "reason": "SNAPSHOTS_HELD", "interval_seconds": next_detailed_interval(store.ledger(), policy, 1)}
    collected = []
    plans = {(row["event_id"], row["moment"]): row for row in store.plans()}
    keys = requested_keys(REHEARSAL_SPORT)
    for state in states:
        if state.get("season_phase") != "preseason":
            continue
        for moment in due_moments(state):
            if moment == "pregame":
                continue
            event_id = str(state.get("event_id") or "")
            planned = plans.get((event_id, moment))
            if planned is None or planned.get("status") == "COLLECTED":
                continue
            allowed, reason = authorize(store.ledger(), "preseason_snapshots", len(keys), policy)
            if not allowed:
                return {"collected": collected, "reason": reason, "interval_seconds": None}
            sport_key = str(state.get("sport_key") or REHEARSAL_SPORT)
            payload, headers = transport.event_odds(sport_key, event_id, keys)
            at = stamp(now)
            store.save_raw(
                {
                    "recorded_at": at,
                    "endpoint": "event_odds",
                    "sport_key": sport_key,
                    "event_id": event_id,
                    "season_phase": "preseason",
                    "body": payload,
                }
            )
            _record_headers(
                store,
                headers,
                bucket="preseason_snapshots",
                purpose=moment,
                endpoint="event_odds",
                season_phase="preseason",
                at=at,
            )
            for line in observed_lines_from_odds(
                payload if isinstance(payload, dict) else {},
                event_id=event_id,
                nba_game_id=state.get("nba_game_id"),
                season_phase="preseason",
                retrieved_at=at,
            ):
                store.add_observed_line(line)
            store.save_plan({**planned, "status": "COLLECTED"})
            collected.append(moment)
    return {"collected": collected, "reason": "OK", "interval_seconds": next_detailed_interval(store.ledger(), policy, len(keys))}


def _write_board(store: Store, matched: list[dict], nba_games: list[dict], now: datetime) -> None:
    """Keep a scheduled game when William Hill has not posted a price."""
    listed = store.meta_get("preseason_listed") == "true"
    by_event = {str(row.get("event_id")): row for row in matched}
    by_nba = {str(game.get("nba_game_id")): game for game in nba_games if game.get("nba_game_id")}
    grouped: dict[str, list[dict]] = {}
    for line in store.observed_lines():
        grouped.setdefault(str(line.get("event_id")), []).append(line)
    rows = []
    seen_games: set[str] = set()
    for event_id, event_lines in grouped.items():
        event = by_event.get(event_id, {})
        game = by_nba.get(str(event.get("nba_game_id") or event_lines[0].get("nba_game_id") or ""))
        rows.append(_quoted_row(event, game, event_lines))
        if game and game.get("nba_game_id"):
            seen_games.add(str(game["nba_game_id"]))
    for event in matched:
        event_id = str(event.get("event_id") or "")
        if event_id in grouped:
            continue
        game = by_nba.get(str(event.get("nba_game_id") or ""))
        rows.append(_scheduled_row(event, game))
        if game and game.get("nba_game_id"):
            seen_games.add(str(game["nba_game_id"]))
    for game in nba_games:
        game_id = str(game.get("nba_game_id") or "")
        if game.get("season_type") != "preseason" or not game_id or game_id in seen_games:
            continue
        rows.append(_scheduled_row({}, game))
        seen_games.add(game_id)
    preseason_games = [game for game in nba_games if game.get("season_type") == "preseason" and game.get("start_utc")]
    starts = [game.get("start_utc") for game in preseason_games]
    body = {
        "snapshot_id": f"coverage-{at_compact(now)}",
        "retrieved_at": stamp(now),
        "method": METHOD,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "source_label": "SOURCE_UNAVAILABLE",
        "mode": "ODDS_API",
        "cadence_label": "PROVIDER_CADENCE_NOT_5S",
        "preseason_start": min(starts) if starts else None,
        "preseason_start_source": "NBA_SCHEDULE" if starts else "UNAVAILABLE",
        "empty_state": "PRESEASON_NOT_LISTED" if not listed else "WILLIAM_HILL_ABSENT",
        "games": rows,
    }
    store.save_snapshot(body["snapshot_id"], now, body, {})


def merge_unquoted_schedule(store: Store, nba_games: list[dict], now: datetime) -> None:
    """Add NBA preseason games that have no stored price. Do not drop a quoted row."""
    body = store.current_body()
    if body is None:
        _write_board(store, [], nba_games, now)
        return
    rows = list(body.get("games") or [])
    seen = {str(row.get("id")) for row in rows}
    added = False
    for game in nba_games:
        game_id = str(game.get("nba_game_id") or "")
        if game.get("season_type") != "preseason" or not game_id or game_id in seen:
            continue
        rows.append(_scheduled_row({}, game))
        seen.add(game_id)
        added = True
    if not added:
        return
    updated = dict(body)
    updated["games"] = rows
    updated["snapshot_id"] = f"coverage-{at_compact(now)}"
    updated["retrieved_at"] = stamp(now)
    store.save_snapshot(updated["snapshot_id"], now, updated, {})


def _scheduled_row(event: dict, game: dict | None) -> dict:
    home = (game or {}).get("home_tricode") or event.get("home_team") or "HOME"
    away = (game or {}).get("away_tricode") or event.get("away_team") or "AWAY"
    phase = str((game or {}).get("season_type") or event.get("season_phase") or "")
    return {
        "id": (game or {}).get("nba_game_id") or event.get("event_id"),
        "matchup": f"{away} @ {home}",
        "start_utc": (game or {}).get("start_utc") or event.get("commence_time"),
        "status": (game or {}).get("status") or "upcoming",
        "score": None,
        "period": (game or {}).get("period") or None,
        "clock": (game or {}).get("clock") or None,
        "bookmaker": None,
        "source_label": "SCHEDULED",
        "mapping": event.get("mapping") or ("NBA_SCHEDULE" if game else "UNMATCHED"),
        "season_phase": phase,
        "coverage": "UNAVAILABLE",
        "empty_state": "NO_POSTED_ODDS",
        "moneyline": None,
        "main_spread": None,
        "main_total": None,
        "freshness": {"source_time_label": "SOURCE_TIME_UNAVAILABLE"},
        "observed_lines": [],
    }


def _quoted_row(event: dict, game: dict | None, lines: list[dict]) -> dict:
    home = (game or {}).get("home_tricode") or event.get("home_team") or "HOME"
    away = (game or {}).get("away_tricode") or event.get("away_team") or "AWAY"
    phase = str((game or {}).get("season_type") or event.get("season_phase") or lines[0].get("season_phase") or "")
    return {
        "id": (game or {}).get("nba_game_id") or event.get("event_id") or lines[0].get("event_id"),
        "matchup": f"{away} @ {home}",
        "start_utc": (game or {}).get("start_utc") or event.get("commence_time"),
        "status": (game or {}).get("status") or "upcoming",
        "score": None,
        "period": (game or {}).get("period") or None,
        "clock": (game or {}).get("clock") or None,
        "bookmaker": "williamhill",
        "source_label": "williamhill",
        "mapping": event.get("mapping") or "UNMATCHED",
        "season_phase": phase,
        "coverage": ", ".join(sorted({str(line.get("market_key")) for line in lines if line.get("market_key")})),
        "empty_state": None,
        "moneyline": _market_from_lines(lines, "h2h"),
        "main_spread": _market_from_lines(lines, "spreads"),
        "main_total": _market_from_lines(lines, "totals"),
        "freshness": {
            "source_time_label": next(
                (str(line["source_updated_at"]) for line in lines if line.get("source_updated_at")),
                "SOURCE_TIME_UNAVAILABLE",
            )
        },
        "observed_lines": lines,
    }


def _market_from_lines(lines: list[dict], market_key: str) -> dict | None:
    chosen = [line for line in lines if line.get("market_key") == market_key and line.get("derivation") == "OBSERVED"]
    if not chosen:
        return None
    return {
        "market_family": market_key,
        "normalized": [
            {
                "side": line.get("side"),
                "american": line.get("american"),
                "display_percent": None,
                "source_updated_at": line.get("source_updated_at"),
            }
            for line in chosen
        ],
    }


def at_compact(now: datetime) -> str:
    return stamp(now).replace("-", "").replace(":", "")


def coverage_view(store: Store, now: datetime | None = None) -> dict:
    moment = now or datetime.now(timezone.utc)
    policy = active_policy(moment.date(), plan_name())
    rows = store.ledger()
    cells = store.coverage_cells()
    spent = spent_by_bucket(rows)
    measured = latest_measurement(rows)
    by_phase: dict[str, dict[str, str]] = {}
    for cell in cells:
        phase = str(cell["season_phase"])
        key = str(cell["market_key"])
        current = by_phase.setdefault(phase, {})
        if cell["status"] == "AVAILABLE" or key not in current:
            current[key] = str(cell["status"])
    return {
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "bookmaker": PRIMARY_BOOK,
        "other_books": "NOT_REQUESTED",
        "policy": policy,
        "measured": measured,
        "spent": spent,
        "buckets": {
            name: {"allowance": allowance, "spent": spent.get(name, 0), "remaining": allowance - spent.get(name, 0)}
            for name, allowance in policy["buckets"].items()
        },
        "preseason_listed": store.meta_get("preseason_listed") == "true",
        "coverage": by_phase,
        "plans": store.plans(),
        "observed_line_count": len(store.observed_lines()),
        "snapshot_collection": "HELD" if os.environ.get("ONTOLOGIC_COLLECT_SNAPSHOTS") != "1" else "ARMED",
        "detailed_interval_seconds": next_detailed_interval(rows, policy, 1),
        "illustrative_costs": illustrative_costs(),
        "quoted_versus_modeled": "Stored lines are OBSERVED sportsbook prices. Fair probabilities are not quotes.",
    }


class LiveTransport:
    """Server-side Odds API client. The key stays in the process environment."""

    def __init__(self) -> None:
        load_secrets()
        self.key = os.environ.get("ONTOLOGIC_ODDS_API_KEY") or ""

    def events(self, sport: str) -> tuple[list, dict]:
        payload, headers = self._get(f"https://api.the-odds-api.com/v4/sports/{sport}/events", {})
        return payload if isinstance(payload, list) else [], headers

    def event_markets(self, sport: str, event_id: str) -> tuple[dict, dict]:
        payload, headers = self._get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/markets",
            {"bookmakers": PRIMARY_BOOK, "regions": "uk"},
        )
        return payload if isinstance(payload, dict) else {}, headers

    def event_odds(self, sport: str, event_id: str, markets: tuple[str, ...]) -> tuple[dict, dict]:
        payload, headers = self._get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds",
            {
                "bookmakers": PRIMARY_BOOK,
                "regions": "uk",
                "markets": ",".join(markets),
                "oddsFormat": "american",
            },
        )
        return payload if isinstance(payload, dict) else {}, headers

    def _get(self, url: str, query: dict) -> tuple[object, dict]:
        if not self.key:
            raise RuntimeError("ODDS_API_KEY_MISSING")
        params = {"apiKey": self.key, "dateFormat": "iso", **query}
        request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
        with urllib.request.urlopen(request, timeout=20) as response:
            headers = {key.lower(): value for key, value in response.headers.items() if key.lower().startswith("x-requests")}
            payload = json.loads(response.read().decode("utf-8"), parse_int=str, parse_float=str)
        return payload, headers
