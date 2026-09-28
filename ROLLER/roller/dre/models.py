"""dre.position_state.v1 contract types. Frontend consumes only this shape."""

from __future__ import annotations

from typing import Any, Literal

SCHEMA_VERSION = "dre.position_state.v1"
LIST_SCHEMA_VERSION = "dre.position_list.v1"
PRODUCT = "DRE"
LIVE_EXECUTION = False

Mode = Literal["HISTORICAL", "REPLAY"]
ObservationState = Literal["OBSERVED", "UNKNOWN", "UNAVAILABLE"]

ALLOWED_OBSERVATION_STATES = frozenset({"OBSERVED", "UNKNOWN", "UNAVAILABLE"})
FORBIDDEN_CURRENT_STATES = frozenset(
    {
        "HEALTHY",
        "WATCH",
        "TEMPORARY_DISTRESS",
        "RECOVERING",
        "PERSISTENT_DETERIORATION",
        "INTERVENTION_WINDOW",
        "HEDGE",
        "REDUCE",
        "LIQUIDATE",
        "WATCH_NEGATIVE",
        "PERSISTENCE_2",
        "PERSISTENCE_3PLUS",
        "HEALTHY_AFTER_RECOVERY",
    }
)
FUTURE_STATE_LEGEND = (
    "HEALTHY",
    "WATCH",
    "TEMPORARY_DISTRESS",
    "RECOVERING",
    "PERSISTENT_DETERIORATION",
    "INTERVENTION_WINDOW",
    "HEDGE",
    "REDUCE",
    "LIQUIDATE",
)
EVIDENCE_EVENTS = frozenset({"ENTRY", "ENTRY_QUERY", "AS_OF_QUERY", "CURRENT_AS_OF"})

HOLD_REASON_V1 = "MODEL_OBSERVATION_ONLY"
DYNAMIC_RISK_CLASS_V1 = "UNAVAILABLE"
CT_EV_DEFINITION = "derived-four trade population"
AUSTIN_EV_DEFINITION = "historical nearest-state estimate"
AUSTIN_EV_FORMULA = "20S − 80(1−S)"
CT_EV_FORMULA = "20S − 40(1−S)"


def future_state_legend() -> list[dict[str, str]]:
    return [
        {
            "state": name,
            "availability": "UNAVAILABLE",
            "role": "canonical_future_definition",
            "note": "Not a current 604 position state. DRE V1 has no risk classifier.",
        }
        for name in FUTURE_STATE_LEGEND
    ]


def intervention_stub() -> dict[str, Any]:
    return {
        "authorized": False,
        "policy_id": "NONE",
        "policy_status": "NO_POLICY_FROZEN",
        "available_actions": [],
        "current_action": "NONE",
        "action_reason": "No frozen DRE policy. Model observation only.",
        "hedge_target": None,
        "reduce_target": None,
        "liquidation_target": None,
        "execution_enabled": False,
        "execution": "DISABLED",
        "execution_handler": None,
        "note": "DRE does not submit. Vital is not called.",
    }
