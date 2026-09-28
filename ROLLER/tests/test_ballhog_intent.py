"""BallhogHedgeIntent is independent of TK Ultra assess."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.ballhog.models import INTENT_SCHEMA
from roller.ballhog.tk_ultra_contract import build_intent
from roller.momento.tk_ultra import handle_assess


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_intent_schema_standalone():
    intent = build_intent(
        trade_id="abc",
        as_of="2026-01-01T00:00:00Z",
        decision={
            "research_unit_qty": 1,
            "q_dir": 1,
            "q_hedge": None,
            "rho": None,
            "rho_star": None,
            "q_star": None,
            "delta_star": None,
            "target_exposure_qty": None,
            "austin_alpha_cents": 4.0,
            "alpha_ci": {"lower": 1.0, "note": "Austin bootstrap. Not a Ballhog CI."},
            "decision_status": "POLICY_UNRESOLVED",
            "reason_codes": ["POLICY_UNRESOLVED"],
            "policy_version": "v1",
            "timing": {"timing_state": "WATCH"},
            "acceptable_hedge_price_region": {"grid": list(range(35, 46)), "role": "COUNTERFACTUAL"},
        },
        austin_universe="choosin_nba_2q3q_604",
        choosin_universe="derived_four_936",
    )
    assert intent["schema"] == INTENT_SCHEMA
    assert intent["execution_enabled"] is False
    assert intent["live_execution"] is False
    assert intent["rho_star"] is None
    assert intent["intent_status"] == "UNRESOLVED"
    assert intent["provenance"]["austin_universe"] == "choosin_nba_2q3q_604"
    assert intent["provenance"]["choosin_universe"] == "derived_four_936"
    assert "NOT_IMPLEMENTED" in intent["note"]
    assert "wing_price" not in intent
    assert "beta" not in intent


def test_intent_status_no_hedge_when_q_star_zero():
    intent = build_intent(
        trade_id="abc",
        as_of="2026-01-01T00:00:00Z",
        decision={
            "research_unit_qty": 1,
            "q_dir": 1,
            "q_hedge": 0,
            "rho": 0.0,
            "rho_star": 0.0,
            "q_star": 0,
            "delta_star": 1,
            "target_exposure_qty": 1,
            "austin_alpha_cents": 14.26,
            "decision_status": "RESOLVED",
            "risk_intent": "BEGIN_REDUCTION",
            "hedge_feasibility": "NO_ADMISSIBLE_HEDGE",
            "reason_codes": ["NO_ADMISSIBLE_HEDGE"],
            "policy_version": "v1",
            "timing": {"timing_state": "BEGIN_REDUCTION"},
            "acceptable_hedge_price_region": {"grid": list(range(35, 46)), "role": "COUNTERFACTUAL"},
        },
        austin_universe="choosin_nba_2q3q_604",
        choosin_universe="derived_four_936",
    )
    assert intent["intent_status"] == "NO_HEDGE"
    assert intent["risk_intent"] == "BEGIN_REDUCTION"
    assert intent["hedge_feasibility"] == "NO_ADMISSIBLE_HEDGE"


def test_intent_status_hedge_requested_when_q_star_positive():
    intent = build_intent(
        trade_id="abc",
        as_of="2026-01-01T00:00:00Z",
        decision={
            "q_star": 1,
            "q_hedge": 1,
            "rho_star": 0.5,
            "decision_status": "RESOLVED",
            "risk_intent": "BEGIN_REDUCTION",
            "hedge_feasibility": "ADMISSIBLE_HEDGE_AVAILABLE",
            "timing": {"timing_state": "BEGIN_REDUCTION"},
        },
        austin_universe="choosin_nba_2q3q_604",
        choosin_universe="derived_four_936",
    )
    assert intent["intent_status"] == "HEDGE_REQUESTED"


def test_tk_ultra_assess_signature_and_behavior_unchanged():
    assert "rho_star" not in inspect.signature(handle_assess).parameters
    client = _client()
    missing = client.get("/momento/tk-ultra/assess").json()
    assert missing["status"] == "SOURCE_UNAVAILABLE"
    assert "wing_price" in missing["missing"]
    nq = client.get(
        "/momento/tk-ultra/assess",
        params={
            "wing_price": "14033",
            "base_price": "4382.50",
            "beta": "1.325",
            "wing_anchor": "13954.8",
            "base_anchor": "4349.46",
            "ticks_per_handle": "4",
        },
    ).json()
    assert nq["status"] == "RESEARCH_ONLY"
    assert nq["reading"] == "WING_CHEAP"
    assert nq["rv_ticks"] == "-247.92"
    assert "rho_star" not in nq
    src = Path(__file__).resolve().parents[1] / "roller" / "momento" / "tk_ultra.py"
    text = src.read_text(encoding="utf-8")
    assert "rho_star" not in text
    assert "ballhog" not in text.lower()
