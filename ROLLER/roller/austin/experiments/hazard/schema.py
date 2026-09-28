"""Frozen loss_hazard_recovery_v1 schema. Definitions are not tuned mid-run."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.austin.experiments.hazard.ids import (
    FAMILIES,
    HAZARD_SCHEMA_VERSION,
    JEFFREYS_A,
    JEFFREYS_B,
    STATE_SCHEMA_HASH,
    STATE_SCHEMA_VERSION,
)


def hazard_schema() -> dict[str, Any]:
    return {
        "version": HAZARD_SCHEMA_VERSION,
        "source_state_schema_version": STATE_SCHEMA_VERSION,
        "source_state_schema_hash": STATE_SCHEMA_HASH,
        "model_families": list(FAMILIES),
        "conditioning": {
            "H0": ["member"],
            "H1": ["core_state"],
            "H2": ["core_state", "CI_state"],
        },
        "no_h2_to_h1_fallback": True,
        "prior": {"name": "JEFFREYS", "alpha": JEFFREYS_A, "beta": JEFFREYS_B},
        "estimator": "p_hat = (y + 0.5) / (n + 1); n=0 => UNAVAILABLE",
        "crossfit": "LEAVE_ONE_GAME_OUT exclude internal_game_id",
        "observation_schedule": "EVERY_2_GAME_CLOCK_MINUTES",
        "horizons": ["t1", "t2", "t3"],
        "targets": {
            "TARGET_terminal_loss": "1 if locked FIRST80 settles loss else 0",
            "TARGET_recovery_t1": "next adjacent valid PRIMARY EV>=0; UNAVAILABLE if gap",
            "TARGET_recovery_by_t2": "EV>=0 within next two adjacent valids; UNAVAILABLE if incomplete",
            "TARGET_recovery_by_t3": "EV>=0 within next three adjacent valids; UNAVAILABLE if incomplete",
            "TARGET_deeper_distress_next": "next valid core_state has greater STATE_DEPTH",
            "TARGET_T40_before_recovery": "NOT_APPLICABLE if T40 already at entry",
        },
        "eligibility": {
            "terminal_loss": "all first trade x core_state entries",
            "recovery": "WATCH_NEGATIVE PERSISTENCE_2 PERSISTENCE_3PLUS only",
        },
        "censoring": "UNAVAILABLE is never coded as 0",
        "gap_rule": "Invalid or UNRESOLVED PRIMARY slot breaks continuity. No interpolation.",
        "no_threshold_search": True,
        "no_classifier": True,
        "no_policy": True,
        "no_composite_score": True,
    }


def schema_hash(schema: dict[str, Any] | None = None) -> str:
    payload = schema if schema is not None else hazard_schema()
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
