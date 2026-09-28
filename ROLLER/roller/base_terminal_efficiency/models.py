"""Observation contract. Statuses are OBSERVED / DERIVED / UNAVAILABLE / AMBIGUOUS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from roller.base_terminal_efficiency.versions import (
    CODE_VERSION,
    ENTRY_PRICE_DEFINITION,
    SCHEMA_VERSION,
    SEMANTICS_VERSION,
)

OBSERVED = "OBSERVED"
DERIVED = "DERIVED"
UNAVAILABLE = "UNAVAILABLE"
AMBIGUOUS = "AMBIGUOUS"
UNALIGNED = "UNALIGNED"
TERMINAL_YES = "YES"
TERMINAL_NO = "NO"
TERMINAL_MISSING = "MISSING"
WIN = "WIN"
LOSS = "LOSS"
INVALID_SEMANTICS = "INVALID_SEMANTICS"
DATA_REQUIRED = "DATA_REQUIRED"
TIE_EXACT_TIMESTAMP = "TIE_EXACT_TIMESTAMP"


@dataclass(frozen=True)
class Observation:
    observation_id: str
    game_id: str
    ticker: str
    league: str | None
    season: str | None
    team_side: str | None
    team: str | None
    opponent: str | None
    observation_ts: str
    period: Any = None
    game_clock: Any = None
    remaining_game_time: int | None = None
    elapsed_game_time: int | None = None
    alignment_status: str = UNALIGNED
    team_points: int | None = None
    opponent_points: int | None = None
    total_points: int | None = None
    point_differential: int | None = None
    point_differential_abs_e0: int | None = None
    point_differential_sign: int | None = None
    score_path_team: tuple[int, ...] = ()
    score_path_opponent: tuple[int, ...] = ()
    score_change_from_start: int | None = None
    opponent_score_change_from_start: int | None = None
    total_score_change_from_start: int | None = None
    differential_change_from_start: int | None = None
    team_score_volatility: float | None = None
    opponent_score_volatility: float | None = None
    total_score_volatility: float | None = None
    differential_volatility: float | None = None
    entry_price_e4: int = 0
    entry_price_cents: int = 0
    entry_price_ts: str = ""
    entry_price_source: str = "kalshi_candles"
    entry_price_definition: str = ENTRY_PRICE_DEFINITION
    initial_market_price_e4: int | None = None
    signed_price_displacement_e4: int | None = None
    absolute_price_displacement_e4: int | None = None
    cumulative_price_travel_e4: int | None = None
    max_price_pre_entry_e4: int | None = None
    min_price_pre_entry_e4: int | None = None
    price_path_range_e4: int | None = None
    entry_price_volatility: float | None = None
    recent_entry_price_volatility: float | None = None
    score_status: str = UNAVAILABLE
    market_status: str = OBSERVED
    feature_status: str = UNAVAILABLE
    terminal_outcome: str = TERMINAL_MISSING
    source_dataset: str = "kalshi_candles+pbp"
    source_version: str = ""
    semantics_version: str = SEMANTICS_VERSION
    schema_version: str = SCHEMA_VERSION
    code_version: str = CODE_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "observation_id": self.observation_id,
            "game_id": self.game_id,
            "ticker": self.ticker,
            "league": self.league,
            "season": self.season,
            "team_side": self.team_side,
            "team": self.team,
            "opponent": self.opponent,
            "observation_ts": self.observation_ts,
            "period": self.period,
            "game_clock": self.game_clock,
            "remaining_game_time": self.remaining_game_time,
            "elapsed_game_time": self.elapsed_game_time,
            "alignment_status": self.alignment_status,
            "team_points": self.team_points,
            "opponent_points": self.opponent_points,
            "total_points": self.total_points,
            "point_differential": self.point_differential,
            "point_differential_abs_e0": self.point_differential_abs_e0,
            "point_differential_sign": self.point_differential_sign,
            "score_path_team": list(self.score_path_team),
            "score_path_opponent": list(self.score_path_opponent),
            "score_change_from_start": self.score_change_from_start,
            "opponent_score_change_from_start": self.opponent_score_change_from_start,
            "total_score_change_from_start": self.total_score_change_from_start,
            "differential_change_from_start": self.differential_change_from_start,
            "team_score_volatility": self.team_score_volatility,
            "opponent_score_volatility": self.opponent_score_volatility,
            "total_score_volatility": self.total_score_volatility,
            "differential_volatility": self.differential_volatility,
            "team_points_volatility": self.team_score_volatility,
            "opponent_points_volatility": self.opponent_score_volatility,
            "total_points_volatility": self.total_score_volatility,
            "entry_price_e4": self.entry_price_e4,
            "entry_price_cents": self.entry_price_cents,
            "entry_price_ts": self.entry_price_ts,
            "entry_price_source": self.entry_price_source,
            "entry_price_definition": self.entry_price_definition,
            "initial_market_price_e4": self.initial_market_price_e4,
            "signed_price_displacement_e4": self.signed_price_displacement_e4,
            "absolute_price_displacement_e4": self.absolute_price_displacement_e4,
            "cumulative_price_travel_e4": self.cumulative_price_travel_e4,
            "max_price_pre_entry_e4": self.max_price_pre_entry_e4,
            "min_price_pre_entry_e4": self.min_price_pre_entry_e4,
            "price_path_range_e4": self.price_path_range_e4,
            "entry_price_volatility": self.entry_price_volatility,
            "recent_entry_price_volatility": self.recent_entry_price_volatility,
            "score_status": self.score_status,
            "market_status": self.market_status,
            "feature_status": self.feature_status,
            "terminal_outcome": self.terminal_outcome,
            "source_dataset": self.source_dataset,
            "source_version": self.source_version,
            "semantics_version": self.semantics_version,
            "schema_version": self.schema_version,
            "code_version": self.code_version,
        }
        if self.extra:
            payload.update(self.extra)
        return payload
