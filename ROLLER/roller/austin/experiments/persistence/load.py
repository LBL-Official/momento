"""Discovery-only readers. Confirmation result files are refused."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, MEMBERS, assert_experiment_id
from roller.austin.experiments.interpretation import load_discovery_queries
from roller.austin.experiments.policies import confirmation_artifacts_exist
from roller.austin.paths import experiment_dir, suite_freeze_path
from roller.austin.store import load_json

from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH, LOCKED_DISCOVERY_HASH

CONFIRMATION_RESULT_MARKERS = (
    "/confirmation/state_queries.csv",
    "/confirmation/statistics.json",
    "/confirmation/policy_ledger.csv",
    "/confirmation/baseline_hold_ledger.csv",
    "/confirmation/baseline_8040_ledger.csv",
    "/confirmation/intervention_ledger.csv",
    "/confirmation/REPORT.md",
    "/confirmation_state_queries.csv",
    "/confirmation_statistics.json",
    "/confirmation_policy_ledger.csv",
    "/confirmation_REPORT.md",
)


def refuse_confirmation_path(path: Path) -> Path:
    text = str(path.resolve()).replace("\\", "/")
    for marker in CONFIRMATION_RESULT_MARKERS:
        if text.endswith(marker) or marker in text:
            raise AustinError("LOCK_MISMATCH", f"confirmation result file refused: {path}")
    return path


def assert_discovery_only() -> None:
    if suite_freeze_path().is_file():
        raise AustinError("LOCK_MISMATCH", "persistence audit refuses to run after POLICY_FREEZE.json")
    if confirmation_artifacts_exist():
        raise AustinError("LOCK_MISMATCH", "persistence audit refuses confirmation result artifacts")


def load_discovery_cohort(experiment_id: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    path = refuse_confirmation_path(experiment_dir(experiment_id) / "discovery_cohort.json")
    payload = load_json(path)
    if payload.get("cohort_hash") != LOCKED_DISCOVERY_HASH[experiment_id]:
        raise AustinError("LOCK_MISMATCH", f"{experiment_id} discovery cohort hash drifted")
    if any(str(t.get("slice")) == "H2_2" for t in payload.get("trades") or []):
        raise AustinError("LOCK_MISMATCH", "H2_2 leaked into discovery cohort")
    return payload


def load_confirmation_identity(experiment_id: str) -> dict[str, Any]:
    """Hash and counts only. Does not use confirmation outcomes."""
    experiment_id = assert_experiment_id(experiment_id)
    path = experiment_dir(experiment_id) / "confirmation_cohort.json"
    if not path.is_file():
        raise AustinError("DATA_REQUIRED", f"{experiment_id} confirmation_cohort.json missing")
    payload = load_json(path)
    identity = {
        "experiment_id": payload.get("experiment_id"),
        "role": payload.get("role"),
        "n_trades": payload.get("n_trades"),
        "n_games": payload.get("n_games"),
        "cohort_hash": payload.get("cohort_hash"),
    }
    if identity["cohort_hash"] != LOCKED_CONFIRMATION_HASH[experiment_id]:
        raise AustinError("LOCK_MISMATCH", f"{experiment_id} confirmation cohort hash drifted")
    if identity["role"] != "CONFIRMATION":
        raise AustinError("LOCK_MISMATCH", f"{experiment_id} confirmation role drifted")
    return identity


def load_member_discovery(experiment_id: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    assert_discovery_only()
    cohort = load_discovery_cohort(experiment_id)
    queries = load_discovery_queries(experiment_id)
    refuse_confirmation_path(experiment_dir(experiment_id) / "discovery" / "state_queries.csv")
    if any(str(r.get("slice")) == "H2_2" for r in queries):
        raise AustinError("LOCK_MISMATCH", "H2_2 leaked into discovery queries")
    identity = load_confirmation_identity(experiment_id)
    return {
        "experiment_id": experiment_id,
        "trades": list(cohort["trades"]),
        "queries": queries,
        "discovery_hash": cohort["cohort_hash"],
        "confirmation_identity": identity,
    }


def load_suite_discovery() -> dict[str, dict[str, Any]]:
    assert_discovery_only()
    return {eid: load_member_discovery(eid) for eid in (EXPERIMENT_A, EXPERIMENT_B)}


def confirmation_files_absent() -> dict[str, Any]:
    missing = []
    present = []
    for eid in MEMBERS:
        root = experiment_dir(eid)
        for rel in (
            "confirmation/state_queries.csv",
            "confirmation/statistics.json",
            "confirmation/policy_ledger.csv",
            "confirmation_state_queries.csv",
            "confirmation_statistics.json",
        ):
            path = root / rel
            if path.is_file():
                present.append(str(path))
            else:
                missing.append(str(path))
    return {
        "confirmation_accessed": False,
        "confirmation_result_files_present": present,
        "confirmation_result_files_absent": missing,
        "status": "PASS" if not present else "FAIL",
    }
