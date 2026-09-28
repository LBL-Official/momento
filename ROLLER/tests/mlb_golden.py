"""Canonical MLB dated FT75 / TE lead+1 fixture.

N=554 is a frozen warehouse identity, not a claim of edge.
Missing settlement stays missing. LAST TRADE != YES BID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.research_query.compiler import compile_draft
from roller.research_query.hashing import layer_hashes
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    ExecutionPath,
    ResearchStatus,
    TouchOrdinal,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "mlb_golden_ft75_lead1_dated.json"


def load_golden() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def golden_draft() -> dict[str, Any]:
    return json.loads(json.dumps(load_golden()["draft"]))


GOLDEN_DRAFT = golden_draft()


def assert_golden_compile(compiled: Any | None = None) -> Any:
    golden = load_golden()
    compiled = compiled or compile_draft(golden["draft"])
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    assert compiled.execution_path is ExecutionPath.GENERIC_QUERY
    assert compiled.reference_match is None
    q = compiled.question
    assert q.basis() == BASIS_LAST_TRADE
    assert q.universe.date_from == "2026-04-01"
    assert q.universe.date_to == "2026-09-08"
    assert q.entry_conditions[0].ordinal is TouchOrdinal.FIRST_TOUCH
    assert q.entry_conditions[0].price_e4 == 7500
    assert q.win_hold is True
    assert any(p.price_e4 == 4000 for p in q.path_conditions)
    assert "kalshi_1m_last_trade" in compiled.available
    assert "polymarket_1m_last_trade" not in compiled.available
    assert "tradable_yes_bid_close_cross" not in compiled.available
    hashes = layer_hashes(q, state=golden["draft"]["teFilters"])
    exp = golden["expected"]
    assert hashes["question_hash"] == exp["question_hash"]
    assert hashes["universe_hash"] == exp["universe_hash"]
    return compiled


def assert_golden_result(out: dict[str, Any]) -> None:
    golden = load_golden()
    exp = golden["expected"]
    prov_exp = golden["provenance"]
    assert out["execution_status"] == "COMPLETE"
    ident = out["identity"]
    trades = out["population"]["trades"]
    n = int(out["summary"]["population_n"])
    yes = int(ident["terminal_yes"])
    no = int(ident["terminal_no"])
    missing = int(ident["terminal_missing"])
    path_true = int(ident["path_true"])
    path_false = int(ident["path_false"])
    win = sum(1 for t in trades if t.get("win_exit"))
    loss = sum(1 for t in trades if t.get("loss_exit"))
    assert n == exp["n"] == len(trades)
    assert win == exp["win_exit"] == path_true
    assert loss == exp["loss_exit"]
    assert path_true == exp["path_true"]
    assert path_false == exp["path_false"]
    assert yes == exp["terminal_yes"]
    assert no == exp["terminal_no"]
    assert missing == exp["terminal_missing"]
    assert yes + no + missing == n
    assert path_true + path_false == n
    assert win + loss == exp["classified"]
    funnel = (out.get("mlb") or {}).get("funnel") or {}
    if funnel:
        assert int(funnel["universe"]) == exp["universe_tickers"]
        assert int(funnel["entry_candidates"]) == exp["entry_candidates"]
        assert int(funnel["te_scoped"]) == exp["n"]
    y25 = [t["ticker"] for t in trades if str(t["ticker"]).startswith("KXMLBGAME-25")]
    assert y25 == []
    for row in trades:
        assert row["entry_operation"] == "FIRST_TOUCH"
        assert row["entry_price_e4"] == 7500
        assert row["price_basis"] == "LAST_TRADE_PRINT"
        assert int(row["te"]["point_differential"]) == 1
    prov = out["provenance"]
    assert prov["path"] == prov_exp["path"]
    assert "warehouse_frozen_v1" not in json.dumps(prov)
    assert prov["market_data"] == prov_exp["market_data"]
    assert prov["market_data_type"] == prov_exp["market_data_type"]
    assert prov["price_basis"] == prov_exp["price_basis"]
    assert prov["price_rule"] == prov_exp["price_rule"]
    assert prov["terminal_source"] == prov_exp["terminal_source"]
    settle = prov.get("settlement") or {}
    assert settle.get("overlay_applied") is prov_exp["overlay_applied"]
    assert settle.get("n_direct") == prov_exp["n_direct"]
    assert settle.get("n_complement") == prov_exp["n_complement"]
    uni = out["compile"]["question"]["universe"]
    assert uni["date_from"] == "2026-04-01"
    assert uni["date_to"] == "2026-09-08"
    assert out["hashes"]["question_hash"] == exp["question_hash"]
