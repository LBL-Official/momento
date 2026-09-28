"""Assemble PIT-safe observations. Entry state never sees future bars or terminal."""

from __future__ import annotations

from typing import Any

from roller.base_terminal_efficiency.market import market_path_metrics
from roller.base_terminal_efficiency.models import (
    OBSERVED,
    Observation,
    UNALIGNED,
    UNAVAILABLE,
)
from roller.base_terminal_efficiency.score import score_state
from roller.base_terminal_efficiency.settlement import terminal_outcome
from roller.base_terminal_efficiency.versions import ENTRY_PRICE_DEFINITION, SCHEMA_VERSION
from roller.research_query.entry_engine import TradableBar, tradable_sequence
from roller.research_query.models import BASIS_LAST_TRADE
from roller.state.observation_id import compact_observation_time


def observation_id(game_id: str, ticker: str, observation_ts, schema: str = SCHEMA_VERSION) -> str:
    compact = compact_observation_time(observation_ts)
    safe_ticker = str(ticker).replace("/", "_")
    return f"BTE_{game_id}_{safe_ticker}_{compact}_V{schema}"


def _iso(ts) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _teams(game: dict[str, Any] | None, team_side: str | None) -> tuple[str | None, str | None]:
    if not game:
        return None, None
    home = game.get("home_team_id")
    away = game.get("away_team_id")
    if team_side == "away":
        return away, home
    if team_side == "home":
        return home, away
    return None, None


def build_observation(
    bars_to_entry: list[TradableBar],
    *,
    pbp_events: list[dict[str, Any]] | None = None,
    game: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    league: str | None = "NBA",
    season: str | None = "2025-2026",
    sport: str = "NBA",
    source_version: str = "",
    attach_terminal: bool = False,
) -> Observation | None:
    if not bars_to_entry:
        return None
    entry = bars_to_entry[-1]
    team_side = (entry.raw or {}).get("team_side") or None
    scored = score_state(pbp_events or [], entry.ts, team_side=team_side, sport=sport)
    extra: dict[str, Any] = {}
    from roller.research_query.sport_family import is_baseball, is_tennis

    if is_baseball(sport):
        from roller.mlb.snap import snap_mlb

        mlb = snap_mlb(pbp_events or [], entry.ts, team_side=team_side)
        extra = {
            "inning": mlb.get("inning"),
            "half": mlb.get("half"),
            "yes_batting": mlb.get("yes_batting"),
            "yes_pitching": mlb.get("yes_pitching"),
            "outs": mlb.get("outs"),
            "balls": mlb.get("balls"),
            "strikes": mlb.get("strikes"),
            "count_display": mlb.get("count_display"),
            "count_leverage": mlb.get("count_leverage"),
            "runners": mlb.get("runners"),
            "runner_on_1": mlb.get("runner_on_1"),
            "runner_on_2": mlb.get("runner_on_2"),
            "runner_on_3": mlb.get("runner_on_3"),
            "batting_team": mlb.get("batting_team"),
            "run_differential": scored.get("point_differential"),
            "point_differential_unit": "runs",
        }
        if mlb.get("status") == UNALIGNED:
            return None
    if is_tennis(sport):
        from roller.tennis.snap import NO_POINT_DATA, snap_tennis

        ten = snap_tennis(pbp_events or [], entry.ts, team_side=team_side)
        extra = {
            "pbp_basis": ten.get("pbp_basis"),
            "pit_joinable": ten.get("pit_joinable"),
            "point_snapshot_available": ten.get("point_snapshot_available"),
            "snapshot_age_seconds": ten.get("snapshot_age_seconds"),
            "set_number": ten.get("set_number"),
            "game_number": ten.get("game_number"),
            "yes_serving": ten.get("yes_serving"),
            "yes_returning": ten.get("yes_returning"),
            "yes_set_lead": ten.get("yes_set_lead"),
            "yes_game_lead": ten.get("yes_game_lead"),
            "yes_point_lead": ten.get("yes_point_lead"),
            "yes_set_point": ten.get("yes_set_point"),
            "yes_match_point": ten.get("yes_match_point"),
            "break_point": ten.get("break_point"),
            "is_tiebreak": ten.get("is_tiebreak"),
            "point_score_raw": ten.get("point_score_raw"),
            "server": ten.get("server"),
            "point_differential_unit": "tennis_not_collapsed",
        }
        if ten.get("status") == NO_POINT_DATA:
            extra["alignment_status"] = UNALIGNED
            extra["exclusion_reason"] = ten.get("exclusion_reason")
            return None
        extra["alignment_status"] = "aligned"
    elif scored["alignment_status"] == UNALIGNED and scored["team_points"] is None:
        return None
    mkt = market_path_metrics([b.bid for b in bars_to_entry])
    team, opp = _teams(game, team_side)
    term = terminal_outcome(market) if attach_terminal else "MISSING"
    feature = OBSERVED
    if scored["score_status"] != OBSERVED:
        feature = scored["score_status"] or UNAVAILABLE
    return Observation(
        observation_id=observation_id(entry.game_id, entry.ticker, entry.ts),
        game_id=entry.game_id,
        ticker=entry.ticker,
        league=league or (game or {}).get("league"),
        season=season or (game or {}).get("season"),
        team_side=team_side,
        team=team,
        opponent=opp,
        observation_ts=_iso(entry.ts),
        period=scored["period"],
        game_clock=scored["game_clock"],
        remaining_game_time=scored["remaining_game_time"],
        elapsed_game_time=scored["elapsed_game_time"],
        alignment_status=scored["alignment_status"],
        team_points=scored["team_points"],
        opponent_points=scored["opponent_points"],
        total_points=scored["total_points"],
        point_differential=scored["point_differential"],
        point_differential_abs_e0=scored["point_differential_abs_e0"],
        point_differential_sign=scored["point_differential_sign"],
        score_path_team=tuple(scored["score_path_team"]),
        score_path_opponent=tuple(scored["score_path_opponent"]),
        score_change_from_start=scored["score_change_from_start"],
        opponent_score_change_from_start=scored["opponent_score_change_from_start"],
        total_score_change_from_start=scored["total_score_change_from_start"],
        differential_change_from_start=scored["differential_change_from_start"],
        team_score_volatility=scored["team_score_volatility"],
        opponent_score_volatility=scored["opponent_score_volatility"],
        total_score_volatility=scored["total_score_volatility"],
        differential_volatility=scored["differential_volatility"],
        entry_price_e4=int(entry.bid),
        entry_price_cents=int(entry.bid) // 100,
        entry_price_ts=_iso(entry.ts),
        entry_price_source=(
            "kalshi_last_trade" if getattr(entry, "basis", "") == BASIS_LAST_TRADE else "kalshi_candles"
        ),
        entry_price_definition=ENTRY_PRICE_DEFINITION,
        initial_market_price_e4=mkt["initial_market_price_e4"],
        signed_price_displacement_e4=mkt["signed_price_displacement_e4"],
        absolute_price_displacement_e4=mkt["absolute_price_displacement_e4"],
        cumulative_price_travel_e4=mkt["cumulative_price_travel_e4"],
        max_price_pre_entry_e4=mkt["max_price_pre_entry_e4"],
        min_price_pre_entry_e4=mkt["min_price_pre_entry_e4"],
        price_path_range_e4=mkt["price_path_range_e4"],
        entry_price_volatility=mkt["entry_price_volatility"],
        recent_entry_price_volatility=mkt["recent_entry_price_volatility"],
        score_status=scored["score_status"],
        market_status=OBSERVED,
        feature_status=feature,
        terminal_outcome=term,
        source_version=source_version,
        extra=extra,
    )


def path_store_record(bars: list[TradableBar], pbp_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not bars:
        return {}
    return {
        "ticker": bars[0].ticker,
        "game_id": bars[0].game_id,
        "bars": [
            {
                "ts": _iso(b.ts),
                "yes_bid_close": b.bid,
                "available_at": _iso(b.ts),
            }
            for b in bars
        ],
    }


def observations_for_ticker(
    candles: list[dict[str, Any]],
    pbp_events: list[dict[str, Any]],
    *,
    game: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    league: str | None = "NBA",
    season: str | None = "2025-2026",
    source_version: str = "",
    attach_terminal: bool = False,
) -> tuple[list[Observation], dict[str, Any]]:
    bars, _skipped = tradable_sequence(candles)
    seen_aligned = False
    rows: list[Observation] = []
    for i in range(len(bars)):
        obs = build_observation(
            bars[: i + 1],
            pbp_events=pbp_events,
            game=game,
            market=market,
            league=league,
            season=season,
            source_version=source_version,
            attach_terminal=attach_terminal,
        )
        if obs is None:
            continue
        seen_aligned = True
        rows.append(obs)
    if not seen_aligned:
        return [], path_store_record(bars, pbp_events)
    return rows, path_store_record(bars, pbp_events)
