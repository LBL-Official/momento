"""Tennis hashes must not mutate NBA/NCAAB hashes. TE chips stay off entry_hash."""

from roller.research_query.compiler import compile_draft
from roller.research_query.hashing import layer_hashes, normalize_state_filters
from roller.research_query.models import TouchOrdinal
from tests.test_research_query_engine import _q
from tests.test_research_query_operations import _nba_universe


def test_nba_any_any_still_unchanged():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    bare = layer_hashes(q)
    scoped = layer_hashes(q, state={"scoreSide": "any", "absDiff": "any"})
    tennis_idle = layer_hashes(q, state={"scoreSide": "any", "absDiff": "any", "tennisServe": []})
    assert normalize_state_filters({"scoreSide": "any", "absDiff": "any"}) is None
    assert bare["question_hash"] == scoped["question_hash"] == tennis_idle["question_hash"]
    assert bare["entry_hash"] == scoped["entry_hash"]


def test_tennis_te_changes_question_not_entry():
    tennis = compile_draft(
        {
            "universe": {
                "sports": ["tennis"],
                "leagues": ["ATP"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "S1"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    bare = layer_hashes(tennis)
    te = layer_hashes(tennis, state={"tennisServe": ["serving"], "tennisSetLead": {"scoreSide": "leading"}})
    assert te["entry_hash"] == bare["entry_hash"]
    assert te["question_hash"] != bare["question_hash"]
    assert te["state_hash"] != bare["state_hash"]


def test_tennis_set_window_changes_entry_hash():
    nba = compile_draft(
        {
            "universe": _nba_universe(),
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    s1 = compile_draft(
        {
            "universe": {
                "sports": ["tennis"],
                "leagues": ["ATP"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "S1"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    s2 = compile_draft(
        {
            "universe": {
                "sports": ["tennis"],
                "leagues": ["ATP"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "S2"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    ).question
    assert layer_hashes(nba)["entry_hash"] != layer_hashes(s1)["entry_hash"]
    assert layer_hashes(s1)["entry_hash"] != layer_hashes(s2)["entry_hash"]
