"""Austin NCAAB transfer experiment locks. Does not change the query desk."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path

import numpy as np
import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.cohorts import (
    assert_locked_population,
    load_asked_six_ncaab,
    split_games,
)
from roller.austin.experiments.ids import (
    EXPERIMENT_A,
    EXPERIMENT_B,
    FEE_MODEL,
    FORBIDDEN_IDS,
    N_A,
    N_B,
    N_UNION,
    PAGE3_BOOK_CENTS,
    PAGE3_EV_CENTS,
    PAGE3_N,
    PAGE3_S,
    SUITE_ID,
    assert_experiment_id,
    assert_slice,
)
from roller.austin.experiments.ledgers import hold_rows, choosin_8040_rows, policy_rows
from roller.austin.experiments.ncaab_state import (
    mutate_future_and_rebuild,
    time_since_entry_ncaab,
)
from roller.austin.experiments.outcomes_ncaab import baseline_8040_cents, baseline_hold_cents, outcomes_for_trade
from roller.austin.experiments.policies import (
    POLICY_FAMILY,
    assign_ev_entry,
    canonical_definition,
    confirmation_artifacts_exist,
    decide,
    policy_hash,
)
from roller.austin.experiments.report import render_report
from roller.austin.experiments.run import main, stage_confirmation, stage_freeze
from roller.austin.experiments.schedule import build_observation_grid, grid_points
from roller.austin.experiments.statistics import (
    build_statistics,
    clustered_delta_ci,
    path_coverage,
    warning_rows,
)
from roller.austin.features import build_feature_vector
from roller.austin.outcomes import NOT_APPLICABLE
from roller.austin.query import query_match
from roller.choosin_texas.locks import PARTITIONS

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "ROLLER" / "roller" / "austin"
BOOK = (
    REPO
    / "research"
    / "choosin_texas"
    / "library"
    / "nba_2q_regular_8040_1lot_2026_27"
    / "book.json"
)
TS0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def _trade(**kwargs):
    row = {
        "trade_id": "t1",
        "internal_game_id": "g1",
        "asked_game_id": "g1",
        "event_id": "e1",
        "ticker": "KXTEST-1",
        "game_date": "2026-01-01",
        "entry_timestamp": TS0.isoformat(),
        "period": 1,
        "entry_seconds_remaining": 1054,
        "side": "home",
        "entry_price_cents": 80,
        "home_score_entry": 20,
        "away_score_entry": 18,
        "won": True,
        "t40": False,
        "slice": "H1_2",
        "entry_source": "ASKED_SIX_FIRST80",
        "last_tradable_timestamp": (TS0 + timedelta(hours=3)).isoformat(),
    }
    row.update(kwargs)
    return row


def _pbp_through_ot():
    events = []
    t = TS0 - timedelta(minutes=20)
    for period, remaining in grid_points(max_period=3):
        events.append(
            {
                "ts": t,
                "period": period,
                "seconds_remaining": remaining,
                "home_score": 20,
                "away_score": 18,
            }
        )
        t += timedelta(minutes=2)
    return events


def _bars(start: datetime, n: int = 40, first_price: float = 80.0):
    rows = []
    price = first_price
    for i in range(n):
        rows.append((start + timedelta(minutes=i), price, price, price))
        price = max(1.0, price - 1)
    return rows


def test_locked_n_and_forbidden_h2_2():
    rows = load_asked_six_ncaab()
    assert_locked_population(rows)
    assert len([r for r in rows if r["slice"] == "H1_2"]) == N_A == 193
    assert len([r for r in rows if r["slice"] == "H2_1"]) == N_B == 139
    assert len(rows) == N_UNION == 332
    assert all(r["slice"] != "H2_2" for r in rows)
    lock_a = next(p for p in PARTITIONS if p.partition_id == "ncaab_h1_2")
    lock_b = next(p for p in PARTITIONS if p.partition_id == "ncaab_h2_1")
    assert lock_a.n == 193 and lock_b.n == 139
    with pytest.raises(AustinError):
        assert_experiment_id("NCAAB_H2_2_AUSTIN_TRANSFER_V1")
    with pytest.raises(AustinError):
        assert_experiment_id(next(iter(FORBIDDEN_IDS)))
    with pytest.raises(AustinError):
        assert_slice("H2_2")
    with pytest.raises(AustinError):
        assert_slice("2ND10")


def test_floor_g_over_2_unique_game_split():
    rows = []
    for i in range(5):
        gid = f"g{i}"
        rows.append(
            _trade(
                trade_id=f"a{i}",
                internal_game_id=gid,
                asked_game_id=gid,
                game_date=f"2026-01-{i+1:02d}",
                entry_timestamp=datetime(2026, 1, i + 1, tzinfo=timezone.utc).isoformat(),
            )
        )
        rows.append(
            _trade(
                trade_id=f"b{i}",
                internal_game_id=gid,
                asked_game_id=gid,
                game_date=f"2026-01-{i+1:02d}",
                entry_timestamp=datetime(2026, 1, i + 1, 1, tzinfo=timezone.utc).isoformat(),
            )
        )
    disc, conf = split_games(rows)
    assert len(disc) == floor(5 / 2) == 2
    assert len(conf) == 3
    assert set(disc) & set(conf) == set()
    assert disc == ["g0", "g1"]
    assert all(r["internal_game_id"] not in disc or r["internal_game_id"] not in conf for r in rows)


def test_slice_is_not_observation_horizon():
    pbp = _pbp_through_ot()
    bars = _bars(TS0 - timedelta(minutes=5), n=80)
    h12 = build_observation_grid(
        _trade(period=1, entry_seconds_remaining=454, slice="H1_2"),
        bars=bars,
        pbp=pbp,
    )
    primary = [r for r in h12 if r["primary"]]
    assert any(r["period"] == 2 for r in primary)
    assert any(r["period"] == 3 for r in primary)
    h21 = build_observation_grid(
        _trade(period=2, entry_seconds_remaining=1140, slice="H2_1"),
        bars=bars,
        pbp=pbp,
    )
    primary_b = [r for r in h21 if r["primary"]]
    assert any(r["period"] == 2 and r["game_clock_remaining"] <= 600 for r in primary_b)
    assert any(r["period"] == 3 for r in primary_b)


def test_entry_is_not_automatic_primary_checkpoint():
    pbp = _pbp_through_ot()
    bars = _bars(TS0 - timedelta(minutes=30))
    grid = build_observation_grid(_trade(period=1, entry_seconds_remaining=1054), bars=bars, pbp=pbp)
    eighteen = next(r for r in grid if r["period"] == 1 and r["game_clock_remaining"] == 1080)
    sixteen = next(r for r in grid if r["period"] == 1 and r["game_clock_remaining"] == 960)
    assert eighteen["skip_reason"] == "PRE_ENTRY"
    assert eighteen["primary"] is False
    assert sixteen["primary"] is True
    assert sixteen["skip_reason"] is None


def test_ev_entry_first_valid_primary_and_policy_d():
    rows = assign_ev_entry(
        [
            {
                "trade_id": "t1",
                "primary": True,
                "availability_status": "UNAVAILABLE",
                "conditional_ev_cents": None,
            },
            {
                "trade_id": "t1",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": 4.0,
            },
            {
                "trade_id": "t1",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": -6.0,
            },
            {
                "trade_id": "t1",
                "primary": False,
                "role": "DIAGNOSTIC_EVENT",
                "availability_status": "VALUE",
                "conditional_ev_cents": -99.0,
            },
        ]
    )
    assert rows[0]["ev_at_entry"] is None
    assert rows[1]["ev_at_entry"] == 4.0
    assert rows[2]["ev_at_entry"] == 4.0
    assert rows[2]["ev_change"] == -10.0
    assert decide("POLICY_D", ev=-6.0, ci_lower=-10, ci_upper=-1, ev_entry=None, primary=True) == "NONE"
    assert decide("POLICY_D", ev=-6.0, ci_lower=-10, ci_upper=-1, ev_entry=4.0, primary=True) == "INTERVENE"
    assert decide("POLICY_A", ev=-1.0, ci_lower=-4, ci_upper=1, ev_entry=4.0, primary=False) == "NONE"


def test_three_ledgers_stay_separate_and_hold_is_primary():
    trades = [_trade(won=True, t40=False), _trade(trade_id="t2", won=False, t40=True)]
    assert [r["pnl_cents"] for r in hold_rows(trades)] == [20, -80]
    assert [r["pnl_cents"] for r in choosin_8040_rows(trades)] == [20, -40]
    assert baseline_hold_cents(trades[0]) == 20
    assert baseline_8040_cents(trades[1]) == -40
    queries = assign_ev_entry(
        [
            {
                "trade_id": "t1",
                "internal_game_id": "g1",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": -3.0,
                "ci_lower_cents": -8,
                "ci_upper_cents": 1,
                "timestamp_utc": (TS0 + timedelta(minutes=4)).isoformat(),
                "current_price_cents": 60,
                "game_clock_remaining": 960,
                "period": 1,
            }
        ]
    )
    policies, inter = policy_rows(trades[:1], queries, policy_ids=["POLICY_A"])
    assert policies[0]["baseline_hold_pnl"] == 20
    assert policies[0]["baseline_8040_pnl"] == 20
    assert policies[0]["scenario_label"] == "SCENARIO — NOT OBSERVED FILL"
    assert "baseline_ledger" not in policies[0]
    assert inter[0]["winner_abandoned"] is True
    assert inter[0]["cents_sacrificed"] is not None
    ts = TS0 + timedelta(minutes=10)
    bars = [(TS0, 80.0, 80.0, 80.0), (ts, 39.0, 39.0, 39.0), (ts + timedelta(minutes=1), 38.0, 38.0, 38.0)]
    oc = outcomes_for_trade({"entry_price_cents": 80, "won": False, "t40": True}, snapshot_ts=ts, bars=bars)
    assert oc["t40_already"] is True
    assert oc["pnl_8040_after_t"] is None
    assert oc["pnl_8040_after_t_status"] == NOT_APPLICABLE
    assert oc["pnl_hold_after_t"] == -80


def test_diagnostics_cannot_arm_primary_policy():
    queries = [
        {
            "trade_id": "t1",
            "primary": False,
            "role": "DIAGNOSTIC_EVENT",
            "diagnostic_print": 42,
            "availability_status": "VALUE",
            "conditional_ev_cents": -20.0,
            "ci_lower_cents": -30,
            "ci_upper_cents": -10,
            "timestamp_utc": TS0.isoformat(),
            "current_price_cents": 42,
        }
    ]
    policies, inter = policy_rows([_trade()], queries, policy_ids=["POLICY_A"])
    assert policies[0]["intervention"] == "NONE"
    assert inter == []


def test_travel_zero_variance_and_pre80_no_fake_ev():
    from roller.austin.raw_state import RawState
    from roller.austin.store import load_pca_model, load_snapshots

    raw = RawState(
        is_query=True,
        trade_id="ncaab-q",
        side="home",
        entry_price_cents=80,
        current_price_cents=80,
        home_score_entry=20,
        away_score_entry=18,
        home_score_current=20,
        away_score_current=18,
        entry_quarter=1,
        current_quarter=1,
        entry_seconds_remaining=600,
        current_seconds_remaining=600,
        time_since_entry_sec=0,
        query_mode="POST_80",
        entry_source="ASKED_SIX_FIRST80",
        clock_sport="NCAAB",
    )
    bundle = build_feature_vector(raw)
    assert bundle["numeric"]["price_travel"] == 0.0
    assert bundle["features"]["price_travel"]["status"] == "VALUE"
    snaps = load_snapshots()
    model = load_pca_model()
    pre = RawState(
        is_query=True,
        trade_id="pre",
        side="home",
        entry_price_cents=None,
        current_price_cents=70,
        home_score_entry=None,
        away_score_entry=None,
        home_score_current=10,
        away_score_current=8,
        entry_quarter=None,
        current_quarter=1,
        entry_seconds_remaining=None,
        current_seconds_remaining=1100,
        time_since_entry_sec=None,
        query_mode="PRE_80",
        entry_source="NONE",
        clock_sport="NCAAB",
    )
    out = query_match(pre, snapshots=snaps, model=model, calibration={})
    assert out["conditional_ev"] is None
    assert out["reason"] == "NO_ENTRY_IN_FITTED_SPACE"
    assert out["submits"] is False


def test_ncaab_clock_and_future_mutation_does_not_change_features():
    from roller.state.clock import elapsed_game_seconds
    from roller.austin.clock import game_elapsed_seconds

    ncaab = elapsed_game_seconds(1, 600, sport="NCAAB")
    nba_wrong = game_elapsed_seconds(1, 600)
    assert ncaab == 600
    assert nba_wrong != ncaab
    assert time_since_entry_ncaab(
        entry_period=1,
        entry_remaining=1054,
        current_period=2,
        current_remaining=1200,
        wall=None,
    ) == 1054
    trade = _trade()
    t = TS0 + timedelta(minutes=6)
    bars = _bars(TS0, n=8, first_price=80)
    pbp = [
        {"ts": TS0, "period": 1, "seconds_remaining": 1054, "home_score": 20, "away_score": 18},
        {"ts": t, "period": 1, "seconds_remaining": 694, "home_score": 24, "away_score": 20},
    ]
    a, b = mutate_future_and_rebuild(trade, timestamp_utc=t.isoformat(), future_price=10.0, bars=bars, pbp=pbp)
    fa = build_feature_vector(a)
    fb = build_feature_vector(b)
    assert fa["numeric"] == fb["numeric"]


def test_warning_missing_is_not_zero_and_coverage_classes():
    trades = [_trade(), _trade(trade_id="t2", internal_game_id="g2")]
    queries = [
        {
            "trade_id": "t1",
            "primary": True,
            "availability_status": "VALUE",
            "conditional_ev_cents": -2.0,
            "ci_upper_cents": -0.1,
            "game_clock_remaining": 600,
            "timestamp_utc": TS0.isoformat(),
            "current_price_cents": 50,
        }
    ]
    warns = warning_rows(trades, queries)
    assert warns[0]["class"] == "WARNING_AVAILABLE"
    assert warns[0]["warning_to_settlement_game_clock_minutes"] == 10.0
    assert warns[1]["class"] == "PATH_UNAVAILABLE"
    assert warns[1]["warning_unavailable_not_zero"] is True
    assert warns[1].get("warning_to_settlement_game_clock_minutes") is None
    cov = path_coverage(trades, queries)
    assert cov["N_games"] == 2
    assert cov["N_trades"] == 2
    assert cov["N_state_observations"] == 1
    assert cov["N_path_complete"] == 1
    assert cov["N_path_unavailable"] == 1


def test_clustered_bootstrap_resamples_games():
    rows = [
        {"internal_game_id": "g1", "trade_id": "a", "baseline_hold_pnl": 20, "hypothetical_pnl_b": 0},
        {"internal_game_id": "g1", "trade_id": "b", "baseline_hold_pnl": 20, "hypothetical_pnl_b": 0},
        {"internal_game_id": "g2", "trade_id": "c", "baseline_hold_pnl": -80, "hypothetical_pnl_b": -20},
    ]
    ci = clustered_delta_ci(rows, baseline_key="baseline_hold_pnl", policy_key="hypothetical_pnl_b")
    assert ci["cluster"] == "internal_game_id"
    assert ci["seed"] == 80
    assert ci["B"] == 1000
    assert ci["n_games"] == 2
    assert ci["n_trades"] == 3
    assert ci["ci"][0] <= ci["ci"][1]


def test_page3_control_and_fees_and_report_language():
    assert PAGE3_N == 280
    assert PAGE3_S == "218/280"
    assert PAGE3_EV_CENTS == 6.7143
    assert PAGE3_BOOK_CENTS == 1880
    stats = {
        "N_games": 1,
        "N_trades": 1,
        "N_state_observations": 2,
        "baseline_hold": {"ev_cents": 20},
        "policies": {},
        "warning": {},
        "coverage": {"N_path_complete": 1, "N_path_partial": 0, "N_path_unavailable": 0},
        "hedge_resolution": {"TRIGGER_RESOLUTION": "1m_close"},
        "calibration": {"status": "INSUFFICIENT_SAMPLE"},
    }
    text = render_report(experiment_id=EXPERIMENT_A, cohort="DISCOVERY", stats=stats, freeze=None)
    assert "No holy grail" in text
    assert "Austin works" not in text
    assert "LIVE READY" not in text
    assert "WHAT THE DATA SHOWS" in text
    assert "WHAT AUSTIN ADDS" in text
    assert "WHAT HAS NOT BEEN PROVEN" in text
    assert "WHETHER THE EVIDENCE JUSTIFIES THE NEXT VALIDATION STAGE" in text
    assert "CONFIRMATION RESULT:** NOT RUN" in text
    assert "POLICY STATUS:** UNFROZEN" in text
    assert str(PAGE3_N) in text
    assert FEE_MODEL == "UNAVAILABLE"


def test_suite_freeze_shared_and_cannot_read_confirmation(tmp_path, monkeypatch):
    from roller.austin.experiments import artifacts as artmod
    from roller.austin.experiments import cohorts as cohortmod
    from roller.austin.experiments import policies as polmod
    from roller.austin.experiments import run as runmod
    from roller.austin import paths

    root = tmp_path / "experiments"

    def _edir(eid: str):
        return root / eid

    monkeypatch.setattr(paths, "experiments_root", lambda: root)
    monkeypatch.setattr(paths, "suite_dir", lambda: root / SUITE_ID)
    monkeypatch.setattr(paths, "suite_freeze_path", lambda: root / SUITE_ID / "POLICY_FREEZE.json")
    monkeypatch.setattr(paths, "experiment_dir", _edir)
    monkeypatch.setattr(runmod, "suite_dir", lambda: root / SUITE_ID)
    monkeypatch.setattr(runmod, "suite_freeze_path", lambda: root / SUITE_ID / "POLICY_FREEZE.json")
    monkeypatch.setattr(runmod, "experiment_dir", _edir)
    monkeypatch.setattr(polmod, "experiment_dir", _edir)
    monkeypatch.setattr(polmod, "suite_freeze_path", lambda: root / SUITE_ID / "POLICY_FREEZE.json")
    monkeypatch.setattr(artmod, "suite_freeze_path", lambda: root / SUITE_ID / "POLICY_FREEZE.json")
    monkeypatch.setattr(artmod, "experiment_dir", _edir)
    monkeypatch.setattr(cohortmod, "experiment_dir", _edir)

    from roller.austin.experiments.cohorts import write_all_cohorts
    from roller.austin.experiments.manifest import persist_model_manifest, verify_model_manifest

    persist_model_manifest()
    verify_model_manifest()
    cohorts = write_all_cohorts()
    for eid in (EXPERIMENT_A, EXPERIMENT_B):
        qdir = root / eid / "discovery"
        qdir.mkdir(parents=True, exist_ok=True)
        (qdir / "state_queries.csv").write_text("trade_id\n", encoding="utf-8")
        assert eid in cohorts

    with pytest.raises(AustinError):
        stage_freeze(SUITE_ID, "POLICY_E") if False else main(
            ["--experiment", EXPERIMENT_A, "--stage", "freeze", "--policy", "POLICY_E"]
        )
    with pytest.raises(AustinError):
        main(["--suite", SUITE_ID, "--stage", "all", "--policy", "POLICY_E"])
    freeze = stage_freeze(SUITE_ID, "POLICY_E")
    assert freeze["suite_id"] == SUITE_ID
    assert freeze["policy_id"] == "POLICY_E"
    assert freeze["confirmation_read"] is False
    assert freeze["canonical_policy_definition"] == canonical_definition("POLICY_E")
    assert freeze["policy_hash"] == policy_hash("POLICY_E")
    assert freeze["A_discovery_cohort_hash"] == cohorts[EXPERIMENT_A]["discovery"]["cohort_hash"]
    assert freeze["B_confirmation_cohort_hash"] == cohorts[EXPERIMENT_B]["confirmation"]["cohort_hash"]
    assert set(POLICY_FAMILY) == {"POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E", "POLICY_F"}

    with pytest.raises(AustinError):
        stage_confirmation(EXPERIMENT_A, policy="POLICY_A")
    (root / EXPERIMENT_A / "confirmation").mkdir(parents=True)
    (root / EXPERIMENT_A / "confirmation" / "statistics.json").write_text("{}", encoding="utf-8")
    assert confirmation_artifacts_exist() is True
    with pytest.raises(AustinError):
        stage_freeze(SUITE_ID, "POLICY_A")


def test_handle_experiments_lists_members_separately():
    from roller.austin.api import handle_experiments

    payload = handle_experiments()
    assert payload["submits"] is False
    assert payload["page3_control"]["n"] == 280
    assert payload["page3_control"]["queried"] is False
    assert payload["combined_headline_forbidden"] is True
    ids = [m["experiment_id"] for m in payload["members"]]
    assert ids == [EXPERIMENT_A, EXPERIMENT_B]


def test_low_support_label_retained():
    from roller.austin.experiments.query_runner import _support_status

    assert _support_status(3.1, "OBSERVED") == "LOW_HISTORICAL_SUPPORT"
    assert _support_status(1.0, "OBSERVED") == "OBSERVED"


def test_statistics_keeps_n_separate_and_fees_do_not_alter_ev():
    trades = [_trade(won=True), _trade(trade_id="t2", internal_game_id="g2", won=False, t40=True)]
    queries = assign_ev_entry(
        [
            {
                "trade_id": "t1",
                "internal_game_id": "g1",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": 3.0,
                "pnl_hold_after_t": 20,
                "timestamp_utc": TS0.isoformat(),
            },
            {
                "trade_id": "t2",
                "internal_game_id": "g2",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": -4.0,
                "pnl_hold_after_t": -80,
                "timestamp_utc": TS0.isoformat(),
            },
        ]
    )
    policies, inter = policy_rows(trades, queries, policy_ids=["POLICY_A"])
    stats = build_statistics(
        experiment_id=EXPERIMENT_A,
        cohort="DISCOVERY",
        trades=trades,
        queries=queries,
        policy_ledger=policies,
        interventions=inter,
    )
    assert stats["N_games"] == 2
    assert stats["N_trades"] == 2
    assert stats["N_state_observations"] == 2
    assert stats["fee_model"] == "UNAVAILABLE"
    assert stats["page3_n280_queried"] is False
    assert stats["submits"] is False
    assert stats["baseline_hold"]["ev_cents"] == (20 - 80) / 2


def test_freeze_live_paths_and_forbidden_ui_words():
    src = "\n".join(p.read_text(encoding="utf-8") for p in (PKG / "experiments").glob("*.py"))
    assert "ENABLE_LIVE_TRADING" not in src
    assert "place_order" not in src
    assert "first80.py" not in src
    ui = (REPO / "frontend" / "dynamic-risk-engine" / "src" / "RiskReport.tsx").read_text(encoding="utf-8")
    app = (REPO / "frontend" / "choosin-texas" / "src" / "App.tsx").read_text(encoding="utf-8")
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "BUY", "SKIP"):
        assert word not in ui
        assert word not in app
    assert ">HOLD<" not in ui
    assert "austin/risk" in app
    assert "127.0.0.1:5191" in app
    assert "NOT RUN" in ui
    assert "Confirmation artifacts not written yet" not in ui
    assert BOOK.is_file()
    assert (REPO / "apps" / "trading-engine").exists()
    assert (REPO / "crates" / "risk").exists()
    first80 = list((REPO / "ROLLER").rglob("first80.py"))
    assert first80


def test_model_pin_hashes():
    from roller.austin.experiments.manifest import persist_model_manifest, verify_model_manifest

    payload = persist_model_manifest()
    assert payload["training_n_trades"] == 604
    assert payload["training_n_snapshots"] == 48752
    assert payload["ncaab_used_for_training"] is False
    verified = verify_model_manifest()
    assert verified["hashes"] == payload["hashes"]
    path = REPO / "research" / "austin" / "experiments" / "_model" / "MODEL_MANIFEST.json"
    assert path.is_file()


def test_git_pin_status_reason_and_hash_lock():
    from roller.austin.experiments.manifest import (
        LOCKED_HASHES,
        LOCKED_MANIFEST_HASH,
        persist_model_manifest,
        resolve_git_commit,
    )

    before = persist_model_manifest()
    git = resolve_git_commit()
    after = persist_model_manifest()
    assert before["hashes"] == LOCKED_HASHES == after["hashes"]
    assert before["model_manifest_hash"] == LOCKED_MANIFEST_HASH == after["model_manifest_hash"]
    assert after["git_commit_status"] in {"RESOLVED", "UNAVAILABLE"}
    assert after["git_commit_reason"]
    assert git["git_commit_status"] == after["git_commit_status"]
    if git["git_commit_status"] == "UNAVAILABLE":
        assert git["git_commit"] == "UNAVAILABLE"
        assert git["git_commit_reason"] in {"not_a_git_repo", "git_not_found"} or git["git_commit_reason"].startswith(
            "command_failed:"
        )
    else:
        assert len(git["git_commit"]) >= 7


def test_epoch_settlement_parse_and_after_settlement():
    from roller.austin.clock import parse_utc
    from roller.austin.experiments.cohorts import normalize_timestamp

    epoch = "1769565360"
    stamp = parse_utc(epoch)
    assert stamp is not None
    assert stamp.tzinfo is not None
    iso = normalize_timestamp(epoch)
    assert iso is not None and "T" in iso
    assert parse_utc(iso) == stamp
    settle = TS0 + timedelta(minutes=10)
    trade = _trade(last_tradable_timestamp=str(int(settle.timestamp())), period=1, entry_seconds_remaining=1054)
    pbp = _pbp_through_ot()
    bars = _bars(TS0 - timedelta(minutes=30), n=80)
    grid = build_observation_grid(trade, bars=bars, pbp=pbp)
    assert any(r.get("skip_reason") == "AFTER_SETTLEMENT" for r in grid)


def test_stage_grid_writes_rows_and_does_not_query_match(tmp_path, monkeypatch):
    from roller.austin.experiments import cohorts as cohortmod
    from roller.austin.experiments import query_runner as qmod
    from roller.austin.experiments import run as runmod
    from roller.austin.store import write_json

    called: list[bool] = []

    def _edir(eid: str):
        return tmp_path / eid

    monkeypatch.setattr(runmod, "experiment_dir", _edir)
    monkeypatch.setattr(qmod, "experiment_dir", _edir)
    monkeypatch.setattr(cohortmod, "experiment_dir", _edir)
    monkeypatch.setattr(runmod, "verify_model_manifest", lambda: {"model_manifest_hash": "x", "verified": True})
    monkeypatch.setattr(qmod, "query_match", lambda *a, **k: called.append(True) or {})
    trade = _trade()
    write_json(_edir(EXPERIMENT_A) / "discovery_cohort.json", {"trades": [trade], "n_trades": 1, "n_games": 1})
    monkeypatch.setattr(
        qmod,
        "load_trade_warehouse",
        lambda trades: {"bars": {trade["ticker"]: _bars(TS0 - timedelta(minutes=30), n=80)}, "pbp": {trade["internal_game_id"]: _pbp_through_ot()}},
    )
    from roller.austin.experiments.run import stage_grid

    out = stage_grid(EXPERIMENT_A)
    assert called == []
    assert out["n_grid_rows"] > 0
    grid_path = _edir(EXPERIMENT_A) / "discovery" / "observation_grid.csv"
    assert grid_path.is_file()
    text = grid_path.read_text(encoding="utf-8")
    assert "PRIMARY_GRID" in text or "PRE_ENTRY" in text


def test_discovery_does_not_write_confirmation_or_freeze(tmp_path, monkeypatch):
    from roller.austin.experiments import audits as auditmod
    from roller.austin.experiments import cohorts as cohortmod
    from roller.austin.experiments import ledgers as ledgermod
    from roller.austin.experiments import query_runner as qmod
    from roller.austin.experiments import report as reportmod
    from roller.austin.experiments import run as runmod
    from roller.austin.experiments import statistics as statsmod
    from roller.austin.store import write_json

    def _edir(eid: str):
        return tmp_path / eid

    for mod in (runmod, qmod, ledgermod, statsmod, reportmod, auditmod, cohortmod):
        monkeypatch.setattr(mod, "experiment_dir", _edir)
    monkeypatch.setattr(
        runmod,
        "verify_model_manifest",
        lambda: {"model_manifest_hash": "x", "feature_schema_hash": "y", "pca_version": "austin_pca_v1"},
    )
    trade = _trade()
    write_json(_edir(EXPERIMENT_A) / "discovery_cohort.json", {"trades": [trade], "n_trades": 1, "n_games": 1})
    write_json(_edir(EXPERIMENT_A) / "MANIFEST.json", {"experiment_id": EXPERIMENT_A})
    queries = assign_ev_entry(
        [
            {
                "trade_id": "t1",
                "internal_game_id": "g1",
                "primary": True,
                "availability_status": "VALUE",
                "conditional_ev_cents": -3.0,
                "ci_lower_cents": -8,
                "ci_upper_cents": 1,
                "timestamp_utc": (TS0 + timedelta(minutes=4)).isoformat(),
                "current_price_cents": 60,
                "game_clock_remaining": 960,
                "period": 1,
                "pnl_hold_after_t": 20,
            }
        ]
    )
    monkeypatch.setattr(runmod, "run_queries", lambda *a, **k: queries)
    monkeypatch.setattr(runmod, "load_trade_warehouse", lambda trades: {"bars": {}, "pbp": {}})
    monkeypatch.setattr(runmod, "run_leakage_audit", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(runmod, "run_self_neighbor_audit", lambda *a, **k: {"status": "PASS"})
    from roller.austin.experiments.run import stage_discovery

    stage_discovery(EXPERIMENT_A)
    root = _edir(EXPERIMENT_A)
    assert not (root / "confirmation" / "statistics.json").is_file()
    assert not (root / "confirmation_state_queries.csv").is_file()
    assert not (root / "POLICY_FREEZE.json").is_file()
    assert not (tmp_path / SUITE_ID / "POLICY_FREEZE.json").is_file()
    man = (root / "MANIFEST.json").read_text(encoding="utf-8")
    assert "UNFROZEN" in man
    assert "NOT RUN" in man
    assert (root / "discovery" / "statistics.json").is_file()


def test_agent_cannot_auto_pick_policy():
    from roller.austin.experiments.policies import refuse_auto_policy

    with pytest.raises(AustinError):
        refuse_auto_policy({"policies": {"POLICY_A": {"delta_mean": 99.0}}})


def test_confirmation_refused_without_suite_freeze(tmp_path, monkeypatch):
    from roller.austin.experiments import run as runmod

    missing = tmp_path / "POLICY_FREEZE.json"
    monkeypatch.setattr(runmod, "suite_freeze_path", lambda: missing)
    with pytest.raises(AustinError):
        stage_confirmation(EXPERIMENT_A)


def test_warning_available_median_is_none_when_only_too_late():
    from roller.austin.experiments.interpretation import warning_denominators

    trades = [_trade(), _trade(trade_id="t2", internal_game_id="g2", won=False)]
    queries = [
        {
            "trade_id": "t1",
            "primary": True,
            "conditional_ev_cents": -4.0,
            "ci_upper_cents": -0.1,
            "current_price_cents": 40,
            "game_clock_remaining": 180,
            "period": 2,
            "timestamp_utc": TS0.isoformat(),
            "t40_already": True,
        }
    ]
    warn = warning_denominators(trades, queries)
    assert warn["n_WARNING_AVAILABLE"] == 0
    assert warn["n_WARNING_TOO_LATE"] == 1
    assert warn["median_warning_available"]["n"] == 0
    assert warn["median_warning_available"]["median"] is None
    assert warn["median_warning_too_late"]["median"] == 3.0
    assert warn["median_first_negative_to_settlement"]["median"] == 3.0
    assert "AVAILABLE+TOO_LATE" in warn["label"]


def test_coverage_flags_clock_wall_alignment_not_missing_warehouse():
    from roller.austin.experiments.interpretation import coverage_audit

    trade = _trade(entry_timestamp=(TS0 + timedelta(minutes=30)).isoformat())
    queries = [
        {
            "trade_id": "t1",
            "internal_game_id": "g1",
            "primary": True,
            "query_mode": "PRE_80",
            "availability_status": "NOT_APPLICABLE",
            "knn_status": "INSUFFICIENT_SAMPLE",
            "reason": "NO_ENTRY_IN_FITTED_SPACE",
            "timestamp_utc": TS0.isoformat(),
            "period": 2,
            "game_clock_remaining": 600,
            "current_price_cents": 70,
            "conditional_ev_cents": None,
            "pnl_hold_after_t": -80,
        }
    ]
    cov = coverage_audit([trade], queries)
    assert cov["primary_query_mode"]["PRE_80"] == 1
    assert cov["primary_pre80_wall_before_entry"] == 1
    assert cov["missing_warehouse_not_the_cause"] is True
    assert "clock-vs-wall" in cov["diagnosis"]


def test_clustered_ev_ordering_and_first_negative_classes():
    from roller.austin.experiments.interpretation import first_negative_audit, ordering_audit
    from roller.austin.experiments.statistics import clustered_mean_diff

    rows = [
        {"internal_game_id": "g1", "hold_after": 20, "ev_negative": False},
        {"internal_game_id": "g1", "hold_after": 20, "ev_negative": False},
        {"internal_game_id": "g2", "hold_after": -80, "ev_negative": True},
        {"internal_game_id": "g2", "hold_after": -80, "ev_negative": True},
    ]
    ci = clustered_mean_diff(
        rows,
        value_key="hold_after",
        positive_pred=lambda r: not r["ev_negative"],
        negative_pred=lambda r: r["ev_negative"],
    )
    assert ci["observed_delta"] == 100
    assert ci["excludes_zero"] is True
    trades = [
        _trade(won=True),
        _trade(trade_id="t2", internal_game_id="g2", won=False, t40=True),
    ]
    queries = [
        {
            "trade_id": "t1",
            "internal_game_id": "g1",
            "primary": True,
            "conditional_ev_cents": -3.0,
            "ev_change": -8.0,
            "pnl_hold_after_t": 20,
            "timestamp_utc": TS0.isoformat(),
            "current_price_cents": 55,
        },
        {
            "trade_id": "t1",
            "internal_game_id": "g1",
            "primary": True,
            "conditional_ev_cents": 4.0,
            "ev_change": -1.0,
            "pnl_hold_after_t": 20,
            "timestamp_utc": (TS0 + timedelta(minutes=4)).isoformat(),
            "current_price_cents": 82,
        },
        {
            "trade_id": "t2",
            "internal_game_id": "g2",
            "primary": True,
            "conditional_ev_cents": -10.0,
            "ev_change": -10.0,
            "pnl_hold_after_t": -80,
            "timestamp_utc": TS0.isoformat(),
            "current_price_cents": 50,
            "t40_already": True,
        },
        {
            "trade_id": "t2",
            "internal_game_id": "g2",
            "primary": True,
            "conditional_ev_cents": -12.0,
            "ev_change": -12.0,
            "pnl_hold_after_t": -80,
            "timestamp_utc": (TS0 + timedelta(minutes=4)).isoformat(),
            "current_price_cents": 38,
            "hit_40_after": True,
        },
    ]
    first = first_negative_audit(trades, queries)
    assert first["n_first_negative_trades"] == 2
    assert first["n_eventually_win"] == 1
    assert first["n_eventually_lose"] == 1
    assert first["deterioration_class"]["TEMPORARY_DETERIORATION"] == 1
    assert first["deterioration_class"]["PERSISTENT_DETERIORATION"] == 1
    assert first["recovered_to_80"]["n"] == 1
    ord_ = ordering_audit(trades, queries)
    assert ord_["n_valid_states"] == 4
    assert "status" in ord_["state_ev_ordering"]


def test_scoring_is_not_a_single_accuracy():
    from roller.austin.experiments.interpretation import scoring_audit

    trades = [
        _trade(won=True),
        _trade(trade_id="t2", internal_game_id="g2", won=False, t40=True),
        _trade(trade_id="t3", internal_game_id="g3", won=True),
    ]
    queries = [
        {
            "trade_id": "t1",
            "internal_game_id": "g1",
            "primary": True,
            "conditional_ev_cents": 10.0,
            "pnl_hold_after_t": 20,
        },
        {
            "trade_id": "t2",
            "internal_game_id": "g2",
            "primary": True,
            "conditional_ev_cents": -40.0,
            "pnl_hold_after_t": -80,
        },
        {
            "trade_id": "t3",
            "internal_game_id": "g3",
            "primary": True,
            "conditional_ev_cents": -5.0,
            "pnl_hold_after_t": 20,
        },
    ]
    sc = scoring_audit(trades, queries)
    assert sc["not_a_single_accuracy"] is True
    assert "not Austin accuracy" in sc["label"]
    assert sc["mae_cents"]["observed"] == (10 + 40 + 25) / 3
    assert sc["sign_accuracy_ev_gt_0_vs_hold_gt_0"]["observed"] == 2 / 3
    crude = sc["crude_final_loss_classifier"]
    assert crude["tp_losses_detected"] == 1
    assert crude["fp_winners_flagged"] == 1
    assert crude["tn_winners_unflagged"] == 1
    assert crude["naive_always_win_accuracy"] == 2 / 3
    assert crude["classification_accuracy"] is not None
    assert "Austin accuracy" in crude["definition"]


def test_interpret_writes_audit_not_confirmation(tmp_path, monkeypatch):
    from roller.austin.experiments import cohorts as cohortmod
    from roller.austin.experiments import interpretation as interp
    from roller.austin.experiments import run as runmod
    from roller.austin.store import write_json

    def _edir(eid: str):
        return tmp_path / eid

    monkeypatch.setattr(runmod, "experiment_dir", _edir)
    monkeypatch.setattr(interp, "experiment_dir", _edir)
    monkeypatch.setattr(cohortmod, "experiment_dir", _edir)
    trade = _trade()
    write_json(_edir(EXPERIMENT_A) / "discovery_cohort.json", {"trades": [trade], "n_trades": 1, "n_games": 1})
    qdir = _edir(EXPERIMENT_A) / "discovery"
    qdir.mkdir(parents=True)
    fields = [
        "trade_id",
        "internal_game_id",
        "primary",
        "query_mode",
        "availability_status",
        "knn_status",
        "reason",
        "conditional_ev_cents",
        "pnl_hold_after_t",
        "ev_change",
        "timestamp_utc",
        "current_price_cents",
        "period",
        "game_clock_remaining",
        "ci_upper_cents",
        "t40_already",
        "hit_40_after",
        "ev_at_entry",
        "ev_now",
        "ci_lower_cents",
        "entry_price_cents",
    ]
    with (qdir / "state_queries.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "trade_id": "t1",
                "internal_game_id": "g1",
                "primary": "True",
                "query_mode": "POST_80",
                "availability_status": "VALUE",
                "knn_status": "OBSERVED",
                "reason": "",
                "conditional_ev_cents": "-3",
                "pnl_hold_after_t": "20",
                "ev_change": "0",
                "timestamp_utc": TS0.isoformat(),
                "current_price_cents": "55",
                "period": "1",
                "game_clock_remaining": "600",
                "ci_upper_cents": "1",
                "t40_already": "False",
                "hit_40_after": "False",
                "ev_at_entry": "-3",
                "ev_now": "-3",
                "ci_lower_cents": "-8",
                "entry_price_cents": "80",
            }
        )
    from roller.austin.experiments.run import main

    main(["--experiment", EXPERIMENT_A, "--stage", "interpret"])
    assert (_edir(EXPERIMENT_A) / "discovery" / "interpretation.json").is_file()
    assert (_edir(EXPERIMENT_A) / "INTERPRETATION.md").is_file()
    assert not (_edir(EXPERIMENT_A) / "confirmation" / "statistics.json").is_file()
    assert not (_edir(EXPERIMENT_A) / "POLICY_FREEZE.json").is_file()
