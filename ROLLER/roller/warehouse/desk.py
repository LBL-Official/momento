"""Shared warehouse-desk helpers. NBA, MLB, NCAAB, ATP, and WTA.

LAST_TRADE_PRINT is not TRADABLE_YES_BID.
Basketball+NCAAB is NCAAB. Basketball+NBA is NBA.
ATP-only is ATP. WTA-only is WTA. Mixed ATP+WTA fail closed.
Tennis with no tour fails closed. Mixed desks fail closed.
"""

from __future__ import annotations

from typing import Any, Iterable

from roller.research_query.models import ResearchQuestion, Universe

DESK_SPORTS = frozenset({"NBA", "MLB", "NCAAB", "ATP", "WTA"})
DEFAULT_SEASON = "2025-2026"
BASKETBALL_PERIODS = frozenset({"Q1", "Q2", "Q3", "Q4", "OT", "H1", "H2"})
MLB_INNING_PERIODS = frozenset(
    {f"{side}{n}" for n in range(1, 10) for side in ("T", "B")} | {"TX", "BX", "I7"}
)
TENNIS_PERIODS = frozenset({"S1", "S2", "S3", "S4", "S5", "G1-3", "G4-6", "G7-9", "G10+"})
TENNIS_FOREIGN_PERIODS = BASKETBALL_PERIODS | MLB_INNING_PERIODS | frozenset({"P5"})
LAST_TRADE_TOKENS = frozenset({"LAST_TRADE", "LAST_TRADE_PRINT"})
TRADABLE_TOKENS = frozenset(
    {
        "CANDLES",
        "CANDLE",
        "TRADABLE_YES_BID",
        "1_MINUTE",
        "1-MINUTE",
        "1_MINUTE_CANDLE",
    }
)


def _token(value: object) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("↔", "_").replace("-", "_")


def desk_sport_from_tokens(sports: Iterable[str], leagues: Iterable[str]) -> str | None:
    """Return a single desk sport. Mixed desks or tennis-without-tour → None."""
    tokens = {_token(s) for s in (*sports, *leagues) if _token(s)}
    tokens -= {"KALSHI", "CANDLES", "LAST_TRADE", "LAST_TRADE_PRINT", "TENNIS"}
    mlb = bool(tokens & {"MLB", "BASEBALL"})
    ncaab = bool(tokens & {"NCAAB"})
    nba = bool(tokens & {"NBA"}) or (bool(tokens & {"BASKETBALL"}) and not ncaab)
    atp = bool(tokens & {"ATP"})
    wta = bool(tokens & {"WTA"})
    extra = tokens - {"MLB", "BASEBALL", "NBA", "BASKETBALL", "NCAAB", "ATP", "WTA"}
    selected = [
        name
        for name, flag in (("MLB", mlb), ("NCAAB", ncaab), ("NBA", nba), ("ATP", atp), ("WTA", wta))
        if flag
    ]
    if extra or len(selected) != 1:
        return None
    return selected[0]


def desk_lab_folder(
    question: ResearchQuestion | Universe | dict[str, Any] | None,
    requested: str | None = None,
) -> str:
    """Labs folder for a desk. Stale NBA default must not swallow other desks."""
    inferred = desk_sport(question) or "NBA"
    req = str(requested or "").strip()
    if not req:
        return inferred
    if req.upper() == "NBA" and inferred in {"NCAAB", "MLB", "ATP", "WTA"}:
        return inferred
    return req


def desk_sport(question: ResearchQuestion | Universe | dict[str, Any] | None) -> str | None:
    if question is None:
        return None
    if isinstance(question, Universe):
        return desk_sport_from_tokens(question.sports, question.leagues)
    if isinstance(question, ResearchQuestion):
        return desk_sport_from_tokens(question.universe.sports, question.universe.leagues)
    if isinstance(question, dict):
        uni = question.get("universe") if isinstance(question.get("universe"), dict) else question
        sports = uni.get("sports") or ()
        leagues = uni.get("leagues") or ()
        return desk_sport_from_tokens(sports, leagues)
    return None


def observation_basis_for(question: ResearchQuestion) -> str:
    md = {_token(x) for x in question.universe.market_data}
    if md & LAST_TRADE_TOKENS:
        return "LAST_TRADE_PRINT"
    return "TRADABLE_YES_BID"


def basis_dir_name(basis: str) -> str:
    token = _token(basis)
    if token == "LAST_TRADE_PRINT":
        return "basis=last_trade_print"
    return "basis=tradable_yes_bid"


def mlb_basketball_period_or_clock(question: ResearchQuestion) -> tuple[str, ...]:
    """Basketball clock chips on an MLB question are OPERATION_REQUIRED."""
    ops: list[str] = []
    for entry in question.entry_conditions:
        period = _token(entry.period)
        if period and period in BASKETBALL_PERIODS:
            ops.append("MLB_BASKETBALL_PERIOD")
        if entry.clock is not None:
            ops.append("MLB_GAME_CLOCK")
        for window in getattr(entry, "period_windows", ()) or ():
            w_period = _token(getattr(window, "period", None))
            if w_period in BASKETBALL_PERIODS:
                ops.append("MLB_BASKETBALL_PERIOD")
            if getattr(window, "clock", None) is not None:
                ops.append("MLB_GAME_CLOCK")
    for path in question.path_conditions:
        kind = _token(getattr(path, "horizon_kind", None))
        if kind in {"CLOCK", "GAME", "GAME_CLOCK"}:
            ops.append("MLB_GAME_CLOCK")
    return tuple(dict.fromkeys(ops))


def tennis_foreign_period_or_clock(question: ResearchQuestion) -> tuple[str, ...]:
    """Basketball / MLB clock chips on a tennis question are OPERATION_REQUIRED."""
    ops: list[str] = []
    for entry in question.entry_conditions:
        period = _token(entry.period)
        if period and period in TENNIS_FOREIGN_PERIODS:
            ops.append("TENNIS_FOREIGN_PERIOD")
        if entry.clock is not None:
            ops.append("TENNIS_GAME_CLOCK")
        for window in getattr(entry, "period_windows", ()) or ():
            w_period = _token(getattr(window, "period", None))
            if w_period in TENNIS_FOREIGN_PERIODS:
                ops.append("TENNIS_FOREIGN_PERIOD")
            if getattr(window, "clock", None) is not None:
                ops.append("TENNIS_GAME_CLOCK")
    for path in question.path_conditions:
        kind = _token(getattr(path, "horizon_kind", None))
        if kind in {"CLOCK", "GAME", "GAME_CLOCK"}:
            ops.append("TENNIS_GAME_CLOCK")
    return tuple(dict.fromkeys(ops))
