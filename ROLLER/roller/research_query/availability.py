"""Data availability — independent of operation capability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from roller.config import RollerConfig
from roller.research_query.models import PathOp, ResearchQuestion, Universe
from roller.research_query.season_mapping import (
    default_warehouse_season,
    sport_from_league,
    warehouse_season,
)

# Candle / game rows are tagged with these keys by the combined-league union.
RESEARCH_SPORT = "_research_sport"
RESEARCH_LEAGUE = "_research_league"
RESEARCH_SEASON = "_research_season"


@dataclass(frozen=True)
class LeagueScope:
    """One warehouse slice. Combined NBA+NCAAB is a union of these, not a lock."""

    league: str
    sport: str
    season: str


OPTIONAL_PBP = frozenset({"espn", "nba_api"})
NO_WAREHOUSE_SPORTS = frozenset()
TENNIS_WAREHOUSE_SPORTS = frozenset({"tennis", "ATP", "WTA"})
LAST_TRADE_NOT_YES_BID = (
    "Kalshi last-trade 1-minute bars are last chronological prints. "
    "LAST TRADE ≠ YES BID. Minutes without a print are absent, not forward-filled."
)
NO_WAREHOUSE_MARKET_DATA = frozenset({"tick", "l2"})
NO_WAREHOUSE_PBP = frozenset({"kenpom", "ncaa", "wnba_pbp"})
POLYMARKET_NO_WAREHOUSE = (
    "This question requires Polymarket market data. "
    "No Polymarket warehouse is currently available. "
    "Kalshi cannot be substituted automatically."
)
POLYMARKET_LAST_PRICE_NOT_TOB = (
    "Polymarket 1-minute warehouse series is last-trade price history "
    "(CLOB /prices-history), not tradable top-of-book bid/ask. "
    "Kalshi cannot be substituted automatically."
)
CROSS_VENUE_NO_JOINT_BASIS = (
    "Kalshi and Polymarket have different observation bases "
    "(tradable top-of-book vs last-trade print). Joint cross-venue semantics "
    "are not defined. Select one market. Neither venue is substituted for the other."
)


def _dataset_exists(cfg: RollerConfig, sport: str, season: str, name: str) -> bool:
    try:
        path = cfg.dataset_path(sport, season, name)
    except (KeyError, FileNotFoundError):
        return False
    p = Path(path)
    if p.is_file():
        return True
    if p.is_dir():
        return any(p.rglob("*"))
    return False


def resolve_league_scopes(universe: Universe) -> tuple[LeagueScope, ...] | None:
    """Every selected league × season. None if a league cannot be mapped.

    Combined NBA + NCAAB is a warehouse union. Clocks stay league-native.
    This is not a FIRST80 lock and does not invent a joint market.
    """
    leagues = list(universe.leagues)
    if not leagues:
        from roller.research_query.sport_family import is_baseball

        from roller.research_query.sport_family import is_tennis

        if any(is_baseball(s) for s in universe.sports):
            leagues = ["MLB"]
        elif any(is_tennis(s) for s in universe.sports):
            leagues = ["ATP", "WTA"]
        else:
            return None
    ui_seasons = tuple(universe.seasons) if universe.seasons else (None,)
    out: list[LeagueScope] = []
    seen: set[tuple[str, str, str]] = set()
    for league in leagues:
        try:
            sport = sport_from_league(league)
        except ValueError:
            return None
        canon = sport
        for ui in ui_seasons:
            season = default_warehouse_season(sport) if ui is None else warehouse_season(ui, sport)
            key = (canon, sport, season)
            if key in seen:
                continue
            seen.add(key)
            out.append(LeagueScope(league=canon, sport=sport, season=season))
    return tuple(out) if out else None


def resolve_sport_season(universe: Universe) -> tuple[str, str] | None:
    """Single-league helper. Combined universes return None — use resolve_league_scopes."""
    scopes = resolve_league_scopes(universe)
    if scopes is None or len(scopes) != 1:
        return None
    return scopes[0].sport, scopes[0].season


def polymarket_candles_available(question: ResearchQuestion, cfg: RollerConfig) -> bool:
    scopes = resolve_league_scopes(question.universe)
    if not scopes:
        return False
    return all(_dataset_exists(cfg, s.sport, s.season, "polymarket_candles") for s in scopes)


def baseball_warehouse_ready(cfg: RollerConfig | None = None) -> bool:
    cfg = cfg or RollerConfig()
    return (
        _dataset_exists(cfg, "MLB", "2025-2026", "games")
        and _dataset_exists(cfg, "MLB", "2025-2026", "pbp")
        and (
            _dataset_exists(cfg, "MLB", "2025-2026", "kalshi_last_trade")
            or _dataset_exists(cfg, "MLB", "2025-2026", "kalshi_candles")
        )
    )


def tennis_warehouse_ready(cfg: RollerConfig | None = None) -> bool:
    """True when the shared ATP/WTA canonical tree has games + a market layer."""
    cfg = cfg or RollerConfig()
    return _dataset_exists(cfg, "ATP", "2025-2026", "games") and (
        _dataset_exists(cfg, "ATP", "2025-2026", "kalshi_candles")
        or _dataset_exists(cfg, "ATP", "2025-2026", "kalshi_last_trade")
    )


def tennis_observation_layers(cfg: RollerConfig | None = None) -> dict:
    """Per-layer tennis coverage. Not a compile gate. Missing ≠ DATA_REQUIRED for other layers."""
    from roller.tennis.observability import tennis_observation_layers as _layers

    return _layers(cfg)


def data_gaps(question: ResearchQuestion, *, cfg: RollerConfig | None = None) -> list[str]:
    u = question.universe
    gaps: list[str] = []
    cfg = cfg or RollerConfig()
    from roller.research_query.market_path import required_market_dataset
    from roller.research_query.sport_family import is_baseball, is_tennis, mixed_clock_families

    for s in u.sports:
        if s in NO_WAREHOUSE_SPORTS:
            gaps.append(f"No authoritative ROLLER dataset currently exists for {s}.")
        if s in TENNIS_WAREHOUSE_SPORTS or is_tennis(s):
            if not tennis_warehouse_ready(cfg):
                gaps.append(
                    "No authoritative ROLLER tennis warehouse currently exists. "
                    "Kalshi acquisition and canonical ingest must complete before tennis is runnable. "
                    "This is DATA_REQUIRED, not N=0."
                )
                break
    if mixed_clock_families(u.sports, u.leagues):
        from roller.research_query.sport_family import MIXED_CLOCK_REASON

        gaps.append(MIXED_CLOCK_REASON)
    if not u.markets:
        gaps.append("Select a market.")
    scopes = resolve_league_scopes(u)
    if scopes is None:
        if not u.leagues:
            gaps.append("Select a league.")
        else:
            gaps.append("Unknown or unresolvable league.")
        return gaps
    if "polymarket" in u.markets:
        if not polymarket_candles_available(question, cfg):
            gaps.append(POLYMARKET_NO_WAREHOUSE)
    if "candles" not in u.market_data and u.market_data:
        if all(d in NO_WAREHOUSE_MARKET_DATA for d in u.market_data):
            gaps.append("Requested market data is not in the warehouse.")
    needs_pbp = any(e.has_period_or_clock() for e in question.entry_conditions) or any(
        p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game"
        for p in question.path_conditions
    )
    for scope in scopes:
        needed = required_market_dataset(question, scope)
        if needed and "kalshi" in u.markets:
            if not _dataset_exists(cfg, scope.sport, scope.season, needed):
                if needed == "kalshi_last_trade":
                    gaps.append(
                        f"Kalshi last-trade 1-minute prints are not available for {scope.sport} {scope.season}. "
                        + LAST_TRADE_NOT_YES_BID
                    )
                else:
                    gaps.append(
                        f"Kalshi 1-minute candles are not available for {scope.sport} {scope.season}."
                    )
            elif needed == "kalshi_candles" and is_baseball(scope.sport):
                from roller.research_query.market_path import candles_quality_ready

                if not candles_quality_ready(cfg, scope.sport, scope.season):
                    gaps.append(
                        "MLB Kalshi candles cannot pass frozen quality() without positive volume. "
                        "Volume is not invented from print count. LAST TRADE remains the runnable path. "
                        "This is not an empty FIRST_TOUCH population."
                    )
        if needs_pbp and not _dataset_exists(cfg, scope.sport, scope.season, "pbp"):
            if is_baseball(scope.sport):
                gaps.append(
                    "Inning / half entry filters require PBP. "
                    f"No PBP warehouse is available for {scope.sport} {scope.season}."
                )
            elif is_tennis(scope.sport) or is_tennis(scope.league):
                gaps.append(
                    "Tennis set/game/point entry windows require canonical PBP. "
                    f"No PBP warehouse is available for {scope.sport} {scope.season}. "
                    "SEQUENCE-ONLY PBP is not a PIT snap. This is DATA_REQUIRED, not N=0."
                )
            else:
                gaps.append(
                    "Game-clock exits and period/clock entry filters require PBP. "
                    f"No PBP warehouse is available for {scope.sport} {scope.season}. "
                    "Reach-only is not substituted for Game clock WIN."
                )
    return gaps


def optional_omissions(question: ResearchQuestion) -> list[str]:
    omitted: list[str] = []
    for d in question.universe.market_data:
        if d in NO_WAREHOUSE_MARKET_DATA:
            omitted.append(d)
    for s in question.universe.game_data:
        if s in NO_WAREHOUSE_PBP:
            omitted.append(s)
    return omitted
