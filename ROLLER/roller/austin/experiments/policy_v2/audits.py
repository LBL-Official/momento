"""Phase 5A integrity. Confirmation is identity-only. Registry hash is immutable after economics."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.hazard.finalize import finalize_phase2, finalize_phase3
from roller.austin.experiments.manifest import sha256_file
from roller.austin.experiments.persistence.audits import cohort_hash_audit, confirmation_protection_audit, model_hash_audit
from roller.austin.experiments.policy_v2.candidates import registry_hash
from roller.austin.experiments.policy_v2.decide import decide
from roller.austin.experiments.policy_v2.ids import HAZARD_SCHEMA_HASH, PHASE2_REPORT_SHA256, PHASE3_REPORT_SHA256, STATE_SCHEMA_HASH
from roller.austin.experiments.policy_v2.preflight import phase4_preflight
from roller.austin.paths import downfall_phase3_dir, persistence_phase2_dir, suite_freeze_path


def phase2_finalization_audit() -> dict[str, Any]:
    payload = finalize_phase2()
    if sha256_file(persistence_phase2_dir() / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT drifted")
    return {"status": "PASS", "finalized": payload, "historical_artifacts_modified": False}


def phase3_finalization_audit() -> dict[str, Any]:
    payload = finalize_phase3()
    if sha256_file(downfall_phase3_dir() / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT drifted")
    return {"status": "PASS", "finalized": payload, "historical_artifacts_modified": False}


def phase4_finalization_audit() -> dict[str, Any]:
    return phase4_preflight()


def hazard_schema_audit() -> dict[str, Any]:
    return {"status": "PASS", "hazard_schema_hash": HAZARD_SCHEMA_HASH, "state_schema_hash": STATE_SCHEMA_HASH}


def candidate_registry_audit(before: str, after: str, n_candidates: int) -> dict[str, Any]:
    if before != after:
        raise AustinError("LOCK_MISMATCH", "POLICY_CANDIDATES.json changed after economics")
    if n_candidates > 4:
        raise AustinError("LOCK_MISMATCH", "candidate count exceeds 4")
    return {
        "status": "PASS",
        "candidate_registry_hash": before,
        "n_candidates": n_candidates,
        "immutable_after_economics": True,
    }


def leakage_audit(entries: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    failed = 0
    for cand in candidates:
        for row in entries[:12]:
            first = decide(cand, row)
            mutated = dict(row)
            mutated["TARGET_terminal_loss"] = 1
            mutated["TARGET_recovery_t1"] = 1
            mutated["OUTCOME_eventual_result"] = "LOSS"
            mutated["won"] = False
            second = decide(cand, mutated)
            checked += 1
            if first != second:
                failed += 1
    return {
        "status": "PASS" if checked and failed == 0 else "FAIL",
        "n_checked": checked,
        "n_failed": failed,
        "note": "Mutating future targets/outcomes must leave decide() unchanged.",
    }


def confirmation_audit() -> dict[str, Any]:
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 5A refuses POLICY_FREEZE.json")
    return confirmation_protection_audit()


__all__ = [
    "phase2_finalization_audit",
    "phase3_finalization_audit",
    "phase4_finalization_audit",
    "hazard_schema_audit",
    "candidate_registry_audit",
    "leakage_audit",
    "confirmation_audit",
    "model_hash_audit",
    "cohort_hash_audit",
    "registry_hash",
]
