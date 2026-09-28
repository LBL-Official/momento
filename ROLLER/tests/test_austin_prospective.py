"""Austin Phase 7 prospective harness. Arm only. No 2026-27 ingest."""

from __future__ import annotations

import pandas as pd
import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, PHASE7_ID, assert_experiment_id, MEMBERS
from roller.austin.experiments.manifest import sha256_file
from roller.austin.experiments.policy_v2.freeze import stage_policy_freeze
from roller.austin.experiments.prospective.eligibility import INELIGIBLE, classify_event
from roller.austin.experiments.run import main
from roller.austin.paths import policy_phase5_dir, prospective_phase7_dir, repo_root
from roller.austin.store import load_json
from roller.choosin_texas.book import BOOK_ID, LIBRARY_RELATIVE

REPO = repo_root()


def test_phase7_lock_empty_stores_and_no_backfill():
    stage_policy_freeze("NONE")
    from roller.austin.experiments.confirmation_gate.run import stage_confirmation_gate
    from roller.austin.experiments.prospective.run import stage_prospective

    stage_confirmation_gate()
    book_path = REPO / LIBRARY_RELATIVE
    book_hash_before = sha256_file(book_path)
    payload = stage_prospective()
    root = prospective_phase7_dir()
    assert payload["status"] == "ARMED_WAITING_FOR_DATA"
    assert payload["eligible_n"] == 0
    assert payload["completed_n"] == 0
    assert payload["policy_status"] == "NO_POLICY_FROZEN" or payload.get("lock_already_present")
    lock = load_json(root / "PROSPECTIVE_LOCK.json")
    assert lock["page3_strategy_id"] == BOOK_ID
    assert lock["page3_status"] == "RESEARCH_REGISTERED"
    assert lock["no_historical_backfill"] is True
    assert lock["austin_never_filters_entry"] is True
    assert lock["execution_enabled"] is False
    assert lock.get("prospective_lock_hash")
    manifest = load_json(root / "MANIFEST.json")
    assert manifest["policy_status"] == "NO_POLICY_FROZEN"
    assert manifest["confirmation_A_status"] == "SEALED_UNSPENT"
    assert manifest["confirmation_B_status"] == "SEALED_UNSPENT"
    assert manifest["execution_enabled"] is False
    assert manifest["collection_status"] == "ARMED_WAITING_FOR_DATA"
    collection = load_json(root / "collection_status.json")
    assert collection["status"] == "ARMED_WAITING_FOR_DATA"
    assert collection["eligible_n"] == 0
    assert collection["completed_n"] == 0
    events = pd.read_parquet(root / "prospective_events.parquet")
    outcomes = pd.read_parquet(root / "prospective_outcomes.parquet")
    assert len(events) == 0
    assert len(outcomes) == 0
    assert "settlement" not in events.columns
    assert "won" not in events.columns
    assert (root / "revision_log.jsonl").read_text(encoding="utf-8") == ""
    rules = load_json(root / "runtime_rules.json")
    assert rules["events_before_lock"] == "INELIGIBLE_FOR_PHASE7"
    assert "INTERVENE" in rules["actions_forbidden"]
    assert classify_event("2020-01-01T00:00:00+00:00", lock["prospective_lock_timestamp"]) == INELIGIBLE
    assert classify_event(None, lock["prospective_lock_timestamp"]) == INELIGIBLE
    again = stage_prospective()
    assert again["prospective_lock_hash"] == lock["prospective_lock_hash"]
    assert sha256_file(book_path) == book_hash_before
    assert sha256_file(book_path) == lock["page3_book_hash"]
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    assert "No scoring yet. Prospective collection only." in report
    assert "PHASE 8 NOT YET JUSTIFIED BY OUTCOMES" in report


def test_phase7_cli_refuses_policy_and_transfer_member():
    with pytest.raises(AustinError):
        main(["--stage", "prospective", "--policy", "POLICY_A"])
    with pytest.raises(AustinError):
        main(["--stage", "prospective", "--experiment", EXPERIMENT_A])
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE7_ID)
    assert PHASE7_ID not in MEMBERS


def test_phase7_api_and_ui_and_confirmation_still_sealed():
    stage_policy_freeze("NONE")
    from roller.austin.experiments.confirmation_gate.run import stage_confirmation_gate
    from roller.austin.experiments.prospective.run import stage_prospective

    stage_confirmation_gate()
    stage_prospective()
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments

    suite = handle_experiments()
    assert suite["prospective_phase7"]["experiment_id"] == PHASE7_ID
    payload = handle_experiment(PHASE7_ID)
    assert payload["policy_status"] == "NO_POLICY_FROZEN"
    assert payload["execution_enabled"] is False
    assert payload["submits"] is False
    assert payload.get("collection_status") == "ARMED_WAITING_FOR_DATA"
    gate = handle_experiment("AUSTIN_CONFIRMATION_GATE_V1")
    assert gate.get("A_CONFIRMATION_STATUS") == "SEALED_UNSPENT"
    assert gate.get("B_CONFIRMATION_STATUS") == "SEALED_UNSPENT"
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    assert "PHASE 7 · SHADOW RESEARCH" in ui
    assert "NO HISTORICAL BACKFILL" in ui
    assert "ARMED" in ui
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert ">HOLD<" not in ui
