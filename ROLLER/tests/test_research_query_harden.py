"""Increment 1: identity, hashes, reserved scopes, telemetry. No FIRST80 edits."""

from __future__ import annotations

import json

from roller.research_query.compiler import compile_draft, compile_question, question_from_draft
from roller.research_query.execute import execute_compiled, execute_question
from roller.research_query.hashing import layer_hashes, question_hash
from roller.research_query.identity import identity_holds
from roller.research_query.models import (
    EntryCondition,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.research_query.scopes import RESERVED_FAMILIES

from tests.test_research_query_engine import _q, _series, _snap_quarter


def _payload(tickers: dict, snap="Q3", markets=None):
    compiled = compile_question(_q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3"))
    return execute_compiled(
        compiled,
        ticker_payloads=tickers,
        snap_fn=_snap_quarter(snap),
        markets_by_ticker=markets or {t: {"result": "yes"} for t in tickers},
    )


def test_identity_universe_minus_exclusions():
    tickers = {
        "T-A": _series([7000, 8000], ticker="T-A", game="G-A"),
        "T-B": _series([5000, 5500], ticker="T-B", game="G-B"),
        "T-C": _series([7000, 8000], ticker="T-C", game="G-C"),
    }
    out = _payload(tickers)
    ident = out["identity"]
    assert ident["universe_tickers"] == 3
    assert ident["entry_eligible"] == 2
    assert ident["exclusions"]["no_nth_touch"] == 1
    assert identity_holds(ident)
    assert out["performance"]["total_ms"] >= 0
    assert {s["stage"] for s in out["stages"]} >= {
        "universe_loaded",
        "entry_events",
        "path",
        "measurements",
    }


def test_yes_plus_no_plus_missing_eq_measured():
    tickers = {
        "T-A": _series([7000, 8000, 7000, 8000, 4000], ticker="T-A", game="G-A"),
        "T-B": _series([7000, 8000, 7000, 8000, 4000], ticker="T-B", game="G-B"),
        "T-C": _series([7000, 8000, 7000, 8000, 4000], ticker="T-C", game="G-C"),
    }
    q = _q(
        TouchOrdinal.SECOND_TOUCH,
        8000,
        None,
        path=(PathCondition(id="p", op=PathOp.REACH, price_e4=4000),),
        terminal=TerminalOutcome.BOTH,
    )
    compiled = compile_question(q)
    out = execute_compiled(
        compiled,
        ticker_payloads=tickers,
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={
            "T-A": {"result": "yes"},
            "T-B": {"result": "no"},
            "T-C": {},
        },
    )
    ident = out["identity"]
    assert ident["terminal_yes"] + ident["terminal_no"] + ident["terminal_missing"] == ident[
        "measured_eligible"
    ]
    p = out["empirical_partition"]
    cells = {c["key"]: c["n"] for c in p["cells"]}
    assert cells["T_AND_W"] + cells["T_AND_NOT_W"] + cells["NOT_T_AND_W"] + cells["NOT_T_AND_NOT_W"] == p[
        "n_joint_available"
    ]
    assert identity_holds(ident)


def test_terminal_yes_is_filter_not_entry_rewrite():
    tickers = {
        "T-A": _series([7000, 8000], ticker="T-A", game="G-A"),
        "T-B": _series([7000, 8000], ticker="T-B", game="G-B"),
    }
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.YES)
    compiled = compile_question(q)
    out = execute_compiled(
        compiled,
        ticker_payloads=tickers,
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={"T-A": {"result": "yes"}, "T-B": {"result": "no"}},
    )
    ident = out["identity"]
    assert ident["entry_eligible"] == 2
    assert ident["reported_n"] == 1
    assert ident["terminal_is_measurement_filter"] is True
    assert out["summary"]["population_n"] == 1


def test_reserved_scope_operation_required_not_zero():
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"},
            {"id": "e2", "family": "xib", "priceCents": 80},
        ],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    out = execute_question({"draft": draft})
    assert out["execution_status"] == "OPERATION_REQUIRED"
    assert out["summary"]["population_n"] is None
    assert "xib" in " ".join(c.reasons).lower() or any("xib" in r.lower() for r in c.reasons)


def test_game_scope_family_not_empty_population():
    assert "xib" in RESERVED_FAMILIES
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "team_win_pct", "priceCents": 80}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    out = execute_question({"draft": draft})
    assert out["execution_status"] == "OPERATION_REQUIRED"
    assert out["population"]["status"] == "ABSENT"


def test_question_hash_stable_and_distinct():
    a = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    b = _q(TouchOrdinal.SECOND_TOUCH, 8000, "Q3")
    c = _q(TouchOrdinal.FIRST_TOUCH, 6000, "Q3")
    d = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q2")
    assert question_hash(a) != question_hash(b)
    assert question_hash(a) != question_hash(c)
    assert question_hash(a) != question_hash(d)
    assert question_hash(a) == question_hash(
        ResearchQuestion.from_dict(json.loads(json.dumps(a.to_dict())))
    )


def test_serialization_reach_not_drop_sequential_not_and():
    reach = PathCondition(id="p", op=PathOp.REACH, price_e4=4000, sequential=True)
    drop = PathCondition(id="p", op=PathOp.DROP_TO, price_e4=4000, sequential=True)
    rec = PathCondition(id="p2", op=PathOp.RECOVER, price_e4=8000, sequential=True)
    q_reach = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", path=(reach,))
    q_drop = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", path=(drop,))
    q_seq = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", path=(reach, rec))
    q_and = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    q_and = ResearchQuestion(
        universe=q_and.universe,
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3"),
            EntryCondition(id="e2", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6000, period="Q3"),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    assert question_from_draft(
        {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
                {"id": "t", "kind": "terminal", "family": "both"},
            ],
        }
    ).path_conditions[0].op is PathOp.REACH
    assert layer_hashes(q_reach)["path_hash"] != layer_hashes(q_drop)["path_hash"]
    assert layer_hashes(q_seq)["path_hash"] != layer_hashes(q_and)["path_hash"]
    assert layer_hashes(q_seq)["entry_hash"] != layer_hashes(q_and)["entry_hash"]


def test_layer_hashes_terminal_change_only_measurement():
    both = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.BOTH)
    yes = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.YES)
    hb = layer_hashes(both)
    hy = layer_hashes(yes)
    assert hb["entry_hash"] == hy["entry_hash"]
    assert hb["path_hash"] == hy["path_hash"]
    assert hb["universe_hash"] == hy["universe_hash"]
    assert hb["measurement_hash"] != hy["measurement_hash"]


def test_generic_envelope_has_performance_keys(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    q = _q(TouchOrdinal.SECOND_TOUCH, 8000, "Q3")
    compiled = compile_question(q)
    out = execute_compiled(
        compiled,
        ticker_payloads={"T-A": _series([7000, 8000, 7000, 8000])},
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={"T-A": {"result": "yes"}},
    )
    for key in (
        "dataset_load_ms",
        "entry_scan_ms",
        "pbp_alignment_ms",
        "population_intersection_ms",
        "path_measurement_ms",
        "aggregation_ms",
        "total_ms",
    ):
        assert key in out["performance"]
    assert out["hashes"]["question_hash"] == question_hash(q)
    assert out["provenance"]["path"] == "generic_query"
    assert "warehouse_frozen_v1" not in json.dumps(out["provenance"])
