"""Read persisted experiment artifacts for the research API. No inference."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import (
    AUDIT_ID,
    PHASE2_ID,
    PHASE3_ID,
    PHASE4_ID,
    PHASE5_ID,
    PHASE6_ID,
    PHASE7_ID,
    EXECUTION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    FILL_STATUS,
    LIVE_FEED,
    MEMBERS,
    N_BY_EXPERIMENT,
    PAGE3_BOOK_CENTS,
    PAGE3_EV_CENTS,
    PAGE3_N,
    PAGE3_S,
    SLICE_BY_EXPERIMENT,
    SUITE_ID,
    assert_experiment_id,
)
from roller.austin.paths import (
    experiment_dir,
    model_manifest_path,
    downfall_phase3_dir,
    hazard_phase4_dir,
    policy_phase5_dir,
    confirmation_gate_dir,
    prospective_phase7_dir,
    persistence_audit_dir,
    persistence_phase2_dir,
    suite_freeze_path,
)
from roller.austin.store import load_json


def _optional_json(path) -> dict[str, Any] | None:
    payload = load_json(path, required=False)
    return payload or None


def _cohort_summary(experiment_id: str, role: str) -> dict[str, Any] | None:
    name = "discovery_cohort.json" if role == "DISCOVERY" else "confirmation_cohort.json"
    payload = _optional_json(experiment_dir(experiment_id) / name)
    if not payload:
        return None
    return {
        "role": role,
        "n_games": payload.get("n_games"),
        "n_trades": payload.get("n_trades"),
        "cohort_hash": payload.get("cohort_hash"),
        "split_method": payload.get("split_method"),
    }


def _stage_block(experiment_id: str, role: str) -> dict[str, Any]:
    folder = experiment_dir(experiment_id) / role.lower()
    stats = _optional_json(folder / "statistics.json")
    report = folder / "REPORT.md"
    confirmation_result = "NOT RUN" if role == "CONFIRMATION" and stats is None else ("OBSERVED" if stats is not None else None)
    return {
        "role": role,
        "label": "NOT RUN" if role == "CONFIRMATION" and stats is None else ("CONFIRMATION" if role == "CONFIRMATION" else "DISCOVERY"),
        "headline": role == "CONFIRMATION",
        "present": stats is not None,
        "result": confirmation_result,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "path_coverage": _optional_json(folder / "path_coverage.json"),
    }


def handle_experiments() -> dict[str, Any]:
    freeze = _optional_json(suite_freeze_path())
    members = []
    for experiment_id in MEMBERS:
        members.append(
            {
                "experiment_id": experiment_id,
                "slice": SLICE_BY_EXPERIMENT[experiment_id],
                "n_lock": N_BY_EXPERIMENT[experiment_id],
                "discovery": _cohort_summary(experiment_id, "DISCOVERY"),
                "confirmation": _cohort_summary(experiment_id, "CONFIRMATION"),
                "confirmation_present": (experiment_dir(experiment_id) / "confirmation" / "statistics.json").is_file(),
                "discovery_present": (experiment_dir(experiment_id) / "discovery" / "statistics.json").is_file(),
            }
        )
    return {
        "status": "OBSERVED",
        "product": "Austin",
        "page": "CONDITIONAL RISK VALIDATION",
        "suite_id": SUITE_ID,
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "training_n": 604,
        "page3_control": {
            "n": PAGE3_N,
            "s": PAGE3_S,
            "ev_cents": PAGE3_EV_CENTS,
            "book_cents": PAGE3_BOOK_CENTS,
            "role": "DISPLAY_ONLY_NOT_AUSTIN_COHORT",
            "queried": False,
        },
        "policy_freeze": freeze,
        "members": members,
        "persistence_audit": {
            "audit_id": AUDIT_ID,
            "present": (persistence_audit_dir() / "MANIFEST.json").is_file(),
            "policy_status": "UNFROZEN",
            "confirmation_accessed": False,
        },
        "persistence_phase2": {
            "audit_id": PHASE2_ID,
            "present": (persistence_phase2_dir() / "MANIFEST.json").is_file(),
            "policy_status": "UNFROZEN",
            "confirmation_accessed": False,
        },
        "downfall_phase3": {
            "model_id": PHASE3_ID,
            "present": (downfall_phase3_dir() / "MANIFEST.json").is_file(),
            "policy_status": "UNFROZEN",
            "confirmation_accessed": False,
            "hazard_model_built": False,
        },
        "hazard_phase4": {
            "model_id": PHASE4_ID,
            "present": (hazard_phase4_dir() / "MANIFEST.json").is_file(),
            "policy_status": "UNFROZEN",
            "confirmation_accessed": False,
        },
        "dre_policy_phase5a": {
            "policy_object": PHASE5_ID,
            "present": (policy_phase5_dir() / "MANIFEST.json").is_file(),
            "policy_status": (
                "FROZEN"
                if (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
                else (
                    "NO_POLICY_FROZEN"
                    if (policy_phase5_dir() / "PHASE5_FINALIZED.json").is_file()
                    else "UNFROZEN"
                )
            ),
            "confirmation_accessed": False,
            "phase_5b_present": (policy_phase5_dir() / "POLICY_DECISION.json").is_file(),
            "phase5_finalized": (policy_phase5_dir() / "PHASE5_FINALIZED.json").is_file(),
            "policy_freeze_present": (policy_phase5_dir() / "POLICY_FREEZE.json").is_file(),
        },
        "confirmation_gate_phase6": {
            "gate_id": PHASE6_ID,
            "present": (confirmation_gate_dir() / "MANIFEST.json").is_file(),
            "status": "BLOCKED_NO_FROZEN_POLICY" if (confirmation_gate_dir() / "MANIFEST.json").is_file() else "NOT_RUN",
            "policy_status": "NO_POLICY_FROZEN",
            "confirmation_accessed": False,
        },
        "prospective_phase7": {
            "experiment_id": PHASE7_ID,
            "present": (prospective_phase7_dir() / "MANIFEST.json").is_file(),
            "status": "ARMED_WAITING_FOR_DATA" if (prospective_phase7_dir() / "MANIFEST.json").is_file() else "NOT_RUN",
            "policy_status": "NO_POLICY_FROZEN",
            "execution_enabled": False,
        },
        "combined_headline_forbidden": True,
        "note": "A and B are separate. Confirmation is the headline when present. Discovery is labeled DISCOVERY.",
    }


def handle_persistence_audit() -> dict[str, Any]:
    root = persistence_audit_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    stats = _optional_json(root / "statistics.json")
    report = root / "REPORT.md"
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "audit_id": AUDIT_ID,
        "page": "PERSISTENCE MECHANISM AUDIT",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "manifest": manifest,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "A": None if not stats else stats.get("A"),
        "B": None if not stats else stats.get("B"),
        "alignment": None if not stats else stats.get("alignment_verdict"),
        "interpretation": None if not stats else stats.get("interpretation"),
        "note": "DISCOVERY ONLY. POLICY UNFROZEN. CONFIRMATION UNTOUCHED. EXECUTION DISABLED.",
    }


def handle_persistence_phase2() -> dict[str, Any]:
    root = persistence_phase2_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    stats = _optional_json(root / "statistics.json")
    report = root / "REPORT.md"
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "audit_id": PHASE2_ID,
        "phase": "PHASE_2",
        "page": "PHASE 2 · PERSISTENCE MECHANISM",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "manifest": manifest,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "A": None if not stats else stats.get("A"),
        "B": None if not stats else stats.get("B"),
        "alignment": None if not stats else stats.get("alignment_verdict"),
        "interpretation": None if not stats else stats.get("interpretation"),
        "note": "DISCOVERY ONLY. MODEL FROZEN. POLICY UNFROZEN. CONFIRMATION UNTOUCHED. EXECUTION DISABLED.",
    }


def handle_downfall_phase3() -> dict[str, Any]:
    root = downfall_phase3_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    stats = _optional_json(root / "statistics.json")
    report = root / "REPORT.md"
    schema = _optional_json(root / "STATE_SCHEMA.json")
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "model_id": PHASE3_ID,
        "phase": "PHASE_3",
        "page": "PHASE 3 · DOWNFALL STATE MODEL",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "hazard_model_built": False,
        "phase_2_actionability_gate": "NOT_MET",
        "manifest": manifest,
        "schema": schema,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "A": None if not stats else stats.get("A"),
        "B": None if not stats else stats.get("B"),
        "alignment": None if not stats else stats.get("alignment_verdict"),
        "interpretation": None if not stats else stats.get("interpretation"),
        "note": "RESEARCH ONLY. MODEL FROZEN. POLICY UNFROZEN. CONFIRMATION UNTOUCHED. HAZARD MODEL NOT BUILT. EXECUTION DISABLED.",
    }


def handle_hazard_phase4() -> dict[str, Any]:
    root = hazard_phase4_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    stats = _optional_json(root / "statistics.json")
    report = root / "REPORT.md"
    schema = _optional_json(root / "HAZARD_SCHEMA.json")
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "model_id": PHASE4_ID,
        "phase": "PHASE_4",
        "page": "PHASE 4 · LOSS HAZARD / RECOVERY",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "phase_2_status": "FINALIZED",
        "phase_2_actionability": "NOT_MET",
        "phase_3_status": "COMPLETE",
        "phase_3_result": "MIXED",
        "manifest": manifest,
        "schema": schema,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "A": None if not stats else stats.get("A"),
        "B": None if not stats else stats.get("B"),
        "interpretation": None if not stats else stats.get("interpretation"),
        "note": "HAZARD MODEL RESEARCH ONLY. PHASE 2 FINALIZED. PHASE 3 COMPLETE. POLICY UNFROZEN. CONFIRMATION UNTOUCHED. EXECUTION DISABLED.",
    }


def handle_policy_phase5a() -> dict[str, Any]:
    root = policy_phase5_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    stats = _optional_json(root / "statistics.json")
    report = root / "REPORT.md"
    registry = _optional_json(root / "POLICY_CANDIDATES.json")
    decision = _optional_json(root / "POLICY_DECISION.json")
    freeze = _optional_json(root / "POLICY_FREEZE.json")
    finalized = _optional_json(root / "PHASE5_FINALIZED.json")
    closeout = root / "PHASE5B_CLOSEOUT.md"
    readiness = root / "FREEZE_READINESS.md"
    if freeze:
        policy_status = "FROZEN"
    elif finalized:
        policy_status = "NO_POLICY_FROZEN"
    else:
        policy_status = "UNFROZEN"
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "policy_object": PHASE5_ID,
        "phase": "PHASE_5A",
        "page": "PHASE 5A · DRE POLICY PREREGISTRATION",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": policy_status,
        "policy_selected": "NONE" if not freeze else freeze.get("human_selected_policy"),
        "policy_proposed": None if not stats else (stats.get("policy_proposed") or "NONE"),
        "human_selected_policy": None if not decision else decision.get("human_selected_policy"),
        "human_decision_status": None if not decision else decision.get("human_decision_status"),
        "freeze_evidence_status": None if not decision else decision.get("human_freeze_justified"),
        "freeze_status": "NOT_WRITTEN" if not freeze else "FROZEN",
        "policy_freeze_hash": None if not freeze else freeze.get("policy_freeze_hash"),
        "phase5_finalized": finalized,
        "phase5_finalized_status": None if not finalized else finalized.get("status"),
        "closeout_policy_status": None if not finalized else "NO_POLICY_FROZEN",
        "phase_6_status": "NOT STARTED" if not (confirmation_gate_dir() / "MANIFEST.json").is_file() else "BLOCKED_NO_FROZEN_POLICY",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "phase_2_status": "FINALIZED",
        "phase_2_actionability": "NOT_MET",
        "phase_3_status": "COMPLETE",
        "phase_4_status": "COMPLETE",
        "manifest": manifest,
        "candidates": None if not registry else registry.get("candidates"),
        "candidate_registry": registry,
        "statistics": stats,
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "phase5b_closeout_md": closeout.read_text(encoding="utf-8") if closeout.is_file() else None,
        "A": None if not stats else stats.get("A"),
        "B": None if not stats else stats.get("B"),
        "interpretation": None if not stats else stats.get("interpretation"),
        "policy_decision": decision,
        "policy_freeze": freeze,
        "freeze_readiness_md": readiness.read_text(encoding="utf-8") if readiness.is_file() else None,
        "note": "DISCOVERY ONLY. POLICY UNFROZEN. CONFIRMATION UNTOUCHED. SCENARIO ≠ FILL. EXECUTION DISABLED.",
        "phase5b_note": "PHASE5_FINALIZED. NO_POLICY_FROZEN. CONFIRMATION UNTOUCHED. EXECUTION DISABLED.",
    }


def handle_confirmation_gate() -> dict[str, Any]:
    root = confirmation_gate_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    report = root / "REPORT.md"
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "gate_id": PHASE6_ID,
        "phase": "PHASE_6",
        "page": "PHASE 6 · CONFIRMATION SEALED",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "NO_POLICY_FROZEN",
        "confirmation_accessed": False,
        "A_CONFIRMATION_STATUS": None if not manifest else manifest.get("A_CONFIRMATION_STATUS"),
        "B_CONFIRMATION_STATUS": None if not manifest else manifest.get("B_CONFIRMATION_STATUS"),
        "confirmation_A_expected_N": None if not manifest else manifest.get("confirmation_A_expected_N"),
        "confirmation_B_expected_N": None if not manifest else manifest.get("confirmation_B_expected_N"),
        "gate_status": None if not manifest else manifest.get("status"),
        "manifest": manifest,
        "cohort_audit": _optional_json(root / "confirmation_cohort_audit.json"),
        "access_audit": _optional_json(root / "confirmation_access_audit.json"),
        "phase5_policy_audit": _optional_json(root / "phase5_policy_audit.json"),
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "note": "CONFIRMATION SEALED. NO POLICY FROZEN. A 97 UNSPENT. B 70 UNSPENT. EXECUTION DISABLED.",
    }


def handle_prospective_phase7() -> dict[str, Any]:
    root = prospective_phase7_dir()
    manifest = _optional_json(root / "MANIFEST.json")
    lock = _optional_json(root / "PROSPECTIVE_LOCK.json")
    collection = _optional_json(root / "collection_status.json")
    report = root / "REPORT.md"
    return {
        "status": "OBSERVED" if manifest else "NOT_RUN",
        "experiment_id": PHASE7_ID,
        "phase": "PHASE_7",
        "page": "PHASE 7 · SHADOW RESEARCH",
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "policy_status": "NO_POLICY_FROZEN",
        "execution_enabled": False,
        "collection_status": None if not collection else collection.get("status"),
        "eligible_n": None if not collection else collection.get("eligible_n"),
        "completed_n": None if not collection else collection.get("completed_n"),
        "prospective_lock_hash": None if not lock else lock.get("prospective_lock_hash"),
        "page3_strategy_id": None if not lock else lock.get("page3_strategy_id"),
        "manifest": manifest,
        "lock": lock,
        "collection": collection,
        "integrity_audit": _optional_json(root / "integrity_audit.json"),
        "confirmation_preservation_audit": _optional_json(root / "confirmation_preservation_audit.json"),
        "report_md": report.read_text(encoding="utf-8") if report.is_file() else None,
        "note": "SHADOW RESEARCH. NO POLICY. NO EXECUTION. NO HISTORICAL BACKFILL. LOCKED. ARMED.",
    }


def handle_experiment(experiment_id: str) -> dict[str, Any]:
    raw = str(experiment_id or "").strip()
    if raw == AUDIT_ID:
        return handle_persistence_audit()
    if raw == PHASE2_ID:
        return handle_persistence_phase2()
    if raw == PHASE3_ID:
        return handle_downfall_phase3()
    if raw == PHASE4_ID:
        return handle_hazard_phase4()
    if raw == PHASE5_ID:
        return handle_policy_phase5a()
    if raw == PHASE6_ID:
        return handle_confirmation_gate()
    if raw == PHASE7_ID:
        return handle_prospective_phase7()
    experiment_id = assert_experiment_id(experiment_id)
    freeze = _optional_json(suite_freeze_path())
    confirmation = _stage_block(experiment_id, "CONFIRMATION")
    discovery = _stage_block(experiment_id, "DISCOVERY")
    return {
        "status": "OBSERVED",
        "suite_id": SUITE_ID,
        "experiment_id": experiment_id,
        "slice": SLICE_BY_EXPERIMENT[experiment_id],
        "n_lock": N_BY_EXPERIMENT[experiment_id],
        "live_feed": LIVE_FEED,
        "execution": EXECUTION,
        "submits": False,
        "fill_status": FILL_STATUS,
        "page3_n280_queried": False,
        "model_manifest": _optional_json(model_manifest_path()),
        "manifest": _optional_json(experiment_dir(experiment_id) / "MANIFEST.json"),
        "policy_freeze": freeze,
        "policy_status": None if freeze else "UNFROZEN",
        "confirmation_result": confirmation.get("result") or "NOT RUN",
        "headline": confirmation if confirmation["present"] else None,
        "confirmation": confirmation,
        "discovery": {**discovery, "headline": False, "label": "DISCOVERY"},
        "note": "Do not combine this member with the other experiment as a headline OOS result.",
    }
