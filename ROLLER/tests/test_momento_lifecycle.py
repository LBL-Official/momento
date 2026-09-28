"""Offline FIRST80 lifecycle. No hidden hops. No NBA submit."""

from __future__ import annotations

from roller.choosin_texas.locks import POOL_CELLS, POOL_N, STOP_CENTS
from roller.momento.lifecycle import run_offline_first80
from roller.momento.registry import LIVE_EXECUTION


REQUIRED_HOPS = (
    "data_ingestion",
    "database",
    "data_modeling",
    "fair_odds_modeling",
    "in_house_odds_modeling",
    "game_modeling",
    "signal_generation",
    "trade_breakdown",
    "position_stratification",
    "dynamic_risk_engine",
    "hedging_analysis",
    "relative_value_hedging",
    "position_management",
    "algorithmic_execution",
    "trade_reconciliation",
    "system_orchestration",
)


def test_offline_lifecycle_traverse():
    assert LIVE_EXECUTION is False
    trace = run_offline_first80()
    assert trace["live_execution"] is False
    assert trace["submits"] is False
    assert trace["nba_bot"] == "NOT_IMPLEMENTED"
    assert trace["legacy_stop_cents"] == STOP_CENTS
    seen = [hop["source_system"] for hop in trace["hops"]]
    for name in REQUIRED_HOPS:
        assert name in seen
    objects = trace["objects"]
    assert objects["trade"]["n"] == POOL_N
    assert objects["trade"]["s_numer"] == POOL_CELLS[0]
    assert objects["trade"]["stop_cents"] == 40
    assert objects["dre"]["phase3_is_execution_policy"] is False
    assert objects["execution_intent"]["submits"] is False
    assert objects["execution_intent"]["bot_id"] == "nba-first80-001"
    assert objects["fill"]["observed"] is False
    assert objects["fair_odds"]["status"] == "NOT_IMPLEMENTED"
    for key, payload in objects.items():
        assert payload["source_system"]
        assert payload["generated_at"]
        assert payload["as_of"]
        if key != "fair_odds":
            assert payload.get("live_execution") is False
