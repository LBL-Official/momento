"""Phase 1 logical entities. Does not change Confirm & Run or detectors."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path

import pytest

from roller.admin import load_dataset
from roller.warehouse.crosswalk import link_status, make_link
from roller.warehouse.entities import (
    ENTITY_MODEL_VERSION,
    Game,
    GameMarketLink,
    LinkStatus,
    Market,
    MarketObservation,
    ObservationBasis,
    PBPEvent,
    Settlement,
    SettlementResult,
    kalshi_result_to_settlement,
)
from roller.warehouse.query_context import ResearchContext
from roller.warehouse.schema import BASIS_LAST_TRADE_PRINT, BASIS_TRADABLE_YES_BID


def test_entity_model_version():
    assert ENTITY_MODEL_VERSION == "1.0.0"


def test_observation_has_no_generic_price():
    names = {f.name for f in fields(MarketObservation)}
    assert "price" not in names
    assert "yes_bid_close" in names
    assert "last_close_e4" in names
    assert "best_yes_bid_e4" in names


def test_game_and_market_have_no_price_or_settlement_result():
    game_names = {f.name for f in fields(Game)}
    market_names = {f.name for f in fields(Market)}
    pbp_names = {f.name for f in fields(PBPEvent)}
    assert "price" not in game_names
    assert "result" not in game_names
    assert "price" not in market_names
    assert "result" not in market_names
    assert "price" not in pbp_names
    assert "yes_bid_close" not in pbp_names


def test_tradable_observation_rejects_last_trade_fields():
    bar = MarketObservation(
        ticker="KX-T",
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at="2026-01-01T00:00:00Z",
        internal_game_id="NBA_20260101_AAA_BBB",
        yes_bid_close=6300,
        yes_ask_close=6400,
    )
    assert bar.basis.value == BASIS_TRADABLE_YES_BID
    assert bar.yes_bid_close == 6300
    assert bar.last_close_e4 is None
    with pytest.raises(ValueError, match="last_"):
        MarketObservation(
            ticker="KX-T",
            basis=ObservationBasis.TRADABLE_YES_BID,
            available_at="2026-01-01T00:00:00Z",
            yes_bid_close=6300,
            last_close_e4=6300,
        )


def test_last_trade_observation_rejects_yes_bid():
    bar = MarketObservation(
        ticker="KX-T",
        basis=ObservationBasis.LAST_TRADE_PRINT,
        available_at="2026-04-01T00:00:00Z",
        last_close_e4=7500,
        print_count=3,
    )
    assert bar.basis.value == BASIS_LAST_TRADE_PRINT
    assert bar.last_close_e4 == 7500
    assert bar.yes_bid_close is None
    with pytest.raises(ValueError, match="yes_bid"):
        MarketObservation(
            ticker="KX-T",
            basis=ObservationBasis.LAST_TRADE_PRINT,
            available_at="2026-04-01T00:00:00Z",
            last_close_e4=7500,
            yes_bid_close=7500,
        )


def test_orderbook_observation_is_not_a_candle():
    snap = MarketObservation(
        ticker="KX-T",
        basis=ObservationBasis.ORDERBOOK_SNAPSHOT,
        available_at="2026-09-12T20:00:00Z",
        best_yes_bid_e4=4300,
        best_no_bid_e4=5600,
    )
    assert snap.yes_bid_close is None
    assert snap.last_close_e4 is None
    with pytest.raises(ValueError, match="candle"):
        MarketObservation(
            ticker="KX-T",
            basis=ObservationBasis.ORDERBOOK_SNAPSHOT,
            available_at="2026-09-12T20:00:00Z",
            best_yes_bid_e4=4300,
            yes_bid_close=4300,
        )


def test_settlement_missing_is_not_no():
    assert kalshi_result_to_settlement("") is SettlementResult.MISSING
    assert kalshi_result_to_settlement(None) is SettlementResult.MISSING
    assert kalshi_result_to_settlement("yes") is SettlementResult.YES
    assert kalshi_result_to_settlement("no") is SettlementResult.NO
    assert kalshi_result_to_settlement("scalar") is SettlementResult.INVALID
    missing = Settlement(ticker="KX-T", result=SettlementResult.MISSING)
    no = Settlement(ticker="KX-T", result=SettlementResult.NO)
    assert missing.result is not no.result
    with pytest.raises(ValueError, match="invent"):
        Settlement(ticker="KX-T", result=SettlementResult.MISSING, settlement_value_e4=0)


def test_pbp_requires_identity_and_timestamp():
    ev = PBPEvent(
        internal_game_id="NBA_20251010_BOS_TOR",
        event_timestamp="2025-10-10T23:12:27Z",
        period="1",
        clock="PT12M00.00S",
    )
    assert ev.internal_game_id.startswith("NBA_")
    with pytest.raises(ValueError, match="internal_game_id"):
        PBPEvent(internal_game_id="", event_timestamp="2025-10-10T23:12:27Z")


def test_link_statuses_do_not_guess():
    assert link_status(internal_game_id="G1", ticker="T1") is LinkStatus.LINKED
    assert link_status(internal_game_id="", ticker="T1") is LinkStatus.UNLINKED
    assert link_status(internal_game_id="G1", ticker="") is LinkStatus.INVALID
    assert (
        link_status(internal_game_id="G1", ticker="T1", candidate_game_ids=("G1", "G2"))
        is LinkStatus.AMBIGUOUS
    )
    assert (
        link_status(internal_game_id="G1", ticker="T1", candidate_game_ids=("G2",))
        is LinkStatus.AMBIGUOUS
    )
    blank = make_link(ticker="KXMLB-X")
    assert blank.status is LinkStatus.UNLINKED
    assert blank.internal_game_id == ""


def test_research_context_is_a_bag_not_a_loader():
    ctx = ResearchContext(
        games=(
            Game(
                internal_game_id="NBA_20251010_BOS_TOR",
                sport="NBA",
                season="2025-2026",
                league="NBA",
                game_date="2025-10-10",
            ),
        ),
        links=(make_link(internal_game_id="NBA_20251010_BOS_TOR", ticker="KX-T"),),
    )
    assert len(ctx.games) == 1
    assert ctx.links[0].status is LinkStatus.LINKED
    import roller.warehouse.query_context as qc

    assert hasattr(qc, "get_research_context")
    assert callable(qc.get_research_context)


def test_live_execute_paths_do_not_import_entities():
    root = Path(__file__).resolve().parents[1] / "roller"
    forbidden = {
        "roller.warehouse.entities",
        "roller.warehouse.crosswalk",
        "roller.warehouse.query_context",
        "roller.warehouse.identity",
        "roller.warehouse.market_link",
        "roller.warehouse.observations",
        "roller.warehouse.pbp_events",
        "roller.warehouse.layout_v0",
        "roller.warehouse.settlement",
        "roller.warehouse.orderbook",
        "roller.warehouse.layout",
        "roller.warehouse.layout_benchmark",
        "roller.warehouse.coverage",
        "roller.warehouse.research_compiler",
        "roller.warehouse.conditional_backtest",
        "roller.warehouse.auto_ingest",
        "roller.warehouse.auto_verify",
        "roller.warehouse.frontend_contract",
    }
    for rel in (
        "admin.py",
        "research_query/execute.py",
        "research_query/compiler.py",
        "research_query/planner.py",
        "research_query/reference_engine.py",
        "research/first80.py",
    ):
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert imported.isdisjoint(forbidden), rel


def test_load_dataset_still_csv():
    src = inspect.getsource(load_dataset)
    assert "read_parquet" not in src
    assert "ResearchContext" not in src
    assert "GameMarketLink" not in src
