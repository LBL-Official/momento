"""Canonical RawState. Historical snapshots and queries share this object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

QUERY_MODES = ("PRE_80", "INTRA_80", "POST_80")
ENTRY_SOURCES = ("CHOOSIN_604_CSV", "ASKED_SIX_FIRST80", "WAREHOUSE_FIRST_GE_80", "NONE")


@dataclass
class Lookback:
    seconds_ago: int
    price_cents: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    clock_seconds: int | None = None


@dataclass
class PathPoint:
    t_sec: int
    price_cents: int | None = None
    home_score: int | None = None
    away_score: int | None = None


@dataclass
class RawState:
    is_query: bool
    trade_id: str | None
    side: str
    entry_price_cents: int | None
    current_price_cents: int | None
    home_score_entry: int | None
    away_score_entry: int | None
    home_score_current: int | None
    away_score_current: int | None
    entry_quarter: int | None
    current_quarter: int | None
    entry_seconds_remaining: int | None
    current_seconds_remaining: int | None
    time_since_entry_sec: int | None
    lookbacks: list[Lookback] = field(default_factory=list)
    path_to_t: list[PathPoint] = field(default_factory=list)
    snapshot_kind: str = "query"
    availability_timestamp: str | None = None
    query_mode: str = "POST_80"
    query_source: str = "MANUAL"
    entry_source: str = "NONE"
    internal_game_id: str | None = None
    ticker: str | None = None
    event_id: str | None = None
    snapshot_id: str | None = None
    clock_sport: str | None = None

    def __post_init__(self) -> None:
        side = str(self.side or "").strip().lower()
        if side not in {"home", "away"}:
            from roller.austin.errors import AustinError

            raise AustinError("QUERY_REJECTED", f"side must be home|away, got {self.side!r}")
        self.side = side
        mode = str(self.query_mode or "POST_80").strip().upper().replace("-", "_")
        if mode not in QUERY_MODES:
            from roller.austin.errors import AustinError

            raise AustinError("QUERY_REJECTED", f"query_mode must be PRE_80|INTRA_80|POST_80, got {self.query_mode!r}")
        self.query_mode = mode
        src = str(self.entry_source or "NONE").strip().upper()
        self.entry_source = src if src in ENTRY_SOURCES else "NONE"


def lookback_from_dict(row: dict[str, Any]) -> Lookback:
    return Lookback(
        seconds_ago=int(row["seconds_ago"]),
        price_cents=_opt_int(row.get("price_cents")),
        home_score=_opt_int(row.get("home_score")),
        away_score=_opt_int(row.get("away_score")),
        clock_seconds=_opt_int(row.get("clock_seconds")),
    )


def infer_query_mode(body: dict[str, Any]) -> str:
    explicit = str(body.get("query_mode") or "").strip().upper().replace("-", "_")
    if explicit in QUERY_MODES:
        return explicit
    entry = _opt_int(body.get("entry_price_cents"))
    if entry is None:
        return "PRE_80"
    return "POST_80"


def raw_from_query(body: dict[str, Any]) -> RawState:
    looks = [lookback_from_dict(x) for x in list(body.get("lookbacks") or [])]
    mode = infer_query_mode(body)
    entry = _opt_int(body.get("entry_price_cents"))
    current = _opt_int(body.get("current_price_cents"))
    if mode == "PRE_80":
        entry = None
    return RawState(
        is_query=True,
        trade_id=_opt_str(body.get("trade_id")),
        side=str(body.get("side") or "home"),
        entry_price_cents=entry,
        current_price_cents=current,
        home_score_entry=_opt_int(body.get("home_score_entry")),
        away_score_entry=_opt_int(body.get("away_score_entry")),
        home_score_current=_opt_int(body.get("home_score_current")),
        away_score_current=_opt_int(body.get("away_score_current")),
        entry_quarter=_opt_int(body.get("entry_quarter")),
        current_quarter=_opt_int(body.get("current_quarter")),
        entry_seconds_remaining=_opt_int(body.get("entry_seconds_remaining")),
        current_seconds_remaining=_opt_int(body.get("current_seconds_remaining")),
        time_since_entry_sec=_opt_int(body.get("time_since_entry_sec")),
        lookbacks=looks,
        path_to_t=[],
        snapshot_kind=str(body.get("snapshot_kind") or "query"),
        availability_timestamp=_opt_str(body.get("availability_timestamp")),
        query_mode=mode,
        query_source=str(body.get("query_source") or "MANUAL"),
        entry_source=str(body.get("entry_source") or ("NONE" if entry is None else "CHOOSIN_604_CSV")),
        internal_game_id=_opt_str(body.get("internal_game_id")),
        ticker=_opt_str(body.get("ticker")),
        event_id=_opt_str(body.get("event_id")),
        snapshot_id=_opt_str(body.get("snapshot_id")),
        clock_sport=_opt_str(body.get("clock_sport")),
    )


def entry_probe(state: RawState) -> RawState:
    """Same game at entry: current = entry, travel = 0. Used for STATE CHANGE FROM ENTRY."""
    if state.entry_price_cents is None:
        return state
    return RawState(
        is_query=True,
        trade_id=state.trade_id,
        side=state.side,
        entry_price_cents=state.entry_price_cents,
        current_price_cents=state.entry_price_cents,
        home_score_entry=state.home_score_entry,
        away_score_entry=state.away_score_entry,
        home_score_current=state.home_score_entry,
        away_score_current=state.away_score_entry,
        entry_quarter=state.entry_quarter,
        current_quarter=state.entry_quarter,
        entry_seconds_remaining=state.entry_seconds_remaining,
        current_seconds_remaining=state.entry_seconds_remaining,
        time_since_entry_sec=0,
        lookbacks=[],
        path_to_t=[],
        snapshot_kind="entry_probe",
        availability_timestamp=state.availability_timestamp,
        query_mode="POST_80",
        query_source=state.query_source,
        entry_source=state.entry_source,
        internal_game_id=state.internal_game_id,
        ticker=state.ticker,
        event_id=state.event_id,
        snapshot_id=None,
        clock_sport=state.clock_sport,
    )


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
