"""Universal Results contract. Basis-aware. No sport branches. No query re-run."""

from __future__ import annotations

from pathlib import Path

from roller.results_math.analyze import analyze_result
from roller.results_math.exposure import GAME, MULTI_ENTRY_PER_GAME, TICKER, TEAM, EVENT, verify_exposure
from roller.results_math.models import (
    CARDINALITY_VIOLATION,
    HYPOTHETICAL,
    INCOMPLETE,
    NOT_APPLICABLE,
    OBSERVED,
    UNAVAILABLE,
    UNVERIFIED,
)
from roller.results_math.results_contract import (
    LAST_TRADE_UNAVAILABLE,
    MODE_LAST_TRADE,
    MODE_TRADABLE,
    is_exact_model_a_8040,
    results_contract,
)
from tests.fixtures.results_contract.envelopes import (
    mlb_last_trade_1661,
    mlb_last_trade_554,
    nba_8040_candle,
    ncaab_8040_candle,
    tennis_candle,
    tennis_last_trade,
    wnba_8040_candle,
)

CONTRACT_SRC = Path(__file__).resolve().parents[1] / "roller" / "results_math" / "results_contract.py"


def _q(entry_e4: int, loss_e4: int):
    class _Q:
        entry_conditions = [type("E", (), {"price_e4": entry_e4})()]
        path_conditions = [type("P", (), {"op": type("O", (), {"value": "REACH"})(), "price_e4": loss_e4})()]

    return _Q()


def test_no_sport_or_league_branches_in_contract_source():
    src = CONTRACT_SRC.read_text(encoding="utf-8")
    for token in ("NBA", "NCAAB", "WNBA", "MLB", "Tennis", "ATP", "WTA"):
        assert token not in src


def test_mlb_1661_last_trade_rates_and_unavailable_economics():
    c = results_contract(mlb_last_trade_1661())
    assert c["economic_mode"] == MODE_LAST_TRADE
    counts = c["rates"]["counts"]
    assert counts["n"] == 1661
    assert counts["n_entry"] == 1846
    assert counts["path_true"] == 73
    assert counts["path_false"] == 1588
    assert counts["win_exit"] == 73
    assert counts["loss_exit"] == 379
    assert counts["classified"] == 452
    assert counts["terminal_yes"] == 79
    assert counts["terminal_no"] == 16
    assert counts["settled"] == 95
    assert counts["terminal_missing"] == 1566
    assert c["rates"]["path_rate"]["value"] == 73 / 1661
    assert c["rates"]["classified_win_rate"]["value"] == 73 / 452
    assert c["rates"]["classified_loss_rate"]["value"] == 379 / 452
    assert c["rates"]["terminal_yes_rate"]["value"] == 79 / 95
    assert c["rates"]["terminal_coverage"]["value"] == 95 / 1661
    assert c["economics"]["observed_path_ev"]["status"] == UNAVAILABLE
    assert LAST_TRADE_UNAVAILABLE in c["economics"]["observed_path_ev"]["reason"]
    assert c["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE
    assert c["economics"]["capitalization"]["status"] == UNAVAILABLE
    assert c["economics"]["sharpe"]["status"] == UNAVAILABLE
    assert c["economics"]["settlement_ev"]["status"] == INCOMPLETE
    assert c["exposure"]["status"] == UNVERIFIED
    assert c["exposure"]["declared_unit"] == GAME
    assert c["exposure"]["exposure_unit"] == GAME
    assert c["exposure"]["max_entries_per_game"] == 1
    assert c["exposure"]["source"] == "strategy_default"
    assert c["exposure"]["execution_enforced"] is False
    assert c["invariants"]["path_false_is_not_loss"] is True
    assert c["invariants"]["strategy_game_exposure_verified"] is False


def test_mlb_554_n_unchanged():
    c = results_contract(mlb_last_trade_554())
    assert c["rates"]["counts"]["n"] == 554
    assert c["rates"]["counts"]["path_true"] == 59
    assert c["rates"]["counts"]["loss_exit"] == 159
    assert c["rates"]["counts"]["settled"] == 84
    assert c["economic_mode"] == MODE_LAST_TRADE
    assert c["economics"]["observed_path_ev"]["status"] == UNAVAILABLE


def test_nba_ncaab_wnba_8040_same_economic_mode():
    nba = results_contract(nba_8040_candle())
    ncaab = results_contract(ncaab_8040_candle())
    wnba = results_contract(wnba_8040_candle())
    for c in (nba, ncaab, wnba):
        assert c["economic_mode"] == MODE_TRADABLE
        assert c["economics"]["model_a_8040_ev"]["status"] == HYPOTHETICAL
        assert c["economics"]["model_a_8040_ev"]["eligible"] is True
        assert c["economics"]["model_a_8040_ev"]["formula"].startswith("EV_cents = 20 - 60q")
        assert c["economics"]["settlement_ev"]["status"] == INCOMPLETE
    assert abs(nba["economics"]["model_a_8040_ev"]["estimate_cents"] - (20 - 60 * (4 / 12))) < 1e-12
    assert nba["rates"]["counts"]["n"] == 12
    assert ncaab["rates"]["counts"]["n"] == 9
    assert wnba["economic_mode"] == nba["economic_mode"]


def test_tennis_candle_is_tradable_not_last_trade():
    c = results_contract(tennis_candle())
    assert c["economic_mode"] == MODE_TRADABLE
    assert c["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE
    assert c["economics"]["settlement_ev"]["status"] == INCOMPLETE
    assert c["rates"]["counts"]["n"] == 8


def test_tennis_last_trade_same_contract_as_mlb():
    c = results_contract(tennis_last_trade())
    assert c["economic_mode"] == MODE_LAST_TRADE
    assert c["economics"]["observed_path_ev"]["status"] == UNAVAILABLE
    assert c["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE
    assert c["economics"]["settlement_ev"]["status"] == INCOMPLETE
    assert c["print_displacement"] is None or c["print_displacement"].get("feeds_population_ev") is False


def test_cross_basis_poison_last_trade_rows_cannot_become_population_ev():
    rows = [
        {
            "bid": 8000,
            "entry_close": 8000,
            "exit_close": 2313,
            "hyp_pnl_cents": -56.87,
            "loss_exit": True,
            "price_basis": "LAST_TRADE_PRINT",
            "internal_game_id": f"G{i}",
        }
        for i in range(5)
    ]
    out = analyze_result(rows, last_trade=True, metrics={"win_exit": 0, "loss_exit": 5, "path_true": 0, "path_available": 5})
    c = out["results_contract"]
    assert c["economic_mode"] == MODE_LAST_TRADE
    assert c["economics"]["observed_path_ev"]["status"] == UNAVAILABLE
    assert c["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE
    assert c["economics"]["sharpe"]["status"] == UNAVAILABLE
    assert c["economics"]["capitalization"]["status"] == UNAVAILABLE
    assert out["print_displacement"]["feeds_population_ev"] is False
    assert out["print_displacement"]["n"] == 5
    assert out["observed_ev"].get("estimate_cents") is None


def test_terminal_poison_missing_is_not_no():
    env = nba_8040_candle()
    env["summary"]["population_n"] = 100
    env["population"]["count"] = 100
    env["identity"].update(
        {
            "reported_n": 100,
            "path_true": 20,
            "path_false": 80,
            "terminal_yes": 10,
            "terminal_no": 10,
            "terminal_missing": 80,
        }
    )
    env["measurements"] = [
        {"name": "path_rate", "value": 0.2, "detail": {"count_true": 20, "count_available": 100}},
        {"name": "win_exit_rate", "value": 0.4, "detail": {"count_true": 20, "count_available": 50}},
        {"name": "loss_exit_rate", "value": 0.6, "detail": {"count_true": 30, "count_available": 50}},
        {"name": "kalshi_yes_rate", "value": 0.5, "detail": {"count_true": 10, "count_available": 20}},
    ]
    c = results_contract(env)
    assert c["rates"]["terminal_yes_rate"]["value"] == 10 / 20
    assert c["rates"]["terminal_coverage"]["value"] == 20 / 100
    assert c["rates"]["terminal_missing_rate"]["value"] == 80 / 100
    assert c["economics"]["settlement_ev"]["status"] == INCOMPLETE
    assert c["rates"]["terminal_yes_rate"]["value"] != 10 / 100


def test_path_poison_path_false_is_not_loss():
    env = nba_8040_candle()
    env["summary"]["population_n"] = 100
    env["population"]["count"] = 100
    env["identity"].update(
        {
            "reported_n": 100,
            "path_true": 20,
            "path_false": 80,
            "terminal_yes": 0,
            "terminal_no": 0,
            "terminal_missing": 100,
        }
    )
    env["measurements"] = [
        {"name": "path_rate", "value": 0.2, "detail": {"count_true": 20, "count_available": 100}},
        {"name": "win_exit_rate", "value": 0.4, "detail": {"count_true": 20, "count_available": 50}},
        {"name": "loss_exit_rate", "value": 0.6, "detail": {"count_true": 30, "count_available": 50}},
    ]
    c = results_contract(env)
    assert c["rates"]["path_rate"]["value"] == 20 / 100
    assert c["rates"]["classified_win_rate"]["value"] == 20 / 50
    assert c["rates"]["classified_loss_rate"]["value"] == 30 / 50
    assert c["rates"]["counts"]["path_false"] == 80
    assert c["rates"]["counts"]["loss_exit"] == 30
    assert c["invariants"]["path_false_is_not_loss"] is True


def test_hold_poison_win_exit_close_none_is_valid():
    rows = [
        {
            "win_exit": True,
            "path_true": True,
            "entry_close": 8000,
            "exit_close": None,
            "hyp_pnl_cents": None,
            "price_basis": "LAST_TRADE_PRINT",
            "internal_game_id": "G1",
        }
    ]
    out = analyze_result(rows, last_trade=True)
    assert out["print_displacement"]["win_hold_no_exit"] == 1
    assert out["observed_ev"]["status"] == UNAVAILABLE
    assert out["results_contract"]["hold"]["exit_close_null_is_valid_for_win_hold"] is True


def test_model_a_poison_only_tradable_exact_8040():
    assert is_exact_model_a_8040(_q(8000, 4000)) is True
    assert is_exact_model_a_8040(_q(7500, 4000)) is False
    assert is_exact_model_a_8040(_q(8000, 3500)) is False
    tradable = analyze_result(
        [{"hyp_pnl_cents": 10, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "G1", "path_true": False}],
        last_trade=False,
        question=_q(8000, 4000),
        metrics={"path_true": 1, "path_available": 3, "win_exit": 0, "loss_exit": 1},
        identity={"reported_n": 1, "path_true": 1, "path_false": 0, "terminal_yes": 0, "terminal_no": 0, "terminal_missing": 1},
    )
    assert tradable["results_contract"]["economics"]["model_a_8040_ev"]["status"] == HYPOTHETICAL
    last = analyze_result(
        [{"entry_close": 8000, "exit_close": 4000, "loss_exit": True, "internal_game_id": "G1"}],
        last_trade=True,
        question=_q(8000, 4000),
    )
    assert last["results_contract"]["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE
    off = results_contract(tennis_candle())
    assert off["economics"]["model_a_8040_ev"]["status"] == NOT_APPLICABLE


def test_analyze_both_branches_emit_results_contract():
    last = analyze_result([], last_trade=True, identity={"reported_n": 2, "terminal_missing": 2})
    yes = analyze_result(
        [{"hyp_pnl_cents": 4, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "G1"}],
        last_trade=False,
    )
    assert last["results_contract"]["economic_mode"] == MODE_LAST_TRADE
    assert yes["results_contract"]["economic_mode"] == MODE_TRADABLE
    assert "rates" in last["results_contract"]
    assert "rates" in yes["results_contract"]


def test_cardinality_unverified_does_not_rewrite_n_1661():
    env = mlb_last_trade_1661()
    assert env["population"]["trades"] == []
    c = results_contract(env)
    assert c["rates"]["counts"]["n"] == 1661
    assert c["exposure"]["status"] == UNVERIFIED
    assert c["exposure"]["n_equals_unique_games"] is None
    assert c["limitations"]["cardinality_unverified"] is True
    assert c["limitations"]["cardinality_violation"] is False


def test_cardinality_violation_fail_closes_strategy_statistics():
    rows = [
        {"internal_game_id": "G1", "hyp_pnl_cents": 10, "entry_ts": "2026-01-01T00:00:00Z", "path_true": False},
        {"internal_game_id": "G1", "hyp_pnl_cents": -20, "entry_ts": "2026-01-01T00:05:00Z", "path_true": True},
        {"internal_game_id": "G2", "hyp_pnl_cents": 5, "entry_ts": "2026-01-02T00:00:00Z", "path_true": False},
    ]
    out = analyze_result(rows, last_trade=False, question=_q(8000, 4000))
    c = out["results_contract"]
    assert c["exposure"]["status"] == CARDINALITY_VIOLATION
    assert c["exposure"]["strategy_statistics_permitted"] is False
    assert c["exposure"]["max_trades_per_game"] == 2
    assert "G1" in c["exposure"]["duplicate_games"]
    assert c["economics"]["observed_path_ev"]["status"] == CARDINALITY_VIOLATION
    assert c["economics"]["model_a_8040_ev"]["status"] == CARDINALITY_VIOLATION
    assert c["economics"]["capitalization"]["status"] == CARDINALITY_VIOLATION
    assert c["rates"]["counts"]["n"] == 3


def test_one_game_one_trade_verified_when_unique():
    rows = [
        {"internal_game_id": "G1", "hyp_pnl_cents": 10, "entry_ts": "2026-01-01T00:00:00Z"},
        {"internal_game_id": "G2", "hyp_pnl_cents": -8, "entry_ts": "2026-01-02T00:00:00Z"},
    ]
    out = analyze_result(rows, last_trade=False)
    exp = out["results_contract"]["exposure"]
    assert exp["status"] == OBSERVED
    assert exp["n_unique_games"] == 2
    assert exp["n_equals_unique_games"] is True
    assert exp["strategy_statistics_permitted"] is True
    assert out["results_contract"]["economics"]["observed_path_ev"]["status"] == OBSERVED


def test_explicit_multi_entry_unit_is_not_a_violation():
    rows = [
        {"internal_game_id": "G1", "hyp_pnl_cents": 1},
        {"internal_game_id": "G1", "hyp_pnl_cents": 2},
    ]
    exp = verify_exposure(rows=rows, n=2, declared=MULTI_ENTRY_PER_GAME)
    assert exp["status"] == OBSERVED
    assert exp["strategy_statistics_permitted"] is True
    env = nba_8040_candle()
    env["exposure_unit"] = MULTI_ENTRY_PER_GAME
    env["population"]["trades"] = rows
    c = results_contract(env)
    assert c["exposure"]["declared_unit"] == MULTI_ENTRY_PER_GAME
    assert c["exposure"]["status"] == OBSERVED
    assert c["economics"]["observed_path_ev"]["status"] != CARDINALITY_VIOLATION


def test_n_not_equal_unique_games_is_violation():
    rows = [{"internal_game_id": "G1"}, {"internal_game_id": "G2"}]
    exp = verify_exposure(rows=rows, n=5, declared=GAME)
    assert exp["status"] == CARDINALITY_VIOLATION
    assert exp["n_unique_games"] == 2
    assert exp["n_equals_unique_games"] is False


def test_declared_ticker_unit_is_not_game_cardinality():
    rows = [
        {"ticker": "A", "internal_game_id": "G1"},
        {"ticker": "B", "internal_game_id": "G1"},
    ]
    exp = verify_exposure(rows=rows, n=2, declared=TICKER)
    assert exp["status"] == OBSERVED
    assert exp["declared_unit"] == TICKER
    assert exp["n_unique_tickers"] == 2
    assert exp["strategy_statistics_permitted"] is True


def test_declared_team_and_event_units():
    teams = verify_exposure(
        rows=[{"team_id": "NYY"}, {"team_id": "BOS"}],
        n=2,
        declared=TEAM,
    )
    assert teams["status"] == OBSERVED
    assert teams["declared_unit"] == TEAM
    events = verify_exposure(
        rows=[{"event_ticker": "E1"}, {"event_ticker": "E1"}],
        n=2,
        declared=EVENT,
    )
    assert events["status"] == CARDINALITY_VIOLATION
    assert events["declared_unit"] == EVENT


def test_legacy_one_game_alias_normalizes_to_game():
    exp = verify_exposure(rows=[{"internal_game_id": "G1"}], n=1, declared="ONE_GAME_ONE_TRADE")
    assert exp["exposure_unit"] == GAME
    assert exp["max_entries_per_unit"] == 1
    assert exp["status"] == OBSERVED
