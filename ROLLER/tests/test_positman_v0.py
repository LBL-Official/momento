"""Positman compositor. Quantity from Ballhog. Route from TK Ultra. No submit."""

from __future__ import annotations

import ast
from pathlib import Path

from roller.positman.composer import compose_plan, execution_boundary
from roller.positman.matching import match_siblings
from roller.positman.models import DEFAULT_TRADE_ID, LIVE_EXECUTION, PLAN_SCHEMA

REPO = Path(__file__).resolve().parents[2]
POSITMAN_PY = Path(__file__).resolve().parents[1] / "roller" / "positman"
POSITMAN_UI = REPO / "frontend" / "positman" / "src"


def _intent(**extra):
    body = {
        "schema": "ballhog.hedge_intent.v1",
        "position_id": DEFAULT_TRADE_ID,
        "trade_id": DEFAULT_TRADE_ID,
        "as_of": "2026-01-15T00:12:00Z",
        "q_star": 1,
        "rho_star": 0.5,
        "risk_intent": "REDUCE",
        "hedge_feasibility": "ADMISSIBLE",
        "decision_status": "RESOLVED",
        "current_exposure": 1,
        "target_exposure": 0,
        "target_residual_qty": 0,
        "event_id": "evt-1",
        "a_contract": "KXNBAGAME-A",
        "b_contract": "KXNBAGAME-B",
    }
    body.update(extra)
    return body


def _assess(**extra):
    body = {
        "schema": "tk_ultra.assessment.v0",
        "identity": {
            "trade_id": DEFAULT_TRADE_ID,
            "event_id": "evt-1",
            "a_contract": "KXNBAGAME-A",
            "b_contract": "KXNBAGAME-B",
            "as_of": "2026-01-15T00:12:00Z",
        },
        "as_of": "2026-01-15T00:12:00Z",
        "route_preference": "BUY_B_BETTER",
        "current_a_qty": 1,
        "gross_route_edge": "1.0000",
    }
    body.update(extra)
    return body


def test_buy_b_and_no_change_and_parity():
    matched = match_siblings(_intent(), _assess())
    buy = compose_plan(
        match=matched,
        ballhog={"availability": "OBSERVED", "intent": _intent()},
        tk_ultra={"availability": "OBSERVED", "assessment": _assess()},
    )
    assert buy["schema"] == PLAN_SCHEMA
    assert buy["position_route"] == "ACQUIRE_B"
    assert buy["planned_qty"] == 1
    assert buy["quantity_source"] == "BALLHOG"
    assert buy["route_source"] == "TK_ULTRA"
    assert buy["execution_enabled"] is False
    assert buy["live_execution"] is LIVE_EXECUTION
    zero = compose_plan(
        match=matched,
        ballhog={"availability": "OBSERVED", "intent": _intent(q_star=0, hedge_feasibility="NO_ADMISSIBLE_HEDGE")},
        tk_ultra={"availability": "OBSERVED", "assessment": _assess()},
    )
    assert zero["position_route"] == "NO_CHANGE"
    assert zero["planned_qty"] == 0
    parity = compose_plan(
        match=matched,
        ballhog={"availability": "OBSERVED", "intent": _intent()},
        tk_ultra={"availability": "OBSERVED", "assessment": _assess(route_preference="PARITY")},
    )
    assert parity["position_route"] == "ROUTE_PARITY_UNRESOLVED"
    assert parity["planned_qty"] is None


def test_identity_and_time_mismatch():
    left = _intent()
    right = _assess()
    right["identity"] = {**right["identity"], "trade_id": "other"}
    bad = match_siblings(left, right)
    assert bad["match_status"] == "IDENTITY_MISMATCH"
    timed = _assess()
    timed["identity"] = {**timed["identity"], "as_of": "2026-01-15T00:99:00Z"}
    timed["as_of"] = "2026-01-15T00:99:00Z"
    clock = match_siblings(left, timed)
    assert clock["match_status"] == "STATE_TIME_MISMATCH"


def test_sell_a_qty_guard_and_boundary():
    matched = match_siblings(_intent(q_star=2), _assess(route_preference="SELL_A_BETTER", current_a_qty=1))
    plan = compose_plan(
        match=matched,
        ballhog={"availability": "OBSERVED", "intent": _intent(q_star=2)},
        tk_ultra={"availability": "OBSERVED", "assessment": _assess(route_preference="SELL_A_BETTER", current_a_qty=1)},
    )
    assert plan["plan_status"] == "PLAN_UNRESOLVED"
    ok = compose_plan(
        match=match_siblings(_intent(q_star=1), _assess(route_preference="SELL_A_BETTER")),
        ballhog={"availability": "OBSERVED", "intent": _intent(q_star=1)},
        tk_ultra={"availability": "OBSERVED", "assessment": _assess(route_preference="SELL_A_BETTER", current_a_qty=1)},
    )
    assert ok["position_route"] == "REDUCE_A"
    boundary = execution_boundary(ok)
    assert boundary["execution_enabled"] is False
    assert boundary["status"] == "NOT_SUBMITTED"


def test_package_does_not_import_sibling_adapters_or_submit():
    blob = "\n".join(path.read_text(encoding="utf-8") for path in POSITMAN_PY.rglob("*.py"))
    assert "from roller.ballhog.adapters" not in blob
    assert "from roller.tk_ultra.adapters" not in blob
    assert "place_order" not in blob
    assert "ENABLE_LIVE_TRADING" not in blob
    tree = ast.parse((POSITMAN_PY / "adapters" / "ballhog.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "roller.ballhog.api" in imported
    if POSITMAN_UI.is_dir():
        sources = "\n".join(path.read_text(encoding="utf-8") for path in POSITMAN_UI.rglob("*.tsx"))
        sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in POSITMAN_UI.rglob("*.ts"))
        assert "/api/positman" in sources
        assert "place_order" not in sources
        assert "5192" in sources
        assert "tk-ultra" in sources
