"""Assemble one Ontologic X snapshot from NBA games and paired quotes."""

from __future__ import annotations

from collections import defaultdict

from roller.ontologic_x import LIVE_EXECUTION, METHOD
from roller.ontologic_x.identity import match_canonical, match_game, normalize_nba_game, preseason_start
from roller.ontologic_x.pairing import pair_quotes, split_books, survival_points

QUARTERS = ("Q1", "Q2", "Q3", "Q4")


def natural_key(quote: dict) -> str:
    line = "" if quote.get("line") is None else str(quote.get("line"))
    return "|".join(
        [
            str(quote.get("provider_event_id")),
            str(quote.get("bookmaker")),
            str(quote.get("market_family")),
            str(quote.get("period")),
            str(quote.get("settlement")),
            str(quote.get("side")),
            line,
            "1" if quote.get("main") else "0",
        ]
    )


def merge_quotes(incoming: list[dict], previous: dict[str, dict], retrieved_at: str) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for quote in incoming:
        key = natural_key(quote)
        seen.add(key)
        prior = previous.get(key)
        source = quote.get("source_updated_at") if "source_updated_at" in quote else None
        changed = (
            prior is None
            or str(prior.get("american")) != str(quote.get("american"))
            or prior.get("status") != quote.get("status", "open")
        )
        merged.append(
            {
                **quote,
                "status": quote.get("status") or "open",
                "source_updated_at": source,
                "last_quote_change_at": retrieved_at if changed else prior.get("last_quote_change_at"),
                "active": (quote.get("status") or "open") == "open",
                "natural_key": key,
            }
        )
    for key, prior in previous.items():
        if key in seen:
            continue
        if prior.get("status") == "open":
            merged.append({**prior, "status": "withdrawn", "active": False, "last_quote_change_at": retrieved_at})
        else:
            merged.append({**prior, "active": False})
    return merged


def _by_event(quotes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for quote in quotes:
        grouped[str(quote.get("provider_event_id"))].append(quote)
    return grouped


def _matchup(game: dict) -> str:
    away = game.get("away_tricode") or game.get("away_name") or "AWAY"
    home = game.get("home_tricode") or game.get("home_name") or "HOME"
    return f"{away} @ {home}"


def _score(game: dict) -> str | None:
    home = game.get("home_score")
    away = game.get("away_score")
    if home is None or away is None or home == "" or away == "":
        return None
    return f"{away}-{home}"


def _freshness(quotes: list[dict], retrieved_at: str) -> dict:
    times = [quote.get("source_updated_at") for quote in quotes]
    changes = [quote.get("last_quote_change_at") for quote in quotes if quote.get("last_quote_change_at")]
    if not quotes or any(item is None or item == "" for item in times):
        source_label = "SOURCE_TIME_UNAVAILABLE"
        source_value = None
    else:
        source_value = max(str(item) for item in times)
        source_label = source_value
    return {
        "source_updated_at": source_value,
        "source_time_label": source_label,
        "last_quote_change_at": max(changes) if changes else None,
        "retrieved_at": retrieved_at,
    }


def _primary(pairs: list[dict], family: str) -> dict | None:
    ranked = [
        pair
        for pair in pairs
        if pair.get("market_family") == family
        and pair.get("period") == "game"
        and pair.get("main")
        and pair.get("status") in {"OK", "CONDITIONAL_ON_NO_PUSH"}
    ]
    return ranked[0] if ranked else None


def _coverage(pairs: list[dict]) -> str:
    families = []
    for family in ("moneyline", "spread", "total"):
        if any(pair.get("market_family") == family and pair.get("status") in {"OK", "CONDITIONAL_ON_NO_PUSH"} for pair in pairs):
            families.append(family)
    quarters = [
        quarter
        for quarter in QUARTERS
        if any(pair.get("period") == quarter and pair.get("status") in {"OK", "CONDITIONAL_ON_NO_PUSH"} for pair in pairs)
    ]
    if quarters:
        families.extend(quarters)
    return ", ".join(families) if families else "NO_POSTED_ODDS"


def _partition_for(pairs: list[dict], family: str, period: str, variable: str) -> dict:
    settlements = [
        pair.get("settlement")
        for pair in pairs
        if pair.get("market_family") == family and pair.get("period") == period and pair.get("settlement")
    ]
    if not settlements:
        return survival_points(pairs, family, period, "including_overtime", variable)
    settlement = "including_overtime" if "including_overtime" in settlements else settlements[0]
    return survival_points(pairs, family, period, str(settlement), variable)


def _game_row(game: dict, quotes: list[dict], canonical: list[dict], retrieved_at: str, source_label: str) -> dict:
    active = [quote for quote in quotes if quote.get("active")]
    inactive = [quote for quote in quotes if not quote.get("active")]
    pairs = pair_quotes(active)
    internal, canonical_status = match_canonical(game, canonical)
    margin = _partition_for(pairs, "spread", "game", "M")
    total = _partition_for(pairs, "total", "game", "T")
    quarters = {}
    for quarter in QUARTERS:
        part = _partition_for(pairs, "total", quarter, f"T_{quarter}")
        quarters[quarter] = part if part.get("status") == "OK" else {"status": "UNAVAILABLE", "buckets": [], "variable": f"T_{quarter}"}
    flags = []
    for pair in pairs:
        if pair.get("status") not in {None, "OK"} and pair.get("status") not in flags:
            flags.append(pair["status"])
    if margin.get("status") == "SUPPRESSED" and margin.get("reason") not in flags:
        flags.append(margin.get("reason"))
    if not flags:
        flags.append("OK")
    empty = None
    if not quotes:
        empty = "NO_POSTED_ODDS"
    elif not active:
        empty = "SUSPENDED"
    elif not any(pair.get("status") in {"OK", "CONDITIONAL_ON_NO_PUSH"} for pair in pairs):
        empty = "INCOMPLETE"
    elif margin.get("status") == "SUPPRESSED":
        empty = "INCONSISTENT_LADDER"
    return {
        "id": game.get("nba_game_id"),
        "matchup": _matchup(game),
        "start_utc": game.get("start_utc"),
        "status": game.get("status") or "upcoming",
        "score": _score(game),
        "period": game.get("period") or None,
        "clock": game.get("clock") or None,
        "neutral": bool(game.get("neutral")),
        "season_type": game.get("season_type"),
        "bookmaker": "williamhill" if active else None,
        "source_label": source_label,
        "mapping": "NEUTRAL_UNMATCHED" if game.get("neutral") else "MATCHED",
        "internal_game_id": internal,
        "canonical_mapping": canonical_status,
        "moneyline": _primary(pairs, "moneyline"),
        "main_spread": _primary(pairs, "spread"),
        "main_total": _primary(pairs, "total"),
        "coverage": _coverage(pairs),
        "freshness": _freshness(active, retrieved_at),
        "markets": pairs,
        "history": inactive,
        "margin_partition": margin,
        "total_partition": total,
        "quarters": quarters,
        "coherence": flags,
        "empty_state": empty,
        "nba": {
            "nba_game_id": game.get("nba_game_id"),
            "home_team_id": game.get("home_team_id"),
            "away_team_id": game.get("away_team_id"),
            "home_tricode": game.get("home_tricode"),
            "away_tricode": game.get("away_tricode"),
            "season": game.get("season"),
            "season_type": game.get("season_type"),
        },
    }


def _event_row(event_id: str, quotes: list[dict], mapping: str, retrieved_at: str, source_label: str) -> dict:
    sample = quotes[0]
    away = sample.get("away_tricode") or sample.get("away_name") or sample.get("away_team_id")
    home = sample.get("home_tricode") or sample.get("home_name") or sample.get("home_team_id")
    active = [quote for quote in quotes if quote.get("active")]
    pairs = pair_quotes(active)
    return {
        "id": f"unmatched-{event_id}",
        "matchup": f"{away} @ {home}",
        "start_utc": sample.get("start_utc"),
        "status": "unmatched",
        "score": None,
        "period": None,
        "clock": None,
        "neutral": False,
        "season_type": None,
        "bookmaker": "williamhill" if active else None,
        "source_label": source_label,
        "mapping": mapping,
        "internal_game_id": None,
        "canonical_mapping": "UNMATCHED",
        "moneyline": _primary(pairs, "moneyline"),
        "main_spread": _primary(pairs, "spread"),
        "main_total": _primary(pairs, "total"),
        "coverage": _coverage(pairs),
        "freshness": _freshness(active, retrieved_at),
        "markets": pairs,
        "history": [quote for quote in quotes if not quote.get("active")],
        "margin_partition": {"status": "UNAVAILABLE", "buckets": []},
        "total_partition": {"status": "UNAVAILABLE", "buckets": []},
        "quarters": {quarter: {"status": "UNAVAILABLE", "buckets": []} for quarter in QUARTERS},
        "coherence": [mapping],
        "empty_state": mapping,
        "nba": None,
    }


def _sort_key(game: dict) -> tuple:
    rank = {"live": 0, "upcoming": 1, "unmatched": 2, "completed": 3}.get(game.get("status"), 4)
    return (rank, game.get("start_utc") or "")


def build_snapshot(
    *,
    nba_games: list[dict],
    canonical_games: list[dict],
    quotes: list[dict],
    previous: dict[str, dict],
    retrieved_at: str,
    snapshot_id: str,
    source_label: str,
    mode: str,
    cadence_label: str,
    rejected: list[dict],
) -> tuple[dict, dict[str, dict]]:
    games = [normalize_nba_game(game) for game in nba_games]
    kept, book_rejected = split_books(quotes)
    active_incoming = []
    for quote in kept:
        game, status = match_game(quote, games)
        if status == "MATCHED" and game is not None and game.get("status") == "completed":
            continue
        active_incoming.append(quote)
    merged = merge_quotes(active_incoming, previous, retrieved_at)
    states = {quote["natural_key"]: quote for quote in merged}
    events = _by_event(merged)
    assigned: dict[str, list[dict]] = {str(game.get("nba_game_id")): [] for game in games}
    loose: list[dict] = []
    for event_id, event_quotes in events.items():
        sample = event_quotes[0]
        game, status = match_game(sample, games)
        if status == "MATCHED" and game is not None and game.get("status") != "completed":
            assigned[str(game.get("nba_game_id"))].extend(event_quotes)
        else:
            loose.append(_event_row(event_id, event_quotes, status, retrieved_at, source_label))
    rows = [_game_row(game, assigned.get(str(game.get("nba_game_id")), []), canonical_games, retrieved_at, source_label) for game in games]
    rows.extend(loose)
    rows.sort(key=_sort_key)
    body = {
        "snapshot_id": snapshot_id,
        "retrieved_at": retrieved_at,
        "method": METHOD,
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "source_label": source_label,
        "mode": mode,
        "cadence_label": cadence_label,
        "preseason_start": preseason_start(games),
        "preseason_start_source": source_label,
        "canonical_source": "CANONICAL_FIXTURE" if mode == "FIXTURE" else "NBA_SCHEDULE",
        "rejected_books": book_rejected + [_rejected_row(item) for item in rejected],
        "games": rows,
    }
    return body, states


def _rejected_row(item: object) -> dict:
    if isinstance(item, dict):
        return item
    return {"bookmaker": item, "reason": str(item)}
