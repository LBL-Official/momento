"""Build observation indexes from the same canonical sources as _load_warehouse.

Index builders persist facts. Detectors stay in operations.py — do not reimplement them here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.research_query.dataset_version import dataset_fingerprint
from roller.research_query.facts import TradableIndex
from roller.research_query.hashing import CODE_VERSION
from roller.research_query.indexes.bars import BARS_NAME, write_bars
from roller.research_query.indexes.manifest import (
    INDEX_VERSION,
    MANIFEST_NAME,
    IndexManifest,
    file_sha256,
    git_sha,
    now_utc,
    write_manifest,
)
from roller.research_query.indexes.settlement import SETTLEMENT_NAME, write_settlement
from roller.research_query.indexes.snaps import SNAPS_NAME, write_snaps
from roller.research_query.indexes.transitions import TRANSITIONS_NAME, write_transitions
from roller.research_query.indexes.universe import UNIVERSE_NAME, write_universe
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    OPERATION_SEMANTICS_VERSION,
    ResearchQuestion,
    Universe,
)
from roller.research_query.season_mapping import sport_from_league, warehouse_season


def index_basis_leaf(basis: str) -> str:
    return "last_trade" if basis == BASIS_LAST_TRADE else "tradable"


def warehouse_season_dir(cfg: RollerConfig, sport: str, season: str) -> Path:
    """On-disk season root from roller.json. ATP/WTA share data/tennis/."""
    try:
        rel = str(cfg.db_map["sports"][sport]["seasons"][season]["path"])
        return (cfg.root / rel).resolve()
    except KeyError:
        return (cfg.root / "data" / sport.lower() / season.replace("-", "_")).resolve()


def index_root(
    cfg: RollerConfig,
    sport: str,
    season: str,
    *,
    league: str | None = None,
    index_version: str = INDEX_VERSION,
    basis: str = BASIS_TRADABLE,
) -> Path:
    """Fact index leaf. League is required so ATP and WTA do not overwrite each other."""
    league_id = str(league or sport).upper()
    return (
        warehouse_season_dir(cfg, sport, season)
        / "derived"
        / "research_query"
        / "indexes"
        / index_version
        / league_id
        / index_basis_leaf(basis)
    )


def _question_for(league: str, season: str, *, basis: str = BASIS_TRADABLE) -> ResearchQuestion:
    from roller.research_query.models import TerminalOutcome

    sport = sport_from_league(league)
    if sport == "MLB":
        sports: tuple[str, ...] = ("baseball",)
    elif sport in {"ATP", "WTA"}:
        sports = ("tennis",)
    else:
        sports = ("basketball",)
    market_data = ("last_trade",) if basis == BASIS_LAST_TRADE else ("candles",)
    return ResearchQuestion(
        universe=Universe(
            sports=sports,
            leagues=(league,),
            seasons=(season,),
            markets=("kalshi",),
            market_data=market_data,
        ),
        entry_conditions=(),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )


def build_index(
    *,
    league: str,
    season: str,
    cfg: RollerConfig | None = None,
    ticker_payloads: dict[str, list[dict[str, Any]]] | None = None,
    pbp_by_game: dict[str, list[dict[str, Any]]] | None = None,
    markets_by_ticker: dict[str, dict[str, Any]] | None = None,
    dest: Path | None = None,
    basis: str = BASIS_TRADABLE,
) -> IndexManifest:
    cfg = cfg or RollerConfig()
    sport = sport_from_league(league)
    wh_season = warehouse_season(season, sport)
    q = _question_for(league, season, basis=basis)
    games: list[dict[str, Any]] = []
    if ticker_payloads is None:
        from roller.research_query.execute import _load_warehouse

        ticker_payloads, pbp_by_game, markets_by_ticker, games = _load_warehouse(cfg, q)
        print(
            f"loaded {league} {basis}: tickers={len(ticker_payloads)} "
            f"bars={sum(len(v) for v in ticker_payloads.values())}",
            flush=True,
        )
    pbp_by_game = pbp_by_game or {}
    markets_by_ticker = markets_by_ticker or {}
    index = TradableIndex.build(ticker_payloads, basis=basis)
    out = dest or index_root(cfg, sport, wh_season, league=league, basis=basis)
    out.mkdir(parents=True, exist_ok=True)
    bar_rows = write_bars(out / BARS_NAME, index)
    transition_rows = write_transitions(out / TRANSITIONS_NAME, index)
    write_snaps(out / SNAPS_NAME, pbp_by_game)
    settlement_rows = write_settlement(out / SETTLEMENT_NAME, markets_by_ticker)
    write_universe(out / UNIVERSE_NAME, index, league, wh_season, games=games)
    files = {}
    for name in (BARS_NAME, TRANSITIONS_NAME, SNAPS_NAME, SETTLEMENT_NAME, UNIVERSE_NAME):
        files[name] = file_sha256(out / name)
    source_paths: list[str] = []
    for name in ("kalshi_candles", "kalshi_last_trade", "pbp", "kalshi_markets", "games"):
        try:
            source_paths.append(str(cfg.dataset_path(sport, wh_season, name)))
        except (KeyError, FileNotFoundError):
            continue
    games = {bars[0].game_id for bars in index.bars.values() if bars}
    ds_ver = dataset_fingerprint(q, cfg=cfg) if dest is None else "injected"
    manifest = IndexManifest(
        index_version=INDEX_VERSION,
        dataset_version=ds_ver,
        code_version=CODE_VERSION,
        operation_semantics_version=OPERATION_SEMANTICS_VERSION,
        league=league,
        season=wh_season,
        sport=sport,
        built_at_utc=now_utc(),
        git_sha=git_sha(),
        source_paths=source_paths,
        files=files,
        ticker_count=len(index.bars),
        game_count=len(games),
        bar_rows=bar_rows,
        transition_rows=transition_rows,
        settlement_rows=settlement_rows,
        coverage={"full_season": dest is None, "date_from": None, "date_to": None, "basis": basis},
    )
    write_manifest(out / MANIFEST_NAME, manifest)
    return manifest
