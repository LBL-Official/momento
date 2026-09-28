"""Tennis layers stay independent. PIT is NO_POINT_DATA. Not a compile gate."""

from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import CompileResult, ExecutionPath, ResearchStatus
from roller.tennis.observability import (
    AVAILABLE,
    MISSING,
    NO_POINT_DATA,
    PARTIAL,
    tennis_observation_layers,
)
from tests.test_tennis_execute import _candle, _draft, _ts_point


def test_layers_are_not_one_data_required_blob():
    out = tennis_observation_layers()
    layers = out["layers"]
    assert layers["event_identity"]["status"] == AVAILABLE
    assert layers["event_identity"]["have"] == 9097
    assert layers["kalshi_settlement"]["status"] in {AVAILABLE, PARTIAL}
    assert layers["yes_bid_candles"]["status"] in {PARTIAL, AVAILABLE}
    assert layers["last_trade_1m"]["status"] in {PARTIAL, AVAILABLE}
    assert layers["trade_ticks"]["status"] == MISSING
    assert layers["mcp_pbp"]["status"] == PARTIAL
    assert layers["mcp_pbp"]["have"] == 688
    assert layers["pit_point_state"]["status"] == NO_POINT_DATA
    assert "DATA_REQUIRED" not in out["summary"]


def test_unlisted_competitions_are_not_forced_into_pbp_have():
    pbp = tennis_observation_layers()["layers"]["mcp_pbp"]
    assert pbp["have"] == 688
    assert pbp["universe"] == 9097
    assert pbp["have"] < pbp["universe"]


def test_execute_exposes_tennis_layers_without_changing_path():
    compiled = compile_draft(_draft())
    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=compiled.question,
        reasons=[],
        unavailable=[],
    )
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={"TENNIS_G1": [_ts_point("2026-06-18T12:00:30Z")]},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"result": "yes", "internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["tennis"]["layers"]["pit_point_state"]["status"] == NO_POINT_DATA
    assert out["mlb"] is None


def test_nba_execute_does_not_grow_a_tennis_block():
    from tests.test_research_query_engine import _q
    from roller.research_query.models import TouchOrdinal

    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    compiled = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    out = execute_compiled(
        compiled,
        ticker_payloads={"KXNBAGAME-X": [_candle(0, 7900), _candle(1, 8000)]},
        pbp_by_game={},
        markets_by_ticker={"KXNBAGAME-X": {"result": "yes", "internal_game_id": "G1"}},
        games=[{"internal_game_id": "G1", "league": "NBA", "sport": "NBA"}],
    )
    assert out.get("tennis") is None
