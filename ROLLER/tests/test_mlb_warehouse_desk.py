"""MLB warehouse desk. Does not remint game_pk. Does not touch Confirm & Run."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.coverage import CapabilityName, get_catalog, question_capabilities
from roller.warehouse.desk import desk_sport, observation_basis_for
from roller.warehouse.entities import LinkStatus, ObservationBasis
from roller.warehouse.identity import IDENTITY_RULE_VERSION, parse_internal_game_id
from roller.warehouse.layout import warehouse_root
from roller.warehouse.market_link import classify_market_ticker, identity_ticker_index
from roller.jump.bots.versions import FACTORY_ID
from roller.jump.bots.factory import FACTORY
from roller.superasi.iti.mlb_question import MLB_ITI_QUESTION, iti_question_for_folder
from roller.warehouse.mlb_desk import (
    PHASE20_QUESTION,
    assert_no_yes_bid_columns,
    mlb_crosswalk_path,
    project_last_trade_frame,
    verify_mlb_desk,
    verify_mlb_identity,
)
from roller.warehouse.production import unavailable_production_sport
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE_GAMES = ROLLER_ROOT / "data" / "mlb" / "2025_2026" / "canonical" / "games.csv"
LIVE_WAREHOUSE = warehouse_root(CFG, "MLB", "2025-2026") / "manifest.json"
NBA_CROSSWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def _identity_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "internal_game_id": "MLB_20250401_NYY_BOS_746000",
                "sport": "MLB",
                "season": "2025-2026",
                "event_ticker": "KXMLBGAME-25APR01NYYBOS",
                "kalshi_market_yes_home": "KXMLBGAME-25APR01NYYBOS-BOS",
                "kalshi_market_yes_away": "KXMLBGAME-25APR01NYYBOS-NYY",
                "mapping_status": "MAPPED",
            },
            {
                "internal_game_id": "MLB_20260802_MIL_LAA_823996",
                "sport": "MLB",
                "season": "2025-2026",
                "event_ticker": "KXMLBGAME-26AUG02MILLAA",
                "kalshi_market_yes_home": "KXMLBGAME-26AUG02MILLAA-LAA",
                "kalshi_market_yes_away": "",
                "mapping_status": "MAPPED",
            },
        ]
    )


LAST_TRADE_QUESTION = replace(
    PHASE20_QUESTION.on_last_trade_basis(),
    universe=replace(PHASE20_QUESTION.universe, market_data=("last_trade",)),
)


def test_desk_sport_and_basis():
    q = PHASE20_QUESTION
    assert desk_sport(q) == "MLB"
    assert observation_basis_for(q) == "TRADABLE_YES_BID"
    assert observation_basis_for(LAST_TRADE_QUESTION) == "LAST_TRADE_PRINT"
    assert unavailable_production_sport(q) is None


def test_last_trade_is_not_tick_capability():
    caps = question_capabilities(LAST_TRADE_QUESTION)
    assert CapabilityName.LAST_TRADE_PRINT_1M in caps
    assert CapabilityName.TICK not in caps
    assert CapabilityName.TRADABLE_YES_BID_1M not in caps
    candle_caps = question_capabilities(PHASE20_QUESTION)
    assert CapabilityName.TRADABLE_YES_BID_1M in candle_caps
    assert CapabilityName.LAST_TRADE_PRINT_1M not in candle_caps


def test_one_sided_identity_ticker_stays_explicit():
    index = identity_ticker_index(_identity_rows(), sport="MLB")
    home = classify_market_ticker(ticker="KXMLBGAME-26AUG02MILLAA-LAA", index=index)
    missing = classify_market_ticker(ticker="KXMLBGAME-26AUG02MILLAA-MIL", index=index)
    assert home.status is LinkStatus.LINKED
    assert home.internal_game_id == "MLB_20260802_MIL_LAA_823996"
    assert missing.status is LinkStatus.UNLINKED
    assert "823996" in home.internal_game_id


def test_last_trade_frame_rejects_yes_bid_and_stamps_link():
    with pytest.raises(ValueError, match="yes-bid"):
        assert_no_yes_bid_columns(["last_close_e4", "yes_bid_close"])
    crosswalk = pd.DataFrame(
        [
            {
                "ticker": "KXMLBGAME-25APR01NYYBOS-BOS",
                "internal_game_id": "MLB_20250401_NYY_BOS_746000",
                "link_status": "LINKED",
            }
        ]
    )
    raw = pd.DataFrame(
        [
            {
                "ticker": "KXMLBGAME-25APR01NYYBOS-BOS",
                "internal_game_id": "MLB_20250401_NYY_BOS_746000",
                "available_at": "2025-04-01T17:00:00Z",
                "last_close_e4": 6500,
                "last_open_e4": 6400,
                "last_high_e4": 6600,
                "last_low_e4": 6300,
            }
        ]
    )
    out = project_last_trade_frame(raw, crosswalk)
    assert list(out["basis"]) == [ObservationBasis.LAST_TRADE_PRINT.value]
    assert "yes_bid_close" not in out.columns
    assert out.iloc[0]["internal_game_id"] == "MLB_20250401_NYY_BOS_746000"
    assert out.iloc[0]["game_link_status"] == "LINKED"


def test_q4_on_mlb_is_operation_required():
    q = ResearchQuestion(
        universe=Universe(
            sports=("MLB",),
            leagues=("MLB",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("last_trade",),
            date_from="2025-04-01",
            date_to="2025-04-30",
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6500,
                period="Q4",
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4000, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
    )
    plan = compile_research(q, CFG)
    assert plan.status in {ResearchStatus.OPERATION_REQUIRED, ResearchStatus.DATA_REQUIRED}
    if plan.status is ResearchStatus.OPERATION_REQUIRED:
        assert "MLB_BASKETBALL_PERIOD" in plan.missing_operations


@pytest.mark.skipif(not LIVE_GAMES.is_file(), reason="MLB games.csv absent")
def test_live_identity_copy_does_not_remint():
    before = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    report = verify_mlb_identity(CFG, write=True)
    assert report["reminted"] is False
    assert report["games_only_after"] == 0
    after = pd.read_csv(LIVE_GAMES, dtype=str, keep_default_na=False)
    assert list(before["internal_game_id"]) == list(after["internal_game_id"])
    for gid in after["internal_game_id"]:
        parsed = parse_internal_game_id(gid)
        assert parsed is not None
        assert parsed.game_pk
    assert report["identity_rule_version"] == IDENTITY_RULE_VERSION


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="MLB Phase 8 warehouse absent")
def test_mlb_frontend_draft_to_results():
    from roller.warehouse.frontend_contract import (
        compile_frontend_research,
        execute_frontend_research,
        question_from_draft,
    )

    question, errors = question_from_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dateFrom": "2025-04-01",
                "dateTo": "2025-04-30",
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 65}],
            "exitConditions": [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            ],
        }
    )
    assert question is not None
    assert not errors
    assert question.universe.sports == ("MLB",)
    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == "READY"
    executed = execute_frontend_research({"question": question.to_dict()}, include_reference=True)
    assert executed["status"] == "READY"
    assert executed["difference_count"] == 0
    assert executed["results_contract"]["statistics"]["basis"] == "observed_candle_path"


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="MLB Phase 8 warehouse absent")
def test_live_mlb_catalog_and_phase20_compile():
    cat = get_catalog(CFG, sport="MLB")
    assert cat.sport == "MLB"
    assert cat.observations["last_trade_print_count"] > 0
    assert cat.observations["tradable_yes_bid_count"] > 0
    assert cat.resolve([CapabilityName.LAST_TRADE_PRINT_1M]).status is ResearchStatus.READY
    assert cat.resolve([CapabilityName.TICK]).status is ResearchStatus.DATA_REQUIRED
    plan = compile_research(PHASE20_QUESTION, CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.observation_basis == "TRADABLE_YES_BID"
    last_plan = compile_research(LAST_TRADE_QUESTION, CFG)
    assert last_plan.status is ResearchStatus.READY
    assert last_plan.observation_basis == "LAST_TRADE_PRINT"
    if NBA_CROSSWALK.is_file():
        assert mlb_crosswalk_path(CFG) != NBA_CROSSWALK


def test_jump_factory_stays_mlb_factory_v1():
    assert FACTORY_ID == "mlb_factory_v1"
    assert FACTORY["factory_id"] == "mlb_factory_v1"
    assert FACTORY["signal"] == "80_to_81_yes_bid"
    assert FACTORY["max_entry_cents"] == 83


def test_mlb_iti_question_is_not_nba_q4():
    q = iti_question_for_folder("MLB")
    assert q["universe"]["sports"] == ["MLB"]
    assert q["universe"]["market_data"] == ["candles"]
    assert q["entry_conditions"][0]["period"] is None
    assert q["entry_conditions"][0]["clock"] is None
    assert q["entry_conditions"][0]["price_field"] == "yes_bid_close"
    assert "Q4" not in str(q)
    assert MLB_ITI_QUESTION["entry_conditions"][0]["period"] is None


@pytest.mark.skipif(not LIVE_WAREHOUSE.is_file(), reason="MLB Phase 8 warehouse absent")
def test_live_mlb_edges_and_reference_equals_optimized():
    from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest
    from roller.warehouse.entities import ObservationBasis
    from roller.warehouse.layout import observations_dir, pbp_dir
    from roller.warehouse.partitioning import list_month_parquets, month_key

    report = verify_mlb_desk(CFG)
    assert report["golden_554_1661_rewritten"] is False
    assert report["phase20_status"] == "READY"
    assert "2025-12" in report["missing_last_trade_vs_candle"]
    last_dir = observations_dir(CFG, "MLB", "2025-2026", basis="LAST_TRADE_PRINT")
    candle_dir = observations_dir(CFG, "MLB", "2025-2026", basis="TRADABLE_YES_BID")
    last_months = {month_key(p) for p in list_month_parquets(last_dir)}
    candle_months = {month_key(p) for p in list_month_parquets(candle_dir)}
    assert "2025-04" in last_months
    assert "2025-12" in candle_months
    assert "2025-12" not in last_months
    last_sample = pd.read_parquet(list_month_parquets(last_dir)[0])
    candle_sample = pd.read_parquet(list_month_parquets(candle_dir)[0])
    assert "yes_bid_close" not in last_sample.columns
    assert "last_close_e4" not in candle_sample.columns
    assert set(last_sample["basis"].astype(str).unique()) == {ObservationBasis.LAST_TRADE_PRINT.value}
    pbp_months = list_month_parquets(pbp_dir(CFG, "MLB", "2025-2026"))
    assert pbp_months
    pbp_sample = pd.read_parquet(pbp_months[0], columns=["inning", "half", "period"])
    assert "inning" in pbp_sample.columns
    links = pd.read_parquet(mlb_crosswalk_path(CFG))
    identity = pd.read_csv(CFG.root / "meta" / "game_identity.csv", dtype=str, keep_default_na=False)
    mlb_ident = identity[identity["sport"] == "MLB"]
    one_sided = mlb_ident[
        ((mlb_ident["kalshi_market_yes_home"].str.strip() == "") ^ (mlb_ident["kalshi_market_yes_away"].str.strip() == ""))
    ]
    for rec in one_sided.to_dict("records"):
        gid = rec["internal_game_id"]
        present = {rec["kalshi_market_yes_home"].strip(), rec["kalshi_market_yes_away"].strip()} - {""}
        linked = links[(links["internal_game_id"] == gid) & (links["link_status"] == "LINKED")]
        assert set(linked["ticker"].astype(str)) <= present
    doubleheaders = mlb_ident[mlb_ident["game_date"] == "2026-08-02"]
    if len(doubleheaders) >= 2:
        assert doubleheaders["internal_game_id"].nunique() == len(doubleheaders)
        pks = [parse_internal_game_id(g).game_pk for g in doubleheaders["internal_game_id"] if parse_internal_game_id(g)]
        assert len(set(pks)) == len(doubleheaders)
    ref = run_conditional_backtest(PHASE20_QUESTION, CFG, engine_id="reference")
    opt = run_conditional_backtest(PHASE20_QUESTION, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value in {"READY", "ZERO_RESULTS"}
    assert opt.status.value == ref.status.value
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0
    assert ref.observation_basis == "TRADABLE_YES_BID"
    empty = ResearchQuestion(
        universe=Universe(
            sports=("MLB",),
            leagues=("MLB",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            date_from="2024-01-01",
            date_to="2024-01-02",
        ),
        entry_conditions=PHASE20_QUESTION.entry_conditions,
        path_conditions=PHASE20_QUESTION.path_conditions,
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
    )
    empty_plan = compile_research(empty, CFG)
    assert empty_plan.status is ResearchStatus.READY
    empty_run = run_conditional_backtest(empty, CFG)
    assert empty_run.status.value == "ZERO_RESULTS"
    assert empty_run.population == 0
