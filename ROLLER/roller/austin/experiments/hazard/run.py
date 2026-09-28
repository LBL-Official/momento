"""Discovery-only Phase 4 runner. Does not rewrite Phase 2/3 results. Does not freeze. Does not confirm."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.timeline import trade_primary
from roller.austin.experiments.hazard.analyses import (
    by_state,
    by_state_ci,
    dynamic_updates,
    ev_vs_hazard,
    missingness,
    predeclared_contrasts,
    support_rows,
    t40_rows,
    timing_rows,
    trajectories,
    transition_risk,
)
from roller.austin.experiments.hazard.audits import (
    cohort_hash_audit,
    confirmation_audit,
    crossfit_audit,
    leakage_audit,
    model_hash_audit,
    phase2_finalization_audit,
    phase3_finalization_audit,
    state_schema_audit,
    warning_audit,
)
from roller.austin.experiments.hazard.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    EV_DEFINITION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    HAZARD_SCHEMA_VERSION,
    H0,
    H1,
    H2,
    LOCKED_CONFIRMATION_HASH,
    LOCKED_DISCOVERY_HASH,
    MODEL_ID,
    NEGATIVE_STATES,
    OBSERVATION_SCHEDULE,
    PHASE,
    PHASE2_ID,
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_ID,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    PHASE4_ID,
    PHASE4_PHASE,
    PHASE_NAME,
    STATE_SCHEMA_HASH,
    STATE_SCHEMA_VERSION,
    SUITE_ID,
    TARGETS,
)
from roller.austin.experiments.hazard.io import read_csv
from roller.austin.experiments.hazard.logo import attach_predictions, crossfit_rows, predict_family
from roller.austin.experiments.hazard.metrics import calibration_rows, family_metrics
from roller.austin.experiments.hazard.report import interpret_hazard, render_report
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash
from roller.austin.experiments.hazard.targets import attach_targets
from roller.austin.experiments.ids import MEMBERS
from roller.austin.experiments.manifest import LOCKED_HASHES, resolve_git_commit, verify_model_manifest
from roller.austin.experiments.persistence.load import assert_discovery_only, load_suite_discovery
from roller.austin.experiments.persistence.util import write_csv
from roller.austin.experiments.warehouse_cache import load_trade_warehouse
from roller.austin.paths import downfall_phase3_dir, hazard_phase4_dir, suite_freeze_path
from roller.austin.store import write_json

PRED_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "core_state",
    "CI_state",
    "family",
    "target",
    "scoring_internal_game_id",
    "training_game_count",
    "same_game_present_in_training",
    "conditioning_key",
    "p_hat",
    "support_n",
    "event_n",
    "posterior_lower",
    "posterior_upper",
    "status",
]

PREFIXES = (
    "terminal_loss",
    "recovery_t1",
    "recovery_by_t2",
    "recovery_by_t3",
    "deeper_distress_next",
)

ENTRY_FIELDS = [
    "phase_id",
    "model_id",
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "ticker",
    "slice",
    "state_sequence_number",
    "state_entry_timestamp",
    "period",
    "game_clock",
    "core_state",
    "negative_streak_length",
    "CI_state",
    "support_state",
    "EV",
    "CI_lower",
    "CI_upper",
    "CI_width",
    "EV_entry",
    "EV_change_from_entry",
    "EV_change_from_previous",
    "EV_velocity",
    "EV_acceleration",
    "price",
    "price_travel",
    "score_diff",
    "score_diff_travel",
    "game_time_remaining",
    "time_since_entry",
    "ESS",
    "median_distance",
    "feature_coverage",
    "TARGET_terminal_loss",
    "TARGET_recovery_t1",
    "TARGET_recovery_by_t2",
    "TARGET_recovery_by_t3",
    "TARGET_deeper_distress_next",
    "TARGET_T40_before_recovery",
]
for _family in (H0, H1, H2):
    for _prefix in PREFIXES:
        ENTRY_FIELDS.extend(
            [
                f"p_{_prefix}_{_family}",
                f"support_n_{_prefix}_{_family}",
                f"event_n_{_prefix}_{_family}",
                f"posterior_lower_{_prefix}_{_family}",
                f"posterior_upper_{_prefix}_{_family}",
            ]
        )

BY_STATE_FIELDS = [
    "source_experiment_id",
    "core_state",
    "N",
    "terminal_losses",
    "p_terminal_loss_H1",
    "p_terminal_loss_lo",
    "p_terminal_loss_hi",
    "support_n_loss",
    "p_recovery_t1_H1",
    "p_recovery_by_t2_H1",
    "p_recovery_by_t3_H1",
    "mean_pnl_hold_after_state",
]
BY_CI_FIELDS = [
    "source_experiment_id",
    "core_state",
    "CI_state",
    "N",
    "losses",
    "p_terminal_loss_H2",
    "posterior_lower",
    "posterior_upper",
    "label",
]
CAL_FIELDS = ["source_experiment_id", "target", "family", "bin_lo", "bin_hi", "N", "mean_predicted", "observed_rate", "difference", "strong_evidence"]
METRIC_FIELDS = [
    "source_experiment_id",
    "target",
    "family",
    "eligible_N",
    "event_N",
    "unavailable_N",
    "brier",
    "bss_vs_H0",
    "bss_ci",
    "log_loss",
    "delta_log_loss_vs_H0",
    "delta_log_loss_ci",
    "roc_auc",
    "pr_auc",
]
COMPARE_FIELDS = ["source_experiment_id", "target", "family", "bss_vs_H0", "bss_ci_lo", "bss_ci_hi", "delta_log_loss_vs_H0", "delta_log_loss_ci_lo", "delta_log_loss_ci_hi"]
TRAJ_FIELDS = [
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "core_state",
    "state_sequence_number",
    "p_terminal_loss_H1",
    "p_recovery_t1_H1",
    "delta_p_loss_H1",
    "delta_p_recovery_t1_H1",
]
TRANS_FIELDS = [
    "source_experiment_id",
    "trade_id",
    "from_state",
    "to_state",
    "branch",
    "p_terminal_loss_H1",
    "p_recovery_t1_H1",
    "p_recovery_by_t2_H1",
    "p_recovery_by_t3_H1",
    "p_terminal_loss_H2",
    "p_recovery_t1_H2",
]
EV_FIELDS = ["source_experiment_id", "contrast", "n", "spearman", "ci_lo", "ci_hi"]
SUPPORT_FIELDS = ["source_experiment_id", "core_state", "N", "mean_ESS", "mean_median_distance", "mean_feature_coverage", "low_cell_support_N"]
TIMING_FIELDS = [
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "core_state",
    "price",
    "price_travel",
    "future_min_price",
    "adverse_cents_remaining",
    "minutes_to_worst_price",
    "minutes_to_settlement",
    "p_terminal_loss_H1",
    "p_recovery_t1_H1",
    "p_recovery_by_t2_H1",
    "p_recovery_by_t3_H1",
]
MISS_FIELDS = ["source_experiment_id", "target", "eligible", "positive", "negative", "unavailable", "not_applicable"]
T40_FIELDS = ["source_experiment_id", "N_negative_entries", "N_not_applicable", "N_unavailable", "N_observable", "n_T40_before_recovery"]
CONTRAST_FIELDS = ["source_experiment_id", "contrast", "metric", "n_left", "n_right", "observed_delta", "ci_lo", "ci_hi", "classification"]


def _group_timeline(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("source_experiment_id")), str(row.get("trade_id")))].append(row)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=lambda r: int(r.get("state_sequence_number") or 0))
    return grouped


def _join_timeline(entry: dict[str, Any], timeline: list[dict[str, Any]]) -> dict[str, Any]:
    seq = int(entry.get("state_sequence_number") or 0)
    match = next((r for r in timeline if int(r.get("state_sequence_number") or 0) == seq), {})
    out = dict(entry)
    out["state_entry_timestamp"] = entry.get("timestamp")
    out["price"] = entry.get("current_price")
    for key in (
        "EV_entry",
        "EV_change_from_entry",
        "EV_change_from_previous",
        "EV_velocity",
        "EV_acceleration",
        "score_diff",
        "score_diff_travel",
        "game_time_remaining",
        "time_since_entry",
    ):
        out.setdefault(key, match.get(key))
    return out


def _ci(row: dict[str, Any], key: str) -> str:
    band = row.get(key) or [None, None]
    return f"[{band[0]}, {band[1]}]"


def _timing_summary(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for state in NEGATIVE_STATES:
        group = [r for r in rows if r.get("core_state") == state]
        p = [float(r["p_terminal_loss_H1"]) for r in group if r.get("p_terminal_loss_H1") is not None]
        adv = [float(r["adverse_cents_remaining"]) for r in group if r.get("adverse_cents_remaining") is not None]
        mins = [float(r["OUTCOME_minutes_to_worst_price"]) for r in group if r.get("OUTCOME_minutes_to_worst_price") is not None]
        out.append(
            {
                "core_state": state,
                "N": len(group),
                "mean_adverse_cents_remaining": None if not adv else sum(adv) / len(adv),
                "mean_minutes_to_worst_price": None if not mins else sum(mins) / len(mins),
                "mean_p_loss": None if not p else sum(p) / len(p),
                "p_spread": None if len(p) < 2 else max(p) - min(p),
            }
        )
    return out


def _transition_summary(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("from_state")), str(row.get("to_state")))].append(row)
    out = []
    for (src, dst), group in grouped.items():
        p = [float(r["p_terminal_loss_H1"]) for r in group if r.get("p_terminal_loss_H1") is not None]
        out.append(
            {
                "from_state": src,
                "to_state": dst,
                "N": len(group),
                "mean_p_loss_from": None if not p else sum(p) / len(p),
            }
        )
    return out


def _member_stats(
    experiment_id: str,
    rows: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = family_metrics(rows, y_key="TARGET_terminal_loss", prefix="terminal_loss", experiment_id=experiment_id)
    for target, prefix in (
        ("TARGET_recovery_t1", "recovery_t1"),
        ("TARGET_recovery_by_t2", "recovery_by_t2"),
        ("TARGET_recovery_by_t3", "recovery_by_t3"),
        ("TARGET_deeper_distress_next", "deeper_distress_next"),
    ):
        metrics.extend(family_metrics(rows, y_key=target, prefix=prefix, experiment_id=experiment_id))
    loss_cal = []
    rec_cal = {1: [], 2: [], 3: []}
    from roller.austin.experiments.hazard.metrics import _pairs

    for family in (H0, H1, H2):
        loss_cal.extend(calibration_rows(_pairs(rows, "TARGET_terminal_loss", f"p_terminal_loss_{family}"), target="TARGET_terminal_loss", family=family, experiment_id=experiment_id))
        rec_cal[1].extend(calibration_rows(_pairs(rows, "TARGET_recovery_t1", f"p_recovery_t1_{family}"), target="TARGET_recovery_t1", family=family, experiment_id=experiment_id))
        rec_cal[2].extend(calibration_rows(_pairs(rows, "TARGET_recovery_by_t2", f"p_recovery_by_t2_{family}"), target="TARGET_recovery_by_t2", family=family, experiment_id=experiment_id))
        rec_cal[3].extend(calibration_rows(_pairs(rows, "TARGET_recovery_by_t3", f"p_recovery_by_t3_{family}"), target="TARGET_recovery_by_t3", family=family, experiment_id=experiment_id))
    trans = transition_risk(rows, transitions, experiment_id)
    loss_h1 = next((m for m in metrics if m["target"] == "TARGET_terminal_loss" and m["family"] == H1), {})
    loss_h2 = next((m for m in metrics if m["target"] == "TARGET_terminal_loss" and m["family"] == H2), {})
    return {
        "experiment_id": experiment_id,
        "n_entries": len(rows),
        "n_terminal_loss_eligible": sum(1 for r in rows if r.get("TARGET_terminal_loss") in (0, 1)),
        "n_recovery_t1_eligible": sum(1 for r in rows if r.get("TARGET_recovery_t1") in (0, 1)),
        "n_recovery_t2_eligible": sum(1 for r in rows if r.get("TARGET_recovery_by_t2") in (0, 1)),
        "n_recovery_t3_eligible": sum(1 for r in rows if r.get("TARGET_recovery_by_t3") in (0, 1)),
        "n_recovery_t1_unavailable": sum(1 for r in rows if r.get("core_state") in NEGATIVE_STATES and r.get("TARGET_recovery_t1") is None),
        "n_recovery_t2_unavailable": sum(1 for r in rows if r.get("core_state") in NEGATIVE_STATES and r.get("TARGET_recovery_by_t2") is None),
        "n_recovery_t3_unavailable": sum(1 for r in rows if r.get("core_state") in NEGATIVE_STATES and r.get("TARGET_recovery_by_t3") is None),
        "metrics": metrics,
        "by_state": by_state(rows, experiment_id),
        "by_state_ci": by_state_ci(rows, experiment_id),
        "missingness": missingness(rows, experiment_id),
        "loss_calibration": loss_cal,
        "recovery_t1_calibration": rec_cal[1],
        "recovery_t2_calibration": rec_cal[2],
        "recovery_t3_calibration": rec_cal[3],
        "trajectories": trajectories(rows),
        "transitions": trans,
        "transition_summary": _transition_summary(trans, experiment_id),
        "ev_vs_hazard": ev_vs_hazard(rows, experiment_id),
        "support": support_rows(rows, experiment_id),
        "timing": timing_rows(rows),
        "timing_summary": _timing_summary(rows, experiment_id),
        "t40": t40_rows(rows, experiment_id),
        "contrasts": predeclared_contrasts(rows, experiment_id),
        "dynamic": dynamic_updates(rows, experiment_id),
        "loss_bss_ci_H1": _ci(loss_h1, "bss_ci"),
        "loss_bss_ci_H2": _ci(loss_h2, "bss_ci"),
    }


def stage_hazard() -> dict[str, Any]:
    assert_discovery_only()
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "hazard refuses POLICY_FREEZE.json")
    phase2 = phase2_finalization_audit()
    phase3 = phase3_finalization_audit()
    model_lock = verify_model_manifest()
    schema = hazard_schema()
    hashed = schema_hash(schema)
    schema_audit = state_schema_audit(hashed)
    suite = load_suite_discovery()
    warning = warning_audit(suite)
    source = downfall_phase3_dir()
    if not (source / "state_entries.csv").is_file() or not (source / "state_timeline.csv").is_file():
        raise AustinError("DATA_REQUIRED", "Phase 3 state_entries/state_timeline missing")
    entries = read_csv(source / "state_entries.csv")
    timeline = read_csv(source / "state_timeline.csv")
    transitions = read_csv(source / "state_transitions.csv")
    keys = [(r.get("source_experiment_id"), r.get("trade_id"), r.get("core_state")) for r in entries]
    if len(keys) != len(set(keys)):
        raise AustinError("LOCK_MISMATCH", "Phase 3 first-entry uniqueness broken")
    grouped = _group_timeline(timeline)
    primaries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for eid, member in suite.items():
        for trade in member["trades"]:
            primaries[(eid, trade["trade_id"])] = trade_primary(member["queries"], trade["trade_id"])
    attached = []
    for entry in entries:
        eid = str(entry.get("source_experiment_id"))
        tid = str(entry.get("trade_id"))
        joined = _join_timeline(entry, grouped.get((eid, tid)) or [])
        attached.append(attach_targets(joined, grouped.get((eid, tid)) or [], primaries.get((eid, tid)) or []))
    predicted = attach_predictions(attached)
    for row in predicted:
        row["phase_id"] = PHASE4_PHASE
        row["model_id"] = MODEL_ID
    preds = {H0: [], H1: [], H2: []}
    for family in (H0, H1, H2):
        for target in TARGETS:
            preds[family].extend(predict_family(attached, family=family, target=target))
    xf = crossfit_rows(attached)
    xf_audit = crossfit_audit(xf)
    trades = list(suite[EXPERIMENT_A]["trades"]) + list(suite[EXPERIMENT_B]["trades"])
    warehouse = load_trade_warehouse(trades)
    leak = leakage_audit(predicted, grouped, suite, warehouse=warehouse)
    if leak["status"] != "PASS":
        raise AustinError("LOCK_MISMATCH", f"Phase 4 leakage {leak['status']}; Gate A required")
    confirmation = confirmation_audit()
    model_audit = model_hash_audit()
    cohort = cohort_hash_audit(suite)
    a_rows = [r for r in predicted if r.get("source_experiment_id") == EXPERIMENT_A]
    b_rows = [r for r in predicted if r.get("source_experiment_id") == EXPERIMENT_B]
    a = _member_stats(EXPERIMENT_A, a_rows, transitions)
    b = _member_stats(EXPERIMENT_B, b_rows, transitions)
    interp = interpret_hazard(a, b, leakage=leak, crossfit=xf_audit)
    git = resolve_git_commit()
    run_ts = datetime.now(timezone.utc).isoformat()
    if cohort["members"][EXPERIMENT_A]["discovery_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A discovery hash drifted")
    if cohort["members"][EXPERIMENT_B]["discovery_hash"] != LOCKED_DISCOVERY_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B discovery hash drifted")
    if cohort["members"][EXPERIMENT_A]["confirmation_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_A]:
        raise AustinError("LOCK_MISMATCH", "A confirmation identity hash drifted")
    if cohort["members"][EXPERIMENT_B]["confirmation_hash"] != LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]:
        raise AustinError("LOCK_MISMATCH", "B confirmation identity hash drifted")
    manifest = {
        "phase": PHASE,
        "phase_name": PHASE_NAME,
        "model_id": MODEL_ID,
        "hazard_schema_version": HAZARD_SCHEMA_VERSION,
        "hazard_schema_hash": hashed,
        "source_austin_model": "austin_v2",
        "source_phase_3": PHASE3_ID,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "state_schema_hash": STATE_SCHEMA_HASH,
        "source_phase_2": PHASE2_ID,
        "phase_2_status": "FINALIZED",
        "phase_2_actionability": "NOT_MET",
        "phase_3_status": "COMPLETE",
        "phase_3_result": "MIXED",
        "phase_4_authorization": "EXPLICIT_RESEARCHER_AUTHORIZATION",
        "probability_model": "EMPIRICAL_BETA_BINOMIAL",
        "prior": "JEFFREYS_0_5_0_5",
        "crossfit": "LEAVE_ONE_GAME_OUT",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_B": BOOTSTRAP_B,
        "cluster_unit": "internal_game_id",
        "A_discovery_hash": suite[EXPERIMENT_A]["discovery_hash"],
        "A_confirmation_hash": suite[EXPERIMENT_A]["confirmation_identity"]["cohort_hash"],
        "B_discovery_hash": suite[EXPERIMENT_B]["discovery_hash"],
        "B_confirmation_hash": suite[EXPERIMENT_B]["confirmation_identity"]["cohort_hash"],
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "execution_enabled": False,
        "submits": False,
        "git_commit": git["git_commit"],
        "git_commit_reason": git["git_commit_reason"],
        "run_timestamp": run_ts,
        "model_manifest_hash": model_lock["model_manifest_hash"],
        "feature_schema_hash": LOCKED_HASHES["registry.yaml"],
        "observation_schedule": OBSERVATION_SCHEDULE,
        "EV_definition": EV_DEFINITION,
        "source_suite": SUITE_ID,
        "phase_2_report_hash": PHASE2_REPORT_SHA256,
        "phase_2_statistics_hash": PHASE2_STATISTICS_SHA256,
        "phase_2_manifest_hash": PHASE2_MANIFEST_SHA256,
        "phase_3_report_hash": PHASE3_REPORT_SHA256,
        "phase_3_statistics_hash": PHASE3_STATISTICS_SHA256,
        "live_feed": "UNAVAILABLE",
        "execution": "DISABLED",
    }
    statistics = {
        "model_id": PHASE4_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "phase_2_actionability": "NOT_MET",
        "phase_3_result": "MIXED",
        "A": {
            "experiment_id": EXPERIMENT_A,
            "n_entries": a["n_entries"],
            "n_terminal_loss_eligible": a["n_terminal_loss_eligible"],
            "n_recovery_t1_eligible": a["n_recovery_t1_eligible"],
            "n_recovery_t2_eligible": a["n_recovery_t2_eligible"],
            "n_recovery_t3_eligible": a["n_recovery_t3_eligible"],
            "n_recovery_t1_unavailable": a["n_recovery_t1_unavailable"],
            "n_recovery_t2_unavailable": a["n_recovery_t2_unavailable"],
            "n_recovery_t3_unavailable": a["n_recovery_t3_unavailable"],
            "metrics": a["metrics"],
            "by_state": a["by_state"],
            "by_state_ci": a["by_state_ci"],
            "dynamic": a["dynamic"],
            "ev_vs_hazard": a["ev_vs_hazard"],
            "t40": a["t40"],
            "contrasts": a["contrasts"],
            "timing_summary": a["timing_summary"],
            "missingness": a["missingness"],
            "transition_summary": a["transition_summary"],
        },
        "B": {
            "experiment_id": EXPERIMENT_B,
            "n_entries": b["n_entries"],
            "n_terminal_loss_eligible": b["n_terminal_loss_eligible"],
            "n_recovery_t1_eligible": b["n_recovery_t1_eligible"],
            "n_recovery_t2_eligible": b["n_recovery_t2_eligible"],
            "n_recovery_t3_eligible": b["n_recovery_t3_eligible"],
            "n_recovery_t1_unavailable": b["n_recovery_t1_unavailable"],
            "n_recovery_t2_unavailable": b["n_recovery_t2_unavailable"],
            "n_recovery_t3_unavailable": b["n_recovery_t3_unavailable"],
            "metrics": b["metrics"],
            "by_state": b["by_state"],
            "by_state_ci": b["by_state_ci"],
            "dynamic": b["dynamic"],
            "ev_vs_hazard": b["ev_vs_hazard"],
            "t40": b["t40"],
            "contrasts": b["contrasts"],
            "timing_summary": b["timing_summary"],
            "missingness": b["missingness"],
            "transition_summary": b["transition_summary"],
        },
        "interpretation": interp,
    }
    root = hazard_phase4_dir()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "HAZARD_SCHEMA.json", schema)
    write_json(root / "MANIFEST.json", manifest)
    write_json(root / "statistics.json", statistics)
    write_json(root / "model_hash_audit.json", model_audit)
    write_json(root / "state_schema_audit.json", schema_audit)
    write_json(root / "cohort_hash_audit.json", cohort)
    write_json(root / "leakage_audit.json", leak)
    write_json(root / "crossfit_audit.json", xf_audit)
    write_json(root / "confirmation_protection_audit.json", confirmation)
    write_json(root / "phase2_finalization_audit.json", phase2)
    write_json(root / "phase3_finalization_audit.json", phase3)
    write_json(root / "warning_audit.json", warning)
    write_csv(root / "hazard_state_entries.csv", predicted, ENTRY_FIELDS)
    write_csv(root / "hazard_predictions_H0.csv", preds[H0], PRED_FIELDS)
    write_csv(root / "hazard_predictions_H1.csv", preds[H1], PRED_FIELDS)
    write_csv(root / "hazard_predictions_H2.csv", preds[H2], PRED_FIELDS)
    write_csv(root / "hazard_by_state.csv", a["by_state"] + b["by_state"], BY_STATE_FIELDS)
    write_csv(root / "hazard_by_state_ci.csv", a["by_state_ci"] + b["by_state_ci"], BY_CI_FIELDS)
    write_csv(root / "loss_calibration.csv", a["loss_calibration"] + b["loss_calibration"], CAL_FIELDS)
    write_csv(root / "recovery_t1_calibration.csv", a["recovery_t1_calibration"] + b["recovery_t1_calibration"], CAL_FIELDS)
    write_csv(root / "recovery_t2_calibration.csv", a["recovery_t2_calibration"] + b["recovery_t2_calibration"], CAL_FIELDS)
    write_csv(root / "recovery_t3_calibration.csv", a["recovery_t3_calibration"] + b["recovery_t3_calibration"], CAL_FIELDS)
    write_csv(root / "model_metrics.csv", a["metrics"] + b["metrics"], METRIC_FIELDS)
    compare = []
    for stats in (a, b):
        for row in stats["metrics"]:
            if row["family"] == H0:
                continue
            ci = row.get("bss_ci") or [None, None]
            dci = row.get("delta_log_loss_ci") or [None, None]
            compare.append(
                {
                    "source_experiment_id": row["source_experiment_id"],
                    "target": row["target"],
                    "family": row["family"],
                    "bss_vs_H0": row.get("bss_vs_H0"),
                    "bss_ci_lo": ci[0],
                    "bss_ci_hi": ci[1],
                    "delta_log_loss_vs_H0": row.get("delta_log_loss_vs_H0"),
                    "delta_log_loss_ci_lo": dci[0],
                    "delta_log_loss_ci_hi": dci[1],
                }
            )
    write_csv(root / "model_comparison.csv", compare, COMPARE_FIELDS)
    write_csv(root / "hazard_trajectories.csv", a["trajectories"] + b["trajectories"], TRAJ_FIELDS)
    write_csv(root / "transition_risk_analysis.csv", a["transitions"] + b["transitions"], TRANS_FIELDS)
    write_csv(root / "loss_risk_vs_ev.csv", a["ev_vs_hazard"] + b["ev_vs_hazard"], EV_FIELDS)
    write_csv(root / "support_analysis.csv", a["support"] + b["support"], SUPPORT_FIELDS)
    write_csv(root / "hazard_timing.csv", a["timing"] + b["timing"], TIMING_FIELDS)
    write_csv(root / "t40_before_recovery.csv", a["t40"] + b["t40"], T40_FIELDS)
    write_csv(root / "recovery_missingness.csv", a["missingness"] + b["missingness"], MISS_FIELDS)
    write_csv(root / "predeclared_contrasts.csv", a["contrasts"] + b["contrasts"], CONTRAST_FIELDS)
    report = render_report(
        {
            "manifest": manifest,
            "A": a,
            "B": b,
            "interpretation": interp,
            "audits": {
                "leakage": leak,
                "crossfit": xf_audit,
                "phase2": phase2,
                "phase3": phase3,
            },
        }
    )
    (root / "REPORT.md").write_text(report + "\n", encoding="utf-8")
    from roller.austin.experiments.manifest import sha256_file

    if sha256_file(source / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT.md changed during Phase 4")
    if sha256_file(source / "statistics.json") != PHASE3_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 statistics.json changed during Phase 4")
    from roller.austin.paths import persistence_phase2_dir

    p2 = persistence_phase2_dir()
    if sha256_file(p2 / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT.md changed during Phase 4")
    if sha256_file(p2 / "statistics.json") != PHASE2_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 statistics.json changed during Phase 4")
    return {
        "model_id": PHASE4_ID,
        "phase": PHASE,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "confirmation_accessed": False,
        "confirmation_A": "NOT RUN",
        "confirmation_B": "NOT RUN",
        "phase_2_actionability": "NOT_MET",
        "phase_3_result": "MIXED",
        "phase_4_complete": interp["phase_4_complete"],
        "phase_5_decision": interp["phase_5_decision"],
        "interpretation": interp,
        "members": MEMBERS,
        "execution": "DISABLED",
        "submits": False,
        "n_entries": len(predicted),
    }
