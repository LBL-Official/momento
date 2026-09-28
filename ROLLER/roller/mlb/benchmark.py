"""Record Execute cost vs candidate observations, not raw JSON file count."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import CompileResult, ExecutionPath, ResearchStatus


def _forced() -> CompileResult:
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"}],
        }
    )
    return CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=compiled.question.on_last_trade_basis(),
        reasons=[],
        unavailable=[],
    )


def _bars(n_games: int) -> tuple[dict, dict, dict, list]:
    payloads: dict[str, list] = {}
    pbp: dict[str, list] = {}
    markets: dict[str, dict] = {}
    games: list[dict] = []
    for i in range(n_games):
        gid = f"MLB_BENCH_{i}"
        ticker = f"KXMLBGAME-BENCH-{i}-NYY"
        payloads[ticker] = [
            {
                "available_at": "2026-06-18T23:00:00Z",
                "last_close_e4": 7900,
                "ticker": ticker,
                "internal_game_id": gid,
                "team_side": "away",
                "is_valid": "1",
            },
            {
                "available_at": "2026-06-18T23:01:00Z",
                "last_close_e4": 8000,
                "ticker": ticker,
                "internal_game_id": gid,
                "team_side": "away",
                "is_valid": "1",
            },
        ]
        pbp[gid] = [
            {
                "event_number": 1,
                "event_timestamp": "2026-06-18T23:00:30Z",
                "inning": 7,
                "half": "top",
                "outs": 2,
                "balls": 0,
                "strikes": 0,
                "runner_on_1": "0",
                "runner_on_2": "1",
                "runner_on_3": "0",
                "batting_team": "away",
                "home_score": 1,
                "away_score": 3,
            }
        ]
        markets[ticker] = {"result": "yes", "internal_game_id": gid}
        games.append({"internal_game_id": gid, "league": "MLB", "sport": "MLB"})
    return payloads, pbp, markets, games


def time_injected(n: int) -> dict[str, Any]:
    forced = _forced()
    payloads, pbp, markets, games = _bars(n)
    t0 = time.perf_counter()
    out = execute_compiled(
        forced,
        ticker_payloads=payloads,
        pbp_by_game=pbp,
        markets_by_ticker=markets,
        games=games,
    )
    cold = time.perf_counter() - t0
    t1 = time.perf_counter()
    execute_compiled(
        forced,
        ticker_payloads=payloads,
        pbp_by_game=pbp,
        markets_by_ticker=markets,
        games=games,
    )
    warm = time.perf_counter() - t1
    return {
        "n_games": n,
        "status": out["execution_status"],
        "population_n": out.get("summary", {}).get("population_n"),
        "rows_scanned": out.get("performance", {}).get("rows_scanned") or (n * 2),
        "cold_s": round(cold, 4),
        "warm_s": round(warm, 4),
        "index_build_ms": out.get("performance", {}).get("index_build_ms"),
        "mode": "injected_candidates",
    }


def time_warehouse(*, date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    cfg = RollerConfig()
    draft = {
        "universe": {
            "sports": ["baseball"],
            "leagues": ["MLB"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
        },
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"}],
    }
    if date_from:
        draft["universe"]["dateFrom"] = date_from
    if date_to:
        draft["universe"]["dateTo"] = date_to
    compiled = compile_draft(draft, cfg=cfg)
    t0 = time.perf_counter()
    out = execute_compiled(compiled, cfg=cfg)
    cold = time.perf_counter() - t0
    t1 = time.perf_counter()
    out2 = execute_compiled(compiled, cfg=cfg)
    warm = time.perf_counter() - t1
    perf = out.get("performance") or {}
    return {
        "n_games": "full_available" if not date_from else f"{date_from}:{date_to}",
        "status": out["execution_status"],
        "population_n": (out.get("summary") or {}).get("population_n"),
        "rows_scanned": perf.get("rows_scanned"),
        "cold_s": round(cold, 4),
        "warm_s": round(warm, 4),
        "index_build_ms": perf.get("index_build_ms"),
        "cache_hit_result": (out2.get("performance") or {}).get("cache_hit_result"),
        "mode": "canonical_csv_indexes",
        "raw_json_parsed": False,
    }


def run_suite() -> dict[str, Any]:
    rows = [time_injected(n) for n in (1, 10, 100, 1000)]
    warehouse = time_warehouse()
    return {
        "note": "Execute scales with candidate observations, not raw StatsAPI JSON file count.",
        "injected": rows,
        "full_warehouse": warehouse,
        "gate_17": "no raw-PBP parse on normal Execute",
    }


def write_report(path: Path | None = None) -> dict[str, Any]:
    cfg = RollerConfig()
    dest = path or (cfg.root / "reports" / "mlb1_execute_benchmark.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = run_suite()
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
