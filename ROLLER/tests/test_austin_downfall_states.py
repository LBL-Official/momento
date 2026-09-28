"""Austin Phase 3 downfall state model. Discovery only. No confirmation. No policy. No hazard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.engine import derive_downfall_state, walk_core
from roller.austin.experiments.downfall.ids import (
    CI_CROSSES_ZERO,
    CI_NEGATIVE,
    FORBIDDEN_CORE,
    HEALTHY,
    HEALTHY_AFTER_RECOVERY,
    LOCKED_CLOCK_ORDER,
    LOW_HISTORICAL_SUPPORT,
    MODEL_ID,
    NORMAL_SUPPORT,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PRE_ENTRY,
    RECOVERING,
    UNRESOLVED,
    WATCH_NEGATIVE,
)
from roller.austin.experiments.downfall.outcomes import attach_entry_outcomes
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.downfall.timeline import TIMELINE_FIELDS, build_timeline, first_entries
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, PHASE2_ID, PHASE3_ID, PHASE3_PHASE
from roller.austin.experiments.manifest import LOCKED_HASHES, LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH, LOCKED_DISCOVERY_HASH
from roller.austin.experiments.persistence.load import load_confirmation_identity, load_discovery_cohort, refuse_confirmation_path
from roller.austin.experiments.run import main
from roller.austin.paths import downfall_phase3_dir, experiment_dir, persistence_phase2_dir, repo_root
from roller.austin.store import load_json, load_snapshots

REPO = repo_root()
PKG = REPO / "ROLLER" / "roller" / "austin" / "experiments" / "downfall"


def _row(ev, *, remaining=600, period=1, lo=-4, hi=2, support="OBSERVED", price=70, **kwargs):
    row = {
        "conditional_ev_cents": ev,
        "period": period,
        "game_clock_remaining": remaining,
        "timestamp_utc": kwargs.get("ts", datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).isoformat()),
        "ci_lower_cents": lo,
        "ci_upper_cents": hi,
        "support_status": support,
        "current_price_cents": price,
        "ev_at_entry": kwargs.get("ev_entry", 8),
        "effective_sample_size": 12,
        "median_distance": 1.1,
        "mean_distance": 1.2,
        "feature_coverage": 0.9,
        "availability_status": "VALUE" if ev is not None else "UNAVAILABLE",
        "primary": True,
        "trade_id": kwargs.get("trade_id", "t1"),
        "t40_already": False,
        "hit_40_after": False,
        "home_score": 40,
        "away_score": 38,
        "pnl_hold_after_t": kwargs.get("pnl", 20),
    }
    row.update(kwargs)
    return row


def test_model_and_cohort_locks_unchanged():
    model = verify_model_manifest()
    assert model["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    assert int(model["training_n_trades"]) == 604
    assert int(model["training_n_snapshots"]) == 48752
    assert int(model.get("knn_k") or 25) == 25
    assert model["ncaab_used_for_training"] is False
    assert model["ncaab_used_for_pca"] is False
    assert len(load_snapshots()) == 48752
    for name, digest in LOCKED_HASHES.items():
        assert digest
    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        disc = load_discovery_cohort(eid)
        ident = load_confirmation_identity(eid)
        assert disc["cohort_hash"] == LOCKED_DISCOVERY_HASH[eid]
        assert ident["cohort_hash"] == LOCKED_CONFIRMATION_HASH[eid]
        assert all(t.get("slice") != "H2_2" for t in disc["trades"])


def test_phase2_report_and_actionability_unchanged():
    root = persistence_phase2_dir()
    assert sha256_file(root / "REPORT.md") == PHASE2_REPORT_SHA256
    assert sha256_file(root / "statistics.json") == PHASE2_STATISTICS_SHA256
    stats = load_json(root / "statistics.json")
    assert stats["interpretation"]["phase_3_justified"] is False
    assert "not an actionable" in str(stats["interpretation"]["acceptance"]).lower()
    assert stats["A"]["economics"]["n_first_negative"] == LOCKED_CLOCK_ORDER[EXPERIMENT_A]["n_first_negative"]
    assert stats["A"]["economics"]["n_temporary"] == 51
    assert stats["A"]["economics"]["n_persistent"] == 15
    assert stats["A"]["economics"]["n_unresolved"] == 1
    assert stats["B"]["economics"]["n_first_negative"] == 22
    assert stats["B"]["economics"]["n_temporary"] == 5
    assert stats["B"]["economics"]["n_persistent"] == 6
    assert stats["B"]["economics"]["n_unresolved"] == 11
    assert stats["alignment_verdict"]["status"] == "EXPECTED_FROM_CANONICAL_TIMING"
    assert stats["alignment_verdict"]["potential_data_alignment_defect"] is False
    assert stats["confirmation_accessed"] is False
    assert stats["policy_status"] == "UNFROZEN"


def test_schema_frozen_and_no_critical():
    schema = state_schema()
    assert schema["version"] == "downfall_state_v1"
    assert "CRITICAL" not in schema["states"]
    assert FORBIDDEN_CORE.isdisjoint(schema["states"])
    digest = schema_hash(schema)
    assert len(digest) == 64
    assert schema_hash(schema) == digest


def test_assignment_cases_and_gap_breaks_streak():
    assert walk_core([]) == (PRE_ENTRY, 0)
    assert walk_core([_row(3.0)])[0] == HEALTHY
    assert walk_core([_row(-2.0)])[0] == WATCH_NEGATIVE
    assert walk_core([_row(-2.0, remaining=600), _row(-3.0, remaining=480)])[0] == PERSISTENCE_2
    assert walk_core([_row(-2.0, remaining=600), _row(-3.0, remaining=480), _row(-4.0, remaining=360)])[0] == PERSISTENCE_3PLUS
    assert walk_core([_row(-2.0, remaining=600), _row(1.0, remaining=480)])[0] == RECOVERING
    assert walk_core([_row(-2.0, remaining=600), _row(1.0, remaining=480), _row(2.0, remaining=360)])[0] == HEALTHY_AFTER_RECOVERY
    gap = walk_core([_row(-2.0, remaining=600), _row(None, remaining=480), _row(-3.0, remaining=360)])
    assert gap[0] == WATCH_NEGATIVE
    assert gap[1] == 1
    unresolved = walk_core([_row(-2.0, remaining=600), _row(None, remaining=480)])
    assert unresolved[0] == UNRESOLVED


def test_future_and_outcomes_never_enter_assignment():
    state = derive_downfall_state([_row(-5.0)])
    assert state["core_state"] == WATCH_NEGATIVE
    assert set(state) & {
        "won",
        "OUTCOME_future_T40",
        "OUTCOME_future_MAE",
        "OUTCOME_eventual_result",
        "negative_ev_class",
    } == set()
    later = [_row(-5.0, remaining=600), _row(-9.0, remaining=480, pnl=-80)]
    now = derive_downfall_state(later[:1])
    mutated = [_row(-5.0, remaining=600), _row(99.0, remaining=480, pnl=20, t40_already=True)]
    replay = derive_downfall_state(mutated[:1])
    assert now["core_state"] == replay["core_state"]
    assert now["negative_streak_length"] == replay["negative_streak_length"]


def test_overlays_do_not_change_core_and_price_score_do_not_define_core():
    a = derive_downfall_state([_row(-2.0, lo=-8, hi=-1, price=70, home_score=40, away_score=38)])
    b = derive_downfall_state([_row(-2.0, lo=-1, hi=4, price=40, home_score=10, away_score=80)])
    assert a["core_state"] == b["core_state"] == WATCH_NEGATIVE
    assert a["CI_state"] == CI_NEGATIVE
    assert b["CI_state"] == CI_CROSSES_ZERO
    low = derive_downfall_state([_row(-2.0, support="LOW_HISTORICAL_SUPPORT")])
    obs = derive_downfall_state([_row(-2.0, support="OBSERVED")])
    assert low["core_state"] == obs["core_state"]
    assert low["support_state"] == LOW_HISTORICAL_SUPPORT
    assert obs["support_state"] == NORMAL_SUPPORT


def test_timeline_pit_only_and_first_entry_unique():
    trade = {"trade_id": "t1", "internal_game_id": "g1", "ticker": "X", "won": False}
    queries = [
        _row(4.0, remaining=600, trade_id="t1"),
        _row(-2.0, remaining=480, trade_id="t1"),
        _row(-3.0, remaining=360, trade_id="t1"),
        _row(1.0, remaining=240, trade_id="t1"),
        _row(2.0, remaining=120, trade_id="t1"),
    ]
    timeline = build_timeline(EXPERIMENT_A, trade, queries)
    assert [r["core_state"] for r in timeline] == [
        HEALTHY,
        WATCH_NEGATIVE,
        PERSISTENCE_2,
        RECOVERING,
        HEALTHY_AFTER_RECOVERY,
    ]
    for row in timeline:
        assert set(row) & {"OUTCOME_future_T40", "OUTCOME_pnl_hold_after_state", "won"} == set()
        for key in TIMELINE_FIELDS:
            assert key in row
    entries = first_entries(timeline)
    keys = [(e["trade_id"], e["core_state"]) for e in entries]
    assert len(keys) == len(set(keys))
    attached = [attach_entry_outcomes(e, timeline, trade) for e in entries]
    assert attached[0]["OUTCOME_eventual_result"] == "LOSS"
    assert all(e.get("core_state") for e in attached)


def test_downfall_stage_rejects_member_and_policy():
    with pytest.raises(AustinError):
        main(["--stage", "downfall", "--experiment", EXPERIMENT_A])
    with pytest.raises(AustinError):
        main(["--stage", "downfall", "--policy", "POLICY_A"])


def test_no_classifier_policy_hazard_in_package():
    src = "\n".join(p.read_text(encoding="utf-8") for p in PKG.rglob("*.py"))
    assert "sklearn" not in src
    assert "LogisticRegression" not in src
    assert "POLICY_G" not in src
    assert "PERSISTENCE_POLICY" not in src
    assert "ENABLE_LIVE_TRADING" not in src
    assert "place_order" not in src
    assert "from roller.austin.query import query_match" not in src
    assert "hazard_probability" not in src
    assert "CRITICAL" not in src or 'FORBIDDEN_CORE' in src
    assert "BOOTSTRAP_SEED = 80" in (REPO / "ROLLER" / "roller" / "austin" / "experiments" / "ids.py").read_text(encoding="utf-8")
    assert "BOOTSTRAP_B = 1000" in (REPO / "ROLLER" / "roller" / "austin" / "experiments" / "ids.py").read_text(encoding="utf-8")


def test_do_not_touch_live_and_phase2_paths():
    assert (REPO / "research" / "choosin_texas" / "library" / "nba_2q_regular_8040_1lot_2026_27" / "book.json").is_file()
    assert (REPO / "apps" / "trading-engine").exists()
    assert (REPO / "crates" / "risk").exists()
    assert list((REPO / "ROLLER").rglob("first80.py"))
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
    assert ">HOLD<" not in ui
    assert "PHASE 3 · DOWNFALL STATE MODEL" in ui
    assert "HAZARD MODEL NOT BUILT" in ui
    assert "RESEARCH ONLY" in ui
    assert not (REPO / "research" / "austin" / "experiments" / "AUSTIN_NCAAB_TRANSFER_V1" / "POLICY_FREEZE.json").is_file()
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256


def test_confirmation_still_absent_and_phase3_not_a_member():
    from roller.austin.experiments.artifacts import handle_experiment, handle_experiments
    from roller.austin.experiments.ids import MEMBERS, assert_experiment_id

    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
    with pytest.raises(AustinError):
        assert_experiment_id(PHASE3_ID)
    assert PHASE3_ID not in MEMBERS
    assert PHASE2_ID not in MEMBERS
    suite = handle_experiments()
    assert suite["downfall_phase3"]["model_id"] == PHASE3_ID
    assert suite["downfall_phase3"]["hazard_model_built"] is False
    payload = handle_experiment(PHASE3_ID)
    assert payload["policy_status"] == "UNFROZEN"
    assert payload["confirmation_accessed"] is False
    assert payload["submits"] is False
    assert payload["hazard_model_built"] is False
    assert payload["phase_2_actionability_gate"] == "NOT_MET"


def test_artifacts_after_downfall_if_present():
    root = downfall_phase3_dir()
    if not (root / "MANIFEST.json").is_file():
        pytest.skip("phase 3 artifacts not written yet")
    manifest = load_json(root / "MANIFEST.json")
    assert manifest["model_id"] == MODEL_ID
    assert manifest["phase"] == "PHASE_3"
    assert manifest["confirmation_accessed"] is False
    assert manifest["policy_status"] == "UNFROZEN"
    assert manifest["policy_selected"] == "NONE"
    assert manifest["hazard_model_built"] is False
    assert manifest["execution_enabled"] is False
    assert manifest["submits"] is False
    assert manifest["phase_2_actionability_gate"] == "NOT_MET"
    assert manifest["phase_3_authorization"] == "EXPLICIT_RESEARCHER_AUTHORIZATION"
    assert manifest["state_schema_version"] == "downfall_state_v1"
    assert manifest["state_schema_hash"] == schema_hash()
    assert manifest["bootstrap_seed"] == 80
    assert manifest["bootstrap_B"] == 1000
    assert manifest["cluster_unit"] == "internal_game_id"
    assert manifest["model_manifest_hash"] == LOCKED_MANIFEST_HASH
    required = [
        "STATE_SCHEMA.json",
        "state_timeline.csv",
        "state_entries.csv",
        "state_summary.csv",
        "state_economics.csv",
        "state_contrasts.csv",
        "state_transitions.csv",
        "transition_counts.csv",
        "transition_rates.csv",
        "transition_entries.csv",
        "transition_economics.csv",
        "path_archetypes.csv",
        "archetype_economics.csv",
        "state_depth_analysis.csv",
        "ci_overlay_analysis.csv",
        "support_overlay_analysis.csv",
        "state_intervention_window.csv",
        "state_timing.csv",
        "statistics.json",
        "model_hash_audit.json",
        "cohort_hash_audit.json",
        "leakage_audit.json",
        "confirmation_protection_audit.json",
        "state_determinism_audit.json",
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
    assert "HAZARD MODEL NOT BUILT" in report
    assert "PHASE 4 — NOT STARTED" in report
    stats = load_json(root / "statistics.json")
    assert stats["confirmation_accessed"] is False
    assert stats["A"]["experiment_id"] == EXPERIMENT_A
    assert stats["B"]["experiment_id"] == EXPERIMENT_B
    assert stats["interpretation"]["phase_4_justified"] is False
    import csv

    timeline = list(csv.DictReader((root / "state_timeline.csv").open(encoding="utf-8")))
    assert timeline
    assert "OUTCOME_future_T40" not in timeline[0]
    assert all(r.get("phase_id") == PHASE3_PHASE for r in timeline)
    entries = list(csv.DictReader((root / "state_entries.csv").open(encoding="utf-8")))
    keys = [(r["source_experiment_id"], r["trade_id"], r["core_state"]) for r in entries]
    assert len(keys) == len(set(keys))
    leak = load_json(root / "leakage_audit.json")
    assert leak["status"] == "PASS"
    det = load_json(root / "state_determinism_audit.json")
    assert det["status"] == "PASS"
    assert sha256_file(persistence_phase2_dir() / "REPORT.md") == PHASE2_REPORT_SHA256
