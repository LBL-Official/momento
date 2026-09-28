"""Base TE WIN/LOSS. Exact-timestamp AMBIGUOUS. Does not modify _classify_exits."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.base_terminal_efficiency.exits import classify_first_exit
from roller.base_terminal_efficiency.models import (
    AMBIGUOUS,
    DATA_REQUIRED,
    INVALID_SEMANTICS,
    LOSS,
    TIE_EXACT_TIMESTAMP,
    WIN,
)
from roller.research_query.entry_engine import TradableBar
from roller.research_query.models import PathCondition, PathOp

UTC = timezone.utc


def _tb(minute: int, bid: int, *, ticker="T-A", game="G1", second: int = 0) -> TradableBar:
    ts = datetime(2025, 12, 20, 20, minute, second, tzinfo=UTC)
    return TradableBar(ts=ts, bid=bid, ask=bid + 400, volume=10, ticker=ticker, game_id=game, raw={})


def test_win_90_after_80():
    entry = _tb(0, 8000)
    after = [_tb(1, 8500), _tb(2, 9000)]
    out = classify_first_exit(entry, after, win_price_e4=9000, loss_price_e4=4000)
    assert out["exit_outcome"] == WIN
    assert out["exit_price_e4"] == 9000


def test_loss_40_after_80():
    entry = _tb(0, 8000)
    after = [_tb(1, 6000), _tb(2, 4000)]
    out = classify_first_exit(entry, after, win_price_e4=9000, loss_price_e4=4000)
    assert out["exit_outcome"] == LOSS
    assert out["exit_price_e4"] == 4000


def test_later_win_does_not_override_earlier_loss():
    entry = _tb(0, 8000)
    after = [_tb(1, 4000), _tb(2, 9000)]
    out = classify_first_exit(entry, after, win_price_e4=9000, loss_price_e4=4000)
    assert out["exit_outcome"] == LOSS


def test_entry_bar_cannot_satisfy_win():
    entry = _tb(0, 9000)
    after = [_tb(1, 8500), _tb(2, 8000)]
    out = classify_first_exit(entry, after + [entry], win_price_e4=9000, loss_price_e4=4000)
    assert out["exit_outcome"] is None


def test_exact_timestamp_tie_ambiguous():
    entry = _tb(0, 8000)
    t = datetime(2025, 12, 20, 20, 5, 0, tzinfo=UTC)
    loss_bar = TradableBar(ts=t, bid=4000, ask=4400, volume=10, ticker="T-A", game_id="G1", raw={})
    win_bar = TradableBar(ts=t, bid=9000, ask=9400, volume=10, ticker="T-A", game_id="G1", raw={})
    out = classify_first_exit(entry, [loss_bar, win_bar], win_price_e4=9000, loss_price_e4=4000)
    assert out["exit_outcome"] == AMBIGUOUS
    assert out["exclusion_reason"] == TIE_EXACT_TIMESTAMP


def test_invalid_win_below_entry():
    entry = _tb(0, 8000)
    out = classify_first_exit(entry, [_tb(1, 4000)], win_price_e4=4000)
    assert out["status"] == INVALID_SEMANTICS


def test_invalid_loss_above_entry():
    entry = _tb(0, 8000)
    out = classify_first_exit(entry, [_tb(1, 9000)], loss_price_e4=9000)
    assert out["status"] == INVALID_SEMANTICS


def test_game_clock_without_snap_is_data_required():
    entry = _tb(0, 8000)
    steps = [
        PathCondition(id="h", op=PathOp.HORIZON_WIN, price_e4=5000, horizon_kind="game", horizon_minutes=5)
    ]
    out = classify_first_exit(entry, [_tb(1, 9000)], win_steps=steps, snap_fn=None)
    assert out["status"] == DATA_REQUIRED
    assert out["exit_outcome"] is None
