"""Discovery-only persistence runner. Writes AUDIT_V1 and Phase 2. No query_match. No freeze."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, MEMBERS
from roller.austin.experiments.manifest import LOCKED_HASHES, resolve_git_commit, verify_model_manifest
from roller.austin.experiments.persistence.alignment import (
    ALIGNMENT_FIELDS,
    EXAMPLE_FIELDS,
    alignment_verdict,
    classify_trade,
    example_rows,
)
from roller.austin.experiments.persistence.audits import (
    cohort_hash_audit,
    confirmation_protection_audit,
    leakage_audit,
    model_hash_audit,
)
from roller.austin.experiments.persistence.contrasts import (
    PIT_COMPARE_FIELDS,
    TRAJ_COMPARE_FIELDS,
    economics_block,
    flatten_pit,
    pit_feature_comparison,
    trajectory_feature_comparison,
)
from roller.austin.experiments.persistence.events import EVENT_FIELDS, build_first_negative_events
from roller.austin.experiments.persistence.ids import (
    AUDIT_ID,
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    EV_DEFINITION,
    OBSERVATION_SCHEDULE,
    PHASE,
    PHASE2_ID,
    PHASE_NAME,
    SUITE_ID,
)
from roller.austin.experiments.persistence.landmarks import LANDMARK_FIELDS, flatten_landmarks, landmark_tables
from roller.austin.experiments.persistence.load import assert_discovery_only, load_suite_discovery
from roller.austin.experiments.persistence.phase2 import (
    DOWNFALL_FIELDS,
    RECOVERY_FIELDS,
    SUPPORT_FIELDS,
    WINDOW_FIELDS,
    attach_dynamics,
    downfall_row,
    downfall_summary,
    dynamics_summary,
    intervention_rows,
    recovery_row,
    recovery_summary,
    support_row,
    support_summary,
    warning_timing_summary,
    window_summary,
)
from roller.austin.experiments.persistence.report import interpret_persistence, render_report
from roller.austin.experiments.persistence.report_phase2 import interpret_phase2, render_phase2_report
from roller.austin.experiments.persistence.trajectories import (
    DURATION_FIELDS,
    TRAJECTORY_FIELDS,
    build_trajectory,
    persistence_duration,
)
from roller.austin.experiments.persistence.util import write_csv
from roller.austin.experiments.persistence.warning import WARNING_FIELDS, preserved_warning, warning_persistence_rows
from roller.austin.experiments.warehouse_cache import load_trade_warehouse
from roller.austin.paths import persistence_audit_dir, persistence_phase2_dir, suite_freeze_path
from roller.austin.store import load_pca_model, write_json


def _member_payload(
    experiment_id: str,
    member: dict[str, Any],
    *,
    warehouse: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    events = build_first_negative_events(
        experiment_id,
        member["trades"],
        member["queries"],
        warehouse=warehouse,
        model=model,
    )
    trajectories: list[dict[str, Any]] = []
    durations: list[dict[str, Any]] = []
    recoveries: list[dict[str, Any]] = []
    downfalls: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    supports: list[dict[str, Any]] = []
    for event in events:
        traj = build_trajectory(event)
        attach_dynamics(event, traj)
        trajectories.extend(traj)
        durations.append(persistence_duration(event, traj))
        recoveries.append(recovery_row(event))
        downfalls.append(downfall_row(event))
        windows.extend(intervention_rows(event))
        supports.append(support_row(event))
    warning_timing = warning_persistence_rows(events)
    landmark_payload = landmark_tables(events)[0]
    return {
        "events": events,
        "trajectories": trajectories,
        "durations": durations,
        "recoveries": recoveries,
        "downfalls": downfalls,
        "windows": windows,
        "supports": supports,
        "landmarks": flatten_landmarks(experiment_id, events),
        "availability": landmark_payload["availability"],
        "economics": economics_block(events),
        "pit_comparison": pit_feature_comparison(events),
        "t1_comparison": trajectory_feature_comparison(events, "t1"),
        "t2_comparison": trajectory_feature_comparison(events, "t2"),
        "t3_comparison": trajectory_feature_comparison(events, "t3"),
        "dynamics": dynamics_summary(events),
        "recovery": recovery_summary(events),
        "downfall": downfall_summary(events),
        "window": window_summary(windows),
        "support": support_summary(events),
        "warning_timing": warning_timing,
        "warning_timing_summary": warning_timing_summary(warning_timing),
        "warning_preserved": preserved_warning(member["trades"], member["queries"]),
    }


def _stats_member(payload: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "economics": payload["economics"],
        "pit_comparison": payload["pit_comparison"],
        "t1_comparison": payload["t1_comparison"],
        "t2_comparison": payload["t2_comparison"],
        "t3_comparison": payload["t3_comparison"],
        "landmarks": payload["landmarks"],
        "availability": payload["availability"],
        "dynamics": payload["dynamics"],
        "recovery": payload["recovery"],
        "downfall": payload["downfall"],
        "window": payload["window"],
        "support": payload["support"],
        "warning_preserved": payload["warning_preserved"],
        "warning_timing_summary": payload["warning_timing_summary"],
    }


def _write_shared_tables(root: Path, a: dict[str, Any], b: dict[str, Any], *, b_align, b_examples) -> None:
    write_csv(root / "first_negative_events.csv", a["events"] + b["events"], EVENT_FIELDS)
    write_csv(root / "negative_ev_trajectories.csv", a["trajectories"] + b["trajectories"], TRAJECTORY_FIELDS)
    write_csv(root / "persistence_summary.csv", a["durations"] + b["durations"], DURATION_FIELDS)
    write_csv(root / "persistence_landmarks.csv", a["landmarks"] + b["landmarks"], LANDMARK_FIELDS)
    write_csv(
        root / "pit_feature_comparison.csv",
        flatten_pit(EXPERIMENT_A, a["pit_comparison"]) + flatten_pit(EXPERIMENT_B, b["pit_comparison"]),
        PIT_COMPARE_FIELDS,
    )
    write_csv(
        root / "trajectory_feature_comparison.csv",
        flatten_pit(EXPERIMENT_A, a["t1_comparison"])
        + flatten_pit(EXPERIMENT_A, a["t2_comparison"])
        + flatten_pit(EXPERIMENT_A, a["t3_comparison"])
        + flatten_pit(EXPERIMENT_B, b["t1_comparison"])
        + flatten_pit(EXPERIMENT_B, b["t2_comparison"])
        + flatten_pit(EXPERIMENT_B, b["t3_comparison"]),
        TRAJ_COMPARE_FIELDS,
    )
    write_csv(root / "warning_persistence_timing.csv", a["warning_timing"] + b["warning_timing"], WARNING_FIELDS)
    write_csv(root / "h2_1_alignment_audit.csv", b_align, ALIGNMENT_FIELDS)
    write_csv(root / "h2_1_alignment_examples.csv", b_examples, EXAMPLE_FIELDS)


def _write_phase2_tables(root: Path, a: dict[str, Any], b: dict[str, Any]) -> None:
    write_csv(root / "recovery_analysis.csv", a["recoveries"] + b["recoveries"], RECOVERY_FIELDS)
    write_csv(root / "downfall_analysis.csv", a["downfalls"] + b["downfalls"], DOWNFALL_FIELDS)
    write_csv(root / "intervention_window_analysis.csv", a["windows"] + b["windows"], WINDOW_FIELDS)
    write_csv(root / "support_analysis.csv", a["supports"] + b["supports"], SUPPORT_FIELDS)


def _guard_report(report: str) -> str:
    lowered = report.lower()
    if "holy grail" in lowered or "austin works" in lowered or "live ready" in lowered or "production ready" in lowered:
        raise AustinError("LOCK_MISMATCH", "persistence report used forbidden language")
    return report


def _add_phase1_pointer() -> None:
    from roller.austin.paths import experiment_dir

    pointer = (
        "\n\n## Phase 2 research object\n\n"
        "Discovery-only persistence mechanism continues at "
        "`research/austin/experiments/AUSTIN_PERSISTENCE_MECHANISM_V1/`.\n"
        "This file remains the Phase 1 discovery interpretation. "
        "Confirmation remains NOT RUN. Policy remains UNFROZEN.\n"
    )
    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        path = experiment_dir(eid) / "INTERPRETATION.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "AUSTIN_PERSISTENCE_MECHANISM_V1" in text:
            continue
        path.write_text(text.rstrip() + pointer, encoding="utf-8")


def stage_persist() -> dict[str, Any]:
    assert_discovery_only()
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "persist refuses POLICY_FREEZE.json")
    model_lock = verify_model_manifest()
    pca = load_pca_model()
    suite = load_suite_discovery()
    trades = list(suite[EXPERIMENT_A]["trades"]) + list(suite[EXPERIMENT_B]["trades"])
    warehouse = load_trade_warehouse(trades)
    built = {
        EXPERIMENT_A: _member_payload(EXPERIMENT_A, suite[EXPERIMENT_A], warehouse=warehouse, model=pca),
        EXPERIMENT_B: _member_payload(EXPERIMENT_B, suite[EXPERIMENT_B], warehouse=warehouse, model=pca),
    }
    a = built[EXPERIMENT_A]
    b = built[EXPERIMENT_B]
    git = resolve_git_commit()
    audits = {
        "model": model_hash_audit(),
        "cohort": cohort_hash_audit(suite),
        "confirmation": confirmation_protection_audit(),
        "leakage": leakage_audit(a["events"] + b["events"], warehouse=warehouse),
    }
    b_align = []
    b_examples = []
    for trade in sorted(
        suite[EXPERIMENT_B]["trades"],
        key=lambda t: (str(t.get("game_date") or ""), str(t.get("entry_timestamp") or ""), str(t.get("trade_id") or "")),
    ):
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        b_align.append(
            classify_trade(
                trade,
                suite[EXPERIMENT_B]["queries"],
                bars=warehouse.get("bars", {}).get(ticker, []),
                pbp=warehouse.get("pbp", {}).get(gid, []),
            )
        )
    for trade in sorted(
        suite[EXPERIMENT_B]["trades"],
        key=lambda t: (str(t.get("game_date") or ""), str(t.get("entry_timestamp") or ""), str(t.get("trade_id") or "")),
    )[:10]:
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        b_examples.append(
            example_rows(
                trade,
                suite[EXPERIMENT_B]["queries"],
                bars=warehouse.get("bars", {}).get(ticker, []),
                pbp=warehouse.get("pbp", {}).get(gid, []),
            )
        )
    verdict = alignment_verdict(b_align)
    stats_a = _stats_member(a, EXPERIMENT_A)
    stats_b = _stats_member(b, EXPERIMENT_B)
    audit_interp = interpret_persistence(stats_a, stats_b)
    phase2_interp = interpret_phase2(stats_a, stats_b, alignment=verdict)
    pooled = {
        "n_first_negative": len(a["events"]) + len(b["events"]),
        "label": "POOLED DESCRIPTIVE — NOT CONFIRMATION",
    }
    run_ts = datetime.now(timezone.utc).isoformat()
    audit_manifest = {
        "audit_id": AUDIT_ID,
        "phase2_research_object": PHASE2_ID,
        "source_suite": SUITE_ID,
        "source_experiment_A": EXPERIMENT_A,
        "source_experiment_B": EXPERIMENT_B,
        "model_manifest_hash": model_lock["model_manifest_hash"],
        "A_discovery_cohort_hash": suite[EXPERIMENT_A]["discovery_hash"],
        "A_confirmation_cohort_hash": suite[EXPERIMENT_A]["confirmation_identity"]["cohort_hash"],
        "B_discovery_cohort_hash": suite[EXPERIMENT_B]["discovery_hash"],
        "B_confirmation_cohort_hash": suite[EXPERIMENT_B]["confirmation_identity"]["cohort_hash"],
        "model_version": "austin_v2",
        "feature_schema_version": "austin_features_v1",
        "pca_version": "austin_pca_v1",
        "K": 25,
        "EV_definition": EV_DEFINITION,
        "observation_schedule": OBSERVATION_SCHEDULE,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_B": BOOTSTRAP_B,
        "cluster_unit": "internal_game_id",
        "git_commit": git["git_commit"],
        "git_commit_reason": git["git_commit_reason"],
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "run_timestamp": run_ts,
        "submits": False,
        "live_feed": "UNAVAILABLE",
        "execution": "DISABLED",
    }
    phase2_manifest = {
        "phase": PHASE,
        "phase_name": PHASE_NAME,
        "audit_id": PHASE2_ID,
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
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_B": BOOTSTRAP_B,
        "cluster_unit": "internal_game_id",
        "git_commit": git["git_commit"],
        "git_commit_reason": git["git_commit_reason"],
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "execution_enabled": False,
        "submits": False,
        "run_timestamp": run_ts,
        "live_feed": "UNAVAILABLE",
        "execution": "DISABLED",
    }
    audit_statistics = {
        "audit_id": AUDIT_ID,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "A": stats_a,
        "B": stats_b,
        "alignment_verdict": verdict,
        "pooled_descriptive_not_confirmation": pooled,
        "interpretation": audit_interp,
    }
    phase2_statistics = {
        "audit_id": PHASE2_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "A": stats_a,
        "B": stats_b,
        "alignment_verdict": verdict,
        "pooled_descriptive_not_confirmation": pooled,
        "interpretation": phase2_interp,
    }

    audit_root = persistence_audit_dir()
    audit_root.mkdir(parents=True, exist_ok=True)
    write_json(audit_root / "MANIFEST.json", audit_manifest)
    write_json(audit_root / "statistics.json", audit_statistics)
    write_json(audit_root / "leakage_audit.json", audits["leakage"])
    write_json(audit_root / "confirmation_protection_audit.json", audits["confirmation"])
    write_json(audit_root / "model_hash_audit.json", audits["model"])
    write_json(audit_root / "cohort_hash_audit.json", audits["cohort"])
    _write_shared_tables(audit_root, a, b, b_align=b_align, b_examples=b_examples)
    audit_report = _guard_report(
        render_report(
            {
                "manifest": audit_manifest,
                "A": {**a, **stats_a},
                "B": {**b, **stats_b},
                "interpretation": audit_interp,
                "alignment_verdict": verdict,
                "audits": audits,
                "pooled": pooled,
            }
        )
    )
    (audit_root / "REPORT.md").write_text(audit_report + "\n", encoding="utf-8")

    phase2_root = persistence_phase2_dir()
    phase2_root.mkdir(parents=True, exist_ok=True)
    write_json(phase2_root / "MANIFEST.json", phase2_manifest)
    write_json(phase2_root / "statistics.json", phase2_statistics)
    write_json(phase2_root / "leakage_audit.json", audits["leakage"])
    write_json(phase2_root / "confirmation_protection_audit.json", audits["confirmation"])
    write_json(phase2_root / "model_hash_audit.json", audits["model"])
    write_json(phase2_root / "cohort_hash_audit.json", audits["cohort"])
    _write_shared_tables(phase2_root, a, b, b_align=b_align, b_examples=b_examples)
    _write_phase2_tables(phase2_root, a, b)
    phase2_report = _guard_report(
        render_phase2_report(
            {
                "manifest": phase2_manifest,
                "A": {**a, **stats_a},
                "B": {**b, **stats_b},
                "interpretation": phase2_interp,
                "alignment_verdict": verdict,
                "audits": audits,
                "pooled": pooled,
            }
        )
    )
    (phase2_root / "REPORT.md").write_text(phase2_report + "\n", encoding="utf-8")
    _add_phase1_pointer()
    return {
        "audit_id": AUDIT_ID,
        "phase2_id": PHASE2_ID,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "n_first_negative_A": a["economics"]["n_first_negative"],
        "n_first_negative_B": b["economics"]["n_first_negative"],
        "alignment": verdict,
        "interpretation": phase2_interp,
        "members": MEMBERS,
        "execution": "DISABLED",
        "submits": False,
    }
