"""CLI stages. Never --stage all. Freeze is suite-level only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.audits import run_leakage_audit, run_self_neighbor_audit
from roller.austin.experiments.cohorts import load_cohort, print_lock_card, write_all_cohorts
from roller.austin.experiments.interpretation import interpret_suite, stage_interpret
from roller.austin.experiments.ids import (
    AUDIT_ID,
    PHASE2_ID,
    PHASE3_ID,
    PHASE4_ID,
    PHASE5_ID,
    PHASE6_ID,
    PHASE7_ID,
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    EV_DEFINITION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    MEMBERS,
    SUITE_ID,
    assert_experiment_id,
    assert_suite_id,
)
from roller.austin.experiments.ledgers import persist_ledgers, policy_rows
from roller.austin.experiments.manifest import git_commit, persist_model_manifest, resolve_git_commit, verify_model_manifest
from roller.austin.experiments.policies import (
    POLICY_FAMILY,
    assert_policy_id,
    canonical_definition,
    confirmation_artifacts_exist,
    policy_hash,
)
from roller.austin.experiments.query_runner import persist_grids, persist_queries, run_grids, run_queries
from roller.austin.experiments.report import persist_report, render_report, render_stop_report
from roller.austin.experiments.statistics import build_statistics, persist_statistics, warning_rows
from roller.austin.experiments.warehouse_cache import load_trade_warehouse
from roller.austin.paths import experiment_dir, experiments_root, suite_dir, suite_freeze_path
from roller.austin.store import load_json, write_json


def _enrich_experiment_manifest(experiment_id: str, *, model: dict[str, Any], cohort: str) -> None:
    path = experiment_dir(experiment_id) / "MANIFEST.json"
    current = load_json(path, required=False) or {}
    git = resolve_git_commit()
    current.update(
        {
            "experiment_id": experiment_id,
            "suite_id": SUITE_ID,
            "model_manifest_hash": model.get("model_manifest_hash"),
            "feature_schema_hash": model.get("feature_schema_hash"),
            "policy_status": "UNFROZEN" if cohort == "DISCOVERY" else "FROZEN",
            "policy_hash": "UNAVAILABLE" if cohort == "DISCOVERY" else current.get("policy_hash") or "UNAVAILABLE",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_B": BOOTSTRAP_B,
            "ci_method": "clustered_bootstrap",
            "git_commit": git["git_commit"],
            "git_commit_status": git["git_commit_status"],
            "git_commit_reason": git["git_commit_reason"],
            "confirmation_result": "NOT RUN" if cohort == "DISCOVERY" else "OBSERVED",
        }
    )
    write_json(path, current)


def stage_pin() -> dict[str, Any]:
    return persist_model_manifest()


def stage_cohorts() -> dict[str, Any]:
    model = verify_model_manifest()
    payload = write_all_cohorts()
    card = print_lock_card(payload, model)
    (experiments_root() / "LOCK_CARD.txt").write_text(card + "\n", encoding="utf-8")
    return payload


def stage_grid(experiment_id: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    verify_model_manifest()
    payload = load_cohort(experiment_id, "DISCOVERY")
    trades = list(payload["trades"])
    rows = run_grids(experiment_id, trades, cohort="DISCOVERY")
    persist_grids(experiment_id, "DISCOVERY", rows)
    return {"experiment_id": experiment_id, "cohort": "DISCOVERY", "n_grid_rows": len(rows), "n_trades": len(trades)}


def _run_stage(experiment_id: str, cohort: str, *, limit: int | None, policy_ids: list[str], freeze: dict[str, Any] | None) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    model = verify_model_manifest()
    payload = load_cohort(experiment_id, cohort)
    trades = list(payload["trades"])
    queries = run_queries(experiment_id, trades, cohort=cohort, limit=limit)
    persist_queries(experiment_id, cohort, queries)
    persist_ledgers(experiment_id, cohort, trades, queries, policy_ids=policy_ids)
    policies, interventions = policy_rows(trades, queries, policy_ids=policy_ids)
    stats = build_statistics(
        experiment_id=experiment_id,
        cohort=cohort,
        trades=trades,
        queries=queries,
        policy_ledger=policies,
        interventions=interventions,
    )
    warnings = warning_rows(trades, queries)
    persist_statistics(experiment_id, cohort, stats, warnings)
    warehouse = load_trade_warehouse(trades)
    leakage = run_leakage_audit(experiment_id, cohort, trades, warehouse)
    neighbor = run_self_neighbor_audit(experiment_id, cohort, trades)
    audits = {"leakage": leakage, "self_neighbor": neighbor}
    if cohort == "CONFIRMATION":
        write_json(experiment_dir(experiment_id) / "confirmation_leakage_audit.json", leakage)
        write_json(experiment_dir(experiment_id) / "confirmation_self_neighbor_audit.json", neighbor)
    text = render_report(experiment_id=experiment_id, cohort=cohort, stats=stats, freeze=freeze)
    persist_report(experiment_id, cohort, text)
    _enrich_experiment_manifest(experiment_id, model=model, cohort=cohort)
    if cohort == "DISCOVERY":
        stop = render_stop_report(experiment_id, stats, audits)
        print(stop, flush=True)
        (experiment_dir(experiment_id) / "discovery" / "STOP_REPORT.txt").write_text(stop, encoding="utf-8")
        (experiment_dir(experiment_id) / "STOP_REPORT.txt").write_text(stop, encoding="utf-8")
    return {
        "experiment_id": experiment_id,
        "cohort": cohort,
        "n_queries": len(queries),
        "n_trades": len(trades),
        "audits": audits,
        "policy_status": "UNFROZEN" if cohort == "DISCOVERY" else "FROZEN",
        "confirmation_result": "NOT RUN" if cohort == "DISCOVERY" else "OBSERVED",
    }


def stage_discovery(experiment_id: str, *, limit: int | None = None) -> dict[str, Any]:
    if experiment_dir(experiment_id).joinpath("POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "experiment-local POLICY_FREEZE.json is forbidden")
    return _run_stage(experiment_id, "DISCOVERY", limit=limit, policy_ids=list(POLICY_FAMILY), freeze=None)


def stage_freeze(suite_id: str, policy_id: str) -> dict[str, Any]:
    assert_suite_id(suite_id)
    policy_id = assert_policy_id(policy_id)
    if confirmation_artifacts_exist():
        raise AustinError("LOCK_MISMATCH", "cannot freeze after confirmation artifacts exist")
    model = verify_model_manifest()
    from roller.austin.experiments.cohorts import ensure_cohorts

    cohorts = ensure_cohorts()
    for experiment_id in MEMBERS:
        if not (experiment_dir(experiment_id) / "discovery" / "state_queries.csv").is_file():
            raise AustinError("DATA_REQUIRED", f"{experiment_id} discovery queries missing")
        if (experiment_dir(experiment_id) / "POLICY_FREEZE.json").is_file():
            raise AustinError("LOCK_MISMATCH", "experiment-local POLICY_FREEZE.json is forbidden")
    payload = {
        "suite_id": SUITE_ID,
        "policy_id": policy_id,
        "canonical_policy_definition": canonical_definition(policy_id),
        "policy_hash": policy_hash(policy_id),
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "model_manifest_hash": model["model_manifest_hash"],
        "feature_schema_hash": model["feature_schema_hash"],
        "pca_version": model["pca_version"] if "pca_version" in model else "austin_pca_v1",
        "scaler_version": "austin_v2_mu_sd",
        "K": 25,
        "EV_definition": EV_DEFINITION,
        "CI_method": "weighted_bootstrap",
        "observation_schedule": "EVERY_2_GAME_CLOCK_MINUTES",
        "A_discovery_cohort_hash": cohorts[EXPERIMENT_A]["discovery"]["cohort_hash"],
        "A_confirmation_cohort_hash": cohorts[EXPERIMENT_A]["confirmation"]["cohort_hash"],
        "B_discovery_cohort_hash": cohorts[EXPERIMENT_B]["discovery"]["cohort_hash"],
        "B_confirmation_cohort_hash": cohorts[EXPERIMENT_B]["confirmation"]["cohort_hash"],
        "confirmation_read": False,
    }
    suite_dir().mkdir(parents=True, exist_ok=True)
    write_json(suite_freeze_path(), payload)
    return payload


def stage_confirmation(experiment_id: str, *, limit: int | None = None, policy: str | None = None) -> dict[str, Any]:
    if policy:
        raise AustinError("QUERY_REJECTED", "confirmation refuses --policy; load suite POLICY_FREEZE.json")
    freeze = load_json(suite_freeze_path())
    if freeze.get("confirmation_read") is True:
        raise AustinError("LOCK_MISMATCH", "POLICY_FREEZE confirmation_read must be false")
    model = verify_model_manifest()
    if freeze.get("model_manifest_hash") != model["model_manifest_hash"]:
        raise AustinError("LOCK_MISMATCH", "model hash changed after freeze")
    from roller.austin.experiments.cohorts import ensure_cohorts

    cohorts = ensure_cohorts()
    key_d = "A_discovery_cohort_hash" if experiment_id == EXPERIMENT_A else "B_discovery_cohort_hash"
    key_c = "A_confirmation_cohort_hash" if experiment_id == EXPERIMENT_A else "B_confirmation_cohort_hash"
    if freeze.get(key_d) != cohorts[experiment_id]["discovery"]["cohort_hash"]:
        raise AustinError("LOCK_MISMATCH", "discovery cohort hash changed after freeze")
    if freeze.get(key_c) != cohorts[experiment_id]["confirmation"]["cohort_hash"]:
        raise AustinError("LOCK_MISMATCH", "confirmation cohort hash changed after freeze")
    return _run_stage(
        experiment_id,
        "CONFIRMATION",
        limit=limit,
        policy_ids=[freeze["policy_id"]],
        freeze=freeze,
    )


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else None
    if raw is not None and "--stage" in raw:
        idx = raw.index("--stage")
        if idx + 1 < len(raw) and raw[idx + 1] == "all":
            raise AustinError("QUERY_REJECTED", "--stage all is forbidden")
    parser = argparse.ArgumentParser(description="Austin NCAAB transfer experiment")
    parser.add_argument("--suite", default=None)
    parser.add_argument("--experiment", default=None)
    parser.add_argument(
        "--stage",
        required=True,
        choices=(
            "pin",
            "cohorts",
            "grid",
            "discovery",
            "interpret",
            "persist",
            "downfall",
            "hazard",
            "policy",
            "policy-freeze",
            "confirmation-gate",
            "prospective",
            "freeze",
            "confirmation",
        ),
    )
    parser.add_argument("--policy", default=None)
    parser.add_argument("--human-selected-policy", default="UNSET")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    if args.stage == "pin":
        stage_pin()
        return 0
    if args.stage == "cohorts":
        stage_cohorts()
        return 0
    if args.stage == "interpret":
        if args.experiment:
            stage_interpret(args.experiment)
        else:
            interpret_suite()
        return 0
    if args.stage == "persist":
        from roller.austin.experiments.persistence.run import stage_persist

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "persist is suite-level discovery-only; do not pass a transfer member")
        print(stage_persist(), flush=True)
        return 0
    if args.stage == "downfall":
        from roller.austin.experiments.downfall.run import stage_downfall

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "downfall is suite-level discovery-only; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "downfall refuses --policy; policy remains UNFROZEN")
        print(stage_downfall(), flush=True)
        return 0
    if args.stage == "hazard":
        from roller.austin.experiments.hazard.run import stage_hazard

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, PHASE4_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "hazard is suite-level discovery-only; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "hazard refuses --policy; policy remains UNFROZEN")
        print(stage_hazard(), flush=True)
        return 0
    if args.stage == "policy":
        from roller.austin.experiments.policy_v2.run import stage_policy

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE5_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "policy is suite-level discovery-only; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "policy refuses --policy; POLICY_A…F are historical; Phase 5A stays UNFROZEN")
        print(stage_policy(), flush=True)
        return 0
    if args.stage == "policy-freeze":
        from roller.austin.experiments.policy_v2.freeze import stage_policy_freeze

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE5_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "policy-freeze is suite-level; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "policy-freeze refuses --policy; POLICY_A…F are historical")
        print(stage_policy_freeze(args.human_selected_policy), flush=True)
        return 0
    if args.stage == "confirmation-gate":
        from roller.austin.experiments.confirmation_gate.run import stage_confirmation_gate

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE5_ID, PHASE6_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "confirmation-gate is suite-level; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "confirmation-gate refuses --policy; confirmation is not spent")
        print(stage_confirmation_gate(), flush=True)
        return 0
    if args.stage == "prospective":
        from roller.austin.experiments.prospective.run import stage_prospective

        if args.experiment and args.experiment not in {AUDIT_ID, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE5_ID, PHASE6_ID, PHASE7_ID, SUITE_ID}:
            raise AustinError("QUERY_REJECTED", "prospective is suite-level; do not pass a transfer member")
        if args.policy:
            raise AustinError("QUERY_REJECTED", "prospective refuses --policy; no policy is frozen")
        print(stage_prospective(), flush=True)
        return 0
    if args.stage == "freeze":
        if args.experiment:
            raise AustinError("QUERY_REJECTED", "freeze is suite-level; do not pass --experiment")
        if not args.suite:
            raise AustinError("QUERY_REJECTED", "freeze requires --suite AUSTIN_NCAAB_TRANSFER_V1")
        if not args.policy:
            raise AustinError("QUERY_REJECTED", "freeze requires explicit --policy POLICY_A…F")
        stage_freeze(args.suite, args.policy)
        return 0
    if not args.experiment:
        raise AustinError("QUERY_REJECTED", f"{args.stage} requires --experiment")
    if args.stage == "grid":
        stage_grid(args.experiment)
        return 0
    if args.stage == "discovery":
        stage_discovery(args.experiment, limit=args.limit)
        return 0
    if args.stage == "confirmation":
        stage_confirmation(args.experiment, limit=args.limit, policy=args.policy)
        return 0
    raise AustinError("QUERY_REJECTED", f"unknown stage {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
