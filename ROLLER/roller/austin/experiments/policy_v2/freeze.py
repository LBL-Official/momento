"""Phase 5B human freeze gate. UNSET writes readiness only. Does not run confirmation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash as hazard_schema_hash
from roller.austin.experiments.ids import PHASE5_ID
from roller.austin.experiments.manifest import LOCKED_HASHES, LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.load import confirmation_files_absent
from roller.austin.experiments.policy_v2.frozen import freeze_object_hash
from roller.austin.experiments.policy_v2.ids import (
    HAZARD_SCHEMA_HASH,
    LOCKED_CONFIRMATION_HASH,
    LOCKED_DISCOVERY_HASH,
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
    EXPERIMENT_A,
    EXPERIMENT_B,
)
from roller.austin.experiments.policy_v2.phase5a_lock import (
    CANDIDATE_REGISTRY_HASH,
    PHASE5A_FILE_HASHES,
    PHASE5A_MANIFEST_HASH,
    PHASE5A_REQUIRED,
)
from roller.austin.paths import downfall_phase3_dir, hazard_phase4_dir, persistence_phase2_dir, policy_phase5_dir
from roller.austin.store import load_json, write_json

FREEZE_ID = "AUSTIN_DRE_POLICY_V2_FREEZE_001"
UNSET = "UNSET"
BLOCKING_JUSTIFICATIONS = {"NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"}
ALLOWED_JUSTIFICATIONS = {"SUPPORTED", "MIXED", "NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"}


def _require_phase5a() -> dict[str, Any]:
    root = policy_phase5_dir()
    missing = [name for name in PHASE5A_REQUIRED if not (root / name).is_file()]
    if missing:
        raise AustinError("DATA_REQUIRED", f"PHASE 5B BLOCKED. Phase 5A incomplete: {missing}")
    hashes = {name: sha256_file(root / name) for name in PHASE5A_REQUIRED}
    for name, expected in PHASE5A_FILE_HASHES.items():
        if hashes[name] != expected:
            raise AustinError("LOCK_MISMATCH", f"Phase 5A artifact drifted: {name}")
    manifest = load_json(root / "MANIFEST.json")
    stats = load_json(root / "statistics.json")
    registry = load_json(root / "POLICY_CANDIDATES.json")
    interp = stats.get("interpretation") or {}
    if manifest.get("phase") != "PHASE_5A":
        raise AustinError("LOCK_MISMATCH", "PHASE 5B BLOCKED. Phase 5A incomplete.")
    if manifest.get("policy_status") != "UNFROZEN":
        raise AustinError("LOCK_MISMATCH", "Phase 5A policy_status drifted")
    if hashes["POLICY_CANDIDATES.json"] != CANDIDATE_REGISTRY_HASH:
        raise AustinError("LOCK_MISMATCH", "candidate_registry_hash drifted")
    if manifest.get("candidate_registry_hash") != CANDIDATE_REGISTRY_HASH:
        raise AustinError("LOCK_MISMATCH", "MANIFEST candidate_registry_hash drifted")
    justified = interp.get("human_freeze_justified")
    if justified not in ALLOWED_JUSTIFICATIONS:
        raise AustinError("LOCK_MISMATCH", f"HUMAN_FREEZE_JUSTIFIED unusable: {justified}")
    return {
        "root": root,
        "manifest": manifest,
        "stats": stats,
        "registry": registry,
        "interp": interp,
        "proposed": interp.get("proposed_policy") or manifest.get("policy_proposed") or "NONE",
        "justified": justified,
        "phase5a_hashes": hashes,
    }


def _prior_locks() -> dict[str, Any]:
    p2 = persistence_phase2_dir()
    p3 = downfall_phase3_dir()
    p4 = hazard_phase4_dir()
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
    if schema_hash(state_schema()) != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "state schema hash drifted")
    p4_stats = load_json(p4 / "statistics.json")
    if not (p4_stats.get("interpretation") or {}).get("phase_4_complete"):
        raise AustinError("LOCK_MISMATCH", "Phase 4 is not COMPLETE")
    p4_manifest = load_json(p4 / "MANIFEST.json")
    if p4_manifest.get("hazard_schema_hash") != HAZARD_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "Phase 4 hazard schema hash drifted")
    if hazard_schema_hash(hazard_schema()) != HAZARD_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "in-code hazard schema drifted")
    model = verify_model_manifest()
    if model.get("model_manifest_hash") != LOCKED_MANIFEST_HASH:
        raise AustinError("LOCK_MISMATCH", "Austin model hash drifted")
    if int(model.get("training_n_trades") or 0) != 604:
        raise AustinError("LOCK_MISMATCH", "training_n_trades drifted")
    if int(model.get("training_n_snapshots") or 0) != 48752:
        raise AustinError("LOCK_MISMATCH", "training_n_snapshots drifted")
    if int(model.get("knn_k") or 0) != 25:
        raise AustinError("LOCK_MISMATCH", "K drifted")
    from roller.austin.paths import model_manifest_path

    disk = load_json(model_manifest_path())
    if disk.get("model_version") != "austin_v2":
        raise AustinError("LOCK_MISMATCH", "model_version drifted")
    if disk.get("dataset_version") != "choosin_nba_2q3q_604":
        raise AustinError("LOCK_MISMATCH", "dataset_version drifted")
    for name, expected in LOCKED_HASHES.items():
        if (model.get("hashes") or {}).get(name) != expected:
            raise AustinError("LOCK_MISMATCH", f"Austin artifact hash drifted: {name}")
    if disk.get("ncaab_used_for_training") is not False:
        raise AustinError("LOCK_MISMATCH", "NCAAB used for training")
    if sha256_file(policy_phase5_dir() / "POLICY_CANDIDATES.json") != CANDIDATE_REGISTRY_HASH:
        raise AustinError("LOCK_MISMATCH", "candidate registry hash drifted")
    return {
        "status": "PASS",
        "phase_2": "FINALIZED",
        "phase_2_actionability": "NOT_MET",
        "phase_3": "COMPLETE",
        "state_schema_hash": STATE_SCHEMA_HASH,
        "phase_4": "COMPLETE",
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "austin_manifest_hash": LOCKED_MANIFEST_HASH,
        "candidate_registry_hash": CANDIDATE_REGISTRY_HASH,
        "A_discovery_hash": LOCKED_DISCOVERY_HASH[EXPERIMENT_A],
        "A_confirmation_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_A],
        "B_discovery_hash": LOCKED_DISCOVERY_HASH[EXPERIMENT_B],
        "B_confirmation_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_B],
        "five_austin_artifact_hashes": LOCKED_HASHES,
    }


def _assert_phase5a_unchanged(before: dict[str, str]) -> None:
    root = policy_phase5_dir()
    for name, expected in before.items():
        if sha256_file(root / name) != expected:
            raise AustinError("LOCK_MISMATCH", f"Phase 5A artifact rewritten: {name}")


def _candidate(registry: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for row in registry.get("candidates") or []:
        if row.get("candidate_id") == candidate_id:
            return json_clone(row)
    raise AustinError("QUERY_REJECTED", f"unknown candidate_id {candidate_id}")


def json_clone(payload: dict[str, Any]) -> dict[str, Any]:
    import json

    return json.loads(json.dumps(payload))


def _write_none_closeout(root, phase5a: dict[str, Any], justified: str) -> None:
    from roller.austin.experiments.policy_v2.frozen import freeze_object_hash

    finalized = {
        "phase": "PHASE_5",
        "status": "FINALIZED",
        "phase5a_status": "COMPLETE",
        "phase5b_status": "COMPLETE",
        "proposed_policy": phase5a["proposed"],
        "human_selected_policy": "NONE",
        "human_freeze_justified": justified,
        "policy_frozen": False,
        "confirmation_spend_authorized": False,
        "next_waterfall_stage": "PHASE_6_CONFIRMATION_GATE",
        "confirmation_expected_action": "PRESERVE_UNTOUCHED",
        "candidate_registry_hash": CANDIDATE_REGISTRY_HASH,
        "policy_freeze_created": False,
        "confirmation_accessed": False,
        "execution_enabled": False,
        "submits": False,
    }
    digest = freeze_object_hash(finalized)
    finalized["phase5_finalization_hash"] = digest
    write_json(root / "PHASE5_FINALIZED.json", finalized)
    reread = load_json(root / "PHASE5_FINALIZED.json")
    if freeze_object_hash({k: v for k, v in reread.items() if k != "phase5_finalization_hash"}) != digest:
        raise AustinError("LOCK_MISMATCH", "PHASE5_FINALIZED hash drifted")
    (root / "PHASE5B_CLOSEOUT.md").write_text(
        "\n".join(
            [
                "AUSTIN DRE",
                "PHASE 5B — HUMAN POLICY DECISION",
                "",
                "NO POLICY SELECTED",
                "",
                "DISCOVERY EVIDENCE DID NOT SUPPORT FREEZE",
                "",
                "CONFIRMATION UNTOUCHED",
                "EXECUTION DISABLED",
                "",
                "C1/C2 fired but did not establish supported economic improvement.",
                "C3/C4 never fired.",
                "Timing remained weak.",
                "Phase 5A therefore proposed NONE.",
                "Researcher selected NONE.",
                "No policy is frozen.",
                "",
                "NONE is a research decision, not an executable policy.",
                "POLICY_FREEZE.json was not created.",
                "Confirmation remains unspent.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _readiness_md(payload: dict[str, Any]) -> str:
    lines = [
        "AUSTIN DRE",
        "PHASE 5B — POLICY FREEZE GATE",
        "",
        "POLICY FREEZE GATE",
        "CONFIRMATION UNTOUCHED",
        "EXECUTION DISABLED",
        "",
        f"Phase 5A status: {payload['phase5a_status']}",
        f"Phase 5A proposed policy: {payload['phase5a_proposed_policy']}",
        f"human freeze justification: {payload['human_freeze_justified']}",
        f"human selected policy: {payload['human_selected_policy']}",
        f"candidate exists in registry?: {payload['candidate_in_registry']}",
        f"all prior hashes valid?: {payload['prior_hashes']}",
        f"confirmation untouched?: {payload['confirmation_untouched']}",
        f"freeze permitted?: {payload['freeze_permitted']}",
        f"freeze created?: {payload['freeze_created']}",
        f"policy freeze hash: {payload['policy_freeze_hash']}",
        "Phase 6 started?: NO",
        "",
        f"FREEZE {payload['readiness_label']}",
        payload["closing_line"],
        "",
    ]
    return "\n".join(lines)


def stage_policy_freeze(human_selected_policy: str = UNSET) -> dict[str, Any]:
    human = str(human_selected_policy or UNSET).strip() or UNSET
    phase5a = _require_phase5a()
    locks = _prior_locks()
    confirmation = confirmation_files_absent()
    if confirmation.get("status") != "PASS":
        raise AustinError("LOCK_MISMATCH", "confirmation result artifacts present")
    root = phase5a["root"]
    if (root / "PHASE6_CONTRACT.json").is_file() and human == UNSET:
        # readiness-only may still run; Phase 6 execution remains forbidden
        pass
    freeze_exists = (root / "POLICY_FREEZE.json").is_file()
    ids = [c.get("candidate_id") for c in phase5a["registry"].get("candidates") or []]
    in_registry = human in ids
    justified = phase5a["justified"]
    evidence_blocks = justified in BLOCKING_JUSTIFICATIONS
    freeze_permitted = justified in {"SUPPORTED", "MIXED"} and human not in {UNSET, "NONE"} and in_registry
    freeze_created = False
    freeze_hash = None
    decision_status = "AWAITING_HUMAN_POLICY_SELECTION"
    policy_status = "UNFROZEN"
    closing = "AWAITING HUMAN POLICY SELECTION"
    readiness_label = "NOT READY" if evidence_blocks or human == UNSET else "READY"
    if human == UNSET:
        freeze_permitted = False
        readiness_label = "NOT READY" if evidence_blocks else "READY"
        closing = "AWAITING HUMAN POLICY SELECTION"
        decision_status = "AWAITING_HUMAN_POLICY_SELECTION"
    elif human == "NONE":
        freeze_permitted = False
        readiness_label = "NOT READY"
        closing = "HUMAN DECISION NONE. NO EXECUTABLE FREEZE."
        decision_status = "NO_POLICY_SELECTED"
        policy_status = "NO_POLICY_FROZEN"
    elif not in_registry:
        raise AustinError("QUERY_REJECTED", f"unknown candidate_id {human}")
    elif evidence_blocks:
        freeze_permitted = False
        readiness_label = "NOT READY"
        closing = "POLICY FREEZE BLOCKED BY PHASE 5A EVIDENCE"
        decision_status = "BLOCKED_BY_PHASE_5A_EVIDENCE"
        policy_status = "UNFROZEN"
    else:
        if freeze_exists:
            raise AustinError("LOCK_MISMATCH", "POLICY_FREEZE.json already exists; will not overwrite")
        decision_status = "AUTHORIZED"
        policy_status = "FROZEN"
        readiness_label = "READY"
        closing = "FREEZE CREATED"
        candidate = _candidate(phase5a["registry"], human)
        freeze_payload = {
            "freeze_id": FREEZE_ID,
            "phase": "PHASE_5B",
            "policy_object": PHASE5_ID,
            "human_selected_policy": human,
            "phase5a_proposed_policy": phase5a["proposed"],
            "human_freeze_justified": justified,
            "freeze_evidence_status": justified if justified == "MIXED" else justified,
            "candidate_definition": candidate,
            "candidate_registry_hash": CANDIDATE_REGISTRY_HASH,
            "source_phase5a_manifest_hash": PHASE5A_MANIFEST_HASH,
            "source_phase4_model": "AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1",
            "hazard_schema_version": "loss_hazard_recovery_v1",
            "hazard_schema_hash": HAZARD_SCHEMA_HASH,
            "source_phase3_model": "AUSTIN_DOWNFALL_STATE_MODEL_V1",
            "state_schema_version": "downfall_state_v1",
            "state_schema_hash": STATE_SCHEMA_HASH,
            "source_austin_model": "austin_v2",
            "austin_manifest_hash": LOCKED_MANIFEST_HASH,
            "A_discovery_hash": LOCKED_DISCOVERY_HASH[EXPERIMENT_A],
            "A_confirmation_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_A],
            "B_discovery_hash": LOCKED_DISCOVERY_HASH[EXPERIMENT_B],
            "B_confirmation_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_B],
            "observation_schedule": "EVERY_2_GAME_CLOCK_MINUTES",
            "first_fire_only": True,
            "missing_required_input_behavior": "NONE",
            "execution_semantics": "INTERVENE_OR_NONE_RESEARCH_ONLY",
            "scenario_primary": "SCENARIO_B_NEXT_AVAILABLE_1M_CLOSE_NOT_FILL",
            "policy_status": "FROZEN",
            "confirmation_accessed": False,
            "confirmation_run": False,
            "execution_enabled": False,
            "submits": False,
            "git_commit": "UNAVAILABLE",
            "git_commit_reason": "not_a_git_repo",
            "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        freeze_hash = freeze_object_hash(freeze_payload)
        freeze_payload["policy_freeze_hash"] = freeze_hash
        write_json(root / "POLICY_FREEZE.json", freeze_payload)
        reread = load_json(root / "POLICY_FREEZE.json")
        if freeze_object_hash(reread) != freeze_hash or reread.get("policy_freeze_hash") != freeze_hash:
            raise AustinError("LOCK_MISMATCH", "policy freeze read-back hash mismatch")
        write_json(
            root / "PHASE6_CONTRACT.json",
            {
                "source_policy_freeze_id": FREEZE_ID,
                "policy_freeze_hash": freeze_hash,
                "Austin_model_hash": LOCKED_MANIFEST_HASH,
                "state_schema_hash": STATE_SCHEMA_HASH,
                "hazard_schema_hash": HAZARD_SCHEMA_HASH,
                "candidate_registry_hash": CANDIDATE_REGISTRY_HASH,
                "A_confirmation_cohort_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_A],
                "B_confirmation_cohort_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_B],
                "confirmation_A_expected_N": 97,
                "confirmation_B_expected_N": 70,
                "member_order": ["A", "B"],
                "allow_policy_modification": False,
                "allow_threshold_modification": False,
                "allow_model_refit": False,
                "allow_state_schema_change": False,
                "allow_hazard_schema_change": False,
                "allow_candidate_change": False,
                "allow_confirmation_peek": False,
                "phase_6_started": False,
            },
        )
        freeze_created = True

    if human in {UNSET, "NONE"} or evidence_blocks or not freeze_created:
        if (root / "POLICY_FREEZE.json").is_file() and human == UNSET:
            raise AustinError("LOCK_MISMATCH", "UNSET must not create POLICY_FREEZE.json")

    decision = {
        "phase": "PHASE_5B",
        "phase5a_proposed_policy": phase5a["proposed"],
        "human_selected_policy": human,
        "human_freeze_justified": justified,
        "human_decision_status": decision_status,
        "candidate_registry_hash": CANDIDATE_REGISTRY_HASH,
        "policy_freeze_created": freeze_created,
        "policy_freeze_hash": freeze_hash,
        "confirmation_accessed": False,
        "confirmation_A": "NOT_RUN",
        "confirmation_B": "NOT_RUN",
        "phase6_started": False,
        "policy_status": policy_status,
        "phase6_authorized": False,
        "phase_6_authorized": False,
        "execution_enabled": False,
        "submits": False,
        "note": (
            f"Phase 5A proposed {phase5a['proposed']}. "
            + ("Researcher has not selected a policy." if human == UNSET else f"Researcher selected {human}.")
        ),
    }
    readiness = {
        "phase5a_status": "COMPLETE",
        "phase5a_proposed_policy": phase5a["proposed"],
        "human_freeze_justified": justified,
        "human_selected_policy": human,
        "candidate_in_registry": in_registry,
        "prior_hashes": "PASS",
        "confirmation_untouched": True,
        "freeze_permitted": freeze_permitted,
        "freeze_created": freeze_created,
        "policy_freeze_hash": freeze_hash or "NOT_WRITTEN",
        "readiness_label": readiness_label,
        "closing_line": closing,
        "freeze_evidence_status": justified,
    }
    audit = {
        "status": "PASS",
        "phase": "PHASE_5B",
        "human_selected_policy": human,
        "phase5a_proposed_policy": phase5a["proposed"],
        "human_freeze_justified": justified,
        "freeze_evidence_status": justified,
        "prior_locks": locks,
        "phase5a_hashes": phase5a["phase5a_hashes"],
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "phase_6_started": False,
        "policy_freeze_created": freeze_created,
        "policy_freeze_hash": freeze_hash,
        "execution_enabled": False,
        "submits": False,
    }
    write_json(root / "POLICY_DECISION.json", decision)
    write_json(root / "FREEZE_AUDIT.json", audit)
    (root / "FREEZE_READINESS.md").write_text(_readiness_md(readiness) + "\n", encoding="utf-8")
    if human == "NONE":
        _write_none_closeout(root, phase5a, justified)
    _assert_phase5a_unchanged(phase5a["phase5a_hashes"])
    if human == UNSET and (root / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "UNSET wrote POLICY_FREEZE.json")
    if human == "NONE" and (root / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "NONE created an executable freeze")
    if human == UNSET and (root / "PHASE6_CONTRACT.json").is_file():
        raise AustinError("LOCK_MISMATCH", "UNSET wrote PHASE6_CONTRACT.json")
    return {
        "phase": "PHASE_5B",
        "human_selected_policy": human,
        "phase5a_proposed_policy": phase5a["proposed"],
        "human_freeze_justified": justified,
        "policy_status": policy_status,
        "policy_freeze_created": freeze_created,
        "policy_freeze_hash": freeze_hash,
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "phase_6_started": False,
        "execution": "DISABLED",
        "submits": False,
        "closing": closing,
    }
