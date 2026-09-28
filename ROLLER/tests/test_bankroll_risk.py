"""Bankroll & Risk Engine unit anchors. Does not change ConditionalBacktest."""

from __future__ import annotations

import pytest

from roller.risk.engine import run_risk
from roller.risk.formulas import (
    RiskConfigError,
    bankroll_loss_return,
    bankroll_win_return,
    break_even_probability,
    required_win_probability,
    target_ev_per_trade,
    trade_capital,
    trade_ev,
    weekly_ev,
    weekly_return_from_wins,
    weekly_volatility,
)
from roller.risk.simulation import simulate_mode_a


def test_break_even():
    assert break_even_probability(0.01, -0.02) == pytest.approx(2.0 / 3.0)
    assert break_even_probability(0.01, -0.02) == pytest.approx(0.666666667)


def test_target_probability():
    T_t = target_ev_per_trade(0.01, 10)
    assert required_win_probability(T_t, 0.01, -0.02) == pytest.approx(0.70)


def test_trade_and_weekly_ev():
    ev_t = trade_ev(0.70, 0.01, -0.02)
    assert ev_t == pytest.approx(0.001)
    assert weekly_ev(10, ev_t) == pytest.approx(0.01)
    assert trade_capital(20_000, 0.05) == 1000
    assert bankroll_win_return(0.05, 0.20) == pytest.approx(0.01)
    assert bankroll_loss_return(0.05, -0.40) == pytest.approx(-0.02)


def test_weekly_return_anchors():
    assert weekly_return_from_wins(7, 10, 0.01, -0.02) == pytest.approx(0.01)
    assert weekly_return_from_wins(6, 10, 0.01, -0.02) == pytest.approx(-0.02)
    assert weekly_return_from_wins(10, 10, 0.01, -0.02) == pytest.approx(0.10)
    assert weekly_return_from_wins(0, 10, 0.01, -0.02) == pytest.approx(-0.20)


def test_weekly_volatility():
    assert weekly_volatility(10, 0.70, 0.01, -0.02) == pytest.approx(0.0435, rel=0.01)


def test_static_weekly_sizing():
    payload = run_risk({"mode": "A", "seed": 1, "config": {"monte_carlo_paths": 200}})
    assert payload["static_weekly_sizing"] is True
    assert payload["monte_carlo"]["static_weekly_sizing"] is True
    assert payload["deterministic"]["capital_per_trade"] == 1000


def test_monte_carlo_converges_to_weekly_ev():
    sim = simulate_mode_a(
        {
            "initial_bankroll": 20_000,
            "trade_allocation": 0.05,
            "win_return": 0.20,
            "loss_return": -0.40,
            "win_probability": 0.70,
            "trades_per_week": 10,
            "target_weekly_ev": 0.01,
            "weeks_per_year": 52,
            "monte_carlo_paths": 20_000,
        },
        seed=20260913,
    )
    assert sim["mean_weekly_return"] == pytest.approx(0.01, abs=0.001)
    assert "mean" in sim["terminal_bankroll"]
    assert "median" in sim["terminal_bankroll"]


def test_invalid_inputs_fail_closed():
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"trades_per_week": 0}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"initial_bankroll": 0}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"win_probability": 1.2}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"trade_allocation": 1.5}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"target_weekly_ev": -0.01}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"monte_carlo_paths": 0}})
    with pytest.raises(RiskConfigError):
        run_risk({"config": {"win_return": -0.1, "loss_return": 0.2}})
    with pytest.raises(RiskConfigError):
        run_risk({"mode": "C", "probabilities": []})
    with pytest.raises(RiskConfigError):
        run_risk({"mode": "B"})


def test_mode_b_marks_costs_unavailable():
    payload = run_risk(
        {
            "mode": "B",
            "seed": 2,
            "classifications": ["WIN", "LOSS", "WIN", "MISSING_SETTLEMENT"],
            "config": {"monte_carlo_paths": 500},
        }
    )
    assert payload["monte_carlo"]["fees"] == "UNAVAILABLE"
    assert payload["monte_carlo"]["fills"] == "UNAVAILABLE"
    assert payload["costs"]["net_ev"] == "NOT_COMPUTABLE"
    assert payload["correlation"]["status"] == "CORRELATION_DATA_REQUIRED"
    assert payload["artifact"] == "risk_result"
    assert payload["research_result_hash"] == ""


def test_baseline_engine_numbers():
    payload = run_risk({"mode": "A", "seed": 3, "config": {"monte_carlo_paths": 200}})
    d = payload["deterministic"]
    assert d["capital_per_trade"] == 1000
    assert d["win_pnl"] == pytest.approx(200)
    assert d["loss_pnl"] == pytest.approx(-400)
    assert d["break_even_probability"] == pytest.approx(2.0 / 3.0)
    assert d["trade_ev"] == pytest.approx(0.001)
    assert d["trade_ev_dollars"] == pytest.approx(20)
    assert d["weekly_ev"] == pytest.approx(0.01)
    assert d["weekly_ev_dollars"] == pytest.approx(200)
    assert d["min_wins_for_target"] == 7
    assert len(d["weekly_table"]) == 11
