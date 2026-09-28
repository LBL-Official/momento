"""Fail closed if manifest missing, checksum bad, or dataset_version ≠ current fingerprint."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from roller.config import RollerConfig
from roller.research_query.facts import TradableIndex
from roller.research_query.indexes.bars import BARS_NAME, read_bars
from roller.research_query.indexes.builder import index_root
from roller.research_query.indexes.manifest import (
    INDEX_VERSION,
    MANIFEST_NAME,
    IndexManifest,
    file_sha256,
    read_manifest,
)
from roller.research_query.indexes.settlement import SETTLEMENT_NAME, read_settlement
from roller.research_query.indexes.snaps import SNAPS_NAME, read_snaps
from roller.research_query.indexes.transitions import TRANSITIONS_NAME, read_transitions
from roller.research_query.indexes.universe import UNIVERSE_NAME, read_universe
from roller.research_query.availability import LeagueScope
from roller.research_query.models import BASIS_TRADABLE, ResearchQuestion


class IndexUnavailable(Exception):
    """Missing, corrupt, stale, or out-of-coverage observation index."""


@dataclass
class ObservationIndex:
    manifest: IndexManifest
    bars: TradableIndex
    transitions: list[dict]
    pbp_by_game: dict[str, list[dict]]
    markets_by_ticker: dict[str, dict]
    universe: list[dict]
    root: Path

    @property
    def rows_scanned(self) -> int:
        return int(self.manifest.bar_rows)


def _verify_files(root: Path, manifest: IndexManifest) -> None:
    for name, expected in manifest.files.items():
        path = root / name
        if not path.is_file():
            raise IndexUnavailable(f"index file missing: {name}")
        actual = file_sha256(path)
        if actual != expected:
            raise IndexUnavailable(f"index checksum mismatch: {name}")


def verify_index_checksums(root: Path) -> IndexManifest:
    """Read manifest and fail closed if any listed file hash diverges.

    Does not write. Does not rebuild. Used by AUTO ROLLER VERIFY.
    """
    man_path = root / MANIFEST_NAME
    if not man_path.is_file():
        raise IndexUnavailable(f"index manifest missing: {man_path}")
    manifest = read_manifest(man_path)
    _verify_files(root, manifest)
    return manifest


def open_index(
    question: ResearchQuestion,
    *,
    cfg: RollerConfig | None = None,
    dest: Path | None = None,
    expected_dataset_version: str | None = None,
) -> ObservationIndex:
    cfg = cfg or RollerConfig()
    from roller.research_query.availability import resolve_sport_season
    from roller.research_query.dataset_version import dataset_fingerprint

    resolved = resolve_sport_season(question.universe)
    if resolved is None and dest is None:
        if len(question.universe.leagues) > 1:
            raise FileNotFoundError("combined_league_union has no single-league index")
        raise IndexUnavailable("universe does not resolve to a single league/season")
    if dest is None:
        sport, season = resolved  # type: ignore[misc]
        root = index_root(
            cfg, sport, season, league=sport, basis=question.basis() or BASIS_TRADABLE
        )
    else:
        root = dest
    man_path = root / MANIFEST_NAME
    if not man_path.is_file():
        raise FileNotFoundError(str(man_path))
    manifest = read_manifest(man_path)
    if manifest.index_version != INDEX_VERSION:
        raise IndexUnavailable(
            f"index_version {manifest.index_version} != {INDEX_VERSION}"
        )
    ds = expected_dataset_version
    if ds is None and dest is None:
        ds = dataset_fingerprint(question, cfg=cfg)
    if ds is not None and manifest.dataset_version != ds:
        raise IndexUnavailable("dataset_version mismatch — index is stale")
    _verify_files(root, manifest)
    date_from = question.universe.date_from
    date_to = question.universe.date_to
    cov = manifest.coverage or {}
    if (date_from or date_to) and cov.get("full_season") is False:
        raise IndexUnavailable("query dates are outside declared index coverage")
    return ObservationIndex(
        manifest=manifest,
        bars=read_bars(root / BARS_NAME),
        transitions=read_transitions(root / TRANSITIONS_NAME),
        pbp_by_game=read_snaps(root / SNAPS_NAME),
        markets_by_ticker=read_settlement(root / SETTLEMENT_NAME),
        universe=read_universe(root / UNIVERSE_NAME),
        root=root,
    )


def _load_root(
    root: Path,
    *,
    expected_dataset_version: str | None,
    date_from: str | None,
    date_to: str | None,
) -> ObservationIndex:
    man_path = root / MANIFEST_NAME
    if not man_path.is_file():
        raise FileNotFoundError(str(man_path))
    manifest = read_manifest(man_path)
    if manifest.index_version != INDEX_VERSION:
        raise IndexUnavailable(
            f"index_version {manifest.index_version} != {INDEX_VERSION}"
        )
    if expected_dataset_version is not None and manifest.dataset_version != expected_dataset_version:
        raise IndexUnavailable("dataset_version mismatch — index is stale")
    _verify_files(root, manifest)
    cov = manifest.coverage or {}
    if (date_from or date_to) and cov.get("full_season") is False:
        raise IndexUnavailable("query dates are outside declared index coverage")
    return ObservationIndex(
        manifest=manifest,
        bars=read_bars(root / BARS_NAME),
        transitions=read_transitions(root / TRANSITIONS_NAME),
        pbp_by_game=read_snaps(root / SNAPS_NAME),
        markets_by_ticker=read_settlement(root / SETTLEMENT_NAME),
        universe=read_universe(root / UNIVERSE_NAME),
        root=root,
    )


def open_scope_index(
    scope: LeagueScope,
    *,
    cfg: RollerConfig | None = None,
    basis: str = BASIS_TRADABLE,
    date_from: str | None = None,
    date_to: str | None = None,
    expected_dataset_version: str | None = None,
) -> ObservationIndex:
    """Open one league's fact index. Combined queries call this per scope."""
    cfg = cfg or RollerConfig()
    from roller.research_query.dataset_version import scope_fingerprint

    root = index_root(cfg, scope.sport, scope.season, league=scope.league, basis=basis)
    ds = expected_dataset_version or scope_fingerprint(scope, cfg=cfg)
    return _load_root(root, expected_dataset_version=ds, date_from=date_from, date_to=date_to)


def union_observation_indexes(parts: list[ObservationIndex]) -> ObservationIndex:
    """Union per-league indexes. Prefix only when ticker/game ids collide."""
    if len(parts) == 1:
        return parts[0]
    ticker_owners: dict[str, set[str]] = {}
    game_owners: dict[str, set[str]] = {}
    for idx in parts:
        sport = idx.manifest.sport
        for ticker in idx.bars.bars:
            ticker_owners.setdefault(ticker, set()).add(sport)
        for gid in idx.pbp_by_game:
            game_owners.setdefault(gid, set()).add(sport)
    collide_t = {t for t, owners in ticker_owners.items() if len(owners) > 1}
    collide_g = {g for g, owners in game_owners.items() if len(owners) > 1}

    bars: dict[str, list] = {}
    skipped: dict[str, int] = {}
    pbp: dict[str, list[dict]] = {}
    markets: dict[str, dict] = {}
    universe: list[dict] = []
    bar_rows = 0
    basis = parts[0].bars.basis
    for idx in parts:
        sport = idx.manifest.sport
        bar_rows += int(idx.manifest.bar_rows)
        for ticker, seq in idx.bars.bars.items():
            key = f"{sport}:{ticker}" if ticker in collide_t else ticker
            bars[key] = seq
            skipped[key] = int(idx.bars.skipped.get(ticker, 0))
        for gid, events in idx.pbp_by_game.items():
            key = f"{sport}:{gid}" if gid in collide_g else gid
            pbp[key] = events
        for ticker, rec in idx.markets_by_ticker.items():
            key = f"{sport}:{ticker}" if ticker in collide_t else ticker
            markets[key] = rec
        for rec in idx.universe:
            row = dict(rec)
            ticker = str(row.get("ticker") or "")
            if ticker in collide_t:
                row["source_ticker"] = ticker
                row["ticker"] = f"{sport}:{ticker}"
            universe.append(row)
    merged = replace(parts[0].manifest, bar_rows=bar_rows, ticker_count=len(bars))
    return ObservationIndex(
        manifest=merged,
        bars=TradableIndex(bars=bars, skipped=skipped, basis=basis),
        transitions=[],
        pbp_by_game=pbp,
        markets_by_ticker=markets,
        universe=universe,
        root=parts[0].root,
    )
