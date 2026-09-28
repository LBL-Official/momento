"""Write Phase 2 / Phase 3 lock markers only. Do not rewrite historical results."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.ids import (
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
)
from roller.austin.experiments.ids import PHASE2_ID, PHASE3_ID
from roller.austin.experiments.manifest import sha256_file
from roller.austin.paths import downfall_phase3_dir, persistence_phase2_dir
from roller.austin.store import load_json, write_json


def _require_hash(path, expected: str, label: str) -> str:
    digest = sha256_file(path)
    if digest != expected:
        raise AustinError("LOCK_MISMATCH", f"{label} hash drifted; STOP")
    return digest


def finalize_phase2() -> dict[str, Any]:
    root = persistence_phase2_dir()
    report_sha = _require_hash(root / "REPORT.md", PHASE2_REPORT_SHA256, "Phase 2 REPORT.md")
    stats_sha = _require_hash(root / "statistics.json", PHASE2_STATISTICS_SHA256, "Phase 2 statistics.json")
    manifest_sha = _require_hash(root / "MANIFEST.json", PHASE2_MANIFEST_SHA256, "Phase 2 MANIFEST.json")
    stats = load_json(root / "statistics.json")
    interp = stats.get("interpretation") or {}
    if interp.get("phase_3_justified") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 2 phase_3_justified drifted")
    payload = {
        "phase": "PHASE_2",
        "status": "FINALIZED",
        "audit_id": PHASE2_ID,
        "actionability_gate": "NOT_MET",
        "gate_a_persistence_economics": interp.get("gate_a_persistence_economics"),
        "gate_b_pit_distinguishability": interp.get("gate_b_pit_distinguishability"),
        "gate_c_timing": interp.get("gate_c_timing"),
        "gate_d_data_integrity": interp.get("gate_d_data_integrity"),
        "report_hash": report_sha,
        "statistics_hash": stats_sha,
        "manifest_hash": manifest_sha,
        "policy_status": "UNFROZEN",
        "confirmation_A": "NOT_RUN",
        "confirmation_B": "NOT_RUN",
        "finalized_for_waterfall": True,
        "historical_artifacts_modified": False,
    }
    path = root / "FINALIZED.json"
    if path.is_file():
        current = load_json(path)
        if current.get("report_hash") != report_sha or current.get("actionability_gate") != "NOT_MET":
            raise AustinError("LOCK_MISMATCH", "Phase 2 FINALIZED.json drifted")
        return current
    write_json(path, payload)
    if sha256_file(root / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT changed while writing FINALIZED.json")
    return payload


def finalize_phase3() -> dict[str, Any]:
    root = downfall_phase3_dir()
    _require_hash(root / "REPORT.md", PHASE3_REPORT_SHA256, "Phase 3 REPORT.md")
    _require_hash(root / "statistics.json", PHASE3_STATISTICS_SHA256, "Phase 3 statistics.json")
    hashed = schema_hash(state_schema())
    if hashed != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "downfall_state_v1 hash drifted")
    stats = load_json(root / "statistics.json")
    interp = stats.get("interpretation") or {}
    if interp.get("gate_a_state_validity") != "PASS":
        raise AustinError("LOCK_MISMATCH", "Phase 3 Gate A drifted")
    payload = {
        "phase": "PHASE_3",
        "status": "COMPLETE",
        "model_id": PHASE3_ID,
        "state_schema_version": "downfall_state_v1",
        "state_schema_hash": STATE_SCHEMA_HASH,
        "state_validity": interp.get("gate_a_state_validity"),
        "economic_state_separation": interp.get("gate_b_economic_separation"),
        "transition_information": interp.get("gate_c_transition_information"),
        "timing": interp.get("gate_d_timing_remaining_damage"),
        "phase_4_decision": "MIXED",
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "historical_artifacts_modified": False,
        "report_hash": PHASE3_REPORT_SHA256,
        "statistics_hash": PHASE3_STATISTICS_SHA256,
    }
    path = root / "FINALIZED.json"
    if path.is_file():
        current = load_json(path)
        if current.get("state_schema_hash") != STATE_SCHEMA_HASH:
            raise AustinError("LOCK_MISMATCH", "Phase 3 FINALIZED.json drifted")
        return current
    write_json(path, payload)
    if sha256_file(root / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT changed while writing FINALIZED.json")
    return payload
