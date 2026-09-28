"""Persistent NBA GameMarketLink. Phase 3 only.

Source of truth for ticker → internal_game_id is already-materialized
identity columns kalshi_market_yes_home / kalshi_market_yes_away.

Does not parse ticker bodies. Does not call infer_market_tickers.
Does not guess from date or team names. mapping_status ≠ link_status.

Not used by execute / compile_draft / load_dataset.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from roller.canonical.markets import markets_parquet
from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.io_csv import read_csv, read_csv_optional, sha256_file, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.crosswalk import link_status
from roller.warehouse.entities import GameMarketLink, LinkStatus, Market
from roller.warehouse.identity import IDENTITY_RULE_VERSION, identity_artifact_path
from roller.warehouse.layout_v0 import (
    LINK_METHOD_IDENTITY_TICKER,
    LINK_RULE_VERSION,
    crosswalk_manifest_path,
    crosswalk_path,
    markets_parquet_path,
    sport_crosswalk_manifest_path,
    sport_crosswalk_path,
    warehouse_v0_readme_path,
    warehouse_v0_root,
)

PHASE3_SPORT = "NBA"

CROSSWALK_COLUMNS = [
    "market_id",
    "ticker",
    "internal_game_id",
    "event_ticker",
    "link_status",
    "link_method",
    "source_evidence",
    "sport",
    "season",
    "team_side",
    "identity_rule_version",
    "link_rule_version",
]

MARKET_COLUMNS = [
    "market_id",
    "ticker",
    "source_market_id",
    "source",
    "event_id",
    "event_ticker",
    "market_type",
    "title",
    "sport",
    "league",
    "season",
    "team_side",
    "venue",
    "internal_game_id",
]

WAREHOUSE_V0_README = """# warehouse_v0 (provisional)

NBA Phase 3–5 projection. Not a Confirm & Run source.
Phase 8 will choose the physical layout. Do not treat this tree as final.
"""


@dataclass
class TickerBinding:
    internal_game_id: str
    event_ticker: str
    team_side: str
    season: str
    mapping_status: str


@dataclass
class IdentityTickerIndex:
    unique: dict[str, TickerBinding] = field(default_factory=dict)
    ambiguous: dict[str, tuple[str, ...]] = field(default_factory=dict)
    invalid_empty: list[str] = field(default_factory=list)


@dataclass
class MarketLinkBuild:
    links: pd.DataFrame
    markets: pd.DataFrame
    status_counts: dict[str, int]
    games_with_linked_markets: int
    identity_tickers: int
    suite_tickers: int
    canonical_tickers: int
    input_hashes: dict[str, str]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def identity_ticker_index(identity: pd.DataFrame, *, sport: str = PHASE3_SPORT) -> IdentityTickerIndex:
    """Map explicit identity ticker columns. One ticker → many games is AMBIGUOUS."""
    by_ticker: dict[str, set[str]] = defaultdict(set)
    meta: dict[str, TickerBinding] = {}
    invalid_empty: list[str] = []
    scoped = identity
    if not identity.empty and "sport" in identity.columns:
        scoped = identity[identity["sport"].astype(str) == sport]
    for rec in scoped.to_dict("records"):
        gid = _text(rec.get("internal_game_id"))
        if not gid:
            continue
        event = _text(rec.get("event_ticker"))
        season = _text(rec.get("season"))
        mapping = _text(rec.get("mapping_status"))
        home_t = _text(rec.get("kalshi_market_yes_home"))
        away_t = _text(rec.get("kalshi_market_yes_away"))
        p1_t = _text(rec.get("kalshi_market_yes_p1"))
        p2_t = _text(rec.get("kalshi_market_yes_p2"))
        for ticker, side in ((home_t, "home"), (away_t, "away"), (p1_t, "p1"), (p2_t, "p2")):
            if not ticker:
                if gid:
                    invalid_empty.append(gid)
                continue
            by_ticker[ticker].add(gid)
            meta[ticker] = TickerBinding(
                internal_game_id=gid,
                event_ticker=event,
                team_side=side,
                season=season,
                mapping_status=mapping,
            )
    unique: dict[str, TickerBinding] = {}
    ambiguous: dict[str, tuple[str, ...]] = {}
    for ticker, games in by_ticker.items():
        ordered = tuple(sorted(games))
        if len(ordered) > 1:
            ambiguous[ticker] = ordered
        else:
            unique[ticker] = meta[ticker]
    return IdentityTickerIndex(unique=unique, ambiguous=ambiguous, invalid_empty=invalid_empty)


def classify_market_ticker(
    *,
    ticker: str,
    index: IdentityTickerIndex,
) -> GameMarketLink:
    tick = _text(ticker)
    if not tick:
        return GameMarketLink(status=LinkStatus.INVALID, reason="ticker missing")
    if tick in index.ambiguous:
        return GameMarketLink(
            status=LinkStatus.AMBIGUOUS,
            ticker=tick,
            reason="ticker maps to multiple internal_game_id values",
            source_evidence="identity_explicit_ticker_conflict",
            identity_rule_version=IDENTITY_RULE_VERSION,
        )
    binding = index.unique.get(tick)
    if binding is None:
        return GameMarketLink(
            status=LinkStatus.UNLINKED,
            ticker=tick,
            reason="ticker not in identity catalog",
            source_evidence="suite_or_canonical_ticker_without_identity",
        )
    status = link_status(internal_game_id=binding.internal_game_id, ticker=tick)
    return GameMarketLink(
        status=status,
        internal_game_id=binding.internal_game_id,
        ticker=tick,
        event_ticker=binding.event_ticker,
        reason="identity kalshi_market_yes_home/away",
        link_method=LINK_METHOD_IDENTITY_TICKER,
        source_evidence=f"identity_ticker:{binding.team_side}:{binding.mapping_status or 'NONE'}",
        identity_rule_version=IDENTITY_RULE_VERSION,
    )


def market_from_link_row(row: dict[str, Any]) -> Market:
    ticker = _text(row.get("ticker") or row.get("market_id"))
    return Market(
        ticker=ticker,
        market_id=ticker,
        event_ticker=_text(row.get("event_ticker")),
        internal_game_id=_text(row.get("internal_game_id")),
        venue=_text(row.get("venue")) or "kalshi",
        team_side=_text(row.get("team_side")),
        event_id=_text(row.get("event_id")),
        source_market_id=_text(row.get("source_market_id")),
        source=_text(row.get("source")),
        market_type=_text(row.get("market_type")),
        title=_text(row.get("title")),
        sport=_text(row.get("sport")) or PHASE3_SPORT,
        league=_text(row.get("league")) or PHASE3_SPORT,
    )


def _hash_if_file(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ""


def _ticker_prefix(sport: str) -> str:
    token = str(sport or "").upper()
    if token == "ATP":
        return "KXATPMATCH"
    if token == "WTA":
        return "KXWTAMATCH"
    return ""


def _filter_sport_tickers(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    prefix = _ticker_prefix(sport)
    if not prefix or frame is None or frame.empty or "ticker" not in frame.columns:
        return frame if frame is not None else pd.DataFrame()
    keep = frame["ticker"].map(_text).str.startswith(prefix)
    return frame.loc[keep].copy()


def _suite_layer(cfg: RollerConfig, sport: str, season: str) -> str:
    token = str(sport or "").upper()
    if token in {"ATP", "WTA"}:
        return token.lower()
    return str(cfg.season_meta(sport, season)["warehouse_sport"])


def _suite_markets(cfg: RollerConfig, season: str, *, sport: str = PHASE3_SPORT) -> pd.DataFrame:
    try:
        _, _, wh = load_sport_games(cfg, sport, season)
        src = markets_parquet(wh, _suite_layer(cfg, sport, season))
    except (KeyError, FileNotFoundError, OSError):
        return pd.DataFrame()
    if not src.is_file():
        return pd.DataFrame()
    frame = pd.read_parquet(src)
    if frame.empty or "ticker" not in frame.columns:
        return pd.DataFrame()
    return _filter_sport_tickers(frame, sport)


def _canonical_markets(cfg: RollerConfig, season: str, *, sport: str = PHASE3_SPORT) -> pd.DataFrame:
    try:
        path = cfg.dataset_path(sport, season, "kalshi_markets")
    except KeyError:
        return pd.DataFrame()
    if not path.is_file():
        return pd.DataFrame()
    return _filter_sport_tickers(read_csv(path), sport)


def _collect_tickers(
    index: IdentityTickerIndex,
    suite: pd.DataFrame,
    canonical: pd.DataFrame,
) -> list[str]:
    tickers: set[str] = set(index.unique)
    tickers.update(index.ambiguous)
    if not suite.empty and "ticker" in suite.columns:
        tickers.update(_text(t) for t in suite["ticker"].tolist() if _text(t))
    if not canonical.empty and "ticker" in canonical.columns:
        tickers.update(_text(t) for t in canonical["ticker"].tolist() if _text(t))
    return sorted(tickers)


def _suite_by_ticker(suite: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if suite.empty or "ticker" not in suite.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for rec in suite.to_dict("records"):
        ticker = _text(rec.get("ticker"))
        if ticker:
            out[ticker] = rec
    return out


def _canonical_by_ticker(canonical: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if canonical.empty or "ticker" not in canonical.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for rec in canonical.to_dict("records"):
        ticker = _text(rec.get("ticker"))
        if ticker:
            out[ticker] = rec
    return out


def _default_market_type(sport: str) -> str:
    token = str(sport or "").upper()
    if token == "NBA":
        return "KXNBAGAME"
    if token == "NCAAB":
        return "KXNCAAMBGAME"
    if token == "MLB":
        return "KXMLBGAME"
    if token == "ATP":
        return "KXATPMATCH"
    if token == "WTA":
        return "KXWTAMATCH"
    return f"KX{token}GAME"


def build_market_links(
    cfg: RollerConfig,
    *,
    sport: str = PHASE3_SPORT,
    season: str = "2025-2026",
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> MarketLinkBuild:
    ident_path = identity_artifact_path(cfg)
    if identity is None:
        identity = read_csv_optional(ident_path)
    if suite is None:
        suite = _suite_markets(cfg, season, sport=sport)
    if canonical is None:
        canonical = _canonical_markets(cfg, season, sport=sport)
    index = identity_ticker_index(identity, sport=sport)
    tickers = _collect_tickers(index, suite, canonical)
    suite_map = _suite_by_ticker(suite)
    canon_map = _canonical_by_ticker(canonical)

    link_rows: list[dict[str, str]] = []
    market_rows: list[dict[str, str]] = []
    status_counts = {s.value: 0 for s in LinkStatus}
    games: set[str] = set()
    default_type = _default_market_type(sport)

    for ticker in tickers:
        link = classify_market_ticker(ticker=ticker, index=index)
        status_counts[link.status.value] += 1
        if link.status is LinkStatus.LINKED and link.internal_game_id:
            games.add(link.internal_game_id)
        suite_rec = suite_map.get(ticker, {})
        canon_rec = canon_map.get(ticker, {})
        event = link.event_ticker or _text(canon_rec.get("event_ticker")) or _text(suite_rec.get("event_ticker"))
        if not event:
            event = _text(suite_rec.get("event_id"))
        season_s = ""
        team_side = ""
        if ticker in index.unique:
            season_s = index.unique[ticker].season
            team_side = index.unique[ticker].team_side
        if not team_side:
            team_side = _text(canon_rec.get("team_side"))
        link_rows.append(
            {
                "market_id": ticker,
                "ticker": ticker,
                "internal_game_id": link.internal_game_id,
                "event_ticker": event,
                "link_status": link.status.value,
                "link_method": link.link_method,
                "source_evidence": link.source_evidence or link.reason,
                "sport": sport,
                "season": season_s or season,
                "team_side": team_side,
                "identity_rule_version": link.identity_rule_version or IDENTITY_RULE_VERSION,
                "link_rule_version": LINK_RULE_VERSION,
            }
        )
        title = _text(suite_rec.get("market_title")) or _text(suite_rec.get("title")) or _text(canon_rec.get("title"))
        source_market_id = _text(suite_rec.get("market_id")) or _text(canon_rec.get("market_id"))
        market_rows.append(
            {
                "market_id": ticker,
                "ticker": ticker,
                "source_market_id": source_market_id,
                "source": _text(suite_rec.get("source")) or _text(canon_rec.get("source")) or "kalshi",
                "event_id": _text(suite_rec.get("event_id")) or _text(canon_rec.get("event_id")),
                "event_ticker": event,
                "market_type": _text(suite_rec.get("series_ticker")) or _text(canon_rec.get("series_ticker")) or default_type,
                "title": title,
                "sport": sport,
                "league": _text(suite_rec.get("league")) or _text(canon_rec.get("league")) or sport,
                "season": season_s or _text(suite_rec.get("season")) or _text(canon_rec.get("season")) or season,
                "team_side": team_side,
                "venue": "kalshi",
                "internal_game_id": link.internal_game_id,
            }
        )

    links = pd.DataFrame(link_rows, columns=CROSSWALK_COLUMNS)
    markets = pd.DataFrame(market_rows, columns=MARKET_COLUMNS)
    if not links.empty:
        links = links.sort_values(["ticker"], kind="mergesort").reset_index(drop=True)
    if not markets.empty:
        markets = markets.sort_values(["ticker"], kind="mergesort").reset_index(drop=True)

    hashes = {"identity": _hash_if_file(ident_path)}
    try:
        hashes["kalshi_markets"] = _hash_if_file(cfg.dataset_path(sport, season, "kalshi_markets"))
    except KeyError:
        hashes["kalshi_markets"] = ""
    try:
        _, _, wh = load_sport_games(cfg, sport, season)
        hashes["suite_markets"] = _hash_if_file(
            markets_parquet(wh, _suite_layer(cfg, sport, season))
        )
    except (KeyError, FileNotFoundError, OSError):
        hashes["suite_markets"] = ""

    return MarketLinkBuild(
        links=links,
        markets=markets,
        status_counts=status_counts,
        games_with_linked_markets=len(games),
        identity_tickers=len(index.unique) + len(index.ambiguous),
        suite_tickers=len(suite_map),
        canonical_tickers=len(canon_map),
        input_hashes=hashes,
    )


def build_nba_market_links(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> MarketLinkBuild:
    return build_market_links(
        cfg,
        sport=PHASE3_SPORT,
        season=season,
        identity=identity,
        suite=suite,
        canonical=canonical,
    )


def write_market_links(cfg: RollerConfig, built: MarketLinkBuild, *, sport: str = PHASE3_SPORT) -> dict[str, Any]:
    xwalk = sport_crosswalk_path(cfg, sport)
    xwalk.parent.mkdir(parents=True, exist_ok=True)
    built.links.to_parquet(xwalk, index=False)
    markets_path = markets_parquet_path(cfg, sport)
    markets_path.parent.mkdir(parents=True, exist_ok=True)
    built.markets.to_parquet(markets_path, index=False)
    readme = warehouse_v0_readme_path(cfg, sport)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    manifest = {
        "artifact": "game_market_crosswalk",
        "sport": sport,
        "link_rule_version": LINK_RULE_VERSION,
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "row_count": int(len(built.links)),
        "market_row_count": int(len(built.markets)),
        "status_counts": built.status_counts,
        "games_with_linked_markets": built.games_with_linked_markets,
        "identity_tickers": built.identity_tickers,
        "suite_tickers": built.suite_tickers,
        "canonical_tickers": built.canonical_tickers,
        "input_hashes": built.input_hashes,
        "crosswalk_sha256": sha256_file(xwalk),
        "markets_sha256": sha256_file(markets_path),
        "updated_at": now_utc_iso(),
        "provisional_layout": str(warehouse_v0_root(cfg, sport)),
    }
    write_json(sport_crosswalk_manifest_path(cfg, sport), manifest)
    return manifest


def write_nba_market_links(cfg: RollerConfig, built: MarketLinkBuild) -> dict[str, Any]:
    return write_market_links(cfg, built, sport=PHASE3_SPORT)


def load_nba_crosswalk(cfg: RollerConfig) -> pd.DataFrame:
    path = crosswalk_path(cfg)
    if not path.is_file():
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)
    return pd.read_parquet(path)


def linked_game_id(crosswalk: pd.DataFrame, ticker: str) -> str:
    """Resolve a ticker through the persisted crosswalk. No ticker parsing."""
    tick = _text(ticker)
    if tick == "" or crosswalk.empty:
        return ""
    rows = crosswalk[crosswalk["ticker"].astype(str) == tick]
    if rows.empty:
        return ""
    statuses = { _text(s) for s in rows["link_status"].tolist() }
    gids = { _text(g) for g in rows["internal_game_id"].tolist() if _text(g) }
    if LinkStatus.AMBIGUOUS.value in statuses or len(gids) > 1:
        return ""
    if LinkStatus.LINKED.value not in statuses:
        return ""
    return next(iter(gids))


def audit_link_frame(links: pd.DataFrame) -> dict[str, int]:
    if links.empty:
        return {
            "rows": 0,
            "duplicate_tickers": 0,
            "one_ticker_many_games": 0,
            "linked": 0,
            "unlinked": 0,
            "ambiguous": 0,
            "invalid": 0,
        }
    tickers = links["ticker"].astype(str)
    dup = int(tickers.duplicated().sum())
    linked = links[links["link_status"] == LinkStatus.LINKED.value]
    many = 0
    if not linked.empty:
        many = int(
            linked.groupby("ticker", sort=False)["internal_game_id"].nunique().gt(1).sum()
        )
    return {
        "rows": int(len(links)),
        "duplicate_tickers": dup,
        "one_ticker_many_games": many,
        "linked": int((links["link_status"] == LinkStatus.LINKED.value).sum()),
        "unlinked": int((links["link_status"] == LinkStatus.UNLINKED.value).sum()),
        "ambiguous": int((links["link_status"] == LinkStatus.AMBIGUOUS.value).sum()),
        "invalid": int((links["link_status"] == LinkStatus.INVALID.value).sum()),
    }


def build_and_write_nba_market_links(cfg: RollerConfig, *, season: str = "2025-2026") -> dict[str, Any]:
    built = build_nba_market_links(cfg, season=season)
    return write_nba_market_links(cfg, built)
