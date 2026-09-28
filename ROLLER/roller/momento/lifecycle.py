"""One offline FIRST80 lifecycle. Execution disabled. No invented fills."""

from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
from typing import Any

from roller.choosin_texas.ev import book_cents
from roller.choosin_texas.locks import (
    ENTRY_CENTS,
    GAIN_CENTS,
    NBA_PATH_N,
    POOL_CELLS,
    POOL_N,
    POOL_W,
    STOP_CENTS,
)
from roller.momento.contracts import (
    ExecutionIntent,
    Fill,
    GameState,
    HedgeAnalysis,
    MarketState,
    OddsSnapshot,
    PathModelSnapshot,
    PositionReconciliation,
    PositionSnapshot,
    PositionStratum,
    RiskAssessment,
    TargetExposure,
    TerminalModelSnapshot,
    TradeBreakdown,
    TradeSignal,
)
from roller.momento.execution import dry_run_intent, empty_reconciliation, no_fill
from roller.momento.position_management import target_from_research
from roller.momento.registry import LIVE_EXECUTION
from roller.momento.relative_value import TkRelativeValueV1, binary_yes_no

STAMP = "2026-09-18T08:00:00+00:00"
AS_OF = "2026-09-18T07:59:00+00:00"
GAME_ID = "offline_first80_lifecycle_v0"


def _now_ok() -> None:
    if LIVE_EXECUTION:
        raise RuntimeError("LIVE_EXECUTION must stay false")
    if datetime.fromisoformat(AS_OF) > datetime.fromisoformat(STAMP):
        raise RuntimeError("PIT fixture invalid")


def run_offline_first80() -> dict[str, Any]:
    _now_ok()
    s_numer = POOL_CELLS[0]
    book = book_cents(s_numer, POOL_N, gain=GAIN_CENTS, loss=ENTRY_CENTS - STOP_CENTS)
    tz = timezone.utc
    _ = tz

    ingestion = {
        "source_system": "data_ingestion",
        "status": "PARTIAL",
        "note": "Mapped ingest plane. Autojest NOT_IMPLEMENTED.",
    }
    game = GameState(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="database",
        game_id=GAME_ID,
        sport="NBA",
        period="research_pool",
        status="RESEARCH_ONLY",
    )
    market = MarketState(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="database",
        game_id=GAME_ID,
        yes_bid_cents=ENTRY_CENTS,
        status="RESEARCH_ONLY",
    )
    path = PathModelSnapshot(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="data_modeling",
        game_id=GAME_ID,
        n=POOL_N,
        s_numer=s_numer,
        s_denom=POOL_N,
        legacy_stop_cents=STOP_CENTS,
        provenance={"data_analysis": "superasi_four_cell_identity", "pool": "derived_four"},
        status="PARTIAL",
    )
    fair = OddsSnapshot(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="fair_odds_modeling",
        game_id=GAME_ID,
        model="none",
        status="NOT_IMPLEMENTED",
    )
    house = OddsSnapshot(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="in_house_odds_modeling",
        game_id=GAME_ID,
        model="XIB-NBA-V1",
        status="NOT_IMPLEMENTED",
        provenance={"phase_7": "NOT_AUTHORIZED"},
    )
    terminal = TerminalModelSnapshot(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="game_modeling",
        game_id=GAME_ID,
        n=POOL_N,
        w_numer=POOL_W,
        w_denom=POOL_N,
        status="PARTIAL",
        provenance={"note": "empirical W/N; not XIB vs K"},
    )
    signal = TradeSignal(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="signal_generation",
        game_id=GAME_ID,
        eligible=True,
        reason="research FIRST80 touch-80 on locked book; not live FIRST01",
        status="RESEARCH_ONLY",
    )
    trade = TradeBreakdown(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="trade_breakdown",
        game_id=GAME_ID,
        n=POOL_N,
        s_numer=s_numer,
        s_denom=POOL_N,
        entry_cents=ENTRY_CENTS,
        gain_cents=GAIN_CENTS,
        stop_cents=STOP_CENTS,
        book_cents=book,
        status="COMPLETE",
    )
    stratum = PositionStratum(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="position_stratification",
        game_id=GAME_ID,
        book_n=NBA_PATH_N,
        label="nba_2q_3q_neighborhood_research",
        status="PARTIAL",
    )
    dre = RiskAssessment(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="dynamic_risk_engine",
        game_id=GAME_ID,
        hold_reason_intact="UNKNOWN",
        phase3_is_execution_policy=False,
        status="RESEARCH_ONLY",
        provenance={"note": "Austin DRE research; not policy"},
    )
    hedge = HedgeAnalysis(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="hedging_analysis",
        game_id=GAME_ID,
        method="legacy_benchmark_hold_100",
        target_exposure_bps=10_000,
        note="BUY NO taker not implemented. 40-stop remains legacy benchmark.",
        status="PARTIAL",
    )
    rv = binary_yes_no(
        TkRelativeValueV1(),
        generated_at=STAMP,
        as_of=AS_OF,
        game_id=GAME_ID,
        yes_cents=80,
        no_cents=20,
        yes_anchor_cents=80,
        no_anchor_cents=20,
        beta=Fraction(1, 1),
    )
    position = PositionSnapshot(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="position_management",
        game_id=GAME_ID,
        yes_quantity=1,
        no_quantity=0,
        current_exposure_bps=10_000,
        status="RESEARCH_ONLY",
    )
    target: TargetExposure = target_from_research(
        hedge,
        rv,
        current_exposure_bps=position.current_exposure_bps,
        generated_at=STAMP,
        as_of=AS_OF,
        game_id=GAME_ID,
    )
    intent: ExecutionIntent = dry_run_intent(target)
    fill: Fill = no_fill(intent)
    recon: PositionReconciliation = empty_reconciliation(intent)

    hops = [
        ("data_ingestion", ingestion["status"]),
        ("database", game.status),
        ("data_modeling", path.status),
        ("fair_odds_modeling", fair.status),
        ("in_house_odds_modeling", house.status),
        ("game_modeling", terminal.status),
        ("signal_generation", signal.status),
        ("trade_breakdown", trade.status),
        ("position_stratification", stratum.status),
        ("dynamic_risk_engine", dre.status),
        ("hedging_analysis", hedge.status),
        ("relative_value_hedging", rv.status),
        ("position_management", target.status),
        ("algorithmic_execution", intent.status),
        ("trade_reconciliation", recon.status),
        ("system_orchestration", "NOT_IMPLEMENTED"),
    ]
    return {
        "live_execution": False,
        "submits": False,
        "nba_bot": "NOT_IMPLEMENTED",
        "game_id": GAME_ID,
        "legacy_stop_cents": STOP_CENTS,
        "hops": [{"source_system": src, "status": status} for src, status in hops],
        "objects": {
            "game": game.model_dump(),
            "market": market.model_dump(),
            "path": path.model_dump(),
            "fair_odds": fair.model_dump(),
            "in_house_odds": house.model_dump(),
            "terminal": terminal.model_dump(),
            "signal": signal.model_dump(),
            "trade": trade.model_dump(),
            "stratum": stratum.model_dump(),
            "dre": dre.model_dump(),
            "hedge": hedge.model_dump(),
            "rv": rv.model_dump(),
            "position": position.model_dump(),
            "target": target.model_dump(),
            "execution_intent": intent.model_dump(),
            "fill": fill.model_dump(),
            "reconciliation": recon.model_dump(),
        },
    }
