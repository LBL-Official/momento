"""Typed ResearchContext bag and Phase 10 filtered warehouse loader.

The bag remains constructible without calling the loader.
get_research_context reads Phase 8 parquet only. It does not execute a backtest,
does not join PBP to candles, and does not fabricate L2 or ticks.
Confirm & Run must not import this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.research_query.models import ResearchQuestion, ResearchStatus
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    get_catalog,
    question_capabilities,
)
from roller.warehouse.desk import desk_sport, observation_basis_for
from roller.warehouse.research_compiler import ResearchPlan, _context_requirements
from roller.warehouse.entities import (
    Game,
    GameMarketLink,
    LinkStatus,
    Market,
    MarketObservation,
    ObservationBasis,
    PBPEvent,
    Settlement,
    SettlementResult,
)
from roller.warehouse.identity import IDENTITY_RULE_VERSION, game_from_row
from roller.warehouse.layout import (
    games_path,
    links_path,
    manifest_path,
    markets_path,
    observations_dir,
    pbp_dir,
    settlements_path,
)
from roller.warehouse.partitioning import list_month_parquets, month_key

PHASE10_SPORT = "NBA"
DEFAULT_SEASON = "2025-2026"
_PATH_MANIFEST_KEYS = frozenset({"warehouse_root", "baseline_root", "observation_path"})

GAME_COLS = (
    "internal_game_id",
    "sport",
    "season",
    "league",
    "game_date",
    "home_team_id",
    "away_team_id",
    "source_game_id",
    "warehouse_game_id",
    "event_ticker",
    "source_system",
    "identity_rule_version",
)
LINK_COLS = (
    "link_status",
    "internal_game_id",
    "ticker",
    "market_id",
    "event_ticker",
    "reason",
    "link_method",
    "source_evidence",
    "identity_rule_version",
)
MARKET_COLS = (
    "ticker",
    "market_id",
    "event_ticker",
    "internal_game_id",
    "venue",
    "team_side",
    "event_id",
    "source_market_id",
    "source",
    "market_type",
    "title",
    "sport",
    "league",
)
SETTLE_COLS = (
    "ticker",
    "market_id",
    "settlement_status",
    "settlement_value_e4",
    "result_available_at",
    "settlement_time",
)
OBS_COLS = (
    "ticker",
    "market_id",
    "internal_game_id",
    "available_at",
    "basis",
    "yes_bid_close",
    "event_timestamp",
    "ingested_at",
    "volume",
    "print_count",
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
    "last_open_e4",
    "last_high_e4",
    "last_low_e4",
    "last_close_e4",
)
PBP_COLS = (
    "internal_game_id",
    "event_timestamp",
    "source_game_id",
    "event_number",
    "available_at",
    "period",
    "clock",
    "inning",
    "half",
    "outs",
    "event_type",
    "home_score",
    "away_score",
)


@dataclass
class LoadStats:
    parquet_files_opened: int = 0
    observation_months: tuple[str, ...] = ()
    pbp_months: tuple[str, ...] = ()
    observation_rows_read: int = 0
    pbp_rows_read: int = 0
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "parquet_files_opened": self.parquet_files_opened,
            "observation_months": list(self.observation_months),
            "pbp_months": list(self.pbp_months),
            "observation_rows_read": self.observation_rows_read,
            "pbp_rows_read": self.pbp_rows_read,
            "cache_hit": self.cache_hit,
        }


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _int_or_none(value: object) -> int | None:
    text = _text(value)
    if text == "":
        return None
    return int(float(text))


def _normalize_season(value: str) -> str:
    return _text(value).replace("_", "-")


def _public_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _PATH_MANIFEST_KEYS:
            continue
        if isinstance(value, str) and ("/" in value or "\\" in value):
            continue
        out[str(key)] = value
    return out


def _fingerprint(parts: list[str]) -> str:
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _months_for_dates(dates: list[str]) -> list[str]:
    months: set[str] = set()
    for day in dates:
        if len(day) < 7:
            continue
        year = int(day[:4])
        month = int(day[5:7])
        months.add(f"{year}-{month:02d}")
        if month == 12:
            months.add(f"{year + 1}-01")
        else:
            months.add(f"{year}-{month + 1:02d}")
        if month == 1:
            months.add(f"{year - 1}-12")
        else:
            months.add(f"{year}-{month - 1:02d}")
    return sorted(months)


def _series_text(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype(str).str.strip()


def _apply_predicates(frame: pd.DataFrame, filters: list[tuple[str, str, Any]] | None) -> pd.DataFrame:
    if not filters or frame.empty:
        return frame
    out = frame
    for col, op, value in filters:
        if col not in out.columns:
            continue
        series = _series_text(out, col)
        if op == ">=":
            out = out[series >= _text(value)]
        elif op == "<=":
            out = out[series <= _text(value)]
        elif op == "in":
            wanted = {_text(v) for v in value}
            out = out[series.isin(wanted)]
    return out


def _read_parquet_projected(path, columns: tuple[str, ...]) -> pd.DataFrame:
    try:
        return pd.read_parquet(path, columns=list(columns))
    except (ValueError, KeyError, OSError):
        frame = pd.read_parquet(path)
        keep = [c for c in columns if c in frame.columns]
        return frame[keep] if keep else frame


def _read_filtered(
    directory,
    months: list[str],
    column: str,
    values: list[str],
    *,
    columns: tuple[str, ...],
    stats: LoadStats | None = None,
    kind: str = "",
) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    wanted = set(months)
    opened: list[str] = []
    rows_read = 0
    wanted_ids = {_text(v) for v in values}
    if not wanted:
        if stats is not None:
            if kind == "obs":
                stats.observation_months = ()
                stats.observation_rows_read = 0
            elif kind == "pbp":
                stats.pbp_months = ()
                stats.pbp_rows_read = 0
        return pd.DataFrame()
    for path in list_month_parquets(directory):
        month = month_key(path)
        if month not in wanted:
            continue
        opened.append(month)
        frame = _read_parquet_projected(path, columns)
        if column in frame.columns:
            frame = frame[_series_text(frame, column).isin(wanted_ids)]
        rows_read += int(len(frame))
        if not frame.empty:
            frames.append(frame)
        if stats is not None:
            stats.parquet_files_opened += 1
    if stats is not None:
        if kind == "obs":
            stats.observation_months = tuple(opened)
            stats.observation_rows_read = rows_read
        elif kind == "pbp":
            stats.pbp_months = tuple(opened)
            stats.pbp_rows_read = rows_read
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@dataclass(frozen=True)
class ResearchContext:
    """In-memory slice of the six warehouse entities. Not a detector."""

    games: tuple[Game, ...] = field(default_factory=tuple)
    markets: tuple[Market, ...] = field(default_factory=tuple)
    observations: tuple[MarketObservation, ...] = field(default_factory=tuple)
    pbp_events: tuple[PBPEvent, ...] = field(default_factory=tuple)
    settlements: tuple[Settlement, ...] = field(default_factory=tuple)
    links: tuple[GameMarketLink, ...] = field(default_factory=tuple)
    observation_basis: str = OBS_BASIS
    observation_resolution: str = OBS_RESOLUTION
    pit_field: str = PIT_FIELD
    warehouse_version: str = ""
    identity_version: str = IDENTITY_RULE_VERSION
    catalog_version: str = CATALOG_VERSION
    fingerprints: dict[str, str] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    question: ResearchQuestion | None = None
    warehouse_manifest: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextResult:
    status: ResearchStatus
    context: ResearchContext | None
    coverage: dict[str, Any]
    missing_data: tuple[str, ...]
    missing_operations: tuple[str, ...]
    load_stats: LoadStats = field(default_factory=LoadStats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "context": None if self.context is None else "ResearchContext",
            "coverage": dict(self.coverage),
            "missing_data": list(self.missing_data),
            "missing_operations": list(self.missing_operations),
        }


_CONTEXT_CACHE: dict[tuple[str, ...], ContextResult] = {}


def clear_context_cache() -> None:
    _CONTEXT_CACHE.clear()


def _empty_result(
    status: ResearchStatus,
    *,
    coverage: dict[str, Any],
    missing_data: tuple[str, ...] = (),
    missing_operations: tuple[str, ...] = (),
    load_stats: LoadStats | None = None,
) -> ContextResult:
    return ContextResult(
        status=status,
        context=None,
        coverage=coverage,
        missing_data=missing_data,
        missing_operations=missing_operations,
        load_stats=load_stats or LoadStats(),
    )


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    cols = list(frame.columns)
    arrays = [frame[c].tolist() for c in cols]
    return [dict(zip(cols, values)) for values in zip(*arrays)]


def _manifest_stamp(cfg: RollerConfig, sport: str = PHASE10_SPORT) -> str:
    path = manifest_path(cfg, sport, DEFAULT_SEASON)
    if not path.is_file():
        return "missing"
    st = path.stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


def _cache_key(
    question: ResearchQuestion,
    catalog,
    reqs: tuple[str, ...],
    plan_hash: str,
    manifest_stamp: str,
) -> tuple[str, ...]:
    uni = question.universe
    return (
        plan_hash,
        catalog.warehouse_version,
        catalog.catalog_version,
        catalog.identity_version,
        manifest_stamp,
        OBS_BASIS,
        PIT_FIELD,
        _text(uni.date_from)[:10],
        _text(uni.date_to)[:10],
        ",".join(_normalize_season(s) for s in uni.seasons),
        ",".join(reqs),
        ",".join(e.id for e in question.entry_conditions),
        ",".join(p.id for p in question.path_conditions),
    )


def _link_from_row(row: dict[str, Any]) -> GameMarketLink:
    status = LinkStatus(_text(row.get("link_status")) or "UNLINKED")
    return GameMarketLink(
        status=status,
        internal_game_id=_text(row.get("internal_game_id")),
        ticker=_text(row.get("ticker") or row.get("market_id")),
        event_ticker=_text(row.get("event_ticker")),
        reason=_text(row.get("reason")),
        link_method=_text(row.get("link_method")),
        source_evidence=_text(row.get("source_evidence")),
        identity_rule_version=_text(row.get("identity_rule_version")) or IDENTITY_RULE_VERSION,
    )


def _market_from_row(row: dict[str, Any], *, gid: str) -> Market:
    ticker = _text(row.get("ticker") or row.get("market_id"))
    return Market(
        ticker=ticker,
        event_ticker=_text(row.get("event_ticker")),
        internal_game_id=gid,
        venue=_text(row.get("venue")) or "kalshi",
        team_side=_text(row.get("team_side")),
        event_id=_text(row.get("event_id")),
        market_id=ticker,
        source_market_id=_text(row.get("source_market_id")),
        source=_text(row.get("source")),
        market_type=_text(row.get("market_type")),
        title=_text(row.get("title")),
        sport=_text(row.get("sport")),
        league=_text(row.get("league")),
    )


def _obs_from_row(row: dict[str, Any], *, gid: str) -> MarketObservation | None:
    ticker = _text(row.get("ticker") or row.get("market_id"))
    available_at = _text(row.get("available_at"))
    if not ticker or not available_at:
        return None
    basis_text = _text(row.get("basis"))
    last_close = _int_or_none(row.get("last_close_e4"))
    close = _int_or_none(row.get("yes_bid_close"))
    if last_close is not None and (not basis_text or basis_text == ObservationBasis.LAST_TRADE_PRINT.value):
        return MarketObservation(
            ticker=ticker,
            basis=ObservationBasis.LAST_TRADE_PRINT,
            available_at=available_at,
            internal_game_id=gid,
            event_timestamp=_text(row.get("event_timestamp")),
            ingested_at=_text(row.get("ingested_at")),
            volume=_int_or_none(row.get("volume")),
            print_count=_int_or_none(row.get("print_count")),
            last_open_e4=_int_or_none(row.get("last_open_e4")),
            last_high_e4=_int_or_none(row.get("last_high_e4")),
            last_low_e4=_int_or_none(row.get("last_low_e4")),
            last_close_e4=last_close,
        )
    if close is None:
        return None
    if basis_text and basis_text != OBS_BASIS:
        return None
    return MarketObservation(
        ticker=ticker,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=available_at,
        internal_game_id=gid,
        event_timestamp=_text(row.get("event_timestamp")),
        ingested_at=_text(row.get("ingested_at")),
        volume=_int_or_none(row.get("volume")),
        yes_bid_open=_int_or_none(row.get("yes_bid_open")),
        yes_bid_high=_int_or_none(row.get("yes_bid_high")),
        yes_bid_low=_int_or_none(row.get("yes_bid_low")),
        yes_bid_close=close,
        yes_ask_open=_int_or_none(row.get("yes_ask_open")),
        yes_ask_high=_int_or_none(row.get("yes_ask_high")),
        yes_ask_low=_int_or_none(row.get("yes_ask_low")),
        yes_ask_close=_int_or_none(row.get("yes_ask_close")),
    )


def _pbp_from_row(row: dict[str, Any]) -> PBPEvent | None:
    gid = _text(row.get("internal_game_id"))
    ts = _text(row.get("event_timestamp"))
    if not gid or not ts:
        return None
    return PBPEvent(
        internal_game_id=gid,
        event_timestamp=ts,
        source_game_id=_text(row.get("source_game_id")),
        event_number=_text(row.get("event_number")),
        available_at=_text(row.get("available_at")),
        period=_text(row.get("period")),
        clock=_text(row.get("clock")),
        inning=_text(row.get("inning")),
        half=_text(row.get("half")),
        event_type=_text(row.get("event_type")),
        home_score=_int_or_none(row.get("home_score")),
        away_score=_int_or_none(row.get("away_score")),
    )


def _settlement_from_row(row: dict[str, Any]) -> Settlement | None:
    ticker = _text(row.get("ticker") or row.get("market_id"))
    if not ticker:
        return None
    status = _text(row.get("settlement_status"))
    try:
        result = SettlementResult(status)
    except ValueError:
        return None
    return Settlement(
        ticker=ticker,
        result=result,
        settlement_value_e4=_int_or_none(row.get("settlement_value_e4")),
        result_available_at=_text(row.get("result_available_at")),
        settlement_time=_text(row.get("settlement_time")),
    )


def get_research_context(
    question: ResearchQuestion,
    cfg: RollerConfig | None = None,
    *,
    plan: ResearchPlan | None = None,
) -> ContextResult:
    """Load a filtered NBA warehouse slice. Does not execute research."""
    cfg = cfg or RollerConfig()
    sport = desk_sport(question) or PHASE10_SPORT
    try:
        catalog = get_catalog(cfg, sport=sport, season=DEFAULT_SEASON)
    except (OSError, ValueError, FileNotFoundError):
        return _empty_result(
            ResearchStatus.DATA_REQUIRED,
            missing_data=("WAREHOUSE",),
            load_stats=LoadStats(),
        )
    coverage = catalog.public_coverage()
    stats = LoadStats()
    sports = tuple(_text(s).upper() for s in question.universe.sports)
    leagues = tuple(_text(s).upper() for s in question.universe.leagues)
    seasons = tuple(_normalize_season(s) for s in question.universe.seasons)
    if desk_sport(question) is None and (sports or leagues):
        return _empty_result(
            ResearchStatus.DATA_REQUIRED,
            coverage=coverage,
            missing_data=("UNIVERSE",),
            load_stats=stats,
        )
    date_from = _text(question.universe.date_from)[:10]
    date_to = _text(question.universe.date_to)[:10]
    if date_from and date_to and date_from > date_to:
        return _empty_result(
            ResearchStatus.DATA_REQUIRED,
            coverage=coverage,
            missing_data=("DATE_RANGE",),
            load_stats=stats,
        )
    resolved = catalog.resolve(question_capabilities(question))
    if resolved.status is not ResearchStatus.READY:
        return _empty_result(
            resolved.status,
            coverage=coverage,
            missing_data=resolved.missing_data,
            missing_operations=resolved.missing_operations,
            load_stats=stats,
        )

    reqs = plan.context_requirements if plan is not None else _context_requirements(question)
    plan_hash = plan.plan_hash if plan is not None else ""
    key = _cache_key(question, catalog, reqs, plan_hash, _manifest_stamp(cfg, sport))
    cached = _CONTEXT_CACHE.get(key)
    if cached is not None and cached.context is not None:
        hit = LoadStats(
            parquet_files_opened=0,
            observation_months=cached.load_stats.observation_months,
            pbp_months=cached.load_stats.pbp_months,
            observation_rows_read=cached.load_stats.observation_rows_read,
            pbp_rows_read=cached.load_stats.pbp_rows_read,
            cache_hit=True,
        )
        return ContextResult(
            status=cached.status,
            context=cached.context,
            coverage=cached.coverage,
            missing_data=cached.missing_data,
            missing_operations=cached.missing_operations,
            load_stats=hit,
        )

    games_path_ = games_path(cfg, sport, DEFAULT_SEASON)
    game_filters: list[tuple[str, str, Any]] = []
    if date_from:
        game_filters.append(("game_date", ">=", date_from))
    if date_to:
        game_filters.append(("game_date", "<=", date_to))
    games_df = _apply_predicates(_read_parquet_projected(games_path_, GAME_COLS), game_filters or None)
    stats.parquet_files_opened += 1
    if seasons and "season" in games_df.columns:
        games_df = games_df[games_df["season"].map(_normalize_season).isin(set(seasons))]
    games = tuple(game_from_row(rec) for rec in _records(games_df))
    game_ids = {g.internal_game_id for g in games}

    links_path_ = links_path(cfg, sport, DEFAULT_SEASON)
    links_df = _read_parquet_projected(links_path_, LINK_COLS)
    stats.parquet_files_opened += 1
    if game_ids or date_from or date_to:
        links_df = _apply_predicates(links_df, [("internal_game_id", "in", sorted(game_ids))])
    links = tuple(
        _link_from_row(rec)
        for rec in _records(links_df)
        if _text(rec.get("ticker") or rec.get("market_id"))
    )
    ticker_to_gid = {link.ticker: link.internal_game_id for link in links if link.status is LinkStatus.LINKED}
    tickers = list(ticker_to_gid)

    markets_path_ = markets_path(cfg, sport, DEFAULT_SEASON)
    markets_df = _read_parquet_projected(markets_path_, MARKET_COLS)
    stats.parquet_files_opened += 1
    if tickers:
        markets_df = _apply_predicates(markets_df, [("ticker", "in", tickers)])
    else:
        markets_df = markets_df.iloc[0:0]
    markets = tuple(
        _market_from_row(rec, gid=ticker_to_gid.get(_text(rec.get("ticker")), ""))
        for rec in _records(markets_df)
        if _text(rec.get("ticker")) in ticker_to_gid
    )

    settle_path_ = settlements_path(cfg, sport, DEFAULT_SEASON)
    settle_df = _read_parquet_projected(settle_path_, SETTLE_COLS)
    stats.parquet_files_opened += 1
    if tickers:
        settle_df = _apply_predicates(settle_df, [("ticker", "in", tickers)])
    else:
        settle_df = settle_df.iloc[0:0]
    settlements = tuple(
        s
        for rec in _records(settle_df)
        if _text(rec.get("ticker")) in ticker_to_gid
        for s in (_settlement_from_row(rec),)
        if s is not None
    )

    need_obs = "tradable_yes_bid_observations" in reqs or "last_trade_print_observations" in reqs
    obs_basis = observation_basis_for(question)
    need_pbp = "pbp_identity" in reqs or _pbp_needed(question)
    materialize = bool(date_from or date_to)
    observations: tuple[MarketObservation, ...] = ()
    pbp_events: tuple[PBPEvent, ...] = ()
    game_dates = [g.game_date for g in games]
    months = _months_for_dates(game_dates) if game_dates else []
    if materialize and ticker_to_gid and need_obs:
        obs_df = _read_filtered(
            observations_dir(cfg, sport, DEFAULT_SEASON, basis=obs_basis),
            months,
            "internal_game_id",
            sorted(set(ticker_to_gid.values())),
            columns=OBS_COLS,
            stats=stats,
            kind="obs",
        )
        built: list[MarketObservation] = []
        for rec in _records(obs_df):
            ticker = _text(rec.get("ticker") or rec.get("market_id"))
            gid = ticker_to_gid.get(ticker)
            if not gid:
                continue
            if _text(rec.get("internal_game_id")) != gid:
                continue
            item = _obs_from_row(rec, gid=gid)
            if item is not None:
                built.append(item)
        observations = tuple(built)
    if materialize and ticker_to_gid and need_pbp:
        pbp_df = _read_filtered(
            pbp_dir(cfg, sport, DEFAULT_SEASON),
            months,
            "internal_game_id",
            sorted(set(ticker_to_gid.values())),
            columns=PBP_COLS,
            stats=stats,
            kind="pbp",
        )
        pbp_events = tuple(
            ev
            for rec in _records(pbp_df)
            for ev in (_pbp_from_row(rec),)
            if ev is not None and ev.internal_game_id in game_ids
        )

    raw_man = json.loads(manifest_path(cfg, sport, DEFAULT_SEASON).read_text(encoding="utf-8"))
    man = _public_manifest(raw_man)
    slice_coverage = {
        **coverage,
        "loaded_games": len(games),
        "loaded_markets": len(markets),
        "loaded_links": len(links),
        "loaded_observations": len(observations),
        "loaded_settlements": len(settlements),
        "loaded_pbp_events": len(pbp_events),
        "observations_materialized": materialize,
        "identity": "market_id→GameMarketLink→internal_game_id",
        "pit_field": PIT_FIELD,
    }
    context = ResearchContext(
        games=games,
        markets=markets,
        observations=observations,
        pbp_events=pbp_events,
        settlements=settlements,
        links=links,
        observation_basis=obs_basis,
        observation_resolution=OBS_RESOLUTION,
        pit_field=PIT_FIELD,
        warehouse_version=catalog.warehouse_version,
        identity_version=IDENTITY_RULE_VERSION,
        catalog_version=CATALOG_VERSION,
        fingerprints={
            "manifest_updated_at": catalog.warehouse_version,
            "games": _fingerprint(sorted(g.internal_game_id for g in games)),
            "tickers": _fingerprint(sorted(ticker_to_gid)),
        },
        coverage=slice_coverage,
        question=question,
        warehouse_manifest=man,
    )
    result = ContextResult(
        status=ResearchStatus.READY,
        context=context,
        coverage=slice_coverage,
        missing_data=(),
        missing_operations=(),
        load_stats=stats,
    )
    _CONTEXT_CACHE[key] = result
    return result


def _pbp_needed(question: ResearchQuestion) -> bool:
    if any(
        _text(x).upper().replace(" ", "_") == "PBP"
        for x in (*question.universe.game_data, *question.requested_dimensions)
    ):
        return True
    return any(e.has_period_or_clock() for e in question.entry_conditions)
