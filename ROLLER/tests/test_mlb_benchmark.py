"""Execute scales with candidate observations, not raw JSON file count."""

from __future__ import annotations

import time

from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import CompileResult, ExecutionPath, ResearchStatus


def _bars(n_games: int) -> tuple[dict, dict, dict, list]:
    payloads = {}
    pbp = {}
    markets = {}
    games = []
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


def _forced():
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


def test_execute_scales_with_candidates_not_raw_json():
    forced = _forced()
    times = {}
    for n in (1, 10, 100, 1000):
        payloads, pbp, markets, games = _bars(n)
        t0 = time.perf_counter()
        out = execute_compiled(
            forced,
            ticker_payloads=payloads,
            pbp_by_game=pbp,
            markets_by_ticker=markets,
            games=games,
        )
        times[n] = time.perf_counter() - t0
        assert out["execution_status"] == "COMPLETE"
        scanned = out["performance"].get("rows_scanned")
        if scanned is None:
            scanned = sum(len(v) for v in payloads.values())
        assert scanned <= n * 4
    # 1000 candidates should not be 1000× a raw JSON parse of the lake.
    assert times[1] < 5
    assert times[1000] < 60


def test_record_mlb1_benchmark_report():
    from roller.config import RollerConfig
    from roller.mlb.benchmark import write_report
    from roller.research_query.availability import baseball_warehouse_ready

    if not baseball_warehouse_ready():
        return
    payload = write_report()
    path = RollerConfig().root / "reports" / "mlb1_execute_benchmark.json"
    assert path.is_file()
    assert payload["full_warehouse"]["raw_json_parsed"] is False
    assert payload["full_warehouse"]["status"] == "COMPLETE"
