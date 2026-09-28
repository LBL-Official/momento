"""Phase 4 NBA MarketObservation projection. No interpolation. No last-trade as bid."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.warehouse.entities import ObservationBasis
from roller.warehouse.observations import (
    LAST_TRADE_COLS,
    assert_no_last_trade_columns,
    project_observation_frame,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_OCT = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "canonical" / "kalshi_candles" / "month=2025-10.csv"
LIVE_XWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def _crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "KX-A",
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "link_status": "LINKED",
            },
            {
                "ticker": "KX-UNLINKED",
                "internal_game_id": "",
                "link_status": "UNLINKED",
            },
        ]
    )


def _candle(**kwargs) -> dict:
    row = {
        "internal_game_id": "NBA_20251010_BOS_TOR",
        "ticker": "KX-A",
        "available_at": "2025-10-10T08:18:00Z",
        "event_timestamp": "2025-10-10T08:18:00Z",
        "candle_timestamp": "2025-10-10T08:18:00Z",
        "ingested_at": "2026-09-12T07:34:18Z",
        "yes_bid_open": "4600",
        "yes_bid_high": "4600",
        "yes_bid_low": "4600",
        "yes_bid_close": "4600",
        "yes_ask_open": "4900",
        "yes_ask_high": "4900",
        "yes_ask_low": "4900",
        "yes_ask_close": "4900",
        "volume": "0",
        "source_dataset": "warehouse_candles_1m",
    }
    row.update(kwargs)
    return row


def test_source_row_preserved_and_linked_via_crosswalk():
    out = project_observation_frame(pd.DataFrame([_candle()]), _crosswalk())
    assert len(out) == 1
    assert out.loc[0, "internal_game_id"] == "NBA_20251010_BOS_TOR"
    assert out.loc[0, "game_link_status"] == "LINKED"
    assert out.loc[0, "basis"] == ObservationBasis.TRADABLE_YES_BID.value
    assert out.loc[0, "yes_bid_close"] == "4600"
    assert out.loc[0, "available_at"] == "2025-10-10T08:18:00Z"


def test_duplicate_key_detected_not_deduped_on_price():
    rows = [
        _candle(),
        _candle(yes_bid_close="4700"),
    ]
    out = project_observation_frame(pd.DataFrame(rows), _crosswalk())
    assert len(out) == 2
    assert (out["duplicate_key"] == "1").all()


def test_missing_minute_is_absent():
    out = project_observation_frame(pd.DataFrame([_candle()]), _crosswalk())
    assert "2025-10-10T08:19:00Z" not in set(out["available_at"])
    assert len(out) == 1


def test_unlinked_and_conflict_do_not_guess_game():
    unlinked = project_observation_frame(
        pd.DataFrame([_candle(ticker="KX-UNLINKED", internal_game_id="NBA_20251010_BOS_TOR")]),
        _crosswalk(),
    )
    assert unlinked.loc[0, "game_link_status"] == "UNLINKED"
    assert unlinked.loc[0, "internal_game_id"] == ""
    conflict = project_observation_frame(
        pd.DataFrame([_candle(internal_game_id="NBA_20251011_NYK_BKN")]),
        _crosswalk(),
    )
    assert conflict.loc[0, "game_link_status"] == "CONFLICT"
    assert conflict.loc[0, "internal_game_id"] == ""


def test_unknown_market_is_unlinked():
    out = project_observation_frame(
        pd.DataFrame([_candle(ticker="KX-UNKNOWN", internal_game_id="NBA_20251010_BOS_TOR")]),
        _crosswalk(),
    )
    assert out.loc[0, "game_link_status"] == "UNLINKED"
    assert out.loc[0, "internal_game_id"] == ""


def test_last_trade_columns_are_rejected():
    with pytest.raises(ValueError, match="last-trade"):
        assert_no_last_trade_columns([*LAST_TRADE_COLS], path=Path("x.csv"))
    with pytest.raises(ValueError, match="last-trade"):
        project_observation_frame(
            pd.DataFrame([{**_candle(), "last_close_e4": "4600"}]),
            _crosswalk(),
        )


def test_missing_yes_bid_close_is_counted_not_filled():
    out = project_observation_frame(pd.DataFrame([_candle(yes_bid_close="")]), _crosswalk())
    assert out.loc[0, "yes_bid_close"] == ""
    assert len(out) == 1


def test_malformed_timestamp_is_preserved():
    out = project_observation_frame(pd.DataFrame([_candle(available_at="not-a-time")]), _crosswalk())
    assert out.loc[0, "available_at"] == "not-a-time"


@pytest.mark.skipif(not LIVE_OCT.is_file(), reason="NBA October candles absent")
@pytest.mark.skipif(not LIVE_XWALK.is_file(), reason="Phase 3 crosswalk absent")
def test_live_october_candles_preserve_yes_bid():
    cfg = RollerConfig(ROLLER_ROOT)
    from roller.warehouse.market_link import load_nba_crosswalk
    from roller.io_csv import read_csv

    raw = read_csv(LIVE_OCT)
    assert "last_close_e4" not in raw.columns
    out = project_observation_frame(raw, load_nba_crosswalk(cfg), path=LIVE_OCT)
    assert len(out) == len(raw)
    assert (out["basis"] == ObservationBasis.TRADABLE_YES_BID.value).all()
    assert (out["game_link_status"] == "LINKED").all()
    assert int((out["duplicate_key"] == "1").sum()) == 0
    assert out["yes_bid_close"].astype(str).str.strip().ne("").all()
