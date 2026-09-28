"""NBA 001 portfolio rules. No orders. No VITAL_AWS_CONTROL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from roller.momento.nba_001_replay import (
    NY,
    THRESHOLD,
    choose_candidate,
    entry_contracts,
    half_away_fee_cents,
    hedge_reserve_cents,
    kalshi_fee_cents,
    occupies_slot,
    prepare_trade,
    protected_hashes,
    replay_portfolio,
    signal_order,
    week_grid,
    Mark,
)

UTC = ZoneInfo("UTC")


def _fee(count: int, price: int) -> int:
    return kalshi_fee_cents(count, price, role="maker", maker_multiplier=1)


def _mark(cents: int):
    def mark_at(_ticker: str, when: datetime) -> Mark:
        return Mark(cents, when, False)

    return mark_at


def _trade(**overrides):
    entry = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    row = {
        "game_id": "g1",
        "event_id": "KXNBAGAME-TEST",
        "ticker": "T1",
        "entry_ts": entry,
        "exit_ts": entry + timedelta(hours=2),
        "phase": "REGULAR_SEASON",
        "slice": "Q2",
        "entry_price_cents": 80,
        "exit_price_cents": None,
        "settle_yes": True,
        "exit_role": "settlement",
        "exit_basis": "CANDLE_SETTLEMENT",
        "fill_observed": False,
        "entry_role": "maker",
    }
    row.update(overrides)
    return row


def test_fee_ceils_model_then_cent():
    assert kalshi_fee_cents(1, 50, role="taker") == 2
    assert kalshi_fee_cents(1, 50, role="maker", maker_multiplier=1) == 1
    assert kalshi_fee_cents(1, 80, role="taker") == 2
    assert half_away_fee_cents(1, 50, role="taker") == 2


def test_sizing_reduces_for_fee_and_skips_one_contract():
    count = entry_contracts(2_000_000, 2_000_000, 80, _fee)
    assert count < 1000
    assert count * 80 + _fee(count, 80) <= 80_000
    assert entry_contracts(100, 100, 80, _fee) == 0


def test_five_slots_include_unknown_and_pending():
    base = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    trades = [
        _trade(game_id=f"g{index}", ticker=f"T{index}", entry_ts=base, exit_ts=base + timedelta(hours=3))
        for index in range(6)
    ]
    result = replay_portfolio(trades, mark_at=_mark(80))
    assert result["entries"] == 5
    assert result["skip_reasons"]["SLOT_FULL"] == 1
    blocked = replay_portfolio(trades[:1], mark_at=_mark(80), seed_occupants=["unknown", "pending", "partial", "working", "open"])
    assert blocked["entries"] == 0
    assert blocked["skip_reasons"]["SLOT_FULL"] == 1
    assert occupies_slot("unknown")
    assert not occupies_slot("terminal")


def test_game_id_tie_break_and_no_reentry():
    stamp = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    ordered = signal_order([
        {"entry_ts": stamp, "game_id": "b"},
        {"entry_ts": stamp, "game_id": "a"},
    ])
    assert [row["game_id"] for row in ordered] == ["a", "b"]
    trades = [
        _trade(game_id="b", ticker="TB"),
        _trade(game_id="a", ticker="TA"),
    ]
    result = replay_portfolio(trades, mark_at=_mark(80), max_slots=1)
    entered = [row for row in result["skips"] if row["reason"] == "SLOT_FULL"]
    assert entered[0]["game_id"] == "b"
    again = replay_portfolio(
        [_trade(game_id="same", exit_ts=stamp + timedelta(minutes=5)), _trade(game_id="same", entry_ts=stamp + timedelta(hours=1), exit_ts=stamp + timedelta(hours=2))],
        mark_at=_mark(80),
    )
    assert again["entries"] == 1
    assert again["skip_reasons"]["REENTRY"] == 1


def test_hedge_reserve_does_not_raise_favorite_cap_and_hedge_cannot_win():
    reserve = hedge_reserve_cents(10, lambda count, price: kalshi_fee_cents(count, price, role="maker"))
    assert reserve == 10 * 40 + kalshi_fee_cents(10, 40, role="maker")
    assert reserve > 10 * 40
    decision = choose_candidate(
        {"union": Decimal("0.001"), "q2": Decimal("0.001"), "q3": Decimal("0.000"), "hedge": Decimal("0.99")},
        fill_executable=False,
    )
    assert decision["candidate"] == "union"
    assert decision["status"] == "PROVISIONAL"
    assert decision["hedge_eligible"] is False
    selected = choose_candidate({"union": THRESHOLD, "q2": None, "q3": None}, fill_executable=True)
    assert selected["status"] == "SELECTED_FOR_PAPER_TEST"
    paper_blocked = choose_candidate({"union": THRESHOLD}, fill_executable=False)
    assert paper_blocked["status"] == "PROVISIONAL"


def test_spanning_position_marks_each_week_and_zero_weeks_enter_the_mean():
    entry = datetime(2026, 1, 4, 23, 0, tzinfo=NY)
    exit_at = datetime(2026, 1, 6, 1, 0, tzinfo=NY)
    weeks = week_grid(entry, exit_at)

    def mark_at(_ticker: str, when: datetime) -> Mark:
        monday = datetime(2026, 1, 5, 0, 0, tzinfo=NY)
        cents = 70 if when <= monday else 80
        return Mark(cents, when, False)

    result = replay_portfolio(
        [_trade(entry_ts=entry, exit_ts=exit_at, entry_price_cents=80)],
        mark_at=mark_at,
        week_starts=weeks,
    )
    assert all(item is not None for item in result["weekly_returns"])
    assert result["fill_observed"] is False
    assert result["basis"] == "CANDLE_PATH_NOT_A_FILL"
    quiet_entry = datetime(2026, 1, 6, 18, 0, tzinfo=UTC)
    quiet_weeks = [
        datetime(2025, 12, 29, tzinfo=NY),
        datetime(2026, 1, 5, tzinfo=NY),
        datetime(2026, 1, 12, tzinfo=NY),
    ]
    quiet = replay_portfolio(
        [_trade(entry_ts=quiet_entry, exit_ts=quiet_entry + timedelta(hours=1))],
        mark_at=_mark(80),
        week_starts=quiet_weeks,
    )
    returns = [Decimal(item) for item in quiet["weekly_returns"]]
    assert returns[0] == 0
    assert returns[2] == 0
    assert sum(returns, Decimal(0)) / 3 != returns[1]


def test_missing_mark_is_not_zero_and_blocks_entry():
    stamp = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    trades = [
        _trade(game_id="open", ticker="TO", exit_ts=stamp + timedelta(hours=4)),
        _trade(game_id="next", ticker="TN", entry_ts=stamp + timedelta(hours=1), exit_ts=stamp + timedelta(hours=2)),
    ]
    result = replay_portfolio(trades, mark_at=None)
    assert result["entries"] == 1
    assert result["skip_reasons"]["MARK_UNAVAILABLE"] == 1
    assert result["ending_cash_cents"] != 0

    def stale(_ticker: str, when: datetime) -> Mark:
        return Mark(80, when - timedelta(seconds=181), True)

    stale_result = replay_portfolio(trades, mark_at=stale)
    assert stale_result["skip_reasons"]["STALE_MARK"] == 1


def test_conservative_maker_above_80_is_infeasible_and_not_a_fill():
    row = prepare_trade(
        {
            "game_id": "g",
            "event_id": "E",
            "ticker": "T",
            "timestamp_utc": "2026-01-05T18:00:00+00:00",
            "exit_timestamp_utc": "2026-01-05T19:00:00+00:00",
            "entry_bid_cents": 81,
            "t40": False,
            "terminal_yes": True,
            "post_entry_min": 70,
            "season_phase": "REGULAR_SEASON",
            "slice": "Q2",
        },
        layer="conservative",
    )
    assert row["skip"] == "INFEASIBLE_MAKER"
    assert row["fill_observed"] is False


def test_protected_hashes_match_manifest():
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "research"
        / "vital"
        / "bots"
        / "nba-001"
        / "analysis"
        / "SOURCE_MANIFEST.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert protected_hashes() == manifest["protected_sha256"]
    assert manifest["confirmation_outcomes_accessed"] is False
