"""Fee assumptions. Production KalshiFeeModel is UNAVAILABLE."""

from __future__ import annotations

from typing import Any

from roller.austin.config import DEFAULT


def fee_block(*, assumed_cents_per_side: float | None = None) -> dict[str, Any]:
    if assumed_cents_per_side is None:
        return {
            "fee_model_status": DEFAULT.fee_status,
            "fee_model_version": DEFAULT.fee_model_version,
            "gross_ev": None,
            "entry_fees": None,
            "exit_fees": None,
            "hedge_fees": None,
            "net_ev": None,
            "note": "Do not treat demo/audit fees as live KXNBA production fees.",
        }
    return {
        "fee_model_status": "ASSUMPTION",
        "fee_model_version": "configured_assumption",
        "assumed_cents_per_side": float(assumed_cents_per_side),
        "note": "Configured assumption. Not OBSERVED_PRODUCTION_MODEL.",
    }
