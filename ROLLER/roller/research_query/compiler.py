"""Compile ResearchQuestion → status + execution path. No warehouse scan."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.research_query.availability import (
    CROSS_VENUE_NO_JOINT_BASIS,
    data_gaps,
    optional_omissions,
)
from roller.research_query.capabilities import (
    draft_unsupported_families,
    reserved_scope_names,
    unsupported_operations,
)
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    CompileResult,
    ENTRY_OP_EVENT_DEFINITION,
    ENTRY_OP_FAMILIES,
    EntryCondition,
    EntryOp,
    EVENT_DEFINITION,
    EVENT_DEFINITION_BAND,
    ExecutionPath,
    ExitOutcome,
    HORIZON_WIN_E4,
    universe_basis,
    PathCondition,
    PathOp,
    PeriodWindow,
    ClockWindow,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
    cents_to_e4,
    max_entry_e4_from_raw,
    TOUCH_FAMILIES,
)

_HORIZON_FAMS = {
    "horizon_game_win": ("game", PathOp.HORIZON_WIN),
    "horizon_game_loss": ("game", PathOp.HORIZON_LOSS),
    "horizon_market_win": ("market", PathOp.HORIZON_WIN),
    "horizon_market_loss": ("market", PathOp.HORIZON_LOSS),
}
_TERMINAL_FAMS = {
    "yes": TerminalOutcome.YES,
    "hold_expiration_win": TerminalOutcome.YES,
    "no": TerminalOutcome.NO,
    "hold_expiration_loss": TerminalOutcome.NO,
    "both": TerminalOutcome.BOTH,
}
from roller.research_query.season_dates import collapse_full_season_dates
from roller.research_query.season_mapping import warehouse_season
from roller.research_query.sport_family import (
    PBP_PRODUCER_FAMILY,
    families_in,
    period_belongs_to_family,
    remaining_clock_legal,
)
from roller.research_query.validation import validate_question
from roller.state.clock import clock_remaining_seconds

# TE chips that execute can apply. Unknown keys are not silent no-ops.
_KNOWN_TE_KEYS = frozenset(
    {
        "scoreSide",
        "score_side",
        "absDiff",
        "abs_diff",
        "exactDiffs",
        "exact_diffs",
        "customRange",
        "custom_range",
        "half",
        "yesBatting",
        "yes_batting",
        "outs",
        "count",
        "runners",
        "tennisPointScores",
        "tennis_point_scores",
        "tennisServe",
        "tennis_serve",
        "tennisEventStates",
        "tennis_event_states",
        "tennisSetLead",
        "tennis_set_lead",
        "tennisGameLead",
        "tennis_game_lead",
        "tennisPointLead",
        "tennis_point_lead",
    }
)


def _clock_from_draft(from_s: str | None, to_s: str | None):
    from roller.research_query.models import ClockWindow

    if not from_s and not to_s:
        return None
    a = clock_remaining_seconds(from_s)
    b = clock_remaining_seconds(to_s)
    if a is None and b is None:
        return None
    return ClockWindow(int(a if a is not None else 0), int(b if b is not None else 0))


def _period_from_draft(raw: dict[str, Any]) -> tuple[str | None, Any, tuple[PeriodWindow, ...]]:
    """One window stays on period/clock. Two or more windows are OR filters."""
    raw_windows = raw.get("periodWindows") or raw.get("period_windows") or []
    windows: list[PeriodWindow] = []
    for w in raw_windows:
        if not isinstance(w, dict):
            continue
        clock_raw = w.get("clock")
        if isinstance(clock_raw, dict) and "remaining_from_s" in clock_raw:
            clock = ClockWindow.from_dict(clock_raw)
        else:
            clock = _clock_from_draft(
                w.get("clockFrom") or w.get("clock_from"),
                w.get("clockTo") or w.get("clock_to"),
            )
        windows.append(PeriodWindow(period=w.get("period"), clock=clock))
    period = raw.get("period")
    clock = _clock_from_draft(raw.get("clockFrom"), raw.get("clockTo"))
    if len(windows) > 1:
        return None, None, tuple(windows)
    if len(windows) == 1:
        return windows[0].period, windows[0].clock, ()
    return period, clock, ()


def _clock_bounds(clock: ClockWindow | None) -> tuple[int, int] | None:
    if clock is None:
        return None
    a, b = int(clock.remaining_from_s), int(clock.remaining_to_s)
    return (min(a, b), max(a, b))


def _raw_clock_spec(raw: dict[str, Any]) -> tuple[bool, ClockWindow | None]:
    """True when the draft named a clock. Window is None if it did not compile."""
    clock_raw = raw.get("clock")
    if isinstance(clock_raw, dict) and "remaining_from_s" in clock_raw:
        return True, ClockWindow.from_dict(clock_raw)
    from_s = raw.get("clockFrom") if raw.get("clockFrom") is not None else raw.get("clock_from")
    to_s = raw.get("clockTo") if raw.get("clockTo") is not None else raw.get("clock_to")
    if from_s in (None, "") and to_s in (None, ""):
        return False, None
    return True, _clock_from_draft(from_s, to_s)


def _clock_on_condition(cond: EntryCondition, want: ClockWindow, *, period: str | None) -> bool:
    want_bounds = _clock_bounds(want)
    for window in cond.period_filters():
        if period and window.period != period:
            continue
        if _clock_bounds(window.clock) == want_bounds:
            return True
    return False


def _draft_outcome(raw: dict[str, Any]) -> ExitOutcome | None:
    oc = raw.get("outcome")
    if oc in ("win", "loss"):
        return ExitOutcome(oc)
    return None


def _draft_direction(raw: dict[str, Any]) -> str | None:
    d = raw.get("direction")
    if d in ("up", "down"):
        return str(d)
    return None


def question_from_draft(draft: dict[str, Any]) -> ResearchQuestion:
    """Map frontend WorkflowDraft JSON → AST. Preserves SECOND_TOUCH as enum."""
    u = draft.get("universe") or {}
    entries: list[EntryCondition] = []
    for raw in draft.get("entryConditions") or draft.get("entry_conditions") or []:
        family = str(raw.get("family") or "")
        operation: EntryOp | None = None
        if family in TOUCH_FAMILIES:
            ordinal = TOUCH_FAMILIES[family]
        elif family.upper() in TouchOrdinal.__members__:
            ordinal = TouchOrdinal(family.upper())
        elif family in ENTRY_OP_FAMILIES:
            operation = ENTRY_OP_FAMILIES[family]
            ordinal = TouchOrdinal.FIRST_TOUCH
        elif family.upper() in EntryOp.__members__:
            operation = EntryOp(family.upper())
            ordinal = TouchOrdinal.FIRST_TOUCH
        else:
            continue
        cents = raw.get("priceCents") if raw.get("priceCents") is not None else raw.get("price_cents")
        price_from = raw.get("priceFrom") if raw.get("priceFrom") is not None else raw.get("price_from")
        price_to = raw.get("priceTo") if raw.get("priceTo") is not None else raw.get("price_to")
        price_to_e4 = None
        event_definition = EVENT_DEFINITION
        if cents is not None:
            price_e4 = cents_to_e4(int(cents))
        elif raw.get("price_e4") is not None:
            price_e4 = int(raw["price_e4"])
            if raw.get("price_to_e4") is not None:
                price_to_e4 = int(raw["price_to_e4"])
                event_definition = EVENT_DEFINITION_BAND
        elif price_from is not None and price_to is not None:
            price_e4 = cents_to_e4(int(price_from))
            price_to_e4 = cents_to_e4(int(price_to))
            event_definition = EVENT_DEFINITION_BAND
        else:
            continue
        if operation is not None:
            event_definition = ENTRY_OP_EVENT_DEFINITION.get(operation, event_definition)
            price_to_e4 = None
        nth = raw.get("touchNValue") if raw.get("touchN") == "N" else raw.get("touchN")
        if nth == "N":
            nth = raw.get("touchNValue")
        period, clock, period_windows = _period_from_draft(raw)
        entries.append(
            EntryCondition(
                id=str(raw.get("id") or f"e{len(entries)}"),
                ordinal=ordinal,
                price_e4=price_e4,
                period=period,
                clock=clock,
                period_windows=period_windows,
                nth=int(nth) if nth not in (None, "N") else None,
                event_definition=event_definition,
                price_to_e4=price_to_e4,
                max_entry_e4=max_entry_e4_from_raw(raw),
                operation=operation,
                direction=_draft_direction(raw),
            )
        )
    paths: list[PathCondition] = []
    terminal = TerminalOutcome.BOTH
    win_hold = False
    loss_hold = False
    req: list[str] = []
    for raw in draft.get("exitConditions") or draft.get("path_conditions") or []:
        kind = raw.get("kind")
        family = str(raw.get("family") or "")
        outcome = _draft_outcome(raw)
        if kind == "terminal" or family in _TERMINAL_FAMS:
            if outcome is not None and family in ("hold_expiration_win", "yes"):
                win_hold = True
            elif outcome is not None and family in ("hold_expiration_loss", "no"):
                loss_hold = True
            else:
                terminal = _TERMINAL_FAMS.get(family, TerminalOutcome.BOTH)
            continue
        if kind == "horizon" or family in _HORIZON_FAMS:
            mapped = _HORIZON_FAMS.get(family)
            mins = raw.get("horizonMinutes") if raw.get("horizonMinutes") is not None else raw.get("horizon_minutes")
            # Never silently drop a selected horizon into Reach-only.
            if mapped is None or mins is None:
                req.append(family or "horizon")
                continue
            horizon_kind, op = mapped
            paths.append(
                PathCondition(
                    id=str(raw.get("id") or f"p{len(paths)}"),
                    op=op,
                    price_e4=HORIZON_WIN_E4,
                    sequential=bool(raw.get("sequential")),
                    horizon_kind=str(raw.get("horizonKind") or raw.get("horizon_kind") or horizon_kind),
                    horizon_minutes=int(mins),
                    outcome=outcome,
                )
            )
            continue
        op_map = {
            "reach": PathOp.REACH,
            "drop_to": PathOp.DROP_TO,
            "rise_to": PathOp.RISE_TO,
            "recover": PathOp.RECOVER,
            "bounce": PathOp.BOUNCE,
            "revert": PathOp.REVERT,
            "maximum_move": PathOp.MAXIMUM_MOVE,
            "minimum_move": PathOp.MINIMUM_MOVE,
            "never_reach": PathOp.NEVER_REACH,
        }
        if family not in op_map:
            if family:
                req.append(family)
            continue
        cents = raw.get("priceCents") if raw.get("priceCents") is not None else raw.get("price_cents")
        if cents is None and raw.get("price_e4") is not None:
            price_e4 = int(raw["price_e4"])
        elif cents is None:
            req.append(family)
            continue
        else:
            price_e4 = cents_to_e4(int(cents))
        paths.append(
            PathCondition(
                id=str(raw.get("id") or f"p{len(paths)}"),
                op=op_map[family],
                price_e4=price_e4,
                sequential=bool(raw.get("sequential")),
                outcome=outcome,
            )
        )
    for raw in draft.get("entryConditions") or []:
        fam = str(raw.get("family") or "")
        if fam and fam not in TOUCH_FAMILIES and fam not in ENTRY_OP_FAMILIES and fam != "clock":
            req.append(fam)
    raw_leagues = tuple(u.get("leagues") or ())
    from roller.research_query.season_mapping import normalize_league
    from roller.research_query.sport_family import is_baseball

    leagues: tuple[str, ...]
    if raw_leagues:
        canon: list[str] = []
        for item in raw_leagues:
            try:
                mapped = normalize_league(str(item))
            except ValueError:
                mapped = str(item)
            if mapped not in canon:
                canon.append(mapped)
        leagues = tuple(canon)
    elif any(is_baseball(str(s)) for s in (u.get("sports") or ())):
        leagues = ("MLB",)
    else:
        from roller.research_query.sport_family import is_tennis

        if any(is_tennis(str(s)) for s in (u.get("sports") or ())):
            leagues = ("ATP", "WTA")
        else:
            leagues = ()
    seasons = tuple(u.get("seasons") or ())
    # Keep the window the operator entered. Full-season fill is still a window.
    # Lock matching may collapse a copy; execute must not unbind the question.
    date_from = u.get("dateFrom") or u.get("date_from") or None
    date_to = u.get("dateTo") or u.get("date_to") or None
    if date_from == "":
        date_from = None
    if date_to == "":
        date_to = None
    return ResearchQuestion(
        universe=Universe(
            sports=tuple(u.get("sports") or ()),
            leagues=leagues,
            seasons=seasons,
            markets=tuple(u.get("markets") or ()),
            market_data=tuple(u.get("marketData") or u.get("market_data") or ()),
            game_data=tuple(u.get("dataSources") or u.get("game_data") or ()),
            date_from=date_from,
            date_to=date_to,
        ),
        entry_conditions=tuple(entries),
        path_conditions=tuple(paths),
        terminal=terminal,
        requested_dimensions=tuple(req),
        accept_limitations=bool(draft.get("accept_limitations") or draft.get("acceptLimitations")),
        win_hold=win_hold,
        loss_hold=loss_hold,
    )


def _seasons_aligned(seasons: tuple[str, ...]) -> bool:
    if not seasons:
        return True
    mapped = {warehouse_season(s) for s in seasons}
    return mapped <= {"2025-2026"}


def reference_match(question: ResearchQuestion) -> str | None:
    """Exact semantic lock only. Any material difference → None."""
    u = question.universe
    collapsed_from, collapsed_to = collapse_full_season_dates(
        u.leagues, u.seasons, u.date_from, u.date_to
    )
    # Custom subset stays off the lock. Published full-season fill may still lock.
    if collapsed_from or collapsed_to:
        return None
    if "kalshi" not in u.markets or len(u.markets) != 1:
        return None
    if "candles" not in u.market_data:
        return None
    extra_md = [d for d in u.market_data if d != "candles"]
    if extra_md:
        return None
    if not _seasons_aligned(u.seasons):
        return None
    if len(question.entry_conditions) != 1:
        return None
    e = question.entry_conditions[0]
    if e.ordinal is not TouchOrdinal.FIRST_TOUCH:
        return None
    if e.operation is not None and e.operation is not EntryOp.FIRST_TOUCH:
        return None
    if e.direction:
        return None
    if e.price_e4 != 8000:
        return None
    if e.price_to_e4 is not None:
        return None
    if e.max_entry_e4 is not None:
        return None
    if e.clock:
        return None
    if e.period_windows:
        return None
    if question.win_hold or question.loss_hold:
        return None
    paths = question.path_conditions
    if len(paths) != 1:
        return None
    p = paths[0]
    if p.op is not PathOp.REACH or p.price_e4 != 4000 or p.sequential:
        return None
    if p.horizon_kind or p.horizon_minutes:
        return None
    if p.outcome is not None:
        return None
    if question.terminal not in (TerminalOutcome.BOTH, TerminalOutcome.YES, TerminalOutcome.NO):
        return None
    if len(u.leagues) == 1 and u.leagues[0] == "NBA" and e.period == "Q3":
        if u.sports and set(u.sports) - {"basketball"}:
            return None
        return "FIRST80_Q3"
    if len(u.leagues) == 1 and u.leagues[0] == "NCAAB" and e.period == "P5":
        if u.sports and set(u.sports) - {"basketball"}:
            return None
        return "NCAAB_FIRST80_P5"
    return None


def _basis_available(basis: str, universe: Universe | None = None) -> tuple[str, ...]:
    if basis == BASIS_LAST_TRADE:
        if universe is not None and "polymarket" in universe.markets:
            return ("polymarket_1m_last_trade", "last_trade_close_cross")
        return ("kalshi_1m_last_trade", "last_trade_close_cross")
    return ("kalshi_1m_candles", "tradable_yes_bid_close_cross")


def _universe_family(question: ResearchQuestion) -> str | None:
    found = families_in(question.universe.sports, question.universe.leagues)
    if len(found) != 1:
        return None
    return next(iter(found))


def _family_chip_errors(question: ResearchQuestion) -> list[str]:
    """Foreign-family period/clock chips fail closed. They are not silent N=0."""
    fam = _universe_family(question)
    if fam is None:
        return []
    errors: list[str] = []
    for cond in question.entry_conditions:
        for window in cond.period_filters():
            if window.clock and not remaining_clock_legal(fam):
                errors.append(
                    "Basketball remaining-clock chips are not defined on this sport. "
                    "They are not silently dropped into a clock_filter exclusion."
                )
            if window.period and not period_belongs_to_family(window.period, fam):
                errors.append(
                    f"Period {window.period} is not defined on {fam}. "
                    "A foreign-family period is not an empty population."
                )
    return errors


def _pbp_source_errors(question: ResearchQuestion) -> list[str]:
    fam = _universe_family(question)
    if fam is None:
        return []
    errors: list[str] = []
    for src in question.universe.game_data:
        key = str(src or "").strip()
        producer = PBP_PRODUCER_FAMILY.get(key)
        if producer and producer != fam:
            errors.append(
                f"PBP source {key} is not the warehouse producer for {fam}. "
                "Canonical PBP is not silently substituted."
            )
    return errors


def _te_filter_errors(draft: dict[str, Any]) -> list[str]:
    raw = draft.get("teFilters") if isinstance(draft.get("teFilters"), dict) else draft.get("te_filters")
    if not isinstance(raw, dict) or not raw:
        return []
    unknown = [str(k) for k in raw if str(k) not in _KNOWN_TE_KEYS]
    if not unknown:
        return []
    return [
        f"TE chip {name} is not a recognized PIT filter. Unknown chips are not silent no-ops."
        for name in unknown
    ]


def compile_question(
    question: ResearchQuestion,
    *,
    cfg: RollerConfig | None = None,
    draft: dict[str, Any] | None = None,
) -> CompileResult:
    cfg = cfg or RollerConfig()
    from roller.research_query.sport_family import (
        MIXED_CLOCK_REASON,
        is_baseball,
        mixed_clock_families,
    )

    if mixed_clock_families(question.universe.sports, question.universe.leagues):
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=[MIXED_CLOCK_REASON],
            unavailable=["mixed_sport_clock"],
        )
    family_chips = _family_chip_errors(question) + _pbp_source_errors(question)
    if family_chips:
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=family_chips,
            unavailable=["family_chip"],
        )
    if any(is_baseball(x) for x in (*question.universe.sports, *question.universe.leagues)):
        if any(
            p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game"
            for p in question.path_conditions
        ):
            return CompileResult(
                status=ResearchStatus.OPERATION_REQUIRED,
                execution_path=ExecutionPath.NONE,
                reference_match=None,
                question=question,
                reasons=[
                    "MLB has no 48-minute game clock. Game-clock horizons are OPERATION_REQUIRED. "
                    "Use Reach or Hold to settlement."
                ],
                unavailable=["horizon_game"],
            )
    from roller.research_query.sport_family import is_tennis

    if any(is_tennis(x) for x in (*question.universe.sports, *question.universe.leagues)):
        if any(
            p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game"
            for p in question.path_conditions
        ):
            return CompileResult(
                status=ResearchStatus.OPERATION_REQUIRED,
                execution_path=ExecutionPath.NONE,
                reference_match=None,
                question=question,
                reasons=[
                    "Tennis has no basketball game clock. Game-clock horizons are OPERATION_REQUIRED. "
                    "Use Reach or Hold to settlement."
                ],
                unavailable=["horizon_game"],
            )
    basis = universe_basis(question.universe)
    if basis is None:
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=[CROSS_VENUE_NO_JOINT_BASIS],
            unavailable=["cross_venue_joint_basis"],
        )
    if basis == BASIS_LAST_TRADE:
        # Restate the thresholds as print events before any capability check,
        # so nothing downstream can read Polymarket as a tradable quote.
        question = question.on_last_trade_basis()
    errors = validate_question(question)
    reasons: list[str] = list(errors)
    draft = draft or {}
    entry_fams = [str(x.get("family") or "") for x in (draft.get("entryConditions") or [])]
    path_fams = [str(x.get("family") or "") for x in (draft.get("exitConditions") or [])]
    bad_ops = draft_unsupported_families(entry_fams, path_fams) + [
        d for d in question.requested_dimensions if d
    ]
    bad_ops.extend(unsupported_operations(question))
    bad_ops.extend(reserved_scope_names(list(question.requested_dimensions)))
    bad_ops.extend(reserved_scope_names(entry_fams + path_fams))
    # unique preserve
    seen: set[str] = set()
    uniq_ops: list[str] = []
    for o in bad_ops:
        if o and o not in seen:
            seen.add(o)
            uniq_ops.append(o)

    gaps = data_gaps(question, cfg=cfg)
    omitted = optional_omissions(question)
    ref = reference_match(question) if not uniq_ops and not gaps else None

    if uniq_ops:
        reasons: list[str] = []
        for name in uniq_ops:
            if name in _HORIZON_FAMS or name == "horizon":
                reasons.append(
                    f"{name} is incomplete (horizon minutes required). "
                    "Game/Market clock is never silently dropped into Reach-only."
                )
            else:
                reasons.append(
                    f"{name} has no approved candle-close definition. "
                    "The system will not invent one. This is not an empty population."
                )
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=reasons,
            unavailable=uniq_ops,
        )
    if gaps:
        return CompileResult(
            status=ResearchStatus.DATA_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=gaps,
            unavailable=list(gaps),
        )
    if errors:
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=errors,
        )
    if not question.entry_conditions:
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=question,
            reasons=["Define a supported entry operation."],
        )
    if omitted and not question.accept_limitations:
        return CompileResult(
            status=ResearchStatus.READY_WITH_LIMITATIONS,
            execution_path=ExecutionPath.GENERIC_QUERY if not ref else ExecutionPath.FROZEN_REFERENCE,
            reference_match=ref,
            question=question,
            reasons=[
                "Optional requested dimensions are unavailable. "
                "Acknowledge omitted_dimensions to run the reduced question."
            ],
            omitted_dimensions=omitted,
            available=list(_basis_available(basis, question.universe)),
        )
    if ref:
        return CompileResult(
            status=ResearchStatus.READY,
            execution_path=ExecutionPath.FROZEN_REFERENCE,
            reference_match=ref,
            question=question,
            available=["warehouse_frozen_v1", ref],
            omitted_dimensions=omitted if question.accept_limitations else [],
        )
    available = [*_basis_available(basis, question.universe), "pbp_snap"]
    if len(question.universe.leagues) > 1:
        available.append("combined_league_union")
    return CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=question,
        available=available,
        omitted_dimensions=omitted if question.accept_limitations else [],
    )


def _entry_identity_errors(draft: dict[str, Any], question: ResearchQuestion) -> list[str]:
    """Fail closed if draft entry families are not preserved on the AST."""
    raws = [
        r
        for r in (draft.get("entryConditions") or draft.get("entry_conditions") or [])
        if str(r.get("family") or "").strip()
    ]
    # Skip clock-only / incomplete rows that question_from_draft also skips.
    mapped: list[tuple[dict[str, Any], str, EntryCondition]] = []
    cond_i = 0
    for raw in raws:
        fam = str(raw.get("family") or "")
        if fam not in TOUCH_FAMILIES and fam not in ENTRY_OP_FAMILIES and fam.upper() not in TouchOrdinal.__members__ and fam.upper() not in EntryOp.__members__:
            continue
        cents = raw.get("priceCents") if raw.get("priceCents") is not None else raw.get("price_cents")
        if (
            cents is None
            and raw.get("price_e4") is None
            and not (raw.get("priceFrom") is not None and raw.get("priceTo") is not None)
            and not (raw.get("price_from") is not None and raw.get("price_to") is not None)
        ):
            continue
        if cond_i >= len(question.entry_conditions):
            return [f"draft entry {fam} missing from compiled AST"]
        mapped.append((raw, fam, question.entry_conditions[cond_i]))
        cond_i += 1
    if cond_i != len(question.entry_conditions):
        return ["compiled entry count does not match draft"]
    errors: list[str] = []
    for raw, fam, cond in mapped:
        if fam in ENTRY_OP_FAMILIES:
            want = ENTRY_OP_FAMILIES[fam]
            if cond.resolved_operation() is not want:
                errors.append(
                    f"draft family {fam} must compile to {want.value}, got {cond.resolved_operation().value}"
                )
        elif fam in TOUCH_FAMILIES:
            want = TOUCH_FAMILIES[fam]
            if cond.ordinal is not want or cond.operation is not None:
                errors.append(
                    f"draft family {fam} must compile to touch {want.value}, got "
                    f"ordinal={cond.ordinal.value} operation={cond.operation}"
                )
        cents = raw.get("priceCents") if raw.get("priceCents") is not None else raw.get("price_cents")
        if cents is not None and cond.price_e4 != cents_to_e4(int(cents)):
            errors.append(
                f"draft priceCents {cents} must compile to {cents_to_e4(int(cents))}, got {cond.price_e4}"
            )
        want_dir = _draft_direction(raw)
        if want_dir != cond.direction:
            errors.append(
                f"draft direction {want_dir} must compile, got {cond.direction}"
            )
        period = raw.get("period")
        if period and not cond.names_period(str(period)):
            errors.append(
                f"draft period {period} must compile onto the entry window, "
                f"got period={cond.period} windows={cond.period_windows}"
            )
        specified, want_clock = _raw_clock_spec(raw)
        if specified and (want_clock is None or not _clock_on_condition(cond, want_clock, period=period)):
            errors.append(
                f"draft clock must compile onto the entry window, "
                f"got period={cond.period} clock={cond.clock} windows={cond.period_windows}"
            )
        for window in raw.get("periodWindows") or raw.get("period_windows") or []:
            if not isinstance(window, dict):
                continue
            wp = window.get("period")
            if wp and not cond.names_period(str(wp)):
                errors.append(
                    f"draft period window {wp} must compile onto the entry window, "
                    f"got period={cond.period} windows={cond.period_windows}"
                )
            win_specified, win_clock = _raw_clock_spec(window)
            if win_specified and (
                win_clock is None or not _clock_on_condition(cond, win_clock, period=wp)
            ):
                errors.append(
                    f"draft period window clock {wp} must compile onto the entry window, "
                    f"got period={cond.period} clock={cond.clock} windows={cond.period_windows}"
                )
    return errors


_PATH_IDENTITY_FAMS = {
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


def _path_identity_errors(draft: dict[str, Any], question: ResearchQuestion) -> list[str]:
    """Fail closed if draft path chips are dropped or rewritten on the AST."""
    raws = [
        r
        for r in (draft.get("exitConditions") or draft.get("path_conditions") or [])
        if str(r.get("family") or "") in _PATH_IDENTITY_FAMS
        and r.get("kind") in (None, "path")
    ]
    ast = [
        p
        for p in question.path_conditions
        if p.op
        in (
            PathOp.REACH,
            PathOp.DROP_TO,
            PathOp.RISE_TO,
            PathOp.RECOVER,
            PathOp.BOUNCE,
            PathOp.REVERT,
            PathOp.MAXIMUM_MOVE,
            PathOp.MINIMUM_MOVE,
            PathOp.NEVER_REACH,
        )
        and p.horizon_kind is None
    ]
    if len(raws) != len(ast):
        return ["compiled path count does not match draft"]
    errors: list[str] = []
    op_map = {
        "reach": PathOp.REACH,
        "drop_to": PathOp.DROP_TO,
        "rise_to": PathOp.RISE_TO,
        "recover": PathOp.RECOVER,
        "bounce": PathOp.BOUNCE,
        "revert": PathOp.REVERT,
        "maximum_move": PathOp.MAXIMUM_MOVE,
        "minimum_move": PathOp.MINIMUM_MOVE,
        "never_reach": PathOp.NEVER_REACH,
    }
    for raw, cond in zip(raws, ast, strict=True):
        fam = str(raw.get("family") or "")
        if cond.op is not op_map[fam]:
            errors.append(f"draft path {fam} must compile to {op_map[fam].value}, got {cond.op.value}")
        cents = raw.get("priceCents") if raw.get("priceCents") is not None else raw.get("price_cents")
        if cents is not None and cond.price_e4 != cents_to_e4(int(cents)):
            errors.append(
                f"draft path priceCents {cents} must compile to {cents_to_e4(int(cents))}, got {cond.price_e4}"
            )
        oc = raw.get("outcome")
        if oc in ("win", "loss") and (cond.outcome is None or cond.outcome.value != oc):
            errors.append(f"draft path outcome {oc} must compile, got {cond.outcome}")
        if bool(raw.get("sequential")) != bool(cond.sequential):
            errors.append(f"draft path sequential must compile, got {cond.sequential}")
    return errors


def _horizon_identity_errors(draft: dict[str, Any], question: ResearchQuestion) -> list[str]:
    """Fail closed if a complete horizon chip is dropped or rewritten."""
    raws = [
        r
        for r in (draft.get("exitConditions") or draft.get("path_conditions") or [])
        if str(r.get("family") or "") in _HORIZON_FAMS
        and (
            r.get("horizonMinutes") is not None
            or r.get("horizon_minutes") is not None
        )
    ]
    ast = [
        p
        for p in question.path_conditions
        if p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS)
    ]
    if len(raws) != len(ast):
        return ["compiled horizon count does not match draft"]
    errors: list[str] = []
    for raw, cond in zip(raws, ast, strict=True):
        fam = str(raw.get("family") or "")
        want_kind, want_op = _HORIZON_FAMS[fam]
        if cond.op is not want_op:
            errors.append(f"draft horizon {fam} must compile to {want_op.value}, got {cond.op.value}")
        kind = str(raw.get("horizonKind") or raw.get("horizon_kind") or want_kind)
        if str(cond.horizon_kind or "") != kind:
            errors.append(f"draft horizon kind {kind} must compile, got {cond.horizon_kind}")
        mins = raw.get("horizonMinutes") if raw.get("horizonMinutes") is not None else raw.get("horizon_minutes")
        if mins is not None and int(cond.horizon_minutes or 0) != int(mins):
            errors.append(f"draft horizon minutes {mins} must compile, got {cond.horizon_minutes}")
        oc = raw.get("outcome")
        if oc in ("win", "loss") and (cond.outcome is None or cond.outcome.value != oc):
            errors.append(f"draft horizon outcome {oc} must compile, got {cond.outcome}")
    return errors


def _hold_identity_errors(draft: dict[str, Any], question: ResearchQuestion) -> list[str]:
    """Fail closed if tagged hold-to-expiration chips are dropped."""
    raws = draft.get("exitConditions") or draft.get("path_conditions") or []
    want_win = False
    want_loss = False
    for raw in raws:
        fam = str(raw.get("family") or "")
        oc = raw.get("outcome")
        if oc is not None and fam in ("hold_expiration_win", "yes"):
            want_win = True
        elif oc is not None and fam in ("hold_expiration_loss", "no"):
            want_loss = True
    errors: list[str] = []
    if want_win and not question.win_hold:
        errors.append("draft hold_expiration_win must compile to win_hold")
    if want_loss and not question.loss_hold:
        errors.append("draft hold_expiration_loss must compile to loss_hold")
    return errors


def _universe_identity_errors(draft: dict[str, Any], question: ResearchQuestion) -> list[str]:
    """Fail closed if Quick Start chips are dropped or rewritten on the AST."""
    u = draft.get("universe") or {}
    errors: list[str] = []
    date_from = u.get("dateFrom") if u.get("dateFrom") is not None else u.get("date_from")
    date_to = u.get("dateTo") if u.get("dateTo") is not None else u.get("date_to")
    if date_from not in (None, "") and str(question.universe.date_from or "") != str(date_from):
        errors.append(
            f"draft dateFrom {date_from} must compile to the same window, "
            f"got {question.universe.date_from}"
        )
    if date_to not in (None, "") and str(question.universe.date_to or "") != str(date_to):
        errors.append(
            f"draft dateTo {date_to} must compile to the same window, "
            f"got {question.universe.date_to}"
        )
    raw_leagues = [str(x) for x in (u.get("leagues") or ()) if x]
    if raw_leagues:
        from roller.research_query.season_mapping import normalize_league

        want: list[str] = []
        for item in raw_leagues:
            try:
                mapped = normalize_league(item)
            except ValueError:
                mapped = item
            if mapped not in want:
                want.append(mapped)
        if tuple(want) != question.universe.leagues:
            errors.append(
                f"draft leagues {want} must compile, got {list(question.universe.leagues)}"
            )
    raw_md = tuple(u.get("marketData") or u.get("market_data") or ())
    if raw_md and raw_md != question.universe.market_data:
        errors.append(
            f"draft marketData {list(raw_md)} must compile, "
            f"got {list(question.universe.market_data)}"
        )
    raw_markets = tuple(u.get("markets") or ())
    if raw_markets and raw_markets != question.universe.markets:
        errors.append(
            f"draft markets {list(raw_markets)} must compile, "
            f"got {list(question.universe.markets)}"
        )
    raw_gd = tuple(u.get("dataSources") or u.get("game_data") or ())
    if raw_gd and raw_gd != question.universe.game_data:
        errors.append(
            f"draft dataSources {list(raw_gd)} must compile, "
            f"got {list(question.universe.game_data)}"
        )
    return errors


def compile_draft(draft: dict[str, Any], *, cfg: RollerConfig | None = None) -> CompileResult:
    q = question_from_draft(draft)
    entry_id = _entry_identity_errors(draft, q)
    universe_id = _universe_identity_errors(draft, q)
    path_id = _path_identity_errors(draft, q)
    horizon_id = _horizon_identity_errors(draft, q)
    hold_id = _hold_identity_errors(draft, q)
    te_id = _te_filter_errors(draft)
    identity = entry_id + universe_id + path_id + horizon_id + hold_id + te_id
    if identity:
        unavailable: list[str] = []
        if entry_id:
            unavailable.append("entry_identity")
        if universe_id:
            unavailable.append("universe_identity")
        if path_id:
            unavailable.append("path_identity")
        if horizon_id:
            unavailable.append("horizon_identity")
        if hold_id:
            unavailable.append("hold_identity")
        if te_id:
            unavailable.append("te_identity")
        return CompileResult(
            status=ResearchStatus.OPERATION_REQUIRED,
            execution_path=ExecutionPath.NONE,
            reference_match=None,
            question=q,
            reasons=identity,
            unavailable=unavailable,
        )
    return compile_question(q, cfg=cfg, draft=draft)
