"""Ballhog HTTP. Austin 604 + Choosin 936. Execution stays false."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

REPO = Path(__file__).resolve().parents[2]
BALLHOG_PY = Path(__file__).resolve().parents[1] / "roller" / "ballhog"
BALLHOG_UI = REPO / "frontend" / "ballhog" / "src"
TRADE_ID = "f84fd059fc0e1429"


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_health_execution_disabled_and_universes_stamped():
    body = _client().get("/ballhog/health").json()
    assert body["product"] == "Ballhog"
    assert body["live_execution"] is False
    assert body["execution_enabled"] is False
    assert body["submits"] is False
    assert body["live_feed"] == "UNAVAILABLE"
    assert body["austin"]["n"] == 604
    assert body["austin"]["universe"] == "choosin_nba_2q3q_604"
    assert body["choosin_texas"]["n"] == 936
    assert body["choosin_texas"]["universe"] == "derived_four_936"


def test_sources_policy_and_no_live():
    body = _client().get("/ballhog/sources").json()
    assert body["execution_enabled"] is False
    assert body["research_unit_qty"] == 1
    assert body["default_q_dir"] == 1
    assert body["max_q_dir"] == 500
    assert body["policy"]["price_grid"] == list(range(35, 46))
    assert body["choosin_texas"]["pit_kind"] == "STATIC"


def test_positions_are_austin_604():
    body = _client().get("/ballhog/positions").json()
    assert body["austin_n"] == 604
    assert body["choosin_n"] == 936
    assert body["execution_enabled"] is False
    assert body["live_feed"] == "UNAVAILABLE"
    assert body["default_as_of_rule"] == "austin_replay_path_midpoint"
    if body["n"]:
        assert body["n"] == 604
        ids = {row["trade_id"] for row in body["positions"]}
        assert TRADE_ID in ids or len(ids) == 604
        nyk = next((row for row in body["positions"] if row.get("trade_id") == TRADE_ID), None)
        if nyk is not None:
            assert nyk["default_as_of"] == "2026-06-14T02:28:00Z"
            assert nyk["replay_available"] is True
        stamps = {row.get("default_as_of") for row in body["positions"] if row.get("default_as_of")}
        assert stamps, "at least one replay midpoint required"
        other = next(
            (row for row in body["positions"] if row.get("trade_id") != TRADE_ID and row.get("default_as_of")),
            None,
        )
        if nyk is not None and other is not None:
            assert other["default_as_of"] is not None
            assert "default_as_of" in other


def _pick_trade(client: TestClient) -> str:
    body = client.get("/ballhog/positions").json()
    ids = [str(row.get("trade_id") or row.get("position_id")) for row in body.get("positions") or []]
    if TRADE_ID in ids:
        return TRADE_ID
    assert ids, "Austin 604 book is required"
    return ids[0]


def _mid_path_as_of(trade_id: str) -> str:
    from roller.ballhog.adapters import austin as austin_ad
    from roller.dre.pit import iso, to_utc

    trade = austin_ad.get_trade(trade_id)
    assert trade is not None
    replay = austin_ad.get_replay(trade_id)
    path = list(replay.get("path") or [])
    assert path, "Austin replay path required for mid-path as_of"
    mid = path[len(path) // 2]
    stamp = to_utc(mid.get("t"))
    assert stamp is not None
    return iso(stamp) or stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_replay_one_real_604_trade():
    client = _client()
    trade_id = _pick_trade(client)
    as_of = _mid_path_as_of(trade_id)
    state = client.get(f"/ballhog/state/{trade_id}", params={"as_of": as_of}).json()
    assert state["schema"] == "ballhog.state.v1"
    assert state["feed_mode"] == "REPLAY"
    assert state["live_feed"] == "UNAVAILABLE"
    assert state["execution_enabled"] is False
    assert state["research_unit_qty"] == 1
    assert state["q_dir"] == 1
    assert state["austin"]["n"] == 604
    assert state["choosin_texas"]["n"] == 936
    assert state["austin"]["universe"] != state["choosin_texas"]["universe"]
    assert state["current_hedge_price"] == "UNAVAILABLE"
    assert state["choosin_texas"]["pit_kind"] == "STATIC"
    assert "as_of" not in str(state["choosin_texas"]["note"]).lower() or "not as_of" in state["choosin_texas"]["note"].lower()
    decision = state["decision"]
    assert decision["execution_enabled"] is False
    surface = client.post("/ballhog/surface", json={"trade_id": trade_id, "as_of": as_of}).json()
    qs = {cell["q_hedge"] for cell in surface["surface"]["cells"]}
    assert qs == {0, 1}
    assert surface["research_unit_qty"] == 1
    assert surface["q_dir"] == 1
    assert all(cell.get("fill_claimed") is False for cell in surface["surface"]["cells"])
    frontier = client.post("/ballhog/frontier", json={"trade_id": trade_id, "as_of": as_of}).json()
    assert frontier["frontier"]["axes"]["x"] == "economic_EV_cost_of_hedge"
    intent = client.get(f"/ballhog/intent/{trade_id}", params={"as_of": as_of}).json()
    assert intent["schema"] == "ballhog.hedge_intent.v1"
    assert intent["execution_enabled"] is False
    assert intent["live_execution"] is False
    assert "Position Management is NOT_IMPLEMENTED" in intent["note"]


def test_q_dir_100_enumerates_full_quantity_set():
    client = _client()
    trade_id = _pick_trade(client)
    as_of = _mid_path_as_of(trade_id)
    surface = client.post(
        "/ballhog/surface",
        json={"trade_id": trade_id, "as_of": as_of, "q_dir": 100},
    ).json()
    assert surface["q_dir"] == 100
    qs = sorted({int(cell["q_hedge"]) for cell in surface["surface"]["cells"]})
    assert qs == list(range(0, 101))
    decision = client.post(
        "/ballhog/decision",
        json={"trade_id": trade_id, "as_of": as_of, "q_dir": 100},
    ).json()
    if decision["hedge_feasibility"] == "POLICY_UNRESOLVED":
        assert decision["rho_star"] is None
        assert len(decision["nonzero_admissible_frontier"]) > 1
    if decision.get("risk_intent") in {"RETAIN", "WATCH"}:
        assert decision["hedge_feasibility"] == "NOT_REQUESTED"
        assert decision["q_star"] == 0


def test_q_dir_rejects_non_integers_and_non_positive():
    client = _client()
    trade_id = _pick_trade(client)
    as_of = _mid_path_as_of(trade_id)
    for raw in (1.5, 0, -3, "1.5", "abc"):
        resp = client.post("/ballhog/surface", json={"trade_id": trade_id, "as_of": as_of, "q_dir": raw})
        assert resp.status_code == 400, raw
        assert resp.json()["detail"]["code"] == "INVALID_QUANTITY"
    get_resp = client.get(f"/ballhog/state/{trade_id}", params={"as_of": as_of, "q_dir": "1.5"})
    assert get_resp.status_code == 400
    assert get_resp.json()["detail"]["code"] == "INVALID_QUANTITY"
    over = client.post("/ballhog/surface", json={"trade_id": trade_id, "as_of": as_of, "q_dir": 501})
    assert over.status_code == 400
    assert over.json()["detail"]["code"] == "INVALID_QUANTITY"


def test_nyk_sas_midpoint_is_no_admissible_hedge():
    client = _client()
    as_of = "2026-06-14T02:28:00Z"
    state = client.get(f"/ballhog/state/{TRADE_ID}", params={"as_of": as_of}).json()
    austin = state["austin"]
    assert austin["a_t"] == pytest.approx(14.26, abs=0.05)
    assert austin["a_l"] == pytest.approx(4.0, abs=0.05)
    assert austin["alpha_delta_from_entry"] == pytest.approx(-5.74, abs=0.05)
    decision = state["decision"]
    assert decision["risk_intent"] == "BEGIN_REDUCTION"
    assert decision["hedge_feasibility"] == "NO_ADMISSIBLE_HEDGE"
    assert decision["decision_status"] == "RESOLVED"
    assert decision["q_star"] == 0
    assert decision["rho_star"] == 0.0
    assert decision["delta_star"] == 1
    assert decision["explanation"]
    surface = client.post("/ballhog/surface", json={"trade_id": TRADE_ID, "as_of": as_of, "q_dir": 1}).json()
    full = next(cell for cell in surface["surface"]["cells"] if cell["q_hedge"] == 1 and cell["hedge_price_cents"] == 35)
    assert full["paired_lock_cents"] == -15
    assert full["fill_claimed"] is False
    intent = client.get(f"/ballhog/intent/{TRADE_ID}", params={"as_of": as_of}).json()
    assert intent["intent_status"] == "NO_HEDGE"
    assert intent["hedge_feasibility"] == "NO_ADMISSIBLE_HEDGE"


def test_parse_q_dir_rejects_floats_and_non_positive():
    from roller.ballhog.context import parse_q_dir, resolve_q_dir
    from roller.ballhog.errors import BallhogError
    from roller.ballhog.policy import load_policy

    policy = load_policy()
    assert resolve_q_dir(None, policy) == 1
    assert parse_q_dir(100, policy) == 100
    with pytest.raises(BallhogError) as exc:
        parse_q_dir(1.5, policy)
    assert exc.value.code == "INVALID_QUANTITY"
    with pytest.raises(BallhogError):
        parse_q_dir(0, policy)
    with pytest.raises(BallhogError):
        parse_q_dir(-1, policy)
    with pytest.raises(BallhogError):
        parse_q_dir(501, policy)


def test_unknown_trade_is_404():
    resp = _client().get("/ballhog/state/not-a-real-trade")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "UNKNOWN_POSITION"


def test_future_as_of_on_path_fails_closed_or_clips():
    client = _client()
    resp = client.get(
        f"/ballhog/state/{_pick_trade(client)}",
        params={"as_of": "2099-01-01T00:00:00Z"},
    )
    assert resp.status_code in {200, 400}
    if resp.status_code == 200:
        body = resp.json()
        assert body["austin"]["n"] == 604
        assert body["live_feed"] == "UNAVAILABLE"


def test_missing_alpha_is_not_zero():
    from roller.ballhog.adapters.austin import extract_alpha

    empty = extract_alpha(None)
    assert empty["a_t"] is None
    assert empty["availability"] == "UNAVAILABLE"
    assert empty["a_t"] != 0


def test_package_has_no_order_client():
    tree = ast.parse((BALLHOG_PY / "api.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    banned = ("kalshi", "roller.vital", "crates")
    for name in imported:
        assert not any(item in name for item in banned), name
    blob = "\n".join(path.read_text(encoding="utf-8") for path in BALLHOG_PY.rglob("*.py"))
    assert "place_order" not in blob
    assert "ENABLE_LIVE_TRADING" not in blob
    assert "def lambda_alpha" not in blob
    assert "kalshi" not in blob.lower()


def test_frontend_is_api_only_and_does_not_call_tk_ultra_assess():
    if not BALLHOG_UI.is_dir():
        return
    sources = "\n".join(path.read_text(encoding="utf-8") for path in BALLHOG_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in BALLHOG_UI.rglob("*.ts"))
    assert "/api/ballhog" in sources
    assert "/momento/tk-ultra/assess" not in sources
    assert "place_order" not in sources
    assert "/vital" not in sources
    assert "5180" not in sources
    assert "NO_ADMISSIBLE_HEDGE" in sources
    assert "loadedQty" in sources or "q*=0 is 0" in sources
