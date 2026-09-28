"""NBA + NCAAB warehouse union. Not a FIRST80 lock. Clocks stay league-native."""

from __future__ import annotations

import pandas as pd

from roller.research_query.availability import resolve_league_scopes, resolve_sport_season
from roller.research_query.compiler import compile_draft, compile_question
from roller.research_query.execute import (
    _load_warehouse,
    _scope_sport,
    execute_compiled,
)
from roller.research_query.models import (
    ExecutionPath,
    ResearchStatus,
    TouchOrdinal,
    Universe,
)
from roller.research_query.planner import plan_query
from tests.test_research_query_engine import _q, _series


def _combined_draft(**extra):
    universe = {
        "sports": ["basketball"],
        "leagues": ["NBA", "NCAAB"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dateFrom": "2025-10-10",
        "dateTo": "2026-06-13",
    }
    universe.update(extra.get("universe_patch", {}))
    return {
        "universe": universe,
        "entryConditions": [
            {
                "id": "e1",
                "family": "first_touch",
                "priceCents": 80,
                "periodWindows": [
                    {"period": "Q2"},
                    {"period": "Q3"},
                    {"period": "H1_2"},
                    {"period": "H2_1"},
                ],
            }
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
            {"id": "t", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
        ],
        "teFilters": {"scoreSide": "leading", "absDiff": "6_10"},
    }


def _tag(rows: list[dict], *, sport: str, league: str, game: str) -> list[dict]:
    out = []
    for rec in rows:
        item = dict(rec)
        item["_research_sport"] = sport
        item["_research_league"] = league
        item["internal_game_id"] = game
        out.append(item)
    return out


def test_resolve_scopes_nba_ncaab():
    u = Universe(
        sports=("basketball",),
        leagues=("NBA", "NCAAB"),
        seasons=("2025-26",),
        markets=("kalshi",),
        market_data=("candles",),
    )
    assert resolve_sport_season(u) is None
    scopes = resolve_league_scopes(u)
    assert scopes is not None
    assert [(s.league, s.sport) for s in scopes] == [("NBA", "NBA"), ("NCAAB", "NCAAB")]
    assert all(s.season == "2025-2026" for s in scopes)


def test_combined_compile_ready_not_frozen(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    compiled = compile_draft(_combined_draft())
    assert compiled.status is ResearchStatus.READY
    assert compiled.execution_path is ExecutionPath.GENERIC_QUERY
    assert compiled.reference_match is None
    assert "combined_league_union" in compiled.available
    assert compiled.question.win_hold is True
    assert [w.period for w in compiled.question.entry_conditions[0].period_windows] == [
        "Q2",
        "Q3",
        "H1_2",
        "H2_1",
    ]


def test_combined_missing_ncaab_candles_is_data_required(monkeypatch):
    def exists(_cfg, sport, _season, name):
        return not (sport == "NCAAB" and name == "kalshi_candles")

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", exists)
    compiled = compile_draft(_combined_draft())
    assert compiled.status is ResearchStatus.DATA_REQUIRED
    assert compiled.execution_path is ExecutionPath.NONE
    assert any("NCAAB" in r and "candles" in r for r in compiled.reasons)


def test_combined_plan_is_full_scan_not_unavailable(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        "roller.research_query.planner.open_scope_index",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("absent")),
    )
    compiled = compile_draft(_combined_draft())
    plan = plan_query(compiled)
    assert plan.execution_mode == "full_scan"
    assert plan.reason == "combined_league_union"


def test_scope_sport_reads_tag_not_fallback():
    scopes = resolve_league_scopes(
        Universe(
            sports=("basketball",),
            leagues=("NBA", "NCAAB"),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        )
    )
    assert scopes is not None
    nba = [{"_research_sport": "NBA", "internal_game_id": "G1"}]
    ncaab = [{"_research_sport": "NCAAB", "internal_game_id": "G2"}]
    assert _scope_sport(nba, {}, scopes, "NBA") == "NBA"
    assert _scope_sport(ncaab, {}, scopes, "NBA") == "NCAAB"
    assert _scope_sport([{"internal_game_id": "Gx"}], {}, scopes, "NBA") is None


def test_combined_union_keeps_league_native_clocks(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    compiled = compile_draft(_combined_draft())
    nba_rows = _tag(_series([7000, 8000], ticker="NBA-T", game="G-NBA"), sport="NBA", league="NBA", game="G-NBA")
    ncaab_rows = _tag(
        _series([7000, 8000], ticker="NCAAB-T", game="G-NCAAB"),
        sport="NCAAB",
        league="NCAAB",
        game="G-NCAAB",
    )
    pbp = {
        "G-NBA": [
            {
                "event_timestamp": "2025-12-20T20:00:50Z",
                "available_at": "2025-12-20T20:00:50Z",
                "period": 3,
                "clock": "08:00",
                "internal_game_id": "G-NBA",
            }
        ],
        "G-NCAAB": [
            {
                "event_timestamp": "2025-12-20T20:00:50Z",
                "available_at": "2025-12-20T20:00:50Z",
                "period": 1,
                "clock": "05:00",
                "internal_game_id": "G-NCAAB",
            }
        ],
    }
    out = execute_compiled(
        compiled,
        ticker_payloads={"NBA-T": nba_rows, "NCAAB-T": ncaab_rows},
        pbp_by_game=pbp,
    )
    assert out["execution_status"] == "COMPLETE"
    tickers = {r["ticker"] for r in out["population"]["trades"]}
    assert tickers == {"NBA-T", "NCAAB-T"}
    by_t = {r["ticker"]: r for r in out["population"]["trades"]}
    assert by_t["NBA-T"]["sport"] == "NBA"
    assert by_t["NCAAB-T"]["sport"] == "NCAAB"
    assert out["provenance"]["league_producer"] == "combined_league_union"


def test_ncaab_does_not_match_if_nba_clock_is_forced(monkeypatch):
    """If sport were NBA for an NCAAB half snap, H1_2 would become Q1 and miss."""
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    compiled = compile_draft(_combined_draft())
    ncaab_rows = _tag(
        _series([7000, 8000], ticker="NCAAB-T", game="G-NCAAB"),
        sport="NCAAB",
        league="NCAAB",
        game="G-NCAAB",
    )
    pbp = {
        "G-NCAAB": [
            {
                "event_timestamp": "2025-12-20T20:00:50Z",
                "available_at": "2025-12-20T20:00:50Z",
                "period": 1,
                "clock": "05:00",
                "internal_game_id": "G-NCAAB",
            }
        ]
    }
    ok = execute_compiled(compiled, ticker_payloads={"NCAAB-T": ncaab_rows}, pbp_by_game=pbp)
    assert {r["ticker"] for r in ok["population"]["trades"]} == {"NCAAB-T"}

    untagged = _series([7000, 8000], ticker="NCAAB-T", game="G-NCAAB")
    miss = execute_compiled(compiled, ticker_payloads={"NCAAB-T": untagged}, pbp_by_game=pbp)
    assert miss["summary"]["population_n"] == 0


def test_union_namespaces_ticker_collision(monkeypatch):
    def fake_load(_cfg, sport, _season, name, **_kwargs):
        if name == "kalshi_candles":
            return pd.DataFrame(
                [
                    {
                        "ticker": "SAME",
                        "available_at": "2025-12-20T20:00:00Z",
                        "yes_bid_close": 8000,
                        "internal_game_id": f"{sport}-G",
                    }
                ]
            )
        if name == "pbp":
            return pd.DataFrame([{"internal_game_id": f"{sport}-G"}])
        if name == "games":
            return pd.DataFrame(
                [{"internal_game_id": f"{sport}-G", "p5_vs_p5": "0", "game_date": "2025-12-20"}]
            )
        if name == "kalshi_markets":
            return pd.DataFrame()
        raise FileNotFoundError(name)

    monkeypatch.setattr("roller.admin.load_dataset", fake_load)
    q = compile_draft(_combined_draft()).question
    by_t, _pbp, _mkt, games = _load_warehouse(None, q)  # type: ignore[arg-type]
    assert set(by_t) == {"NBA:SAME", "NCAAB:SAME"}
    assert by_t["NBA:SAME"][0]["_research_sport"] == "NBA"
    assert by_t["NCAAB:SAME"][0]["_research_sport"] == "NCAAB"
    assert {g["_research_league"] for g in games} == {"NBA", "NCAAB"}


def test_single_league_still_resolves():
    u = Universe(
        sports=("basketball",),
        leagues=("NBA",),
        seasons=("2025-26",),
        markets=("kalshi",),
        market_data=("candles",),
    )
    assert resolve_sport_season(u) == ("NBA", "2025-2026")
    compiled = compile_question(_q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3"))
    assert "combined_league_union" not in (compiled.available or [])
