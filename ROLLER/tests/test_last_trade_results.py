"""Results-layer contract for LAST_TRADE_PRINT. Does not change query N or TE."""

from __future__ import annotations

from roller.results_math.analyze import analyze_result
from roller.results_math.last_trade_display import (
    LAST_TRADE_UNAVAILABLE,
    is_last_trade_print,
    last_trade_results_contract,
    print_displacement,
)
from roller.results_math.models import INCOMPLETE, UNAVAILABLE
from roller.results_math.observations import normalize_row


def mlb_1661_envelope() -> dict:
    """Authoritative 1661 measurement identities. Counts are not to be 'fixed'."""
    return {
        "observation_basis": "LAST_TRADE_PRINT",
        "summary": {"population_n": 1661},
        "population": {"count": 1661, "trades": []},
        "provenance": {
            "market_data": "kalshi_1m_last_trade",
            "market_data_type": "LAST_TRADE_PRINT",
            "price_basis": "LAST_TRADE_PRINT",
            "price_rule": "last_trade_close_cross",
        },
        "identity": {
            "reported_n": 1661,
            "n_entry_events": 1846,
            "te_scope": {"n_entry": 1846, "n_scoped": 1661},
            "path_true": 73,
            "path_false": 1588,
            "terminal_yes": 79,
            "terminal_no": 16,
            "terminal_missing": 1566,
        },
        "measurements": [
            {
                "name": "path_rate",
                "value": 73 / 1661,
                "detail": {"count_true": 73, "count_available": 1661},
            },
            {
                "name": "win_exit_rate",
                "value": 73 / 452,
                "detail": {"count_true": 73, "count_available": 452},
            },
            {
                "name": "loss_exit_rate",
                "value": 379 / 452,
                "detail": {"count_true": 379, "count_available": 452},
            },
            {
                "name": "kalshi_yes_rate",
                "value": 79 / 95,
                "detail": {"count_true": 79, "count_available": 95},
            },
        ],
        "analysis": {
            "observed_returns": {
                "status": UNAVAILABLE,
                "reason": f"{LAST_TRADE_UNAVAILABLE}. No P&L / EV / Sharpe on this basis.",
            },
            "observed_path": {
                "status": UNAVAILABLE,
                "reason": f"{LAST_TRADE_UNAVAILABLE}. No P&L / EV / Sharpe on this basis.",
            },
        },
    }


def test_is_last_trade_print_from_envelope():
    assert is_last_trade_print(mlb_1661_envelope()) is True
    assert is_last_trade_print({"observation_basis": "YES_BID_CLOSE"}) is False


def test_no_yes_bid_population_ev():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["yes_bid_forbidden"] is True
    assert contract["candle_substitution_forbidden"] is True
    assert contract["tradable_bar_bid_is_not_yes_bid"] is True
    assert contract["observed_path_ev"]["status"] == UNAVAILABLE
    assert LAST_TRADE_UNAVAILABLE in contract["observed_path_ev"]["reason"]


def test_tradable_bar_bid_is_not_yes_bid():
    row = {
        "bid": 8000,
        "entry_close": 8000,
        "exit_close": 3500,
        "loss_exit": True,
        "price_basis": "LAST_TRADE_PRINT",
        "hyp_pnl_cents": None,
    }
    normalized = normalize_row(row, 0)
    assert normalized["entry_price_definition"] == "last_close_e4"
    assert "yes_bid" not in normalized["entry_price_definition"]
    out = analyze_result([row], last_trade=True)
    assert out["observed_ev"]["status"] == UNAVAILABLE
    assert out["observed_returns"]["status"] == UNAVAILABLE


def test_win_hold_to_expiration_exit_close_none():
    rows = [
        {
            "win_exit": True,
            "path_true": True,
            "entry_close": 8000,
            "exit_close": None,
            "hyp_pnl_cents": None,
            "price_basis": "LAST_TRADE_PRINT",
        }
    ]
    diag = print_displacement(rows)
    assert diag["win_hold_no_exit"] == 1
    assert diag["n"] == 0
    out = analyze_result(rows, last_trade=True)
    assert out["observed_ev"]["status"] == UNAVAILABLE
    assert out["print_displacement"]["win_hold_no_exit"] == 1


def test_loss_exit_print_is_valid_and_not_population_ev():
    rows = [
        {
            "loss_exit": True,
            "path_true": False,
            "entry_close": 8000,
            "exit_close": 2313,
            "hyp_pnl_cents": None,
            "price_basis": "LAST_TRADE_PRINT",
        }
    ]
    diag = print_displacement(rows)
    assert diag["n"] == 1
    assert diag["loss_with_exit"] == 1
    assert abs(diag["mean_cents"] - ((2313 - 8000) / 100.0)) < 1e-9
    assert diag["feeds_population_ev"] is False
    assert diag["feeds_capitalization"] is False
    assert diag["feeds_sharpe"] is False
    out = analyze_result(rows, last_trade=True)
    assert out["observed_ev"]["status"] == UNAVAILABLE
    assert out["print_displacement"]["feeds_population_ev"] is False


def test_loss_only_mean_cannot_become_population_ev():
    rows = [
        {
            "loss_exit": True,
            "entry_close": 8000,
            "exit_close": 2313,
            "price_basis": "LAST_TRADE_PRINT",
        }
        for _ in range(379)
    ] + [
        {
            "win_exit": True,
            "entry_close": 8000,
            "exit_close": None,
            "hyp_pnl_cents": None,
            "price_basis": "LAST_TRADE_PRINT",
        }
        for _ in range(73)
    ]
    out = analyze_result(
        rows,
        last_trade=True,
        identity={"terminal_yes": 79, "terminal_no": 16, "terminal_missing": 1566},
        metrics={"win_exit": 73, "loss_exit": 379, "path_true": 73, "path_available": 1661},
    )
    assert out["observed_ev"]["status"] == UNAVAILABLE
    assert out["observed_path_ev"]["status"] == UNAVAILABLE
    assert out["print_displacement"]["n"] == 379
    assert out["print_displacement"]["feeds_population_ev"] is False
    mean = out["print_displacement"]["mean_cents"]
    assert mean is not None
    assert out["observed_ev"].get("value") != mean
    assert out["observed_ev"].get("estimate_cents") is None


def test_observed_path_ev_unavailable_when_envelope_declares_it():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["observed_path_ev"]["status"] == UNAVAILABLE
    assert contract["observed_path_ev"]["server_status"] == UNAVAILABLE


def test_capitalized_path_unavailable():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["capitalized_path"]["status"] == UNAVAILABLE
    out = analyze_result([{"hyp_pnl_cents": None}], last_trade=True)
    assert out["capitalization"]["status"] == UNAVAILABLE


def test_sharpe_not_from_loss_only_prints():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["sharpe"]["status"] == UNAVAILABLE
    assert contract["invariants"]["loss_only_print_not_population_ev"] is True


def test_terminal_yes_is_79_of_95():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["terminal_yes"] == 79
    assert rates["settled"] == 95
    assert rates["terminal_yes"] / rates["settled"] == 79 / 95


def test_terminal_coverage_is_95_of_1661():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["settled"] == 95
    assert rates["n"] == 1661
    assert abs(rates["settled"] / rates["n"] - 95 / 1661) < 1e-12


def test_terminal_missing_remains_1566():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["terminal_missing"] == 1566
    assert rates["terminal_yes"] + rates["terminal_no"] + rates["terminal_missing"] == 1661


def test_path_rate_is_73_of_1661():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["path_true"] == 73
    assert rates["n"] == 1661
    assert rates["path_true"] != rates["classified"] or rates["classified"] == 452


def test_classified_win_is_73_of_452():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["win_exit"] == 73
    assert rates["classified"] == 452


def test_classified_loss_is_379_of_452():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["loss_exit"] == 379
    assert rates["win_exit"] + rates["loss_exit"] == rates["classified"]


def test_path_false_is_not_loss():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["path_false"] == 1588
    assert rates["loss_exit"] == 379
    assert rates["path_false"] != rates["loss_exit"]


def test_settlement_ev_incomplete():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["settlement_ev"]["status"] == INCOMPLETE
    out = analyze_result(
        [],
        last_trade=True,
        identity={"terminal_yes": 79, "terminal_no": 16, "terminal_missing": 1566},
    )
    assert out["settlement_payoff"]["status"] == INCOMPLETE
    assert out["settlement_payoff"]["terminal_missing"] == 1566


def test_no_candle_or_yes_bid_fields_fabricated():
    contract = last_trade_results_contract(mlb_1661_envelope())
    blob = str(contract)
    assert "yes_bid_close" not in blob
    assert "tradable_yes_bid" not in blob
    out = analyze_result(
        [{"entry_close": 8000, "exit_close": None, "win_exit": True, "price_basis": "LAST_TRADE_PRINT"}],
        last_trade=True,
    )
    assert out["economic_hurdle"]["break_even_total_cost_cents"] is None
    assert "yes_bid" not in str(out["observed_ev"]).lower()


def test_break_even_unavailable():
    contract = last_trade_results_contract(mlb_1661_envelope())
    assert contract["break_even_cost"]["status"] == UNAVAILABLE


def test_n_unchanged():
    rates = last_trade_results_contract(mlb_1661_envelope())["rates"]
    assert rates["n"] == 1661
    assert rates["n_entry"] == 1846
