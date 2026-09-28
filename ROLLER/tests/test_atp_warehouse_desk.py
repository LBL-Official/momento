"""ATP warehouse desk. Does not remint event tickers. Does not touch Confirm & Run goldens."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.dashboard_adapter.bindings import NCAAB_FIRST80_P5_EXPECTED_N
from roller.superasi.iti.atp_question import ATP_ITI_QUESTION, iti_question_for_folder
from roller.warehouse.coverage import CapabilityName, get_catalog, question_capabilities
from roller.warehouse.desk import desk_lab_folder, desk_sport, observation_basis_for
from roller.warehouse.entities import LinkStatus
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.layout import warehouse_root
from roller.warehouse.market_link import _default_market_type, classify_market_ticker, identity_ticker_index
from roller.warehouse.production import unavailable_production_sport
from roller.warehouse.research_compiler import compile_research
from roller.research_query.models import ResearchStatus
from roller.warehouse.tennis_desk import (
    ATP_PHASE20_QUESTION,
    NBA_CROSSWALK_SHA256,
    tennis_crosswalk_path,
    verify_atp_desk,
    verify_atp_identity,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE_GAMES = ROLLER_ROOT / "data" / "tennis" / "2025_2026" / "canonical" / "games.csv"
LIVE_WAREHOUSE = warehouse_root(CFG, "ATP", "2025-2026") / "manifest.json"
NBA_CROSSWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def test_desk_sport_and_basis():
    q = ATP_PHASE20_QUESTION
    assert desk_sport(q) == "ATP"
    assert observation_basis_for(q) == "TRADABLE_YES_BID"
    assert unavailable_production_sport(q) is None
    caps = question_capabilities(q)
    assert CapabilityName.TRADABLE_YES_BID_1M in caps
    assert desk_lab_folder(q) == "ATP"
    assert desk_lab_folder(q, "NBA") == "ATP"


def test_match_series_is_kxatpmatch_not_kxatpgame():
    assert _default_market_type("ATP") == "KXATPMATCH"
    assert _default_market_type("ATP") != "KXATPGAME"


def test_identity_p1_ticker_still_links():
    index = identity_ticker_index(
        pd.DataFrame(
            [
                {
                    "internal_game_id": "KXATPMATCH-25JUL01EXAMPLE",
                    "sport": "ATP",
                    "season": "2025-2026",
                    "event_ticker": "KXATPMATCH-25JUL01EXAMPLE",
                    "kalshi_market_yes_p1": "KXATPMATCH-25JUL01EXAMPLE-AAA",
                    "kalshi_market_yes_p2": "KXATPMATCH-25JUL01EXAMPLE-BBB",
                    "mapping_status": "UNMAPPED",
                }
            ]
        ),
        sport="ATP",
    )
    p1 = classify_market_ticker(ticker="KXATPMATCH-25JUL01EXAMPLE-AAA", index=index)
    assert p1.status is LinkStatus.LINKED
    assert p1.internal_game_id == "KXATPMATCH-25JUL01EXAMPLE"


def test_atp_iti_question_is_not_first80_or_nba_q4():
    q = iti_question_for_folder("ATP")
    assert q["universe"]["sports"] == ["ATP"]
    assert q["universe"]["market_data"] == ["candles"]
    assert q["entry_conditions"][0]["period"] is None
    assert q["entry_conditions"][0]["price_field"] == "yes_bid_close"
    assert "Q4" not in str(q)
    assert "FIRST80" not in str(q)
    assert ATP_ITI_QUESTION["universe"]["sports"] != ["NBA"]


def test_frozen_lock_constants_unchanged():
    assert NCAAB_FIRST80_P5_EXPECTED_N == 721


@pytest.mark.skipif(not LIVE_GAMES.is_file(), reason="tennis games.csv absent")
def test_live_identity_copy_does_not_remint():
    before = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    report = verify_atp_identity(CFG, write=True)
    assert report["reminted"] is False
    after = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    assert list(before["internal_game_id"]) == list(after["internal_game_id"])
    assert report["identity_rule_version"] == IDENTITY_RULE_VERSION
    atp = after[after["sport"] == "ATP"]
    assert not any(str(g).startswith("ATP_") or str(g).startswith("TENNIS_") for g in atp["internal_game_id"])


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="ATP Phase 8 warehouse absent")
def test_live_atp_catalog_and_phase20_compile():
    cat = get_catalog(CFG, sport="ATP")
    assert cat.sport == "ATP"
    assert cat.observations["tradable_yes_bid_count"] > 0
    assert cat.observations["last_trade_print_count"] > 0
    assert cat.resolve([CapabilityName.TRADABLE_YES_BID_1M]).status is ResearchStatus.READY
    assert cat.resolve([CapabilityName.LAST_TRADE_PRINT_1M]).status is ResearchStatus.READY
    assert cat.resolve([CapabilityName.TICK]).status is ResearchStatus.DATA_REQUIRED
    plan = compile_research(ATP_PHASE20_QUESTION, CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.observation_basis == "TRADABLE_YES_BID"
    if NBA_CROSSWALK.is_file():
        assert tennis_crosswalk_path(CFG, "ATP") != NBA_CROSSWALK


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="ATP Phase 8 warehouse absent")
def test_live_atp_reference_equals_optimized():
    from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest

    report = verify_atp_desk(CFG)
    assert report["golden_721_rewritten"] is False
    assert report["phase20_status"] == "READY"
    assert report["nba_crosswalk_sha256"] == NBA_CROSSWALK_SHA256
    ref = run_conditional_backtest(ATP_PHASE20_QUESTION, CFG, engine_id="reference")
    opt = run_conditional_backtest(ATP_PHASE20_QUESTION, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value == "READY"
    assert opt.status.value == "READY"
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0
