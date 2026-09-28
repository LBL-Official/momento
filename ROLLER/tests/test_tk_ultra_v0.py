"""TK Ultra V0: BINARY_COMPLEMENT_V0, independent adapters, sibling-only Ballhog."""

from __future__ import annotations

import ast
import sys
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from roller.tk_ultra.api import handle_assess_v0, math_snapshot
from roller.tk_ultra.assessment import MATH_KEYS, assess_binary, attach_sibling
from roller.tk_ultra.hedge_budget import assess_budget, locked_pnl, max_remaining_avg
from roller.tk_ultra.relationship import assess_relationship, expected_b
from roller.tk_ultra.route import assess_route

REPO = Path(__file__).resolve().parents[2]
PKG = Path(__file__).resolve().parents[1] / "roller" / "tk_ultra"
FRONTEND = REPO / "frontend" / "momento-systems" / "src"


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


ACCEPTANCE = {
    "a_entry_cents": "80",
    "a_stop_cents": "40",
    "a_bid_cents": "45",
    "b_ask_cents": "54",
    "a_anchor_cents": "60",
    "b_anchor_cents": "40",
    "a_ref_cents": "50",
    "b_observed_cents": "48",
    "a_ref_basis": "MID",
    "b_observed_basis": "MID",
    "q_a": "1",
    "q_b": "0.4",
    "b_avg_existing_cents": "52",
    "feed_mode": "MANUAL_INPUT",
}


def test_locked_pnl_identities():
    assert locked_pnl(e_a=Fraction(80), b_avg=Fraction(55)) == Fraction(-35)
    assert locked_pnl(e_a=Fraction(80), b_avg=Fraction(60)) == Fraction(-40)
    assert locked_pnl(e_a=Fraction(80), b_avg=Fraction(65)) == Fraction(-45)


def test_b_stop_eq_is_complement_of_a_stop():
    body = assess_budget(
        e_a=Fraction(80),
        s_a=Fraction(40),
        q_a=Fraction(1),
        q_b=Fraction(0),
        b_existing=None,
        b_ask=None,
    )
    assert body["stop_equivalent_b_avg"] == "60.0000"
    assert body["stop_pnl_benchmark"] == "-40.0000"


def test_max_remaining_avg_partial_and_bounds():
    remaining = max_remaining_avg(f=Fraction(2, 5), b_existing=Fraction(52), b_target=Fraction(60))
    assert remaining == Fraction(196, 3)
    assert str(remaining) == "196/3"
    assert max_remaining_avg(f=Fraction(0), b_existing=Fraction(52), b_target=Fraction(60)) == Fraction(60)
    assert max_remaining_avg(f=Fraction(1), b_existing=Fraction(52), b_target=Fraction(60)) == "UNAVAILABLE"
    missing = assess_budget(
        e_a=Fraction(80),
        s_a=Fraction(40),
        q_a=Fraction(1),
        q_b=Fraction(1),
        b_existing=None,
        b_ask=Fraction(54),
    )
    assert missing["max_remaining_avg_price"] == "UNAVAILABLE"
    assert "EXISTING_B_AVG_UNAVAILABLE" in missing["reason_codes"]


def test_route_45_54_and_45_57_and_missing():
    better = assess_route(a_bid=Fraction(45), b_ask=Fraction(54))
    assert better["synthetic_exit_price"] == "46.0000"
    assert better["gross_route_edge"] == "1.0000"
    assert better["route_preference"] == "BUY_B_BETTER"
    worse = assess_route(a_bid=Fraction(45), b_ask=Fraction(57))
    assert worse["gross_route_edge"] == "-2.0000"
    assert worse["route_preference"] == "SELL_A_BETTER"
    missing = assess_route(a_bid=Fraction(45), b_ask=None)
    assert missing["gross_route_edge"] == "UNAVAILABLE"
    assert "QUOTE_UNAVAILABLE" in missing["reason_codes"]


def test_relationship_complement_invariance_and_invalid_anchors():
    a_ref = Fraction(50)
    expected = expected_b(
        a_anchor=Fraction(60),
        b_anchor=Fraction(40),
        a_ref=a_ref,
        beta=Fraction(-1),
    )
    assert expected == Fraction(100) - a_ref
    rel = assess_relationship(
        a_anchor=Fraction(60),
        b_anchor=Fraction(40),
        a_ref=a_ref,
        b_observed=Fraction(48),
        a_ref_basis="MID",
        b_observed_basis="MID",
        a_bid=Fraction(45),
        b_ask=Fraction(54),
    )
    assert rel["expected_wing"] == "50.0000"
    assert rel["tk_residual"] == "-2.0000"
    assert rel["relationship_route_collinear"] is False
    invalid = assess_relationship(
        a_anchor=Fraction(80),
        b_anchor=Fraction(40),
        a_ref=a_ref,
        b_observed=Fraction(48),
        a_ref_basis="MID",
        b_observed_basis="MID",
    )
    assert invalid["status"] == "ANCHOR_INVALID"
    assert invalid["expected_wing"] == "UNAVAILABLE"
    assert invalid["anchor_validity"] == "A_PLUS_B_NOT_100"


def test_relationship_route_collinear_when_bid_ask_forced():
    rel = assess_relationship(
        a_anchor=Fraction(60),
        b_anchor=Fraction(40),
        a_ref=Fraction(45),
        b_observed=Fraction(54),
        a_ref_basis="YES_BID",
        b_observed_basis="YES_ASK",
        a_bid=Fraction(45),
        b_ask=Fraction(54),
    )
    route = assess_route(a_bid=Fraction(45), b_ask=Fraction(54))
    assert rel["relationship_route_collinear"] is True
    assert Fraction(rel["tk_residual"]) == -Fraction(route["gross_route_edge"])
    assert "RELATIONSHIP_ROUTE_COLLINEAR" in rel["reason_codes"]
    preferred = assess_relationship(
        a_anchor=Fraction(60),
        b_anchor=Fraction(40),
        a_ref=Fraction(50),
        b_observed=Fraction(48),
        a_ref_basis="MID",
        b_observed_basis="MID",
        a_bid=Fraction(45),
        b_ask=Fraction(54),
    )
    assert preferred["relationship_route_collinear"] is False


def test_acceptance_compose_manual():
    body = assess_binary(ACCEPTANCE, feed_mode="MANUAL_INPUT")
    assert body["model_mode"] == "BINARY_COMPLEMENT_V0"
    assert body["synthetic_exit_price"] == "46.0000"
    assert body["gross_route_edge"] == "1.0000"
    assert body["route_preference"] == "BUY_B_BETTER"
    assert body["stop_equivalent_b_avg"] == "60.0000"
    assert body["max_remaining_avg_price"] == "65.333333"
    assert body["relationship"]["expected_wing"] == "50.0000"
    assert body["relationship_route_collinear"] is False
    assert body["fees"] == "UNAVAILABLE"
    assert body["slippage"] == "UNAVAILABLE"
    assert body["austin"]["n"] == 604
    assert body["choosin_texas"]["n"] == 936
    assert body.get("combined_n") is None
    assert body.get("n") != 1540
    assert body["live_execution"] is False
    assert body["position_management"] == "NOT_IMPLEMENTED"


def test_independence_math_identical_with_or_without_sibling():
    base = assess_binary(ACCEPTANCE)
    snap = math_snapshot(base)
    down = attach_sibling(dict(base), None)
    up = attach_sibling(
        dict(base),
        {
            "availability": "OBSERVED",
            "intent": {"q_star": 7, "rho_star": 1, "risk_intent": "BEGIN_REDUCTION", "intent_status": "HEDGE_REQUESTED"},
        },
    )
    assert math_snapshot(down) == snap
    assert math_snapshot(up) == snap
    assert set(MATH_KEYS) <= set(snap)
    assert up["sibling_context"]["q_star"] == 7
    assert down["sibling_context"]["availability"] == "UNAVAILABLE"

    def boom(*_args, **_kwargs):
        raise RuntimeError("ballhog down")

    with patch("roller.ballhog.api.handle_intent", side_effect=boom):
        from roller.tk_ultra.adapters.ballhog import read_intent

        sibling = read_intent("any-trade")
    assert sibling["availability"] == "UNAVAILABLE"
    again = attach_sibling(dict(base), sibling)
    assert math_snapshot(again) == snap


def test_package_does_not_import_ballhog_adapters_or_self_http():
    for path in PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "roller.ballhog.adapters" not in text, path
        assert "BallhogState" not in text, path
        assert "extract_alpha" not in text, path
        tree = ast.parse(text)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any(name.startswith("roller.ballhog.adapters") for name in imported)
    sibling = (PKG / "adapters" / "ballhog.py").read_text(encoding="utf-8")
    assert "handle_intent" in sibling
    assert "localhost" not in sibling
    assert "http://" not in sibling
    assert "127.0.0.1" not in sibling


def test_legacy_get_assess_nq_es_and_v0_post():
    client = _client()
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
    assert nq["rv_ticks"] == "-247.92"
    assert nq["model_mode"] == "GENERIC_RV"
    health = client.get("/momento/tk-ultra/health").json()
    assert health["live_execution"] is False
    assert health["austin"]["n"] == 604
    assert health["choosin_texas"]["n"] == 936
    sources = client.get("/momento/tk-ultra/sources").json()
    assert sources["austin"]["n"] == 604
    assert sources["choosin_texas"]["n"] == 936
    posted = client.post("/momento/tk-ultra/assess", json=ACCEPTANCE)
    assert posted.status_code == 200
    body = posted.json()
    assert body["schema"] == "tk_ultra.assessment.v0"
    assert body["gross_route_edge"] == "1.0000"
    assert body["stop_equivalent_b_avg"] == "60.0000"
    assert body["max_remaining_avg_price"] == "65.333333"
    collinear = dict(ACCEPTANCE)
    collinear["a_ref_cents"] = "45"
    collinear["b_observed_cents"] = "54"
    collinear["a_ref_basis"] = "YES_BID"
    collinear["b_observed_basis"] = "YES_ASK"
    flagged = client.post("/momento/tk-ultra/assess", json=collinear).json()
    assert flagged["relationship_route_collinear"] is True
    invalid = dict(ACCEPTANCE)
    invalid["a_anchor_cents"] = "80"
    bad = client.post("/momento/tk-ultra/assess", json=invalid).json()
    assert bad["relationship"]["status"] == "ANCHOR_INVALID"
    missing_ctx = client.get("/momento/tk-ultra/ballhog-context/not-a-real-trade")
    assert missing_ctx.status_code == 200
    assert missing_ctx.json()["availability"] == "UNAVAILABLE"


def test_frontend_binds_v0_without_formula_or_orders():
    tsx = (FRONTEND / "TkUltra.tsx").read_text(encoding="utf-8")
    api = (FRONTEND / "api.ts").read_text(encoding="utf-8")
    assert "postTkUltraAssessV0" in api
    assert "/api/momento/tk-ultra/assess" in api
    assert "SIBLING CONTEXT — NOT MODEL INPUT" in tsx
    assert "BINARY COMPLEMENT V0" in tsx
    assert "parseFloat" not in tsx
    assert "Number(" not in tsx
    assert "place_order" not in tsx
    assert "ENABLE_LIVE_TRADING" not in tsx
    assert "5180" not in tsx
    for banned in ("expected_wing =", "gross_route_edge =", "100 -", "EXPECTED_B"):
        assert banned not in tsx


def test_handle_assess_v0_does_not_need_trade_id():
    body = handle_assess_v0(ACCEPTANCE)
    assert body["feed_mode"] == "MANUAL_INPUT"
    assert body["sibling_context"]["availability"] == "UNAVAILABLE"
    assert body["fees"] != "0"
    assert body["fees"] == "UNAVAILABLE"
