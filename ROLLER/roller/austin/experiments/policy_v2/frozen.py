"""Deterministic frozen-policy reconstruction. Research INTERVENE/NONE only."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.policy_v2.decide import decide
from roller.austin.experiments.policy_v2.ids import INTERVENE, NONE


def freeze_object_hash(payload: dict[str, Any]) -> str:
    body = {
        k: v
        for k, v in payload.items()
        if k
        not in {
            "policy_freeze_hash",
            "phase5_finalization_hash",
            "prospective_lock_hash",
        }
    }
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def evaluate_frozen_dre_policy(frozen_policy: dict[str, Any], pit_state: dict[str, Any]) -> dict[str, Any]:
    expected = frozen_policy.get("policy_freeze_hash")
    if expected:
        digest = freeze_object_hash(frozen_policy)
        if digest != expected:
            raise AustinError("LOCK_MISMATCH", "candidate hash mismatch")
    candidate = frozen_policy.get("candidate_definition")
    if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
        raise AustinError("LOCK_MISMATCH", "frozen candidate_definition missing")
    verdict = decide(candidate, pit_state)
    return {"action": verdict["action"], "reason": verdict["reason"], "timing_class": verdict.get("timing_class")}


def first_fire_frozen(frozen_policy: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(entries, key=lambda r: int(r.get("state_sequence_number") or 0))
    out = []
    fired = False
    for row in ordered:
        verdict = evaluate_frozen_dre_policy(frozen_policy, row)
        if verdict["action"] == INTERVENE and fired:
            out.append({**verdict, "action": NONE, "reason": "IGNORED_FOR_FIRST_FIRE"})
            continue
        if verdict["action"] == INTERVENE:
            fired = True
        out.append(verdict)
    return out
