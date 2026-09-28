"""Logical warehouse entities. Phase 1 types; Phase 2 Game identity; Phase 3 link fields.

Not used by Confirm & Run, compile_draft, or execute.
Do not invent a generic price.

LAST_TRADE_PRINT is not TRADABLE_YES_BID.
Box score is not Kalshi settlement.
PBP identity is not PIT alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from roller.warehouse.schema import (
    BASIS_LAST_TRADE_PRINT,
    BASIS_TRADABLE_YES_BID,
    e4_domain_ok,
)

ENTITY_MODEL_VERSION = "1.0.0"

BASIS_ORDERBOOK_SNAPSHOT = "ORDERBOOK_SNAPSHOT"

_TRADABLE_OHLC = (
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
)
_LAST_TRADE_OHLC = (
    "last_open_e4",
    "last_high_e4",
    "last_low_e4",
    "last_close_e4",
)
_ORDERBOOK_TOB = ("best_yes_bid_e4", "best_no_bid_e4")


class ObservationBasis(str, Enum):
    TRADABLE_YES_BID = BASIS_TRADABLE_YES_BID
    LAST_TRADE_PRINT = BASIS_LAST_TRADE_PRINT
    ORDERBOOK_SNAPSHOT = BASIS_ORDERBOOK_SNAPSHOT


class SettlementResult(str, Enum):
    YES = "YES"
    NO = "NO"
    MISSING = "MISSING"
    INVALID = "INVALID"


class LinkStatus(str, Enum):
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"


def _require_e4(name: str, value: int | None) -> None:
    if value is None:
        return
    if not e4_domain_ok(value):
        raise ValueError(f"{name} is outside Kalshi e4 domain 0..10000")


def _nonempty(value: str, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


@dataclass(frozen=True)
class Game:
    """One contest. Box score is not Kalshi settlement.

    `internal_game_id` is ROLLER's canonical join key.
    `source_game_id` is provenance only and is never a Kalshi ticker.
    `event_ticker` is also provenance, not Game identity.
    """

    internal_game_id: str
    sport: str
    season: str
    league: str
    game_date: str
    home_team_id: str = ""
    away_team_id: str = ""
    source_game_id: str = ""
    warehouse_game_id: str = ""
    event_ticker: str = ""
    scheduled_at: str = ""
    source_system: str = ""
    identity_rule_version: str = ""
    final_home_score: int | None = None
    final_away_score: int | None = None

    def __post_init__(self) -> None:
        _nonempty(self.internal_game_id, "internal_game_id")
        _nonempty(self.sport, "sport")
        _nonempty(self.season, "season")
        _nonempty(self.league, "league")
        _nonempty(self.game_date, "game_date")


@dataclass(frozen=True)
class Market:
    """One Kalshi (or other venue) contract. Not an observation and not a settlement.

    `ticker` is the stable market key. `source_market_id` is provenance only.
    `internal_game_id` is a join stamp, not a second market identity.
    """

    ticker: str
    event_ticker: str = ""
    internal_game_id: str = ""
    venue: str = "kalshi"
    team_side: str = ""
    event_id: str = ""
    market_id: str = ""
    source_market_id: str = ""
    source: str = ""
    market_type: str = ""
    title: str = ""
    sport: str = ""
    league: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.ticker, "ticker")
        if self.market_id and str(self.market_id).strip() != self.ticker:
            raise ValueError("market_id must equal ticker")


@dataclass(frozen=True)
class MarketObservation:
    """One stored observation minute or snapshot.

    There is no generic `price`. The basis selects which fields are legal.
    Absent minutes are not represented as rows.
    """

    ticker: str
    basis: ObservationBasis
    available_at: str
    internal_game_id: str = ""
    event_timestamp: str = ""
    ingested_at: str = ""
    volume: int | None = None
    print_count: int | None = None
    yes_bid_open: int | None = None
    yes_bid_high: int | None = None
    yes_bid_low: int | None = None
    yes_bid_close: int | None = None
    yes_ask_open: int | None = None
    yes_ask_high: int | None = None
    yes_ask_low: int | None = None
    yes_ask_close: int | None = None
    last_open_e4: int | None = None
    last_high_e4: int | None = None
    last_low_e4: int | None = None
    last_close_e4: int | None = None
    best_yes_bid_e4: int | None = None
    best_no_bid_e4: int | None = None

    def __post_init__(self) -> None:
        _nonempty(self.ticker, "ticker")
        _nonempty(self.available_at, "available_at")
        if not isinstance(self.basis, ObservationBasis):
            raise ValueError("basis must be ObservationBasis")
        for name in (*_TRADABLE_OHLC, *_LAST_TRADE_OHLC, *_ORDERBOOK_TOB):
            _require_e4(name, getattr(self, name))
        tradable = tuple(getattr(self, name) for name in _TRADABLE_OHLC)
        last_trade = tuple(getattr(self, name) for name in _LAST_TRADE_OHLC)
        book = tuple(getattr(self, name) for name in _ORDERBOOK_TOB)
        if self.basis is ObservationBasis.TRADABLE_YES_BID:
            if self.yes_bid_close is None:
                raise ValueError("TRADABLE_YES_BID requires yes_bid_close")
            if any(v is not None for v in last_trade):
                raise ValueError("TRADABLE_YES_BID must not carry last_*_e4")
            if any(v is not None for v in book):
                raise ValueError("TRADABLE_YES_BID must not carry orderbook TOB fields")
            if self.print_count is not None:
                raise ValueError("TRADABLE_YES_BID must not carry print_count")
        elif self.basis is ObservationBasis.LAST_TRADE_PRINT:
            if self.last_close_e4 is None:
                raise ValueError("LAST_TRADE_PRINT requires last_close_e4")
            if any(v is not None for v in tradable):
                raise ValueError("LAST_TRADE_PRINT must not carry yes_bid/yes_ask")
            if any(v is not None for v in book):
                raise ValueError("LAST_TRADE_PRINT must not carry orderbook TOB fields")
        elif self.basis is ObservationBasis.ORDERBOOK_SNAPSHOT:
            if self.best_yes_bid_e4 is None and self.best_no_bid_e4 is None:
                raise ValueError("ORDERBOOK_SNAPSHOT requires best_yes_bid_e4 or best_no_bid_e4")
            if any(v is not None for v in tradable):
                raise ValueError("ORDERBOOK_SNAPSHOT must not carry candle yes_bid OHLC")
            if any(v is not None for v in last_trade):
                raise ValueError("ORDERBOOK_SNAPSHOT must not carry last_*_e4")
        else:
            raise ValueError(f"unsupported observation basis {self.basis}")


@dataclass(frozen=True)
class PBPEvent:
    """One source play-by-play event. Identity linkage is not PIT alignment."""

    internal_game_id: str
    event_timestamp: str
    source_game_id: str = ""
    event_number: str = ""
    available_at: str = ""
    period: str = ""
    clock: str = ""
    inning: str = ""
    half: str = ""
    event_type: str = ""
    home_score: int | None = None
    away_score: int | None = None

    def __post_init__(self) -> None:
        _nonempty(self.internal_game_id, "internal_game_id")
        _nonempty(self.event_timestamp, "event_timestamp")


@dataclass(frozen=True)
class Settlement:
    """Official Kalshi result only. Missing is not NO. Never from PBP or box score."""

    ticker: str
    result: SettlementResult
    settlement_value_e4: int | None = None
    result_available_at: str = ""
    settlement_time: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.ticker, "ticker")
        if not isinstance(self.result, SettlementResult):
            raise ValueError("result must be SettlementResult")
        _require_e4("settlement_value_e4", self.settlement_value_e4)
        if self.result is SettlementResult.MISSING and self.settlement_value_e4 is not None:
            raise ValueError("MISSING settlement must not invent settlement_value_e4")
        if self.result is SettlementResult.NO and self.settlement_value_e4 is None:
            # NO may omit value; do not coerce missing rows into NO.
            pass


@dataclass(frozen=True)
class GameMarketLink:
    """Game↔market association. Phase 3 persists NBA rows. No guessing."""

    status: LinkStatus
    internal_game_id: str = ""
    ticker: str = ""
    event_ticker: str = ""
    reason: str = ""
    link_method: str = ""
    source_evidence: str = ""
    identity_rule_version: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, LinkStatus):
            raise ValueError("status must be LinkStatus")
        if self.status is LinkStatus.LINKED:
            _nonempty(self.internal_game_id, "internal_game_id")
            _nonempty(self.ticker, "ticker")
        if self.status is LinkStatus.UNLINKED and not (self.internal_game_id or self.ticker):
            raise ValueError("UNLINKED requires a game or a ticker")


def kalshi_result_to_settlement(raw: object) -> SettlementResult:
    """Map a warehouse `result` cell. Blank stays MISSING. scalar stays INVALID."""
    text = str(raw or "").strip().lower()
    if text == "":
        return SettlementResult.MISSING
    if text == "yes":
        return SettlementResult.YES
    if text == "no":
        return SettlementResult.NO
    return SettlementResult.INVALID
