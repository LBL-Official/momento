"""Systimo transition loop: locked types, hash chain, Orchestra QUERY."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from roller.systimo.errors import SystimoError
from roller.systimo.models import QUERY_TYPES
from roller.systimo.transitions import record_event, tamper_detect, verify_trace
from roller.systimo.transitions.identity import match_identities, trace_id
from roller.systimo.transitions.types import LOCKED_SCHEMAS, STAGE_SEQ, TRANSITION_QUERY_TYPES

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "research" / "systimo"
SYSTIMO_UI = REPO / "frontend" / "systimo" / "src"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    dst = tmp_path / "systimo"
    shutil.copytree(SEED, dst, ignore=shutil.ignore_patterns("generated", "__pycache__"))
    monkeypatch.setenv("SYSTIMO_ROOT", str(dst))
    from roller.systimo.store import CsvStore

    csv_store = CsvStore(dst)
    csv_store.validate_all()
    return csv_store


def test_locked_types_and_query_vocab():
    assert "positman.plan.v0" in LOCKED_SCHEMAS
    assert "drevo.decision.v0" in LOCKED_SCHEMAS
    assert STAGE_SEQ["POSITMAN_PLAN"] == 400
    assert STAGE_SEQ["DREVO_DECISION"] == 500
    for name in TRANSITION_QUERY_TYPES:
        assert name in QUERY_TYPES
    assert "ORCHESTRA_CONTEXT" in QUERY_TYPES


def test_same_identity_same_trace_id():
    ident = {
        "trade_id": "f84fd059fc0e1429",
        "event_id": "e1",
        "a_contract": "A",
        "b_contract": "B",
        "as_of": "2026-01-15T00:12:00Z",
        "source_mode": "HISTORICAL",
    }
    assert trace_id(ident) == trace_id(dict(ident))
    mismatched = match_identities(ident, {**ident, "trade_id": "other"})
    assert mismatched["match_status"] == "IDENTITY_MISMATCH"


def test_hash_chain_verifies_and_tamper_fails(store):
    ident = {
        "trade_id": "f84fd059fc0e1429",
        "event_id": "e1",
        "a_contract": "A",
        "b_contract": "B",
        "as_of": "2026-01-15T00:12:00Z",
        "source_mode": "HISTORICAL",
        "trace_id": trace_id(
            {
                "trade_id": "f84fd059fc0e1429",
                "event_id": "e1",
                "a_contract": "A",
                "b_contract": "B",
                "as_of": "2026-01-15T00:12:00Z",
                "source_mode": "HISTORICAL",
            }
        ),
    }
    first = record_event(
        stage="SOURCE_STATE",
        system_id="systimo",
        object_type="TransitionIdentity",
        object_id="f84fd059fc0e1429",
        schema_name="systimo.transition_trace.v0",
        payload={"identity": ident},
        identity=ident,
        store=store,
    )
    second = record_event(
        stage="POSITMAN_PLAN",
        system_id="position_management",
        object_type="PositmanPositionPlan",
        object_id=ident["trace_id"],
        schema_name="positman.plan.v0",
        payload={"schema": "positman.plan.v0", "plan_status": "PLAN_RESOLVED"},
        identity=ident,
        store=store,
    )
    assert first["trace_id"] == second["trace_id"]
    ok = verify_trace(first["trace_id"], store)
    assert ok["integrity_status"] == "VERIFIED"
    events = store.read("transition_events")
    assert events[-1]["previous_event_hash"] == first["event_hash"]
    from roller.systimo.errors import SystimoError

    with pytest.raises(SystimoError) as append_err:
        store.write("transition_events", events)
    assert append_err.value.code == "APPEND_ONLY"
    rows = store.read("transition_events")
    rows[-1]["previous_event_hash"] = "tamper"
    path = store.path_for("transition_events")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    bad = tamper_detect(first["trace_id"], store)
    assert bad["integrity_status"] == "HASH_MISMATCH"


def test_orchestra_query_partial_failure_is_unavailable(store, monkeypatch):
    from roller.systimo.query.executor import execute

    def boom(*_a, **_k):
        raise RuntimeError("tk down")

    monkeypatch.setattr("roller.systimo.orchestra._tk_ultra", boom)
    body = execute({"query_type": "ORCHESTRA_CONTEXT", "trade_id": "f84fd059fc0e1429"}, store)
    result = body["result"]
    assert result["schema"] == "systimo.orchestra_context.v0"
    assert result["query_only"] is True
    assert result["control"] == "DENY"
    assert result["live_execution"] is False
    tk = result["namespaces"]["tk_ultra"]
    assert tk["availability"] == "UNAVAILABLE"
    assert tk.get("detail") != "$0"
    assert "positman" in result["namespaces"]
    assert "drevo" in result["namespaces"]


def test_closed_loop_records_same_trace(store):
    from roller.dre.decision import decide_for_trade
    from roller.positman.models import DEFAULT_TRADE_ID
    from roller.positman.service import plan

    body = plan(DEFAULT_TRADE_ID, record=True)
    decision = decide_for_trade(DEFAULT_TRADE_ID, record=True)
    assert body["live_execution"] is False
    assert decision["execution_authorized"] is False
    assert decision["execution_boundary"]["status"] == "NOT_SUBMITTED"
    tid = body.get("trace_id") or decision.get("trace_id")
    if tid:
        ok = verify_trace(tid, store)
        assert ok["integrity_status"] == "VERIFIED"
        assert ok["event_count"] >= 1
        if decision.get("trace_id") and body.get("trace_id"):
            assert decision["trace_id"] == body["trace_id"]


def test_systimo_frontend_has_trace_and_orchestra_not_orders():
    if not SYSTIMO_UI.is_dir():
        return
    sources = "\n".join(path.read_text(encoding="utf-8") for path in SYSTIMO_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in SYSTIMO_UI.rglob("*.ts"))
    assert "TRANSITION TRACE" in sources or "Transition trace" in sources
    assert "ORCHESTRA" in sources
    assert "ORCHESTRA_CONTEXT" in sources
    assert "place_order" not in sources
    assert "ENABLE_LIVE_TRADING" not in sources
