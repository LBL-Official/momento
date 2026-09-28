"""Frozen FIRST80_Q3 export is 290, not 200."""

from __future__ import annotations

import pytest

from roller.dashboard_adapter.bindings import (
    warehouse_barrier_trades_available,
    warehouse_first80_available,
)
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object import load_sample
from roller.superasi.import_source import authoritative_trades, import_from_roller


pytestmark = pytest.mark.skipif(
    not warehouse_first80_available() or not warehouse_barrier_trades_available(),
    reason="warehouse FIRST80 artifacts missing",
)


def test_first80_q3_full_trades_not_preview():
    spec = load_sample("first80_q3_path_terminal.json")
    result = execute_research_object(spec)
    assert result["population"]["count"] == 290
    assert result["population"]["rows_truncated"] is True
    assert len(result["population"]["rows"]) == 200
    trades = authoritative_trades(result)
    assert len(trades) == 290


def test_import_first80_q3_n_290(tmp_path):
    spec = load_sample("first80_q3_path_terminal.json")
    out = import_from_roller({"research_spec": spec}, root=tmp_path)
    assert out["population_n"] == 290
    assert out["source"] == "roller_frozen"
