"""NCAAB warehouse desk. Does not remint IDs. Does not touch Confirm & Run 721."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.dashboard_adapter.bindings import NCAAB_FIRST80_P5_EXPECTED_N
from roller.superasi.iti.ncaab_question import NCAAB_ITI_QUESTION, iti_question_for_folder
from roller.warehouse.coverage import CapabilityName, get_catalog, question_capabilities
from roller.warehouse.desk import desk_lab_folder, desk_sport, observation_basis_for
from roller.warehouse.entities import LinkStatus
from roller.warehouse.identity import IDENTITY_RULE_VERSION, parse_internal_game_id
from roller.warehouse.layout import warehouse_root
from roller.warehouse.market_link import classify_market_ticker, identity_ticker_index
from roller.warehouse.ncaab_desk import (
    NBA_CROSSWALK_SHA256,
    PHASE20_QUESTION,
    ncaab_crosswalk_path,
    suite_candles_to_raw,
    verify_ncaab_desk,
    verify_ncaab_identity,
)
from roller.warehouse.production import unavailable_production_sport
from roller.warehouse.research_compiler import compile_research
from roller.research_query.models import ResearchStatus

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE_GAMES = ROLLER_ROOT / "data" / "ncaab" / "2025_2026" / "canonical" / "games.csv"
LIVE_WAREHOUSE = warehouse_root(CFG, "NCAAB", "2025-2026") / "manifest.json"
NBA_CROSSWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def test_desk_sport_and_basis():
    q = PHASE20_QUESTION
    assert desk_sport(q) == "NCAAB"
    assert observation_basis_for(q) == "TRADABLE_YES_BID"
    assert unavailable_production_sport(q) is None
    caps = question_capabilities(q)
    assert CapabilityName.TRADABLE_YES_BID_1M in caps
    assert CapabilityName.LAST_TRADE_PRINT_1M not in caps
    assert desk_lab_folder(q) == "NCAAB"
    assert desk_lab_folder(q, "NBA") == "NCAAB"


def test_unmapped_identity_ticker_still_links():
    index = identity_ticker_index(
        pd.DataFrame(
            [
                {
                    "internal_game_id": "NCAAB_20251103_AFA_BEL",
                    "sport": "NCAAB",
                    "season": "2025-2026",
                    "event_ticker": "KXNCAAMBGAME-25NOV03AFABEL",
                    "kalshi_market_yes_home": "KXNCAAMBGAME-25NOV03AFABEL-BEL",
                    "kalshi_market_yes_away": "KXNCAAMBGAME-25NOV03AFABEL-AFA",
                    "mapping_status": "UNMAPPED",
                }
            ]
        ),
        sport="NCAAB",
    )
    home = classify_market_ticker(ticker="KXNCAAMBGAME-25NOV03AFABEL-BEL", index=index)
    assert home.status is LinkStatus.LINKED
    assert home.internal_game_id == "NCAAB_20251103_AFA_BEL"
    assert "UNMAPPED" in home.source_evidence


def test_suite_candles_require_yes_bid():
    empty = suite_candles_to_raw(pd.DataFrame([{"ticker": "X", "end_time": "2025-11-03T01:00:00Z"}]))
    assert empty.empty
    ok = suite_candles_to_raw(
        pd.DataFrame(
            [
                {
                    "ticker": "KXNCAAMBGAME-25NOV03AFABEL-BEL",
                    "end_time": "2025-11-03T01:00:00Z",
                    "yes_bid_close_e4": 6500,
                    "yes_bid_open_e4": 6400,
                    "yes_bid_high_e4": 6600,
                    "yes_bid_low_e4": 6300,
                    "yes_ask_close_e4": 6700,
                    "volume_hundredths": 100,
                }
            ]
        )
    )
    assert list(ok["yes_bid_close"]) == ["6500"]
    assert "last_close_e4" not in ok.columns


def test_ncaab_iti_question_is_not_first80_or_nba_q4():
    q = iti_question_for_folder("NCAAB")
    assert q["universe"]["sports"] == ["NCAAB"]
    assert q["universe"]["market_data"] == ["candles"]
    assert q["entry_conditions"][0]["period"] is None
    assert q["entry_conditions"][0]["price_field"] == "yes_bid_close"
    assert "Q4" not in str(q)
    assert "FIRST80" not in str(q)
    assert NCAAB_ITI_QUESTION["entry_conditions"][0]["period"] is None


def test_frozen_721_constant_unchanged():
    assert NCAAB_FIRST80_P5_EXPECTED_N == 721


@pytest.mark.skipif(not LIVE_GAMES.is_file(), reason="NCAAB games.csv absent")
def test_live_identity_copy_does_not_remint():
    before = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    report = verify_ncaab_identity(CFG, write=True)
    assert report["reminted"] is False
    assert report["games_only_after"] == 0
    after = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    assert list(before["internal_game_id"]) == list(after["internal_game_id"])
    for gid in after["internal_game_id"]:
        parsed = parse_internal_game_id(gid)
        assert parsed is not None
        assert parsed.sport == "NCAAB"
    assert report["identity_rule_version"] == IDENTITY_RULE_VERSION


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="NCAAB Phase 8 warehouse absent")
def test_live_ncaab_catalog_and_phase20_compile():
    cat = get_catalog(CFG, sport="NCAAB")
    assert cat.sport == "NCAAB"
    assert cat.observations["tradable_yes_bid_count"] > 0
    assert cat.observations["last_trade_print_count"] == 0
    assert cat.resolve([CapabilityName.TRADABLE_YES_BID_1M]).status is ResearchStatus.READY
    assert cat.resolve([CapabilityName.TICK]).status is ResearchStatus.DATA_REQUIRED
    plan = compile_research(PHASE20_QUESTION, CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.observation_basis == "TRADABLE_YES_BID"
    if NBA_CROSSWALK.is_file():
        assert ncaab_crosswalk_path(CFG) != NBA_CROSSWALK


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="NCAAB Phase 8 warehouse absent")
def test_live_ncaab_reference_equals_optimized():
    from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest

    report = verify_ncaab_desk(CFG)
    assert report["golden_721_rewritten"] is False
    assert report["phase20_status"] == "READY"
    assert report["nba_crosswalk_sha256"] == NBA_CROSSWALK_SHA256
    ref = run_conditional_backtest(PHASE20_QUESTION, CFG, engine_id="reference")
    opt = run_conditional_backtest(PHASE20_QUESTION, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value == "READY"
    assert opt.status.value == "READY"
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0
