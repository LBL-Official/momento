"""Austin Phase 4 loss-hazard / recovery model. Discovery only. No confirmation. No policy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.beta import jeffreys_estimate, regularized_incomplete_beta
from roller.austin.experiments.hazard.ids import (
    HAZARD_SCHEMA_VERSION,
    MODEL_ID,
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
)
from roller.austin.experiments.hazard.logo import attach_predictions, predict_family
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash as hazard_schema_hash
from roller.austin.experiments.hazard.targets import deeper_distress_next, recovery_horizon, t40_before_recovery
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, MEMBERS, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE4_PHASE, assert_experiment_id
from roller.austin.experiments.manifest import LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH, LOCKED_DISCOVERY_HASH
from roller.austin.experiments.persistence.load import load_confirmation_identity, load_discovery_cohort, refuse_confirmation_path
from roller.austin.experiments.run import main
from roller.austin.paths import downfall_phase3_dir, experiment_dir, hazard_phase4_dir, persistence_phase2_dir, repo_root
from roller.austin.store import load_json

REPO = repo_root()
PKG = REPO / "ROLLER" / "roller" / "austin" / "experiments" / "hazard"


def test_phase2_and_phase3_finalized_markers_do_not_rewrite_results():
    p2 = persistence_phase2_dir()
    p3 = downfall_phase3_dir()
    assert sha256_file(p2 / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(p2 / "statistics.json") == PHASE2_STATISTICS_SHA256
    assert sha256_file(p2 / "MANIFEST.json") == PHASE2_MANIFEST_SHA256
    assert sha256_file(p3 / "REPORT.md") == PHASE3_REPORT_SHA256
    assert sha256_file(p3 / "statistics.json") == PHASE3_STATISTICS_SHA256
    assert schema_hash(state_schema()) == STATE_SCHEMA_HASH
    marker2 = p2 / "FINALIZED.json"
    marker3 = p3 / "FINALIZED.json"
    if marker2.is_file():
        payload = load_json(marker2)
        assert payload["status"] == "FINALIZED"
        assert payload["actionability_gate"] == "NOT_MET"
        assert payload["historical_artifacts_modified"] is False
        assert payload["report_hash"] == PHASE2_REPORT_SHA256
    if marker3.is_file():
        payload = load_json(marker3)
        assert payload["status"] == "COMPLETE"
        assert payload["phase_4_decision"] == "MIXED"
        assert payload["state_schema_hash"] == STATE_SCHEMA_HASH
        assert payload["historical_artifacts_modified"] is False
        assert payload["report_hash"] == PHASE3_REPORT_SHA256
    assert sha256_file(p2 / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(p3 / "REPORT.md") == PHASE3_REPORT_SHA256


def test_model_cohort_and_schema_locks():
    model = verify_model_manifest()
    assert model["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    assert int(model["training_n_trades"]) == 604
    assert int(model["training_n_snapshots"]) == 48752
    assert int(model.get("knn_k") or 25) == 25
    assert schema_hash(state_schema()) == STATE_SCHEMA_HASH
    schema = hazard_schema()
    assert schema["version"] == HAZARD_SCHEMA_VERSION
    assert schema["no_h2_to_h1_fallback"] is True
    assert schema["no_policy"] is True
    digest = hazard_schema_hash(schema)
    assert len(digest) == 64
    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        disc = load_discovery_cohort(eid)
        ident = load_confirmation_identity(eid)
        assert disc["cohort_hash"] == LOCKED_DISCOVERY_HASH[eid]
        assert ident["cohort_hash"] == LOCKED_CONFIRMATION_HASH[eid]


def test_jeffreys_and_n0_unavailable():
    empty = jeffreys_estimate(0, 0)
    assert empty["p_hat"] is None
    assert empty["status"] == "UNAVAILABLE"
    one = jeffreys_estimate(1, 1)
    assert one["p_hat"] == 1.5 / 2.0
    two = jeffreys_estimate(1, 2)
    assert two["p_hat"] == 1.5 / 3.0
    assert two["posterior_lower"] < two["p_hat"] < two["posterior_upper"]
    assert abs(regularized_incomplete_beta(0.5, 1.5, 1.5) - 0.5) < 1e-8


def test_h0_h1_h2_conditioning_and_no_h2_fallback():
    rows = [
        {"trade_id": "t1", "internal_game_id": "g1", "source_experiment_id": "A", "core_state": "WATCH_NEGATIVE", "CI_state": "CI_NEGATIVE", "TARGET_terminal_loss": 1},
        {"trade_id": "t2", "internal_game_id": "g2", "source_experiment_id": "A", "core_state": "WATCH_NEGATIVE", "CI_state": "CI_CROSSES_ZERO", "TARGET_terminal_loss": 0},
        {"trade_id": "t3", "internal_game_id": "g3", "source_experiment_id": "A", "core_state": "HEALTHY", "CI_state": "CI_POSITIVE", "TARGET_terminal_loss": 0},
        {"trade_id": "t4", "internal_game_id": "g4", "source_experiment_id": "A", "core_state": "WATCH_NEGATIVE", "CI_state": "CI_UNAVAILABLE", "TARGET_terminal_loss": 1},
    ]
    h0 = predict_family(rows, family="H0", target="TARGET_terminal_loss")
    h1 = predict_family(rows, family="H1", target="TARGET_terminal_loss")
    h2 = predict_family(rows, family="H2", target="TARGET_terminal_loss")
    rare = next(r for r in h2 if r["trade_id"] == "t4")
    h1_rare = next(r for r in h1 if r["trade_id"] == "t4")
    assert rare["p_hat"] is None
    assert rare["status"] == "UNAVAILABLE"
    assert h1_rare["p_hat"] is not None
    assert rare["p_hat"] != h1_rare["p_hat"]
    assert all(r["same_game_present_in_training"] is False for r in h0 + h1 + h2)
    attached = attach_predictions(rows)
    assert attached[0]["p_terminal_loss_H0"] != attached[0]["p_terminal_loss_H1"] or attached[0]["core_state"] == "WATCH_NEGATIVE"


def test_logo_excludes_same_game():
    rows = [
        {"trade_id": "t1", "internal_game_id": "g1", "source_experiment_id": "A", "core_state": "WATCH_NEGATIVE", "CI_state": "CI_NEGATIVE", "TARGET_terminal_loss": 1},
        {"trade_id": "t1b", "internal_game_id": "g1", "source_experiment_id": "A", "core_state": "PERSISTENCE_2", "CI_state": "CI_NEGATIVE", "TARGET_terminal_loss": 1},
        {"trade_id": "t2", "internal_game_id": "g2", "source_experiment_id": "A", "core_state": "WATCH_NEGATIVE", "CI_state": "CI_NEGATIVE", "TARGET_terminal_loss": 0},
    ]
    preds = predict_family(rows, family="H1", target="TARGET_terminal_loss")
    watch = next(r for r in preds if r["trade_id"] == "t1")
    assert watch["same_game_present_in_training"] is False
    assert watch["p_hat"] == jeffreys_estimate(0, 1)["p_hat"]


def test_recovery_gap_and_t40_not_applicable():
    watch = {"core_state": "WATCH_NEGATIVE", "state_sequence_number": 1}
    healthy = {"core_state": "HEALTHY", "state_sequence_number": 0}
    later_ok = [
        {"state_sequence_number": 2, "core_state": "PERSISTENCE_2", "EV": -4},
        {"state_sequence_number": 3, "core_state": "RECOVERING", "EV": 2},
    ]
    later_gap = [
        {"state_sequence_number": 2, "core_state": "UNRESOLVED", "EV": None},
        {"state_sequence_number": 3, "core_state": "RECOVERING", "EV": 2},
    ]
    assert recovery_horizon(later_ok, watch, 1) == 0
    assert recovery_horizon(later_ok, watch, 2) == 1
    assert recovery_horizon(later_gap, watch, 2) is None
    assert recovery_horizon(later_ok, healthy, 1) == "NOT_APPLICABLE"
    assert deeper_distress_next(later_ok, watch) == 1
    assert deeper_distress_next(later_ok, healthy) == "NOT_APPLICABLE"
    primary = [
        {"t40_already": True, "hit_40_after": False},
        {"t40_already": True, "hit_40_after": False},
        {"t40_already": True, "hit_40_after": False},
        {"t40_already": True, "hit_40_after": False},
    ]
    assert t40_before_recovery(later_ok, watch, primary) == "NOT_APPLICABLE"


def test_hazard_stage_rejects_member_and_policy():
    with pytest.raises(AustinError):
        main(["--stage", "hazard", "--experiment", EXPERIMENT_A])
    with pytest.raises(AustinError):
        main(["--stage", "hazard", "--policy", "POLICY_A"])


def test_no_classifier_policy_threshold_or_dre_score():
    src = "\n".join(p.read_text(encoding="utf-8") for p in PKG.rglob("*.py"))
    assert "sklearn" not in src
    assert "LogisticRegression" not in src
    assert "if p_loss >" not in src
    assert "ENABLE_LIVE_TRADING" not in src
    assert "place_order" not in src
    assert "POLICY_G" not in src
    assert "CRITICAL" not in src
    assert "BOOTSTRAP_SEED = 80" in (REPO / "ROLLER" / "roller" / "austin" / "experiments" / "ids.py").read_text(encoding="utf-8")
    assert "BOOTSTRAP_B = 1000" in (REPO / "ROLLER" / "roller" / "austin" / "experiments" / "ids.py").read_text(encoding="utf-8")


def test_confirmation_untouched_and_phase4_not_a_member():
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments

    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE4_ID)
    assert PHASE4_ID not in MEMBERS
    assert PHASE3_ID not in MEMBERS
    assert PHASE2_ID not in MEMBERS
    suite = handle_experiments()
    assert suite["hazard_phase4"]["model_id"] == PHASE4_ID
    assert suite["downfall_phase3"]["hazard_model_built"] is False
    payload = handle_experiment(PHASE4_ID)
    assert payload["policy_status"] == "UNFROZEN"
    assert payload["confirmation_accessed"] is False
    assert payload["submits"] is False
    assert payload["phase_2_actionability"] == "NOT_MET"
    assert payload["phase_3_result"] == "MIXED"


def test_do_not_touch_live_and_prior_phase_paths():
    assert (REPO / "research" / "choosin_texas" / "library" / "nba_2q_regular_8040_1lot_2026_27" / "book.json").is_file()
    assert (REPO / "apps" / "trading-engine").exists()
    assert (REPO / "crates" / "risk").exists()
    assert list((REPO / "ROLLER").rglob("first80.py"))
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert ">HOLD<" not in ui
    assert "HEDGE" not in ui
    assert "REDUCE" not in ui
    assert "PHASE 4 · LOSS HAZARD / RECOVERY" in ui
    assert "HAZARD MODEL RESEARCH ONLY" in ui
    assert "HAZARD MODEL NOT BUILT" in ui
    assert not (REPO / "research" / "austin" / "experiments" / "AUSTIN_NCAAB_TRANSFER_V1" / "POLICY_FREEZE.json").is_file()
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(downfall_phase3_dir() / "REPORT.md") == PHASE3_REPORT_SHA256


def test_artifacts_after_hazard_if_present():
    root = hazard_phase4_dir()
    if not (root / "MANIFEST.json").is_file():
        pytest.skip("phase 4 artifacts not written yet")
    manifest = load_json(root / "MANIFEST.json")
    assert manifest["model_id"] == MODEL_ID
    assert manifest["phase"] == "PHASE_4"
    assert manifest["confirmation_accessed"] is False
    assert manifest["policy_status"] == "UNFROZEN"
    assert manifest["policy_selected"] == "NONE"
    assert manifest["execution_enabled"] is False
    assert manifest["submits"] is False
    assert manifest["phase_2_actionability"] == "NOT_MET"
    assert manifest["phase_3_result"] == "MIXED"
    assert manifest["phase_4_authorization"] == "EXPLICIT_RESEARCHER_AUTHORIZATION"
    assert manifest["prior"] == "JEFFREYS_0_5_0_5"
    assert manifest["crossfit"] == "LEAVE_ONE_GAME_OUT"
    assert manifest["state_schema_hash"] == STATE_SCHEMA_HASH
    assert manifest["bootstrap_seed"] == 80
    assert manifest["bootstrap_B"] == 1000
    assert manifest["cluster_unit"] == "internal_game_id"
    assert manifest["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    required = [
        "HAZARD_SCHEMA.json",
        "hazard_state_entries.csv",
        "hazard_predictions_H0.csv",
        "hazard_predictions_H1.csv",
        "hazard_predictions_H2.csv",
        "hazard_by_state.csv",
        "hazard_by_state_ci.csv",
        "loss_calibration.csv",
        "recovery_t1_calibration.csv",
        "recovery_t2_calibration.csv",
        "recovery_t3_calibration.csv",
        "model_metrics.csv",
        "model_comparison.csv",
        "hazard_trajectories.csv",
        "transition_risk_analysis.csv",
        "loss_risk_vs_ev.csv",
        "support_analysis.csv",
        "hazard_timing.csv",
        "t40_before_recovery.csv",
        "recovery_missingness.csv",
        "statistics.json",
        "model_hash_audit.json",
        "state_schema_audit.json",
        "cohort_hash_audit.json",
        "leakage_audit.json",
        "crossfit_audit.json",
        "confirmation_protection_audit.json",
        "phase2_finalization_audit.json",
        "phase3_finalization_audit.json",
        "REPORT.md",
    ]
    for name in required:
        assert (root / name).is_file(), name
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    assert "holy grail" not in report.lower()
    assert "austin works" not in report.lower()
    assert "live ready" not in report.lower()
    assert "POLICY UNFROZEN" in report
    assert "CONFIRMATION UNTOUCHED" in report
    assert "PHASE 5 — NOT STARTED" in report
    assert "if p_loss >" not in report
    stats = load_json(root / "statistics.json")
    assert stats["confirmation_accessed"] is False
    assert stats["A"]["experiment_id"] == EXPERIMENT_A
    assert stats["B"]["experiment_id"] == EXPERIMENT_B
    assert stats["interpretation"]["gate_a_probability_validity"] == "PASS"
    leak = load_json(root / "leakage_audit.json")
    assert leak["status"] == "PASS"
    xf = load_json(root / "crossfit_audit.json")
    assert xf["same_game_present_in_training"] is False
    import csv

    entries = list(csv.DictReader((root / "hazard_state_entries.csv").open(encoding="utf-8")))
    keys = [(r["source_experiment_id"], r["trade_id"], r["core_state"]) for r in entries]
    assert len(keys) == len(set(keys))
    assert all(r.get("phase_id") == PHASE4_PHASE for r in entries)
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(downfall_phase3_dir() / "REPORT.md") == PHASE3_REPORT_SHA256
    assert sha256_file(persistence_phase2_dir() / "statistics.json") == PHASE2_STATISTICS_SHA256
    assert sha256_file(downfall_phase3_dir() / "statistics.json") == PHASE3_STATISTICS_SHA256
