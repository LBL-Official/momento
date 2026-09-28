"""Phase 9 NBA warehouse coverage catalog.

Reads the Phase 8 parquet warehouse and Phase 7 orderbook capability.
Does not load Confirm & Run CSV. Does not execute research.
Public API returns no filesystem paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq

from roller.config import RollerConfig
from roller.research_query.models import ResearchQuestion, ResearchStatus
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.desk import DESK_SPORTS
from roller.warehouse.layout import (
    games_path,
    links_path,
    manifest_path,
    markets_path,
    observations_dir,
    pbp_dir,
    settlements_path,
    warehouse_root,
)
from roller.warehouse.layout_v0 import orderbook_capability_path
from roller.warehouse.partitioning import list_month_parquets, month_key

CATALOG_VERSION = "1.0.0"
PHASE9_SPORT = "NBA"
DEFAULT_SEASON = "2025-2026"
PIT_FIELD = "available_at"
OBS_BASIS = "TRADABLE_YES_BID"
OBS_RESOLUTION = "1_MINUTE_CANDLE"


class CapabilityName(str, Enum):
    GAME = "GAME"
    MARKET = "MARKET"
    GAME_MARKET_LINK = "GAME_MARKET_LINK"
    TRADABLE_YES_BID_1M = "TRADABLE_YES_BID_1M"
    CANDLE_PIT = "CANDLE_PIT"
    SETTLEMENT = "SETTLEMENT"
    PBP = "PBP"
    ORDERBOOK = "ORDERBOOK"
    TICK = "TICK"
    HISTORICAL_L2 = "HISTORICAL_L2"
    HISTORICAL_TICK = "HISTORICAL_TICK"
    PBP_MARKET_PIT_ALIGNMENT = "PBP_MARKET_PIT_ALIGNMENT"
    LAST_TRADE_PRINT_1M = "LAST_TRADE_PRINT_1M"


READY_CAPABILITIES = frozenset(
    {
        CapabilityName.GAME,
        CapabilityName.MARKET,
        CapabilityName.GAME_MARKET_LINK,
        CapabilityName.TRADABLE_YES_BID_1M,
        CapabilityName.CANDLE_PIT,
        CapabilityName.SETTLEMENT,
        CapabilityName.PBP,
    }
)
DATA_REQUIRED_CAPABILITIES = frozenset(
    {
        CapabilityName.ORDERBOOK,
        CapabilityName.TICK,
        CapabilityName.HISTORICAL_L2,
        CapabilityName.HISTORICAL_TICK,
    }
)
OPERATION_REQUIRED_CAPABILITIES = frozenset({CapabilityName.PBP_MARKET_PIT_ALIGNMENT})


_CATALOG_CACHE: dict[tuple[str, str, str, float], WarehouseCatalog] = {}

_DATA_TOKENS = {
    "TICK": CapabilityName.TICK,
    "TICKS": CapabilityName.TICK,
    "HISTORICAL_TICK": CapabilityName.HISTORICAL_TICK,
    "LAST_TRADE": CapabilityName.LAST_TRADE_PRINT_1M,
    "LAST_TRADE_PRINT": CapabilityName.LAST_TRADE_PRINT_1M,
    "TRADE_TAPE": CapabilityName.TICK,
    "TRADES": CapabilityName.TICK,
    "L2": CapabilityName.HISTORICAL_L2,
    "HISTORICAL_L2": CapabilityName.HISTORICAL_L2,
    "ORDERBOOK": CapabilityName.ORDERBOOK,
    "ORDERBOOK_SNAPSHOT": CapabilityName.ORDERBOOK,
    "CANDLES": CapabilityName.TRADABLE_YES_BID_1M,
    "CANDLE": CapabilityName.TRADABLE_YES_BID_1M,
    "TRADABLE_YES_BID": CapabilityName.TRADABLE_YES_BID_1M,
    "1_MINUTE": CapabilityName.TRADABLE_YES_BID_1M,
    "1-MINUTE": CapabilityName.TRADABLE_YES_BID_1M,
    "1_MINUTE_CANDLE": CapabilityName.TRADABLE_YES_BID_1M,
}

_PIT_ALIGN_TOKENS = frozenset(
    {
        "PBP_MARKET_PIT_ALIGNMENT",
        "PBP_CANDLE_PIT",
        "PBP_CANDLE_PIT_ALIGNMENT",
        "PBP_PIT_ALIGNMENT",
        "PBP_MARKET_PIT",
    }
)


def _token(value: object) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("↔", "_").replace("-", "_")


def question_capabilities(question: ResearchQuestion) -> tuple[CapabilityName, ...]:
    """Map a ResearchQuestion onto catalog capabilities. Does not execute."""
    reqs: list[CapabilityName] = [
        CapabilityName.GAME,
        CapabilityName.MARKET,
        CapabilityName.GAME_MARKET_LINK,
        CapabilityName.SETTLEMENT,
    ]
    seen = {r.value for r in reqs}

    def _add(name: CapabilityName) -> None:
        if name.value not in seen:
            seen.add(name.value)
            reqs.append(name)

    md = [_token(x) for x in question.universe.market_data]
    gd = [_token(x) for x in question.universe.game_data]
    dims = [_token(x) for x in question.requested_dimensions]
    data_caps = [_DATA_TOKENS[t] for t in md if t in _DATA_TOKENS]
    missing_basis = [c for c in data_caps if c in DATA_REQUIRED_CAPABILITIES]
    wants_last_trade = CapabilityName.LAST_TRADE_PRINT_1M in data_caps
    wants_tradable = CapabilityName.TRADABLE_YES_BID_1M in data_caps
    if missing_basis:
        for cap in missing_basis:
            _add(cap)
    if wants_last_trade:
        _add(CapabilityName.LAST_TRADE_PRINT_1M)
    if wants_tradable or (not missing_basis and not wants_last_trade):
        _add(CapabilityName.TRADABLE_YES_BID_1M)
        _add(CapabilityName.CANDLE_PIT)
    if any(t in _PIT_ALIGN_TOKENS for t in (*gd, *dims, *md)):
        _add(CapabilityName.PBP_MARKET_PIT_ALIGNMENT)
    needs_pbp = any(t == "PBP" for t in (*gd, *dims))
    if not needs_pbp:
        needs_pbp = any(e.has_period_or_clock() for e in question.entry_conditions)
    if needs_pbp:
        _add(CapabilityName.PBP)
    return tuple(reqs)


def _capability(name: str | CapabilityName) -> CapabilityName:
    if isinstance(name, CapabilityName):
        return name
    key = str(name).strip().upper().replace(" ", "_").replace("↔", "_").replace("-", "_")
    aliases = {
        "L2": CapabilityName.HISTORICAL_L2,
        "ORDERBOOK_SNAPSHOT": CapabilityName.ORDERBOOK,
        "LAST_TRADE": CapabilityName.LAST_TRADE_PRINT_1M,
        "LAST_TRADE_PRINT": CapabilityName.LAST_TRADE_PRINT_1M,
        "PBP_CANDLE_PIT": CapabilityName.PBP_MARKET_PIT_ALIGNMENT,
        "PBP_CANDLE_PIT_ALIGNMENT": CapabilityName.PBP_MARKET_PIT_ALIGNMENT,
        "TRADABLE_YES_BID": CapabilityName.TRADABLE_YES_BID_1M,
        "CANDLE_PIT_AVAILABLE_AT": CapabilityName.CANDLE_PIT,
    }
    if key in aliases:
        return aliases[key]
    return CapabilityName(key)


@dataclass(frozen=True)
class CoverageResolution:
    status: ResearchStatus
    requirements: tuple[str, ...]
    satisfied_capabilities: tuple[str, ...]
    missing_data: tuple[str, ...]
    missing_operations: tuple[str, ...]
    coverage: dict[str, Any]
    warehouse_version: str
    observation_basis: str
    observation_resolution: str
    pit_field: str
    catalog_version: str = CATALOG_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "requirements": list(self.requirements),
            "satisfied_capabilities": list(self.satisfied_capabilities),
            "missing_data": list(self.missing_data),
            "missing_operations": list(self.missing_operations),
            "coverage": dict(self.coverage),
            "warehouse_version": self.warehouse_version,
            "observation_basis": self.observation_basis,
            "observation_resolution": self.observation_resolution,
            "pit_field": self.pit_field,
            "catalog_version": self.catalog_version,
        }


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parquet_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    return int(pq.ParquetFile(path).metadata.num_rows)


def _month_rows(directory: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for path in list_month_parquets(directory):
        out[month_key(path)] = _parquet_rows(path)
    return out


def _column_minmax(directory: Path, column: str) -> tuple[str, str]:
    lo, hi = "", ""
    for path in list_month_parquets(directory):
        pf = pq.ParquetFile(path)
        names = [f.name for f in pf.schema_arrow]
        if column not in names:
            continue
        idx = names.index(column)
        for g in range(pf.metadata.num_row_groups):
            stats = pf.metadata.row_group(g).column(idx).statistics
            if stats is None or not stats.has_min_max:
                continue
            a = _text(stats.min)
            b = _text(stats.max)
            if a and (not lo or a < lo):
                lo = a
            if b and (not hi or b > hi):
                hi = b
    return lo, hi


def _unique_strings(directory: Path, column: str) -> set[str]:
    values: set[str] = set()
    for path in list_month_parquets(directory):
        pf = pq.ParquetFile(path)
        if column not in pf.schema_arrow.names:
            continue
        table = pf.read(columns=[column])
        if table.num_rows == 0:
            continue
        for v in table.column(0).unique().to_pylist():
            text = _text(v)
            if text:
                values.add(text)
    return values


def _nonzero_count(directory: Path, column: str) -> int:
    n = 0
    for path in list_month_parquets(directory):
        pf = pq.ParquetFile(path)
        if column not in pf.schema_arrow.names:
            continue
        table = pf.read(columns=[column])
        if table.num_rows == 0:
            continue
        for v in table.column(0).to_pylist():
            if _text(v):
                n += 1
    return n


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class WarehouseCatalog:
    sport: str
    season: str
    warehouse_version: str
    catalog_version: str
    identity_version: str
    games: dict[str, Any]
    markets: dict[str, Any]
    links: dict[str, Any]
    observations: dict[str, Any]
    settlements: dict[str, Any]
    pbp: dict[str, Any]
    orderbook: dict[str, Any]
    fingerprints: dict[str, str] = field(default_factory=dict)
    _game_dates: tuple[str, ...] = ()
    _games_with_obs: frozenset[str] = frozenset()
    _games_with_pbp: frozenset[str] = frozenset()
    _games_with_settlement: frozenset[str] = frozenset()
    _markets_with_settlement: frozenset[str] = frozenset()
    _markets_with_obs: frozenset[str] = frozenset()
    _ready_extra: frozenset[CapabilityName] = frozenset()

    def _ready_set(self) -> frozenset[CapabilityName]:
        return frozenset(set(READY_CAPABILITIES) | set(self._ready_extra))

    def resolve(self, requirements: Iterable[str | CapabilityName]) -> CoverageResolution:
        reqs = tuple(_capability(r) for r in requirements)
        ready = self._ready_set()
        satisfied: list[str] = []
        missing_data: list[str] = []
        missing_ops: list[str] = []
        for req in reqs:
            if req in ready:
                satisfied.append(req.value)
            elif req in DATA_REQUIRED_CAPABILITIES:
                missing_data.append(req.value)
            elif req in OPERATION_REQUIRED_CAPABILITIES:
                missing_ops.append(req.value)
            else:
                missing_data.append(req.value)
        if missing_data:
            status = ResearchStatus.DATA_REQUIRED
        elif missing_ops:
            status = ResearchStatus.OPERATION_REQUIRED
        else:
            status = ResearchStatus.READY
        return CoverageResolution(
            status=status,
            requirements=tuple(r.value for r in reqs),
            satisfied_capabilities=tuple(satisfied),
            missing_data=tuple(missing_data),
            missing_operations=tuple(missing_ops),
            coverage=self.public_coverage(),
            warehouse_version=self.warehouse_version,
            observation_basis=_text(self.observations.get("observation_basis")) or OBS_BASIS,
            observation_resolution=_text(self.observations.get("resolution")) or OBS_RESOLUTION,
            pit_field=PIT_FIELD,
        )

    def date_coverage(self, date_from: str, date_to: str) -> dict[str, Any]:
        lo = min(self._game_dates) if self._game_dates else ""
        hi = max(self._game_dates) if self._game_dates else ""
        start = _text(date_from)[:10]
        end = _text(date_to)[:10]
        in_range = [d for d in self._game_dates if start <= d <= end] if start and end else []
        obs_lo = _text(self.observations.get("min_available_at"))
        obs_hi = _text(self.observations.get("max_available_at"))
        candles_overlap = bool(obs_lo and obs_hi and end >= obs_lo[:10] and start <= obs_hi[:10])
        return {
            "requested_from": start,
            "requested_to": end,
            "warehouse_contains_date_range": bool(in_range),
            "warehouse_outside_date_range": not bool(in_range),
            "dates_without_market_observations": bool(in_range) and not candles_overlap,
            "markets_without_settlement": int(
                self.markets.get("market_count", 0) - len(self._markets_with_settlement)
            ),
            "games_without_pbp": int(self.games.get("game_count", 0) - len(self._games_with_pbp)),
            "matching_game_dates": len(in_range),
            "warehouse_game_date_min": lo,
            "warehouse_game_date_max": hi,
        }

    def public_coverage(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "season": self.season,
            "games": dict(self.games),
            "markets": dict(self.markets),
            "links": dict(self.links),
            "observations": dict(self.observations),
            "settlements": dict(self.settlements),
            "pbp": dict(self.pbp),
            "orderbook": dict(self.orderbook),
        }

    def capability_matrix(self) -> dict[str, str]:
        ready = self._ready_set()
        matrix = {name.value: ResearchStatus.READY.value for name in ready}
        for name in DATA_REQUIRED_CAPABILITIES:
            if name not in ready:
                matrix[name.value] = ResearchStatus.DATA_REQUIRED.value
        for name in OPERATION_REQUIRED_CAPABILITIES:
            matrix[name.value] = ResearchStatus.OPERATION_REQUIRED.value
        return dict(sorted(matrix.items()))


def get_catalog(
    cfg: RollerConfig | None = None,
    *,
    sport: str = PHASE9_SPORT,
    season: str = DEFAULT_SEASON,
) -> WarehouseCatalog:
    cfg = cfg or RollerConfig()
    sport = sport.upper()
    if sport not in DESK_SPORTS:
        raise ValueError(f"Phase 9 catalog supports {sorted(DESK_SPORTS)}; got {sport}")
    man_path = manifest_path(cfg, sport, season)
    if sport in {"MLB", "NCAAB", "ATP", "WTA"} and not man_path.is_file():
        raise ValueError(f"{sport} Phase 8 warehouse is absent")
    mtime = man_path.stat().st_mtime if man_path.is_file() else 0.0
    cache_key = (str(cfg.root), sport.upper(), season, mtime)
    cached = _CATALOG_CACHE.get(cache_key)
    if cached is not None:
        return cached
    man = _read_json(man_path)
    cap = _read_json(orderbook_capability_path(cfg, sport, season))

    games_df = pd.read_parquet(games_path(cfg, sport, season))
    markets_df = pd.read_parquet(markets_path(cfg, sport, season))
    links_df = pd.read_parquet(links_path(cfg, sport, season))
    settle_df = pd.read_parquet(settlements_path(cfg, sport, season))

    obs_dir = observations_dir(cfg, sport, season)
    last_dir = observations_dir(cfg, sport, season, basis="LAST_TRADE_PRINT")
    pbp_directory = pbp_dir(cfg, sport, season)
    obs_months = _month_rows(obs_dir)
    last_months = _month_rows(last_dir)
    pbp_months = _month_rows(pbp_directory)
    obs_rows = int(sum(obs_months.values()))
    last_rows = int(sum(last_months.values()))
    pbp_rows = int(sum(pbp_months.values()))
    if int(man.get("observation_rows") or 0) and int(man["observation_rows"]) != obs_rows:
        raise ValueError(
            f"observation row metadata mismatch: manifest {man.get('observation_rows')} parquet {obs_rows}"
        )
    if int(man.get("pbp_rows") or 0) and int(man["pbp_rows"]) != pbp_rows:
        raise ValueError(f"PBP row metadata mismatch: manifest {man.get('pbp_rows')} parquet {pbp_rows}")

    avail_min, avail_max = _column_minmax(obs_dir, "available_at")
    event_min, event_max = _column_minmax(obs_dir, "event_timestamp")
    obs_games = _unique_strings(obs_dir, "internal_game_id")
    obs_markets = _unique_strings(obs_dir, "ticker")
    pbp_games = _unique_strings(pbp_directory, "internal_game_id")
    pbp_periods = tuple(sorted(_unique_strings(pbp_directory, "period")))
    clock_n = _nonzero_count(pbp_directory, "clock")
    pbp_ts_n = _nonzero_count(pbp_directory, "event_timestamp")

    game_dates = tuple(sorted({_text(d) for d in games_df["game_date"].tolist() if _text(d)}))
    settle_status = settle_df["settlement_status"].astype(str)
    settle_yes = int((settle_status == "YES").sum())
    settle_no = int((settle_status == "NO").sum())
    settle_missing = int((settle_status == "MISSING").sum())
    settle_invalid = int((settle_status == "INVALID").sum())
    settle_games = frozenset(
        _text(g)
        for g, st in zip(settle_df["internal_game_id"], settle_status)
        if _text(g) and st in {"YES", "NO", "INVALID"}
    )
    settle_markets = frozenset(
        _text(t)
        for t, st in zip(settle_df["ticker"], settle_status)
        if _text(t) and st in {"YES", "NO", "INVALID"}
    )
    link_status = links_df["link_status"].astype(str)
    linked_games = frozenset(
        _text(g)
        for g, st in zip(links_df["internal_game_id"], link_status)
        if st == "LINKED" and _text(g)
    )

    warehouse_version = _text(man.get("updated_at")) or f"{sport.lower()}_warehouse"
    last_min, last_max = _column_minmax(last_dir, "available_at") if last_rows else ("", "")
    last_games = _unique_strings(last_dir, "internal_game_id") if last_rows else set()
    last_markets = _unique_strings(last_dir, "ticker") if last_rows else set()
    desk_tradable = obs_rows > 0
    obs_public = {
        "observation_basis": OBS_BASIS if desk_tradable else ("LAST_TRADE_PRINT" if last_rows else OBS_BASIS),
        "resolution": OBS_RESOLUTION,
        "observation_count": obs_rows if desk_tradable else last_rows,
        "games_with_observations": len(obs_games if desk_tradable else last_games),
        "markets_with_observations": len(obs_markets if desk_tradable else last_markets),
        "min_event_time": event_min if desk_tradable else last_min,
        "max_event_time": event_max if desk_tradable else last_max,
        "min_available_at": avail_min if desk_tradable else last_min,
        "max_available_at": avail_max if desk_tradable else last_max,
        "PIT_available": True,
        "pit_field": PIT_FIELD,
        "tradable_yes_bid_count": obs_rows,
        "last_trade_print_count": last_rows,
    }
    ready_extra = frozenset(
        {CapabilityName.LAST_TRADE_PRINT_1M} if last_rows else set()
    )
    catalog = WarehouseCatalog(
        sport=sport,
        season=season,
        warehouse_version=warehouse_version,
        catalog_version=CATALOG_VERSION,
        identity_version=IDENTITY_RULE_VERSION,
        games={
            "game_count": int(len(games_df)),
            "min_game_date": game_dates[0] if game_dates else "",
            "max_game_date": game_dates[-1] if game_dates else "",
            "seasons": tuple(sorted({_text(s) for s in games_df["season"].tolist() if _text(s)})),
            "leagues": tuple(sorted({_text(s) for s in games_df["league"].tolist() if _text(s)})),
        },
        markets={
            "market_count": int(len(markets_df)),
            "ticker_count": int(markets_df["ticker"].nunique()),
            "games_with_markets": int(markets_df["internal_game_id"].map(_text).nunique()),
            "market_source": "kalshi_markets.result" if sport == "MLB" else "kalshi_rest",
        },
        links={
            "linked_count": int((link_status == "LINKED").sum()),
            "unlinked_count": int((link_status == "UNLINKED").sum()),
            "ambiguous_count": int((link_status == "AMBIGUOUS").sum()),
            "invalid_count": int((link_status == "INVALID").sum()),
            "games_with_linked_markets": len(linked_games),
        },
        observations=obs_public,
        settlements={
            "settlement_count": int(len(settle_df)),
            "YES": settle_yes,
            "NO": settle_no,
            "MISSING": settle_missing,
            "INVALID": settle_invalid,
            "games_with_settlement": len(settle_games),
            "markets_with_settlement": len(settle_markets),
        },
        pbp={
            "pbp_event_count": pbp_rows,
            "games_with_pbp": len(pbp_games),
            "period_coverage": pbp_periods,
            "clock_available": clock_n > 0,
            "event_timestamp_available": pbp_ts_n > 0,
            "pbp_pit_aligned_to_candles": False,
        },
        orderbook={
            "availability": _text(cap.get("availability")) or "SOURCE_UNAVAILABLE",
            "rows": int(cap.get("snapshot_rows") or 0),
            "depth": _text(cap.get("depth")) or "NONE",
            "top_of_book": _text(cap.get("top_of_book")) or "NONE",
            "market_data_basis": _text(cap.get("market_data_basis")) or "ONE_MINUTE_CANDLE",
        },
        fingerprints={"manifest_updated_at": warehouse_version},
        _game_dates=game_dates,
        _games_with_obs=frozenset(obs_games),
        _games_with_pbp=frozenset(pbp_games),
        _games_with_settlement=settle_games,
        _markets_with_settlement=settle_markets,
        _markets_with_obs=frozenset(obs_markets | last_markets),
        _ready_extra=ready_extra,
    )
    _ = warehouse_root(cfg, sport, season)  # path stays internal
    _CATALOG_CACHE[cache_key] = catalog
    return catalog
