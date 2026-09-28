"""Versioned inter-system objects. Research / dry-run only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from roller.momento.registry import LIVE_EXECUTION

CONTRACT_SCHEMA = "momento_contract_v1"
LIVE_EXECUTION = LIVE_EXECUTION


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


class Envelope(BaseModel):
    schema_version: str = CONTRACT_SCHEMA
    generated_at: str
    as_of: str
    source_system: str
    game_id: str | None = None
    event_id: str | None = None
    ticker: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    live_execution: bool = False

    @model_validator(mode="after")
    def pit_and_live_gate(self) -> Envelope:
        if self.live_execution or LIVE_EXECUTION:
            raise ValueError("LIVE_EXECUTION must stay false")
        if _parse_iso(self.as_of) > _parse_iso(self.generated_at):
            raise ValueError("PIT violation: as_of after generated_at")
        return self


class GameState(Envelope):
    sport: str = "NBA"
    period: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    status: str = "RESEARCH_ONLY"


class MarketState(Envelope):
    yes_bid_cents: int | None = None
    basis: str = "TRADABLE_YES_BID"
    status: str = "RESEARCH_ONLY"


class OddsSnapshot(Envelope):
    model: str
    p_numer: int | None = None
    p_denom: int | None = None
    status: str = "NOT_IMPLEMENTED"


class PathModelSnapshot(Envelope):
    n: int
    s_numer: int
    s_denom: int
    legacy_stop_cents: int = 40
    status: str = "PARTIAL"


class TerminalModelSnapshot(Envelope):
    n: int
    w_numer: int
    w_denom: int
    status: str = "PARTIAL"


class TradeSignal(Envelope):
    rule: str = "FIRST80"
    eligible: bool
    reason: str
    status: str = "RESEARCH_ONLY"


class TradeBreakdown(Envelope):
    n: int
    s_numer: int
    s_denom: int
    entry_cents: int = 80
    gain_cents: int = 20
    stop_cents: int = 40
    book_cents: int
    legacy_benchmark: str = "stop_40"
    status: str = "COMPLETE"


class PositionStratum(Envelope):
    book_n: int = 604
    label: str
    status: str = "PARTIAL"


class PositionSnapshot(Envelope):
    yes_quantity: int = 0
    no_quantity: int = 0
    current_exposure_bps: int = 0
    status: str = "RESEARCH_ONLY"


class RiskAssessment(Envelope):
    hold_reason_intact: str = "UNKNOWN"
    phase3_is_execution_policy: bool = False
    status: str = "RESEARCH_ONLY"


class HedgeAnalysis(Envelope):
    method: str
    target_exposure_bps: int
    note: str
    status: str = "PARTIAL"


class RVHedgeAssessment(Envelope):
    method: str = "tk_relative_value_v1"
    base_price_cents: int
    wing_price_cents: int
    base_anchor_cents: int
    wing_anchor_cents: int
    beta_numer: int
    beta_denom: int
    relationship_multiplier_numer: int
    relationship_multiplier_denom: int
    expected_wing_cents_numer: int
    expected_wing_cents_denom: int
    residual_cents_numer: int
    residual_cents_denom: int
    rv_ticks_numer: int
    rv_ticks_denom: int
    ticks_per_handle: int
    binary_formula_is_truth: bool = False
    status: str = "RESEARCH_ONLY"


class TargetExposure(Envelope):
    current_exposure_bps: int
    target_exposure_bps: int
    status: str = "RESEARCH_ONLY"


class ExecutionIntent(Envelope):
    bot_id: str = "nba-first80-001"
    submits: bool = False
    mode: Literal["dry_run", "shadow", "disabled"] = "disabled"
    target_exposure_bps: int
    status: str = "NOT_IMPLEMENTED"


class OrderIntent(Envelope):
    bot_id: str = "nba-first80-001"
    side: str
    quantity: int
    submits: bool = False
    status: str = "NOT_IMPLEMENTED"


class ExecutionReport(Envelope):
    bot_id: str = "nba-first80-001"
    submits: bool = False
    accepted: bool = False
    status: str = "NOT_IMPLEMENTED"


class Fill(Envelope):
    quantity: int = 0
    price_cents: int | None = None
    observed: bool = False
    status: str = "NOT_IMPLEMENTED"


class PositionReconciliation(Envelope):
    yes_quantity: int = 0
    no_quantity: int = 0
    matched: bool = True
    note: str = "No NBA fills. Dry-run only."
    status: str = "NOT_IMPLEMENTED"


class SystemHealth(Envelope):
    system_id: str
    state: str
    ok: bool | None = None
    detail: str = ""


CONTRACT_TYPES: dict[str, type[Envelope]] = {
    "GameState": GameState,
    "MarketState": MarketState,
    "OddsSnapshot": OddsSnapshot,
    "PathModelSnapshot": PathModelSnapshot,
    "TerminalModelSnapshot": TerminalModelSnapshot,
    "TradeSignal": TradeSignal,
    "TradeBreakdown": TradeBreakdown,
    "PositionStratum": PositionStratum,
    "PositionSnapshot": PositionSnapshot,
    "RiskAssessment": RiskAssessment,
    "HedgeAnalysis": HedgeAnalysis,
    "RVHedgeAssessment": RVHedgeAssessment,
    "TargetExposure": TargetExposure,
    "ExecutionIntent": ExecutionIntent,
    "OrderIntent": OrderIntent,
    "ExecutionReport": ExecutionReport,
    "Fill": Fill,
    "PositionReconciliation": PositionReconciliation,
    "SystemHealth": SystemHealth,
}
