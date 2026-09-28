"""Orderbook parse and Kalshi settlement helpers. No historical L2."""

from __future__ import annotations

from roller.ingest.orderbook import parse_orderbook_payload
from roller.research.first80 import settled_yes


def test_best_yes_is_last_yes_dollars_level():
    parsed = parse_orderbook_payload(
        {"orderbook_fp": {"yes_dollars": [["0.3900", "1.00"], ["0.4000", "5.00"]], "no_dollars": [["0.5900", "2.00"]]}}
    )
    assert parsed["best_yes_bid_e4"] == "4000"
    assert parsed["best_no_bid_e4"] == "5900"
    assert parsed["market_data_type"] == "ORDERBOOK_SNAPSHOT"
    assert parsed["yes_levels"] == 2


def test_settled_yes_from_result_or_e4():
    assert settled_yes("yes", None) == "1"
    assert settled_yes("no", None) == "0"
    assert settled_yes("", 10000) == "1"
    assert settled_yes("", 0) == "0"
    assert settled_yes("", None) == ""
