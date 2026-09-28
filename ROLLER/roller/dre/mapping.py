"""Mechanical DRE V1 mapping. No HEALTHY/WATCH/HEDGE current states."""

from __future__ import annotations

from typing import Any

from roller.dre.models import ALLOWED_OBSERVATION_STATES, HOLD_REASON_V1


def observation_from_austin(query: dict[str, Any] | None) -> dict[str, Any]:
    if not query:
        return {
            "observation_state": "UNAVAILABLE",
            "insufficient_support": False,
            "reason": "No current Austin inference",
        }
    status = str(query.get("status") or "")
    knn = str(query.get("knn_status") or status)
    reason = str(query.get("reason") or "")
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    support_label = str(support.get("support") or "")
    low_support = support_label in {"LOW HISTORICAL SUPPORT", "LOW_HISTORICAL_SUPPORT"}
    if status in {"UNAVAILABLE", "DATA_REQUIRED", "QUERY_REJECTED"} or knn in {"UNAVAILABLE"}:
        return {
            "observation_state": "UNAVAILABLE",
            "insufficient_support": False,
            "reason": reason or status or "Austin inference unavailable",
        }
    if status == "INSUFFICIENT_SAMPLE" or knn == "INSUFFICIENT_SAMPLE" or reason in {
        "NO_ENTRY_IN_FITTED_SPACE",
    }:
        return {
            "observation_state": "UNKNOWN",
            "insufficient_support": True,
            "reason": reason or "INSUFFICIENT_SAMPLE",
        }
    if status in {"OBSERVED", "QUERY_PARTIAL"} or knn == "OBSERVED":
        return {
            "observation_state": "OBSERVED",
            "insufficient_support": low_support,
            "reason": "LOW_HISTORICAL_SUPPORT" if low_support else "Austin historical query observed",
        }
    return {
        "observation_state": "UNKNOWN",
        "insufficient_support": low_support,
        "reason": reason or status or "Austin status not mapped",
    }


def assert_observation_state(value: str) -> str:
    if value not in ALLOWED_OBSERVATION_STATES:
        raise ValueError(f"illegal DRE V1 observation_state {value!r}")
    return value


def hold_reason_v1() -> str:
    return HOLD_REASON_V1
