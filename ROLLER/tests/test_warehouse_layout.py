"""Phase 8 physical layout. Lossless. 1-minute candles only. No L2 partition."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.admin import load_dataset
import inspect

from roller.warehouse.layout import (
    OBSERVATION_BASIS_DIR,
    OBS_FINGERPRINT_COLS,
    assert_layout_contract,
    fingerprint_frame,
    manifest_path,
    observations_dir,
    project_games,
    warehouse_root,
    write_nba_warehouse,
    write_sorted_parquet,
)
from roller.warehouse.layout_v0 import observations_dir as v0_obs
from roller.warehouse.partitioning import month_parquet

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_WAREHOUSE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse" / "manifest.json"


def test_fingerprint_ignores_row_order_and_keeps_available_at():
    a = pd.DataFrame(
        [
            {"ticker": "KX-B", "available_at": "2025-10-10T08:19:00Z", "yes_bid_close": "4700"},
            {"ticker": "KX-A", "available_at": "2025-10-10T08:18:00Z", "yes_bid_close": "4600"},
        ]
    )
    b = a.iloc[::-1].reset_index(drop=True)
    cols = ["ticker", "available_at", "yes_bid_close"]
    fa, na = fingerprint_frame(a, cols)
    fb, nb = fingerprint_frame(b, cols)
    assert fa == fb
    assert na == nb == 2
    drifted = a.copy()
    drifted.loc[0, "available_at"] = "2025-10-10T08:18:00Z"
    fd, _ = fingerprint_frame(drifted, cols)
    assert fd != fa


def test_observation_path_keeps_explicit_basis(tmp_path: Path):
    root = tmp_path / "warehouse"
    (root / "observations" / OBSERVATION_BASIS_DIR).mkdir(parents=True)
    assert_layout_contract(root)
    (root / "observations" / "basis=orderbook_snapshot").mkdir()
    with pytest.raises(ValueError, match="orderbook"):
        assert_layout_contract(root)


def test_no_orderbook_parquet_partition(tmp_path: Path):
    root = tmp_path / "warehouse"
    (root / "observations" / OBSERVATION_BASIS_DIR).mkdir(parents=True)
    (root / "orderbook").mkdir()
    (root / "orderbook" / "snapshots.parquet").write_bytes(b"PAR1")
    with pytest.raises(ValueError, match="orderbook parquet"):
        assert_layout_contract(root)


def test_sorted_write_preserves_available_at(tmp_path: Path):
    frame = pd.DataFrame(
        [
            {
                "internal_game_id": "NBA_B",
                "market_id": "KX-B",
                "available_at": "2025-10-11T00:00:00Z",
                "yes_bid_close": "1",
            },
            {
                "internal_game_id": "NBA_A",
                "market_id": "KX-A",
                "available_at": "2025-10-10T00:00:00Z",
                "yes_bid_close": "2",
            },
        ]
    )
    path = tmp_path / "obs.parquet"
    write_sorted_parquet(frame, path, sort_cols=["internal_game_id", "market_id", "available_at"])
    out = pd.read_parquet(path)
    assert list(out["available_at"]) == ["2025-10-10T00:00:00Z", "2025-10-11T00:00:00Z"]
    assert set(out["available_at"]) == set(frame["available_at"])


def test_games_projection_does_not_copy_home_win():
    identity = pd.DataFrame(
        [
            {
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "sport": "NBA",
                "season": "2025-2026",
                "game_date": "2025-10-10",
                "home_team_id": "TOR",
                "away_team_id": "BOS",
                "home_team_name": "Raptors",
                "away_team_name": "Celtics",
                "source_game_id": "001",
                "warehouse_game_id": "w1",
                "event_ticker": "EV",
                "mapping_status": "MAPPED",
                "home_win": "1",
            }
        ]
    )
    games = project_games(identity)
    assert "home_win" not in games.columns
    assert games.loc[0, "internal_game_id"] == "NBA_20251010_BOS_TOR"
    assert games.loc[0, "league"] == "NBA"


def test_load_dataset_still_csv_after_layout():
    src = inspect.getsource(load_dataset)
    assert "read_parquet" not in src
    assert "warehouse_root" not in src or "derived/warehouse" not in src


def test_execute_does_not_import_layout():
    root = Path(__file__).resolve().parents[1] / "roller"
    tree = ast.parse((root / "research_query" / "execute.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.warehouse.layout" not in imported
    assert "roller.warehouse.layout_benchmark" not in imported


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="Phase 8 warehouse not written yet")
def test_live_selected_warehouse_contract():
    cfg = RollerConfig(ROLLER_ROOT)
    root = warehouse_root(cfg)
    assert_layout_contract(root)
    man = __import__("json").loads(manifest_path(cfg).read_text(encoding="utf-8"))
    assert man["observation_basis"] == "TRADABLE_YES_BID"
    assert man["observation_resolution"] == "1_MINUTE_CANDLE"
    assert man["tick_data_available"] is False
    assert man["orderbook_data_available"] is False
    assert man["candle_pit_available"] is True
    assert man["candle_pit_field"] == "available_at"
    assert man["pbp_pit_aligned_to_candles"] is False
    assert man["available_at_preserved"] is True
    assert not (root / "orderbook").exists() or not list((root / "orderbook").glob("*.parquet"))
    assert observations_dir(cfg).name == OBSERVATION_BASIS_DIR
    oct_v0 = month_parquet(v0_obs(cfg), "2025-10")
    oct_wh = month_parquet(observations_dir(cfg), "2025-10")
    if oct_v0.is_file() and oct_wh.is_file():
        a = pd.read_parquet(oct_v0, columns=OBS_FINGERPRINT_COLS)
        b = pd.read_parquet(oct_wh, columns=OBS_FINGERPRINT_COLS)
        fa, na = fingerprint_frame(a, OBS_FINGERPRINT_COLS)
        fb, nb = fingerprint_frame(b, OBS_FINGERPRINT_COLS)
        assert fa == fb
        assert na == nb
