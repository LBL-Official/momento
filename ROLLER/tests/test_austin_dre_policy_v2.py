"""Austin Phase 5A DRE policy preregistration. Discovery only. No freeze. No confirmation."""

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
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, MEMBERS, PHASE2_ID, PHASE3_ID, PHASE4_ID, PHASE5_ID, assert_experiment_id
from roller.austin.experiments.manifest import LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH, LOCKED_DISCOVERY_HASH
from roller.austin.experiments.persistence.load import load_confirmation_identity, load_discovery_cohort, refuse_confirmation_path
from roller.austin.experiments.policy_v2.candidates import candidate_registry, candidates
from roller.austin.experiments.policy_v2.decide import decide
from roller.austin.experiments.policy_v2.ids import DISTRESS_STATES, HAZARD_SCHEMA_HASH
from roller.austin.experiments.policy_v2.preflight import phase4_preflight
from roller.austin.experiments.run import main
from roller.austin.paths import (
    downfall_phase3_dir,
    experiment_dir,
    hazard_phase4_dir,
    persistence_phase2_dir,
    policy_phase5_dir,
    repo_root,
)
from roller.austin.store import load_json

REPO = repo_root()
PKG = REPO / "ROLLER" / "roller" / "austin" / "experiments" / "policy_v2"


def _watch_entry(**extra):
    row = {
        "core_state": "WATCH_NEGATIVE",
        "CI_state": "CI_NEGATIVE",
        "support_state": "OBSERVED",
        "p_terminal_loss_H1": 0.25,
        "p_recovery_t1_H1": 0.10,
        "support_n_terminal_loss_H1": 20,
        "support_n_recovery_t1_H1": 20,
        "t40_already": False,
        "TARGET_terminal_loss": 0,
        "won": True,
    }
    row.update(extra)
    return row


def test_phase2_phase3_phase4_complete_before_phase5():
    p2 = persistence_phase2_dir()
    p3 = downfall_phase3_dir()
    p4 = hazard_phase4_dir()
    assert sha256_file(p2 / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(p2 / "statistics.json") == PHASE2_STATISTICS_SHA256
    assert sha256_file(p2 / "MANIFEST.json") == PHASE2_MANIFEST_SHA256
    assert sha256_file(p3 / "REPORT.md") == PHASE3_REPORT_SHA256
    assert sha256_file(p3 / "statistics.json") == PHASE3_STATISTICS_SHA256
    assert schema_hash(state_schema()) == STATE_SCHEMA_HASH
    assert (p4 / "MANIFEST.json").is_file()
    stats = load_json(p4 / "statistics.json")
    assert stats["interpretation"]["phase_4_complete"] is True
    assert stats["interpretation"]["phase_5_classification"] == "MIXED"
    assert load_json(p4 / "MANIFEST.json")["hazard_schema_hash"] == HAZARD_SCHEMA_HASH
    assert hazard_schema_hash(hazard_schema()) == HAZARD_SCHEMA_HASH
    gate = phase4_preflight()
    assert gate["status"] == "PASS"
    assert gate["phase_4_complete"] is True
    assert gate["phase_5_classification"] == "MIXED"


def test_model_state_hazard_and_cohort_locks():
    model = verify_model_manifest()
    assert model["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    assert int(model["training_n_trades"]) == 604
    assert int(model["training_n_snapshots"]) == 48752
    assert int(model.get("knn_k") or 25) == 25
    assert schema_hash(state_schema()) == STATE_SCHEMA_HASH
    assert hazard_schema_hash(hazard_schema()) == HAZARD_SCHEMA_HASH
    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        disc = load_discovery_cohort(eid)
        ident = load_confirmation_identity(eid)
        assert disc["cohort_hash"] == LOCKED_DISCOVERY_HASH[eid]
        assert ident["cohort_hash"] == LOCKED_CONFIRMATION_HASH[eid]


def test_candidate_registry_is_small_and_pit_only():
    family = candidates()
    assert 1 <= len(family) <= 4
    registry = candidate_registry()
    assert registry["no_policy_a_f"] is True
    assert registry["no_ev_threshold"] is True
    assert registry["no_h2_fallback"] is True
    assert registry["t40_already_semantic"] == "ALLOW_TRIGGER_CLASSIFY_TOO_LATE"
    forbidden = {
        "POLICY_A",
        "POLICY_B",
        "POLICY_C",
        "POLICY_D",
        "POLICY_E",
        "POLICY_F",
        "future_T40",
        "eventual",
        "EV_threshold",
    }
    blob = str(registry)
    for word in forbidden:
        assert word not in blob
    for cand in family:
        assert set(cand["required_core_states"]).issubset(set(DISTRESS_STATES))
        assert cand["first_fire_behavior"]
        assert cand["missing_value_behavior"] == "NONE"


def test_decide_forbidden_missing_first_fire_and_no_future():
    cand = next(c for c in candidates() if c["candidate_id"] == "DRE_C3_DISTRESS_TWO_SIDED")
    healthy = decide(cand, _watch_entry(core_state="HEALTHY"))
    assert healthy["action"] == "NONE"
    assert healthy["reason"] == "FORBIDDEN_STATE"
    missing = decide(cand, _watch_entry(p_terminal_loss_H1=None))
    assert missing["action"] == "NONE"
    assert missing["reason"] == "REQUIRED_HAZARD_UNAVAILABLE"
    low = decide(cand, _watch_entry(support_n_terminal_loss_H1=3))
    assert low["action"] == "NONE"
    assert low["reason"] == "SUPPORT_BELOW_MINIMUM"
    fire = decide(cand, _watch_entry())
    assert fire["action"] == "INTERVENE"
    late = decide(cand, _watch_entry(t40_already=True))
    assert late["action"] == "INTERVENE"
    assert late["timing_class"] == "TOO_LATE"
    mutated = _watch_entry(TARGET_terminal_loss=1, won=False, OUTCOME_eventual_result="LOSS")
    assert decide(cand, mutated) == fire
    from roller.austin.experiments.policy_v2.economics import first_fire

    entries = [
        _watch_entry(source_experiment_id="A", trade_id="t1", state_sequence_number=1, core_state="WATCH_NEGATIVE"),
        _watch_entry(source_experiment_id="A", trade_id="t1", state_sequence_number=2, core_state="PERSISTENCE_2"),
    ]
    events = first_fire(entries, cand)
    assert len(events) == 1
    assert events[0]["action"] == "INTERVENE"
    assert events[0]["entry"]["state_sequence_number"] == 1


def test_policy_stage_rejects_member_and_historical_policy():
    with pytest.raises(AustinError):
        main(["--stage", "policy", "--experiment", EXPERIMENT_A])
    with pytest.raises(AustinError):
        main(["--stage", "policy", "--policy", "POLICY_A"])
    with pytest.raises(AustinError):
        main(["--stage", "policy", "--policy", "POLICY_E"])


def test_ncaab_query_only_and_no_retrain_or_confirmation():
    src = "\n".join(p.read_text(encoding="utf-8") for p in PKG.rglob("*.py"))
    assert "POLICY_FAMILY" not in src
    assert "stage_confirmation" not in src
    assert "POLICY_FREEZE.json" in src
    assert "fit(" not in src
    assert "ENABLE_LIVE_TRADING" not in src
    assert "place_order" not in src
    assert "H2_2" not in src or "absent" in src.lower() or "forbidden" in src.lower()
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments

    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE5_ID)
    assert PHASE5_ID not in MEMBERS
    assert PHASE4_ID not in MEMBERS
    assert PHASE3_ID not in MEMBERS
    assert PHASE2_ID not in MEMBERS
    suite = handle_experiments()
    assert suite["dre_policy_phase5a"]["policy_object"] == PHASE5_ID
    assert suite["dre_policy_phase5a"]["policy_status"] in {"UNFROZEN", "NO_POLICY_FROZEN"}
    assert suite["dre_policy_phase5a"]["policy_status"] != "FROZEN"
    payload = handle_experiment(PHASE5_ID)
    assert payload["policy_status"] in {"UNFROZEN", "NO_POLICY_FROZEN"}
    assert payload["policy_status"] != "FROZEN"
    assert payload["policy_selected"] == "NONE"
    assert payload["confirmation_accessed"] is False
    assert payload["submits"] is False
    assert payload["confirmation_A"] == "NOT RUN"
    assert payload["confirmation_B"] == "NOT RUN"


def test_do_not_touch_live_or_prior_phase_paths():
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
    assert "PHASE 5A · DRE POLICY PREREGISTRATION" in ui
    assert "DISCOVERY ONLY" in ui
    assert "POLICY UNFROZEN" in ui
    assert "CONFIRMATION UNTOUCHED" in ui
    assert "SCENARIO ≠ FILL" in ui
    assert "EXECUTION DISABLED" in ui
    assert not (REPO / "research" / "austin" / "experiments" / "AUSTIN_NCAAB_TRANSFER_V1" / "POLICY_FREEZE.json").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(downfall_phase3_dir() / "REPORT.md") == PHASE3_REPORT_SHA256
    assert sha256_file(hazard_phase4_dir() / "HAZARD_SCHEMA.json")
    assert load_json(hazard_phase4_dir() / "MANIFEST.json")["hazard_schema_hash"] == HAZARD_SCHEMA_HASH


def test_artifacts_after_policy_if_present():
    root = policy_phase5_dir()
    if not (root / "MANIFEST.json").is_file():
        pytest.skip("phase 5A artifacts not written yet")
    manifest = load_json(root / "MANIFEST.json")
    assert manifest["phase"] == "PHASE_5A"
    assert manifest["policy_object"] == PHASE5_ID
    assert manifest["confirmation_accessed"] is False
    assert manifest["policy_status"] == "UNFROZEN"
    assert manifest["policy_selected"] == "NONE"
    assert manifest["execution_enabled"] is False
    assert manifest["submits"] is False
    assert manifest["hazard_schema_hash"] == HAZARD_SCHEMA_HASH
    assert manifest["state_schema_hash"] == STATE_SCHEMA_HASH
    assert manifest["Austin_manifest_hash"] == LOCKED_MANIFEST_HASH
    assert manifest["bootstrap_seed"] == 80
    assert manifest["bootstrap_B"] == 1000
    assert manifest["cluster_unit"] == "internal_game_id"
    assert not (root / "POLICY_FREEZE.json").is_file()
    required = [
        "MANIFEST.json",
        "POLICY_CANDIDATES.json",
        "candidate_discovery_events.csv",
        "candidate_economics_A.csv",
        "candidate_economics_B.csv",
        "candidate_comparison.csv",
        "first_intervention_events.csv",
        "timing_analysis.csv",
        "winner_sacrifice_analysis.csv",
        "loss_avoidance_analysis.csv",
        "dre_value_added.csv",
        "statistics.json",
        "model_lock_audit.json",
        "phase2_finalization_audit.json",
        "phase3_finalization_audit.json",
        "phase4_finalization_audit.json",
        "hazard_schema_audit.json",
        "cohort_hash_audit.json",
        "leakage_audit.json",
        "confirmation_protection_audit.json",
        "candidate_registry_audit.json",
        "REPORT.md",
    ]
    for name in required:
        assert (root / name).is_file(), name
    registry_hash = sha256_file(root / "POLICY_CANDIDATES.json")
    assert manifest["candidate_registry_hash"] == registry_hash
    audit = load_json(root / "candidate_registry_audit.json")
    assert audit["candidate_registry_hash"] == registry_hash
    assert audit["n_candidates"] <= 4
    assert audit["immutable_after_economics"] is True
    registry = load_json(root / "POLICY_CANDIDATES.json")
    assert len(registry["candidates"]) <= 4
    ids = [c["candidate_id"] for c in registry["candidates"]]
    assert "POLICY_A" not in ids
    stats = load_json(root / "statistics.json")
    assert stats["confirmation_accessed"] is False
    assert stats["policy_status"] == "UNFROZEN"
    assert stats["policy_selected"] == "NONE"
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    assert "holy grail" not in report.lower()
    assert "live ready" not in report.lower()
    assert "POLICY UNFROZEN" in report
    assert "CONFIRMATION UNTOUCHED" in report
    assert "DISCOVERY ONLY" in report
    assert "PROPOSED_POLICY" in report
    assert "HUMAN_FREEZE_JUSTIFIED" in report
    leak = load_json(root / "leakage_audit.json")
    assert leak["status"] == "PASS"
    conf = load_json(root / "confirmation_protection_audit.json")
    assert conf["confirmation_accessed"] is False
    import csv

    firsts = list(csv.DictReader((root / "first_intervention_events.csv").open(encoding="utf-8")))
    keys = [(r["source_experiment_id"], r["trade_id"], r["candidate_id"]) for r in firsts]
    assert len(keys) == len(set(keys))
    assert all(r["action"] == "INTERVENE" for r in firsts)
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(downfall_phase3_dir() / "REPORT.md") == PHASE3_REPORT_SHA256
    assert load_json(hazard_phase4_dir() / "MANIFEST.json")["hazard_schema_hash"] == HAZARD_SCHEMA_HASH
