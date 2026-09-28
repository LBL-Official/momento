"""Phase 10 ResearchContext loader. Filtered parquet. No backtest. No fake L2."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from roller.admin import load_dataset
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
from roller.warehouse.entities import (
    LinkStatus,
    ObservationBasis,
    SettlementResult,
)
from roller.warehouse.query_context import ResearchContext, get_research_context

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)


def _question(
    *,
    date_from: str | None = "2025-10-10",
    date_to: str | None = "2025-10-10",
    market_data: tuple[str, ...] = ("candles",),
    game_data: tuple[str, ...] = ("pbp",),
    sports: tuple[str, ...] = ("NBA",),
    leagues: tuple[str, ...] = ("NBA",),
    seasons: tuple[str, ...] = ("2025-2026",),
    requested_dimensions: tuple[str, ...] = ("HOLD_TO_SETTLEMENT",),
    period: str | None = "Q2",
) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=sports,
            leagues=leagues,
            seasons=seasons,
            markets=("kalshi",),
            market_data=market_data,
            game_data=game_data,
            date_from=date_from,
            date_to=date_to,
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period=period,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=requested_dimensions,
    )


def test_research_context_bag_still_constructible_without_loader():
    ctx = ResearchContext()
    assert ctx.games == ()
    assert ctx.observation_basis == "TRADABLE_YES_BID"
    assert ctx.pit_field == "available_at"


def test_valid_nba_context_resolves_identity_and_pit():
    result = get_research_context(_question(), CFG)
    assert result.status is ResearchStatus.READY
    ctx = result.context
    assert ctx is not None
    gids = {g.internal_game_id for g in ctx.games}
    assert "NBA_20251010_BOS_TOR" in gids
    assert all(g.sport == "NBA" for g in ctx.games)
    assert all(link.status is LinkStatus.LINKED for link in ctx.links if link.internal_game_id in gids)
    ticker_to_gid = {link.ticker: link.internal_game_id for link in ctx.links}
    assert ticker_to_gid
    for market in ctx.markets:
        assert market.ticker in ticker_to_gid
        assert market.internal_game_id == ticker_to_gid[market.ticker]
        assert market.internal_game_id in gids
    assert ctx.observation_basis == "TRADABLE_YES_BID"
    assert ctx.observation_resolution == "1_MINUTE_CANDLE"
    assert ctx.pit_field == "available_at"
    assert ctx.observations
    assert all(o.basis is ObservationBasis.TRADABLE_YES_BID for o in ctx.observations)
    assert all(o.available_at for o in ctx.observations)
    assert all(o.last_close_e4 is None for o in ctx.observations)
    assert all(o.ticker in ticker_to_gid for o in ctx.observations)
    assert all(o.internal_game_id == ticker_to_gid[o.ticker] for o in ctx.observations)
    bos_obs = [o for o in ctx.observations if o.internal_game_id == "NBA_20251010_BOS_TOR"]
    assert len(bos_obs) == 1136
    assert ctx.settlements
    assert {s.result for s in ctx.settlements} <= {SettlementResult.YES, SettlementResult.NO, SettlementResult.INVALID, SettlementResult.MISSING}
    assert ctx.pbp_events
    assert all(ev.internal_game_id in gids for ev in ctx.pbp_events)
    dumped = str(result.to_dict()) + str(ctx.coverage) + str(ctx.warehouse_manifest)
    assert "/Users/" not in dumped
    assert "derived/warehouse" not in dumped


def test_settlement_not_inferred_and_invalid_preserved():
    result = get_research_context(
        _question(date_from="2026-01-08", date_to="2026-01-08", period=None, game_data=()),
        CFG,
    )
    assert result.status is ResearchStatus.READY
    ctx = result.context
    assert ctx is not None
    assert any(g.internal_game_id == "NBA_20260108_MIA_CHI" for g in ctx.games)
    mia_tickers = {
        link.ticker
        for link in ctx.links
        if link.internal_game_id == "NBA_20260108_MIA_CHI"
    }
    mia_settle = [s for s in ctx.settlements if s.ticker in mia_tickers]
    assert mia_settle
    assert all(s.result is SettlementResult.INVALID for s in mia_settle)
    assert not any(o.internal_game_id == "NBA_20260108_MIA_CHI" for o in ctx.observations)
    src = inspect.getsource(get_research_context)
    assert "home_win" not in src
    assert "official_settlement" not in src


def test_missing_observations_and_pbp_are_empty_not_invented():
    result = get_research_context(
        _question(date_from="2026-01-08", date_to="2026-01-08", game_data=("pbp",)),
        CFG,
    )
    ctx = result.context
    assert ctx is not None
    assert not any(o.internal_game_id == "NBA_20260108_MIA_CHI" for o in ctx.observations)
    assert not any(ev.internal_game_id == "NBA_20260108_MIA_CHI" for ev in ctx.pbp_events)


def test_tick_and_l2_are_data_required_without_fabricated_observations():
    tick = get_research_context(_question(market_data=("tick",)), CFG)
    assert tick.status is ResearchStatus.DATA_REQUIRED
    assert tick.context is None
    assert "TICK" in tick.missing_data
    l2 = get_research_context(_question(market_data=("l2",)), CFG)
    assert l2.status is ResearchStatus.DATA_REQUIRED
    assert l2.context is None
    assert "HISTORICAL_L2" in l2.missing_data
    tape = get_research_context(_question(market_data=("trade_tape",)), CFG)
    assert tape.status is ResearchStatus.DATA_REQUIRED
    assert tape.context is None


def test_pbp_candle_pit_alignment_is_operation_required():
    result = get_research_context(
        _question(requested_dimensions=("PBP_MARKET_PIT_ALIGNMENT",)),
        CFG,
    )
    assert result.status is ResearchStatus.OPERATION_REQUIRED
    assert result.context is None
    assert "PBP_MARKET_PIT_ALIGNMENT" in result.missing_operations


def test_context_is_deterministic_and_carries_provenance():
    a = get_research_context(_question(), CFG)
    b = get_research_context(_question(), CFG)
    assert a.status is ResearchStatus.READY
    ca, cb = a.context, b.context
    assert ca is not None and cb is not None
    assert ca.fingerprints == cb.fingerprints
    assert len(ca.observations) == len(cb.observations)
    assert [o.available_at for o in ca.observations] == [o.available_at for o in cb.observations]
    assert ca.warehouse_version == cb.warehouse_version
    assert ca.catalog_version
    assert ca.identity_version == "1.0.0"
    assert ca.pit_field == "available_at"
    assert ca.question is not None
    assert "manifest_updated_at" in ca.fingerprints


def test_no_csv_confirm_and_run_or_first80_dependency():
    src = inspect.getsource(get_research_context)
    assert "kalshi_markets.csv" not in src
    assert "load_dataset" not in src
    assert "first80" not in src.lower()
    assert "official_settlement" not in src
    assert "compile_question" not in src
    load_src = inspect.getsource(load_dataset)
    assert "get_research_context" not in load_src
    tree = ast.parse((ROLLER_ROOT / "roller" / "research_query" / "execute.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.warehouse.query_context" not in imported
