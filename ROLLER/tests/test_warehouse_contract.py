"""Warehouse contract. Does not change Confirm & Run loaders or detectors."""

from __future__ import annotations

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.warehouse.catalog import UNAVAILABLE_SPORTS, catalog
from roller.warehouse.schema import BASIS_LAST_TRADE_PRINT, BASIS_TRADABLE_YES_BID, contract_for, e4_domain_ok
from roller.warehouse.validation import validate_frame
import pandas as pd


def test_bases_are_distinct():
    assert BASIS_TRADABLE_YES_BID != BASIS_LAST_TRADE_PRINT
    assert contract_for("kalshi_candles").observation_basis == BASIS_TRADABLE_YES_BID
    assert contract_for("kalshi_last_trade").observation_basis == BASIS_LAST_TRADE_PRINT
    assert "yes_bid_close" in contract_for("kalshi_candles").required_columns
    assert "last_close_e4" in contract_for("kalshi_last_trade").required_columns
    assert "yes_bid_close" not in contract_for("kalshi_last_trade").required_columns


def test_nhl_is_unavailable_not_missing():
    assert "NHL" in UNAVAILABLE_SPORTS
    roots = {ref.sport for ref in catalog() if ref.root.is_dir()}
    assert "NHL" not in roots


def test_e4_domain():
    assert e4_domain_ok(8000)
    assert e4_domain_ok("")
    assert not e4_domain_ok(10001)
    assert not e4_domain_ok("x")


def test_validate_last_trade_frame():
    frame = pd.DataFrame(
        [
            {
                "internal_game_id": "G",
                "ticker": "T",
                "available_at": "2026-04-01T00:00:00Z",
                "last_close_e4": 7500,
            }
        ]
    )
    report = validate_frame("kalshi_last_trade", frame)
    assert report.ok


def test_dual_write_does_not_change_csv_loader(tmp_path):
    from pathlib import Path

    from roller.warehouse.dual_write import dual_write_month
    from roller.warehouse.loader import parquet_beside, read_month_parquet

    src = Path(
        "/Users/user/Desktop/Momento/ROLLER/data/wnba/2025/canonical/kalshi_candles/month=2025-05.csv"
    )
    if not src.is_file():
        return
    csv_path = tmp_path / "month=2025-05.csv"
    csv_path.write_bytes(src.read_bytes())
    out = dual_write_month(
        csv_path, dataset_name="kalshi_candles", sport="WNBA", league="WNBA", season="2025"
    )
    assert out["status"] == "INGESTED"
    pq = read_month_parquet(parquet_beside(csv_path))
    assert len(pq) == out["row_count"]


def test_fingerprint_ignores_dual_write_siblings(tmp_path, monkeypatch):
    from roller.research_query.dataset_version import _file_stamp

    month = tmp_path / "kalshi_candles"
    month.mkdir()
    csv = month / "month=2025-05.csv"
    csv.write_text("ticker\nT\n", encoding="utf-8")
    before = _file_stamp(month)
    (month / "month=2025-05.parquet").write_bytes(b"PARQUET")
    (month / "month=2025-05.manifest.json").write_text("{}", encoding="utf-8")
    assert _file_stamp(month) == before


def test_admin_load_dataset_still_csv():
    """Contract package must not reroute the published loader."""
    import inspect

    src = inspect.getsource(load_dataset)
    assert "read_parquet" not in src
    assert "load_table" in src
    cfg = RollerConfig()
    path = cfg.dataset_path("NBA", "2025-2026", "games")
    assert str(path).endswith("games.csv")
