"""Phase 9 NBA warehouse coverage catalog. No Confirm & Run CSV. No execution."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.research_query.models import ResearchStatus
from roller.warehouse.catalog import catalog, get_catalog
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    CapabilityName,
    WarehouseCatalog,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_MANIFEST = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse" / "manifest.json"


def test_existing_csv_catalog_is_unchanged():
    refs = catalog()
    assert refs
    assert all(hasattr(r, "datasets") for r in refs)


def test_nba_catalog_loads_and_counts():
    cat = get_catalog(RollerConfig(ROLLER_ROOT))
    assert isinstance(cat, WarehouseCatalog)
    assert cat.games["game_count"] == 1362
    assert cat.markets["market_count"] == 2724
    assert cat.links["linked_count"] == 2724
    assert cat.links["unlinked_count"] == 0
    assert cat.observations["observation_count"] == 6165183
    assert cat.observations["observation_basis"] == OBS_BASIS
    assert cat.observations["resolution"] == OBS_RESOLUTION
    assert cat.observations["PIT_available"] is True
    assert cat.observations["pit_field"] == PIT_FIELD
    assert cat.observations["min_available_at"]
    assert cat.observations["max_available_at"]
    assert cat.settlements["settlement_count"] == 2724
    assert cat.settlements["YES"] == 1359
    assert cat.settlements["NO"] == 1359
    assert cat.settlements["INVALID"] == 6
    assert cat.settlements["MISSING"] == 0
    assert cat.settlements["INVALID"] != cat.settlements["NO"]
    assert cat.pbp["pbp_event_count"] == 780137
    assert cat.pbp["pbp_pit_aligned_to_candles"] is False
    assert cat.pbp["clock_available"] is True
    assert cat.pbp["event_timestamp_available"] is True
    assert cat.orderbook["availability"] == "SOURCE_UNAVAILABLE"
    assert cat.orderbook["rows"] == 0
    assert cat.orderbook["depth"] == "NONE"
    assert cat.orderbook["top_of_book"] == "NONE"


def test_capability_matrix_and_resolve():
    cat = get_catalog(RollerConfig(ROLLER_ROOT))
    ready = cat.resolve(
        [
            CapabilityName.GAME,
            CapabilityName.TRADABLE_YES_BID_1M,
            CapabilityName.CANDLE_PIT,
            CapabilityName.SETTLEMENT,
            CapabilityName.PBP,
        ]
    )
    assert ready.status is ResearchStatus.READY
    assert "ZERO_RESULTS" not in ready.to_dict()
    tick = cat.resolve([CapabilityName.TICK])
    assert tick.status is ResearchStatus.DATA_REQUIRED
    assert "TICK" in tick.missing_data
    l2 = cat.resolve([CapabilityName.HISTORICAL_L2])
    assert l2.status is ResearchStatus.DATA_REQUIRED
    align = cat.resolve([CapabilityName.PBP_MARKET_PIT_ALIGNMENT])
    assert align.status is ResearchStatus.OPERATION_REQUIRED
    assert "PBP_MARKET_PIT_ALIGNMENT" in align.missing_operations
    both = cat.resolve([CapabilityName.HISTORICAL_L2, CapabilityName.PBP_MARKET_PIT_ALIGNMENT])
    assert both.status is ResearchStatus.DATA_REQUIRED
    public = ready.to_dict()
    dumped = str(public)
    assert "/Users/" not in dumped
    assert "derived/warehouse" not in dumped
    assert public["observation_basis"] == OBS_BASIS
    assert public["pit_field"] == PIT_FIELD
    assert public["catalog_version"] == CATALOG_VERSION


def test_date_coverage_inside_and_outside():
    cat = get_catalog(RollerConfig(ROLLER_ROOT))
    inside = cat.date_coverage("2025-10-10", "2025-10-31")
    assert inside["warehouse_contains_date_range"] is True
    assert inside["warehouse_outside_date_range"] is False
    outside = cat.date_coverage("2019-01-01", "2019-01-31")
    assert outside["warehouse_contains_date_range"] is False
    assert outside["warehouse_outside_date_range"] is True


def test_deterministic_repeated_build():
    cfg = RollerConfig(ROLLER_ROOT)
    a = get_catalog(cfg)
    b = get_catalog(cfg)
    assert a.public_coverage() == b.public_coverage()
    assert a.resolve([CapabilityName.SETTLEMENT]).to_dict() == b.resolve([CapabilityName.SETTLEMENT]).to_dict()


def test_no_csv_or_confirm_and_run_dependency():
    src = inspect.getsource(get_catalog)
    # Re-export wrapper; implementation is coverage.get_catalog.
    from roller.warehouse import coverage as cov

    body = inspect.getsource(cov.get_catalog)
    assert "kalshi_markets.csv" not in body
    assert "official_settlement" not in body
    assert "load_dataset" not in body
    assert "first80" not in body.lower()
    src_load = inspect.getsource(load_dataset)
    assert "get_catalog" not in src_load


def test_no_inferred_l2_or_score_settlement():
    cat = get_catalog(RollerConfig(ROLLER_ROOT))
    assert cat.orderbook["rows"] == 0
    assert cat.settlements["INVALID"] == 6
    body = inspect.getsource(__import__("roller.warehouse.coverage", fromlist=["x"]))
    assert "home_win" not in body
    assert "yes_bid_close" not in inspect.getsource(cat.resolve)


def test_execute_does_not_import_coverage():
    root = Path(__file__).resolve().parents[1] / "roller"
    tree = ast.parse((root / "research_query" / "execute.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.warehouse.coverage" not in imported
