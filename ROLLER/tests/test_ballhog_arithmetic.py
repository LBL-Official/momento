"""Ballhog dual-leg arithmetic. Lock applies to every paired unit."""

from __future__ import annotations

from roller.ballhog.arithmetic import evaluate_candidate, lock_cents
from roller.ballhog.policy import load_policy
from roller.ballhog.surface import build_surface


def test_lock_identity():
    assert lock_cents(35) == -15
    assert lock_cents(45) == -25
    assert lock_cents(20) == 0


def test_q0_equals_n_times_austin_alpha():
    row = evaluate_candidate(
        q_dir=7,
        q_hedge=0,
        hedge_price_cents=40,
        a_t=12.5,
        a_l=3.0,
        weighted_t40_rate=0.4,
        research_unit_qty=1,
    )
    assert row["portfolio_EV_after"] == 7 * 12.5
    assert row["robust_portfolio_EV_after"] == 7 * 3.0
    assert row["economic_EV_cost_of_hedge"] == 0
    assert row["q_hedge"] == 0
    assert row["rho"] == 0.0
    assert row["residual_qty"] == 7
    assert row["fill_claimed"] is False


def test_full_hedge_equals_n_times_lock():
    p = 40
    n = 7
    row = evaluate_candidate(
        q_dir=n,
        q_hedge=n,
        hedge_price_cents=p,
        a_t=12.5,
        a_l=3.0,
        weighted_t40_rate=0.4,
    )
    assert row["portfolio_EV_after"] == n * (20 - p)
    assert row["robust_portfolio_EV_after"] == n * (20 - p)
    assert row["rho"] == 1.0
    assert row["residual_qty"] == 0


def test_partial_q_uses_both_slices():
    n, q, p, a_t = 10, 4, 35, 8.0
    row = evaluate_candidate(
        q_dir=n,
        q_hedge=q,
        hedge_price_cents=p,
        a_t=a_t,
        a_l=2.0,
        weighted_t40_rate=0.5,
    )
    unpaired = (n - q) * a_t
    paired = q * (20 - p)
    assert row["directional_alpha_exposure_retained"] == unpaired
    assert row["paired_lock_value"] == paired
    assert row["portfolio_EV_after"] == unpaired + paired
    assert row["economic_EV_cost_of_hedge"] == n * a_t - (unpaired + paired)
    assert row["rho"] == 0.4


def test_negative_economic_cost_is_not_clamped():
    row = evaluate_candidate(
        q_dir=1,
        q_hedge=1,
        hedge_price_cents=35,
        a_t=-20.0,
        a_l=-25.0,
        weighted_t40_rate=0.6,
    )
    assert row["economic_EV_cost_of_hedge"] == -20.0 - (20 - 35)
    assert row["economic_EV_cost_of_hedge"] < 0


def test_replay_default_q_dir_is_binary():
    policy = load_policy()
    surface = build_surface(
        q_dir=1,
        a_t=6.0,
        a_l=1.0,
        weighted_t40_rate=0.3,
        policy=policy,
        research_unit_qty=1,
    )
    qs = {int(cell["q_hedge"]) for cell in surface["cells"]}
    assert qs == {0, 1}
    rhos = {cell["rho"] for cell in surface["cells"]}
    assert rhos == {0.0, 1.0}
    prices = {cell["hedge_price_cents"] for cell in surface["cells"] if cell["q_hedge"]}
    assert prices == set(range(35, 46))
    zero = next(cell for cell in surface["cells"] if cell["q_hedge"] == 0)
    assert zero["hedge_price_cents"] is None
    assert zero["price_relevant"] is False
    assert surface["fill_claimed"] is False
    assert surface["execution_assumption"] == "THEORETICAL"
    assert surface["current_hedge_price"] == "UNAVAILABLE"


def test_q0_cell_price_is_not_relevant():
    row = evaluate_candidate(
        q_dir=3,
        q_hedge=0,
        hedge_price_cents=40,
        a_t=10.0,
        a_l=4.0,
        weighted_t40_rate=0.3,
    )
    assert row["price_relevant"] is False
    assert row["is_robust_positive"] is True
    assert row["austin_alpha_per_unit"] == 10.0
    assert row["portfolio_ev_before"] == 30.0


def test_identity_q_dir_100_partial_25_at_35():
    a_t = 14.26
    row = evaluate_candidate(
        q_dir=100,
        q_hedge=25,
        hedge_price_cents=35,
        a_t=a_t,
        a_l=4.0,
        weighted_t40_rate=0.4,
    )
    assert row["portfolio_EV_after"] == 75 * a_t + 25 * (-15)
    assert row["paired_lock_cents"] == -15
    assert row["fill_claimed"] is False
    assert row["price_relevant"] is True


def test_explicit_q_dir_100_enumerates_zero_through_n():
    policy = load_policy()
    surface = build_surface(
        q_dir=100,
        a_t=6.0,
        a_l=1.0,
        weighted_t40_rate=0.3,
        policy=policy,
        research_unit_qty=1,
    )
    qs = sorted({int(cell["q_hedge"]) for cell in surface["cells"]})
    assert qs == list(range(0, 101))
    assert surface["research_unit_qty"] == 1
    assert surface["q_dir"] == 100
    hedge_cells = [cell for cell in surface["cells"] if cell["q_hedge"]]
    assert {cell["hedge_price_cents"] for cell in hedge_cells} == set(range(35, 46))
    assert all(cell["fill_claimed"] is False for cell in surface["cells"])
    assert all("alpha surrendered" not in str(cell).lower() for cell in surface["cells"])
