"""Drevo structural gate. POLICY_UNRESOLVED is not ACCEPT. execution_authorized is false."""

from __future__ import annotations

from pathlib import Path

from roller.dre.decision import decide
from roller.positman.composer import compose_plan
from roller.positman.matching import match_siblings
from roller.positman.models import DEFAULT_TRADE_ID

REPO = Path(__file__).resolve().parents[2]
DRE_UI = REPO / "frontend" / "dynamic-risk-engine" / "src"


def _plan(**extra):
    intent = {
        "schema": "ballhog.hedge_intent.v1",
        "position_id": DEFAULT_TRADE_ID,
        "trade_id": DEFAULT_TRADE_ID,
        "as_of": "2026-01-15T00:12:00Z",
        "q_star": 1,
        "decision_status": "RESOLVED",
        "current_exposure": 1,
        "event_id": "evt-1",
        "a_contract": "A",
        "b_contract": "B",
    }
    assess = {
        "schema": "tk_ultra.assessment.v0",
        "identity": {
            "trade_id": DEFAULT_TRADE_ID,
            "event_id": "evt-1",
            "a_contract": "A",
            "b_contract": "B",
            "as_of": "2026-01-15T00:12:00Z",
        },
        "route_preference": "BUY_B_BETTER",
        "current_a_qty": 1,
    }
    matched = match_siblings(intent, assess)
    body = compose_plan(
        match=matched,
        ballhog={"availability": "OBSERVED", "intent": intent},
        tk_ultra={"availability": "OBSERVED", "assessment": assess},
    )
    body.update(extra)
    return body


def test_structurally_valid_is_policy_unresolved_not_accept():
    decision = decide(_plan())
    assert decision["schema"] == "drevo.decision.v0"
    assert decision["product"] == "Drevo"
    assert decision["structural_status"] == "VALID"
    assert decision["decision_status"] == "POLICY_UNRESOLVED"
    assert decision["execution_authorized"] is False
    assert decision["execution_enabled"] is False
    assert decision["execution_boundary"]["status"] == "NOT_SUBMITTED"
    assert "NO_POLICY_FROZEN" in decision["reason_codes"]


def test_identity_mismatch_rejects():
    decision = decide(_plan(match_status="IDENTITY_MISMATCH", plan_status="IDENTITY_MISMATCH"))
    assert decision["structural_status"] == "INVALID"
    assert decision["decision_status"] in {"REJECT", "IDENTITY_MISMATCH"}
    assert decision["execution_authorized"] is False


def test_drevo_frontend_keeps_dre_alias_and_surfaces_positman():
    if not DRE_UI.is_dir():
        return
    sources = "\n".join(path.read_text(encoding="utf-8") for path in DRE_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in DRE_UI.rglob("*.ts"))
    assert "/api/dre" in sources
    assert "DREVO" in sources
    assert "Positman" in sources
    assert "PORTFOLIO_OBJECTIVE_V1" in sources
    assert "/vital" not in sources
    assert "5180" not in sources
