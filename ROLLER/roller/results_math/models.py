"""Analysis statuses. No PREDICTED / ALPHA / EDGE as empirical statuses."""

from __future__ import annotations

from typing import Any, TypeVar

OBSERVED = "OBSERVED"
DERIVED = "DERIVED"
HYPOTHETICAL = "HYPOTHETICAL"
MODEL_ASSUMED = "MODEL_ASSUMED"
UNAVAILABLE = "UNAVAILABLE"
INCOMPLETE = "INCOMPLETE"
DATA_REQUIRED = "DATA_REQUIRED"
NOT_APPLICABLE = "NOT_APPLICABLE"
CARDINALITY_VIOLATION = "CARDINALITY_VIOLATION"
UNVERIFIED = "UNVERIFIED"
INVALID_SEMANTICS = "INVALID_SEMANTICS"
AMBIGUOUS = "AMBIGUOUS"
INSUFFICIENT_PROCESS = "INSUFFICIENT_PROCESS"
NOT_COMPUTED = "NOT_COMPUTED"

T = TypeVar("T")


def unavailable(reason: str) -> dict[str, Any]:
    return {"status": UNAVAILABLE, "value": None, "reason": reason}


def not_computed(reason: str) -> dict[str, Any]:
    return {"status": NOT_COMPUTED, "value": None, "reason": reason}


def measured(value: T, *, provenance: str, **detail: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"status": provenance, "value": value}
    out.update(detail)
    return out
