"""Query planner. Decides what to read, not what the answer is.

GENERIC_QUERY only. Frozen FIRST80 never enters this planner.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.research_query.availability import resolve_league_scopes
from roller.research_query.indexes.reader import (
    IndexUnavailable,
    ObservationIndex,
    open_index,
    open_scope_index,
    union_observation_indexes,
)
from roller.research_query.models import (
    BASIS_TRADABLE,
    CompileResult,
    ExecutionPath,
    ResearchQuestion,
)


@dataclass
class QueryPlan:
    execution_mode: str
    index_version: str | None
    rows_scanned: int | None
    index: ObservationIndex | None
    reason: str | None = None


def plan_query(
    compiled: CompileResult,
    *,
    cfg: RollerConfig | None = None,
    dest: Path | None = None,
    dataset_version: str | None = None,
) -> QueryPlan:
    if compiled.execution_path is not ExecutionPath.GENERIC_QUERY:
        return QueryPlan("full_scan", None, None, None, "not_generic")
    question: ResearchQuestion = compiled.question
    cfg = cfg or RollerConfig()
    basis = question.basis() or BASIS_TRADABLE
    if dest is not None:
        try:
            idx = open_index(question, cfg=cfg, dest=dest, expected_dataset_version=dataset_version)
        except FileNotFoundError:
            return QueryPlan("full_scan", None, None, None, "index_absent")
        except IndexUnavailable as exc:
            return QueryPlan("unavailable", None, None, None, str(exc))
        return QueryPlan("indexed", idx.manifest.index_version, idx.rows_scanned, idx, None)

    scopes = resolve_league_scopes(question.universe)
    if not scopes:
        return QueryPlan("full_scan", None, None, None, "index_absent")

    opened: list[ObservationIndex] = []
    missing = 0
    for scope in scopes:
        try:
            opened.append(
                open_scope_index(
                    scope,
                    cfg=cfg,
                    basis=basis,
                    date_from=question.universe.date_from,
                    date_to=question.universe.date_to,
                )
            )
        except FileNotFoundError:
            missing += 1
        except IndexUnavailable as exc:
            return QueryPlan("unavailable", None, None, None, str(exc))

    if missing:
        if len(scopes) > 1:
            return QueryPlan("full_scan", None, None, None, "combined_league_union")
        return QueryPlan("full_scan", None, None, None, "index_absent")
    if not opened:
        return QueryPlan("full_scan", None, None, None, "index_absent")
    idx = union_observation_indexes(opened)
    return QueryPlan(
        execution_mode="indexed",
        index_version=idx.manifest.index_version,
        rows_scanned=idx.rows_scanned,
        index=idx,
        reason="combined_league_union" if len(scopes) > 1 else None,
    )


def bundle_from_index(idx: ObservationIndex) -> dict[str, Any]:
    """Minimal warehouse-shaped payloads so Phase 1 detectors run unchanged."""
    from roller.research_query.availability import RESEARCH_LEAGUE, RESEARCH_SEASON, RESEARCH_SPORT

    meta_by_ticker = {str(row.get("ticker") or ""): row for row in idx.universe}
    payloads: dict[str, list[dict[str, Any]]] = {}
    games: list[dict[str, Any]] = []
    seen_games: set[str] = set()
    for ticker, bars in idx.bars.bars.items():
        gid = bars[0].game_id if bars else ""
        meta = meta_by_ticker.get(ticker) or {}
        league = str(meta.get("league") or idx.manifest.league or "")
        season = str(meta.get("season") or idx.manifest.season or "")
        team_side = meta.get("team_side") or (bars[0].raw or {}).get("team_side") if bars else meta.get("team_side")
        available_at = ""
        if bars:
            available_at = bars[0].ts.isoformat().replace("+00:00", "Z")
        payloads[ticker] = [
            {
                "ticker": ticker,
                "internal_game_id": gid,
                "available_at": available_at,
                "is_valid": True,
                "team_side": team_side,
                RESEARCH_SPORT: league,
                RESEARCH_LEAGUE: league,
                RESEARCH_SEASON: season,
            }
        ]
        if gid and gid not in seen_games:
            seen_games.add(gid)
            games.append(
                {
                    "internal_game_id": gid,
                    "game_id": gid,
                    "league": league,
                    "p5_vs_p5": meta.get("p5_vs_p5"),
                    RESEARCH_SPORT: league,
                    RESEARCH_LEAGUE: league,
                    RESEARCH_SEASON: season,
                }
            )
    return {
        "ticker_payloads": payloads,
        "pbp_by_game": idx.pbp_by_game,
        "markets_by_ticker": idx.markets_by_ticker,
        "tradable_index": idx.bars,
        "games": games,
    }
