"""Frozen Phase 5A candidate registry. Written and hashed before any PNL."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.austin.experiments.policy_v2.ids import (
    BIN_GE_02,
    DISTRESS_STATES,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    SUPPORT_MIN,
    WATCH_NEGATIVE,
)

# Phase 4 fixed calibration bins are [0,0.2), [0.2,0.4), ...
# N<10 is not strong evidence. H1 only. No EV / price / clock cuts.
# These four are the entire family. Do not add more after economics.


def candidate_registry() -> dict[str, Any]:
    return {
        "phase": "PHASE_5A",
        "policy_object": "AUSTIN_DRE_POLICY_V2",
        "source_phase_4": "AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1",
        "hazard_family": "H1",
        "no_h2_fallback": True,
        "no_ev_threshold": True,
        "no_policy_a_f": True,
        "threshold_source": "phase4_fixed_calibration_bins_and_frozen_core_states",
        "t40_already_semantic": "ALLOW_TRIGGER_CLASSIFY_TOO_LATE",
        "missing_required_probability": "NONE",
        "missing_reason": "REQUIRED_HAZARD_UNAVAILABLE",
        "first_fire_only": True,
        "support_rule": {
            "min_support_n": SUPPORT_MIN,
            "reject_austin_support": "LOW_HISTORICAL_SUPPORT",
            "source": "Phase 4 N<10 is not strong evidence; declared before economics",
        },
        "candidates": [
            {
                "candidate_id": "DRE_C1_WATCH_LOSS_GE_0P2",
                "required_core_states": [WATCH_NEGATIVE],
                "required_CI_state": None,
                "p_terminal_loss_condition": {"field": "p_terminal_loss_H1", "op": "ge", "value": BIN_GE_02},
                "p_recovery_condition": None,
                "support_requirement": {"p_terminal_loss_H1": SUPPORT_MIN, "reject_low_historical_support": True},
                "T40_ALREADY_handling": "ALLOW_AND_CLASSIFY_TOO_LATE",
                "missing_value_behavior": "NONE",
                "first_fire_behavior": "first PIT state satisfying frozen policy",
                "rationale": (
                    "Phase 4 WATCH vs HEALTHY p_loss is the only directionally consistent loss contrast. "
                    "0.2 is the frozen second calibration-bin edge. A WATCH mean 0.213 and B WATCH 0.543 sit at/above it."
                ),
            },
            {
                "candidate_id": "DRE_C2_P2PLUS_RECOVERY_LT_0P2",
                "required_core_states": [PERSISTENCE_2, PERSISTENCE_3PLUS],
                "required_CI_state": None,
                "p_terminal_loss_condition": None,
                "p_recovery_condition": {"field": "p_recovery_t1_H1", "op": "lt", "value": BIN_GE_02},
                "support_requirement": {"p_recovery_t1_H1": SUPPORT_MIN, "reject_low_historical_support": True},
                "T40_ALREADY_handling": "ALLOW_AND_CLASSIFY_TOO_LATE",
                "missing_value_behavior": "NONE",
                "first_fire_behavior": "first PIT state satisfying frozen policy",
                "rationale": (
                    "Phase 4 A recovery t1 drops into the first calibration bin at P2/P3PLUS "
                    "(0.069 / 0.051). B recovery is expected thin; support rule will fail-close those cells."
                ),
            },
            {
                "candidate_id": "DRE_C3_DISTRESS_TWO_SIDED",
                "required_core_states": list(DISTRESS_STATES),
                "required_CI_state": None,
                "p_terminal_loss_condition": {"field": "p_terminal_loss_H1", "op": "ge", "value": BIN_GE_02},
                "p_recovery_condition": {"field": "p_recovery_t1_H1", "op": "lt", "value": BIN_GE_02},
                "support_requirement": {
                    "p_terminal_loss_H1": SUPPORT_MIN,
                    "p_recovery_t1_H1": SUPPORT_MIN,
                    "reject_low_historical_support": True,
                },
                "T40_ALREADY_handling": "ALLOW_AND_CLASSIFY_TOO_LATE",
                "missing_value_behavior": "NONE",
                "first_fire_behavior": "first PIT state satisfying frozen policy",
                "rationale": (
                    "Two-sided Phase 4 language: elevated loss-bin and impaired recovery-bin on any distress state."
                ),
            },
            {
                "candidate_id": "DRE_C4_WATCH_TWO_SIDED",
                "required_core_states": [WATCH_NEGATIVE],
                "required_CI_state": None,
                "p_terminal_loss_condition": {"field": "p_terminal_loss_H1", "op": "ge", "value": BIN_GE_02},
                "p_recovery_condition": {"field": "p_recovery_t1_H1", "op": "lt", "value": BIN_GE_02},
                "support_requirement": {
                    "p_terminal_loss_H1": SUPPORT_MIN,
                    "p_recovery_t1_H1": SUPPORT_MIN,
                    "reject_low_historical_support": True,
                },
                "T40_ALREADY_handling": "ALLOW_AND_CLASSIFY_TOO_LATE",
                "missing_value_behavior": "NONE",
                "first_fire_behavior": "first PIT state satisfying frozen policy",
                "rationale": (
                    "Same two-sided bins restricted to WATCH_NEGATIVE, the only B distress state that still had "
                    "adverse cents remaining in Phase 4 timing."
                ),
            },
        ],
    }


def registry_hash(payload: dict[str, Any] | None = None) -> str:
    blob = json.dumps(payload if payload is not None else candidate_registry(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def candidates() -> list[dict[str, Any]]:
    return list(candidate_registry()["candidates"])
