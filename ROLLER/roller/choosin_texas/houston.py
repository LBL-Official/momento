"""Houston: declared taker other-side identity. Not L2. Not a fill."""

from __future__ import annotations

from typing import Any

HOUSTON_ID = "HOUSTON_TAKER_OTHER_SIDE_V1"
NO_ASK_SOURCE = "SOURCE_UNAVAILABLE"
DECLARED_NO_TAKER = "DECLARED_COMPLEMENT_OF_YES_BID"


def houston_identity() -> dict[str, Any]:
    return {
        "desk": "Houston",
        "identity": HOUSTON_ID,
        "role": "TAKER_OTHER_SIDE_SCENARIO",
        "standalone_page": False,
        "live_execution": False,
        "submits": False,
        "l2": NO_ASK_SOURCE,
        "no_ask": NO_ASK_SOURCE,
        "declared_no_taker_price": DECLARED_NO_TAKER,
        "formula": "no_taker_cents = 100 - yes_bid; lock_vs_entry = yes_bid - 80",
        "fill_status": "FILL_UNAVAILABLE",
        "fee_model": "UNAVAILABLE",
        "candle_path_not_fill": True,
        "note": "Houston is declared inside Katy. It is not warehouse L2 and not a Kalshi taker fill.",
    }


def declared_no_taker_cents(yes_bid: int) -> int:
    return 100 - int(yes_bid)


def declared_lock_vs_entry_cents(yes_bid: int, *, entry_cents: int = 80) -> int:
    return int(yes_bid) - int(entry_cents)
