"""Last-print bars never forward-fill and never invent yes_bid."""

import pandas as pd

from roller.mlb.last_print import (
    aggregate_last_prints,
    aggregate_last_prints_frame,
    last_print_has_yes_bid,
)


def test_last_print_minute_absence_and_last_chronological():
    trades = [
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:10Z", "yes_price_cents": 80},
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:40Z", "yes_price_cents": 81},
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:02:05Z", "yes_price_cents": 79},
    ]
    rows = aggregate_last_prints(trades, ingested_at="t", pipeline_version="test")
    by_min = {r["candle_timestamp"]: int(r["last_close_e4"]) for r in rows}
    assert by_min["2026-06-18T12:00:00Z"] == 8100
    assert "2026-06-18T12:01:00Z" not in by_min
    assert by_min["2026-06-18T12:02:00Z"] == 7900
    assert all(not last_print_has_yes_bid(r) for r in rows)


def test_only_last_trade_does_not_create_yes_bid():
    rows = aggregate_last_prints(
        [{"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:00Z", "yes_price_cents": 81}],
        ingested_at="t",
        pipeline_version="test",
    )
    assert rows[0]["last_close_e4"] == "8100"
    assert "yes_bid_close" not in rows[0] or rows[0].get("yes_bid_close") in (None, "")


def test_subcent_and_missing_ts_are_dropped():
    rows = aggregate_last_prints(
        [
            {"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:10Z", "yes_price_dollars": "0.8010"},
            {"ticker": "T", "yes_price_cents": 80},
            {"ticker": "", "exchange_timestamp": "2026-06-18T12:00:10Z", "yes_price_cents": 80},
        ],
        ingested_at="t",
        pipeline_version="test",
    )
    assert rows == []


def test_landing_overlay_same_minute_last_print_wins():
    parquet = aggregate_last_prints(
        [{"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:10Z", "yes_price_cents": 70}],
        ingested_at="t",
        pipeline_version="test",
    )
    landing = aggregate_last_prints(
        [{"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:40Z", "yes_price_cents": 81}],
        ingested_at="t",
        pipeline_version="test",
    )
    from roller.mlb.ingest import _index_rows

    merged = _index_rows(parquet)
    merged.update(_index_rows(landing))
    row = merged[("T", "2026-06-18T12:00:00Z")]
    assert row["last_close_e4"] == "8100"


def test_frame_aggregator_matches_list_contract():
    trades = [
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:10Z", "yes_price_cents": 80},
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:00:40Z", "yes_price_cents": 81},
        {"ticker": "T", "exchange_timestamp": "2026-06-18T12:02:05Z", "yes_price_cents": 79},
    ]
    listed = {
        r["candle_timestamp"]: int(r["last_close_e4"])
        for r in aggregate_last_prints(trades, ingested_at="t", pipeline_version="test")
    }
    framed = {
        r["candle_timestamp"]: int(r["last_close_e4"])
        for r in aggregate_last_prints_frame(
            pd.DataFrame(trades), ingested_at="t", pipeline_version="test"
        )
    }
    assert listed == framed
    assert "2026-06-18T12:01:00Z" not in framed
