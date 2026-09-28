"""Frozen downfall_state_v1 schema. Definitions are not tuned mid-run."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.austin.experiments.downfall.ids import (
    ARCHETYPE_NEG_RECOVERY,
    ARCHETYPE_PERS_RECOVERY,
    ARCHETYPE_SINGLE,
    ARCHETYPE_STABLE,
    ARCHETYPE_TO_P2,
    ARCHETYPE_TO_P3,
    ARCHETYPE_UNRESOLVED,
    CORE_STATES,
    FORBIDDEN_CORE,
    STATE_SCHEMA_VERSION,
)


def state_schema() -> dict[str, Any]:
    return {
        "version": STATE_SCHEMA_VERSION,
        "states": list(CORE_STATES),
        "forbidden_core_states": sorted(FORBIDDEN_CORE),
        "rules": {
            "PRE_ENTRY": "empty history; no locked FIRST80 position yet",
            "HEALTHY": "EV>=0 and this segment has never entered distress",
            "WATCH_NEGATIVE": "EV<0 and first valid negative of the current streak",
            "PERSISTENCE_2": "current and immediately previous adjacent valid PRIMARY both EV<0",
            "PERSISTENCE_3PLUS": "current plus at least two immediately previous adjacent valids EV<0",
            "RECOVERING": "previous valid EV<0 and current EV>=0",
            "HEALTHY_AFTER_RECOVERY": "after RECOVERING, subsequent valid rows that stay EV>=0",
            "UNRESOLVED": "current PRIMARY has no valid EV, or continuity cannot be established",
        },
        "gap_rule": (
            "An unavailable/invalid PRIMARY checkpoint emits UNRESOLVED and breaks the streak. "
            "The next valid row starts a new segment: HEALTHY or WATCH_NEGATIVE. "
            "Recovery memory does not survive a gap. Persistence is never inferred across a gap."
        ),
        "overlays": {
            "CI_STATE": ["CI_POSITIVE", "CI_CROSSES_ZERO", "CI_NEGATIVE", "CI_UNAVAILABLE"],
            "SUPPORT_STATE": ["NORMAL_SUPPORT", "LOW_HISTORICAL_SUPPORT", "SUPPORT_UNAVAILABLE"],
            "note": "Overlays do not modify core_state.",
        },
        "archetypes_first_match": [
            ARCHETYPE_UNRESOLVED,
            ARCHETYPE_STABLE,
            ARCHETYPE_PERS_RECOVERY,
            ARCHETYPE_TO_P3,
            ARCHETYPE_TO_P2,
            ARCHETYPE_SINGLE,
            ARCHETYPE_NEG_RECOVERY,
        ],
        "archetype_rules": {
            ARCHETYPE_UNRESOLVED: "no valid core state other than UNRESOLVED, or WATCH with no later branch",
            ARCHETYPE_STABLE: "never WATCH_NEGATIVE",
            ARCHETYPE_PERS_RECOVERY: "reached PERSISTENCE_2 or PERSISTENCE_3PLUS, later RECOVERING",
            ARCHETYPE_TO_P3: "reached PERSISTENCE_3PLUS, never RECOVERING",
            ARCHETYPE_TO_P2: "reached PERSISTENCE_2, never PERSISTENCE_3PLUS, never RECOVERING",
            ARCHETYPE_SINGLE: "WATCH then RECOVERING, never PERSISTENCE_2",
            ARCHETYPE_NEG_RECOVERY: "WATCH then RECOVERING after other observed distress not covered above",
        },
        "no_threshold_search": True,
        "no_hazard_model": True,
        "price_does_not_define_core": True,
        "score_does_not_define_core": True,
    }


def schema_hash(schema: dict[str, Any] | None = None) -> str:
    payload = schema if schema is not None else state_schema()
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
