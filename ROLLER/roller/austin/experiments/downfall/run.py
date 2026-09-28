"""Discovery-only Phase 3 runner. Does not write Phase 2. Does not freeze. Does not confirm."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.archetypes import (
    ARCH_ECON_FIELDS,
    ARCHETYPE_FIELDS,
    DEPTH_FIELDS,
    archetype_economics,
    depth_analysis,
    trade_archetype_row,
)
from roller.austin.experiments.downfall.audits import (
    cohort_hash_audit,
    confirmation_protection_audit,
    determinism_audit,
    leakage_audit,
    model_hash_audit,
    phase2_unchanged_audit,
    warning_audit,
)
from roller.austin.experiments.downfall.economics import (
    CONTRAST_FIELDS,
    ECON_FIELDS,
    POP_FIELDS,
    flatten_contrasts,
    ordering_status,
    state_contrasts,
    state_economics,
    state_populations,
)
from roller.austin.experiments.downfall.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    EV_DEFINITION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    LOCKED_CONFIRMATION_HASH,
    LOCKED_DISCOVERY_HASH,
    MODEL_ID,
    OBSERVATION_SCHEDULE,
    PHASE,
    PHASE2_ID,
    PHASE3_ID,
    PHASE_NAME,
    STATE_SCHEMA_VERSION,
    SUITE_ID,
    WATCH_NEGATIVE,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
)
from roller.austin.experiments.downfall.outcomes import ENTRY_FIELDS, attach_entry_outcomes
from roller.austin.experiments.downfall.overlays import CI_FIELDS, SUPPORT_FIELDS, ci_overlay_analysis, flatten_ci, support_overlay_analysis
from roller.austin.experiments.downfall.report import interpret_downfall, render_report
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.downfall.timeline import TIMELINE_FIELDS, build_timeline, first_entries
from roller.austin.experiments.downfall.transitions import (
    BRANCH_FIELDS,
    COUNT_FIELDS,
    RATE_FIELDS,
    TENTRY_FIELDS,
    TECON_FIELDS,
    TRANSITION_FIELDS,
    adjacent_transitions,
    first_transition_entries,
    flatten_branch,
    transition_branch_contrasts,
    transition_economics,
    transition_matrix,
)
from roller.austin.experiments.downfall.windows import (
    TIMING_FIELDS,
    WINDOW_FIELDS,
    remaining_damage_summary,
    timing_rows,
    timing_summary,
    window_rows,
)
from roller.austin.experiments.ids import MEMBERS
from roller.austin.experiments.manifest import LOCKED_HASHES, resolve_git_commit, verify_model_manifest
from roller.austin.experiments.persistence.load import assert_discovery_only, load_suite_discovery
from roller.austin.experiments.persistence.util import write_csv
from roller.austin.experiments.warehouse_cache import load_trade_warehouse
from roller.austin.paths import downfall_phase3_dir, suite_freeze_path
from roller.austin.store import write_json


def _timing_gate(remaining: list[dict[str, Any]]) -> str:
    deeper = [r for r in remaining if r["core_state"] in {PERSISTENCE_2, PERSISTENCE_3PLUS, WATCH_NEGATIVE}]
    if not deeper or all(not r.get("N_trades") for r in deeper):
        return "INSUFFICIENT_SAMPLE"
    adverse = [r.get("mean_adverse_cents_remaining") for r in deeper if r.get("mean_adverse_cents_remaining") is not None]
    minutes = [r.get("mean_minutes_to_worst_price") for r in deeper if r.get("mean_minutes_to_worst_price") is not None]
    if not adverse:
        return "INSUFFICIENT_SAMPLE"
    positive = [x for x in adverse if x > 0]
    late = [x for x in minutes if x is not None and x <= 0]
    if positive and not late and all(x > 0 for x in adverse):
        return "SUPPORTED"
    if positive:
        return "MIXED"
    return "NOT_SUPPORTED"


def _member_payload(experiment_id: str, member: dict[str, Any]) -> dict[str, Any]:
    trades = list(member["trades"])
    queries = member["queries"]
    timeline: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    archetypes: list[dict[str, Any]] = []
    for trade in trades:
        rows = build_timeline(experiment_id, trade, queries)
        timeline.extend(rows)
        first = first_entries(rows)
        attached = [attach_entry_outcomes(row, rows, trade) for row in first]
        entries.extend(attached)
        edges = adjacent_transitions(rows)
        transitions.extend(edges)
        archetypes.append(trade_archetype_row(trade, rows, attached))
    by_trade_state = {(e["trade_id"], e["core_state"]): e for e in entries}
    t_entries = first_transition_entries(transitions, by_trade_state)
    counts, rates = transition_matrix(transitions)
    remaining = remaining_damage_summary(entries)
    return {
        "experiment_id": experiment_id,
        "n_discovery": len(trades),
        "timeline": timeline,
        "entries": entries,
        "transitions": transitions,
        "transition_entries": t_entries,
        "transition_counts": counts,
        "transition_rates": rates,
        "transition_economics": transition_economics(t_entries),
        "transition_branches": transition_branch_contrasts(t_entries),
        "populations": state_populations(timeline, entries, len(trades)),
        "economics": state_economics(entries),
        "contrasts": state_contrasts(entries),
        "ordering": ordering_status(state_economics(entries)),
        "archetypes": archetypes,
        "archetype_economics": archetype_economics(archetypes),
        "depth": depth_analysis(entries),
        "ci_overlay": ci_overlay_analysis(entries),
        "support_overlay": support_overlay_analysis(entries),
        "windows": window_rows(entries),
        "timing": timing_rows(entries),
        "remaining_damage": remaining,
        "timing_summary": timing_summary(entries),
        "timing_gate": _timing_gate(remaining),
    }


def _stats_member(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "n_discovery": payload["n_discovery"],
        "populations": payload["populations"],
        "economics": payload["economics"],
        "contrasts": payload["contrasts"],
        "ordering": payload["ordering"],
        "transition_counts": payload["transition_counts"],
        "transition_rates": payload["transition_rates"],
        "transition_economics": payload["transition_economics"],
        "transition_branches": payload["transition_branches"],
        "archetype_economics": payload["archetype_economics"],
        "depth": payload["depth"],
        "ci_overlay": payload["ci_overlay"],
        "support_overlay": payload["support_overlay"],
        "remaining_damage": payload["remaining_damage"],
        "timing_summary": payload["timing_summary"],
        "timing_gate": payload["timing_gate"],
    }


def _with_source(experiment_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item.setdefault("source_experiment_id", experiment_id)
        out.append(item)
    return out


def stage_downfall() -> dict[str, Any]:
    assert_discovery_only()
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "downfall refuses POLICY_FREEZE.json")
    model_lock = verify_model_manifest()
    phase2 = phase2_unchanged_audit()
    suite = load_suite_discovery()
    warning = warning_audit(suite)
    trades = list(suite[EXPERIMENT_A]["trades"]) + list(suite[EXPERIMENT_B]["trades"])
    warehouse = load_trade_warehouse(trades)
    built = {
        EXPERIMENT_A: _member_payload(EXPERIMENT_A, suite[EXPERIMENT_A]),
        EXPERIMENT_B: _member_payload(EXPERIMENT_B, suite[EXPERIMENT_B]),
    }
    a = built[EXPERIMENT_A]
    b = built[EXPERIMENT_B]
    git = resolve_git_commit()
    schema = state_schema()
    hashed = schema_hash(schema)
    audits = {
        "phase2": phase2,
        "model": model_hash_audit(),
        "cohort": cohort_hash_audit(suite),
        "confirmation": confirmation_protection_audit(),
        "warning": warning,
        "determinism": determinism_audit(suite),
        "leakage": leakage_audit(suite, warehouse=warehouse),
    }
    alignment = phase2["alignment"]
    stats_a = _stats_member(a)
    stats_b = _stats_member(b)
    interp = interpret_downfall(
        stats_a,
        stats_b,
        determinism=audits["determinism"],
        leakage=audits["leakage"],
        alignment=alignment,
    )
    run_ts = datetime.now(timezone.utc).isoformat()
    manifest = {
        "phase": PHASE,
        "phase_name": PHASE_NAME,
        "model_id": MODEL_ID,
        "source_phase_2": PHASE2_ID,
        "source_suite": SUITE_ID,
        "source_experiment_A": EXPERIMENT_A,
        "source_experiment_B": EXPERIMENT_B,
        "model_version": "austin_v2",
        "dataset_version": "choosin_nba_2q3q_604",
        "model_manifest_hash": model_lock["model_manifest_hash"],
        "feature_schema_hash": LOCKED_HASHES["registry.yaml"],
        "pca_version": "austin_pca_v1",
        "K": 25,
        "distance_metric": "euclidean_pca",
        "EV_definition": EV_DEFINITION,
        "A_discovery_cohort_hash": suite[EXPERIMENT_A]["discovery_hash"],
        "A_confirmation_cohort_hash": suite[EXPERIMENT_A]["confirmation_identity"]["cohort_hash"],
        "B_discovery_cohort_hash": suite[EXPERIMENT_B]["discovery_hash"],
        "B_confirmation_cohort_hash": suite[EXPERIMENT_B]["confirmation_identity"]["cohort_hash"],
        "observation_schedule": OBSERVATION_SCHEDULE,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "state_schema_hash": hashed,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_B": BOOTSTRAP_B,
        "cluster_unit": "internal_game_id",
        "git_commit": git["git_commit"],
        "git_commit_reason": git["git_commit_reason"],
        "phase_2_actionability_gate": "NOT_MET",
        "phase_3_authorization": "EXPLICIT_RESEARCHER_AUTHORIZATION",
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "hazard_model_built": False,
        "execution_enabled": False,
        "submits": False,
        "run_timestamp": run_ts,
        "live_feed": "UNAVAILABLE",
        "execution": "DISABLED",
    }
    if manifest["A_discovery_cohort_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A discovery hash drifted")
    if manifest["B_discovery_cohort_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B discovery hash drifted")
    if manifest["A_confirmation_cohort_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A confirmation identity hash drifted")
    if manifest["B_confirmation_cohort_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B confirmation identity hash drifted")
    statistics = {
        "model_id": PHASE3_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "hazard_model_built": False,
        "A": stats_a,
        "B": stats_b,
        "alignment_verdict": alignment,
        "interpretation": interp,
    }
    root = downfall_phase3_dir()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "STATE_SCHEMA.json", schema)
    write_json(root / "MANIFEST.json", manifest)
    write_json(root / "statistics.json", statistics)
    write_json(root / "model_hash_audit.json", audits["model"])
    write_json(root / "cohort_hash_audit.json", audits["cohort"])
    write_json(root / "leakage_audit.json", audits["leakage"])
    write_json(root / "confirmation_protection_audit.json", audits["confirmation"])
    write_json(root / "state_determinism_audit.json", audits["determinism"])
    write_csv(root / "state_timeline.csv", a["timeline"] + b["timeline"], TIMELINE_FIELDS)
    write_csv(root / "state_entries.csv", a["entries"] + b["entries"], ENTRY_FIELDS)
    write_csv(
        root / "state_summary.csv",
        _with_source(EXPERIMENT_A, a["populations"]) + _with_source(EXPERIMENT_B, b["populations"]),
        POP_FIELDS,
    )
    write_csv(
        root / "state_economics.csv",
        _with_source(EXPERIMENT_A, a["economics"]) + _with_source(EXPERIMENT_B, b["economics"]),
        ECON_FIELDS,
    )
    write_csv(
        root / "state_contrasts.csv",
        flatten_contrasts(EXPERIMENT_A, a["contrasts"]) + flatten_contrasts(EXPERIMENT_B, b["contrasts"]),
        CONTRAST_FIELDS,
    )
    write_csv(root / "state_transitions.csv", a["transitions"] + b["transitions"], TRANSITION_FIELDS)
    write_csv(
        root / "transition_counts.csv",
        _with_source(EXPERIMENT_A, a["transition_counts"]) + _with_source(EXPERIMENT_B, b["transition_counts"]),
        COUNT_FIELDS,
    )
    write_csv(
        root / "transition_rates.csv",
        _with_source(EXPERIMENT_A, a["transition_rates"]) + _with_source(EXPERIMENT_B, b["transition_rates"]),
        RATE_FIELDS,
    )
    write_csv(root / "transition_entries.csv", a["transition_entries"] + b["transition_entries"], TENTRY_FIELDS)
    write_csv(
        root / "transition_economics.csv",
        _with_source(EXPERIMENT_A, a["transition_economics"]) + _with_source(EXPERIMENT_B, b["transition_economics"]),
        TECON_FIELDS,
    )
    write_csv(root / "path_archetypes.csv", a["archetypes"] + b["archetypes"], ARCHETYPE_FIELDS)
    write_csv(
        root / "archetype_economics.csv",
        _with_source(EXPERIMENT_A, a["archetype_economics"]) + _with_source(EXPERIMENT_B, b["archetype_economics"]),
        ARCH_ECON_FIELDS,
    )
    write_csv(
        root / "state_depth_analysis.csv",
        _with_source(EXPERIMENT_A, a["depth"]) + _with_source(EXPERIMENT_B, b["depth"]),
        DEPTH_FIELDS,
    )
    write_csv(
        root / "ci_overlay_analysis.csv",
        flatten_ci(EXPERIMENT_A, a["ci_overlay"]) + flatten_ci(EXPERIMENT_B, b["ci_overlay"]),
        CI_FIELDS,
    )
    write_csv(
        root / "support_overlay_analysis.csv",
        _with_source(EXPERIMENT_A, a["support_overlay"]) + _with_source(EXPERIMENT_B, b["support_overlay"]),
        SUPPORT_FIELDS,
    )
    write_csv(root / "state_intervention_window.csv", a["windows"] + b["windows"], WINDOW_FIELDS)
    write_csv(root / "state_timing.csv", a["timing"] + b["timing"], TIMING_FIELDS)
    report = render_report(
        {
            "manifest": manifest,
            "A": {**a, **stats_a},
            "B": {**b, **stats_b},
            "interpretation": interp,
            "alignment_verdict": alignment,
            "audits": audits,
        }
    )
    (root / "REPORT.md").write_text(report + "\n", encoding="utf-8")
    return {
        "model_id": PHASE3_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "hazard_model_built": False,
        "phase_2_actionability_gate": "NOT_MET",
        "phase_4_decision": interp["phase_4_decision"],
        "interpretation": interp,
        "members": MEMBERS,
        "execution": "DISABLED",
        "submits": False,
        "n_timeline_rows": len(a["timeline"]) + len(b["timeline"]),
        "n_entries": len(a["entries"]) + len(b["entries"]),
    }
