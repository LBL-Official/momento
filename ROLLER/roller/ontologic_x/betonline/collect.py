"""Collect BetOnline NBA quotes into the Ontologic X store. Does not submit orders."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from roller.ontologic_x import LIVE_EXECUTION, METHOD
from roller.ontologic_x.betonline import BOOKMAKER, SOURCE_URL, event_url
from roller.ontologic_x.betonline.client import Client, CollectionBlocked, CollectionFailed
from roller.ontologic_x.betonline.parse import iter_league_games, parse_bundle
from roller.ontologic_x.collector import match_event
from roller.ontologic_x.pairing import pair_quotes
from roller.ontologic_x.sources import cadence_for
from roller.ontologic_x.store import Store, utc_stamp

QUARTERS = ("Q1", "Q2", "Q3", "Q4")
_COLLECT_LOCK = threading.Lock()
_WORKERS = 4


def interval_seconds() -> int:
    _seconds, _label = cadence_for("BETONLINE")
    return _seconds


def collect(store: Store, client, nba_games: list[dict], now: datetime) -> dict:
    """One cycle. A blocked league read keeps the previous snapshot. One event failure does not."""
    if not _COLLECT_LOCK.acquire(blocking=False):
        return {"status": "ALREADY_RUNNING", "kept_snapshot": True, "bookmaker": BOOKMAKER}
    owner = f"betonline-{os.getpid()}"
    try:
        if not store.try_acquire(owner, now, ttl_seconds=max(180, interval_seconds())):
            return {"status": "ALREADY_RUNNING", "kept_snapshot": True, "bookmaker": BOOKMAKER}
        try:
            return _collect_locked(store, client, nba_games, now)
        finally:
            store.release(owner)
    finally:
        _COLLECT_LOCK.release()


def _collect_locked(store: Store, client, nba_games: list[dict], now: datetime) -> dict:
    at = utc_stamp(now)
    try:
        league = client.league(0)
        games = iter_league_games(league)
    except CollectionBlocked as exc:
        return _fail(store, now, exc.reason, nba_games, status=exc.status)
    except CollectionFailed as exc:
        return _fail(store, now, exc.reason, nba_games, detail=exc.detail)
    store.save_raw(
        {
            "recorded_at": at,
            "endpoint": "betonline_offering_by_league",
            "sport_key": "basketball_nba",
            "event_id": None,
            "season_phase": "nba",
            "body": {"bookmaker": BOOKMAKER, "source_url": SOURCE_URL, "payload": league},
        }
    )
    try:
        inspections = _inspect_events(client, games)
    except CollectionBlocked as exc:
        return _fail(store, now, exc.reason, nba_games, status=exc.status)
    records: list[dict] = []
    coverages: list[dict] = []
    failed_ids: set[str] = set()
    for inspection in inspections:
        game = inspection["game"]
        game_id = str(game.get("GameId"))
        event = inspection["event"]
        linked = inspection["linked"]
        event_ok = inspection["event_error"] is None
        linked_ok = inspection["linked_error"] is None
        if event is not None:
            store.save_raw(
                {
                    "recorded_at": at,
                    "endpoint": "betonline_get_event",
                    "sport_key": "basketball_nba",
                    "event_id": game_id,
                    "season_phase": "nba",
                    "body": {"bookmaker": BOOKMAKER, "source_url": event_url(game_id), "payload": event},
                }
            )
        if linked is not None:
            store.save_raw(
                {
                    "recorded_at": at,
                    "endpoint": "betonline_get_linked_events",
                    "sport_key": "basketball_nba",
                    "event_id": game_id,
                    "season_phase": "nba",
                    "body": {"bookmaker": BOOKMAKER, "source_url": event_url(game_id), "payload": linked},
                }
            )
        if not event_ok:
            failed_ids.add(game_id)
            coverage = {
                "provider_event_id": game_id,
                "source_url": event_url(game_id),
                "groups_discovered": ["game_lines", "linked_periods", "team_totals", "alternates", "player_props"],
                "groups_fetched": ["linked_periods"] if linked_ok else [],
                "markets_parsed": 0,
                "unmapped_count": 0,
                "failures": [f"FETCH_FAILED:{inspection['event_error']}"],
                "status": "FETCH_FAILED",
            }
            coverages.append(coverage)
            store.save_event_coverage({**coverage, "bookmaker": BOOKMAKER, "recorded_at": at, "observed_at": at})
            continue
        parsed, coverage = parse_bundle(game, event, linked, event_ok=True, linked_ok=linked_ok)
        for record in parsed:
            record["observed_at"] = at
            if linked_ok or record.get("market_family") not in {"period", "player_prop"}:
                record["last_seen_at"] = at
        if linked_ok:
            _mark_absent(store, game_id, parsed, nba_games, at)
            records.extend(parsed)
        else:
            failed_ids.add(f"partial:{game_id}")
            records.extend(
                row
                for row in parsed
                if row.get("status") not in {"COVERAGE_INCOMPLETE", "FETCH_FAILED"} and row.get("market_family") != "period"
            )
        coverages.append(coverage)
        store.save_event_coverage({**coverage, "bookmaker": BOOKMAKER, "recorded_at": at, "observed_at": at})
    inserted = _persist(store, records, nba_games, at)
    poll_id = store.record_poll(now, "betonline", True, "BETONLINE", "ok" if not failed_ids else "PARTIAL")
    body = _board(records, nba_games, now, empty_state=None, failed_ids=failed_ids, coverages=coverages, previous=store.current_body())
    body["snapshot_id"] = f"betonline-{poll_id}"
    store.save_snapshot(body["snapshot_id"], now, body, _states(records, at))
    store.meta_set("betonline_last_success_at", at)
    store.meta_set("betonline_last_error", "" if not failed_ids else "PARTIAL")
    categories: dict[str, int] = {}
    for row in records:
        if row.get("american") is None and row.get("status") == "MARKET_NOT_OFFERED":
            continue
        categories[str(row.get("market_family"))] = categories.get(str(row.get("market_family")), 0) + 1
    return {
        "status": "OBSERVED" if not failed_ids else "PARTIAL",
        "games": len({row["provider_event_id"] for row in records} | failed_ids),
        "events_inspected": len(inspections),
        "events_failed": len(failed_ids),
        "inserted": inserted,
        "retrieved_at": at,
        "bookmaker": BOOKMAKER,
        "unmapped": sum(coverage.get("unmapped_count") or 0 for coverage in coverages),
        "failures": [failure for coverage in coverages for failure in coverage.get("failures") or []],
        "by_category": categories,
        "groups_fetched": sorted({group for coverage in coverages for group in coverage.get("groups_fetched") or []}),
    }


def _inspect_events(client, games: list[dict]) -> list[dict]:
    if not games:
        return []

    def one(game: dict) -> dict:
        game_id = int(game["GameId"])
        event = None
        linked = None
        event_error = None
        linked_error = None
        try:
            event = client.event(game_id)
        except CollectionBlocked:
            raise
        except CollectionFailed as exc:
            event_error = exc.detail
        except AttributeError:
            event_error = "EVENT_UNAVAILABLE"
        try:
            linked = client.linked_events(game_id)
        except CollectionBlocked:
            raise
        except CollectionFailed as exc:
            linked_error = exc.detail
        except AttributeError:
            linked_error = "LINKED_UNAVAILABLE"
        return {
            "game": game,
            "event": event,
            "linked": linked,
            "event_error": event_error,
            "linked_error": linked_error,
        }

    inspections: list[dict] = []
    workers = 1 if len(games) == 1 else min(_WORKERS, len(games))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, game) for game in games]
        for future in as_completed(futures):
            inspections.append(future.result())
    return inspections


def _fail(store: Store, now: datetime, reason: str, nba_games: list[dict], status: int | None = None, detail: str | None = None) -> dict:
    store.meta_set("betonline_last_error", reason if detail is None else f"{reason}:{detail}"[:240])
    poll_id = store.record_poll(now, "betonline", False, "BETONLINE", reason)
    if store.current_body() is not None:
        return {"status": reason, "kept_snapshot": True, "http_status": status}
    body = _board([], nba_games, now, empty_state=reason)
    body["snapshot_id"] = f"betonline-{poll_id}"
    store.save_snapshot(body["snapshot_id"], now, body, {})
    return {"status": reason, "kept_snapshot": False, "http_status": status}


def _identity(record: dict) -> tuple:
    return (
        str(record.get("period")),
        str(record.get("market_family")),
        "" if record.get("market_name") is None else str(record.get("market_name")),
        "" if record.get("participant") is None else str(record.get("participant")),
        str(record.get("side")),
        "" if record.get("line") is None else str(record.get("line")),
    )


def _mark_absent(store: Store, game_id: str, records: list[dict], nba_games: list[dict], at: str) -> None:
    """A market missing from a complete snapshot is absent now. History stays."""
    present = {_identity(record) for record in records}
    sample = records[0] if records else {"provider_event_id": game_id, "home_team": None, "away_team": None}
    canonical = {"spread": "Spread", "moneyline": "Moneyline", "total": "Total", "alternate": "Alternate"}
    for previous in store.latest_event_quotes(BOOKMAKER, game_id):
        named = dict(previous)
        if not named.get("market_name") and named.get("market_family") in canonical:
            named["market_name"] = canonical[str(named.get("market_family"))]
        key = _identity(named)
        if key in present or previous.get("status") == "MARKET_NOT_OFFERED":
            continue
        absent = {
            **sample,
            "provider_event_id": game_id,
            "period": previous.get("period"),
            "market_family": previous.get("market_family"),
            "market_name": previous.get("market_name"),
            "participant": previous.get("participant"),
            "side": previous.get("side"),
            "line": previous.get("line"),
            "status": "MARKET_NOT_OFFERED",
            "american": None,
            "decimal_odds": None,
            "implied": None,
            "source_updated_at": None,
            "observed_at": at,
            "last_seen_at": at,
            "bookmaker": BOOKMAKER,
        }
        records.append(absent)


def _persist(store: Store, records: list[dict], nba_games: list[dict], at: str) -> int:
    inserted = 0
    for record in records:
        game, mapping = match_event(
            {
                "home_team": record.get("home_team"),
                "away_team": record.get("away_team"),
                "commence_time": record.get("wager_cutoff") or record.get("start_utc"),
            },
            nba_games,
        )
        phase = str(game.get("season_type")) if game is not None and mapping == "MATCHED" else "UNMATCHED"
        nba_game_id = None if game is None or mapping != "MATCHED" else game.get("nba_game_id")
        nba_start = None if game is None else game.get("start_utc")
        stored = {
            **record,
            "recorded_at": at,
            "retrieved_at": at,
            "observed_at": record.get("observed_at") or at,
            "last_seen_at": record.get("last_seen_at") or at,
            "nba_game_id": nba_game_id,
            "nba_start_utc": nba_start,
            "season_phase": phase,
            "body": {
                "bookmaker": BOOKMAKER,
                "no_vig_status": record.get("no_vig_status"),
                "no_vig_probability": record.get("no_vig_probability"),
                "no_vig_method": record.get("no_vig_method"),
                "source_decimal": record.get("source_decimal"),
                "decimal_discrepancy": record.get("decimal_discrepancy"),
                "market_id": record.get("market_id"),
                "outcome_id": record.get("outcome_id"),
                "raw_market": record.get("raw_market"),
            },
        }
        if store.add_book_quote(stored):
            inserted += 1
            if record.get("status") == "open" and record.get("american") is not None:
                store.add_observed_line(
                    {
                        "recorded_at": at,
                        "event_id": record["provider_event_id"],
                        "nba_game_id": nba_game_id,
                        "season_phase": phase,
                        "bookmaker": BOOKMAKER,
                        "market_key": f"{record['period']}:{record['market_family']}:{record.get('market_name')}:{record.get('line')}",
                        "side": record["side"],
                        "line": record.get("line"),
                        "american": record.get("american"),
                        "source_updated_at": None,
                        "retrieved_at": at,
                        "derivation": "OBSERVED",
                    }
                )
    return inserted


def _states(records: list[dict], at: str) -> dict[str, dict]:
    states = {}
    for record in records:
        if record.get("status") != "open":
            continue
        key = "|".join(
            [
                BOOKMAKER,
                str(record.get("provider_event_id")),
                str(record.get("period")),
                str(record.get("market_family")),
                str(record.get("side")),
                "" if record.get("line") is None else str(record.get("line")),
            ]
        )
        states[key] = {
            "american": record.get("american"),
            "status": "open",
            "source_updated_at": None,
            "last_quote_change_at": at,
            "active": True,
            "bookmaker": BOOKMAKER,
        }
    return states


def _board(
    records: list[dict],
    nba_games: list[dict],
    now: datetime,
    empty_state: str | None,
    failed_ids: set[str] | None = None,
    coverages: list[dict] | None = None,
    previous: dict | None = None,
) -> dict:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(str(record.get("provider_event_id")), []).append(record)
    rows = []
    seen: set[str] = set()
    coverage_by_event = {str(row.get("provider_event_id")): row for row in coverages or []}
    failed = {item for item in (failed_ids or set()) if not str(item).startswith("partial:")}
    carried = {
        str(game.get("provider_event_id")): game
        for game in (previous or {}).get("games") or []
        if game.get("provider_event_id")
    }
    for event_id in failed:
        if event_id in grouped:
            continue
        previous_row = carried.get(event_id)
        if previous_row is not None:
            kept = dict(previous_row)
            kept["event_coverage"] = {
                **(kept.get("event_coverage") or {}),
                "status": "FETCH_FAILED",
                "failures": (coverage_by_event.get(event_id) or {}).get("failures") or ["FETCH_FAILED"],
            }
            rows.append(kept)
            if kept.get("nba", {}) and kept["nba"].get("nba_game_id"):
                seen.add(str(kept["nba"]["nba_game_id"]))
            continue
        rows.append(
            {
                "id": f"betonline-{event_id}",
                "provider_event_id": event_id,
                "matchup": event_id,
                "start_utc": None,
                "bookmaker": None,
                "source_label": BOOKMAKER,
                "mapping": "UNMATCHED",
                "empty_state": "FETCH_FAILED",
                "coverage": "FETCH_FAILED",
                "event_coverage": coverage_by_event.get(event_id),
                "markets": [],
                "outcomes": [],
                "specialty_outcomes": [],
                "freshness": {"source_quote_age": "UNKNOWN", "source_time_label": "SOURCE_QUOTE_AGE_UNKNOWN", "stale": True},
                "quarters": {quarter: {"status": "FETCH_FAILED", "buckets": []} for quarter in QUARTERS},
            }
        )
    for event_id, event_records in grouped.items():
        sample = event_records[0]
        game, mapping = match_event(
            {
                "home_team": sample.get("home_team"),
                "away_team": sample.get("away_team"),
                "commence_time": sample.get("wager_cutoff") or sample.get("start_utc"),
            },
            nba_games,
        )
        if game is not None and game.get("nba_game_id"):
            seen.add(str(game["nba_game_id"]))
        rows.append(_quoted_row(sample, event_records, game, mapping, now, coverage_by_event.get(event_id)))
    for game in nba_games:
        game_id = str(game.get("nba_game_id") or "")
        if game.get("season_type") != "preseason" or not game_id or game_id in seen:
            continue
        rows.append(_scheduled_row(game))
    rows.sort(key=lambda row: (row.get("start_utc") or "", row.get("matchup") or ""))
    starts = [game.get("start_utc") for game in nba_games if game.get("season_type") == "preseason" and game.get("start_utc")]
    seconds, label = cadence_for("BETONLINE")
    return {
        "snapshot_id": f"betonline-{utc_stamp(now).replace('-', '').replace(':', '')}",
        "retrieved_at": utc_stamp(now),
        "method": METHOD,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "source_label": BOOKMAKER,
        "bookmaker": BOOKMAKER,
        "mode": "BETONLINE",
        "cadence_label": label,
        "provider_interval_seconds": seconds,
        "quote_age_seconds": 0,
        "stale": False,
        "source_url": SOURCE_URL,
        "preseason_start": min(starts) if starts else None,
        "preseason_start_source": "NBA_SCHEDULE" if starts else "UNAVAILABLE",
        "empty_state": empty_state,
        "observation_note": "BetOnline WagerCutOff is a betting cutoff, not a quote update. source_updated_at stays empty when the feed has no update time. Observation age uses last_seen_at.",
        "games": rows,
    }


def _quoted_row(sample: dict, records: list[dict], game: dict | None, mapping: str, now: datetime, coverage: dict | None = None) -> dict:
    open_quotes = []
    for record in records:
        if record.get("status") != "open" or record.get("american") is None:
            continue
        open_quotes.append(
            {
                "provider": "betonline",
                "bookmaker": BOOKMAKER,
                "provider_event_id": record.get("provider_event_id"),
                "home_name": record.get("home_team"),
                "away_name": record.get("away_team"),
                "start_utc": record.get("start_utc"),
                "market_family": record.get("market_family"),
                "period": record.get("period"),
                "main": bool(record.get("main")),
                "side": record.get("side"),
                "line": record.get("line"),
                "american": record.get("american"),
                "decimal_odds": record.get("decimal_odds"),
                "implied": record.get("implied"),
                "status": "open",
                "active": True,
                "settlement": record.get("settlement"),
                "market_name": record.get("market_name"),
                "participant": record.get("participant"),
                "source_updated_at": None,
            }
        )
    pairs = pair_quotes(open_quotes)
    for record in records:
        if record.get("status") in {"MARKET_NOT_OFFERED", "NOT_YET_PRICED"} and record.get("market_family") in {"moneyline", "spread", "total", "alternate", "board"}:
            pairs.append(
                {
                    "method": METHOD,
                    "status": record["status"],
                    "market_family": record["market_family"],
                    "period": record["period"],
                    "line": record.get("line"),
                    "settlement": None,
                    "normalized": [],
                    "bookmaker": BOOKMAKER,
                }
            )
    home = (game or {}).get("home_tricode") or sample.get("home_team") or "HOME"
    away = (game or {}).get("away_tricode") or sample.get("away_team") or "AWAY"
    phase = str((game or {}).get("season_type") or "UNMATCHED")
    suspended = sample.get("event_status") not in {None, "", "ACTIVE", "OPEN"}
    outcomes = [_outcome_view(record) for record in records if not record.get("specialty") and record.get("market_family") != "player_prop"]
    specialty = [_outcome_view(record) for record in records if record.get("specialty") or record.get("market_family") in {"player_prop", "unmapped"}]
    nba_start = None if game is None else game.get("start_utc")
    return {
        "id": (game or {}).get("nba_game_id") or f"betonline-{sample.get('provider_event_id')}",
        "provider_event_id": sample.get("provider_event_id"),
        "matchup": f"{away} @ {home}",
        "start_utc": nba_start or sample.get("wager_cutoff"),
        "nba_start_utc": nba_start,
        "wager_cutoff": sample.get("wager_cutoff"),
        "last_seen_at": sample.get("last_seen_at") or utc_stamp(now),
        "status": "suspended" if suspended else ((game or {}).get("status") or "upcoming"),
        "score": None,
        "period": None,
        "clock": None,
        "bookmaker": None if suspended or not open_quotes else BOOKMAKER,
        "source_label": BOOKMAKER,
        "mapping": mapping,
        "season_phase": phase,
        "season_type": phase,
        "coverage": _coverage(open_quotes),
        "empty_state": "SUSPENDED" if suspended else (None if open_quotes else "NO_POSTED_ODDS"),
        "moneyline": _primary(pairs, "moneyline"),
        "main_spread": _primary(pairs, "spread"),
        "main_total": _primary(pairs, "total"),
        "freshness": {
            "source_time_label": "SOURCE_QUOTE_AGE_UNKNOWN",
            "source_quote_age": "UNKNOWN",
            "source_updated_at": None,
            "last_seen_at": sample.get("last_seen_at") or utc_stamp(now),
            "retrieved_at": utc_stamp(now),
            "stale": False,
        },
        "markets": pairs,
        "outcomes": outcomes,
        "specialty_outcomes": specialty,
        "event_coverage": coverage,
        "quarters": {
            quarter: {"status": _quarter_status(records, quarter), "buckets": []}
            for quarter in QUARTERS
        },
        "nba": None
        if game is None
        else {"nba_game_id": game.get("nba_game_id"), "season_type": game.get("season_type")},
    }


def _scheduled_row(game: dict) -> dict:
    home = game.get("home_tricode") or game.get("home_full_name") or "HOME"
    away = game.get("away_tricode") or game.get("away_full_name") or "AWAY"
    return {
        "id": game.get("nba_game_id"),
        "matchup": f"{away} @ {home}",
        "start_utc": game.get("start_utc"),
        "status": game.get("status") or "upcoming",
        "score": None,
        "period": None,
        "clock": None,
        "bookmaker": None,
        "source_label": "SCHEDULED",
        "mapping": "NBA_SCHEDULE",
        "season_phase": "preseason",
        "season_type": "preseason",
        "coverage": "UNAVAILABLE",
        "empty_state": "NO_POSTED_ODDS",
        "event_coverage": {
            "status": "NO_BETONLINE_EVENT",
            "groups_discovered": [],
            "groups_fetched": [],
            "markets_parsed": 0,
            "unmapped_count": 0,
            "failures": [],
        },
        "outcomes": [],
        "specialty_outcomes": [],
        "moneyline": None,
        "main_spread": None,
        "main_total": None,
        "freshness": {"source_time_label": "SOURCE_QUOTE_AGE_UNKNOWN", "source_quote_age": "UNKNOWN", "stale": False},
        "markets": [],
        "quarters": {quarter: {"status": "NO_BETONLINE_EVENT", "buckets": []} for quarter in QUARTERS},
        "nba": {"nba_game_id": game.get("nba_game_id"), "season_type": "preseason"},
    }


def _outcome_view(record: dict) -> dict:
    return {
        "market_family": record.get("market_family"),
        "market_name": record.get("market_name"),
        "period": record.get("period"),
        "participant": record.get("participant"),
        "side": record.get("side"),
        "line": record.get("line"),
        "american": record.get("american"),
        "source_decimal": record.get("source_decimal"),
        "decimal_odds": record.get("decimal_odds"),
        "decimal_discrepancy": record.get("decimal_discrepancy"),
        "status": record.get("status"),
        "no_vig_status": record.get("no_vig_status"),
        "observed_at": record.get("observed_at"),
        "last_seen_at": record.get("last_seen_at"),
        "source_updated_at": record.get("source_updated_at"),
        "wager_cutoff": record.get("wager_cutoff"),
    }


def _quarter_status(records: list[dict], quarter: str) -> str:
    rows = [record for record in records if record.get("period") == quarter]
    if not rows:
        return "COVERAGE_INCOMPLETE"
    if any(record.get("status") == "open" for record in rows):
        return "open"
    return str(rows[0].get("status") or "MARKET_NOT_OFFERED")


def _primary(pairs: list[dict], family: str) -> dict | None:
    ranked = [
        pair
        for pair in pairs
        if pair.get("market_family") == family
        and pair.get("period") == "game"
        and pair.get("status") in {"OK", "CONDITIONAL_ON_NO_PUSH"}
    ]
    return ranked[0] if ranked else None


def _coverage(quotes: list[dict]) -> str:
    families = []
    for family in ("moneyline", "spread", "total"):
        if any(quote.get("market_family") == family and quote.get("period") == "game" for quote in quotes):
            families.append(family)
    return ", ".join(families) if families else "UNAVAILABLE"


def betonline_coverage(store: Store) -> dict:
    now = datetime.now(timezone.utc)
    body = annotate_age(store.current_body() or {}, now)
    quotes = store.book_quotes(BOOKMAKER)
    return {
        "live_execution": False,
        "submits": False,
        "bookmaker": BOOKMAKER,
        "other_books": "NOT_MIXED",
        "policy": {"name": "betonline", "active": True, "detailed_interval_seconds": interval_seconds()},
        "snapshot_collection": "BETONLINE",
        "preseason_listed": False,
        "observed_line_count": len([row for row in quotes if row.get("status") == "open"]),
        "quoted_versus_modeled": (
            "Stored BetOnline lines are OBSERVED sportsbook prices. "
            "Fair probabilities use PROPORTIONAL_NO_VIG_V1 on a complete pair only."
        ),
        "buckets": {},
        "coverage": {},
        "illustrative_costs": [],
        "last_success_at": store.meta_get("betonline_last_success_at"),
        "last_error": store.meta_get("betonline_last_error") or None,
        "quote_age_seconds": body.get("quote_age_seconds"),
        "stale": body.get("stale"),
        "retrieved_at": body.get("retrieved_at"),
    }


def _seconds_since(stamp: object, now: datetime) -> int | None:
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((now - moment).total_seconds()))


def annotate_age(body: dict, now: datetime) -> dict:
    """Observation age comes from last_seen_at. A missing source update time stays unknown."""
    payload = dict(body)
    seconds, _label = cadence_for("BETONLINE")
    games = []
    for game in payload.get("games") or []:
        row = dict(game)
        freshness = dict(row.get("freshness") or {})
        coverage_status = (row.get("event_coverage") or {}).get("status")
        if coverage_status == "NO_BETONLINE_EVENT" or (row.get("bookmaker") is None and row.get("empty_state") == "NO_POSTED_ODDS"):
            freshness["observation_age_seconds"] = None
            freshness["source_quote_age"] = "UNKNOWN"
            freshness["source_time_label"] = "SOURCE_QUOTE_AGE_UNKNOWN"
            freshness["stale"] = False
        else:
            age = _seconds_since(row.get("last_seen_at") or freshness.get("last_seen_at"), now)
            freshness["observation_age_seconds"] = age
            freshness["source_quote_age"] = "UNKNOWN" if not freshness.get("source_updated_at") else "KNOWN"
            freshness["source_time_label"] = "SOURCE_QUOTE_AGE_UNKNOWN" if freshness["source_quote_age"] == "UNKNOWN" else freshness.get("source_time_label")
            freshness["stale"] = age is None or age > seconds * 2
        row["freshness"] = freshness
        games.append(row)
    payload["games"] = games
    payload["quote_age_seconds"] = _seconds_since(payload.get("retrieved_at"), now)
    payload["stale"] = any(game.get("freshness", {}).get("stale") for game in games)
    if payload["stale"]:
        payload["cadence_label"] = "STALE"
    return payload


def main() -> None:
    from pathlib import Path

    from roller.ontologic_x.identity import fetch_nba_catalog
    from roller.ontologic_x.sources import load_local_secrets

    root = Path(__file__).resolve().parents[4]
    load_local_secrets(root / ".env.ontologic")
    now = datetime.now(timezone.utc)
    store = Store(root / "research" / "ontologic_x" / "v1" / "ontologic_x.sqlite")
    catalog = fetch_nba_catalog(now)
    games = list(catalog.get("games") or [])
    if games:
        store.save_probe(
            now,
            str(catalog.get("status")),
            catalog.get("preseason_start"),
            str(catalog.get("season")),
            catalog.get("detail"),
            games,
        )
    elif store.probe():
        games = list((store.probe() or {}).get("games") or [])
    result = collect(store, Client(), games, now)
    print(
        {
            "status": result.get("status"),
            "games": result.get("games"),
            "inserted": result.get("inserted"),
            "retrieved_at": result.get("retrieved_at"),
            "kept_snapshot": result.get("kept_snapshot"),
            "bookmaker": BOOKMAKER,
            "events_inspected": result.get("events_inspected"),
            "events_failed": result.get("events_failed"),
            "groups_fetched": result.get("groups_fetched"),
            "by_category": result.get("by_category"),
            "unmapped": result.get("unmapped"),
            "failures": result.get("failures"),
        }
    )


if __name__ == "__main__":
    main()
