"""Phase 6: record why confirmation is not spent. No confirmation queries."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, PHASE5_ID, PHASE6_ID
from roller.austin.experiments.manifest import LOCKED_MANIFEST_HASH, sha256_file
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH
from roller.austin.experiments.persistence.load import confirmation_files_absent, load_confirmation_identity
from roller.austin.experiments.policy_v2.ids import HAZARD_SCHEMA_HASH, STATE_SCHEMA_HASH
from roller.austin.paths import confirmation_gate_dir, policy_phase5_dir
from roller.austin.store import load_json, write_json


def stage_confirmation_gate() -> dict[str, Any]:
    phase5 = policy_phase5_dir()
    if (phase5 / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "POLICY_FREEZE.json present; Phase 6 fail-closed")
    finalized = load_json(phase5 / "PHASE5_FINALIZED.json")
    decision = load_json(phase5 / "POLICY_DECISION.json")
    if finalized.get("human_selected_policy") != "NONE" or finalized.get("policy_frozen") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 5 did not close with NONE / unfrozen")
    if finalized.get("confirmation_spend_authorized") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 5 confirmation spend must be unauthorized")
    if decision.get("human_selected_policy") != "NONE":
        raise AustinError("LOCK_MISMATCH", "POLICY_DECISION is not NONE")
    authorized = decision.get("phase6_authorized")
    if authorized is None:
        authorized = decision.get("phase_6_authorized")
    if authorized is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 6 is not authorized")
    if confirmation_files_absent().get("status") != "PASS":
        raise AustinError("LOCK_MISMATCH", "confirmation result artifacts present")
    ident_a = load_confirmation_identity(EXPERIMENT_A)
    ident_b = load_confirmation_identity(EXPERIMENT_B)
    if ident_a["cohort_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A confirmation hash drifted")
    if ident_b["cohort_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B confirmation hash drifted")
    if int(ident_a.get("n_trades") or 0) != 97:
        raise AustinError("LOCK_MISMATCH", "A confirmation N drifted")
    if int(ident_b.get("n_trades") or 0) != 70:
        raise AustinError("LOCK_MISMATCH", "B confirmation N drifted")
    root = confirmation_gate_dir()
    root.mkdir(parents=True, exist_ok=True)
    cohort = {
        "status": "PASS",
        "A": {**ident_a, "expected_n": 97, "status": "SEALED_UNSPENT"},
        "B": {**ident_b, "expected_n": 70, "status": "SEALED_UNSPENT"},
        "outcomes_accessed": False,
    }
    access = {
        "status": "PASS",
        "confirmation_outcomes_accessed": False,
        "confirmation_queries_generated": False,
        "confirmation_state_model_generated": False,
        "confirmation_hazard_generated": False,
        "confirmation_policy_generated": False,
        "confirmation_result_csvs": False,
        "note": "identity/hash only; no confirmation spend",
    }
    policy_audit = {
        "status": "PASS",
        "source_phase5": PHASE5_ID,
        "human_selected_policy": "NONE",
        "policy_frozen": False,
        "policy_freeze_present": False,
        "phase5_finalization_hash": finalized.get("phase5_finalization_hash"),
        "confirmation_spend_authorized": False,
    }
    manifest = {
        "phase": "PHASE_6",
        "phase_name": "UNTOUCHED_CONFIRMATION_GATE",
        "status": "BLOCKED_NO_FROZEN_POLICY",
        "gate_id": PHASE6_ID,
        "source_phase5_status": "FINALIZED",
        "source_policy": "NONE",
        "policy_freeze_present": False,
        "confirmation_A_expected_N": 97,
        "confirmation_B_expected_N": 70,
        "confirmation_A_run": False,
        "confirmation_B_run": False,
        "confirmation_outcomes_accessed": False,
        "confirmation_queries_generated": False,
        "confirmation_state_model_generated": False,
        "confirmation_hazard_generated": False,
        "confirmation_policy_generated": False,
        "A_CONFIRMATION_STATUS": "SEALED_UNSPENT",
        "B_CONFIRMATION_STATUS": "SEALED_UNSPENT",
        "A_confirmation_hash": ident_a["cohort_hash"],
        "B_confirmation_hash": ident_b["cohort_hash"],
        "austin_model_hash": LOCKED_MANIFEST_HASH,
        "state_schema_hash": STATE_SCHEMA_HASH,
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "phase5_finalization_hash": finalized.get("phase5_finalization_hash"),
        "execution_enabled": False,
        "submits": False,
    }
    write_json(root / "confirmation_cohort_audit.json", cohort)
    write_json(root / "confirmation_access_audit.json", access)
    write_json(root / "phase5_policy_audit.json", policy_audit)
    write_json(root / "MANIFEST.json", manifest)
    (root / "REPORT.md").write_text(
        "\n".join(
            [
                "AUSTIN DRE",
                "PHASE 6 — UNTOUCHED CONFIRMATION GATE",
                "",
                "NO FROZEN POLICY",
                "",
                "CONFIRMATION NOT SPENT",
                "",
                "# 1. WHY PHASE 6 DID NOT RUN",
                "",
                "Phase 6 is not a failed confirmation test. No confirmation test occurred.",
                "The confirmation cohorts remain unspent because Phase 5 did not produce a supported frozen policy.",
                "",
                "# 2. PHASE 5 HANDOFF",
                "",
                "HUMAN_SELECTED_POLICY NONE. POLICY_STATUS NO_POLICY_FROZEN. PHASE6_AUTHORIZED false.",
                "",
                "# 3. CONFIRMATION COHORT INTEGRITY",
                "",
                "A expected N=97 SEALED_UNSPENT. B expected N=70 SEALED_UNSPENT. Hashes identity-checked only.",
                "",
                "# 4. CONFIRMATION ACCESS AUDIT",
                "",
                "No outcomes, queries, states, hazards, or policy ledgers were generated.",
                "",
                "# 5. WHAT WOULD HAVE BEEN REQUIRED TO RUN",
                "",
                "POLICY_FREEZE.json, valid policy_freeze_hash, PHASE6_CONTRACT.json, and explicit Phase 6 authorization.",
                "",
                "# 6. WHY PRESERVATION IS THE CORRECT RESULT",
                "",
                "Spending confirmation without a frozen policy would convert an untested cohort into a fishing sample.",
                "",
                "# 7. NEXT WATERFALL STAGE",
                "",
                "PHASE 7 — PROSPECTIVE NBA 2026–27 VALIDATION. Do not reopen historical confirmation.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if (phase5 / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 6 wrote or found POLICY_FREEZE.json")
    return {
        "phase": "PHASE_6",
        "status": "BLOCKED_NO_FROZEN_POLICY",
        "A_CONFIRMATION_STATUS": "SEALED_UNSPENT",
        "B_CONFIRMATION_STATUS": "SEALED_UNSPENT",
        "confirmation_outcomes_accessed": False,
        "policy_status": "NO POLICY FROZEN",
        "execution": "DISABLED",
        "manifest_hash": sha256_file(root / "MANIFEST.json"),
    }
