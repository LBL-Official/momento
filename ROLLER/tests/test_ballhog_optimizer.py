"""Frontier, timing, and two-stage risk_intent × hedge_feasibility. No lambda. No silent ties."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from roller.ballhog.frontier import build_frontier
from roller.ballhog.optimizer import decide
from roller.ballhog.policy import load_policy
from roller.ballhog.surface import build_surface
from roller.ballhog.timing import timing_decision
from roller.dre.pit import DrePitError, Stamped, assert_all_not_after


def _alpha(**overrides):
    body = {
        "availability": "OBSERVED",
        "a_t": 8.0,
        "a_l": 3.0,
        "ci_upper": 12.0,
        "ci_level": 0.95,
        "ci_method": "weighted_bootstrap",
        "support": "OBSERVED",
        "effective_sample_size": 40,
        "weighted_t40_rate": 0.35,
        "weighted_survival_rate": 0.65,
        "alpha_delta_from_entry": 0.5,
    }
    body.update(overrides)
    return body


def test_frontier_axes_are_cost_vs_t40_risk_proxy():
    policy = load_policy()
    surface = build_surface(
        q_dir=5,
        a_t=8.0,
        a_l=3.0,
        weighted_t40_rate=0.4,
        policy=policy,
    )
    frontier = build_frontier(list(surface["cells"]), require_positive_robust=True)
    assert frontier["axes"]["x"] == "economic_EV_cost_of_hedge"
    assert frontier["axes"]["y"] == "risk_removed"
    assert frontier["axes"]["y_metric"] == "T40_RISK_PROXY"
    for row in frontier["frontier"]:
        assert row["on_frontier"] is True
        assert row["is_frontier"] is True
        assert row["dominated"] is False


def test_retain_forces_q0_even_when_q_dir_100_has_many_positive_cells():
    policy = load_policy()
    decision = decide(q_dir=100, alpha=_alpha(a_l=5.0), policy=policy, research_unit_qty=1)
    assert decision["risk_intent"] == "RETAIN"
    assert decision["hedge_feasibility"] == "NOT_REQUESTED"
    assert decision["decision_status"] == "RESOLVED"
    assert decision["rho_star"] == 0.0
    assert decision["q_star"] == 0
    assert decision["delta_star"] == 100
    assert decision["timing"]["timing_state"] == "RETAIN"
    assert "POLICY_UNRESOLVED" not in decision["reason_codes"]
    assert decision["execution_enabled"] is False


def test_unique_q0_when_one_contract_and_robust_positive():
    policy = load_policy()
    decision = decide(q_dir=1, alpha=_alpha(), policy=policy, research_unit_qty=1)
    assert decision["decision_status"] == "RESOLVED"
    assert decision["risk_intent"] == "RETAIN"
    assert decision["hedge_feasibility"] == "NOT_REQUESTED"
    assert decision["rho_star"] == 0.0
    assert decision["q_star"] == 0
    assert decision["delta_star"] == 1
    assert decision["execution_enabled"] is False
    robust = decision["chosen_frontier_point"]["robust_portfolio_EV_after"]
    assert robust == 1 * 3.0
    assert "POLICY_UNRESOLVED" not in decision["reason_codes"]


def test_begin_reduction_unique_nonzero_is_admissible():
    policy = load_policy()
    decision = decide(
        q_dir=2,
        alpha=_alpha(a_t=18.0, a_l=15.5, alpha_delta_from_entry=-1.0),
        policy=policy,
        research_unit_qty=1,
    )
    assert decision["risk_intent"] == "BEGIN_REDUCTION"
    assert decision["hedge_feasibility"] == "ADMISSIBLE_HEDGE_AVAILABLE"
    assert decision["decision_status"] == "RESOLVED"
    assert decision["q_star"] == 1
    assert decision["chosen_frontier_point"]["hedge_price_cents"] == 35
    assert decision["timing"]["timing_state"] == "BEGIN_REDUCTION"
    assert decision["timing"]["timing_state"] != "REDUCE"


def test_begin_reduction_none_nonzero_is_no_admissible_hedge():
    policy = load_policy()
    decision = decide(
        q_dir=1,
        alpha=_alpha(a_t=14.26, a_l=4.0, alpha_delta_from_entry=-5.74),
        policy=policy,
        research_unit_qty=1,
    )
    assert decision["risk_intent"] == "BEGIN_REDUCTION"
    assert decision["hedge_feasibility"] == "NO_ADMISSIBLE_HEDGE"
    assert decision["decision_status"] == "RESOLVED"
    assert decision["q_star"] == 0
    assert decision["rho_star"] == 0.0
    assert decision["delta_star"] == 1
    assert "NO_ADMISSIBLE_HEDGE" in decision["reason_codes"]
    assert "NO_ADMISSIBLE_HEDGE" in decision["explanation"]


def test_begin_reduction_many_nonzero_is_policy_unresolved():
    policy = load_policy()
    decision = decide(
        q_dir=5,
        alpha=_alpha(a_t=18.0, a_l=20.0, alpha_delta_from_entry=-1.0),
        policy=policy,
        research_unit_qty=1,
    )
    assert decision["risk_intent"] == "BEGIN_REDUCTION"
    assert decision["hedge_feasibility"] == "POLICY_UNRESOLVED"
    assert decision["decision_status"] == "POLICY_UNRESOLVED"
    assert decision["rho_star"] is None
    assert decision["q_star"] is None
    assert "POLICY_UNRESOLVED" in decision["reason_codes"]
    assert len(decision["nonzero_admissible_frontier"]) > 1


def test_neutralize_when_robust_unhedged_nonpositive():
    policy = load_policy()
    decision = decide(q_dir=1, alpha=_alpha(a_t=-2.0, a_l=-4.0), policy=policy, research_unit_qty=1)
    assert decision["risk_intent"] == "NEUTRALIZE"
    assert decision["decision_status"] == "UNAVAILABLE"
    assert decision["q_star"] is None
    assert decision["rho_star"] is None
    assert "ROBUST_PORTFOLIO_NONPOSITIVE" in decision["reason_codes"]


def test_source_unavailable_when_austin_alpha_missing():
    policy = load_policy()
    decision = decide(q_dir=1, alpha=_alpha(a_t=None, availability="UNAVAILABLE"), policy=policy, research_unit_qty=1)
    assert decision["decision_status"] == "SOURCE_UNAVAILABLE"
    assert decision["hedge_feasibility"] == "SOURCE_UNAVAILABLE"
    assert decision["rho_star"] is None


def test_watch_also_forces_q0():
    policy = load_policy()
    decision = decide(
        q_dir=8,
        alpha=_alpha(support="LOW HISTORICAL SUPPORT"),
        policy=policy,
        research_unit_qty=1,
    )
    assert decision["risk_intent"] == "WATCH"
    assert decision["hedge_feasibility"] == "NOT_REQUESTED"
    assert decision["q_star"] == 0
    assert decision["decision_status"] == "RESOLVED"


def test_timing_from_austin_fields_not_price_triggers():
    policy = load_policy()
    retain = timing_decision(_alpha(), policy)
    assert retain["timing_state"] == "RETAIN"
    assert retain["current_hedge_price"] == "UNAVAILABLE"
    assert "A1" not in retain["note"] or "not" in retain["note"].lower()
    watch = timing_decision(_alpha(support="LOW HISTORICAL SUPPORT"), policy)
    assert watch["timing_state"] == "WATCH"
    assert "INSUFFICIENT_SUPPORT" in watch["reason_codes"]
    reduce = timing_decision(_alpha(alpha_delta_from_entry=-2.0), policy)
    assert reduce["timing_state"] == "BEGIN_REDUCTION"
    assert "ALPHA_DETERIORATING" in reduce["reason_codes"]
    dead = timing_decision(_alpha(a_l=-1.0), policy)
    assert dead["timing_state"] == "NEUTRALIZE"
    missing = timing_decision(_alpha(a_t=None, availability="UNAVAILABLE"), policy)
    assert missing["timing_state"] == "UNAVAILABLE"


def test_timing_does_not_key_off_a2_45_or_a1_55():
    policy = load_policy()
    src = Path(__file__).resolve().parents[1] / "roller" / "ballhog" / "timing.py"
    text = src.read_text(encoding="utf-8")
    assert "A2 <= 45" not in text
    assert "A1 <= 55" not in text
    assert "BEGIN_REDUCTION" in text
    assert policy.timing.get("begin_reduction_if_alpha_delta_negative") is True


def test_pit_rejects_future_stamps():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = as_of + timedelta(minutes=5)
    with pytest.raises(DrePitError):
        assert_all_not_after(
            as_of,
            [Stamped("austin_query", 12.0, "austin", future, "QUERY")],
        )
