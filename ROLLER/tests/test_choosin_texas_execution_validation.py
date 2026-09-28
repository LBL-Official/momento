"""Execution validation stays off the candle P&L and cannot submit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.choosin_texas.api import handle_execution_validation, handle_health
from roller.choosin_texas.execution_validation.build import (
    SUBMISSION_ACTIONS,
    accept_read_only,
    diagnose_position,
    load_summary,
    verify_baseline,
)
from roller.choosin_texas.execution_validation.classify import classify_buy_limit, classify_sell_limit
from roller.choosin_texas.execution_validation.fees import fee_for_role, historical_fee_status
from roller.choosin_texas.execution_validation.simulator import (
    ExecutionBook,
    attribute_versus_benchmark,
    evaluate_observation,
)
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.sources import repo_root

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "ROLLER" / "roller" / "choosin_texas" / "execution_validation"
FRONTEND = ROOT / "frontend" / "choosin-texas" / "src" / "ExecutionValidation.tsx"


def test_no_order_before_the_signal_is_observable():
    with pytest.raises(ChoosinTexasError, match="before the signal"):
        evaluate_observation(
            signal_ts=100,
            arrival_ts=99,
            post_only=True,
            crosses=False,
            queue_position=None,
            depth_contracts=1,
            sequence_gap=False,
            trade_at_price=False,
        )


def test_marketable_post_only_is_not_a_resting_maker_fill():
    observed = evaluate_observation(
        signal_ts=100,
        arrival_ts=100,
        post_only=True,
        crosses=True,
        queue_position=0,
        depth_contracts=10,
        sequence_gap=False,
        trade_at_price=True,
    )
    assert observed["status"] == "POST_ONLY_REJECTED"
    assert observed["role"] == "POST_ONLY_REJECT"
    assert observed["fill_label"] is None
    quote = classify_buy_limit(
        limit_cents=80,
        bid_cents=80,
        ask_cents=80,
        depth_available=True,
        sequence_known=True,
        queue_position=0,
    )
    assert quote["quote_relation"] == "MARKETABLE_AT_CANDLE_CLOSE"
    assert quote["modeled_filled_contracts"] is None
    standing_stop = classify_sell_limit(
        limit_cents=65,
        bid_cents=80,
        ask_cents=82,
        depth_available=False,
        sequence_known=False,
        queue_position=None,
        taker_fallback="NOT_AUTHORIZED",
    )
    assert standing_stop["quote_relation"] == "MARKETABLE_AT_CANDLE_CLOSE"
    assert standing_stop["modeled_filled_contracts"] is None


def test_quote_touch_and_missing_depth_stay_unresolved():
    touch = evaluate_observation(
        signal_ts=100,
        arrival_ts=100,
        post_only=True,
        crosses=False,
        queue_position=None,
        depth_contracts=5,
        sequence_gap=False,
        trade_at_price=False,
    )
    assert touch["status"] == "UNCERTAIN"
    assert touch["modeled_filled_contracts"] is None
    assert "quote touch" in touch["reason"]
    gap = evaluate_observation(
        signal_ts=100,
        arrival_ts=100,
        post_only=True,
        crosses=False,
        queue_position=0,
        depth_contracts=None,
        sequence_gap=True,
        trade_at_price=True,
    )
    assert gap["status"] == "UNCERTAIN"
    assert gap["modeled_filled_contracts"] is None


def test_partial_entry_reserves_remainder_and_counts_toward_the_cap():
    book = ExecutionBook(100_000, max_open_positions=3)
    assert book.reserve_entry(event_id="A", signal_ts=10, arrival_ts=10, contracts=100, limit_cents=80) == "RESERVED"
    book.apply_entry_fill("A", 40, ts=11)
    state = book.states["A"]
    assert state["reserved_contracts"] == 60
    assert state["filled_contracts"] == 40
    assert state["reserved_premium_cents"] == 4_800
    assert book.cash_cents == 92_000
    for name in ("B", "C"):
        assert book.reserve_entry(event_id=name, signal_ts=12, arrival_ts=12, contracts=10, limit_cents=80) == "RESERVED"
    assert book.reserve_entry(event_id="D", signal_ts=12, arrival_ts=12, contracts=10, limit_cents=80) == "POSITION_CAP"
    assert book.slots_open() == 3
    assert book.reconstruct_max_concurrent(horizon_ts=13) == 3


def test_partial_exit_does_not_free_the_slot_and_unfilled_exit_stays_exposed():
    book = ExecutionBook(100_000, max_open_positions=3)
    book.reserve_entry(event_id="A", signal_ts=10, arrival_ts=10, contracts=100, limit_cents=80)
    book.apply_entry_fill("A", 40, ts=11)
    book.stop_during_entry("A", ts=12)
    assert book.states["A"]["reserved_contracts"] == 0
    assert book.states["A"]["exit_open_contracts"] == 40
    assert book.cash_cents == 96_800
    book.apply_exit_fill("A", 10, price_cents=40, fee_cents=5, ts=13)
    assert book.states["A"]["slot_open"] is True
    assert book.states["A"]["filled_contracts"] - book.states["A"]["exit_filled_contracts"] == 30
    assert book.reserve_entry(event_id="B", signal_ts=14, arrival_ts=14, contracts=10, limit_cents=80) == "RESERVED"
    assert book.reserve_entry(event_id="C", signal_ts=14, arrival_ts=14, contracts=10, limit_cents=80) == "RESERVED"
    assert book.reserve_entry(event_id="D", signal_ts=14, arrival_ts=14, contracts=10, limit_cents=80) == "POSITION_CAP"
    book.reconcile(100_000)
    book.assert_reconciled()


def test_stop_during_partial_entry_cancels_the_remainder():
    book = ExecutionBook(8_000, max_open_positions=3)
    book.reserve_entry(event_id="A", signal_ts=10, arrival_ts=10, contracts=100, limit_cents=80)
    book.apply_entry_fill("A", 25, ts=11)
    book.stop_during_entry("A", ts=12)
    assert book.states["A"]["reserved_contracts"] == 0
    assert book.states["A"]["reserved_premium_cents"] == 0
    assert book.cash_cents == 6_000
    assert book.states["A"]["exit_open_contracts"] == 25
    assert book.states["A"]["slot_open"] is True
    book.reconcile(8_000)


def test_full_cancel_of_an_unfilled_entry_releases_the_slot():
    book = ExecutionBook(8_000, max_open_positions=1)
    book.reserve_entry(event_id="A", signal_ts=10, arrival_ts=10, contracts=100, limit_cents=80)
    book.stop_during_entry("A", ts=11)
    assert book.states["A"]["slot_open"] is False
    assert book.cash_cents == 8_000
    assert book.reserve_entry(event_id="B", signal_ts=12, arrival_ts=12, contracts=10, limit_cents=80) == "RESERVED"
    book.reconcile(8_000)


def test_maker_and_taker_fees_follow_the_modeled_role():
    schedule = {
        "series": ["KXNBAGAME"],
        "effective_from": "2026-09-03T00:00:00+00:00",
        "effective_through": "2026-09-03T23:59:59+00:00",
        "fee_type": "quadratic",
        "maker_fee_cents": 0,
        "provenance": "test-snapshot",
    }
    maker = fee_for_role(
        role="MAKER",
        filled_contracts=10,
        order_ts="2026-09-03T12:00:00+00:00",
        series="KXNBAGAME",
        schedule=schedule,
    )
    taker = fee_for_role(
        role="TAKER",
        filled_contracts=10,
        order_ts="2026-09-03T12:00:00+00:00",
        series="KXNBAGAME",
        schedule=schedule,
    )
    rejected = fee_for_role(
        role="POST_ONLY_REJECT",
        filled_contracts=0,
        order_ts="2026-09-03T12:00:00+00:00",
        series="KXNBAGAME",
        schedule=schedule,
    )
    resting = fee_for_role(
        role="RESTING_UNFILLED",
        filled_contracts=0,
        order_ts="2026-09-03T12:00:00+00:00",
        series="KXNBAGAME",
        schedule=schedule,
    )
    assert maker["status"] == "VERIFIED_ZERO"
    assert maker["fee_cents"] == 0
    assert taker["role"] == "TAKER"
    assert taker["status"] == "FEES_UNAVAILABLE"
    assert taker["fee_cents"] is None
    assert rejected["fee_cents"] == 0
    assert resting["fee_cents"] is None
    historical = historical_fee_status()
    assert historical["historical_book"] == "FEES_UNAVAILABLE"
    assert historical["snapshot"]["applies_to_historical_book"] is False


def test_existing_gap_is_not_charged_twice():
    unresolved = attribute_versus_benchmark(
        benchmark_pnl_cents=-42_000,
        benchmark_exit_cents=38,
        modeled_exit_cents=None,
    )
    assert unresolved["gap_recharged"] is False
    assert unresolved["execution_adjustment_cents"] is None
    assert unresolved["benchmark_pnl_cents"] == -42_000
    compared = attribute_versus_benchmark(
        benchmark_pnl_cents=-42_000,
        benchmark_exit_cents=38,
        modeled_exit_cents=30,
    )
    assert compared["gap_recharged"] is False
    assert compared["exit_difference_cents"] == -8
    assert compared["exit_difference_cents"] != 80 - 38


def test_reconstructed_occupancy_cannot_exceed_three():
    book = ExecutionBook(100_000, max_open_positions=3)
    for name in ("A", "B", "C", "D"):
        book.states[name] = {
            "slot_open": True,
            "slot_start": 10,
            "reserved_contracts": 1,
            "filled_contracts": 0,
            "exit_filled_contracts": 0,
            "exit_open_contracts": 0,
            "reserved_premium_cents": 80,
            "limit_cents": 80,
            "proceeds_cents": 0,
            "fees_cents": 0,
        }
    with pytest.raises(ChoosinTexasError, match="exceeds the cap"):
        book.reconstruct_max_concurrent(horizon_ts=20)


def test_order_before_signal_is_rejected_by_the_book():
    book = ExecutionBook(8_000)
    with pytest.raises(ChoosinTexasError, match="before the signal"):
        book.reserve_entry(event_id="A", signal_ts=10, arrival_ts=9, contracts=10, limit_cents=80)


def test_submission_is_not_reachable():
    source = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py"))
    for forbidden in ("def place_order", "def submit_order", "import socket", "import httpx"):
        assert forbidden not in source
    assert "method=\"POST\"" not in source
    assert "place_order(" not in source
    assert "place_order" in SUBMISSION_ACTIONS
    with pytest.raises(ChoosinTexasError, match="cannot submit"):
        accept_read_only({"action": "place_order"})
    page = FRONTEND.read_text(encoding="utf-8")
    assert "*" not in page
    assert "* 100" not in page


def test_frozen_baseline_and_historical_diagnostics_do_not_invent_fills():
    baseline = verify_baseline()
    assert baseline["unit_book_cents"] == {"80/40": 3297, "80/65": 2410}
    assert baseline["planned_risk_cap3"]["through_close_pnl_cents"]["80/40"] == 5_335_376
    assert baseline["planned_risk_cap3"]["through_close_pnl_cents"]["80/65"] == 8_119_467
    assert baseline["capital_6pct_cap3"]["through_close_pnl_cents"]["80/40"] == 11_164_842
    body = load_summary()
    assert body["execution_aware_portfolio_pnl"] == "NOT_REPORTED"
    assert body["comparison_status"] == "NOT_COMPARABLE"
    assert body["actual_fills"] == 0
    assert body["fees"]["historical_book"] == "FEES_UNAVAILABLE"
    assert body["coverage"]["order_book_depth_snapshots"] == "UNAVAILABLE"
    assert body["prospective_collector"]["submits"] is False
    assert body["prospective_collector"]["simulated_fills"] == "BLOCKED"
    assert body["observation_policy"]["hypothetical_order_intent"].startswith("After the qualifying")
    assert body["observation_policy"]["entry_rest"] == "POLICY_UNRESOLVED"
    assert body["observation_policy"]["exit_priority"] == "POLICY_UNRESOLVED"
    for book, accepted in (("80/40", 820), ("80/65", 865)):
        diag = body["books"][book]["diagnostics"]
        assert diag["events"] == accepted
        assert diag["unresolved_events"] == accepted
        assert diag["partial_fills_modeled"] == 0
        assert diag["depth_available_entry_rows"] == 0
        assert diag["missing_entry_candle"] == 0
        assert diag["missing_trade_file"] == 0
        assert "MARKETABLE_AT_CANDLE_CLOSE" not in diag["entry_quote_relations"]
    health = handle_health()
    assert "choosin_texas_execution_validation" in health["capabilities"]
    served = handle_execution_validation()
    assert served["configuration_id"] == "PLANNED_RISK_CAP3"
    assert served["books"]["80/40"]["benchmark_pnl_cents"] == 5_335_376


def test_prospective_collector_records_clocks_and_not_a_return(tmp_path: Path):
    from roller.choosin_texas.execution_validation.prospective import (
        accept_observation,
        collector_health,
    )

    stored = accept_observation(
        {
            "instrument": "KXNBAGAME-EXAMPLE",
            "signal": "ENTRY",
            "trigger": "CANDLE_CLOSE",
            "exchange_ts": "2026-10-03T00:00:00+00:00",
            "received_ts": "2026-10-03T00:00:01+00:00",
            "yes_bid_cents": 80,
            "yes_ask_cents": 83,
            "depth_contracts": None,
            "sequence": None,
        },
        dest=tmp_path,
    )
    assert stored["sent"] is False
    assert stored["record_kind"] == "HYPOTHETICAL_ORDER_INTENT"
    assert stored["intent_eligible"] is True
    assert stored["fill_label"] is None
    assert stored["modeled_filled_contracts"] is None
    assert stored["portfolio_pnl"] == "NOT_REPORTED"
    early = accept_observation(
        {
            "instrument": "KXNBAGAME-EARLY",
            "signal": "ENTRY",
            "trigger": "CANDLE_CLOSE",
            "exchange_ts": "2026-10-03T00:01:00+00:00",
            "received_ts": "2026-10-03T00:00:59+00:00",
            "yes_bid_cents": 80,
            "yes_ask_cents": 83,
        },
        dest=tmp_path,
    )
    assert early["sent"] is False
    assert early["intent_eligible"] is False
    with pytest.raises(ChoosinTexasError, match="different specification"):
        accept_observation(
            {
                "instrument": "KXNBAGAME-LIVE",
                "signal": "ENTRY",
                "trigger": "LIVE_QUOTE",
                "exchange_ts": "2026-10-03T00:02:00+00:00",
                "received_ts": "2026-10-03T00:02:00+00:00",
            },
            dest=tmp_path,
        )
    health = collector_health(tmp_path)
    assert health["status"] == "CONFIGURED"
    assert health["websocket"] == "NOT_STARTED"
    assert health["submits"] is False
    assert health["return_calculation"] == "BLOCKED"
    assert health["entry_rest"] == "POLICY_UNRESOLVED"
    assert health["exit_priority"] == "POLICY_UNRESOLVED"
    assert health["latency"] == "UNASSUMED"
    assert health["observations_collected"] == 2
    source = (PACKAGE / "prospective.py").read_text(encoding="utf-8")
    assert "import socket" not in source
    assert "import httpx" not in source


def test_public_poll_records_market_data_and_does_not_send(tmp_path: Path):
    from roller.choosin_texas.execution_validation.feed import poll_once, public_request_headers

    assert "Authorization" not in public_request_headers()
    received = "2026-09-25T08:00:00+00:00"

    def fake(path: str) -> tuple[dict, str]:
        if "series_ticker=KXNCAAMBGAME" in path:
            return {"markets": [], "cursor": ""}, received
        if "series_ticker=KXNBAGAME" in path:
            return {
                "markets": [
                    {
                        "ticker": "KXNBAGAME-TEST",
                        "status": "active",
                        "updated_time": received,
                        "yes_bid_dollars": "0.5300",
                        "yes_ask_dollars": "0.5400",
                        "yes_bid_size_fp": "10.67",
                    }
                ],
                "cursor": "",
            }, received
        if path.endswith("/orderbook?depth=10"):
            return {"orderbook_fp": {"yes_dollars": [["0.5300", "10.67"]]}}, received
        if "/trades?" in path:
            return {"trades": [{"created_time": received, "yes_price_dollars": "0.5200", "count_fp": "1.00"}]}, received
        if "candlesticks" in path:
            return {"candlesticks": []}, received
        raise AssertionError(path)

    first = poll_once(tmp_path, get=fake)
    assert first["submits"] is False
    assert first["simulated_fills"] == "BLOCKED"
    assert first["markets_seen"] == 1
    text = (tmp_path / "market_data" / "KXNBAGAME-TEST.jsonl").read_text(encoding="utf-8")
    assert "HYPOTHETICAL_ORDER_INTENT" not in text
    assert '"sent": false' in text
    assert "NOT_REPORTED" in text
    assert "0.5300" in text


def test_one_exported_diagnostic_matches_the_candle_file():
    path = repo_root() / "research" / "choosin_texas" / "execution_validation" / "diagnostics_80_40.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    sample = rows[0]
    candle = next(
        (repo_root() / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/candles_1m").rglob(
            f"{sample['instrument']}.parquet"
        )
    )
    trade = next(
        (repo_root() / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/trades").rglob(
            f"{sample['instrument']}.parquet"
        )
    )
    again = diagnose_position(
        {
            "strategy": sample["strategy"],
            "configuration_id": sample["configuration_id"],
            "event_id": sample["event_id"],
            "ticker": sample["instrument"],
            "entry_ts": sample["signal_ts"],
            "exit_ts": sample["signal_ts"] + 1,
            "exit_type": "SETTLEMENT_YES",
            "contracts": sample["entry"]["contracts_requested"],
            "through_close_cents": sample["benchmark_exit_cents"],
            "realized_pnl_cents": sample["benchmark_pnl_cents"],
        },
        candle_path=candle,
        trade_path=trade,
    )
    assert again["entry"]["classification"]["quote_relation"] == sample["entry"]["classification"]["quote_relation"]
    assert again["entry"]["modeled_filled_contracts"] is None
    assert again["reference"] == "CANDLE_PATH_NOT_FILL"
