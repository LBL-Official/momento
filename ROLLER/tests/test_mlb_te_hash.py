"""Shared lead chips + MLB TE + hash contract."""

from roller.base_terminal_efficiency.attach import row_matches_te_filters
from roller.research_query.compiler import compile_draft
from roller.research_query.hashing import layer_hashes, normalize_state_filters
from roller.research_query.models import ExecutionPath, ResearchStatus, TouchOrdinal
from tests.test_research_query_engine import _q
from tests.test_research_query_operations import _nba_universe


def test_nba_any_any_hash_unchanged():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    bare = layer_hashes(q)
    scoped = layer_hashes(q, state={"scoreSide": "any", "absDiff": "any"})
    assert normalize_state_filters({"scoreSide": "any", "absDiff": "any"}) is None
    assert bare["question_hash"] == scoped["question_hash"]
    assert bare["entry_hash"] == scoped["entry_hash"]


def test_exact_and_custom_change_question_not_entry():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    bare = layer_hashes(q)
    exact = layer_hashes(q, state={"scoreSide": "leading", "exactDiffs": [1]})
    custom = layer_hashes(q, state={"scoreSide": "leading", "customRange": {"min": 1, "max": 3}})
    assert exact["entry_hash"] == bare["entry_hash"]
    assert custom["entry_hash"] == bare["entry_hash"]
    assert exact["question_hash"] != bare["question_hash"]
    assert custom["question_hash"] != bare["question_hash"]


def test_mlb_period_changes_entry_hash():
    nba = compile_draft(
        {
            "universe": _nba_universe(),
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    mlb = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "T7"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    assert layer_hashes(nba)["entry_hash"] != layer_hashes(mlb)["entry_hash"]
    mlb_te = layer_hashes(mlb, state={"scoreSide": "leading", "outs": [2]})
    assert mlb_te["entry_hash"] == layer_hashes(mlb)["entry_hash"]
    assert mlb_te["question_hash"] != layer_hashes(mlb)["question_hash"]


def test_lead_signs_and_tied():
    plus2 = {"te": {"point_differential": 2, "point_differential_abs_e0": 2}}
    minus2 = {"te": {"point_differential": -2, "point_differential_abs_e0": 2}}
    tied = {"te": {"point_differential": 0, "point_differential_abs_e0": 0}}
    plus7 = {"te": {"point_differential": 7, "point_differential_abs_e0": 7}}
    assert row_matches_te_filters(plus2, {"scoreSide": "leading", "exactDiffs": [1, 2]})
    assert not row_matches_te_filters(minus2, {"scoreSide": "leading", "exactDiffs": [1, 2]})
    assert row_matches_te_filters(minus2, {"scoreSide": "trailing", "exactDiffs": [2]})
    assert not row_matches_te_filters(plus2, {"scoreSide": "trailing", "exactDiffs": [2]})
    assert row_matches_te_filters(plus7, {"scoreSide": "leading", "absDiff": "6_10"})
    assert not row_matches_te_filters(
        {"te": {"point_differential": -7, "point_differential_abs_e0": 7}},
        {"scoreSide": "leading", "absDiff": "6_10"},
    )
    assert row_matches_te_filters(tied, {"scoreSide": "tied", "customRange": {"min": 1, "max": 3}})
    assert not row_matches_te_filters(plus2, {"scoreSide": "tied", "customRange": {"min": 1, "max": 3}})
    assert row_matches_te_filters(plus2, {"scoreSide": "leading", "customRange": {"min": 1, "max": 3}})


def test_mlb_te_fail_closed():
    missing = {"te": {"point_differential": 2, "outs": None, "count_display": None, "runners": None}}
    assert not row_matches_te_filters(missing, {"outs": [2]})
    assert not row_matches_te_filters(missing, {"count": "0-0"})
    assert not row_matches_te_filters(missing, {"runners": "risp"})
    ok = {
        "te": {
            "point_differential": 2,
            "outs": 2,
            "count_display": "3-2",
            "count_leverage": "hitter_ahead",
            "runners": "1st+2nd",
            "yes_batting": True,
            "half": "top",
        }
    }
    assert row_matches_te_filters(ok, {"outs": [2], "count": "3-2", "runners": "risp", "yesBatting": "batting"})
    assert row_matches_te_filters(ok, {"count": "hitter_ahead"})
    assert not row_matches_te_filters(ok, {"count": "0-0"})


def test_baseball_compile_is_ready_not_data_required():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"}],
        }
    )
    assert compiled.status is ResearchStatus.READY
    assert compiled.execution_path is ExecutionPath.GENERIC_QUERY
    assert compiled.question.universe.leagues == ("MLB",)


def test_baseball_alias_league_resolves():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["baseball"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        }
    )
    assert compiled.status is ResearchStatus.READY
    assert compiled.question.universe.leagues == ("MLB",)


def test_mixed_nba_mlb_operation_required():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["basketball", "baseball"],
                "leagues": ["NBA", "MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    )
    assert compiled.status is ResearchStatus.OPERATION_REQUIRED
    assert any("clock" in r.lower() or "MLB" in r for r in compiled.reasons)
