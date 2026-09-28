"""Same-N win/loss rates and pre-fee binary breakeven. Does not invent fills."""

from __future__ import annotations

from types import SimpleNamespace

from roller.research_query.measurements import measure_rows
from roller.results_math.analyze import analyze_result
from roller.results_math.last_trade_display import last_trade_results_contract
from roller.results_math.models import HYPOTHETICAL, UNAVAILABLE
from roller.results_math.payoff import binary_trade_on_n, decompose_on_n
from roller.results_math.results_contract import results_contract

from tests.test_last_trade_results import mlb_1661_envelope


def _q(*, entry_e4: int = 7000, win_e4: int | None = None, loss_e4: int | None = None):
    paths = []
    if win_e4 is not None:
        paths.append(SimpleNamespace(outcome=SimpleNamespace(value="WIN"), price_e4=win_e4, op="HOLD"))
    if loss_e4 is not None:
        paths.append(SimpleNamespace(outcome=SimpleNamespace(value="LOSS"), price_e4=loss_e4, op="REACH"))
    return SimpleNamespace(
        entry_conditions=[SimpleNamespace(price_e4=entry_e4)],
        path_conditions=paths,
    )


def test_binary_trade_on_n_same_denominator():
    out = binary_trade_on_n(win_n=2130, n=2985, entry_cents=70)
    assert out["status"] == HYPOTHETICAL
    assert out["n"] == 2985
    assert out["win_n"] == 2130
    assert out["p_win"] == 2130 / 2985
    assert out["breakeven_probability"] == 0.70
    assert abs(out["ev_cents"] - (100 * 2130 / 2985 - 70)) < 1e-9
    assert abs(out["rate_margin_vs_breakeven"] - (2130 / 2985 - 0.70)) < 1e-9


def test_binary_trade_missing_entry_unavailable():
    out = binary_trade_on_n(win_n=10, n=20, entry_cents=None)
    assert out["status"] == UNAVAILABLE


def test_decompose_on_n_residual_is_not_loss():
    out = decompose_on_n(
        win_n=2130,
        loss_n=819,
        n=2985,
        win_payoff_cents=30,
        loss_payoff_cents=-45,
    )
    assert out["status"] == HYPOTHETICAL
    assert out["denominator"] == 2985
    assert out["win_probability"] == 2130 / 2985
    assert out["loss_probability"] == 819 / 2985
    residual = 2985 - 2130 - 819
    assert residual == 36
    assert abs(out["win_probability"] + out["loss_probability"] - (2949 / 2985)) < 1e-12


def test_measure_rows_win_on_n_uses_population_n():
    rows = (
        [{"path_true": True, "exit_outcome": "WIN_EXIT", "terminal_yes": None} for _ in range(2130)]
        + [{"path_true": False, "exit_outcome": "LOSS_EXIT", "terminal_yes": None} for _ in range(819)]
        + [{"path_true": False, "exit_outcome": None, "terminal_yes": None} for _ in range(36)]
    )
    m = measure_rows(rows)
    assert m["n"] == 2985
    assert m["win_exit"] == 2130
    assert m["loss_exit"] == 819
    assert m["win_on_n"] == 2130 / 2985
    assert m["loss_on_n"] == 819 / 2985
    assert m["win_exit_rate"] == 2130 / 2949


def test_last_trade_analyze_exposes_pre_fee_breakeven():
    rows = [
        {"path_true": True, "exit_outcome": "WIN_EXIT", "win_exit": True, "price_basis": "LAST_TRADE_PRINT"}
        for _ in range(2130)
    ] + [
        {
            "path_true": False,
            "exit_outcome": "LOSS_EXIT",
            "loss_exit": True,
            "entry_close": 7000,
            "exit_close": 2500,
            "price_basis": "LAST_TRADE_PRINT",
        }
        for _ in range(819)
    ]
    out = analyze_result(
        rows,
        last_trade=True,
        question=_q(entry_e4=7000, loss_e4=2500),
        metrics={"win_exit": 2130, "loss_exit": 819, "path_true": 2130, "path_available": 2949},
    )
    assert out["observed_ev"]["status"] == UNAVAILABLE
    be = out["trade_breakeven"]
    assert be["status"] == HYPOTHETICAL
    assert be["entry_cents"] == 70
    assert be["breakeven_probability"] == 0.70
    assert be["n"] == 2949
    assert be["p_win"] == 2130 / 2949
    contract = out["results_contract"]
    assert contract["economics"]["trade_breakeven"]["breakeven_probability"] == 0.70
    assert contract["economics"]["observed_path_ev"]["status"] == UNAVAILABLE
    assert contract["economics"]["book_price_ev"]["status"] == UNAVAILABLE


def test_last_trade_book_price_when_both_chips_exist():
    rows = [
        {"path_true": True, "exit_outcome": "WIN_EXIT", "win_exit": True, "price_basis": "LAST_TRADE_PRINT"}
        for _ in range(2)
    ] + [
        {"path_true": False, "exit_outcome": "LOSS_EXIT", "loss_exit": True, "price_basis": "LAST_TRADE_PRINT"}
        for _ in range(1)
    ]
    out = analyze_result(
        rows,
        last_trade=True,
        question=_q(entry_e4=7000, win_e4=10000, loss_e4=2500),
        metrics={"win_exit": 2, "loss_exit": 1, "path_true": 2, "path_available": 3},
    )
    book = out["book_price"]
    assert book["status"] == HYPOTHETICAL
    assert book["n"] == 3
    assert book["win_probability"] == 2 / 3
    assert book["loss_probability"] == 1 / 3
    assert out["observed_ev"]["status"] == UNAVAILABLE


def test_1661_envelope_n_and_classified_rates_unchanged():
    env = mlb_1661_envelope()
    contract = last_trade_results_contract(env)
    rates = contract["rates"]
    assert rates["n"] == 1661
    assert rates["win_exit"] == 73
    assert rates["loss_exit"] == 379
    assert rates["classified"] == 452
    assert contract["observed_path_ev"]["status"] == UNAVAILABLE
    assert contract["break_even_cost"]["status"] == UNAVAILABLE
    raw = results_contract(env)
    assert raw["rates"]["win_on_n"]["value"] == 73 / 1661
    assert raw["rates"]["loss_on_n"]["value"] == 379 / 1661
    assert raw["economics"]["book_price_ev"]["status"] == UNAVAILABLE
