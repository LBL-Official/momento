"""Austin Phase 5B freeze gate. UNSET cannot freeze. Confirmation untouched."""

from __future__ import annotations

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.ids import (
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
)
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash as hazard_schema_hash
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, PHASE5_ID
from roller.austin.experiments.manifest import LOCKED_HASHES, LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH, LOCKED_DISCOVERY_HASH
from roller.austin.experiments.persistence.load import refuse_confirmation_path
from roller.austin.experiments.policy_v2.freeze import stage_policy_freeze
from roller.austin.experiments.policy_v2.frozen import evaluate_frozen_dre_policy, first_fire_frozen, freeze_object_hash
from roller.austin.experiments.policy_v2.ids import HAZARD_SCHEMA_HASH
from roller.austin.experiments.policy_v2.phase5a_lock import CANDIDATE_REGISTRY_HASH, PHASE5A_FILE_HASHES, PHASE5A_REQUIRED
from roller.austin.experiments.run import main
from roller.austin.paths import downfall_phase3_dir, experiment_dir, hazard_phase4_dir, persistence_phase2_dir, policy_phase5_dir, repo_root
from roller.austin.store import load_json

REPO = repo_root()
PKG = REPO / "ROLLER" / "roller" / "austin" / "experiments" / "policy_v2"


def test_prior_phase_and_model_locks_unchanged():
    p2 = persistence_phase2_dir()
    p3 = downfall_phase3_dir()
    p4 = hazard_phase4_dir()
    assert sha256_file(p2 / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(p2 / "statistics.json") == PHASE2_STATISTICS_SHA256
    assert sha256_file(p2 / "MANIFEST.json") == PHASE2_MANIFEST_SHA256
    assert load_json(p2 / "statistics.json")["interpretation"]["phase_3_justified"] is False
    assert sha256_file(p3 / "REPORT.md") == PHASE3_REPORT_SHA256
    assert sha256_file(p3 / "statistics.json") == PHASE3_STATISTICS_SHA256
    assert schema_hash(state_schema()) == STATE_SCHEMA_HASH
    assert load_json(p4 / "statistics.json")["interpretation"]["phase_4_complete"] is True
    assert load_json(p4 / "MANIFEST.json")["hazard_schema_hash"] == HAZARD_SCHEMA_HASH
    assert hazard_schema_hash(hazard_schema()) == HAZARD_SCHEMA_HASH
    model = verify_model_manifest()
    assert model["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    for name, expected in LOCKED_HASHES.items():
        assert model["hashes"][name] == expected
    root = policy_phase5_dir()
    for name, expected in PHASE5A_FILE_HASHES.items():
        assert sha256_file(root / name) == expected, name
    assert sha256_file(root / "POLICY_CANDIDATES.json") == CANDIDATE_REGISTRY_HASH


def test_unset_cannot_create_freeze_and_writes_readiness():
    payload = stage_policy_freeze("UNSET")
    root = policy_phase5_dir()
    assert payload["human_selected_policy"] == "UNSET"
    assert payload["phase5a_proposed_policy"] == "NONE"
    assert payload["human_freeze_justified"] == "NOT_SUPPORTED"
    assert payload["policy_freeze_created"] is False
    assert payload["closing"] == "AWAITING HUMAN POLICY SELECTION"
    assert not (root / "POLICY_FREEZE.json").is_file()
    assert not (root / "PHASE6_CONTRACT.json").is_file()
    decision = load_json(root / "POLICY_DECISION.json")
    assert decision["human_selected_policy"] == "UNSET"
    assert decision["phase5a_proposed_policy"] == "NONE"
    assert decision["policy_freeze_created"] is False
    assert decision["confirmation_accessed"] is False
    assert decision["phase6_started"] is False
    text = (root / "FREEZE_READINESS.md").read_text(encoding="utf-8")
    assert "AWAITING HUMAN POLICY SELECTION" in text
    assert "FREEZE NOT READY" in text
    assert "Phase 6 started?: NO" in text
    for name, expected in PHASE5A_FILE_HASHES.items():
        assert sha256_file(root / name) == expected, name


def test_none_and_unknown_and_evidence_block():
    with pytest.raises(AustinError):
        stage_policy_freeze("POLICY_A")
    with pytest.raises(AustinError):
        stage_policy_freeze("DRE_NOT_A_CANDIDATE")
    payload = stage_policy_freeze("NONE")
    root = policy_phase5_dir()
    assert payload["human_selected_policy"] == "NONE"
    assert payload["policy_freeze_created"] is False
    assert not (root / "POLICY_FREEZE.json").is_file()
    blocked = stage_policy_freeze("DRE_C1_WATCH_LOSS_GE_0P2")
    assert blocked["closing"] == "POLICY FREEZE BLOCKED BY PHASE 5A EVIDENCE"
    assert blocked["policy_freeze_created"] is False
    assert not (root / "POLICY_FREEZE.json").is_file()
    restored = stage_policy_freeze("NONE")
    assert restored["human_selected_policy"] == "NONE"
    assert load_json(root / "POLICY_DECISION.json")["human_selected_policy"] == "NONE"


def test_proposed_is_not_human_approval_and_cli_refuses_old_policy():
    with pytest.raises(AustinError):
        main(["--stage", "policy-freeze", "--policy", "POLICY_A"])
    with pytest.raises(AustinError):
        main(["--stage", "policy-freeze", "--experiment", EXPERIMENT_A])
    src = "\n".join(p.read_text(encoding="utf-8") for p in PKG.rglob("*.py"))
    assert "do not infer" in src.lower() or "UNSET" in src
    assert "stage_confirmation" not in (PKG / "freeze.py").read_text(encoding="utf-8")


def test_frozen_policy_function_fail_closed_and_first_fire():
    candidate = load_json(policy_phase5_dir() / "POLICY_CANDIDATES.json")["candidates"][0]
    frozen = {"candidate_definition": candidate, "policy_freeze_hash": "deadbeef"}
    with pytest.raises(AustinError):
        evaluate_frozen_dre_policy(frozen, {"core_state": "WATCH_NEGATIVE", "p_terminal_loss_H1": 0.3, "support_n_terminal_loss_H1": 20})
    honest = {"candidate_definition": candidate}
    honest["policy_freeze_hash"] = freeze_object_hash(honest)
    assert evaluate_frozen_dre_policy(honest, {"core_state": "UNRESOLVED"})["action"] == "NONE"
    missing = evaluate_frozen_dre_policy(
        honest,
        {"core_state": "WATCH_NEGATIVE", "p_terminal_loss_H1": None, "support_n_terminal_loss_H1": 20},
    )
    assert missing["action"] == "NONE"
    assert missing["reason"] == "REQUIRED_HAZARD_UNAVAILABLE"
    fire = {
        "core_state": "WATCH_NEGATIVE",
        "p_terminal_loss_H1": 0.4,
        "support_n_terminal_loss_H1": 20,
        "support_state": "OBSERVED",
        "TARGET_terminal_loss": 1,
        "won": False,
        "t40_already": False,
        "state_sequence_number": 1,
    }
    assert evaluate_frozen_dre_policy(honest, fire)["action"] == "INTERVENE"
    later = {**fire, "state_sequence_number": 2}
    seq = first_fire_frozen(honest, [fire, later])
    assert seq[0]["action"] == "INTERVENE"
    assert seq[1]["action"] == "NONE"
    assert seq[1]["reason"] == "IGNORED_FOR_FIRST_FIRE"
    mutated = {**fire, "TARGET_terminal_loss": 0, "won": True, "future_EV": 99}
    assert evaluate_frozen_dre_policy(honest, mutated)["action"] == "INTERVENE"


def test_confirmation_untouched_and_live_paths():
    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    assert not (REPO / "research" / "austin" / "experiments" / "AUSTIN_NCAAB_TRANSFER_V1" / "POLICY_FREEZE.json").is_file()
    assert LOCKED_DISCOVERY_HASH[EXPERIMENT_A]
    assert LOCKED_CONFIRMATION_HASH[EXPERIMENT_B]
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    assert "PHASE 5B · POLICY FREEZE" in ui
    assert "POLICY FREEZE GATE" in ui
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert ">HOLD<" not in ui
    assert (REPO / "research" / "choosin_texas" / "library" / "nba_2q_regular_8040_1lot_2026_27" / "book.json").is_file()
    assert (REPO / "apps" / "trading-engine").exists()
    assert (REPO / "crates" / "risk").exists()
    from roller.austin.experiments.artifacts import handle_experiment

    payload = handle_experiment(PHASE5_ID)
    assert payload["confirmation_accessed"] is False
    assert payload["phase_6_status"] in {"NOT STARTED", "BLOCKED_NO_FROZEN_POLICY"}
    assert payload["submits"] is False
    assert payload.get("human_selected_policy") == "NONE"
    decision = load_json(policy_phase5_dir() / "POLICY_DECISION.json")
    assert decision["human_decision_status"] == "NO_POLICY_SELECTED"
    assert decision["policy_status"] == "NO_POLICY_FROZEN"
    assert decision["phase6_authorized"] is False
    assert decision["confirmation_A"] == "NOT_RUN"
    assert decision["confirmation_B"] == "NOT_RUN"
    finalized = load_json(policy_phase5_dir() / "PHASE5_FINALIZED.json")
    assert finalized["status"] == "FINALIZED"
    assert finalized["policy_frozen"] is False
    assert finalized["confirmation_spend_authorized"] is False
    assert finalized["next_waterfall_stage"] == "PHASE_6_CONFIRMATION_GATE"
    assert finalized["confirmation_expected_action"] == "PRESERVE_UNTOUCHED"
    assert finalized.get("phase5_finalization_hash")
    closeout = (policy_phase5_dir() / "PHASE5B_CLOSEOUT.md").read_text(encoding="utf-8")
    assert "C1/C2 fired" in closeout
    assert "C3/C4 never fired" in closeout
    assert "Researcher selected NONE" in closeout
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    assert payload.get("phase5_finalized_status") == "FINALIZED"
    assert payload.get("closeout_policy_status") == "NO_POLICY_FROZEN"
    stage_policy_freeze("NONE")
