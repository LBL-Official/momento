"""Phase 12 NBA conditional backtest. Observation-path classification only.

Executes a READY ResearchPlan against a ResearchContext.
Calls operations.py / path_engine / observe_entry. Does not copy inequalities.
Does not infer fills, L2, ticks, or settlement from score/price.
Confirm & Run must not import this module.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from roller.config import RollerConfig
from roller.research_query.entry_engine import (
    TradableBar,
    TouchEvent,
    default_snap,
    observe_entry,
)
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    ClockWindow,
    EntryCondition,
    EntryOp,
    PathCondition,
    PathOp,
    PeriodWindow,
    ResearchQuestion,
    ResearchStatus,
    TouchOrdinal,
)
from roller.research_query.operations import RecoveryInvalid
from roller.research_query.path_engine import first_later, find_horizon_bar
from roller.timeutil import parse_utc
from roller.warehouse.coverage import OBS_BASIS, OBS_RESOLUTION, PIT_FIELD
from roller.warehouse.desk import desk_sport
from roller.warehouse.entities import (
    LinkStatus,
    MarketObservation,
    ObservationBasis,
    PBPEvent,
    Settlement,
    SettlementResult,
)
from roller.warehouse.query_context import ResearchContext, get_research_context
from roller.warehouse.research_compiler import (
    CompiledEntry,
    CompiledExit,
    ResearchPlan,
    TerminalBehavior,
    compile_research,
)

ENGINE_VERSION = "1.0.0"
ENGINE_REFERENCE = "reference"
ENGINE_OPTIMIZED = "optimized"

_EXIT_TO_PATH = {
    "REACH": PathOp.REACH,
    "DROP": PathOp.DROP_TO,
    "RISE": PathOp.RISE_TO,
    "RECOVER": PathOp.RECOVER,
    "BOUNCE": PathOp.BOUNCE,
    "REVERT": PathOp.REVERT,
    "MAXIMUM_MOVE": PathOp.MAXIMUM_MOVE,
    "MINIMUM_MOVE": PathOp.MINIMUM_MOVE,
    "NEVER_REACH": PathOp.NEVER_REACH,
}


class BacktestStatus(str, Enum):
    READY = "READY"
    ZERO_RESULTS = "ZERO_RESULTS"
    DATA_REQUIRED = "DATA_REQUIRED"
    OPERATION_REQUIRED = "OPERATION_REQUIRED"


class Classification(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    HELD_TO_SETTLEMENT = "HELD_TO_SETTLEMENT"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    INVALID_SETTLEMENT = "INVALID_SETTLEMENT"
    NO_TERMINAL_RESULT = "NO_TERMINAL_RESULT"
    SAME_BAR_TIE = "SAME_BAR_TIE"
    NO_ENTRY = "NO_ENTRY"


def _text(value: object) -> str:
    return str(value or "").strip()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _iso(ts: datetime | None) -> str:
    if ts is None:
        return ""
    raw = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    return raw


@dataclass(frozen=True)
class BacktestRow:
    internal_game_id: str
    market_id: str
    entry_timestamp: str
    entry_value: int
    entry_operation: str
    entry_period: str = ""
    entry_clock: str = ""
    win_exit_timestamp: str = ""
    win_exit_value: int | None = None
    win_exit_operation: str = ""
    loss_exit_timestamp: str = ""
    loss_exit_value: int | None = None
    loss_exit_operation: str = ""
    classification: str = ""
    settlement_status: str = ""
    settlement_value: int | None = None
    observation_basis: str = OBS_BASIS
    observation_resolution: str = OBS_RESOLUTION
    pit_field: str = PIT_FIELD

    def identity(self) -> tuple[str, str, str, str]:
        return (self.internal_game_id, self.market_id, self.entry_timestamp, self.entry_operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "internal_game_id": self.internal_game_id,
            "market_id": self.market_id,
            "entry_timestamp": self.entry_timestamp,
            "entry_value": self.entry_value,
            "entry_operation": self.entry_operation,
            "entry_period": self.entry_period,
            "entry_clock": self.entry_clock,
            "win_exit_timestamp": self.win_exit_timestamp,
            "win_exit_value": self.win_exit_value,
            "win_exit_operation": self.win_exit_operation,
            "loss_exit_timestamp": self.loss_exit_timestamp,
            "loss_exit_value": self.loss_exit_value,
            "loss_exit_operation": self.loss_exit_operation,
            "classification": self.classification,
            "settlement_status": self.settlement_status,
            "settlement_value": self.settlement_value,
            "observation_basis": self.observation_basis,
            "observation_resolution": self.observation_resolution,
            "pit_field": self.pit_field,
        }


@dataclass(frozen=True)
class ConditionalBacktestResult:
    status: BacktestStatus
    rows: tuple[BacktestRow, ...]
    population: int
    classification_counts: dict[str, int]
    exclusions: dict[str, int]
    coverage: dict[str, Any]
    plan_hash: str
    warehouse_version: str
    observation_basis: str = OBS_BASIS
    pit_field: str = PIT_FIELD
    engine_id: str = ENGINE_REFERENCE
    engine_version: str = ENGINE_VERSION
    result_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "rows": [r.to_dict() for r in self.rows],
            "population": self.population,
            "classification_counts": dict(sorted(self.classification_counts.items())),
            "exclusions": dict(sorted(self.exclusions.items())),
            "coverage": dict(self.coverage),
            "plan_hash": self.plan_hash,
            "warehouse_version": self.warehouse_version,
            "observation_basis": self.observation_basis,
            "pit_field": self.pit_field,
            "engine_id": self.engine_id,
            "engine_version": self.engine_version,
        }

    def digest(self) -> str:
        payload = self.to_dict()
        payload.pop("engine_id", None)
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _finish(result: ConditionalBacktestResult) -> ConditionalBacktestResult:
    return ConditionalBacktestResult(
        status=result.status,
        rows=result.rows,
        population=result.population,
        classification_counts=result.classification_counts,
        exclusions=result.exclusions,
        coverage=result.coverage,
        plan_hash=result.plan_hash,
        warehouse_version=result.warehouse_version,
        observation_basis=result.observation_basis,
        pit_field=result.pit_field,
        engine_id=result.engine_id,
        engine_version=result.engine_version,
        result_hash=result.digest(),
    )


def _closed(
    status: BacktestStatus,
    *,
    plan_hash: str = "",
    warehouse_version: str = "",
    coverage: dict[str, Any] | None = None,
    engine_id: str = ENGINE_REFERENCE,
    exclusions: dict[str, int] | None = None,
) -> ConditionalBacktestResult:
    return _finish(
        ConditionalBacktestResult(
            status=status,
            rows=(),
            population=0,
            classification_counts={},
            exclusions=dict(exclusions or {}),
            coverage=dict(coverage or {}),
            plan_hash=plan_hash,
            warehouse_version=warehouse_version,
            engine_id=engine_id,
        )
    )


def observation_to_bar(obs: MarketObservation, *, gid: str) -> TradableBar | None:
    """Price series from the observation basis. available_at is the PIT clock.

    LAST_TRADE_PRINT uses last_close_e4 and is never labeled yes-bid.
    A non-positive close is not a tradable print and is not a REACH.
    """
    ts = parse_utc(obs.available_at)
    if ts is None or _text(obs.available_at) == "":
        return None
    if obs.basis is ObservationBasis.LAST_TRADE_PRINT:
        if obs.last_close_e4 is None or int(obs.last_close_e4) <= 0:
            return None
        return TradableBar(
            ts=ts,
            bid=int(obs.last_close_e4),
            ask=None,
            volume=obs.volume,
            ticker=obs.ticker,
            game_id=gid,
            raw={
                "available_at": obs.available_at,
                "last_close_e4": obs.last_close_e4,
                "ticker": obs.ticker,
                "internal_game_id": gid,
            },
            basis=BASIS_LAST_TRADE,
        )
    if obs.yes_bid_close is None or int(obs.yes_bid_close) <= 0:
        return None
    return TradableBar(
        ts=ts,
        bid=int(obs.yes_bid_close),
        ask=None,
        volume=obs.volume,
        ticker=obs.ticker,
        game_id=gid,
        raw={
            "available_at": obs.available_at,
            "yes_bid_close": obs.yes_bid_close,
            "ticker": obs.ticker,
            "internal_game_id": gid,
        },
        basis=BASIS_TRADABLE,
    )


def _pbp_row(ev: PBPEvent) -> dict[str, Any]:
    return {
        "available_at": ev.available_at,
        "event_timestamp": ev.event_timestamp,
        "period": ev.period,
        "clock": ev.clock,
        "inning": ev.inning,
        "half": ev.half,
        "event_number": ev.event_number,
        "internal_game_id": ev.internal_game_id,
        "home_score": ev.home_score,
        "away_score": ev.away_score,
    }


def _pbp_dicts(events: tuple[PBPEvent, ...], gid: str) -> list[dict[str, Any]]:
    return [_pbp_row(ev) for ev in events if ev.internal_game_id == gid]


def _pbp_by_game(events: tuple[PBPEvent, ...], gids: set[str]) -> dict[str, list[dict[str, Any]]]:
    """One pass over PBP. Same rows as calling `_pbp_dicts` per game."""
    out: dict[str, list[dict[str, Any]]] = {gid: [] for gid in gids}
    for ev in events:
        bucket = out.get(ev.internal_game_id)
        if bucket is None:
            continue
        bucket.append(_pbp_row(ev))
    return out


def _compiled_to_condition(entry: CompiledEntry) -> EntryCondition:
    ordinal = TouchOrdinal(entry.ordinal) if entry.ordinal else TouchOrdinal.FIRST_TOUCH
    try:
        op = EntryOp(entry.op)
    except ValueError:
        op = EntryOp.FIRST_TOUCH if entry.source_vocabulary == "TOUCH" else None
    clock = None
    if entry.clock and "remaining_from_s" in entry.clock:
        clock = ClockWindow(int(entry.clock["remaining_from_s"]), int(entry.clock["remaining_to_s"]))
    windows = tuple(
        PeriodWindow.from_dict(w) if isinstance(w, dict) else w
        for w in (entry.period_windows or ())
        if w
    )
    return EntryCondition(
        id=entry.id,
        ordinal=ordinal,
        price_e4=int(entry.price_e4),
        period=entry.period,
        clock=clock,
        period_windows=windows,
        nth=entry.nth,
        operation=op,
        direction=entry.direction,
        price_to_e4=entry.price_to_e4,
        max_entry_e4=entry.max_entry_e4,
    )


def _bars_after(bars: list[TradableBar], ts: datetime) -> list[TradableBar]:
    return [b for b in bars if b.ts > ts]


def _plan_sport(plan: ResearchPlan) -> str:
    uni = plan.universe if isinstance(plan.universe, dict) else {}
    return desk_sport(uni) or "NBA"


def _plan_basis(plan: ResearchPlan) -> str:
    token = str(plan.observation_basis or BASIS_TRADABLE).strip().upper()
    return BASIS_LAST_TRADE if token == BASIS_LAST_TRADE else BASIS_TRADABLE


def _te_requested(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not filters:
        return None
    from roller.research_query.hashing import normalize_state_filters

    return normalize_state_filters(filters)


def _entry_matches_te(
    event: TouchEvent,
    bars: list[TradableBar],
    *,
    pbp: list[dict[str, Any]],
    sport: str,
    filters: dict[str, Any],
    team_side: str | None = None,
    game: Any | None = None,
    market: Any | None = None,
) -> bool:
    """Canonical TE population scope at the entry bar. Missing score fails closed."""
    from roller.base_terminal_efficiency.attach import row_matches_te_filters
    from roller.base_terminal_efficiency.builder import build_observation

    if team_side:
        event.bar.raw["team_side"] = team_side
    to_entry = [b for b in bars if b.ts <= event.bar.ts] or [event.bar]
    game_dict = None
    if game is not None:
        game_dict = {
            "home_team_id": getattr(game, "home_team_id", ""),
            "away_team_id": getattr(game, "away_team_id", ""),
            "internal_game_id": getattr(game, "internal_game_id", ""),
        }
    market_dict = {"ticker": event.bar.ticker}
    if market is not None:
        market_dict = {
            "ticker": getattr(market, "ticker", event.bar.ticker),
            "team_side": getattr(market, "team_side", "") or team_side,
        }
    obs = build_observation(
        to_entry,
        pbp_events=pbp,
        game=game_dict,
        market=market_dict,
        sport=sport,
        league=getattr(game, "league", None) if game is not None else None,
        season=getattr(game, "season", None) if game is not None else None,
        attach_terminal=False,
    )
    te = obs.to_dict() if obs is not None else {"point_differential": None, "alignment_status": "UNALIGNED"}
    return row_matches_te_filters({"te": te}, filters)


def _detect_entry(
    bars: list[TradableBar],
    entry: CompiledEntry,
    *,
    pbp: list[dict[str, Any]],
    prior: TouchEvent | None = None,
    sport: str = "NBA",
    basis: str = BASIS_TRADABLE,
) -> tuple[TouchEvent | None, str | None]:
    condition = _compiled_to_condition(entry)
    try:
        event, diag = observe_entry(
            [],
            condition,
            sport=sport,
            pbp_events=pbp,
            precomputed=(bars, 0),
            prior_event=prior,
            basis=basis,
        )
    except RecoveryInvalid:
        return None, "recovery_invalid"
    reason = diag.get("reject_reason")
    if event is None:
        return None, str(reason or "no_event")
    return event, None


def _settlement_resolve_bar(
    settlement: Settlement | None,
    bars_after: list[TradableBar],
    *,
    entry_close: int,
) -> TradableBar | None:
    last = bars_after[-1] if bars_after else None
    raw_ts = ""
    if settlement is not None:
        raw_ts = _text(settlement.settlement_time) or _text(settlement.result_available_at)
    if not raw_ts:
        return last
    ts = parse_utc(raw_ts)
    bid = last.bid if last is not None else (
        int(settlement.settlement_value_e4)
        if settlement is not None and settlement.settlement_value_e4 is not None
        else int(entry_close)
    )
    return TradableBar(
        ts=ts,
        bid=bid,
        ask=last.ask if last is not None else None,
        volume=0,
        ticker=last.ticker if last is not None else "",
        game_id=last.game_id if last is not None else "",
        raw={"available_at": raw_ts, "settlement_resolve": True},
    )


def _exit_hit(
    bars_after: list[TradableBar],
    compiled: CompiledExit,
    *,
    entry_close: int,
    entry_ts: datetime,
    pbp: list[dict[str, Any]],
    settlement: Settlement | None = None,
) -> tuple[TradableBar | None, str | None]:
    if compiled.op == "HOLD":
        return None, None
    if compiled.op == "CLOCK":
        clock = compiled.clock or {}
        minutes = clock.get("horizon_minutes")
        kind = _text(clock.get("horizon_kind") or "clock").lower()
        if kind == "clock":
            kind = "game"
        if minutes is None:
            return None, "clock_unaligned"
        sport = "NBA"

        def snap_fn(ts: datetime) -> dict[str, Any]:
            return default_snap(ts, pbp, sport)

        entry_snap = default_snap(entry_ts, pbp, sport)
        rem = entry_snap.get("period_remaining_s")
        if rem is None and not entry_snap.get("clock"):
            return None, "clock_unaligned"
        from roller.research_query.path_engine import _elapsed_from_snap

        elapsed = _elapsed_from_snap(entry_snap, "NBA")
        if kind == "game" and elapsed is None:
            return None, "clock_unaligned"
        hit = find_horizon_bar(
            bars_after,
            kind=kind if kind in {"market", "game"} else "game",
            minutes=int(minutes),
            entry_ts=entry_ts,
            entry_elapsed_s=elapsed,
            snap_fn=snap_fn,
            sport=sport,
        )
        return hit, None
    path_op = _EXIT_TO_PATH.get(compiled.op)
    if path_op is None or compiled.price_e4 is None:
        return None, None
    resolve = None
    if path_op is PathOp.NEVER_REACH:
        resolve = _settlement_resolve_bar(settlement, bars_after, entry_close=entry_close)
    return first_later(
        bars_after,
        entry_close=entry_close,
        op=path_op,
        price_e4=int(compiled.price_e4),
        resolve_bar=resolve,
    ), None


def _classify_hold(settlement: Settlement | None, terminal: TerminalBehavior) -> tuple[str, str, int | None]:
    if terminal is TerminalBehavior.NO_TERMINAL_RESULT:
        return Classification.NO_TERMINAL_RESULT.value, "", None
    if settlement is None:
        return Classification.MISSING_SETTLEMENT.value, SettlementResult.MISSING.value, None
    if settlement.result is SettlementResult.MISSING:
        return Classification.MISSING_SETTLEMENT.value, settlement.result.value, settlement.settlement_value_e4
    if settlement.result is SettlementResult.INVALID:
        return Classification.INVALID_SETTLEMENT.value, settlement.result.value, settlement.settlement_value_e4
    return (
        Classification.HELD_TO_SETTLEMENT.value,
        settlement.result.value,
        settlement.settlement_value_e4,
    )


def _row_from_event(
    event: TouchEvent,
    *,
    ticker: str,
    gid: str,
    classification: str,
    settlement: Settlement | None,
    win_bar: TradableBar | None = None,
    win_op: str = "",
    loss_bar: TradableBar | None = None,
    loss_op: str = "",
) -> BacktestRow:
    settle_status = settlement.result.value if settlement is not None else ""
    settle_value = settlement.settlement_value_e4 if settlement is not None else None
    if classification in {
        Classification.MISSING_SETTLEMENT.value,
        Classification.INVALID_SETTLEMENT.value,
        Classification.NO_TERMINAL_RESULT.value,
    }:
        if classification == Classification.NO_TERMINAL_RESULT.value:
            settle_status = ""
            settle_value = None
    snap = event.snap or {}
    bar_basis = _text(getattr(event.bar, "basis", "")) or OBS_BASIS
    return BacktestRow(
        internal_game_id=gid,
        market_id=ticker,
        entry_timestamp=_text((event.bar.raw or {}).get("available_at")) or _iso(event.bar.ts),
        entry_value=int(event.bar.bid),
        entry_operation=event.operation.value if event.operation is not None else "",
        entry_period=_text(snap.get("slice") or snap.get("period")),
        entry_clock=_text(snap.get("clock")),
        win_exit_timestamp=_text((win_bar.raw or {}).get("available_at")) if win_bar else "",
        win_exit_value=int(win_bar.bid) if win_bar else None,
        win_exit_operation=win_op,
        loss_exit_timestamp=_text((loss_bar.raw or {}).get("available_at")) if loss_bar else "",
        loss_exit_value=int(loss_bar.bid) if loss_bar else None,
        loss_exit_operation=loss_op,
        classification=classification,
        settlement_status=settle_status,
        settlement_value=settle_value,
        observation_basis=bar_basis,
    )


def evaluate_market(
    bars: list[TradableBar],
    plan: ResearchPlan,
    *,
    ticker: str,
    gid: str,
    pbp: list[dict[str, Any]],
    settlement: Settlement | None,
    exclusions: Counter[str],
    te_filters: dict[str, Any] | None = None,
    game: Any | None = None,
    market: Any | None = None,
) -> BacktestRow | None:
    if not bars:
        exclusions["no_obs"] += 1
        return None
    if not plan.entries:
        exclusions["no_entry_spec"] += 1
        return None
    first_spec = plan.entries[0]
    sport = _plan_sport(plan)
    basis = _plan_basis(plan)
    event, reason = _detect_entry(bars, first_spec, pbp=pbp, sport=sport, basis=basis)
    if event is None:
        exclusions[reason or "no_event"] += 1
        return None
    if _te_requested(te_filters):
        team_side = getattr(market, "team_side", None) or (event.bar.raw or {}).get("team_side")
        if not _entry_matches_te(
            event,
            bars,
            pbp=pbp,
            sport=sport,
            filters=te_filters or {},
            team_side=str(team_side) if team_side else None,
            game=game,
            market=market,
        ):
            exclusions["te_scope"] += 1
            return None
    current = event
    for nxt in plan.entries[1:]:
        later = _bars_after(bars, current.bar.ts)
        ev, reason = _detect_entry(later, nxt, pbp=pbp, prior=current, sport=sport, basis=basis)
        if ev is None:
            exclusions[reason or "and_miss"] += 1
            return None
        current = ev
    later = _bars_after(bars, current.bar.ts)
    win_specs = [x for x in plan.exits if x.outcome == "win"]
    loss_specs = [x for x in plan.exits if x.outcome == "loss"]
    win_bar: TradableBar | None = None
    win_op = ""
    loss_bar: TradableBar | None = None
    loss_op = ""
    for spec in win_specs:
        if spec.op == "HOLD":
            continue
        hit, err = _exit_hit(
            later,
            spec,
            entry_close=current.bar.bid,
            entry_ts=current.bar.ts,
            pbp=pbp,
            settlement=settlement,
        )
        if err:
            exclusions[err] += 1
            continue
        if hit is not None:
            win_bar, win_op = hit, spec.op
            break
    for spec in loss_specs:
        if spec.op == "HOLD":
            continue
        hit, err = _exit_hit(
            later,
            spec,
            entry_close=current.bar.bid,
            entry_ts=current.bar.ts,
            pbp=pbp,
            settlement=settlement,
        )
        if err:
            exclusions[err] += 1
            continue
        if hit is not None:
            loss_bar, loss_op = hit, spec.op
            break
    if win_bar is not None and loss_bar is not None and win_bar.ts == loss_bar.ts:
        return _row_from_event(
            current,
            ticker=ticker,
            gid=gid,
            classification=Classification.SAME_BAR_TIE.value,
            settlement=settlement,
            win_bar=win_bar,
            win_op=win_op,
            loss_bar=loss_bar,
            loss_op=loss_op,
        )
    if win_bar is not None and (loss_bar is None or win_bar.ts < loss_bar.ts):
        return _row_from_event(
            current,
            ticker=ticker,
            gid=gid,
            classification=Classification.WIN.value,
            settlement=settlement,
            win_bar=win_bar,
            win_op=win_op,
        )
    if loss_bar is not None and (win_bar is None or loss_bar.ts < win_bar.ts):
        return _row_from_event(
            current,
            ticker=ticker,
            gid=gid,
            classification=Classification.LOSS.value,
            settlement=settlement,
            loss_bar=loss_bar,
            loss_op=loss_op,
        )
    klass, settle_st, settle_val = _classify_hold(settlement, plan.terminal)
    row = _row_from_event(
        current,
        ticker=ticker,
        gid=gid,
        classification=klass,
        settlement=settlement,
    )
    if klass == Classification.NO_TERMINAL_RESULT.value:
        return BacktestRow(
            internal_game_id=row.internal_game_id,
            market_id=row.market_id,
            entry_timestamp=row.entry_timestamp,
            entry_value=row.entry_value,
            entry_operation=row.entry_operation,
            entry_period=row.entry_period,
            entry_clock=row.entry_clock,
            classification=klass,
            settlement_status="",
            settlement_value=None,
        )
    if klass in {Classification.MISSING_SETTLEMENT.value, Classification.INVALID_SETTLEMENT.value}:
        return BacktestRow(
            internal_game_id=row.internal_game_id,
            market_id=row.market_id,
            entry_timestamp=row.entry_timestamp,
            entry_value=row.entry_value,
            entry_operation=row.entry_operation,
            entry_period=row.entry_period,
            entry_clock=row.entry_clock,
            classification=klass,
            settlement_status=settle_st,
            settlement_value=settle_val,
        )
    return row


def _apply_exposure(
    rows: list[BacktestRow],
    exclusions: Counter[str],
    exposure: dict[str, Any] | None,
) -> list[BacktestRow]:
    """Keep the first chronological entry per unit when strategy_enforced.

    Verify-only leaves the per-market First Touch rows unchanged.
    Same-timestamp ties stay fail-closed (neither side is invented).
    """
    from roller.exposure_contract import (
        MODE_STRATEGY_ENFORCED,
        enforce_exposure,
        executable_strategy_contract,
        normalize_enforcement_mode,
    )

    if not exposure:
        return rows
    mode = normalize_enforcement_mode(
        exposure.get("enforcement_mode") or exposure.get("exposure_enforcement_mode")
    )
    if mode != MODE_STRATEGY_ENFORCED:
        return rows
    unit = exposure.get("exposure_unit") or "GAME"
    cap = exposure.get("max_entries_per_unit")
    if cap is None and str(unit).upper() == "GAME":
        cap = 1
    contract = executable_strategy_contract(
        exposure_unit=unit,
        max_entries_per_unit=cap,
        enforcement_mode=MODE_STRATEGY_ENFORCED,
    )
    candidates: list[dict[str, Any]] = []
    for row in rows:
        candidates.append(
            {
                "internal_game_id": row.internal_game_id,
                "ticker": row.market_id,
                "entry_ts": row.entry_timestamp,
                "candidate_id": f"{row.entry_timestamp}|{row.market_id}|{row.internal_game_id}",
                "_row": row,
            }
        )
    decision = enforce_exposure(candidates, contract)
    kept = [item["_row"] for item in decision.get("retained") or []]
    dropped = len(decision.get("excluded") or [])
    if dropped:
        exclusions["exposure_game"] += dropped
    return kept


def _linked_pairs(context: ResearchContext) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in context.links:
        if link.status is not LinkStatus.LINKED:
            continue
        key = (link.internal_game_id, link.ticker)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    pairs.sort()
    return pairs


def _index_context(context: ResearchContext) -> tuple[
    dict[tuple[str, str], list[TradableBar]],
    dict[str, list[dict[str, Any]]],
    dict[str, Settlement],
]:
    ticker_to_gid = {
        link.ticker: link.internal_game_id
        for link in context.links
        if link.status is LinkStatus.LINKED and link.ticker
    }
    obs_index: dict[tuple[str, str], list[TradableBar]] = {}
    for obs in context.observations:
        gid = ticker_to_gid.get(obs.ticker)
        if not gid:
            continue
        if obs.internal_game_id and obs.internal_game_id != gid:
            continue
        bar = observation_to_bar(obs, gid=gid)
        if bar is None:
            continue
        obs_index.setdefault((gid, obs.ticker), []).append(bar)
    for key in obs_index:
        obs_index[key].sort(key=lambda b: (b.ts, b.ticker))
    pbp_index = _pbp_by_game(context.pbp_events, set(ticker_to_gid.values()))
    settle_index = {s.ticker: s for s in context.settlements}
    return obs_index, pbp_index, settle_index


def run_plan(
    plan: ResearchPlan,
    context: ResearchContext,
    *,
    engine_id: str = ENGINE_REFERENCE,
    te_filters: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> ConditionalBacktestResult:
    if plan.status is ResearchStatus.DATA_REQUIRED:
        return _closed(BacktestStatus.DATA_REQUIRED, plan_hash=plan.plan_hash, warehouse_version=context.warehouse_version, engine_id=engine_id)
    if plan.status is ResearchStatus.OPERATION_REQUIRED:
        return _closed(BacktestStatus.OPERATION_REQUIRED, plan_hash=plan.plan_hash, warehouse_version=context.warehouse_version, engine_id=engine_id)
    exclusions: Counter[str] = Counter()
    games_by_id = {g.internal_game_id: g for g in context.games}
    markets_by_ticker = {m.ticker: m for m in context.markets}
    if engine_id == ENGINE_OPTIMIZED:
        obs_index, pbp_index, settle_index = _index_context(context)
        pairs = sorted(obs_index.keys())
        extra = _linked_pairs(context)
        for pair in extra:
            if pair not in obs_index:
                pairs.append(pair)
        pairs = sorted(set(pairs))
        rows: list[BacktestRow] = []
        for gid, ticker in pairs:
            bars = obs_index.get((gid, ticker), [])
            row = evaluate_market(
                bars,
                plan,
                ticker=ticker,
                gid=gid,
                pbp=pbp_index.get(gid, []),
                settlement=settle_index.get(ticker),
                exclusions=exclusions,
                te_filters=te_filters,
                game=games_by_id.get(gid),
                market=markets_by_ticker.get(ticker),
            )
            if row is not None:
                rows.append(row)
    else:
        ticker_to_gid = {
            link.ticker: link.internal_game_id
            for link in context.links
            if link.status is LinkStatus.LINKED and link.ticker
        }
        rows = []
        games = sorted(context.games, key=lambda g: g.internal_game_id)
        uni = plan.universe if isinstance(plan.universe, dict) else {}
        dated = bool(uni.get("date_from") or uni.get("date_to"))
        if not games:
            gids = [] if dated else sorted(set(ticker_to_gid.values()))
        else:
            gids = list(dict.fromkeys(g.internal_game_id for g in games))
        for gid in gids:
            tickers = sorted(t for t, g in ticker_to_gid.items() if g == gid)
            pbp = _pbp_dicts(context.pbp_events, gid)
            settle_by = {s.ticker: s for s in context.settlements}
            for ticker in tickers:
                bars: list[TradableBar] = []
                for obs in context.observations:
                    if obs.ticker != ticker:
                        continue
                    if obs.internal_game_id and obs.internal_game_id != gid:
                        continue
                    bar = observation_to_bar(obs, gid=gid)
                    if bar is None:
                        exclusions["invalid_observation"] += 1
                        continue
                    bars.append(bar)
                bars.sort(key=lambda b: (b.ts, b.ticker))
                row = evaluate_market(
                    bars,
                    plan,
                    ticker=ticker,
                    gid=gid,
                    pbp=pbp,
                    settlement=settle_by.get(ticker),
                    exclusions=exclusions,
                    te_filters=te_filters,
                    game=games_by_id.get(gid),
                    market=markets_by_ticker.get(ticker),
                )
                if row is not None:
                    rows.append(row)
    rows = _apply_exposure(rows, exclusions, exposure)
    rows_t = tuple(sorted(rows, key=lambda r: r.identity()))
    counts = Counter(r.classification for r in rows_t)
    status = BacktestStatus.READY if rows_t else BacktestStatus.ZERO_RESULTS
    return _finish(
        ConditionalBacktestResult(
            status=status,
            rows=rows_t,
            population=len(rows_t),
            classification_counts=dict(counts),
            exclusions=dict(exclusions),
            coverage=dict(context.coverage),
            plan_hash=plan.plan_hash,
            warehouse_version=context.warehouse_version,
            observation_basis=_plan_basis(plan),
            engine_id=engine_id,
        )
    )


def run_plan_reference(
    plan: ResearchPlan,
    context: ResearchContext,
    *,
    te_filters: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> ConditionalBacktestResult:
    return run_plan(plan, context, engine_id=ENGINE_REFERENCE, te_filters=te_filters, exposure=exposure)


def run_plan_optimized(
    plan: ResearchPlan,
    context: ResearchContext,
    *,
    te_filters: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> ConditionalBacktestResult:
    return run_plan(plan, context, engine_id=ENGINE_OPTIMIZED, te_filters=te_filters, exposure=exposure)


def run_conditional_backtest(
    question: ResearchQuestion,
    cfg: RollerConfig | None = None,
    *,
    engine_id: str = ENGINE_OPTIMIZED,
    te_filters: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> ConditionalBacktestResult:
    cfg = cfg or RollerConfig()
    plan = compile_research(question, cfg)
    if plan.status is ResearchStatus.DATA_REQUIRED:
        return _closed(BacktestStatus.DATA_REQUIRED, plan_hash=plan.plan_hash, warehouse_version="", engine_id=engine_id)
    if plan.status is ResearchStatus.OPERATION_REQUIRED:
        return _closed(BacktestStatus.OPERATION_REQUIRED, plan_hash=plan.plan_hash, warehouse_version="", engine_id=engine_id)
    loaded = get_research_context(question, cfg, plan=plan)
    if loaded.status is ResearchStatus.DATA_REQUIRED:
        return _closed(
            BacktestStatus.DATA_REQUIRED,
            plan_hash=plan.plan_hash,
            coverage=loaded.coverage,
            engine_id=engine_id,
        )
    if loaded.status is ResearchStatus.OPERATION_REQUIRED:
        return _closed(
            BacktestStatus.OPERATION_REQUIRED,
            plan_hash=plan.plan_hash,
            coverage=loaded.coverage,
            engine_id=engine_id,
        )
    if loaded.context is None:
        return _closed(BacktestStatus.DATA_REQUIRED, plan_hash=plan.plan_hash, engine_id=engine_id)
    return run_plan(plan, loaded.context, engine_id=engine_id, te_filters=te_filters, exposure=exposure)


def compare_backtest_rows(
    reference: ConditionalBacktestResult,
    optimized: ConditionalBacktestResult,
) -> list[dict[str, Any]]:
    """Identity-keyed field compare. Any difference is a correctness failure."""
    fields = (
        "internal_game_id",
        "market_id",
        "entry_timestamp",
        "entry_value",
        "entry_operation",
        "entry_period",
        "entry_clock",
        "win_exit_timestamp",
        "win_exit_value",
        "win_exit_operation",
        "loss_exit_timestamp",
        "loss_exit_value",
        "loss_exit_operation",
        "classification",
        "settlement_status",
        "settlement_value",
    )
    ref_map = {r.identity(): r for r in reference.rows}
    opt_map = {r.identity(): r for r in optimized.rows}
    diffs: list[dict[str, Any]] = []
    for key in sorted(set(ref_map) | set(opt_map)):
        if key not in ref_map:
            diffs.append(
                {
                    "game": key[0],
                    "market": key[1],
                    "entry": key[2],
                    "field": "row",
                    "reference": None,
                    "optimized": opt_map[key].to_dict(),
                }
            )
            continue
        if key not in opt_map:
            diffs.append(
                {
                    "game": key[0],
                    "market": key[1],
                    "entry": key[2],
                    "field": "row",
                    "reference": ref_map[key].to_dict(),
                    "optimized": None,
                }
            )
            continue
        a, b = ref_map[key].to_dict(), opt_map[key].to_dict()
        for name in fields:
            if a.get(name) != b.get(name):
                diffs.append(
                    {
                        "game": key[0],
                        "market": key[1],
                        "entry": key[2],
                        "field": name,
                        "reference": a.get(name),
                        "optimized": b.get(name),
                    }
                )
    if reference.population != optimized.population:
        diffs.append(
            {
                "game": "",
                "market": "",
                "entry": "",
                "field": "population",
                "reference": reference.population,
                "optimized": optimized.population,
            }
        )
    return diffs
