"""WTA warehouse desk. Does not remint event tickers. Does not touch Confirm & Run goldens."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.superasi.iti.wta_question import WTA_ITI_QUESTION, iti_question_for_folder
from roller.warehouse.coverage import CapabilityName, get_catalog, question_capabilities
from roller.warehouse.desk import desk_lab_folder, desk_sport, observation_basis_for
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.layout import warehouse_root
from roller.warehouse.market_link import _default_market_type
from roller.warehouse.production import unavailable_production_sport
from roller.warehouse.research_compiler import compile_research
from roller.research_query.models import ResearchStatus
from roller.warehouse.tennis_desk import (
    NBA_CROSSWALK_SHA256,
    WTA_PHASE20_QUESTION,
    tennis_crosswalk_path,
    verify_wta_desk,
    verify_wta_identity,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE_GAMES = ROLLER_ROOT / "data" / "tennis" / "2025_2026" / "canonical" / "games.csv"
LIVE_WAREHOUSE = warehouse_root(CFG, "WTA", "2025-2026") / "manifest.json"
NBA_CROSSWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def test_desk_sport_and_basis():
    q = WTA_PHASE20_QUESTION
    assert desk_sport(q) == "WTA"
    assert observation_basis_for(q) == "TRADABLE_YES_BID"
    assert unavailable_production_sport(q) is None
    caps = question_capabilities(q)
    assert CapabilityName.TRADABLE_YES_BID_1M in caps
    assert desk_lab_folder(q) == "WTA"
    assert desk_lab_folder(q, "NBA") == "WTA"


def test_match_series_is_kxwtamatch_not_kxwtagame():
    assert _default_market_type("WTA") == "KXWTAMATCH"
    assert _default_market_type("WTA") != "KXWTAGAME"


def test_wta_iti_question_is_not_first80_or_nba_q4():
    q = iti_question_for_folder("WTA")
    assert q["universe"]["sports"] == ["WTA"]
    assert q["universe"]["market_data"] == ["candles"]
    assert q["entry_conditions"][0]["period"] is None
    assert q["entry_conditions"][0]["price_field"] == "yes_bid_close"
    assert "Q4" not in str(q)
    assert "FIRST80" not in str(q)
    assert WTA_ITI_QUESTION["universe"]["sports"] != ["NBA"]
    assert WTA_ITI_QUESTION["universe"]["sports"] != ["ATP"]


@pytest.mark.skipif(not LIVE_GAMES.is_file(), reason="tennis games.csv absent")
def test_live_identity_copy_does_not_remint():
    before = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    report = verify_wta_identity(CFG, write=True)
    assert report["reminted"] is False
    after = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    assert list(before["internal_game_id"]) == list(after["internal_game_id"])
    assert report["identity_rule_version"] == IDENTITY_RULE_VERSION
    wta = after[after["sport"] == "WTA"]
    assert not any(str(g).startswith("WTA_") or str(g).startswith("TENNIS_") for g in wta["internal_game_id"])


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="WTA Phase 8 warehouse absent")
def test_live_wta_catalog_and_phase20_compile():
    cat = get_catalog(CFG, sport="WTA")
    assert cat.sport == "WTA"
    assert cat.observations["tradable_yes_bid_count"] > 0
    assert cat.observations["last_trade_print_count"] > 0
    assert cat.resolve([CapabilityName.TRADABLE_YES_BID_1M]).status is ResearchStatus.READY
    plan = compile_research(WTA_PHASE20_QUESTION, CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.observation_basis == "TRADABLE_YES_BID"
    if NBA_CROSSWALK.is_file():
        assert tennis_crosswalk_path(CFG, "WTA") != NBA_CROSSWALK


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="WTA Phase 8 warehouse absent")
def test_live_wta_reference_equals_optimized():
    from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest

    report = verify_wta_desk(CFG)
    assert report["golden_721_rewritten"] is False
    assert report["phase20_status"] == "READY"
    assert report["nba_crosswalk_sha256"] == NBA_CROSSWALK_SHA256
    ref = run_conditional_backtest(WTA_PHASE20_QUESTION, CFG, engine_id="reference")
    opt = run_conditional_backtest(WTA_PHASE20_QUESTION, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value == "READY"
    assert opt.status.value == "READY"
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0
