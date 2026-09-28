"""Increment 2: fact index + cache must match Increment 1 goldens exactly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.research_query import cache as rq_cache
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled, execute_question
from roller.research_query.hashing import layer_hashes
from roller.research_query.models import TerminalOutcome

from tests.test_research_query_engine import _q, _series, _snap_quarter
from roller.research_query.models import TouchOrdinal

GOLDEN = Path(__file__).parent / "fixtures" / "research_query_increment1_goldens.json"

GENERIC_IDS = (
    "second_touch_80",
    "first_60_q2",
    "sequential_40_recover_80",
    "layered_and",
)


def _goldens() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_cache_terminal_change_reuses_entry():
    rq_cache.clear()
    tickers = {
        "T-A": _series([7000, 8000], ticker="T-A", game="G-A"),
        "T-B": _series([7000, 8000], ticker="T-B", game="G-B"),
    }
    both = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.BOTH)
    yes = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.YES)
    assert layer_hashes(both)["entry_hash"] == layer_hashes(yes)["entry_hash"]
    hb = layer_hashes(both)
    hy = layer_hashes(yes)
    assert hb["measurement_hash"] != hy["measurement_hash"]
    out_both = execute_compiled(
        compile_draft(
            {
                "universe": {
                    "sports": ["basketball"],
                    "leagues": ["NBA"],
                    "seasons": ["2025-26"],
                    "markets": ["kalshi"],
                    "marketData": ["candles"],
                },
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
                ],
                "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
            }
        ),
        ticker_payloads=tickers,
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={"T-A": {"result": "yes"}, "T-B": {"result": "no"}},
    )
    assert out_both["identity"]["entry_eligible"] == 2
    assert out_both["summary"]["population_n"] == 2


def test_increment2_matches_increment1_goldens():
    if not GOLDEN.exists():
        pytest.skip("Increment 1 goldens missing")
    payload = _goldens()
    by_id = {q["query_id"]: q for q in payload["queries"]}
    rq_cache.clear()

    frozen = execute_question(
        {
            "draft": {
                "universe": {
                    "sports": ["basketball"],
                    "leagues": ["NBA"],
                    "seasons": ["2025-26"],
                    "markets": ["kalshi"],
                    "marketData": ["candles"],
                    "dataSources": ["nba_api"],
                },
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
                ],
                "exitConditions": [
                    {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
                    {"id": "t", "kind": "terminal", "family": "both"},
                ],
            }
        }
    )
    assert frozen["summary"]["population_n"] == by_id["FIRST80_frozen"]["population_n"]
    assert (frozen.get("compile") or {}).get("execution_path") == "frozen_reference"

    drafts = {
        "second_touch_80": {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dataSources": ["nba_api"],
            },
            "entryConditions": [{"id": "e1", "family": "second_touch", "priceCents": 80}],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
        "first_60_q2": {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dataSources": ["nba_api"],
            },
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 60, "period": "Q2"}
            ],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
        "sequential_40_recover_80": {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dataSources": ["nba_api"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
                {"id": "p2", "kind": "path", "family": "recover", "priceCents": 80, "sequential": True},
                {"id": "t", "kind": "terminal", "family": "both"},
            ],
        },
        "layered_and": {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dataSources": ["nba_api"],
            },
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"},
                {"id": "e2", "family": "first_touch", "priceCents": 60},
            ],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
    }

    first = None
    for qid in GENERIC_IDS:
        out = execute_question({"draft": drafts[qid]})
        gold = by_id[qid]
        assert out["execution_status"] == "COMPLETE"
        assert out["provenance"]["path"] == "generic_query"
        assert "warehouse_frozen_v1" not in json.dumps(out["provenance"])
        assert out["summary"]["population_n"] == gold["population_n"]
        assert out["identity"]["entry_eligible"] == gold["identity"]["entry_eligible"]
        cells = {c["key"]: c["n"] for c in out["empirical_partition"]["cells"]}
        assert cells == gold["partition"]
        assert out["empirical_partition"]["n_missing"] == gold["terminal_missing"]
        if first is None:
            first = out
        else:
            assert out["performance"]["cache_hit_warehouse"] is True

    again = execute_question({"draft": drafts["second_touch_80"]})
    assert again["summary"]["population_n"] == by_id["second_touch_80"]["population_n"]
    assert again["performance"]["cache_hit_warehouse"] is True
    assert again["performance"]["cache_hit_entry"] is True
    assert again["performance"]["cache_hit_path"] is True
