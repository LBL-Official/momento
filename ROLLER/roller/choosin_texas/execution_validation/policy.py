"""Versioned execution specification for the frozen PLANNED_RISK_CAP3 comparison.

Parameters that the candle policy does not state stay missing. Missing
parameters are not filled in with a canonical net return.
"""

from __future__ import annotations

from typing import Any

SPEC_ID = "PAIRED_EXECUTION_VALIDATION_V1"
CONFIGURATION_ID = "PLANNED_RISK_CAP3"
REFERENCE_CONFIGURATION_ID = "CAPITAL_6PCT_CAP3"

ENTRY_LIMIT_CENTS = 80
STOP_CENTS = {"80/40": 40, "80/65": 65}
INITIAL_CONTRACTS = {"80/40": 1000, "80/65": 1500}
INITIAL_PREMIUM_CENTS = {"80/40": 80_000, "80/65": 120_000}
PLANNED_LOSS_NOTE = {"80/40": "2% of session basis", "80/65": "1.125% of session basis"}
STARTING_CASH_CENTS = 2_000_000
MAX_OPEN_POSITIONS = 3
REFERENCE_PNL_CENTS = {"80/40": 5_335_376, "80/65": 8_119_467}
REFERENCE_ACCEPTED = {"80/40": 820, "80/65": 865}
CAPITAL_6PCT_PNL_CENTS = {"80/40": 11_164_842, "80/65": 8_119_467}
CAPITAL_6PCT_INITIAL_CONTRACTS = {"80/40": 1500, "80/65": 1500}
UNIT_BOOK_CENTS = {"80/40": 3297, "80/65": 2410}

# Series metadata snapshot after the historical book. It does not cover
# entry dates 2025-10-10 through 2026-06-13.
FEE_SNAPSHOT = {
    "series": ["KXNBAGAME", "KXNCAAMBGAME"],
    "fee_type": "quadratic",
    "fee_multiplier": 1,
    "maker_fee_when_fee_type_is_quadratic": 0,
    "verified_on": "2026-09-03",
    "pdf_effective": "2026-07-07",
    "applies_to_historical_book": False,
    "provenance": "docs/research/KALSHI_SPORTS_FEE_MODEL_2026_2027.md",
}


def specification() -> dict[str, Any]:
    return {
        "spec_id": SPEC_ID,
        "configuration_id": CONFIGURATION_ID,
        "separate_configuration_id": REFERENCE_CONFIGURATION_ID,
        "live_execution": "LIVE_EXECUTION_DISABLED",
        "reference_evidence": "CANDLE_PATH_NOT_FILL",
        "simulated_evidence": "SIMULATED_EXECUTION",
        "actual_evidence": "ACTUAL_FILL",
        "out_of_sample": False,
        "informed_strategy_selection": True,
        "max_open_positions": MAX_OPEN_POSITIONS,
        "established": [
            {
                "name": "entry_signal",
                "value": "Existing ledger timestamp. That second is the minute-close when the candle book marks entry.",
            },
            {
                "name": "earliest_order_submission",
                "value": "The entry or stop signal timestamp. No order is eligible before that close is observable.",
            },
            {
                "name": "entry_side_and_price",
                "value": "Buy YES at 80 cents. Nominal price. The candle close bid may differ.",
            },
            {
                "name": "post_only_intent",
                "value": "The research description is a maker entry and a maker exit.",
            },
            {
                "name": "stop_detection",
                "value": "First later minute whose yes bid close is at or below 40 or 65. Detection is not an order.",
            },
            {
                "name": "settlement",
                "value": "Candle survivors are marked at 100 cents in the benchmark. That mark is not an exchange fill of our order.",
            },
            {
                "name": "taker_fallback",
                "value": "NOT_AUTHORIZED",
            },
            {
                "name": "opponent_hedge",
                "value": "NOT_AUTHORIZED",
            },
            {
                "name": "position_cap",
                "value": "Three open slots across sports and slices. A pending entry occupies a slot.",
            },
        ],
        "missing": [
            "Latency after the candle close. No game-time local receive clock is in the historical files.",
            "Order lifetime and the cancellation clock.",
            "Queue position. A trade at our price is not a fill.",
            "Exit order price after the stop print: the stop level versus the observed bid.",
            "Repricing.",
            "Partial-fill priority across the two books. Accounting rules exist for a later replay. They are not applied to historical P&L.",
            "A fee schedule whose effective dates cover every historical entry.",
        ],
        "canonical_net_return": "NOT_PUBLISHED",
        "execution_aware_portfolio_pnl": "NOT_REPORTED",
    }
