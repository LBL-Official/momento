"""Persistence mechanism audit. Discovery only. No confirmation. No policy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import AUDIT_ID, EXPERIMENT_A, EXPERIMENT_B, PHASE2_ID
from roller.austin.experiments.manifest import LOCKED_MANIFEST_HASH, verify_model_manifest
from roller.austin.experiments.persistence.events import (
    classify_negative,
    first_negative_row,
    later_after,
    pit_descriptors,
    primary_rows,
)
from roller.austin.experiments.persistence.ids import (
    FORBIDDEN_PIT_KEYS,
    LANDMARK_T0,
    LANDMARK_T0_ONLY,
    LANDMARK_T0_T1,
    LANDMARK_T0_T1_T2,
    LANDMARK_T0_T1_T2_T3,
    PERSISTENT_NEGATIVE_EV,
    TEMPORARY_NEGATIVE_EV,
    UNRESOLVED_NO_LATER_VALID_EV,
)
from roller.austin.experiments.persistence.landmarks import assign_landmarks, landmark_states
from roller.austin.experiments.persistence.load import refuse_confirmation_path
from roller.austin.experiments.persistence.trajectories import build_trajectory, ev_area_below_zero
from roller.austin.experiments.run import main
from roller.austin.paths import experiment_dir, persistence_audit_dir, persistence_phase2_dir, repo_root
from roller.austin.store import load_snapshots

REPO = repo_root()
TS0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def _q(trade_id: str, ev, *, period=1, remaining=600, primary=True, ts=None, **kwargs):
    row = {
        "trade_id": trade_id,
        "primary": primary,
        "conditional_ev_cents": ev,
        "period": period,
        "game_clock_remaining": remaining,
        "timestamp_utc": (ts or TS0).isoformat(),
        "current_price_cents": kwargs.get("price", 70),
        "ci_lower_cents": kwargs.get("lo", -10),
        "ci_upper_cents": kwargs.get("hi", 4),
        "ev_at_entry": kwargs.get("ev_entry", 8),
        "price_travel": kwargs.get("price_travel", -10),
        "time_since_entry": kwargs.get("time_since_entry", 120),
        "effective_sample_size": 12,
        "mean_distance": 1.2,
        "median_distance": 1.1,
        "feature_coverage": 0.9,
        "support_status": "OBSERVED",
        "availability_status": "VALUE" if ev is not None else "UNAVAILABLE",
        "t40_already": False,
        "hit_40_after": False,
        "home_score": 40,
        "away_score": 38,
    }
    row.update({k: v for k, v in kwargs.items() if k not in row})
    return row


def test_baseline_model_and_snapshots_locked():
    model = verify_model_manifest()
    assert model["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    assert int(model["training_n_snapshots"]) == 48752
    assert int(model["training_n_trades"]) == 604
    assert model["ncaab_used_for_training"] is False
    assert len(load_snapshots()) == 48752


def test_source_cohort_hashes_and_no_h2_2():
    from roller.austin.experiments.persistence.load import load_discovery_cohort, load_confirmation_identity

    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        disc = load_discovery_cohort(eid)
        ident = load_confirmation_identity(eid)
        assert disc["cohort_hash"]
        assert ident["cohort_hash"]
        assert all(t.get("slice") != "H2_2" for t in disc["trades"])
        assert ident["role"] == "CONFIRMATION"


def test_confirmation_result_path_refused():
    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)


def test_first_negative_is_earliest_valid_primary():
    rows = [
        _q("t1", None, remaining=720),
        _q("t1", 4.0, remaining=600),
        _q("t1", -3.0, remaining=480),
        _q("t1", -5.0, remaining=360),
        _q("t1", -1.0, remaining=420, primary=False),
    ]
    primary = primary_rows(rows, "t1")
    first = first_negative_row(primary)
    assert first is not None
    assert first["game_clock_remaining"] == 480
    assert first["conditional_ev_cents"] == -3.0


def test_diagnostic_rows_cannot_be_first_negative():
    rows = [_q("t1", -9.0, remaining=600, primary=False), _q("t1", 2.0, remaining=480)]
    assert first_negative_row(primary_rows(rows, "t1")) is None


def test_class_rules_and_missing_not_persistent():
    t0 = _q("t1", -4.0, remaining=600)
    recover = _q("t1", 1.0, remaining=480)
    stay = _q("t1", -2.0, remaining=360)
    assert classify_negative([recover]) == TEMPORARY_NEGATIVE_EV
    assert classify_negative([stay]) == PERSISTENT_NEGATIVE_EV
    assert classify_negative([]) == UNRESOLVED_NO_LATER_VALID_EV
    later = later_after([t0], t0)
    assert later == []


def test_no_interpolation_of_t1_t2():
    first = _q("t1", -4.0, remaining=600)
    t1 = _q("t1", -2.0, remaining=480)
    event = {
        "_first": first,
        "_later_valid": [t1],
        "negative_ev_class": PERSISTENT_NEGATIVE_EV,
    }
    flags = assign_landmarks(event)
    assert flags[LANDMARK_T0_T1] is True
    assert flags[LANDMARK_T0_ONLY] is False
    empty = {"_first": first, "_later_valid": [], "negative_ev_class": UNRESOLVED_NO_LATER_VALID_EV}
    flags2 = assign_landmarks(empty)
    assert flags2[LANDMARK_T0_ONLY] is False
    assert flags2[LANDMARK_T0_T1] is False
    assert flags2[LANDMARK_T0_T1_T2] is False
    assert flags2[LANDMARK_T0_T1_T2_T3] is False
    assert flags[LANDMARK_T0] is True
    assert flags2[LANDMARK_T0] is True
    states = landmark_states(event)
    assert states["t2"] is None
    assert states["t3"] is None


def test_pit_excludes_outcomes_and_labels():
    first = _q("t1", -6.0, remaining=600)
    pit = pit_descriptors(first, previous_valid_ev=3.0, ev_entry=5.0, ev_entry_row=first)
    assert pit["first_negative_EV"] == -6.0
    assert pit["EV_DEPTH_BELOW_ZERO"] == 6.0
    assert set(pit) & FORBIDDEN_PIT_KEYS == set()
    assert "won" not in pit
    assert "future_MAE" not in pit
    assert "negative_ev_class" not in pit


def test_ev_area_formula_skips_gaps():
    points = [
        {"EV": -10.0, "period": 1, "clock": 600},
        {"EV": -10.0, "period": 1, "clock": 480},
        {"EV": 4.0, "period": 1, "clock": 360},
    ]
    area = ev_area_below_zero(points)
    assert area is not None
    assert area > 0
    assert ev_area_below_zero([points[0]]) is None


def test_persist_stage_rejects_member_experiment():
    with pytest.raises(AustinError):
        main(["--stage", "persist", "--experiment", EXPERIMENT_A])


def test_persist_does_not_create_policy_or_freeze():
    src = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (REPO / "ROLLER" / "roller" / "austin" / "experiments" / "persistence").rglob("*.py")
    )
    assert "POLICY_G =" not in src
    assert '"POLICY_G"' not in src
    assert "PERSISTENCE_POLICY" not in src
    assert "from roller.austin.query import query_match" not in src
    assert "query_match(" not in src
    assert "ENABLE_LIVE_TRADING" not in src
    report = persistence_audit_dir() / "REPORT.md"
    if report.is_file():
        text = report.read_text(encoding="utf-8").lower()
        assert "holy grail" not in text
        assert "live ready" not in text
        assert "austin works" not in text
    assert not (REPO / "research" / "austin" / "experiments" / "AUSTIN_NCAAB_TRANSFER_V1" / "POLICY_FREEZE.json").is_file()


def test_do_not_touch_paths():
    assert (REPO / "research" / "choosin_texas" / "library" / "nba_2q_regular_8040_1lot_2026_27" / "book.json").is_file()
    assert (REPO / "apps" / "trading-engine").exists()
    assert (REPO / "crates" / "risk").exists()
    first80 = list((REPO / "ROLLER").rglob("first80.py"))
    assert first80
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert "PERSISTENCE MECHANISM AUDIT" in ui
    assert "PHASE 2 · PERSISTENCE MECHANISM" in ui
    assert "DISCOVERY ONLY" in ui
    assert "POLICY UNFROZEN" in ui
    assert "CONFIRMATION UNTOUCHED" in ui


def test_one_first_negative_row_per_trade():
    import csv

    path = persistence_audit_dir() / "first_negative_events.csv"
    if not path.is_file():
        pytest.skip("persist artifacts not written yet")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    ids = [(r["source_experiment_id"], r["trade_id"]) for r in rows]
    assert len(ids) == len(set(ids))
    assert sum(1 for r in rows if r["source_experiment_id"] == EXPERIMENT_A) == 67
    assert sum(1 for r in rows if r["source_experiment_id"] == EXPERIMENT_B) == 22


def test_artifacts_after_persist_if_present():
    root = persistence_audit_dir()
    if not (root / "MANIFEST.json").is_file():
        pytest.skip("persist artifacts not written yet")
    from roller.austin.store import load_json

    manifest = load_json(root / "MANIFEST.json")
    assert manifest["audit_id"] == AUDIT_ID
    assert manifest["confirmation_accessed"] is False
    assert manifest["policy_status"] == "UNFROZEN"
    assert manifest["policy_selected"] == "NONE"
    assert manifest["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    required = [
        "first_negative_events.csv",
        "negative_ev_trajectories.csv",
        "persistence_summary.csv",
        "persistence_landmarks.csv",
        "pit_feature_comparison.csv",
        "trajectory_feature_comparison.csv",
        "warning_persistence_timing.csv",
        "h2_1_alignment_audit.csv",
        "h2_1_alignment_examples.csv",
        "statistics.json",
        "leakage_audit.json",
        "confirmation_protection_audit.json",
        "model_hash_audit.json",
        "cohort_hash_audit.json",
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
    assert not (experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv").is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()


def test_velocity_unavailable_without_enough_points():
    first = _q("t1", -4.0, remaining=600)
    event = {
        "trade_id": "t1",
        "internal_game_id": "g1",
        "source_experiment_id": EXPERIMENT_A,
        "first_negative_EV": -4.0,
        "negative_ev_class": UNRESOLVED_NO_LATER_VALID_EV,
        "_first": first,
        "_later_valid": [],
    }
    traj = build_trajectory(event)
    assert len(traj) == 1
    assert traj[0]["EV_VELOCITY"] is None
    assert traj[0]["EV_ACCELERATION"] is None
    assert traj[0]["EV_DEPTH"] == 4.0


def test_api_audit_id_is_not_a_member():
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments
    from roller.austin.experiments.ids import MEMBERS, assert_experiment_id

    with pytest.raises(AustinError):
        assert_experiment_id(AUDIT_ID)
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE2_ID)
    assert AUDIT_ID not in MEMBERS
    assert PHASE2_ID not in MEMBERS
    suite = handle_experiments()
    assert suite["persistence_audit"]["audit_id"] == AUDIT_ID
    assert suite["persistence_phase2"]["audit_id"] == PHASE2_ID
    payload = handle_experiment(AUDIT_ID)
    assert payload["policy_status"] == "UNFROZEN"
    assert payload["confirmation_accessed"] is False
    assert payload["submits"] is False
    phase = handle_experiment(PHASE2_ID)
    assert phase["policy_status"] == "UNFROZEN"
    assert phase["confirmation_accessed"] is False
    assert phase["submits"] is False


def test_phase2_artifacts_after_persist_if_present():
    root = persistence_phase2_dir()
    if not (root / "MANIFEST.json").is_file():
        pytest.skip("phase 2 artifacts not written yet")
    from roller.austin.store import load_json

    manifest = load_json(root / "MANIFEST.json")
    assert manifest["audit_id"] == PHASE2_ID
    assert manifest["confirmation_accessed"] is False
    assert manifest["policy_status"] == "UNFROZEN"
    assert manifest["policy_selected"] == "NONE"
    assert manifest["execution_enabled"] is False
    assert manifest["submits"] is False
    assert manifest["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    required = [
        "first_negative_events.csv",
        "negative_ev_trajectories.csv",
        "persistence_summary.csv",
        "persistence_landmarks.csv",
        "pit_feature_comparison.csv",
        "trajectory_feature_comparison.csv",
        "recovery_analysis.csv",
        "downfall_analysis.csv",
        "intervention_window_analysis.csv",
        "warning_persistence_timing.csv",
        "support_analysis.csv",
        "h2_1_alignment_audit.csv",
        "h2_1_alignment_examples.csv",
        "statistics.json",
        "leakage_audit.json",
        "confirmation_protection_audit.json",
        "model_hash_audit.json",
        "cohort_hash_audit.json",
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
    assert "PHASE 3 — NOT STARTED" in report
    assert "# 25. WHETHER PHASE 3 IS JUSTIFIED" in report
    stats = load_json(root / "statistics.json")
    assert stats["confirmation_accessed"] is False
    assert stats["A"]["economics"]["n_first_negative"] == 67
    assert stats["B"]["economics"]["n_first_negative"] == 22
    assert not (experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv").is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
