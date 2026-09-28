"""Katy Texas experiments. Confirmation unspent. Not a fill."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B, PHASE6_ID, assert_experiment_id
from roller.austin.experiments.persistence.load import refuse_confirmation_path
from roller.austin.paths import experiment_dir, policy_phase5_dir, repo_root
from roller.choosin_texas.houston import declared_lock_vs_entry_cents, declared_no_taker_cents
from roller.choosin_texas.katy import PRICE_HI, PRICE_LO, _classify, katy_dir

REPO = repo_root()


def test_houston_declared_complement_is_integer():
    assert declared_no_taker_cents(70) == 30
    assert declared_lock_vs_entry_cents(70) == -10
    assert declared_lock_vs_entry_cents(41) == -39
    assert _classify(80, -20) == "NOT_UNDERWATER"
    assert _classify(40, -20) == "THROUGH_BAND"
    assert _classify(65, None) == "AUSTIN_EV_UNAVAILABLE"
    assert _classify(65, 5) == "HOLD"
    assert _classify(65, 4.99) == "HEDGE_SCENARIO"
    assert PRICE_LO == 41
    assert PRICE_HI == 70


def test_katy_artifacts_and_confirmation_still_sealed():
    from roller.choosin_texas.katy import build_katy

    payload = build_katy()
    assert payload["experiment_id"] == "KATY_TEXAS_V1"
    assert payload["slug"] == "late-underwater-41-70-ev5"
    assert payload["number"] == 1
    assert payload["submits"] is False
    assert payload["fill_status"] == "FILL_UNAVAILABLE"
    assert payload["confirmation_accessed"] is False
    assert payload["combined_headline_forbidden"] is True
    assert payload["components"]["houston"]["identity"] == "HOUSTON_TAKER_OTHER_SIDE_V1"
    a = payload["books"]["ncaab_h1_2_discovery"]
    b = payload["books"]["ncaab_h2_1_discovery"]
    nba = payload["books"]["nba_604_in_sample"]
    assert a["n_trades"] == 96
    assert b["n_trades"] == 69
    assert nba["n_trades"] == 604
    assert a["n_hedge_scenario"] >= 0
    assert (katy_dir() / "REPORT.md").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
    path = experiment_dir(EXPERIMENT_A) / "confirmation" / "state_queries.csv"
    with pytest.raises(AustinError, match="confirmation result"):
        refuse_confirmation_path(path)
    assert not path.is_file()
    assert not (experiment_dir(EXPERIMENT_B) / "confirmation" / "statistics.json").is_file()
    with pytest.raises(AustinError):
        assert_experiment_id("NCAAB_H2_2_AUSTIN_TRANSFER_V1")
    assert PHASE6_ID


def test_katy_v2_search_vs_8040_and_catalog():
    from roller.choosin_texas.katy.catalog import build_catalog
    from roller.choosin_texas.katy.v2 import EXPERIMENT_ID, PRICE_HI_GRID, EV_LT_GRID, experiment_dir as v2_dir

    catalog = build_catalog()
    slugs = [row["slug"] for row in catalog["experiments"]]
    assert slugs == [
        "late-underwater-41-70-ev5",
        "q4-open-8040-search",
        "2h-last-10-price-search",
        "last10-clock-trail-55-45",
        "last10-austin-four-book",
    ]
    assert catalog["kind"] == "catalog"
    assert catalog["confirmation_accessed"] is False
    assert catalog["phase5_policy"] == "NONE"

    from roller.choosin_texas.katy import handle_katy_experiment

    payload = handle_katy_experiment("q4-open-8040-search")
    assert payload["experiment_id"] == EXPERIMENT_ID
    assert payload["austin_refit"] is False
    assert payload["search_is_not_a_freeze"] is True
    assert payload["grid_declared"]["price_hi"] == list(PRICE_HI_GRID)
    assert payload["grid_declared"]["austin_ev_lt"] == list(EV_LT_GRID)
    assert payload["confirmation_accessed"] is False
    exam = payload["loser_exam"]["nba_604_in_sample"]
    assert exam["losers"]["n"] >= 1
    assert exam["winners"]["n"] >= 1
    for key in ("ncaab_h1_2_discovery", "ncaab_h2_1_discovery", "nba_604_in_sample"):
        cell = payload["selected"][key]
        assert cell["status"] in {"SELECTED", "NONE"}
        if cell["status"] == "SELECTED":
            assert cell["delta_sum_cents"] > 0
            assert cell["price_lo"] == 41
            assert cell["price_hi"] in PRICE_HI_GRID
    assert payload["books"]["ncaab_h1_2_discovery"]["n_trades"] == 96
    assert payload["books"]["ncaab_h2_1_discovery"]["n_trades"] == 69
    assert payload["books"]["nba_604_in_sample"]["n_trades"] == 604
    assert (v2_dir() / "REPORT.md").is_file()
    assert (v2_dir() / "loser_exam.json").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()


def test_katy_ui_and_api_shape():
    from roller.choosin_texas.api import handle_katy, handle_katy_experiment

    catalog = handle_katy()
    assert catalog["product"] == "Katy Texas"
    assert catalog["kind"] == "catalog"
    assert catalog["phase5_policy"] == "NONE"
    assert len(catalog["experiments"]) >= 5
    assert any(row.get("slug") == "2h-last-10-price-search" for row in catalog["experiments"])
    assert any(row.get("slug") == "last10-clock-trail-55-45" for row in catalog["experiments"])
    assert any(row.get("slug") == "last10-austin-four-book" for row in catalog["experiments"])
    v1 = handle_katy_experiment("late-underwater-41-70-ev5")
    assert v1["experiment_id"] == "KATY_TEXAS_V1"
    ui = (REPO / "frontend" / "choosin-texas" / "src" / "Katy.tsx").read_text(encoding="utf-8")
    app = (REPO / "frontend" / "choosin-texas" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "Katy" in app
    assert "katy/" in app
    assert "HEDGE_SCENARIO" in ui
    assert "never one headline" in ui
    assert "experiment-card" in ui
    assert "fetchKatyExperiment" in ui
    for word in ("EXIT NOW", "BUY", "SKIP"):
        assert word not in ui
    assert (REPO / "research" / "choosin_texas" / "library" / "nba_2q_regular_8040_1lot_2026_27" / "book.json").is_file()


def test_katy_v3_four_universe_independent_of_austin():
    from roller.choosin_texas.katy import v3

    src = Path(v3.__file__).read_text(encoding="utf-8")
    assert "match_query" not in src
    assert "load_pca_model" not in src
    assert "state_queries.csv" not in src
    payload = v3.build_v3()
    assert payload["experiment_id"] == v3.EXPERIMENT_ID
    assert payload["austin_used"] is False
    assert payload["independent_study"] is True
    assert payload["confirmation_accessed"] is False
    assert payload["row_counts"]["nba_2q"] == 314
    assert payload["row_counts"]["nba_3q"] == 290
    assert payload["row_counts"]["ncaab_h1_2"] == 193
    assert payload["row_counts"]["ncaab_h2_1"] == 139
    for key in ("nba_2q", "nba_3q", "ncaab_h1_2", "ncaab_h2_1"):
        cell = payload["selected"][key]
        assert cell["status"] in {"SELECTED", "NONE"}
        exam = payload["loser_exam"][key]
        assert exam["losers"]["n"] >= 1
    ui = (REPO / "frontend" / "choosin-texas" / "src" / "Katy.tsx").read_text(encoding="utf-8")
    assert "2H last 10" in ui
    assert "Four books, never one headline" in ui
    assert "INDEPENDENT · NO AUSTIN" in ui
    assert (v3.experiment_dir() / "REPORT.md").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()


def test_katy_v4_clock_trail_independent_of_austin():
    from roller.choosin_texas.katy import v4

    src = Path(v4.__file__).read_text(encoding="utf-8")
    assert "match_query" not in src
    assert "load_pca_model" not in src
    payload = v4.load_v4() or v4.build_v4()
    assert payload["experiment_id"] == v4.EXPERIMENT_ID
    assert payload["austin_used"] is False
    assert payload["independent_study"] is True
    assert payload["surface"] == "trail"
    assert payload["row_counts"]["nba_2q"] == 314
    assert payload["row_counts"]["nba_3q"] == 290
    assert payload["row_counts"]["ncaab_h1_2"] == 193
    assert payload["row_counts"]["ncaab_h2_1"] == 139
    for key in ("nba_2q", "nba_3q", "ncaab_h1_2", "ncaab_h2_1"):
        book = payload["books"][key]
        assert book["always_8040"]["mean_cents"] is not None
        assert book["overlay_theo"]["mean_cents"] is not None
        assert payload["loser_exam"][key]["losers"]["n"] >= 1
    ui = (REPO / "frontend" / "choosin-texas" / "src" / "Katy.tsx").read_text(encoding="utf-8")
    assert "CLOCK TRAIL" in ui
    assert "2H last 10 conversion" in ui
    assert (v4.experiment_dir() / "REPORT.md").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()


def test_katy_v5_austin_four_book_search():
    from roller.choosin_texas.katy import v5

    payload = v5.load_v5() or v5.build_v5()
    assert payload["experiment_id"] == v5.EXPERIMENT_ID
    assert payload["austin_used"] is True
    assert payload["austin_refit"] is False
    assert payload["search_is_not_a_freeze"] is True
    assert payload["confirmation_accessed"] is False
    assert payload["row_counts"]["nba_2q"] == 314
    assert payload["row_counts"]["nba_3q"] == 290
    assert payload["row_counts"]["ncaab_h1_2_discovery"] == 96
    assert payload["row_counts"]["ncaab_h2_1_discovery"] == 69
    for key in ("nba_2q", "nba_3q", "ncaab_h1_2_discovery", "ncaab_h2_1_discovery"):
        cell = payload["selected"][key]
        assert cell["status"] in {"SELECTED", "NONE"}
        if cell["status"] == "SELECTED":
            assert cell["delta_sum_cents"] > 0
            assert cell["price_lo"] == 41
        exam = payload["loser_exam"][key]
        assert exam["losers"]["n"] >= 1
    ui = (REPO / "frontend" / "choosin-texas" / "src" / "Katy.tsx").read_text(encoding="utf-8")
    assert "last10-austin-four-book" not in ui or "Four books, never one headline" in ui
    assert (v5.experiment_dir() / "REPORT.md").is_file()
    assert not (policy_phase5_dir() / "POLICY_FREEZE.json").is_file()
