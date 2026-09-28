"""Typed research-question AST. Ordinal is a semantic enum, not a bare int."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any


class TouchOrdinal(str, Enum):
    FIRST_TOUCH = "FIRST_TOUCH"
    SECOND_TOUCH = "SECOND_TOUCH"
    THIRD_TOUCH = "THIRD_TOUCH"
    FOURTH_TOUCH = "FOURTH_TOUCH"
    NTH_TOUCH = "NTH_TOUCH"


class EntryOp(str, Enum):
    FIRST_TOUCH = "FIRST_TOUCH"
    SECOND_TOUCH = "SECOND_TOUCH"
    THIRD_TOUCH = "THIRD_TOUCH"
    FOURTH_TOUCH = "FOURTH_TOUCH"
    NTH_TOUCH = "NTH_TOUCH"
    CROSS = "CROSS"
    BREAK = "BREAK"
    REVERSION = "REVERSION"
    BOUNCE = "BOUNCE"
    RECOVERY = "RECOVERY"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    MAXIMUM_TOUCH = "MAXIMUM_TOUCH"
    MINIMUM_TOUCH = "MINIMUM_TOUCH"


class ExitOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"


class PathOp(str, Enum):
    REACH = "REACH"
    DROP_TO = "DROP_TO"
    RISE_TO = "RISE_TO"
    RECOVER = "RECOVER"
    BOUNCE = "BOUNCE"
    REVERT = "REVERT"
    MAXIMUM_MOVE = "MAXIMUM_MOVE"
    MINIMUM_MOVE = "MINIMUM_MOVE"
    NEVER_REACH = "NEVER_REACH"
    HORIZON_WIN = "HORIZON_WIN"
    HORIZON_LOSS = "HORIZON_LOSS"


# Tradable yes_bid_close at a time horizon. Not Kalshi settlement.
HORIZON_WIN_E4 = 5000


class TerminalOutcome(str, Enum):
    YES = "YES"
    NO = "NO"
    BOTH = "BOTH"


class ResearchStatus(str, Enum):
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    DATA_REQUIRED = "DATA_REQUIRED"
    OPERATION_REQUIRED = "OPERATION_REQUIRED"


class ExecutionPath(str, Enum):
    FROZEN_REFERENCE = "frozen_reference"
    GENERIC_QUERY = "generic_query"
    NONE = "none"


class PriceField(str, Enum):
    YES_BID_CLOSE = "yes_bid_close"
    LAST_TRADE_CLOSE = "last_close_e4"


# An observation basis pairs a price field with what that price means.
# TRADABLE_YES_BID is a quote you could have hit. LAST_TRADE_PRINT is a
# transaction that already happened and is not executable.
BASIS_TRADABLE = "TRADABLE_YES_BID"
BASIS_LAST_TRADE = "LAST_TRADE_PRINT"

PRICE_RULE = "tradable_yes_bid_close_cross"
PRICE_RULE_LAST_TRADE = "last_trade_close_cross"
OBSERVABILITY = "CANDLE-LEVEL OBSERVED"
OBSERVABILITY_LAST_TRADE = "LAST-TRADE PRINT OBSERVED — no tradable quote"
EVENT_DEFINITION = "TRADABLE_CLOSE_CROSS"
EVENT_DEFINITION_BAND = "TRADABLE_BAND_ENTER"
EVENT_DEFINITION_BREAK = "TRADABLE_CLOSE_BREAK"
EVENT_DEFINITION_REVERSAL = "TRADABLE_CLOSE_REVERSAL"
EVENT_DEFINITION_BOUNCE = "TRADABLE_CLOSE_BOUNCE"
EVENT_DEFINITION_RECOVERY = "TRADABLE_CLOSE_RECOVERY"
EVENT_DEFINITION_STATE = "TRADABLE_CLOSE_STATE"
EVENT_DEFINITION_EXTREMUM = "TRADABLE_CLOSE_EXTREMUM"
OPERATION_SEMANTICS_VERSION = "1.1.0"

# Last-trade mirrors of the tradable definitions. Same threshold geometry,
# different observability: the crossing is a print, not an executable quote.
EVENT_DEFINITION_LAST_TRADE = "LAST_TRADE_CLOSE_CROSS"
EVENT_DEFINITION_LAST_TRADE_BAND = "LAST_TRADE_BAND_ENTER"
EVENT_DEFINITION_LAST_TRADE_BREAK = "LAST_TRADE_CLOSE_BREAK"
EVENT_DEFINITION_LAST_TRADE_REVERSAL = "LAST_TRADE_CLOSE_REVERSAL"
EVENT_DEFINITION_LAST_TRADE_BOUNCE = "LAST_TRADE_CLOSE_BOUNCE"
EVENT_DEFINITION_LAST_TRADE_RECOVERY = "LAST_TRADE_CLOSE_RECOVERY"
EVENT_DEFINITION_LAST_TRADE_STATE = "LAST_TRADE_CLOSE_STATE"
EVENT_DEFINITION_LAST_TRADE_EXTREMUM = "LAST_TRADE_CLOSE_EXTREMUM"

TRADABLE_EVENT_DEFINITIONS = frozenset(
    {
        EVENT_DEFINITION,
        EVENT_DEFINITION_BAND,
        EVENT_DEFINITION_BREAK,
        EVENT_DEFINITION_REVERSAL,
        EVENT_DEFINITION_BOUNCE,
        EVENT_DEFINITION_RECOVERY,
        EVENT_DEFINITION_STATE,
        EVENT_DEFINITION_EXTREMUM,
    }
)

LAST_TRADE_EVENT_DEFINITIONS = frozenset(
    {
        EVENT_DEFINITION_LAST_TRADE,
        EVENT_DEFINITION_LAST_TRADE_BAND,
        EVENT_DEFINITION_LAST_TRADE_BREAK,
        EVENT_DEFINITION_LAST_TRADE_REVERSAL,
        EVENT_DEFINITION_LAST_TRADE_BOUNCE,
        EVENT_DEFINITION_LAST_TRADE_RECOVERY,
        EVENT_DEFINITION_LAST_TRADE_STATE,
        EVENT_DEFINITION_LAST_TRADE_EXTREMUM,
    }
)

TRADABLE_TO_LAST_TRADE_DEFINITION = {
    EVENT_DEFINITION: EVENT_DEFINITION_LAST_TRADE,
    EVENT_DEFINITION_BAND: EVENT_DEFINITION_LAST_TRADE_BAND,
    EVENT_DEFINITION_BREAK: EVENT_DEFINITION_LAST_TRADE_BREAK,
    EVENT_DEFINITION_REVERSAL: EVENT_DEFINITION_LAST_TRADE_REVERSAL,
    EVENT_DEFINITION_BOUNCE: EVENT_DEFINITION_LAST_TRADE_BOUNCE,
    EVENT_DEFINITION_RECOVERY: EVENT_DEFINITION_LAST_TRADE_RECOVERY,
    EVENT_DEFINITION_STATE: EVENT_DEFINITION_LAST_TRADE_STATE,
    EVENT_DEFINITION_EXTREMUM: EVENT_DEFINITION_LAST_TRADE_EXTREMUM,
}

APPROVED_EVENT_DEFINITIONS = TRADABLE_EVENT_DEFINITIONS | LAST_TRADE_EVENT_DEFINITIONS

CENTS_TO_E4 = 100

UNSUPPORTED_ENTRY = frozenset()
IMPLEMENTED_ENTRY_OPS = frozenset(
    {
        "cross",
        "break",
        "reversion",
        "bounce",
        "recovery",
        "above",
        "below",
        "maximum_touch",
        "minimum_touch",
    }
)
UNSUPPORTED_PATH = frozenset()
IMPLEMENTED_PATH_OPS = frozenset(
    {
        "reach",
        "drop_to",
        "rise_to",
        "recover",
        "bounce",
        "revert",
        "maximum_move",
        "minimum_move",
        "never_reach",
    }
)
TOUCH_FAMILIES = {
    "first_touch": TouchOrdinal.FIRST_TOUCH,
    "second_touch": TouchOrdinal.SECOND_TOUCH,
    "third_touch": TouchOrdinal.THIRD_TOUCH,
    "fourth_touch": TouchOrdinal.FOURTH_TOUCH,
    "nth_touch": TouchOrdinal.NTH_TOUCH,
}

ENTRY_OP_FAMILIES = {
    "cross": EntryOp.CROSS,
    "break": EntryOp.BREAK,
    "reversion": EntryOp.REVERSION,
    "bounce": EntryOp.BOUNCE,
    "recovery": EntryOp.RECOVERY,
    "above": EntryOp.ABOVE,
    "below": EntryOp.BELOW,
    "maximum_touch": EntryOp.MAXIMUM_TOUCH,
    "minimum_touch": EntryOp.MINIMUM_TOUCH,
}

ENTRY_OP_EVENT_DEFINITION = {
    EntryOp.CROSS: EVENT_DEFINITION,
    EntryOp.BREAK: EVENT_DEFINITION_BREAK,
    EntryOp.REVERSION: EVENT_DEFINITION_REVERSAL,
    EntryOp.BOUNCE: EVENT_DEFINITION_BOUNCE,
    EntryOp.RECOVERY: EVENT_DEFINITION_RECOVERY,
    EntryOp.ABOVE: EVENT_DEFINITION_STATE,
    EntryOp.BELOW: EVENT_DEFINITION_STATE,
    EntryOp.MAXIMUM_TOUCH: EVENT_DEFINITION_EXTREMUM,
    EntryOp.MINIMUM_TOUCH: EVENT_DEFINITION_EXTREMUM,
}


def cents_to_e4(cents: int) -> int:
    return int(cents) * CENTS_TO_E4


def max_entry_e4_from_raw(raw: dict[str, Any]) -> int | None:
    """Accept-through ceiling. Not a From–To band and not an assumed fill at P."""
    if raw.get("max_entry_e4") is not None:
        return int(raw["max_entry_e4"])
    cents = raw.get("maxEntryCents")
    if cents is None:
        cents = raw.get("max_entry_cents")
    if cents is None or cents == "":
        return None
    return cents_to_e4(int(cents))


def ordinal_n(ordinal: TouchOrdinal, nth: int | None = None) -> int:
    if ordinal is TouchOrdinal.FIRST_TOUCH:
        return 1
    if ordinal is TouchOrdinal.SECOND_TOUCH:
        return 2
    if ordinal is TouchOrdinal.THIRD_TOUCH:
        return 3
    if ordinal is TouchOrdinal.FOURTH_TOUCH:
        return 4
    if nth is None or int(nth) < 1:
        raise ValueError("NTH_TOUCH requires nth >= 1")
    return int(nth)


@dataclass(frozen=True)
class ClockWindow:
    remaining_from_s: int
    remaining_to_s: int

    def contains(self, remaining_s: float | None) -> bool:
        if remaining_s is None:
            return False
        lo = min(self.remaining_from_s, self.remaining_to_s)
        hi = max(self.remaining_from_s, self.remaining_to_s)
        return lo <= remaining_s <= hi

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ClockWindow | None:
        if not raw:
            return None
        return cls(int(raw["remaining_from_s"]), int(raw["remaining_to_s"]))


@dataclass(frozen=True)
class PeriodWindow:
    """One period/clock filter. Multiple windows on an entry are OR, not AND."""

    period: str | None = None
    clock: ClockWindow | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "clock": self.clock.to_dict() if self.clock else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PeriodWindow:
        raw = raw or {}
        clock_raw = raw.get("clock")
        clock = ClockWindow.from_dict(clock_raw) if isinstance(clock_raw, dict) else None
        return cls(period=raw.get("period"), clock=clock)


@dataclass(frozen=True)
class EntryCondition:
    id: str
    ordinal: TouchOrdinal
    price_e4: int
    period: str | None = None
    clock: ClockWindow | None = None
    period_windows: tuple[PeriodWindow, ...] = ()
    nth: int | None = None
    event_definition: str = EVENT_DEFINITION
    price_field: str = PriceField.YES_BID_CLOSE.value
    price_to_e4: int | None = None
    max_entry_e4: int | None = None
    operation: EntryOp | None = None
    direction: str | None = None

    def resolved_operation(self) -> EntryOp:
        if self.operation is not None:
            return self.operation
        return EntryOp(self.ordinal.value)

    def is_touch_op(self) -> bool:
        return self.resolved_operation().value in {o.value for o in TouchOrdinal}

    def touch_index(self) -> int:
        return ordinal_n(self.ordinal, self.nth)

    def period_filters(self) -> tuple[PeriodWindow, ...]:
        """Normalized period/clock windows. Empty means no filter."""
        if self.period_windows:
            return self.period_windows
        if self.period or self.clock:
            return (PeriodWindow(period=self.period, clock=self.clock),)
        return ()

    def has_period_or_clock(self) -> bool:
        return bool(self.period_filters())

    def names_period(self, name: str) -> bool:
        return any(w.period == name for w in self.period_filters())

    def basis(self) -> str:
        if self.price_field == PriceField.LAST_TRADE_CLOSE.value:
            return BASIS_LAST_TRADE
        return BASIS_TRADABLE

    def on_last_trade_basis(self) -> EntryCondition:
        """Same threshold geometry, restated as a last-trade print event."""
        return replace(
            self,
            price_field=PriceField.LAST_TRADE_CLOSE.value,
            event_definition=TRADABLE_TO_LAST_TRADE_DEFINITION.get(
                self.event_definition, EVENT_DEFINITION_LAST_TRADE
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "ordinal": self.ordinal.value,
            "price_e4": self.price_e4,
            "period": self.period,
            "clock": self.clock.to_dict() if self.clock else None,
            "nth": self.nth,
            "event_definition": self.event_definition,
            "price_field": self.price_field,
        }
        if self.price_to_e4 is not None:
            payload["price_to_e4"] = self.price_to_e4
        if self.max_entry_e4 is not None:
            payload["max_entry_e4"] = self.max_entry_e4
        op = self.operation
        if op is not None and op.value != self.ordinal.value:
            payload["operation"] = op.value
        if self.direction:
            payload["direction"] = self.direction
        if self.period_windows:
            payload["period_windows"] = [w.to_dict() for w in self.period_windows]
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EntryCondition:
        op_raw = raw.get("operation")
        windows = tuple(
            PeriodWindow.from_dict(w)
            for w in (raw.get("period_windows") or raw.get("periodWindows") or [])
            if isinstance(w, dict)
        )
        return cls(
            id=str(raw["id"]),
            ordinal=TouchOrdinal(raw["ordinal"]),
            price_e4=int(raw["price_e4"]),
            period=raw.get("period"),
            clock=ClockWindow.from_dict(raw.get("clock")),
            period_windows=windows,
            nth=raw.get("nth"),
            event_definition=raw.get("event_definition") or EVENT_DEFINITION,
            price_field=raw.get("price_field") or PriceField.YES_BID_CLOSE.value,
            price_to_e4=int(raw["price_to_e4"]) if raw.get("price_to_e4") is not None else None,
            max_entry_e4=max_entry_e4_from_raw(raw),
            operation=EntryOp(op_raw) if op_raw else None,
            direction=raw.get("direction"),
        )


@dataclass(frozen=True)
class PathCondition:
    id: str
    op: PathOp
    price_e4: int
    sequential: bool = False
    horizon_kind: str | None = None
    horizon_minutes: int | None = None
    outcome: ExitOutcome | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "op": self.op.value,
            "price_e4": self.price_e4,
            "sequential": self.sequential,
        }
        if self.horizon_kind is not None:
            payload["horizon_kind"] = self.horizon_kind
        if self.horizon_minutes is not None:
            payload["horizon_minutes"] = self.horizon_minutes
        if self.outcome is not None:
            payload["outcome"] = self.outcome.value
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PathCondition:
        oc = raw.get("outcome")
        return cls(
            id=str(raw["id"]),
            op=PathOp(raw["op"]),
            price_e4=int(raw["price_e4"]),
            sequential=bool(raw.get("sequential")),
            horizon_kind=raw.get("horizon_kind"),
            horizon_minutes=int(raw["horizon_minutes"]) if raw.get("horizon_minutes") is not None else None,
            outcome=ExitOutcome(oc) if oc else None,
        )


MARKET_BASIS = {"kalshi": BASIS_TRADABLE, "polymarket": BASIS_LAST_TRADE}


@dataclass(frozen=True)
class Universe:
    sports: tuple[str, ...]
    leagues: tuple[str, ...]
    seasons: tuple[str, ...]
    markets: tuple[str, ...]
    market_data: tuple[str, ...]
    game_data: tuple[str, ...] = ()
    date_from: str | None = None
    date_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sports": list(self.sports),
            "leagues": list(self.leagues),
            "seasons": list(self.seasons),
            "markets": list(self.markets),
            "market_data": list(self.market_data),
            "game_data": list(self.game_data),
            "date_from": self.date_from,
            "date_to": self.date_to,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Universe:
        return cls(
            sports=tuple(raw.get("sports") or ()),
            leagues=tuple(raw.get("leagues") or ()),
            seasons=tuple(raw.get("seasons") or ()),
            markets=tuple(raw.get("markets") or ()),
            market_data=tuple(raw.get("market_data") or ()),
            game_data=tuple(raw.get("game_data") or ()),
            date_from=raw.get("date_from"),
            date_to=raw.get("date_to"),
        )


def universe_basis(universe: Universe) -> str | None:
    """None when the selected venues have no defined joint basis.

    Kalshi basketball stays TRADABLE_YES_BID unless last_trade is selected.
    MLB Kalshi defaults to LAST_TRADE_PRINT. Genuine candles stay selectable.
    """
    from roller.research_query.market_path import universe_observation_basis

    return universe_observation_basis(universe)


@dataclass(frozen=True)
class ResearchQuestion:
    universe: Universe
    entry_conditions: tuple[EntryCondition, ...]
    path_conditions: tuple[PathCondition, ...]
    terminal: TerminalOutcome
    requested_dimensions: tuple[str, ...] = ()
    accept_limitations: bool = False
    win_hold: bool = False
    loss_hold: bool = False

    def tagged_exits(self) -> bool:
        if self.win_hold or self.loss_hold:
            return True
        return any(p.outcome is not None for p in self.path_conditions)

    def basis(self) -> str | None:
        """Compiled entry conditions win; otherwise infer from the venue."""
        bases = {e.basis() for e in self.entry_conditions}
        if len(bases) == 1:
            return next(iter(bases))
        if bases:
            return None
        return universe_basis(self.universe)

    def on_last_trade_basis(self) -> ResearchQuestion:
        return replace(
            self,
            entry_conditions=tuple(e.on_last_trade_basis() for e in self.entry_conditions),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "universe": self.universe.to_dict(),
            "entry_conditions": [e.to_dict() for e in self.entry_conditions],
            "path_conditions": [p.to_dict() for p in self.path_conditions],
            "terminal": self.terminal.value,
            "requested_dimensions": list(self.requested_dimensions),
            "accept_limitations": self.accept_limitations,
        }
        if self.win_hold:
            payload["win_hold"] = True
        if self.loss_hold:
            payload["loss_hold"] = True
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ResearchQuestion:
        return cls(
            universe=Universe.from_dict(raw.get("universe") or {}),
            entry_conditions=tuple(
                EntryCondition.from_dict(e) for e in (raw.get("entry_conditions") or [])
            ),
            path_conditions=tuple(
                PathCondition.from_dict(p) for p in (raw.get("path_conditions") or [])
            ),
            terminal=TerminalOutcome(raw.get("terminal") or "BOTH"),
            requested_dimensions=tuple(raw.get("requested_dimensions") or ()),
            accept_limitations=bool(raw.get("accept_limitations")),
            win_hold=bool(raw.get("win_hold")),
            loss_hold=bool(raw.get("loss_hold")),
        )


@dataclass
class FunnelStep:
    condition_id: str
    label: str
    qualifying: int
    population_before: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompileResult:
    status: ResearchStatus
    execution_path: ExecutionPath
    reference_match: str | None
    question: ResearchQuestion
    reasons: list[str] = field(default_factory=list)
    available: list[str] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)
    omitted_dimensions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "execution_path": self.execution_path.value,
            "reference_match": self.reference_match,
            "question": self.question.to_dict(),
            "reasons": list(self.reasons),
            "available": list(self.available),
            "unavailable": list(self.unavailable),
            "omitted_dimensions": list(self.omitted_dimensions),
            "warnings": list(self.warnings),
            "observation_basis": self.question.basis(),
        }
