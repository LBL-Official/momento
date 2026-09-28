"""Gate 17: normal Execute never parses raw StatsAPI JSON."""

from roller.config import RollerConfig
from roller.research_query.availability import baseball_warehouse_ready
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import ResearchStatus


def test_execute_does_not_parse_raw_statsapi_json(monkeypatch):
    cfg = RollerConfig()
    if not baseball_warehouse_ready(cfg):
        return
    called: list[str] = []

    def boom(*_a, **_k):
        called.append("parse_file")
        raise AssertionError("raw PBP parse during Execute")

    monkeypatch.setattr("roller.mlb.pbp.parse_file", boom)
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
                "dateFrom": "2026-06-18",
                "dateTo": "2026-06-18",
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"}
            ],
        },
        cfg=cfg,
    )
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    out = execute_compiled(compiled, cfg=cfg)
    assert out["execution_status"] == "COMPLETE"
    assert called == []
    assert out["performance"].get("rows_scanned") is not None
