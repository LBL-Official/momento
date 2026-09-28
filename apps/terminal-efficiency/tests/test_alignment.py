from datetime import datetime, timezone

import pandas as pd

from terminal_efficiency.clocks import to_iso
from terminal_efficiency.state.candle_alignment import align_states_to_candles


def test_alignment_never_uses_future_event():
    t0 = datetime(2024, 11, 1, 1, 0, tzinfo=timezone.utc)
    t1 = datetime(2024, 11, 1, 1, 2, tzinfo=timezone.utc)
    obs = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "game_event_timestamp": to_iso(t0),
                "home_score": 10,
                "timestamp_quality": "OBSERVED",
            },
            {
                "game_id": "g1",
                "game_event_timestamp": to_iso(t1),
                "home_score": 12,
                "timestamp_quality": "OBSERVED",
            },
        ]
    )
    candle_end = datetime(2024, 11, 1, 1, 1, tzinfo=timezone.utc)
    candles = pd.DataFrame(
        [
            {
                "ticker": "T",
                "market_timestamp": to_iso(candle_end),
                "yes_bid_close": "0.55",
            }
        ]
    )
    aligned, cov = align_states_to_candles(obs, candles, game_id_from_ticker=lambda t: "g1")
    assert cov["aligned"] == 1
    assert int(aligned.iloc[0]["home_score"]) == 10


def test_empty_candles_is_gap_not_synthetic():
    obs = pd.DataFrame(
        [{"game_id": "g1", "game_event_timestamp": "2024-11-01T01:00:00Z", "home_score": 1, "timestamp_quality": "OBSERVED"}]
    )
    aligned, cov = align_states_to_candles(obs, pd.DataFrame(), game_id_from_ticker=lambda t: "g1")
    assert aligned.empty
    assert cov["status"] == "DATA_GAP"
    assert "data_gap" in cov
