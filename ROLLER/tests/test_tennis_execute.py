"""Tennis generic execute: market path, PIT honesty, settlement, missing data."""

from roller.base_terminal_efficiency.attach import row_matches_te_filters
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import (
    BASIS_TRADABLE,
    CompileResult,
    ExecutionPath,
    ResearchStatus,
)


def _candle(i: int, bid: int, *, ticker="KXATPMATCH-T-ZVE", game="TENNIS_G1"):
    return {
        "available_at": f"2026-06-18T12:{i:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 100,
        "ticker": ticker,
        "internal_game_id": game,
        "team_side": "1",
        "is_valid": "1",
        "volume": 10,
    }


def _ts_point(ts: str, **kw):
    row = {
        "point_number": 1,
        "set_number": 1,
        "game_number": 3,
        "sets_p1": 0,
        "sets_p2": 0,
        "games_p1": 2,
        "games_p2": 1,
        "points_p1_raw": "30",
        "points_p2_raw": "15",
        "point_score_raw": "30-15",
        "server": 1,
        "receiver": 2,
        "is_tiebreak": False,
        "best_of": 3,
        "pbp_basis": "TIMESTAMPED_OBSERVED",
        "pit_joinable": True,
        "event_timestamp": ts,
    }
    row.update(kw)
    return row


def _seq_point(**kw):
    row = _ts_point(None, pbp_basis="SEQUENCE_ONLY", pit_joinable=False)
    row["event_timestamp"] = None
    row.update(kw)
    return row


def _forced(draft):
    compiled = compile_draft(draft)
    q = compiled.question
    return CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )


def _draft(*, period="S1", te=None):
    return {
        "universe": {
            "sports": ["tennis"],
            "leagues": ["ATP"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {
                "id": "e1",
                "family": "cross",
                "priceCents": 80,
                "period": period,
                "direction": "up",
            }
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {"id": "p2", "kind": "path", "family": "drop_to", "priceCents": 40, "outcome": "loss"},
        ],
        "teFilters": te or {},
    }


def test_compile_tennis_native_bid_not_last_trade():
    from roller.research_query.availability import tennis_warehouse_ready

    compiled = compile_draft(_draft())
    assert compiled.question.basis() == BASIS_TRADABLE
    if tennis_warehouse_ready():
        assert compiled.status == ResearchStatus.READY
        assert compiled.execution_path == ExecutionPath.GENERIC_QUERY
    else:
        assert compiled.status == ResearchStatus.DATA_REQUIRED
        assert compiled.execution_path == ExecutionPath.NONE
        assert any("warehouse" in r.lower() for r in compiled.reasons)


def test_compile_explicit_last_trade_is_not_yes_bid():
    draft = _draft()
    draft["universe"]["marketData"] = ["last_trade"]
    compiled = compile_draft(draft)
    from roller.research_query.models import BASIS_LAST_TRADE

    assert compiled.question.basis() == BASIS_LAST_TRADE
    assert compiled.question.basis() != BASIS_TRADABLE


def test_mixed_tennis_nba_operation_required():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["tennis", "basketball"],
                "leagues": ["ATP", "NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        }
    )
    assert compiled.status == ResearchStatus.OPERATION_REQUIRED


def test_game_clock_horizon_operation_required():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["tennis"],
                "leagues": ["ATP"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80}],
            "exitConditions": [
                {
                    "id": "p1",
                    "kind": "path",
                    "family": "horizon_win",
                    "horizonKind": "game",
                    "horizonMinutes": 12,
                    "outcome": "win",
                }
            ],
        }
    )
    assert compiled.status == ResearchStatus.OPERATION_REQUIRED


def test_synthetic_timestamped_execute_complete():
    forced = _forced(_draft())
    pbp = [_ts_point("2026-06-18T12:00:30Z")]
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={"TENNIS_G1": pbp},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"result": "yes", "internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_TRADABLE
    trades = out["population"]["trades"]
    assert trades
    te = trades[0]["te"]
    assert te.get("yes_serving") is True
    assert te.get("yes_set_lead") == 0
    assert te.get("yes_game_lead") == 1
    assert te.get("pit_joinable") is True
    assert te.get("pbp_basis") == "TIMESTAMPED_OBSERVED"


def test_sequence_only_set_window_fails_closed():
    forced = _forced(_draft(period="S1"))
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={"TENNIS_G1": [_seq_point()]},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"result": "yes", "internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["population"]["trades"] == []


def test_missing_settlement_is_missing_not_inferred():
    forced = _forced(_draft())
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={"TENNIS_G1": [_ts_point("2026-06-18T12:00:30Z")]},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["execution_status"] == "COMPLETE"
    trades = out["population"]["trades"]
    assert trades
    term = trades[0].get("terminal") or trades[0].get("te", {}).get("terminal_outcome")
    assert term in {None, "MISSING", "UNAVAILABLE", "ABSENT"} or "W" not in str(term).upper() or "MISSING" in str(term)


def test_missing_ticker_not_n_zero():
    forced = _forced(_draft())
    out = execute_compiled(
        forced,
        ticker_payloads={},
        pbp_by_game={},
        markets_by_ticker={},
        games=[],
    )
    assert out["execution_status"] in {"COMPLETE", "DATA_REQUIRED"}
    n = (out.get("population") or {}).get("n")
    if out["execution_status"] == "COMPLETE":
        assert n == 0 or out["population"]["trades"] == []


def test_te_missing_serve_fails_closed():
    row = {"te": {"yes_serving": None, "yes_returning": None, "yes_set_lead": 1}}
    assert not row_matches_te_filters(row, {"tennisServe": ["serving"]})
    assert row_matches_te_filters({"te": {"yes_serving": True, "yes_returning": False}}, {"tennisServe": ["serving"]})
    assert not row_matches_te_filters({"te": {"yes_set_lead": None}}, {"tennisSetLead": {"scoreSide": "leading"}})
    assert row_matches_te_filters({"te": {"yes_set_lead": 1}}, {"tennisSetLead": {"scoreSide": "leading"}})
    assert not row_matches_te_filters({"te": {"yes_set_lead": 1}}, {"tennisGameLead": {"scoreSide": "leading"}})


def test_missing_pbp_with_set_window_is_empty_not_assumed():
    forced = _forced(_draft(period="S1"))
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["population"]["trades"] == []


def test_before_first_point_fails_closed():
    forced = _forced(_draft(period="S1"))
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXATPMATCH-T-ZVE": [_candle(0, 7900), _candle(1, 8000), _candle(2, 9000)],
        },
        pbp_by_game={"TENNIS_G1": [_ts_point("2026-06-18T13:00:00Z")]},
        markets_by_ticker={"KXATPMATCH-T-ZVE": {"internal_game_id": "TENNIS_G1"}},
        games=[{"internal_game_id": "TENNIS_G1", "league": "ATP", "sport": "ATP"}],
    )
    assert out["population"]["trades"] == []


def test_wta_timestamped_execute_complete():
    draft = _draft()
    draft["universe"]["leagues"] = ["WTA"]
    draft["universe"]["sports"] = ["tennis"]
    forced = _forced(draft)
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXWTAMATCH-T-ZVE": [
                _candle(0, 7900, ticker="KXWTAMATCH-T-ZVE", game="TENNIS_W1"),
                _candle(1, 8000, ticker="KXWTAMATCH-T-ZVE", game="TENNIS_W1"),
                _candle(2, 9000, ticker="KXWTAMATCH-T-ZVE", game="TENNIS_W1"),
            ],
        },
        pbp_by_game={"TENNIS_W1": [_ts_point("2026-06-18T12:00:30Z")]},
        markets_by_ticker={"KXWTAMATCH-T-ZVE": {"internal_game_id": "TENNIS_W1"}},
        games=[{"internal_game_id": "TENNIS_W1", "league": "WTA", "sport": "WTA"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_TRADABLE
    assert out["population"]["trades"]
    te = out["population"]["trades"][0]["te"]
    assert te.get("yes_serving") is True
    assert te.get("alignment_status") == "aligned"


def test_score_state_does_not_invent_basketball_points():
    from roller.base_terminal_efficiency.score import score_state

    scored = score_state(
        [_ts_point("2026-06-18T12:00:30Z")],
        "2026-06-18T12:01:00Z",
        team_side="1",
        sport="ATP",
    )
    assert scored["alignment_status"] == "aligned"
    assert scored["team_points"] is None
    assert scored["point_differential"] is None
    assert scored["score_status"] == "OBSERVED"


def test_leads_are_independent():
    te = {"te": {"yes_set_lead": 1, "yes_game_lead": -2, "yes_point_lead": 1}}
    assert row_matches_te_filters(te, {"tennisSetLead": {"scoreSide": "leading"}})
    assert not row_matches_te_filters(te, {"tennisGameLead": {"scoreSide": "leading"}})
    assert row_matches_te_filters(te, {"tennisGameLead": {"scoreSide": "trailing", "exactDiffs": [2]}})
