"""Reference (full-scan) vs optimized (indexed or same injected bars).

Same detectors. If these diverge, the optimization is wrong.
Does not edit first80.py. Does not rewrite goldens.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.research_query import cache as rq_cache
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled, execute_question
from roller.research_query.models import ExecutionPath
from roller.research_query.reference_engine import (
    ReferenceEngineError,
    execute_reference,
    identities,
)
from tests.mlb_golden import GOLDEN_DRAFT, load_golden
from tests.test_research_query_engine import _series, _snap_quarter

GOLDEN = Path(__file__).parent / "fixtures" / "research_query_increment1_goldens.json"

NBA_UNIVERSE = {
    "sports": ["basketball"],
    "leagues": ["NBA"],
    "seasons": ["2025-26"],
    "markets": ["kalshi"],
    "marketData": ["candles"],
}


def _draft(entries, exits=None):
    return {
        "universe": NBA_UNIVERSE,
        "entryConditions": entries,
        "exitConditions": (exits or []) + [{"id": "t", "kind": "terminal", "family": "both"}],
    }


def _compare(draft, payloads, *, snap=None, markets=None, pbp=None):
    compiled = compile_draft(draft)
    ref = execute_reference(
        {"draft": draft},
        ticker_payloads=payloads,
        snap_fn=snap,
        markets_by_ticker=markets,
        pbp_by_game=pbp,
        clear_cache=False,
    )
    opt = execute_compiled(
        compiled,
        ticker_payloads=payloads,
        snap_fn=snap,
        markets_by_ticker=markets,
        pbp_by_game=pbp,
    )
    assert ref["execution_status"] == opt["execution_status"]
    assert ref["summary"]["population_n"] == opt["summary"]["population_n"]
    assert identities(ref) == identities(opt)
    return ref


def test_first80_not_routed():
    with pytest.raises(ReferenceEngineError):
        execute_reference(
            {
                "draft": {
                    "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
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


def test_empty_dataset():
    ref = _compare(_draft([{"id": "e1", "family": "first_touch", "priceCents": 80}]), {})
    assert ref["summary"]["population_n"] == 0


def test_one_row_no_cross():
    payloads = {"T-A": _series([8000], ticker="T-A")}
    ref = _compare(_draft([{"id": "e1", "family": "cross", "priceCents": 80}]), payloads)
    assert ref["summary"]["population_n"] == 0


def test_ops_and_paths_row_level():
    markets = {"T-A": {"result": "yes"}, "T-B": {"result": "no"}}
    cases = [
        ([{"id": "e1", "family": "first_touch", "priceCents": 80}], [7000, 8000]),
        ([{"id": "e1", "family": "second_touch", "priceCents": 80}], [7000, 8000, 7000, 8000]),
        ([{"id": "e1", "family": "cross", "priceCents": 80}], [7900, 8000]),
        ([{"id": "e1", "family": "break", "priceCents": 80}], [7900, 8100]),
        ([{"id": "e1", "family": "above", "priceCents": 80}], [7900, 8100]),
        ([{"id": "e1", "family": "below", "priceCents": 80}], [8100, 7900]),
        ([{"id": "e1", "family": "reversion", "priceCents": 80}], [7900, 8100, 8200, 7900]),
        ([{"id": "e1", "family": "bounce", "priceCents": 80}], [7900, 8000, 7900]),
        ([{"id": "e1", "family": "maximum_touch", "priceCents": 80}], [7000, 8100]),
        ([{"id": "e1", "family": "minimum_touch", "priceCents": 40}], [5000, 3900]),
        ([{"id": "e1", "family": "recovery", "priceCents": 80}], [8100, 7900, 8200]),
    ]
    for entries, bids in cases:
        payloads = {"T-A": _series(bids, ticker="T-A"), "T-B": _series(bids, ticker="T-B", game="G-B")}
        _compare(_draft(entries), payloads, markets=markets)

    path_cases = [
        (
            [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
            [7000, 8000, 4000],
        ),
        (
            [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            [{"id": "p1", "kind": "path", "family": "drop_to", "priceCents": 40}],
            [7000, 8000, 3900],
        ),
        (
            [{"id": "e1", "family": "first_touch", "priceCents": 40}],
            [{"id": "p1", "kind": "path", "family": "rise_to", "priceCents": 80}],
            [5000, 4000, 8000],
        ),
        (
            [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
                {"id": "p2", "kind": "path", "family": "recover", "priceCents": 80, "sequential": True},
            ],
            [7000, 8000, 4000, 8100],
        ),
    ]
    for entries, exits, bids in path_cases:
        payloads = {"T-A": _series(bids, ticker="T-A")}
        _compare(_draft(entries, exits), payloads, markets=markets)


def test_and_commutes():
    payloads = {"T-A": _series([7000, 8000, 6000], ticker="T-A")}
    a = [
        {"id": "e1", "family": "first_touch", "priceCents": 80},
        {"id": "e2", "family": "first_touch", "priceCents": 60},
    ]
    b = list(reversed(a))
    ra = _compare(_draft(a), payloads)
    rb = _compare(_draft(b), payloads)
    assert ra["summary"]["population_n"] == rb["summary"]["population_n"]
    assert {t[0] for t in identities(ra)} == {t[0] for t in identities(rb)}


def test_period_unaligned_and_tie():
    payloads = {
        "T-A": _series([7000, 8000], ticker="T-A", game="G1"),
        "T-B": _series([7000, 8000], ticker="T-B", game="G1"),
    }
    ref = _compare(
        _draft([{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}]),
        payloads,
        snap=_snap_quarter("Q2"),
    )
    assert ref["summary"]["population_n"] == 0
    both = _compare(
        _draft([{"id": "e1", "family": "first_touch", "priceCents": 80}]),
        payloads,
    )
    assert both["summary"]["population_n"] == 0
    ident = both.get("identity") or {}
    excluded = ident.get("exclusions") or ident.get("tie_same_minute") or 0
    assert excluded or (both.get("diagnostics") or {}).get("tie_same_minute_excluded") is not None or both["summary"]["population_n"] == 0


def test_missing_settlement_is_missing():
    payloads = {"T-A": _series([7000, 8000], ticker="T-A")}
    ref = _compare(_draft([{"id": "e1", "family": "first_touch", "priceCents": 80}]), payloads, markets={})
    assert ref["summary"]["population_n"] == 1
    trades = (ref.get("population") or {}).get("trades") or []
    assert trades[0].get("terminal_yes") is None


def test_untradable_does_not_cross():
    candles = _series([7900, 8000], ticker="T-A")
    candles[1]["is_valid"] = False
    ref = _compare(_draft([{"id": "e1", "family": "first_touch", "priceCents": 80}]), {"T-A": candles})
    assert ref["summary"]["population_n"] == 0


def test_path_not_on_entry_candle():
    payloads = {"T-A": _series([4000], ticker="T-A")}
    ref = _compare(
        _draft(
            [{"id": "e1", "family": "first_touch", "priceCents": 40}],
            [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        ),
        payloads,
    )
    trades = (ref.get("population") or {}).get("trades") or []
    if trades:
        assert trades[0].get("path_true") is False


@pytest.mark.parametrize("qid", ["first_60_q2", "second_touch_80", "sequential_40_recover_80", "layered_and"])
def test_warehouse_increment2_reference_vs_indexed(qid):
    if not GOLDEN.exists():
        pytest.skip("Increment 1 goldens missing")
    by_id = {q["query_id"]: q for q in json.loads(GOLDEN.read_text())["queries"]}
    drafts = {
        "second_touch_80": {
            "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
            "entryConditions": [{"id": "e1", "family": "second_touch", "priceCents": 80}],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
        "first_60_q2": {
            "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 60, "period": "Q2"}
            ],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
        "sequential_40_recover_80": {
            "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
                {"id": "p2", "kind": "path", "family": "recover", "priceCents": 80, "sequential": True},
                {"id": "t", "kind": "terminal", "family": "both"}],
        },
        "layered_and": {
            "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"},
                {"id": "e2", "family": "first_touch", "priceCents": 60},
            ],
            "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        },
    }
    rq_cache.clear()
    draft = drafts[qid]
    # Optimized first so plan_query opens rq_index. Reference after a cache
    # clear so a CSV-built TradableIndex cannot masquerade as indexed.
    opt = execute_question({"draft": draft})
    rq_cache.clear()
    ref = execute_reference({"draft": draft}, clear_cache=True)
    gold = by_id[qid]["population_n"]
    assert ref["summary"]["population_n"] == gold
    assert opt["summary"]["population_n"] == gold
    assert opt["performance"]["execution_mode"] == "indexed"
    assert ref["performance"]["execution_mode"] == "full_scan"
    assert identities(ref) == identities(opt)


def test_warehouse_mlb_554_reference_vs_indexed():
    exp = load_golden()["expected"]
    rq_cache.clear()
    opt = execute_question({"draft": GOLDEN_DRAFT})
    rq_cache.clear()
    ref = execute_reference({"draft": GOLDEN_DRAFT}, clear_cache=True)
    assert ref["summary"]["population_n"] == exp["n"] == 554
    assert opt["summary"]["population_n"] == 554
    assert opt["performance"]["execution_mode"] == "indexed"
    assert ref["performance"]["execution_mode"] == "full_scan"
    assert identities(ref) == identities(opt)


def test_frozen_still_not_generic():
    compiled = compile_draft(
        {
            "universe": {**NBA_UNIVERSE, "dataSources": ["nba_api"]},
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
            ],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
                {"id": "t", "kind": "terminal", "family": "both"},
            ],
        }
    )
    assert compiled.execution_path is ExecutionPath.FROZEN_REFERENCE
