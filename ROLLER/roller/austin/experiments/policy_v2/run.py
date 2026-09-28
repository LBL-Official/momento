"""Phase 5A runner. Discovery only. Writes candidates before economics. Does not freeze."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.hazard.io import read_csv
from roller.austin.experiments.ids import MEMBERS
from roller.austin.experiments.manifest import LOCKED_HASHES, resolve_git_commit, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.load import assert_discovery_only, load_suite_discovery
from roller.austin.experiments.persistence.util import write_csv
from roller.austin.experiments.policy_v2.audits import (
    candidate_registry_audit,
    cohort_hash_audit,
    confirmation_audit,
    hazard_schema_audit,
    leakage_audit,
    model_hash_audit,
    phase2_finalization_audit,
    phase3_finalization_audit,
    phase4_finalization_audit,
)
from roller.austin.experiments.policy_v2.candidates import candidate_registry, candidates
from roller.austin.experiments.policy_v2.economics import attach_t40, first_fire, score_events, summarize_candidate
from roller.austin.experiments.policy_v2.ids import (
    EV_DEFINITION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    HAZARD_SCHEMA_HASH,
    LOCKED_CONFIRMATION_HASH,
    LOCKED_DISCOVERY_HASH,
    PHASE,
    PHASE2_ID,
    PHASE3_ID,
    PHASE4_ID,
    PHASE5_ID,
    PHASE_NAME,
    POLICY_OBJECT,
    STATE_SCHEMA_HASH,
    SUITE_ID,
)
from roller.austin.experiments.policy_v2.report import interpret, render_report
from roller.austin.paths import downfall_phase3_dir, hazard_phase4_dir, persistence_phase2_dir, policy_phase5_dir, suite_freeze_path
from roller.austin.store import write_json

EVENT_FIELDS = [
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "candidate_id",
    "action",
    "reason",
    "timing_class",
    "core_state",
    "p_terminal_loss_H1",
    "p_recovery_t1_H1",
    "won",
    "t40_already",
    "price",
    "scenario_a_price",
    "scenario_b_price",
    "baseline_hold_pnl",
    "baseline_8040_pnl",
    "hypothetical_pnl_a",
    "hypothetical_pnl_b",
    "delta_vs_hold_b",
    "delta_vs_8040_b",
    "cents_saved",
    "cents_sacrificed",
    "winner_abandoned",
    "loss_avoided",
    "adverse_cents_remaining",
    "minutes_to_worst_price",
    "scenario_label",
]
ECON_FIELDS = [
    "source_experiment_id",
    "candidate_id",
    "n_trades",
    "intervention_n",
    "intervention_rate",
    "losses_intervened",
    "winners_intervened",
    "losses_avoided",
    "winners_abandoned",
    "cents_saved",
    "winner_cents_sacrificed",
    "dre_value_added",
    "scenario_b_ev",
    "delta_vs_hold",
    "delta_vs_hold_ci_lo",
    "delta_vs_hold_ci_hi",
    "delta_vs_8040",
    "max_drawdown",
    "p10",
    "worst_trade",
    "median_trigger_price",
    "median_adverse_cents_remaining",
    "median_minutes_to_worst",
    "n_too_late",
    "execution_cost_cents",
    "execution_cost_assumption",
    "scenario_label",
]


def stage_policy() -> dict[str, Any]:
    assert_discovery_only()
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 5A refuses POLICY_FREEZE.json")
    phase4 = phase4_finalization_audit()
    phase2 = phase2_finalization_audit()
    phase3 = phase3_finalization_audit()
    model_lock = verify_model_manifest()
    suite = load_suite_discovery()
    confirmation = confirmation_audit()
    model_audit = model_hash_audit()
    cohort = cohort_hash_audit(suite)
    schema_audit = hazard_schema_audit()
    if cohort["members"][EXPERIMENT_A]["discovery_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A discovery hash drifted")
    if cohort["members"][EXPERIMENT_B]["discovery_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B discovery hash drifted")
    if cohort["members"][EXPERIMENT_A]["confirmation_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A confirmation identity hash drifted")
    if cohort["members"][EXPERIMENT_B]["confirmation_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B confirmation identity hash drifted")
    source = hazard_phase4_dir()
    entries = attach_t40(read_csv(source / "hazard_state_entries.csv"), suite)
    timing_rows = read_csv(source / "hazard_timing.csv")
    timing_by_key = {
        (str(r.get("source_experiment_id")), str(r.get("trade_id")), str(r.get("core_state"))): r for r in timing_rows
    }
    root = policy_phase5_dir()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 5A must not write or consume POLICY_FREEZE.json")
    registry = candidate_registry()
    family = candidates()
    if len(family) > 4:
        raise AustinError("LOCK_MISMATCH", "candidate count exceeds 4")
    write_json(root / "POLICY_CANDIDATES.json", registry)
    hashed = sha256_file(root / "POLICY_CANDIDATES.json")
    if hashed != sha256_file(root / "POLICY_CANDIDATES.json"):
        raise AustinError("LOCK_MISMATCH", "candidate registry hash unstable at write")
    leak = leakage_audit(entries, family)
    scored: list[dict[str, Any]] = []
    firsts: list[dict[str, Any]] = []
    econ_a: list[dict[str, Any]] = []
    econ_b: list[dict[str, Any]] = []
    for cand in family:
        events = first_fire(entries, cand)
        a_events = [e for e in events if e["source_experiment_id"] == EXPERIMENT_A]
        b_events = [e for e in events if e["source_experiment_id"] == EXPERIMENT_B]
        a_scored = score_events(a_events, suite[EXPERIMENT_A]["trades"], suite[EXPERIMENT_A]["queries"], timing_by_key)
        b_scored = score_events(b_events, suite[EXPERIMENT_B]["trades"], suite[EXPERIMENT_B]["queries"], timing_by_key)
        scored.extend(a_scored)
        scored.extend(b_scored)
        firsts.extend([r for r in a_scored + b_scored if r["action"] == "INTERVENE"])
        econ_a.append(summarize_candidate(a_scored, EXPERIMENT_A, cand["candidate_id"]))
        econ_b.append(summarize_candidate(b_scored, EXPERIMENT_B, cand["candidate_id"]))
    after = sha256_file(root / "POLICY_CANDIDATES.json")
    if after != hashed:
        raise AustinError("LOCK_MISMATCH", "POLICY_CANDIDATES.json changed after economics")
    reg_audit = candidate_registry_audit(hashed, after, len(family))
    interp = interpret(econ_a, econ_b, leakage=leak, phase4=phase4)
    git = resolve_git_commit()
    manifest = {
        "phase": PHASE,
        "phase_name": PHASE_NAME,
        "policy_object": POLICY_OBJECT,
        "source_phase_4": PHASE4_ID,
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "source_phase_3": PHASE3_ID,
        "state_schema_hash": STATE_SCHEMA_HASH,
        "source_phase_2": PHASE2_ID,
        "Austin_model": "austin_v2",
        "Austin_manifest_hash": model_lock["model_manifest_hash"],
        "candidate_registry_hash": hashed,
        "bootstrap_seed": 80,
        "bootstrap_B": 1000,
        "cluster_unit": "internal_game_id",
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "policy_proposed": interp["proposed_policy"],
        "execution_enabled": False,
        "submits": False,
        "A_discovery_hash": suite[EXPERIMENT_A]["discovery_hash"],
        "A_confirmation_hash": suite[EXPERIMENT_A]["confirmation_identity"]["cohort_hash"],
        "B_discovery_hash": suite[EXPERIMENT_B]["discovery_hash"],
        "B_confirmation_hash": suite[EXPERIMENT_B]["confirmation_identity"]["cohort_hash"],
        "feature_schema_hash": LOCKED_HASHES["registry.yaml"],
        "EV_definition": EV_DEFINITION,
        "source_suite": SUITE_ID,
        "git_commit": git["git_commit"],
        "git_commit_reason": git["git_commit_reason"],
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "live_feed": "UNAVAILABLE",
        "execution": "DISABLED",
        "phase_4_classification": phase4["phase_5_classification"],
        "phase_4_decision": phase4["phase_5_decision"],
    }
    statistics = {
        "policy_object": PHASE5_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "policy_proposed": interp["proposed_policy"],
        "confirmation_accessed": False,
        "A": {"experiment_id": EXPERIMENT_A, "economics": econ_a},
        "B": {"experiment_id": EXPERIMENT_B, "economics": econ_b},
        "interpretation": interp,
    }
    write_json(root / "MANIFEST.json", manifest)
    write_json(root / "statistics.json", statistics)
    write_json(root / "model_lock_audit.json", model_audit)
    write_json(root / "phase2_finalization_audit.json", phase2)
    write_json(root / "phase3_finalization_audit.json", phase3)
    write_json(root / "phase4_finalization_audit.json", phase4)
    write_json(root / "hazard_schema_audit.json", schema_audit)
    write_json(root / "cohort_hash_audit.json", cohort)
    write_json(root / "leakage_audit.json", leak)
    write_json(root / "confirmation_protection_audit.json", confirmation)
    write_json(root / "candidate_registry_audit.json", reg_audit)
    write_csv(root / "candidate_discovery_events.csv", scored, EVENT_FIELDS)
    write_csv(root / "first_intervention_events.csv", firsts, EVENT_FIELDS)
    write_csv(root / "candidate_economics_A.csv", econ_a, ECON_FIELDS)
    write_csv(root / "candidate_economics_B.csv", econ_b, ECON_FIELDS)
    write_csv(root / "candidate_comparison.csv", econ_a + econ_b, ECON_FIELDS)
    write_csv(
        root / "timing_analysis.csv",
        [
            {
                "source_experiment_id": r["source_experiment_id"],
                "candidate_id": r["candidate_id"],
                "median_trigger_price": r["median_trigger_price"],
                "median_adverse_cents_remaining": r["median_adverse_cents_remaining"],
                "median_minutes_to_worst": r["median_minutes_to_worst"],
                "n_too_late": r["n_too_late"],
            }
            for r in econ_a + econ_b
        ],
        [
            "source_experiment_id",
            "candidate_id",
            "median_trigger_price",
            "median_adverse_cents_remaining",
            "median_minutes_to_worst",
            "n_too_late",
        ],
    )
    write_csv(
        root / "winner_sacrifice_analysis.csv",
        [{"source_experiment_id": r["source_experiment_id"], "candidate_id": r["candidate_id"], "winners_abandoned": r["winners_abandoned"], "winner_cents_sacrificed": r["winner_cents_sacrificed"]} for r in econ_a + econ_b],
        ["source_experiment_id", "candidate_id", "winners_abandoned", "winner_cents_sacrificed"],
    )
    write_csv(
        root / "loss_avoidance_analysis.csv",
        [{"source_experiment_id": r["source_experiment_id"], "candidate_id": r["candidate_id"], "losses_avoided": r["losses_avoided"], "cents_saved": r["cents_saved"]} for r in econ_a + econ_b],
        ["source_experiment_id", "candidate_id", "losses_avoided", "cents_saved"],
    )
    write_csv(
        root / "dre_value_added.csv",
        [{"source_experiment_id": r["source_experiment_id"], "candidate_id": r["candidate_id"], "dre_value_added": r["dre_value_added"], "cents_saved": r["cents_saved"], "winner_cents_sacrificed": r["winner_cents_sacrificed"], "execution_cost_cents": r["execution_cost_cents"]} for r in econ_a + econ_b],
        ["source_experiment_id", "candidate_id", "dre_value_added", "cents_saved", "winner_cents_sacrificed", "execution_cost_cents"],
    )
    report = render_report(
        {
            "econ_a": econ_a,
            "econ_b": econ_b,
            "interpretation": interp,
            "registry": registry,
            "hazard_schema_hash": HAZARD_SCHEMA_HASH,
            "candidate_registry_hash": hashed,
            "audits": {"leakage": leak},
        }
    )
    (root / "REPORT.md").write_text(report + "\n", encoding="utf-8")
    from roller.austin.experiments.policy_v2.ids import PHASE2_REPORT_SHA256, PHASE3_REPORT_SHA256

    if sha256_file(persistence_phase2_dir() / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT changed during Phase 5A")
    if sha256_file(downfall_phase3_dir() / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT changed during Phase 5A")
    if (root / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 5A wrote POLICY_FREEZE.json")
    return {
        "policy_object": PHASE5_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "policy_proposed": interp["proposed_policy"],
        "human_freeze_justified": interp["human_freeze_justified"],
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "execution": "DISABLED",
        "submits": False,
        "members": MEMBERS,
        "candidate_registry_hash": hashed,
    }
