"""On-disk warehouse catalog. Declared paths are not data.

Phase 9 warehouse coverage lives in roller.warehouse.coverage.
`catalog()` remains the Confirm & Run CSV path inventory.
`get_catalog` is the Phase 9 NBA coverage API (no paths in the public result).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.warehouse.partitioning import list_month_csvs, list_month_parquets, month_key

ON_DISK_SPORTS = ("NBA", "NCAAB", "WNBA", "MLB", "ATP", "WTA")
UNAVAILABLE_SPORTS = ("NHL", "NFL", "NCAAF")

PARTITIONED = frozenset(
    {
        "kalshi_candles",
        "kalshi_last_trade",
        "pbp",
        "polymarket_candles",
        "kalshi_orderbook_snapshots",
        "kalshi_trades",
        "kalshi_trade_ticks",
    }
)


@dataclass(frozen=True)
class DatasetRef:
    sport: str
    league: str
    season: str
    dataset: str
    path: Path
    kind: str  # file | directory | missing
    months: tuple[str, ...] = ()
    parquet_months: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeasonRef:
    sport: str
    league: str
    season: str
    root: Path
    datasets: dict[str, DatasetRef] = field(default_factory=dict)


def _league_for(sport: str) -> str:
    return sport


def declared_seasons(cfg: RollerConfig | None = None) -> list[tuple[str, str, dict[str, Any]]]:
    cfg = cfg or RollerConfig()
    out: list[tuple[str, str, dict[str, Any]]] = []
    for sport, body in (cfg.db_map.get("sports") or {}).items():
        for season, spec in (body.get("seasons") or {}).items():
            out.append((str(sport), str(season), spec or {}))
    return out


def catalog(cfg: RollerConfig | None = None) -> list[SeasonRef]:
    cfg = cfg or RollerConfig()
    seasons: list[SeasonRef] = []
    for sport, season, spec in declared_seasons(cfg):
        rel = str(spec.get("path") or "")
        root = (cfg.root / rel).resolve() if rel else cfg.root / "data" / sport.lower() / season.replace("-", "_")
        datasets: dict[str, DatasetRef] = {}
        for name, rel_path in (spec.get("datasets") or {}).items():
            path = (cfg.root / str(rel_path)).resolve()
            if path.is_dir():
                months = tuple(month_key(p) for p in list_month_csvs(path))
                pq = tuple(month_key(p) for p in list_month_parquets(path))
                datasets[name] = DatasetRef(
                    sport=sport,
                    league=_league_for(sport),
                    season=season,
                    dataset=name,
                    path=path,
                    kind="directory",
                    months=months,
                    parquet_months=pq,
                )
            elif path.is_file():
                datasets[name] = DatasetRef(
                    sport=sport,
                    league=_league_for(sport),
                    season=season,
                    dataset=name,
                    path=path,
                    kind="file",
                )
            else:
                datasets[name] = DatasetRef(
                    sport=sport,
                    league=_league_for(sport),
                    season=season,
                    dataset=name,
                    path=path,
                    kind="missing",
                )
        seasons.append(
            SeasonRef(
                sport=sport,
                league=_league_for(sport),
                season=season,
                root=root,
                datasets=datasets,
            )
        )
    return seasons


def get_catalog(cfg: RollerConfig | None = None, *, sport: str = "NBA", season: str = "2025-2026"):
    """Phase 9 NBA coverage catalog. See roller.warehouse.coverage.get_catalog."""
    from roller.warehouse.coverage import get_catalog as _get_catalog

    return _get_catalog(cfg, sport=sport, season=season)


def sport_on_disk(sport: str, cfg: RollerConfig | None = None) -> bool:
    cfg = cfg or RollerConfig()
    key = sport.upper()
    if key in UNAVAILABLE_SPORTS:
        return False
    for ref in catalog(cfg):
        if ref.sport.upper() == key and ref.root.is_dir():
            return True
    return False
