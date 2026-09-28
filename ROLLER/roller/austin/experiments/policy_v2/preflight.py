"""Fail-closed Phase 4 gate. Do not reconstruct Phase 4 from Discovery."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash as hazard_schema_hash
from roller.austin.experiments.manifest import LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.policy_v2.ids import (
    HAZARD_SCHEMA_HASH,
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
)
from roller.austin.paths import downfall_phase3_dir, hazard_phase4_dir, persistence_phase2_dir, policy_phase5_dir
from roller.austin.store import load_json

REQUIRED_PHASE4 = (
    "HAZARD_SCHEMA.json",
    "MANIFEST.json",
    "statistics.json",
    "REPORT.md",
    "hazard_state_entries.csv",
    "hazard_predictions_H0.csv",
    "hazard_predictions_H1.csv",
    "hazard_predictions_H2.csv",
    "model_metrics.csv",
    "model_comparison.csv",
    "hazard_timing.csv",
    "model_hash_audit.json",
    "state_schema_audit.json",
    "cohort_hash_audit.json",
    "leakage_audit.json",
    "crossfit_audit.json",
    "confirmation_protection_audit.json",
)


def write_blocked(reason: str) -> None:
    root = policy_phase5_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "PHASE5_BLOCKED.md").write_text(
        "\n".join(
            [
                "AUSTIN DRE",
                "PHASE 5 — NOT STARTED",
                "",
                "REASON:",
                reason,
                "",
                "Do not reconstruct Phase 4 from Discovery.",
                "Do not select POLICY_A…F.",
                "POLICY STATUS remains UNFROZEN.",
                "CONFIRMATION UNTOUCHED.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def phase4_preflight() -> dict[str, Any]:
    root = hazard_phase4_dir()
    missing = [name for name in REQUIRED_PHASE4 if not (root / name).is_file()]
    if missing:
        write_blocked("PHASE 4 HAS NOT COMPLETED.")
        raise AustinError("DATA_REQUIRED", "PHASE 5 NOT STARTED. PHASE 4 HAS NOT COMPLETED.")
    manifest = load_json(root / "MANIFEST.json")
    stats = load_json(root / "statistics.json")
    interp = stats.get("interpretation") or {}
    if not interp.get("phase_4_complete"):
        write_blocked("PHASE 4 HAS NOT COMPLETED.")
        raise AustinError("LOCK_MISMATCH", "PHASE 5 NOT STARTED. PHASE 4 HAS NOT COMPLETED.")
    if manifest.get("confirmation_accessed") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 4 confirmation_accessed drifted")
    if manifest.get("policy_status") != "UNFROZEN" or manifest.get("policy_selected") != "NONE":
        raise AustinError("LOCK_MISMATCH", "Phase 4 policy lock drifted")
    if manifest.get("execution_enabled") is not False or manifest.get("submits") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 4 execution lock drifted")
    if manifest.get("hazard_schema_hash") != HAZARD_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "Phase 4 hazard schema hash drifted")
    if hazard_schema_hash(hazard_schema()) != HAZARD_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "in-code hazard schema drifted")
    if schema_hash(state_schema()) != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "downfall_state_v1 hash drifted")
    model = verify_model_manifest()
    if model.get("model_manifest_hash") != LOCKED_MANIFEST_HASH:
        raise AustinError("LOCK_MISMATCH", "Austin model hash drifted")
    p2 = persistence_phase2_dir()
    p3 = downfall_phase3_dir()
    if sha256_file(p2 / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT drifted")
    if sha256_file(p2 / "statistics.json") != PHASE2_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 statistics drifted")
    if sha256_file(p2 / "MANIFEST.json") != PHASE2_MANIFEST_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 MANIFEST drifted")
    if sha256_file(p3 / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT drifted")
    if sha256_file(p3 / "statistics.json") != PHASE3_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 statistics drifted")
    klass = interp.get("phase_5_classification")
    if klass in {"NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"}:
        write_blocked(f"Phase 4 classified Phase 5 as {klass}. A trading policy cannot be scientifically preregistered.")
        raise AustinError("LOCK_MISMATCH", f"PHASE 5 NOT STARTED. Phase 4 classification={klass}")
    if klass not in {"SUPPORTED", "MIXED"}:
        write_blocked(f"Phase 4 Phase 5 classification is {klass}.")
        raise AustinError("LOCK_MISMATCH", "PHASE 5 NOT STARTED. Phase 4 classification unusable.")
    return {
        "status": "PASS",
        "phase_4_complete": True,
        "phase_5_classification": klass,
        "phase_5_decision": interp.get("phase_5_decision"),
        "phase_5_note": interp.get("phase_5_note"),
        "gates": {
            "A": interp.get("gate_a_probability_validity"),
            "B": interp.get("gate_b_terminal_loss_information"),
            "C": interp.get("gate_c_recovery_information"),
            "D": interp.get("gate_d_dynamic_update"),
            "E": interp.get("gate_e_timing"),
            "F": interp.get("gate_f_transfer_support"),
        },
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "mixed_caveat": klass == "MIXED",
    }
