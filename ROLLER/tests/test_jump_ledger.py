"""Bot One MLB ledger PNL. Mirrors crates/pnl. No invented EV."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from roller.jump.dashboard.heartbeat import parse_heartbeat_payload
from roller.jump.dashboard.ledger import (
    pacific_week_start,
    realized_from_position,
    summarize_mlb_ledger,
)

PT = ZoneInfo("America/Los_Angeles")


def _money(cents: int) -> dict:
    return {"cents": cents}


def _fill(*, premium: int, fee: int, kind: str, ts: str, qty: int = 3, raw: int = 1) -> dict:
    return {
        "fill_id": raw,
        "position_id": 1,
        "client_order_id": raw,
        "venue_order_id": None,
        "quantity": {"qty": qty},
        "price": {"cents": 80},
        "premium": _money(premium),
        "fee": {"amount": _money(fee), "kind": kind},
        "exchange_ts": ts,
        "received_at": ts,
    }


def _position(*, strategy_id: int, lifecycle: str, filled: int, fills: list, settlement=None) -> dict:
    return {
        "id": 1,
        "game_id": 10,
        "strategy_id": strategy_id,
        "snapshot_id": 7,
        "approved_economic_budget": _money(625),
        "filled_quantity": {"qty": filled},
        "fill_history": fills,
        "lifecycle": lifecycle,
        "settlement_proceeds": None if settlement is None else _money(settlement),
    }


def test_settlement_matches_crate_ledger():
    pos = _position(
        strategy_id=1,
        lifecycle="Settled",
        filled=3,
        fills=[_fill(premium=240, fee=5, kind="Entry", ts="2026-08-24T18:00:00Z")],
        settlement=300,
    )
    assert realized_from_position(pos) == 55


def test_open_position_has_no_realized():
    pos = _position(
        strategy_id=1,
        lifecycle="Holding",
        filled=3,
        fills=[_fill(premium=240, fee=5, kind="Entry", ts="2026-08-24T18:00:00Z")],
    )
    assert realized_from_position(pos) is None


def test_flat_liquidation_realizes_without_settlement():
    pos = _position(
        strategy_id=1,
        lifecycle="Flat",
        filled=0,
        fills=[
            _fill(premium=567, fee=0, kind="Entry", ts="2026-08-26T01:37:22Z", qty=7, raw=1),
            _fill(premium=441, fee=0, kind="Liquidation", ts="2026-08-26T01:41:15Z", qty=7, raw=2),
        ],
    )
    assert realized_from_position(pos) == -126


def test_wnba_excluded_from_mlb_day_week():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    runtime = {
        "tracker": {
            "positions": [
                _position(
                    strategy_id=2,
                    lifecycle="Settled",
                    filled=5,
                    fills=[_fill(premium=405, fee=0, kind="Entry", ts="2026-08-26T00:07:10Z")],
                    settlement=100,
                )
            ]
        }
    }
    summary = summarize_mlb_ledger(runtime, None, now)
    assert summary["ok"] is True
    assert summary["fields"]["day_pnl_cents"] == 0
    assert summary["fields"]["week_pnl_cents"] == 0
    assert summary["fields"]["open_mlb_positions"] == 0


def test_day_and_week_windows():
    now = datetime(2026, 8, 26, 9, 0, tzinfo=PT).astimezone(timezone.utc)
    snapshot = {
        "bankroll": _money(5000),
        "week_start_utc": "2026-08-24T11:00:00Z",
    }
    today = _position(
        strategy_id=1,
        lifecycle="Settled",
        filled=3,
        fills=[_fill(premium=240, fee=5, kind="Entry", ts="2026-08-26T16:00:00Z")],
        settlement=300,
    )
    prior_day_same_week = _position(
        strategy_id=1,
        lifecycle="Flat",
        filled=0,
        fills=[
            _fill(premium=567, fee=0, kind="Entry", ts="2026-08-25T01:37:22Z", qty=7, raw=1),
            _fill(premium=441, fee=0, kind="Liquidation", ts="2026-08-25T01:41:15Z", qty=7, raw=2),
        ],
    )
    prior_week = _position(
        strategy_id=1,
        lifecycle="Settled",
        filled=3,
        fills=[_fill(premium=240, fee=0, kind="Entry", ts="2026-08-23T20:00:00Z")],
        settlement=0,
    )
    runtime = {"tracker": {"positions": [today, prior_day_same_week, prior_week]}}
    summary = summarize_mlb_ledger(runtime, snapshot, now)
    assert summary["ok"] is True
    assert summary["fields"]["day_pnl_cents"] == 55
    assert summary["fields"]["week_pnl_cents"] == 55 + -126
    assert summary["fields"]["bankroll_cents"] == 5000


def test_pacific_week_start_matches_engine():
    monday_utc_midnight = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)
    start = pacific_week_start(monday_utc_midnight)
    assert start.day == 17
    assert start.hour == 4
    mon_4 = datetime(2026, 8, 24, 4, 0, tzinfo=PT)
    start = pacific_week_start(mon_4.astimezone(timezone.utc))
    assert (start.year, start.month, start.day, start.hour) == (2026, 8, 24, 4)


def test_missing_timestamp_on_realized_fails_closed():
    pos = _position(
        strategy_id=1,
        lifecycle="Settled",
        filled=3,
        fills=[{"premium": _money(240), "fee": {"amount": _money(0), "kind": "Entry"}}],
        settlement=0,
    )
    summary = summarize_mlb_ledger({"tracker": {"positions": [pos]}}, None, datetime.now(timezone.utc))
    assert summary["ok"] is False


def test_probe_ev_keys_are_ignored():
    parsed = parse_heartbeat_payload({"day_ev_cents": 999, "week_ev_cents": 100, "bankroll_cents": 5000})
    assert parsed["fields"]["bankroll_cents"] == 5000
    assert "day_ev_cents" not in parsed["fields"]
    assert "week_ev_cents" not in parsed["fields"]
