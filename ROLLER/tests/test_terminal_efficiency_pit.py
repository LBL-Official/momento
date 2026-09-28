"""Base TE PIT / leakage gate. Does not edit research_query or FIRST80."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.base_terminal_efficiency.builder import build_observation, observations_for_ticker
from roller.base_terminal_efficiency.market import market_path_metrics
from roller.base_terminal_efficiency.pit import filter_visible, is_visible
from roller.research_query.entry_engine import tradable_sequence

UTC = timezone.utc


def _candle(minute: int, bid: int, *, ticker="T-HOME", game="G1", side="home"):
    return {
        "available_at": f"2025-12-20T20:{minute:02d}:00Z",
        "candle_timestamp": f"2025-12-20T20:{minute:02d}:00Z",
        "event_timestamp": f"2025-12-20T20:{minute:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400,
        "volume": 10,
        "ticker": ticker,
        "internal_game_id": game,
        "team_side": side,
    }


def _pbp(minute: int, home: int, away: int, *, n: int, avail_minute: int | None = None):
    am = minute if avail_minute is None else avail_minute
    return {
        "internal_game_id": "G1",
        "event_number": n,
        "event_timestamp": f"2025-12-20T20:{minute:02d}:00Z",
        "available_at": f"2025-12-20T20:{am:02d}:00Z",
        "period": 1,
        "clock": "08:00",
        "home_score": home,
        "away_score": away,
    }


def test_equality_available_at_excluded():
    ts = datetime(2025, 12, 20, 20, 5, tzinfo=UTC)
    assert is_visible("2025-12-20T20:05:00Z", ts) is False
    assert is_visible("2025-12-20T20:06:00Z", ts) is False
    assert is_visible("2025-12-20T20:04:59Z", ts) is True


def test_future_pbp_and_score_cannot_enter_entry():
    candles = [_candle(i, 5000 + i * 100) for i in range(4)]
    pbp = [_pbp(0, 0, 0, n=1), _pbp(1, 10, 0, n=2), _pbp(2, 20, 0, n=3)]
    rows, _ = observations_for_ticker(candles, pbp, attach_terminal=False)
    assert rows
    entry = rows[-1]
    leaked = pbp + [_pbp(9, 99, 50, n=99)]
    rows2, _ = observations_for_ticker(candles, leaked, attach_terminal=False)
    assert rows2[-1].team_points == entry.team_points
    assert rows2[-1].score_path_team == entry.score_path_team
    assert rows2[-1].team_score_volatility == entry.team_score_volatility


def test_future_price_and_path_cannot_enter_entry():
    candles = [_candle(i, bid) for i, bid in enumerate([5000, 6000, 7000, 8000])]
    pbp = [_pbp(0, 2, 0, n=1), _pbp(1, 5, 0, n=2), _pbp(2, 8, 0, n=3)]
    bars, _ = tradable_sequence(candles)
    obs = build_observation(bars, pbp_events=pbp)
    assert obs is not None
    extra = candles + [_candle(20, 9900)]
    bars2, _ = tradable_sequence(extra)
    # Entry is still the 80 bar (index 3), not the future 99
    obs2 = build_observation(bars2[:4], pbp_events=pbp)
    assert obs2 is not None
    assert obs2.entry_price_e4 == 8000
    assert obs2.cumulative_price_travel_e4 == obs.cumulative_price_travel_e4
    assert obs2.entry_price_volatility == obs.entry_price_volatility
    future_only = market_path_metrics([b.bid for b in bars2])
    assert future_only["cumulative_price_travel_e4"] != obs.cumulative_price_travel_e4


def test_future_available_at_same_event_time_excluded():
    """event_timestamp < t but available_at >= t must not leak."""
    ts = "2025-12-20T20:05:00Z"
    rows = [
        {"available_at": "2025-12-20T20:04:00Z", "event_timestamp": "2025-12-20T20:03:00Z", "home_score": 10, "away_score": 0},
        {"available_at": "2025-12-20T20:05:00Z", "event_timestamp": "2025-12-20T20:03:00Z", "home_score": 40, "away_score": 0},
        {"available_at": "2025-12-20T20:06:00Z", "event_timestamp": "2025-12-20T20:04:00Z", "home_score": 80, "away_score": 0},
    ]
    vis = filter_visible(rows, ts)
    assert len(vis) == 1
    assert vis[0]["home_score"] == 10


def test_terminal_does_not_change_entry_fields():
    candles = [_candle(i, 5000 + i * 100) for i in range(3)]
    pbp = [_pbp(0, 3, 1, n=1), _pbp(1, 6, 1, n=2)]
    a, _ = observations_for_ticker(candles, pbp, market=None, attach_terminal=True)
    b, _ = observations_for_ticker(candles, pbp, market={"result": "yes"}, attach_terminal=True)
    assert a[-1].entry_price_e4 == b[-1].entry_price_e4
    assert a[-1].team_points == b[-1].team_points
    assert a[-1].score_path_team == b[-1].score_path_team
    assert a[-1].terminal_outcome == "MISSING"
    assert b[-1].terminal_outcome == "YES"
