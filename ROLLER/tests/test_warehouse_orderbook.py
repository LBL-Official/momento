"""Phase 7 NBA orderbook boundary. Capability only. No L2 warehouse."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.warehouse.layout_v0 import orderbook_capability_path, orderbook_dir
from roller.warehouse.orderbook import (
    AVAILABILITY_UNAVAILABLE,
    MARKET_DATA_BASIS,
    declare_nba_orderbook_capability,
    inventory_nba_orderbook,
    nba_orderbook_parquet_files,
    reject_hypothetical_l2,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_STUB = (
    ROLLER_ROOT
    / "data"
    / "nba"
    / "2025_2026"
    / "canonical"
    / "kalshi_orderbook_snapshots"
    / "month=empty.csv"
)


def _stable(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in {"updated_at", "capability_path", "orderbook_dir"}}


def test_candle_columns_are_not_an_orderbook_snapshot():
    with pytest.raises(ValueError, match="not an orderbook snapshot"):
        reject_hypothetical_l2(
            pd.DataFrame(
                [
                    {
                        "ticker": "KX-A",
                        "yes_bid_open": 4600,
                        "yes_bid_high": 4700,
                        "yes_bid_low": 4500,
                        "yes_bid_close": 4600,
                        "volume": 12,
                    }
                ]
            )
        )
    with pytest.raises(ValueError, match="cannot upgrade"):
        reject_hypothetical_l2(
            pd.DataFrame(
                [
                    {
                        "ticker": "KX-A",
                        "yes_bid_close": 4600,
                        "best_yes_bid_e4": 4600,
                    }
                ]
            )
        )


def test_hypothetical_l2_rejects_malformed_and_negative():
    with pytest.raises(ValueError, match="negative depth"):
        reject_hypothetical_l2(
            pd.DataFrame([{"ticker": "KX-A", "best_yes_bid_e4": 4300, "yes_bid_depth": -1}])
        )
    with pytest.raises(ValueError, match="malformed levels"):
        reject_hypothetical_l2(
            pd.DataFrame([{"ticker": "KX-A", "best_yes_bid_e4": 4300, "levels": "not-json"}])
        )


def test_declare_does_not_emit_parquet(tmp_path: Path, roller_env: Path):
    cfg = RollerConfig(roller_env)
    payload = declare_nba_orderbook_capability(cfg)
    assert payload["availability"] == AVAILABILITY_UNAVAILABLE
    assert payload["snapshot_rows"] == 0
    assert payload["depth"] == "NONE"
    assert payload["top_of_book"] == "NONE"
    assert payload["market_data_basis"] == MARKET_DATA_BASIS
    assert payload["parquet_emitted"] is False
    assert nba_orderbook_parquet_files(cfg) == []
    assert orderbook_capability_path(cfg).is_file()
    assert not list(orderbook_dir(cfg).glob("*.parquet"))
    again = declare_nba_orderbook_capability(cfg)
    assert _stable(payload) == _stable(again)


def test_mlb_orderbook_is_not_an_inspected_nba_path():
    cfg = RollerConfig(ROLLER_ROOT)
    inv = inventory_nba_orderbook(cfg)
    joined = " ".join(inv["inspected_paths"])
    assert "/mlb/" not in joined.lower()
    assert "KXMLB" not in joined


@pytest.mark.skipif(not LIVE_STUB.is_file(), reason="NBA orderbook stub absent")
def test_live_nba_orderbook_is_unavailable():
    cfg = RollerConfig(ROLLER_ROOT)
    inv = inventory_nba_orderbook(cfg)
    assert inv["availability"] == AVAILABILITY_UNAVAILABLE
    assert inv["snapshot_rows"] == 0
    assert inv["inventory"]["canonical_stub_rows"] == 0
    assert inv["inventory"]["raw_orderbook_files"] == 0
    assert inv["inventory"]["suite_raw_has_orderbook"] is False
    assert inv["inventory"]["orderbook_depth_available"] is False
    payload = declare_nba_orderbook_capability(cfg)
    assert payload["snapshot_rows"] == 0
    assert payload["market_data_basis"] == MARKET_DATA_BASIS
    assert nba_orderbook_parquet_files(cfg) == []
    disk = json.loads(orderbook_capability_path(cfg).read_text(encoding="utf-8"))
    assert disk["availability"] == AVAILABILITY_UNAVAILABLE
    assert disk["parquet_emitted"] is False
