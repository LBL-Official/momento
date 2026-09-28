"""Austin Phase 6 confirmation-preservation gate. Confirmation is not spent."""

from __future__ import annotations

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, PHASE6_ID, assert_experiment_id, MEMBERS
from roller.austin.experiments.manifest import sha256_file
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH
from roller.austin.experiments.persistence.load import refuse_confirmation_path
from roller.austin.experiments.policy_v2.freeze import stage_policy_freeze
from roller.austin.experiments.run import main
from roller.austin.paths import confirmation_gate_dir, experiment_dir, policy_phase5_dir, repo_root
from roller.austin.store import load_json

REPO = repo_root()
FORBIDDEN_RESULT_NAMES = (
    "confirmation_outcomes.json",
    "confirmation_queries.csv",
    "confirmation_state_queries.csv",
    "confirmation_hazard.json",
    "confirmation_policy_ledger.csv",
    "statistics.json",
)


def test_phase6_blocked_gate_seals_confirmation_without_spend():
    stage_policy_freeze("NONE")
    from roller.austin.experiments.confirmation_gate.run import stage_confirmation_gate

    payload = stage_confirmation_gate()
    root = confirmation_gate_dir()
    assert payload["status"] == "BLOCKED_NO_FROZEN_POLICY"
    assert payload["A_CONFIRMATION_STATUS"] == "SEALED_UNSPENT"
    assert payload["B_CONFIRMATION_STATUS"] == "SEALED_UNSPENT"
    assert payload["confirmation_outcomes_accessed"] is False
    manifest = load_json(root / "MANIFEST.json")
    assert manifest["status"] == "BLOCKED_NO_FROZEN_POLICY"
    assert manifest["confirmation_A_expected_N"] == 97
    assert manifest["confirmation_B_expected_N"] == 70
    assert manifest["confirmation_A_run"] is False
    assert manifest["confirmation_B_run"] is False
    assert manifest["confirmation_outcomes_accessed"] is False
    assert manifest["confirmation_queries_generated"] is False
    assert manifest["confirmation_state_model_generated"] is False
    assert manifest["confirmation_hazard_generated"] is False
    assert manifest["confirmation_policy_generated"] is False
    assert manifest["A_confirmation_hash"] == LOCKED_CONFIRMATION_HASH[EXPERIMENT_A]
    assert manifest["B_confirmation_hash"] == LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    for name in FORBIDDEN_RESULT_NAMES:
        assert not (root / name).is_file(), name
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    assert "NO CONFIRMATION TEST OCCURRED" in report.upper() or "no confirmation test occurred" in report.lower()
    assert "PHASE 7" in report


def test_phase6_cli_refuses_policy_transfer_and_confirmation_stage():
    with pytest.raises(AustinError):
        main(["--stage", "confirmation-gate", "--policy", "POLICY_A"])
    with pytest.raises(AustinError):
        main(["--stage", "confirmation-gate", "--experiment", EXPERIMENT_A])
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE6_ID)
    assert PHASE6_ID not in MEMBERS
    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()


def test_phase6_api_and_ui():
    stage_policy_freeze("NONE")
    from roller.austin.experiments.confirmation_gate.run import stage_confirmation_gate

    stage_confirmation_gate()
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments

    suite = handle_experiments()
    assert suite["confirmation_gate_phase6"]["gate_id"] == PHASE6_ID
    payload = handle_experiment(PHASE6_ID)
    assert payload["policy_status"] == "NO_POLICY_FROZEN"
    assert payload["confirmation_accessed"] is False
    assert payload["submits"] is False
    assert payload.get("A_CONFIRMATION_STATUS") == "SEALED_UNSPENT"
    assert payload.get("B_CONFIRMATION_STATUS") == "SEALED_UNSPENT"
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    assert "PHASE 6 · CONFIRMATION SEALED" in ui
    assert "A 97 UNSPENT" in ui
    assert "B 70 UNSPENT" in ui
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert sha256_file(policy_phase5_dir() / "POLICY_CANDIDATES.json")
