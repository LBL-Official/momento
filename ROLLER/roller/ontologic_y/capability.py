"""Market capability matrix. A winner classifier does not fill these cells."""

from __future__ import annotations

MARKETS = (
    ("moneyline", "game"),
    ("spread", "game"),
    ("alternate_spread", "game"),
    ("total", "game"),
    ("alternate_total", "game"),
    ("total", "Q1"),
    ("total", "Q2"),
    ("total", "Q3"),
    ("total", "Q4"),
    ("alternate_total", "Q1"),
    ("alternate_total", "Q2"),
    ("alternate_total", "Q3"),
    ("alternate_total", "Q4"),
)


def live_partitions() -> dict:
    unavailable = {"status": "MARKET_MODEL_UNAVAILABLE", "buckets": []}
    return {"margin": unavailable, "total": unavailable, "quarters": unavailable}


def capability_matrix() -> list[dict]:
    return [
        {
            "market": market,
            "period": period,
            "status": "MARKET_MODEL_UNAVAILABLE",
            "query_lines": "CONFIGURED_MODEL_LINES_NOT_SPORTSBOOK",
        }
        for market, period in MARKETS
    ]
