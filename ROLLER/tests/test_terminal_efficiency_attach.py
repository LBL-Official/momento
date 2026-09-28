"""Base TE attach on generic rows. Does not change path_true or FIRST80."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.base_terminal_efficiency.attach import attach_to_row, row_matches_te_filters, summarize_rows
from roller.research_query.execute import apply_te_population_scope
from roller.research_query.hashing import layer_hashes, normalize_state_filters
from roller.base_terminal_efficiency.models import WIN
from roller.research_query.compiler import compile_draft
from roller.research_query.entry_engine import TouchEvent, TradableBar
from roller.research_query.execute import execute_compiled
from roller.research_query.models import EntryOp, ExitOutcome, PathCondition, PathOp, ResearchStatus, TouchOrdinal
from tests.test_research_query_engine import _q, _series
from tests.test_research_query_operations import _nba_universe

UTC = timezone.utc


def _tb(minute: int, bid: int) -> TradableBar:
    return TradableBar(
        ts=datetime(2025, 12, 20, 20, minute, tzinfo=UTC),
        bid=bid,
        ask=bid + 400,
        volume=10,
        ticker="T-A",
        game_id="G1",
        raw={"team_side": "home"},
    )


def test_attach_does_not_change_path_true():
    bars = [_tb(0, 5900), _tb(1, 6000), _tb(2, 9000)]
    entry = TouchEvent(
        ordinal=TouchOrdinal.FIRST_TOUCH,
        touch_index=1,
        price_e4=6000,
        bar=bars[1],
        snap={},
        alignment="ALIGNED",
        operation=EntryOp.CROSS,
    )
    q = _q(
        TouchOrdinal.FIRST_TOUCH,
        6000,
        path=(
            PathCondition(id="w", op=PathOp.REACH, price_e4=9000, outcome=ExitOutcome.WIN),
            PathCondition(id="l", op=PathOp.DROP_TO, price_e4=4000, outcome=ExitOutcome.LOSS),
        ),
    )
    row = {"ticker": "T-A", "path_true": True, "win_exit": True, "exit_outcome": "WIN_EXIT"}
    attach_to_row(row, entry=entry, bars=bars, question=q)
    assert row["path_true"] is True
    assert row["exit_outcome"] == "WIN_EXIT"
    assert row["te"]["exit_outcome"] == WIN
    assert row["te"]["entry_price_e4"] == 6000


def test_te_filter_leading_only():
    rows = [
        {"te": {"point_differential": 4, "point_differential_abs_e0": 4}},
        {"te": {"point_differential": -3, "point_differential_abs_e0": 3}},
    ]
    assert row_matches_te_filters(rows[0], {"scoreSide": "leading"})
    assert not row_matches_te_filters(rows[1], {"scoreSide": "leading"})
    summary = summarize_rows(rows, {"scoreSide": "leading"})
    assert summary["n_te_scoped"] == 1


def test_execute_attaches_te_without_blocking(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {"id": "p2", "kind": "path", "family": "drop_to", "priceCents": 40, "outcome": "loss"},
        ],
        "teFilters": {"scoreSide": "any", "absDiff": "any"},
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.READY
    out = execute_compiled(
        c,
        ticker_payloads={"T-A": _series([5900, 6000, 7000, 9000])},
        te_filters=draft["teFilters"],
    )
    trades = out["population"]["trades"]
    assert trades
    assert trades[0]["entry_operation"] == "CROSS"
    assert "te" in trades[0]
    assert out["base_terminal_efficiency"]["n_te_attached"] >= 1
    assert trades[0]["path_true"] in (True, False)


def test_incomplete_horizon_still_fail_closed(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": _nba_universe(),
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 60}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {"id": "h1", "kind": "horizon", "family": "horizon_game_win", "outcome": "win"},
        ],
    }
    c = compile_draft(draft)
    assert c.status is ResearchStatus.OPERATION_REQUIRED


def test_te_scope_changes_reported_n():
    rows = [
        {"te": {"point_differential": 8, "point_differential_abs_e0": 8}, "league": "NBA"},
        {"te": {"point_differential": -2, "point_differential_abs_e0": 2}, "league": "NCAAB"},
        {"te": {}, "league": "NBA"},
    ]
    kept_any, scope_any = apply_te_population_scope(rows, {"scoreSide": "any", "absDiff": "any"})
    assert len(kept_any) == 3
    assert scope_any["requested"] is None
    kept, scope = apply_te_population_scope(rows, {"scoreSide": "leading", "absDiff": "6_10"})
    assert [r["league"] for r in kept] == ["NBA"]
    assert scope["n_entry"] == 3
    assert scope["n_scoped"] == 1
    assert scope["n_dropped"] == 2
    assert scope["requested"] == {"score_side": "leading", "abs_diff": "6_10"}


def test_te_state_changes_question_hash_not_entry_hash():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    bare = layer_hashes(q)
    scoped = layer_hashes(q, state={"scoreSide": "leading", "absDiff": "6_10"})
    assert normalize_state_filters({"scoreSide": "any", "absDiff": "any"}) is None
    assert bare["entry_hash"] == scoped["entry_hash"]
    assert bare["question_hash"] != scoped["question_hash"]
    assert bare["state_hash"] != scoped["state_hash"]
    assert layer_hashes(q)["question_hash"] == bare["question_hash"]
