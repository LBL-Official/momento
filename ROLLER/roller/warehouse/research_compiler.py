"""Phase 11 isolated NBA research compiler.

ResearchQuestion → normalize → validate → catalog.resolve → ResearchPlan.

Does not call Confirm & Run compiler.py or execute.py. Does not run a backtest.
Does not emit ZERO_RESULTS. Does not invent L2 or remap candles to ticks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    get_catalog,
    question_capabilities,
)
from roller.warehouse.desk import (
    DESK_SPORTS,
    desk_sport,
    mlb_basketball_period_or_clock,
    observation_basis_for,
    tennis_foreign_period_or_clock,
)

COMPILER_VERSION = "1.0.0"
PHASE11_SPORT = "NBA"
DEFAULT_SEASON = "2025-2026"


class TerminalBehavior(str, Enum):
    HOLD_TO_SETTLEMENT = "HOLD_TO_SETTLEMENT"
    NO_TERMINAL_RESULT = "NO_TERMINAL_RESULT"


class PlanExitOp(str, Enum):
    HOLD = "HOLD"
    REACH = "REACH"
    DROP = "DROP"
    RISE = "RISE"
    RECOVER = "RECOVER"
    BOUNCE = "BOUNCE"
    REVERT = "REVERT"
    MAXIMUM_MOVE = "MAXIMUM_MOVE"
    MINIMUM_MOVE = "MINIMUM_MOVE"
    NEVER_REACH = "NEVER_REACH"
    CLOCK = "CLOCK"


_PATH_TO_EXIT = {
    PathOp.REACH: PlanExitOp.REACH,
    PathOp.DROP_TO: PlanExitOp.DROP,
    PathOp.RISE_TO: PlanExitOp.RISE,
    PathOp.RECOVER: PlanExitOp.RECOVER,
    PathOp.BOUNCE: PlanExitOp.BOUNCE,
    PathOp.REVERT: PlanExitOp.REVERT,
    PathOp.MAXIMUM_MOVE: PlanExitOp.MAXIMUM_MOVE,
    PathOp.MINIMUM_MOVE: PlanExitOp.MINIMUM_MOVE,
    PathOp.NEVER_REACH: PlanExitOp.NEVER_REACH,
}

_TOUCH_OPS = {op.value for op in TouchOrdinal}


def _text(value: object) -> str:
    return str(value or "").strip()


def _token(value: object) -> str:
    return _text(value).upper().replace(" ", "_").replace("↔", "_").replace("-", "_")


def _normalize_season(value: str) -> str:
    return _text(value).replace("_", "-")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class CompiledEntry:
    id: str
    op: str
    price_e4: int
    price_to_e4: int | None = None
    max_entry_e4: int | None = None
    ordinal: str | None = None
    nth: int | None = None
    period: str | None = None
    clock: dict[str, int] | None = None
    period_windows: tuple[dict[str, Any], ...] = ()
    conjunction: str | None = None
    direction: str | None = None
    source_vocabulary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "op": self.op,
            "price_e4": self.price_e4,
        }
        if self.price_to_e4 is not None:
            payload["price_to_e4"] = self.price_to_e4
        if self.max_entry_e4 is not None:
            payload["max_entry_e4"] = self.max_entry_e4
        if self.ordinal is not None:
            payload["ordinal"] = self.ordinal
        if self.nth is not None:
            payload["nth"] = self.nth
        if self.period is not None:
            payload["period"] = self.period
        if self.clock is not None:
            payload["clock"] = dict(self.clock)
        if self.period_windows:
            payload["period_windows"] = [dict(w) for w in self.period_windows]
        if self.conjunction is not None:
            payload["conjunction"] = self.conjunction
        if self.direction is not None:
            payload["direction"] = self.direction
        if self.source_vocabulary is not None:
            payload["source_vocabulary"] = self.source_vocabulary
        return payload


@dataclass(frozen=True)
class CompiledExit:
    id: str
    outcome: str
    op: str
    price_e4: int | None = None
    clock: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "outcome": self.outcome,
            "op": self.op,
        }
        if self.price_e4 is not None:
            payload["price_e4"] = self.price_e4
        if self.clock is not None:
            payload["clock"] = dict(self.clock)
        return payload


@dataclass(frozen=True)
class ResearchPlan:
    status: ResearchStatus
    universe: dict[str, Any]
    observation_basis: str
    resolution: str
    pit_requirement: str
    entries: tuple[CompiledEntry, ...]
    exits: tuple[CompiledExit, ...]
    terminal: TerminalBehavior
    required_capabilities: tuple[str, ...]
    satisfied_capabilities: tuple[str, ...]
    missing_data: tuple[str, ...]
    missing_operations: tuple[str, ...]
    context_requirements: tuple[str, ...]
    compiler_version: str = COMPILER_VERSION
    warehouse_version: str = ""
    catalog_version: str = CATALOG_VERSION
    plan_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status.value,
            "universe": dict(self.universe),
            "observation_basis": self.observation_basis,
            "resolution": self.resolution,
            "pit_requirement": self.pit_requirement,
            "entries": [e.to_dict() for e in self.entries],
            "exits": [x.to_dict() for x in self.exits],
            "terminal": self.terminal.value,
            "required_capabilities": list(self.required_capabilities),
            "satisfied_capabilities": list(self.satisfied_capabilities),
            "missing_data": list(self.missing_data),
            "missing_operations": list(self.missing_operations),
            "context_requirements": list(self.context_requirements),
            "compiler_version": self.compiler_version,
            "warehouse_version": self.warehouse_version,
            "catalog_version": self.catalog_version,
        }
        return payload

    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()


def _normalize_universe(universe: Universe) -> Universe:
    return Universe(
        sports=tuple(_text(s).upper() for s in universe.sports),
        leagues=tuple(_text(s).upper() for s in universe.leagues),
        seasons=tuple(_normalize_season(s) for s in universe.seasons),
        markets=tuple(_text(m).lower() for m in universe.markets),
        market_data=tuple(_text(m).lower() for m in universe.market_data),
        game_data=tuple(_text(g).lower() for g in universe.game_data),
        date_from=_text(universe.date_from)[:10] or None,
        date_to=_text(universe.date_to)[:10] or None,
    )


def _entry_op(entry: EntryCondition) -> tuple[EntryOp, str | None]:
    if entry.operation is not None:
        return entry.operation, None
    return EntryOp(entry.ordinal.value), "TOUCH"


def _compile_entry(entry: EntryCondition, *, conjunction: str | None) -> CompiledEntry:
    op, source = _entry_op(entry)
    clock = entry.clock.to_dict() if entry.clock is not None else None
    windows = tuple(w.to_dict() for w in entry.period_windows)
    return CompiledEntry(
        id=entry.id,
        op=op.value,
        price_e4=int(entry.price_e4),
        price_to_e4=int(entry.price_to_e4) if entry.price_to_e4 is not None else None,
        max_entry_e4=int(entry.max_entry_e4) if entry.max_entry_e4 is not None else None,
        ordinal=entry.ordinal.value if op.value in _TOUCH_OPS or source == "TOUCH" else None,
        nth=entry.nth,
        period=entry.period,
        clock=clock,
        period_windows=windows,
        conjunction=conjunction,
        direction=entry.direction,
        source_vocabulary=source,
    )


def _compile_exits(question: ResearchQuestion) -> tuple[CompiledExit, ...]:
    exits: list[CompiledExit] = []
    if question.win_hold:
        exits.append(CompiledExit(id="win_hold", outcome=ExitOutcome.WIN.value, op=PlanExitOp.HOLD.value))
    if question.loss_hold:
        exits.append(CompiledExit(id="loss_hold", outcome=ExitOutcome.LOSS.value, op=PlanExitOp.HOLD.value))
    for path in question.path_conditions:
        outcome = path.outcome.value if path.outcome is not None else ExitOutcome.WIN.value
        if _token(path.horizon_kind) == "CLOCK":
            exits.append(
                CompiledExit(
                    id=path.id,
                    outcome=outcome,
                    op=PlanExitOp.CLOCK.value,
                    price_e4=int(path.price_e4) if path.price_e4 else None,
                    clock={
                        "horizon_kind": "CLOCK",
                        "horizon_minutes": path.horizon_minutes,
                    },
                )
            )
            continue
        op = _PATH_TO_EXIT.get(path.op)
        if op is None:
            continue
        exits.append(
            CompiledExit(
                id=path.id,
                outcome=outcome,
                op=op.value,
                price_e4=int(path.price_e4),
            )
        )
    return tuple(exits)


def _terminal(question: ResearchQuestion) -> TerminalBehavior:
    dims = {_token(d) for d in question.requested_dimensions}
    if TerminalBehavior.NO_TERMINAL_RESULT.value in dims:
        return TerminalBehavior.NO_TERMINAL_RESULT
    return TerminalBehavior.HOLD_TO_SETTLEMENT


def _universe_errors(universe: Universe) -> tuple[str, ...]:
    missing: list[str] = []
    sport = desk_sport(universe)
    if sport is None or sport not in DESK_SPORTS:
        missing.append("UNIVERSE")
    if universe.seasons and DEFAULT_SEASON not in universe.seasons:
        missing.append("UNIVERSE")
    if not universe.sports:
        missing.append("UNIVERSE")
    if universe.date_from and universe.date_to and universe.date_from > universe.date_to:
        missing.append("DATE_RANGE")
    # Preserve insertion order without duplicates.
    return tuple(dict.fromkeys(missing))


def _context_requirements(question: ResearchQuestion) -> tuple[str, ...]:
    reqs = ["games", "markets", "game_market_links", "settlements"]
    md = {_token(x) for x in question.universe.market_data}
    if md & {"LAST_TRADE", "LAST_TRADE_PRINT"}:
        reqs.append("last_trade_print_observations")
    elif not (md & {"TICK", "TICKS", "L2", "HISTORICAL_L2", "ORDERBOOK", "TRADE_TAPE"}):
        reqs.append("tradable_yes_bid_observations")
    if any(e.has_period_or_clock() for e in question.entry_conditions) or any(
        _token(x) == "PBP" for x in (*question.universe.game_data, *question.requested_dimensions)
    ):
        reqs.append("pbp_identity")
    return tuple(reqs)


def compile_research(
    question: ResearchQuestion,
    cfg: RollerConfig | None = None,
) -> ResearchPlan:
    """Compile a plan. Does not scan rows, compute WIN/LOSS, or call execute."""
    cfg = cfg or RollerConfig()
    normalized = ResearchQuestion(
        universe=_normalize_universe(question.universe),
        entry_conditions=question.entry_conditions,
        path_conditions=question.path_conditions,
        terminal=question.terminal,
        requested_dimensions=question.requested_dimensions,
        accept_limitations=question.accept_limitations,
        win_hold=question.win_hold,
        loss_hold=question.loss_hold,
    )
    uni_err = _universe_errors(normalized.universe)
    sport = desk_sport(normalized) or PHASE11_SPORT
    try:
        catalog = get_catalog(cfg, sport=sport, season=DEFAULT_SEASON)
    except (OSError, ValueError, FileNotFoundError):
        missing_data = tuple(dict.fromkeys([*uni_err, "WAREHOUSE"]))
        catalog = None
        resolved_missing_ops: tuple[str, ...] = ()
        satisfied: tuple[str, ...] = ()
        warehouse_version = ""
        caps = question_capabilities(normalized)
        basis = observation_basis_for(normalized)
        status = ResearchStatus.DATA_REQUIRED
        missing_ops = resolved_missing_ops
    else:
        caps = question_capabilities(normalized)
        resolved = catalog.resolve(caps)
        missing_data = tuple(dict.fromkeys([*uni_err, *resolved.missing_data]))
        extra_ops = ()
        if sport == "MLB":
            extra_ops = mlb_basketball_period_or_clock(normalized)
        elif sport in {"ATP", "WTA"}:
            extra_ops = tennis_foreign_period_or_clock(normalized)
        missing_ops = tuple(dict.fromkeys([*resolved.missing_operations, *extra_ops]))
        satisfied = resolved.satisfied_capabilities
        warehouse_version = catalog.warehouse_version
        basis = observation_basis_for(normalized)
        if missing_data:
            status = ResearchStatus.DATA_REQUIRED
        elif missing_ops:
            status = ResearchStatus.OPERATION_REQUIRED
        else:
            status = ResearchStatus.READY
    entries = tuple(
        _compile_entry(entry, conjunction="AND" if i else None)
        for i, entry in enumerate(normalized.entry_conditions)
    )
    plan = ResearchPlan(
        status=status,
        universe=normalized.universe.to_dict(),
        observation_basis=basis,
        resolution=OBS_RESOLUTION,
        pit_requirement=PIT_FIELD,
        entries=entries,
        exits=_compile_exits(normalized),
        terminal=_terminal(normalized),
        required_capabilities=tuple(c.value for c in caps),
        satisfied_capabilities=satisfied,
        missing_data=missing_data,
        missing_operations=missing_ops,
        context_requirements=_context_requirements(normalized),
        warehouse_version=warehouse_version,
        catalog_version=CATALOG_VERSION,
    )
    return ResearchPlan(
        status=plan.status,
        universe=plan.universe,
        observation_basis=plan.observation_basis,
        resolution=plan.resolution,
        pit_requirement=plan.pit_requirement,
        entries=plan.entries,
        exits=plan.exits,
        terminal=plan.terminal,
        required_capabilities=plan.required_capabilities,
        satisfied_capabilities=plan.satisfied_capabilities,
        missing_data=plan.missing_data,
        missing_operations=plan.missing_operations,
        context_requirements=plan.context_requirements,
        compiler_version=COMPILER_VERSION,
        warehouse_version=plan.warehouse_version,
        catalog_version=plan.catalog_version,
        plan_hash=plan.digest(),
    )
