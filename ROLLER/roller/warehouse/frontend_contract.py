"""Phase 19 frontend ↔ warehouse ResearchQuestion contract.

The UI constructs a ResearchQuestion (or its dict). This module validates
syntax, compiles, and executes the existing warehouse path.

Does not implement CROSS / BREAK / path / settlement / PIT math.
Does not call Confirm & Run execute.py or compiler.py.
Does not invent L2, ticks, fills, or PBP↔candle PIT alignment.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from roller.config import RollerConfig
from roller.research_query.models import (
    ClockWindow,
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    PeriodWindow,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
    max_entry_e4_from_raw,
)
from roller.warehouse.conditional_backtest import (
    BacktestStatus,
    compare_backtest_rows,
    run_conditional_backtest,
)
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    get_catalog,
)
from roller.warehouse.desk import desk_sport
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.research_compiler import COMPILER_VERSION, compile_research

VALID_PERIODS = frozenset(
    {
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "OT",
        "H1",
        "H2",
        "H1_1",
        "H1_2",
        "H2_1",
        "H2_2",
        "P5",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "G1-3",
        "G4-6",
        "G7-9",
        "G10+",
    }
)
MLB_PERIODS = frozenset(
    {f"{side}{n}" for n in range(1, 10) for side in ("T", "B")} | {"TX", "BX", "I7"}
)
PRICE_OPS = frozenset(
    {
        "CROSS",
        "TOUCH",
        "FIRST_TOUCH",
        "SECOND_TOUCH",
        "THIRD_TOUCH",
        "FOURTH_TOUCH",
        "NTH_TOUCH",
        "BREAK",
        "REVERSION",
        "BOUNCE",
        "RECOVERY",
        "ABOVE",
        "BELOW",
        "MAXIMUM_TOUCH",
        "MINIMUM_TOUCH",
    }
)
ENTRY_FAMILY = {
    "first_touch": (TouchOrdinal.FIRST_TOUCH, EntryOp.FIRST_TOUCH),
    "second_touch": (TouchOrdinal.SECOND_TOUCH, EntryOp.SECOND_TOUCH),
    "third_touch": (TouchOrdinal.THIRD_TOUCH, EntryOp.THIRD_TOUCH),
    "fourth_touch": (TouchOrdinal.FOURTH_TOUCH, EntryOp.FOURTH_TOUCH),
    "nth_touch": (TouchOrdinal.NTH_TOUCH, EntryOp.NTH_TOUCH),
    "cross": (TouchOrdinal.FIRST_TOUCH, EntryOp.CROSS),
    "touch": (TouchOrdinal.FIRST_TOUCH, EntryOp.FIRST_TOUCH),
    "break": (TouchOrdinal.FIRST_TOUCH, EntryOp.BREAK),
    "reversion": (TouchOrdinal.FIRST_TOUCH, EntryOp.REVERSION),
    "bounce": (TouchOrdinal.FIRST_TOUCH, EntryOp.BOUNCE),
    "recovery": (TouchOrdinal.FIRST_TOUCH, EntryOp.RECOVERY),
    "above": (TouchOrdinal.FIRST_TOUCH, EntryOp.ABOVE),
    "below": (TouchOrdinal.FIRST_TOUCH, EntryOp.BELOW),
    "maximum_touch": (TouchOrdinal.FIRST_TOUCH, EntryOp.MAXIMUM_TOUCH),
    "minimum_touch": (TouchOrdinal.FIRST_TOUCH, EntryOp.MINIMUM_TOUCH),
}
PATH_FAMILY = {
    "reach": PathOp.REACH,
    "drop": PathOp.DROP_TO,
    "drop_to": PathOp.DROP_TO,
    "rise": PathOp.RISE_TO,
    "rise_to": PathOp.RISE_TO,
    "recover": PathOp.RECOVER,
    "bounce": PathOp.BOUNCE,
    "revert": PathOp.REVERT,
    "maximum_move": PathOp.MAXIMUM_MOVE,
    "minimum_move": PathOp.MINIMUM_MOVE,
    "never_reach": PathOp.NEVER_REACH,
}
HOLD_FAMILIES = frozenset(
    {
        "hold",
        "hold_expiration_win",
        "hold_expiration_loss",
        "yes",
        "no",
        "both",
    }
)
MARKET_DATA_TOKEN = {
    "candles": "candles",
    "candle": "candles",
    "tradable_yes_bid": "candles",
    "1_minute": "candles",
    "1-minute": "candles",
    "last_trade": "last_trade",
    "last_trade_print": "last_trade",
    "tick": "historical_tick",
    "ticks": "historical_tick",
    "historical_tick": "historical_tick",
    "l2": "historical_l2",
    "historical_l2": "historical_l2",
    "orderbook": "orderbook",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _token(value: object) -> str:
    return _text(value).lower().replace(" ", "_").replace("-", "_")


def _season(value: object) -> str:
    raw = _text(value).replace("–", "-").replace("_", "-")
    if raw in {"2025-26", "2025-2026"}:
        return "2025-2026"
    return raw


def _cents_to_e4(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None


def _clock_window(clock_from: object, clock_to: object) -> ClockWindow | None | str:
    a = _text(clock_from)
    b = _text(clock_to)
    if not a and not b:
        return None

    def _secs(raw: str) -> int | None:
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        parts = raw.replace(".", ":").split(":")
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return None

    lo = _secs(a)
    hi = _secs(b)
    if lo is None and a:
        return "invalid_clock"
    if hi is None and b:
        return "invalid_clock"
    if lo is None or hi is None:
        return "invalid_clock"
    return ClockWindow(remaining_from_s=lo, remaining_to_s=hi)


def _period_from_draft(raw: dict[str, Any]) -> tuple[str | None, ClockWindow | None | str, tuple[PeriodWindow, ...], list[str]]:
    """One window stays on period/clock. Two or more windows are OR filters."""
    errors: list[str] = []
    raw_windows = raw.get("periodWindows") or raw.get("period_windows") or []
    windows: list[PeriodWindow] = []
    for item in raw_windows:
        if not isinstance(item, dict):
            continue
        clock_raw = item.get("clock")
        if isinstance(clock_raw, dict) and "remaining_from_s" in clock_raw:
            clock = ClockWindow.from_dict(clock_raw)
        else:
            clock = _clock_window(
                item.get("clockFrom") or item.get("clock_from"),
                item.get("clockTo") or item.get("clock_to"),
            )
        if clock == "invalid_clock":
            errors.append("invalid_clock")
            clock = None
        period = _text(item.get("period")).upper() or None
        if period and period not in VALID_PERIODS | MLB_PERIODS:
            errors.append("invalid_period")
        windows.append(PeriodWindow(period=period, clock=clock if isinstance(clock, ClockWindow) else None))
    period = _text(raw.get("period")).upper() or None
    clock = _clock_window(raw.get("clockFrom") or raw.get("clock_from"), raw.get("clockTo") or raw.get("clock_to"))
    if len(windows) > 1:
        return None, None, tuple(windows), errors
    if len(windows) == 1:
        return windows[0].period, windows[0].clock, (), errors
    return period, clock, (), errors


def exposure_from_body(body: dict[str, Any] | None) -> dict[str, Any] | None:
    """Read explicit exposure request. Never infers strategy_enforced from sport."""
    from roller.exposure_contract import (
        MODE_STRATEGY_ENFORCED,
        enforcement_request_from_draft,
        normalize_enforcement_mode,
    )

    if not isinstance(body, dict):
        return None
    draft = body.get("draft") if isinstance(body.get("draft"), dict) else {}
    merged = {**draft, **body}
    mode, unit, cap = enforcement_request_from_draft(merged)
    if mode != MODE_STRATEGY_ENFORCED and not unit and cap is None:
        return None
    return {
        "enforcement_mode": normalize_enforcement_mode(mode),
        "exposure_unit": unit or "GAME",
        "max_entries_per_unit": cap if cap is not None else 1,
    }


def te_filters_from_body(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    raw = body.get("te_filters") or body.get("teFilters")
    if isinstance(raw, dict):
        return raw
    draft = body.get("draft")
    if isinstance(draft, dict):
        nested = draft.get("teFilters") or draft.get("te_filters")
        if isinstance(nested, dict):
            return nested
    question = body.get("question")
    if isinstance(question, dict):
        nested = question.get("te_filters") or question.get("teFilters")
        if isinstance(nested, dict):
            return nested
    return None


def syntactic_errors(question: ResearchQuestion) -> list[str]:
    errors: list[str] = []
    uni = question.universe
    if uni.date_from and uni.date_to and uni.date_from > uni.date_to:
        errors.append("malformed_date_range")
    if not question.entry_conditions:
        errors.append("missing_entry")
    for entry in question.entry_conditions:
        op = entry.resolved_operation().value
        if op in PRICE_OPS and int(entry.price_e4 or 0) <= 0:
            errors.append("missing_threshold")
        period = _text(entry.period).upper()
        if period and period not in VALID_PERIODS | MLB_PERIODS:
            errors.append("invalid_period")
        for window in entry.period_windows:
            wperiod = _text(window.period).upper()
            if wperiod and wperiod not in VALID_PERIODS | MLB_PERIODS:
                errors.append("invalid_period")
        if entry.max_entry_e4 is not None and entry.max_entry_e4 < int(entry.price_e4):
            errors.append("invalid_max_entry")
    has_win = question.win_hold or any(p.outcome is ExitOutcome.WIN for p in question.path_conditions)
    has_loss = question.loss_hold or any(p.outcome is ExitOutcome.LOSS for p in question.path_conditions)
    if not has_win:
        errors.append("missing_win_exit")
    if not has_loss:
        errors.append("missing_loss_exit")
    return list(dict.fromkeys(errors))


def _canonical_nba_universe(
    sports: tuple[str, ...], leagues: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Map the existing UI chip (sport=basketball, league=NBA) onto warehouse NBA."""
    if "MLB" in leagues or "MLB" in sports or "BASEBALL" in sports:
        rest_sports = tuple(s for s in sports if s not in {"MLB", "BASEBALL"})
        rest_leagues = tuple(s for s in leagues if s not in {"MLB", "BASEBALL"})
        return ("MLB",) + rest_sports, ("MLB",) + rest_leagues
    atp = "ATP" in leagues or "ATP" in sports
    wta = "WTA" in leagues or "WTA" in sports
    if atp and not wta:
        rest_sports = tuple(s for s in sports if s not in {"ATP", "TENNIS"})
        rest_leagues = tuple(s for s in leagues if s not in {"ATP", "TENNIS"})
        return ("ATP",) + rest_sports, ("ATP",) + rest_leagues
    if wta and not atp:
        rest_sports = tuple(s for s in sports if s not in {"WTA", "TENNIS"})
        rest_leagues = tuple(s for s in leagues if s not in {"WTA", "TENNIS"})
        return ("WTA",) + rest_sports, ("WTA",) + rest_leagues
    ncaab = "NCAAB" in leagues or "NCAAB" in sports
    nba = "NBA" in leagues or "NBA" in sports
    if ncaab and not nba:
        rest_sports = tuple(s for s in sports if s not in {"NCAAB", "BASKETBALL"})
        rest_leagues = tuple(s for s in leagues if s not in {"NCAAB", "BASKETBALL"})
        return ("NCAAB",) + rest_sports, ("NCAAB",) + rest_leagues
    if nba and not ncaab:
        rest_sports = tuple(s for s in sports if s not in {"NBA", "BASKETBALL"})
        rest_leagues = tuple(s for s in leagues if s not in {"NBA", "BASKETBALL"})
        return ("NBA",) + rest_sports, ("NBA",) + rest_leagues
    return sports, leagues


def question_from_draft(draft: dict[str, Any]) -> tuple[ResearchQuestion | None, list[str]]:
    """Map a WorkflowDraft-shaped dict onto ResearchQuestion. Serialization only."""
    errors: list[str] = []
    uni_raw = draft.get("universe") or {}
    sports, leagues = _canonical_nba_universe(
        tuple(_text(s).upper() for s in (uni_raw.get("sports") or []) if _text(s)),
        tuple(_text(s).upper() for s in (uni_raw.get("leagues") or []) if _text(s)),
    )
    seasons = tuple(_season(s) for s in (uni_raw.get("seasons") or []) if _text(s))
    markets = tuple(_token(m) for m in (uni_raw.get("markets") or []) if _text(m))
    raw_md = [_token(m) for m in (uni_raw.get("marketData") or uni_raw.get("market_data") or [])]
    market_data = tuple(MARKET_DATA_TOKEN.get(m, m) for m in raw_md if m)
    game_data = tuple(
        _token(g) for g in (uni_raw.get("gameData") or uni_raw.get("game_data") or []) if _text(g)
    )
    date_from = _text(uni_raw.get("dateFrom") or uni_raw.get("date_from"))[:10] or None
    date_to = _text(uni_raw.get("dateTo") or uni_raw.get("date_to"))[:10] or None

    entries: list[EntryCondition] = []
    needs_pbp = False
    for raw in draft.get("entryConditions") or draft.get("entry_conditions") or []:
        if not isinstance(raw, dict):
            continue
        fam = _token(raw.get("family") or raw.get("operation") or "")
        mapped = ENTRY_FAMILY.get(fam)
        if mapped is None:
            errors.append("invalid_entry")
            continue
        ordinal, op = mapped
        price = raw.get("price_e4")
        if price is None:
            price = _cents_to_e4(raw.get("priceCents") if "priceCents" in raw else raw.get("price_cents"))
        if price is None:
            errors.append("missing_threshold")
            price = 0
        period, clock, period_windows, period_errors = _period_from_draft(raw)
        errors.extend(period_errors)
        if period and period not in VALID_PERIODS | MLB_PERIODS:
            errors.append("invalid_period")
        if clock == "invalid_clock":
            errors.append("invalid_clock")
            clock = None
        nth = raw.get("touchNValue") or raw.get("nth")
        if ordinal is TouchOrdinal.NTH_TOUCH:
            try:
                nth = int(nth) if nth not in (None, "N") else None
            except (TypeError, ValueError):
                nth = None
            if nth is None:
                errors.append("missing_threshold")
        if period or clock or period_windows:
            needs_pbp = True
        ceiling = max_entry_e4_from_raw(raw)
        if ceiling is not None and ceiling < int(price):
            errors.append("invalid_max_entry")
        entries.append(
            EntryCondition(
                id=_text(raw.get("id")) or f"e{len(entries) + 1}",
                ordinal=ordinal,
                price_e4=int(price),
                period=period,
                clock=clock if isinstance(clock, ClockWindow) else None,
                period_windows=period_windows,
                nth=int(nth) if nth not in (None, "N") else None,
                operation=op,
                direction=_text(raw.get("direction")) or None,
                max_entry_e4=ceiling,
            )
        )

    paths: list[PathCondition] = []
    win_hold = False
    loss_hold = False
    terminal = TerminalOutcome.BOTH
    dims: list[str] = []
    for raw in draft.get("exitConditions") or draft.get("exit_conditions") or []:
        if not isinstance(raw, dict):
            continue
        fam = _token(raw.get("family") or raw.get("op") or "")
        outcome_raw = _token(raw.get("outcome") or "")
        if fam in {"yes"}:
            terminal = TerminalOutcome.YES
            win_hold = True
            continue
        if fam in {"no"}:
            terminal = TerminalOutcome.NO
            loss_hold = True
            continue
        if fam in {"both", "hold"} or fam.startswith("hold_expiration"):
            dims.append("HOLD_TO_SETTLEMENT")
            if fam.endswith("win") or outcome_raw == "win":
                win_hold = True
            elif fam.endswith("loss") or outcome_raw == "loss":
                loss_hold = True
            else:
                win_hold = True
                loss_hold = True
            continue
        if fam == "clock":
            errors.append("invalid_clock")
            continue
        op = PATH_FAMILY.get(fam)
        if op is None:
            errors.append("missing_exit")
            continue
        price = raw.get("price_e4")
        if price is None:
            price = _cents_to_e4(raw.get("priceCents") if "priceCents" in raw else raw.get("price_cents"))
        if price is None:
            errors.append("missing_exit")
            continue
        outcome = ExitOutcome.WIN if outcome_raw == "win" else ExitOutcome.LOSS if outcome_raw == "loss" else None
        if outcome is None:
            outcome = ExitOutcome.WIN if not any(p.outcome is ExitOutcome.WIN for p in paths) else ExitOutcome.LOSS
        paths.append(
            PathCondition(
                id=_text(raw.get("id")) or f"{'win' if outcome is ExitOutcome.WIN else 'loss'}",
                op=op,
                price_e4=int(price),
                sequential=bool(raw.get("sequential")),
                outcome=outcome,
            )
        )

    extra_dims = draft.get("requested_dimensions") or draft.get("requestedDimensions") or []
    for dim in extra_dims:
        token = _text(dim).upper().replace(" ", "_").replace("↔", "_").replace("-", "_")
        if token:
            dims.append(token)
    te_raw = draft.get("teFilters") or draft.get("te_filters")
    if isinstance(te_raw, dict):
        from roller.research_query.hashing import normalize_state_filters

        if normalize_state_filters(te_raw):
            needs_pbp = True
    if needs_pbp and "pbp" not in game_data:
        game_data = (*game_data, "pbp")
    if not dims:
        dims.append("HOLD_TO_SETTLEMENT")

    if date_from and date_to and date_from > date_to:
        errors.append("malformed_date_range")
    if not entries:
        errors.append("missing_entry")
    if not any(p.outcome is ExitOutcome.WIN for p in paths) and not win_hold:
        errors.append("missing_win_exit")
    if not any(p.outcome is ExitOutcome.LOSS for p in paths) and not loss_hold:
        errors.append("missing_loss_exit")

    question = ResearchQuestion(
        universe=Universe(
            sports=sports,
            leagues=leagues or sports,
            seasons=seasons,
            markets=markets or ("kalshi",),
            market_data=market_data or ("candles",),
            game_data=game_data,
            date_from=date_from,
            date_to=date_to,
        ),
        entry_conditions=tuple(entries),
        path_conditions=tuple(paths),
        terminal=terminal,
        requested_dimensions=tuple(dict.fromkeys(dims)),
        accept_limitations=bool(draft.get("accept_limitations") or draft.get("acceptLimitations")),
        win_hold=win_hold,
        loss_hold=loss_hold,
    )
    return question, list(dict.fromkeys(errors))


def question_from_payload(body: dict[str, Any]) -> tuple[ResearchQuestion | None, list[str]]:
    if body.get("question"):
        raw = dict(body["question"])
        try:
            question = ResearchQuestion.from_dict(raw)
        except (KeyError, ValueError, TypeError) as exc:
            return None, [f"invalid_question:{exc}"]
        return question, syntactic_errors(question)
    if body.get("draft"):
        return question_from_draft(dict(body["draft"]))
    return None, ["missing_question"]


def _row_class(row: Any) -> str:
    return _text(getattr(row, "classification", "") or (row.get("classification") if isinstance(row, dict) else "")).upper()


def _row_settlement(row: Any) -> str:
    return _text(
        getattr(row, "settlement_status", "") or (row.get("settlement_status") if isinstance(row, dict) else "")
    ).upper()


# Binary Kalshi settlement in e4. Hold-YES / hold-NO have no path price.
SETTLEMENT_YES_E4 = 10000
SETTLEMENT_NO_E4 = 0


def _hold_exit(plan: Any, outcome: str) -> bool:
    return any(
        _token(getattr(item, "op", None)) == "hold" and _token(getattr(item, "outcome", None)) == outcome
        for item in getattr(plan, "exits", ()) or ()
    )


def _is_win_hold(question: Any | None, plan: Any | None = None) -> bool:
    if question is not None and bool(getattr(question, "win_hold", False)):
        return True
    return bool(plan is not None and _hold_exit(plan, "win"))


def _is_loss_hold(question: Any | None, plan: Any | None = None) -> bool:
    if question is not None and bool(getattr(question, "loss_hold", False)):
        return True
    return bool(plan is not None and _hold_exit(plan, "loss"))


def _plan_trade_prices(plan: Any, question: Any | None) -> tuple[int | None, int | None, int | None]:
    entry = int(plan.entries[0].price_e4) if plan.entries else None
    win_exit = next((int(x.price_e4) for x in plan.exits if _token(x.outcome) == "win" and x.price_e4 is not None), None)
    loss_exit = next((int(x.price_e4) for x in plan.exits if _token(x.outcome) == "loss" and x.price_e4 is not None), None)
    if win_exit is None and _is_win_hold(question, plan):
        win_exit = SETTLEMENT_YES_E4
    if loss_exit is None and _is_loss_hold(question, plan):
        loss_exit = SETTLEMENT_NO_E4
    return entry, win_exit, loss_exit


def _trade_ev_e4(
    *,
    n: int,
    books: dict[str, int],
    entry: int | None,
    win_exit: int | None,
    loss_exit: int | None,
) -> float | None:
    if not n or entry is None:
        return None
    total = 0
    counted = False
    path_win = int(books["path_win_n"])
    terminal_win = int(books["terminal_win_n"])
    path_loss = int(books["path_loss_n"])
    terminal_loss = int(books["terminal_loss_n"])
    if path_win:
        if win_exit is None:
            return None
        total += path_win * (win_exit - entry)
        counted = True
    if terminal_win:
        total += terminal_win * (SETTLEMENT_YES_E4 - entry)
        counted = True
    if path_loss:
        if loss_exit is None:
            return None
        total -= path_loss * (entry - loss_exit)
        counted = True
    if terminal_loss:
        total -= terminal_loss * (entry - SETTLEMENT_NO_E4)
        counted = True
    if not counted:
        return None
    return total / n


def _settlement_books(result: Any, question: Any | None, plan: Any | None = None) -> dict[str, int]:
    rows = list(getattr(result, "rows", None) or [])
    win_hold = _is_win_hold(question, plan)
    path_win = 0
    path_loss = 0
    held_yes = 0
    held_no = 0
    held_missing = 0
    unresolved = 0
    official_yes = 0
    official_no = 0
    for row in rows:
        klass = _row_class(row)
        status = _row_settlement(row)
        if status == "YES":
            official_yes += 1
        elif status == "NO":
            official_no += 1
        if klass == "WIN":
            path_win += 1
            continue
        if klass == "LOSS":
            path_loss += 1
            continue
        if klass == "HELD_TO_SETTLEMENT":
            if status == "YES":
                held_yes += 1
            elif status == "NO":
                held_no += 1
            else:
                held_missing += 1
                unresolved += 1
            continue
        if klass in {"MISSING_SETTLEMENT", "INVALID_SETTLEMENT"}:
            unresolved += 1
    terminal_win = held_yes if win_hold else 0
    terminal_loss = held_no if win_hold else 0
    return {
        "path_win_n": path_win,
        "path_loss_n": path_loss,
        "terminal_win_n": terminal_win,
        "terminal_loss_n": terminal_loss,
        "unresolved_n": unresolved,
        "held_yes_n": held_yes,
        "held_no_n": held_no,
        "held_missing_n": held_missing,
        "official_w_n": official_yes,
        "official_l_n": official_no,
    }


def _statistics(plan: Any, result: Any, question: Any | None = None) -> dict[str, Any]:
    n = int(result.population)
    books = _settlement_books(result, question, plan)
    wins = int(books["path_win_n"] + books["terminal_win_n"])
    losses = int(books["path_loss_n"] + books["terminal_loss_n"])
    classified = wins + losses
    entry, win_exit, loss_exit = _plan_trade_prices(plan, question)
    reward = (win_exit - entry) if entry is not None and win_exit is not None else None
    risk = (entry - loss_exit) if entry is not None and loss_exit is not None else None
    rr = (reward / risk) if reward is not None and risk not in (None, 0) else None
    last_trade = str(getattr(result, "observation_basis", "") or getattr(plan, "observation_basis", "")).upper() == "LAST_TRADE_PRINT"
    ev = None if last_trade else _trade_ev_e4(
        n=n, books=books, entry=entry, win_exit=win_exit, loss_exit=loss_exit
    )
    win_hold = _is_win_hold(question, plan)
    trade_mean = None
    if win_exit is not None and loss_exit is not None:
        ratios: list[float] = []
        for row in getattr(result, "rows", None) or []:
            observed_entry = getattr(row, "entry_value", None)
            if observed_entry in (None, 0):
                continue
            try:
                observed = int(observed_entry)
            except (TypeError, ValueError):
                continue
            row_risk = observed - int(loss_exit)
            if row_risk <= 0:
                continue
            ratios.append((int(win_exit) - observed) / row_risk)
        if ratios:
            trade_mean = sum(ratios) / len(ratios)
    return {
        "population": n,
        "W": wins,
        "L": losses,
        "classified_n": classified,
        "unresolved_n": books["unresolved_n"],
        "path_win_n": books["path_win_n"],
        "path_loss_n": books["path_loss_n"],
        "terminal_win_n": books["terminal_win_n"],
        "terminal_loss_n": books["terminal_loss_n"],
        "official_w_n": books["official_w_n"],
        "official_l_n": books["official_l_n"],
        "official_w_rate": (books["official_w_n"] / n) if n else None,
        "win_rate": (wins / n) if n else None,
        "loss_rate": (losses / n) if n else None,
        "reward_e4": reward,
        "risk_e4": risk,
        "rr": rr,
        "rr_trade_mean": trade_mean,
        "ev_e4": ev,
        "ev_status": "DATA_REQUIRED" if last_trade else ("READY" if ev is not None else "UNAVAILABLE"),
        "unit": "cents_e4",
        "basis": "observed_last_trade_print_path" if last_trade else "observed_candle_path",
        "not": [
            "live_trading_performance",
            "fill",
            "maker_fill",
            "slippage",
            "pnl",
        ],
        "assumption": (
            "Last-trade print path. Not a fill. EV withheld."
            if last_trade
            else (
                "Candle-path observation on TRADABLE_YES_BID. W/L is the trade "
                "(path exit + hold-YES at 100¢ settlement). Not an executable fill."
                if win_hold
                else "Candle-path observation on TRADABLE_YES_BID. W/L is the trade. Not an executable fill."
            )
        ),
    }


def _te_scope_payload(result: Any, te_filters: dict[str, Any] | None) -> dict[str, Any]:
    from roller.research_query.hashing import normalize_state_filters

    requested = normalize_state_filters(te_filters)
    dropped = int((result.exclusions or {}).get("te_scope") or 0)
    n_scoped = int(result.population)
    return {
        "requested": requested,
        "n_entry": n_scoped + dropped,
        "n_scoped": n_scoped,
        "n_dropped": dropped,
    }


def _ensure_pbp_for_filters(question: ResearchQuestion, te_filters: dict[str, Any] | None) -> ResearchQuestion:
    from roller.research_query.hashing import normalize_state_filters

    needs = bool(any(e.has_period_or_clock() for e in question.entry_conditions))
    if normalize_state_filters(te_filters):
        needs = True
    if not needs:
        return question
    if "pbp" in {_token(g) for g in question.universe.game_data}:
        return question
    return replace(question, universe=replace(question.universe, game_data=(*question.universe.game_data, "pbp")))


def _exposure_verify(result: Any, body: dict[str, Any] | None = None) -> dict[str, Any]:
    from roller.results_math.exposure import verify_exposure

    rows = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in (getattr(result, "rows", None) or [])]
    declared: dict[str, Any] = {"exposure_unit": "GAME", "max_entries_per_unit": 1}
    raw = body or {}
    draft = raw.get("draft") if isinstance(raw.get("draft"), dict) else {}
    unit = raw.get("exposure_unit") or raw.get("exposureUnit") or draft.get("exposure_unit") or draft.get("exposureUnit")
    cap = (
        raw.get("max_entries_per_unit")
        or raw.get("maxEntriesPerUnit")
        or raw.get("max_entries_per_game")
        or draft.get("max_entries_per_unit")
        or draft.get("maxEntriesPerGame")
    )
    if unit:
        declared["exposure_unit"] = unit
    if cap not in (None, ""):
        try:
            declared["max_entries_per_unit"] = int(cap)
        except (TypeError, ValueError):
            pass
    return verify_exposure(rows=rows, n=int(result.population), result=declared)


def results_contract(
    question: ResearchQuestion,
    plan: Any,
    result: Any,
    *,
    catalog: Any | None = None,
    te_filters: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = _statistics(plan, result, question)
    coverage = dict(result.coverage or {})
    exclusions = dict(result.exclusions or {})
    books = _settlement_books(result, question, plan)
    te_scope = _te_scope_payload(result, te_filters)
    exposure_view = exposure if exposure is not None else _exposure_verify(result, body)
    requested = exposure_from_body(body)
    from roller.exposure_contract import MODE_STRATEGY_ENFORCED, POLICY_FIRST_CHRONO, normalize_enforcement_mode

    mode = normalize_enforcement_mode((requested or {}).get("enforcement_mode"))
    enforced = mode == MODE_STRATEGY_ENFORCED
    exposure_view = {
        **exposure_view,
        "enforcement_mode": mode,
        "execution_enforced": enforced,
        "selection_policy": POLICY_FIRST_CHRONO if enforced else None,
        "n_unchanged": not enforced,
    }
    return {
        "research_question": question.to_dict(),
        "plan_hash": plan.plan_hash,
        "compiler_version": plan.compiler_version,
        "warehouse_version": result.warehouse_version or plan.warehouse_version,
        "identity_version": getattr(catalog, "identity_version", IDENTITY_RULE_VERSION) if catalog else IDENTITY_RULE_VERSION,
        "catalog_version": plan.catalog_version,
        "observation_basis": result.observation_basis or OBS_BASIS,
        "resolution": OBS_RESOLUTION,
        "pit_field": result.pit_field or PIT_FIELD,
        "entry": [e.to_dict() for e in plan.entries],
        "win_exit": [x.to_dict() for x in plan.exits if _token(x.outcome) == "win"],
        "loss_exit": [x.to_dict() for x in plan.exits if _token(x.outcome) == "loss"],
        "terminal": plan.terminal.value,
        "win_hold": _is_win_hold(question, plan),
        "loss_hold": _is_loss_hold(question, plan),
        "population": result.population,
        "classification": dict(sorted(result.classification_counts.items())),
        "settlement_crosstab": {
            "held_yes": books["held_yes_n"],
            "held_no": books["held_no_n"],
            "held_missing": books["held_missing_n"],
            "path_win": books["path_win_n"],
            "path_loss": books["path_loss_n"],
            "terminal_win": books["terminal_win_n"],
            "terminal_loss": books["terminal_loss_n"],
            "unresolved": books["unresolved_n"],
            "official_w": books["official_w_n"],
            "official_l": books["official_l_n"],
        },
        "statistics": stats,
        "te_scope": te_scope,
        "exposure": exposure_view,
        "coverage": {
            "nominal_universe": {
                "games": (catalog.games if catalog else {}).get("game_count") if catalog else coverage.get("games"),
                "markets": (catalog.markets if catalog else {}).get("market_count") if catalog else coverage.get("markets"),
            },
            "executed_population": result.population,
            "exclusions": exclusions,
            "missing_data": list(plan.missing_data),
            "unsupported_operations": list(plan.missing_operations),
            "context": coverage,
        },
        "exclusions": exclusions,
        "audit_rows": [r.to_dict() for r in result.rows],
        "reproducibility": {
            "plan_hash": result.plan_hash,
            "result_hash": result.result_hash,
            "warehouse_version": result.warehouse_version,
            "observation_basis": result.observation_basis,
            "resolution": OBS_RESOLUTION,
            "pit_field": result.pit_field,
            "compiler_version": COMPILER_VERSION,
            "catalog_version": CATALOG_VERSION,
            "execution_version": result.engine_version,
            "engine_id": result.engine_id,
            "te_scope": te_scope,
        },
        "label": (
            "observed last-trade print research result"
            if str(result.observation_basis or plan.observation_basis).upper() == "LAST_TRADE_PRINT"
            else "observed candle-path research result"
        ),
    }


def compile_frontend_research(body: dict[str, Any], cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    question, errors = question_from_payload(body)
    if question is None:
        return {
            "status": "INVALID",
            "syntactic_errors": errors,
            "source": "warehouse_research",
        }
    from roller.warehouse.production import sport_lock_payload, unavailable_production_sport

    blocked = unavailable_production_sport(question)
    if blocked:
        return sport_lock_payload(question, errors, blocked)
    te_filters = te_filters_from_body(body)
    question = _ensure_pbp_for_filters(question, te_filters)
    plan = compile_research(question, cfg)
    catalog_sport = desk_sport(question) or "NBA"
    try:
        catalog = get_catalog(cfg, sport=catalog_sport)
    except (OSError, ValueError, FileNotFoundError):
        catalog = None
    status = plan.status.value
    if errors and status == ResearchStatus.READY.value:
        status = "INVALID"
    return {
        "status": status,
        "syntactic_errors": errors,
        "question": question.to_dict(),
        "plan": plan.to_dict(),
        "plan_hash": plan.plan_hash,
        "capability": {
            "status": plan.status.value,
            "required": list(plan.required_capabilities),
            "satisfied": list(plan.satisfied_capabilities),
            "missing_data": list(plan.missing_data),
            "missing_operations": list(plan.missing_operations),
            "matrix": catalog.capability_matrix() if catalog is not None else {},
        },
        "observation_basis": plan.observation_basis,
        "resolution": plan.resolution,
        "pit_field": plan.pit_requirement,
        "compiler_version": plan.compiler_version,
        "warehouse_version": plan.warehouse_version,
        "catalog_version": plan.catalog_version,
        "identity_version": catalog.identity_version if catalog is not None else IDENTITY_RULE_VERSION,
        "source": "warehouse_research",
        "te_filters": te_filters,
    }


def execute_frontend_research(
    body: dict[str, Any],
    cfg: RollerConfig | None = None,
    *,
    engine_id: str = "optimized",
    include_reference: bool = False,
) -> dict[str, Any]:
    compiled = compile_frontend_research(body, cfg)
    if compiled.get("status") in {"INVALID", "DATA_REQUIRED", "OPERATION_REQUIRED"}:
        return {
            **compiled,
            "result": None,
            "results_contract": None,
        }
    cfg = cfg or RollerConfig()
    question, _errors = question_from_payload(body)
    assert question is not None
    te_filters = te_filters_from_body(body)
    exposure = exposure_from_body(body)
    question = _ensure_pbp_for_filters(question, te_filters)
    result = run_conditional_backtest(
        question, cfg, engine_id=engine_id, te_filters=te_filters, exposure=exposure
    )
    plan = compile_research(question, cfg)
    catalog_sport = desk_sport(question) or "NBA"
    try:
        catalog = get_catalog(cfg, sport=catalog_sport)
    except (OSError, ValueError, FileNotFoundError):
        catalog = None
    contract = results_contract(question, plan, result, catalog=catalog, te_filters=te_filters, body=body)
    payload: dict[str, Any] = {
        **compiled,
        "status": result.status.value,
        "result": {**result.to_dict(), "result_hash": result.result_hash},
        "results_contract": contract,
    }
    if include_reference:
        ref = run_conditional_backtest(
            question, cfg, engine_id="reference", te_filters=te_filters, exposure=exposure
        )
        opt = result if engine_id == "optimized" else run_conditional_backtest(
            question, cfg, engine_id="optimized", te_filters=te_filters, exposure=exposure
        )
        diffs = compare_backtest_rows(ref, opt)
        payload["reference"] = {**ref.to_dict(), "result_hash": ref.result_hash}
        payload["optimized"] = {**opt.to_dict(), "result_hash": opt.result_hash}
        payload["difference_count"] = len(diffs)
        payload["differences"] = diffs
    return payload


def is_zero_results(payload: dict[str, Any]) -> bool:
    return payload.get("status") == BacktestStatus.ZERO_RESULTS.value
