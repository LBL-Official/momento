"""Isolated ATP / WTA warehouse desks (Phases 2–8, 17, 20).

Reads the shared tennis canonical + Suite tree once, then writes two
isolated parquet warehouses. Does not remint event tickers. Does not
write the NBA / NCAAB / MLB crosswalks. Does not call Confirm & Run
execute / compiler / load_dataset. LAST_TRADE_PRINT ≠ TRADABLE_YES_BID.
Settlement is Kalshi result only. MCP PBP is sequence-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.ingest.kalshi import candles_root, iter_candle_frames
from roller.io_csv import read_csv, read_csv_optional, sha256_file, write_csv, write_json
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    PriceField,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.timeutil import now_utc_iso
from roller.warehouse.desk import DEFAULT_SEASON
from roller.warehouse.entities import (
    ObservationBasis,
    Settlement,
    SettlementResult,
    kalshi_result_to_settlement,
)
from roller.warehouse.identity import (
    IDENTITY_ARTIFACT_COLUMNS,
    IDENTITY_RULE_VERSION,
    identity_artifact_path,
    source_system_for,
)
from roller.warehouse.layout import (
    GAME_SORT,
    LINK_SORT,
    MARKET_SORT,
    OBS_FINGERPRINT_COLS,
    OBS_SORT,
    PBP_FINGERPRINT_COLS,
    PBP_SORT,
    SETTLE_SORT,
    fingerprint_frame,
    orderbook_partition_exists,
    project_games,
    warehouse_root,
    write_sorted_parquet,
)
from roller.warehouse.layout_v0 import (
    LINK_RULE_VERSION,
    orderbook_capability_path,
    warehouse_v0_readme_path,
    warehouse_v0_root,
)
from roller.warehouse.market_link import (
    CROSSWALK_COLUMNS,
    MarketLinkBuild,
    audit_link_frame,
    build_market_links,
    write_market_links,
)
from roller.warehouse.mlb_desk import LAST_TRADE_OBS_COLUMNS, project_last_trade_frame
from roller.warehouse.ncaab_desk import _union_by_key, suite_candles_to_raw
from roller.warehouse.observations import (
    ObservationBuild,
    _update_stats as _update_tradable_stats,
    project_observation_frame,
)
from roller.warehouse.partitioning import list_month_csvs, list_month_parquets, month_key, month_parquet
from roller.warehouse.pbp_events import PBP_COLUMNS, PbpBuild
from roller.warehouse.settlement import (
    SETTLEMENT_COLUMNS,
    SettlementBuild,
    assert_not_inferred_settlement_source,
    coverage_report,
)

TOURS = ("ATP", "WTA")
SERIES_BY_TOUR = {"ATP": "KXATPMATCH", "WTA": "KXWTAMATCH"}
PBP_TOUR_CODE = {"ATP": "M", "WTA": "W"}
TICKER_PREFIX = {"ATP": "KXATPMATCH", "WTA": "KXWTAMATCH"}
NBA_CROSSWALK_SHA256 = "521fa0af3c674935518a42f8de499b548b94b71f6a20e45f305f2f5aaab982d8"
TENNIS_PBP_EXTRA = ("set_number", "game_number", "tennis_match_id", "tour")

WAREHOUSE_V0_README = """# warehouse_v0 (provisional)

Tennis Phase 3–7 projection. Not a Confirm & Run source.
Phase 8 publishes data/atp|wta/2025_2026/derived/warehouse/.
TRADABLE_YES_BID and LAST_TRADE_PRINT. LAST TRADE ≠ YES BID.
"""

TENNIS_WAREHOUSE_README = """# Tennis warehouse (Phase 8 physical layout)

Not a Confirm & Run source. Execution of the new desk reads this parquet tree.

observation_bases: TRADABLE_YES_BID, LAST_TRADE_PRINT
observation_resolution: 1_MINUTE
tick_data_available: false
orderbook_data_available: false
candle_pit_field: available_at
pbp_pit_aligned_to_candles: false
LAST_TRADE_PRINT ≠ TRADABLE_YES_BID
MCP PBP is sequence-only
"""


def _phase20_question(tour: str) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=(tour,),
            leagues=(tour,),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            date_from="2025-07-01",
            date_to="2025-07-31",
        ),
        entry_conditions=(
            EntryCondition(
                id=f"{tour.lower()}_desk_cross_65",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6500,
                operation=EntryOp.CROSS,
                price_field=PriceField.YES_BID_CLOSE.value,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4000, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
    )


ATP_PHASE20_QUESTION = _phase20_question("ATP")
WTA_PHASE20_QUESTION = _phase20_question("WTA")
PHASE20_QUESTION = ATP_PHASE20_QUESTION


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: object) -> str:
    text = _text(value)
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def tennis_crosswalk_path(cfg: RollerConfig, tour: str) -> Path:
    return cfg.root / "meta" / f"game_market_crosswalk_{tour.lower()}.parquet"


def tennis_crosswalk_manifest_path(cfg: RollerConfig, tour: str) -> Path:
    return cfg.root / "meta" / f"game_market_crosswalk_{tour.lower()}.manifest.json"


def load_tennis_crosswalk(cfg: RollerConfig, tour: str) -> pd.DataFrame:
    path = tennis_crosswalk_path(cfg, tour)
    if not path.is_file():
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)
    return pd.read_parquet(path)


def _shared_games_path(cfg: RollerConfig, season: str = DEFAULT_SEASON) -> Path:
    return cfg.dataset_path("ATP", season, "games")


def _shared_markets_path(cfg: RollerConfig, season: str = DEFAULT_SEASON) -> Path:
    return cfg.dataset_path("ATP", season, "kalshi_markets")


def _filter_tour_games(frame: pd.DataFrame, tour: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    sport = frame["sport"].map(_text).str.upper() if "sport" in frame.columns else pd.Series("", index=frame.index)
    league = frame["league"].map(_text).str.upper() if "league" in frame.columns else pd.Series("", index=frame.index)
    return frame.loc[(sport == tour) | (league == tour)].copy()


def _filter_ticker_prefix(frame: pd.DataFrame, tour: str) -> pd.DataFrame:
    if frame is None or frame.empty or "ticker" not in frame.columns:
        return pd.DataFrame() if frame is None else frame
    prefix = TICKER_PREFIX[tour]
    return frame.loc[frame["ticker"].map(_text).str.startswith(prefix)].copy()


def _tickers_by_event(markets: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if markets is None or markets.empty:
        return out
    for rec in markets.to_dict("records"):
        event = _text(rec.get("event_ticker"))
        ticker = _text(rec.get("ticker"))
        if not event or not ticker:
            continue
        out.setdefault(event, [])
        if ticker not in out[event]:
            out[event].append(ticker)
    for event, ticks in out.items():
        ticks.sort()
    return out


def _identity_row_from_tennis_game(
    game: dict[str, Any],
    *,
    tour: str,
    now: str,
    by_event: dict[str, list[str]],
) -> dict[str, str]:
    gid = _text(game.get("internal_game_id")) or _text(game.get("event_ticker"))
    event = _text(game.get("event_ticker")) or gid
    ticks = by_event.get(event, [])
    p1 = _text(game.get("kalshi_market_yes_p1")) or _text(game.get("kalshi_market_yes_home"))
    p2 = _text(game.get("kalshi_market_yes_p2")) or _text(game.get("kalshi_market_yes_away"))
    if not p1 and ticks:
        p1 = ticks[0]
    if not p2 and len(ticks) > 1:
        p2 = ticks[1]
    src = _text(game.get("source_game_id")) or event
    mapped = bool(_text(game.get("tennis_match_id")) or _text(game.get("mcp_match_id")))
    return {
        "internal_game_id": gid,
        "sport": tour,
        "season": _text(game.get("season")) or DEFAULT_SEASON,
        "game_date": _text(game.get("game_date")),
        "home_team_id": _text(game.get("home_team_id")) or _text(game.get("p1_name")),
        "away_team_id": _text(game.get("away_team_id")) or _text(game.get("p2_name")),
        "home_team_name": _text(game.get("home_team_name")) or _text(game.get("p1_name")),
        "away_team_name": _text(game.get("away_team_name")) or _text(game.get("p2_name")),
        "source_game_id": src,
        "warehouse_game_id": _text(game.get("warehouse_game_id")) or event,
        "event_ticker": event,
        "kalshi_market_yes_home": p1,
        "kalshi_market_yes_away": p2,
        "mapping_status": "MAPPED" if mapped else "UNMAPPED",
        "mapping_confidence": "HIGH" if mapped else "NONE",
        "created_at": now,
        "updated_at": now,
    }


def verify_tennis_identities(
    cfg: RollerConfig,
    *,
    tours: tuple[str, ...] = TOURS,
    season: str = DEFAULT_SEASON,
    games: pd.DataFrame | None = None,
    markets: pd.DataFrame | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Copy missing shared-tree IDs onto the identity artifact. Do not remint."""
    path = identity_artifact_path(cfg)
    existing = read_csv_optional(path, IDENTITY_ARTIFACT_COLUMNS)
    existing_ids = set()
    if not existing.empty:
        existing_ids = {_text(g) for g in existing["internal_game_id"].tolist() if _text(g)}
    if games is None:
        src = _shared_games_path(cfg, season)
        games = read_csv(src) if src.is_file() else pd.DataFrame()
    if markets is None:
        msrc = _shared_markets_path(cfg, season)
        markets = read_csv(msrc) if msrc.is_file() else pd.DataFrame()
    by_event = _tickers_by_event(markets)
    now = now_utc_iso()
    new_rows: list[dict[str, str]] = []
    by_tour = {tour: {"appended": 0, "skipped": 0, "games": 0} for tour in tours}
    for tour in tours:
        scoped = _filter_tour_games(games, tour)
        by_tour[tour]["games"] = int(len(scoped))
        for rec in scoped.to_dict("records"):
            gid = _text(rec.get("internal_game_id")) or _text(rec.get("event_ticker"))
            if not gid:
                continue
            if gid in existing_ids:
                by_tour[tour]["skipped"] += 1
                continue
            row = _identity_row_from_tennis_game(rec, tour=tour, now=now, by_event=by_event)
            if not row["internal_game_id"]:
                continue
            new_rows.append(row)
            existing_ids.add(row["internal_game_id"])
            by_tour[tour]["appended"] += 1
    if write and new_rows:
        added = pd.DataFrame(new_rows)
        out = added if existing.empty else pd.concat([existing, added], ignore_index=True)
        for col in IDENTITY_ARTIFACT_COLUMNS:
            if col not in out.columns:
                out[col] = ""
        out = out[IDENTITY_ARTIFACT_COLUMNS]
        out = out.sort_values(["sport", "game_date", "internal_game_id"]).reset_index(drop=True)
        write_csv(path, out, IDENTITY_ARTIFACT_COLUMNS)
    after = read_csv_optional(path, IDENTITY_ARTIFACT_COLUMNS)
    identity_counts = {}
    if not after.empty and "sport" in after.columns:
        identity_counts = after["sport"].astype(str).value_counts().to_dict()
    return {
        "sport": "TENNIS",
        "tours": list(tours),
        "appended": len(new_rows),
        "by_tour": by_tour,
        "identity_counts": {k: int(v) for k, v in identity_counts.items()},
        "reminted": False,
        "identity_rule_version": IDENTITY_RULE_VERSION,
    }


def verify_atp_identity(cfg: RollerConfig, *, write: bool = True) -> dict[str, Any]:
    report = verify_tennis_identities(cfg, tours=("ATP",), write=write)
    report["sport"] = "ATP"
    return report


def verify_wta_identity(cfg: RollerConfig, *, write: bool = True) -> dict[str, Any]:
    report = verify_tennis_identities(cfg, tours=("WTA",), write=write)
    report["sport"] = "WTA"
    return report


def build_tennis_market_links(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> MarketLinkBuild:
    return build_market_links(
        cfg,
        sport=tour,
        season=season,
        identity=identity,
        suite=suite,
        canonical=canonical,
    )


def write_tennis_market_links(cfg: RollerConfig, built: MarketLinkBuild, tour: str) -> dict[str, Any]:
    return write_market_links(cfg, built, sport=tour)


def build_and_write_tennis_market_links(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> dict[str, Any]:
    built = build_tennis_market_links(
        cfg, tour, season=season, identity=identity, suite=suite, canonical=canonical
    )
    return write_tennis_market_links(cfg, built, tour)


def _suite_root(cfg: RollerConfig, season: str = DEFAULT_SEASON) -> Path:
    _, _, wh = load_sport_games(cfg, "ATP", season)
    return wh


def _load_suite_candle_months(wh: Path, layer: str) -> dict[str, pd.DataFrame]:
    months: dict[str, pd.DataFrame] = {}
    if not candles_root(wh, layer).is_dir():
        return months
    for month, frame in iter_candle_frames(wh, layer):
        months[month] = suite_candles_to_raw(frame)
    return months


def project_tennis_tradable_observations(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    crosswalk: pd.DataFrame | None = None,
    canonical_months: dict[str, pd.DataFrame] | None = None,
    suite_months: dict[str, pd.DataFrame] | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_tennis_crosswalk(cfg, tour)
    if crosswalk.empty:
        raise ValueError(f"{tour} GameMarketLink crosswalk is empty; run Phase 3 first")
    src_dir = cfg.dataset_path(tour, season, "kalshi_candles")
    out_dir = warehouse_v0_root(cfg, tour, season) / "observations" / "basis=tradable_yes_bid"
    stats = ObservationBuild()
    tickers: set[str] = set()
    linked_tickers: set[str] = set()
    unlinked_tickers: set[str] = set()
    games: set[str] = set()
    if suite_months is None:
        try:
            suite_months = _load_suite_candle_months(_suite_root(cfg, season), tour.lower())
        except (KeyError, FileNotFoundError, OSError):
            suite_months = {}
    if canonical_months is None:
        canonical_months = {}
        for path in list_month_csvs(src_dir):
            month = month_key(path)
            raw = read_csv(path)
            canonical_months[month] = _filter_ticker_prefix(raw, tour)
    months = sorted(set(canonical_months) | set(suite_months))
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, tour, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for month in months:
        canonical = canonical_months.get(month, pd.DataFrame())
        if canonical is not None and not canonical.empty:
            canonical = _filter_ticker_prefix(canonical, tour)
        suite_raw = suite_months.get(month, pd.DataFrame())
        if suite_raw is not None and not suite_raw.empty:
            suite_raw = _filter_ticker_prefix(suite_raw, tour)
        raw = _union_by_key(canonical, suite_raw)
        if raw.empty:
            continue
        projected = project_observation_frame(raw, crosswalk)
        _update_tradable_stats(stats, projected, month)
        tickers.update(projected["ticker"].astype(str))
        linked_tickers.update(projected.loc[projected["game_link_status"] == "LINKED", "ticker"].astype(str))
        unlinked_tickers.update(projected.loc[projected["game_link_status"] == "UNLINKED", "ticker"].astype(str))
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.tickers = len(tickers)
    stats.linked_tickers = len(linked_tickers)
    stats.unlinked_tickers = len(unlinked_tickers)
    stats.games_with_observations = len(games)
    stats.markets_with_observations = stats.tickers
    report = {
        "sport": tour,
        "basis": ObservationBasis.TRADABLE_YES_BID.value,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "unlinked_rows": stats.unlinked_rows,
        "conflict_rows": stats.conflict_rows,
        "duplicate_keys": stats.duplicate_keys,
        "tickers": stats.tickers,
        "linked_tickers": stats.linked_tickers,
        "unlinked_tickers": stats.unlinked_tickers,
        "games_with_observations": stats.games_with_observations,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "canonical_widened": False,
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def project_tennis_last_trade_observations(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    crosswalk: pd.DataFrame | None = None,
    last_trade_months: dict[str, pd.DataFrame] | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_tennis_crosswalk(cfg, tour)
    if crosswalk.empty:
        raise ValueError(f"{tour} GameMarketLink crosswalk is empty; run Phase 3 first")
    src_dir = cfg.dataset_path(tour, season, "kalshi_last_trade")
    out_dir = warehouse_v0_root(cfg, tour, season) / "observations" / "basis=last_trade_print"
    stats = ObservationBuild()
    tickers: set[str] = set()
    linked_tickers: set[str] = set()
    unlinked_tickers: set[str] = set()
    games: set[str] = set()
    if last_trade_months is None:
        last_trade_months = {}
        for path in list_month_csvs(src_dir):
            last_trade_months[month_key(path)] = read_csv(path)
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, tour, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for month, raw in sorted(last_trade_months.items()):
        scoped = _filter_ticker_prefix(raw, tour)
        if scoped.empty:
            continue
        if "last_close_e4" in scoped.columns:
            scoped = scoped.loc[scoped["last_close_e4"].map(_text).ne("")].copy()
        if scoped.empty:
            continue
        projected = project_last_trade_frame(scoped, crosswalk)
        stats.months[month] = int(len(projected))
        stats.rows += int(len(projected))
        stats.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
        stats.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
        stats.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
        stats.duplicate_keys += int((projected["duplicate_key"] == "1").sum())
        if not projected.empty:
            times = projected["available_at"].astype(str)
            lo, hi = times.min(), times.max()
            if not stats.date_min or lo < stats.date_min:
                stats.date_min = lo
            if not stats.date_max or hi > stats.date_max:
                stats.date_max = hi
        tickers.update(projected["ticker"].astype(str))
        linked_tickers.update(projected.loc[projected["game_link_status"] == "LINKED", "ticker"].astype(str))
        unlinked_tickers.update(projected.loc[projected["game_link_status"] == "UNLINKED", "ticker"].astype(str))
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.tickers = len(tickers)
    stats.linked_tickers = len(linked_tickers)
    stats.unlinked_tickers = len(unlinked_tickers)
    stats.games_with_observations = len(games)
    stats.markets_with_observations = stats.tickers
    report = {
        "sport": tour,
        "basis": ObservationBasis.LAST_TRADE_PRINT.value,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "unlinked_rows": stats.unlinked_rows,
        "conflict_rows": stats.conflict_rows,
        "duplicate_keys": stats.duplicate_keys,
        "tickers": stats.tickers,
        "linked_tickers": stats.linked_tickers,
        "unlinked_tickers": stats.unlinked_tickers,
        "games_with_observations": stats.games_with_observations,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def _tennis_gid_index(identity: pd.DataFrame, tour: str) -> dict[str, str]:
    out: dict[str, str] = {}
    scoped = identity
    if not identity.empty and "sport" in identity.columns:
        scoped = identity[identity["sport"].astype(str) == tour]
    for rec in scoped.to_dict("records"):
        gid = _text(rec.get("internal_game_id"))
        event = _text(rec.get("event_ticker"))
        if gid:
            out[gid] = gid
        if event:
            out[event] = gid or event
    return out


def project_tennis_pbp_frame(frame: pd.DataFrame, index: dict[str, str], tour: str) -> pd.DataFrame:
    cols = list(PBP_COLUMNS) + [c for c in TENNIS_PBP_EXTRA if c not in PBP_COLUMNS]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=cols)
    work = frame.copy()
    code = PBP_TOUR_CODE[tour]
    prefix = TICKER_PREFIX[tour]
    tour_col = work["tour"].map(_text).str.upper() if "tour" in work.columns else pd.Series("", index=work.index)
    gid_col = work["internal_game_id"].map(_text) if "internal_game_id" in work.columns else pd.Series("", index=work.index)
    event_col = (
        work["kalshi_event_ticker"].map(_text) if "kalshi_event_ticker" in work.columns else pd.Series("", index=work.index)
    )
    keep = (tour_col == code) | gid_col.str.startswith(prefix) | event_col.str.startswith(prefix)
    work = work.loc[keep].copy()
    if work.empty:
        return pd.DataFrame(columns=cols)
    resolved: list[str] = []
    status: list[str] = []
    stamped = work["internal_game_id"].map(_text) if "internal_game_id" in work.columns else pd.Series("", index=work.index)
    events = (
        work["kalshi_event_ticker"].map(_text) if "kalshi_event_ticker" in work.columns else pd.Series("", index=work.index)
    )
    for gid, event in zip(stamped.tolist(), events.tolist()):
        key = gid or event
        hit = index.get(key) or index.get(event) or index.get(gid)
        if hit:
            status.append("LINKED")
            resolved.append(hit)
        else:
            status.append("UNLINKED")
            resolved.append("")
    work["source_internal_game_id"] = stamped
    work["internal_game_id"] = resolved
    work["game_link_status"] = status
    work["source_game_id"] = work["tennis_match_id"].map(_text) if "tennis_match_id" in work.columns else ""
    work["event_number"] = work.get("point_number", pd.Series("", index=work.index)).map(_text)
    work["event_timestamp"] = work.get("event_timestamp", pd.Series("", index=work.index)).map(_text)
    work["timestamp_status"] = "SEQUENCE_ONLY"
    work["availability_quality"] = work.get("pbp_basis", pd.Series("SEQUENCE_ONLY", index=work.index)).map(_text)
    sets = pd.to_numeric(work.get("set_number", pd.Series("", index=work.index)), errors="coerce")
    period = pd.Series("", index=work.index, dtype=object)
    ok = sets.notna() & sets.between(1, 5)
    period.loc[ok] = "S" + sets.loc[ok].astype("int64").astype(str)
    work["period"] = period
    work["source"] = work.get("source_dataset", pd.Series("mcp_sequence_only", index=work.index)).map(_text)
    for col in TENNIS_PBP_EXTRA:
        if col in work.columns:
            work[col] = work[col].map(_text)
        else:
            work[col] = ""
    for col in cols:
        if col not in work.columns:
            work[col] = ""
    out = work[cols].copy()
    out["_seq"] = pd.to_numeric(out["event_number"], errors="coerce")
    out = out.sort_values(["internal_game_id", "_seq", "event_number"], kind="mergesort")
    return out.drop(columns=["_seq"]).reset_index(drop=True)


def project_tennis_pbp(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    pbp_months: dict[str, pd.DataFrame] | None = None,
    write: bool = True,
) -> tuple[PbpBuild, dict[str, Any]]:
    if identity is None:
        identity = read_csv_optional(identity_artifact_path(cfg))
    index = _tennis_gid_index(identity, tour)
    src_dir = cfg.dataset_path(tour, season, "pbp")
    out_dir = warehouse_v0_root(cfg, tour, season) / "pbp"
    stats = PbpBuild()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, tour, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    if pbp_months is None:
        pbp_months = {month_key(path): read_csv(path) for path in list_month_csvs(src_dir)}
    for month, raw in sorted(pbp_months.items()):
        projected = project_tennis_pbp_frame(raw, index, tour)
        stats.months[month] = int(len(projected))
        stats.rows += int(len(projected))
        stats.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
        stats.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
        stats.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
        stats.blank_event_timestamp += int(projected["event_timestamp"].astype(str).str.strip().eq("").sum())
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.games_with_pbp = len(games)
    report = {
        "sport": tour,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "conflict_rows": stats.conflict_rows,
        "unlinked_rows": stats.unlinked_rows,
        "blank_event_timestamp": stats.blank_event_timestamp,
        "games_with_pbp": stats.games_with_pbp,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "pit_join_performed": False,
        "timestamps_invented": False,
        "pbp_pit_aligned_to_candles": False,
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def build_tennis_settlements(
    cfg: RollerConfig,
    tour: str,
    *,
    season: str = DEFAULT_SEASON,
    markets: pd.DataFrame | None = None,
    crosswalk: pd.DataFrame | None = None,
) -> SettlementBuild:
    source_hash = ""
    source_path = ""
    if markets is None:
        try:
            wh = _suite_root(cfg, season)
            from roller.canonical.markets import markets_parquet

            src = markets_parquet(wh, tour.lower())
            source_path = str(src)
            source_hash = sha256_file(src) if src.is_file() else ""
            markets = pd.read_parquet(src) if src.is_file() else pd.DataFrame()
        except (KeyError, FileNotFoundError, OSError):
            src = cfg.dataset_path(tour, season, "kalshi_markets")
            source_path = str(src)
            source_hash = sha256_file(src) if src.is_file() else ""
            markets = read_csv(src) if src.is_file() else pd.DataFrame()
    markets = _filter_ticker_prefix(markets, tour)
    if crosswalk is None:
        crosswalk = load_tennis_crosswalk(cfg, tour)
        if crosswalk.empty:
            raise ValueError(f"{tour} GameMarketLink crosswalk is empty; run Phase 3 first")
    assert_not_inferred_settlement_source(
        list(markets.columns) if markets is not None and not markets.empty else ["result"]
    )
    links: dict[str, tuple[str, str]] = {}
    for rec in crosswalk.to_dict("records"):
        ticker = _text(rec.get("ticker") or rec.get("market_id"))
        if ticker:
            links[ticker] = (_text(rec.get("internal_game_id")), _text(rec.get("link_status")))
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    if markets is not None and not markets.empty and "ticker" in markets.columns:
        for rec in markets.to_dict("records"):
            ticker = _text(rec.get("ticker"))
            if not ticker:
                raise ValueError("malformed settlement: blank ticker")
            by_ticker.setdefault(ticker, []).append(rec)
    rows: list[dict[str, str]] = []
    extras = {"duplicate_source_rows": 0, "unlinked_rows": 0, "missing_rows": 0}
    provenance = f"suite:markets.parquet:{source_hash[:16] or 'nohash'}:result"
    for ticker in sorted(set(by_ticker) | set(links)):
        sources = by_ticker.get(ticker, [])
        gid, link_status = links.get(ticker, ("", "UNLINKED"))
        if not sources:
            extras["missing_rows"] += 1
            status = SettlementResult.MISSING
            source_result = ""
            value = ""
            settled_at = ""
        else:
            keys = {kalshi_result_to_settlement(rec.get("result")).value for rec in sources}
            if len(keys) > 1:
                raise ValueError(f"conflicting Kalshi settlements for {ticker}: {sorted(keys)}")
            if len(sources) > 1:
                extras["duplicate_source_rows"] += len(sources) - 1
            rec = sources[0]
            status = kalshi_result_to_settlement(rec.get("result"))
            source_result = _text(rec.get("result")).lower()
            value = "" if status is SettlementResult.MISSING else _text(rec.get("settlement_value_e4"))
            settled_at = _iso(rec.get("settlement_time") or rec.get("close_time") or rec.get("expiration_time"))
            Settlement(
                ticker=ticker,
                result=status,
                settlement_value_e4=None if value == "" else int(value) if str(value).lstrip("-").isdigit() else None,
            )
        if link_status != "LINKED":
            extras["unlinked_rows"] += 1
            gid = ""
            link_status = link_status or "UNLINKED"
        rows.append(
            {
                "market_id": ticker,
                "ticker": ticker,
                "internal_game_id": gid,
                "game_link_status": link_status,
                "source": "kalshi_markets.result",
                "source_market_id": ticker,
                "source_identifier": ticker,
                "source_result": source_result,
                "settlement_status": status.value,
                "settlement_value_e4": value,
                "source_settled_at": settled_at,
                "result_available_at": settled_at,
                "settlement_time": settled_at,
                "close_time": "",
                "expiration_time": "",
                "provenance": provenance,
                "sport": tour,
                "season": season,
            }
        )
    frame = pd.DataFrame(rows, columns=SETTLEMENT_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["market_id"], kind="mergesort").reset_index(drop=True)
    status_counts = {s.value: 0 for s in SettlementResult}
    for status in frame["settlement_status"].astype(str) if not frame.empty else []:
        status_counts[status] = status_counts.get(status, 0) + 1
    games = set()
    if not frame.empty:
        settled = frame[frame["settlement_status"].isin(["YES", "NO", "INVALID"])]
        games = {g for g in settled["internal_game_id"].astype(str) if g}
    return SettlementBuild(
        settlements=frame,
        status_counts=status_counts,
        suite_tickers=int(markets["ticker"].map(_text).astype(bool).sum())
        if markets is not None and not markets.empty and "ticker" in markets.columns
        else 0,
        crosswalk_tickers=0 if crosswalk.empty else int(crosswalk["ticker"].map(_text).nunique()),
        duplicate_source_rows=extras["duplicate_source_rows"],
        unlinked_rows=extras["unlinked_rows"],
        missing_rows=extras["missing_rows"],
        games_with_settlement=len(games),
        input_hashes={"suite_markets": source_hash},
        source_path=source_path,
    )


def write_tennis_settlements(
    cfg: RollerConfig, built: SettlementBuild, tour: str, *, season: str = DEFAULT_SEASON
) -> dict[str, Any]:
    dest = warehouse_v0_root(cfg, tour, season) / "settlements.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    built.settlements.to_parquet(dest, index=False)
    readme = warehouse_v0_readme_path(cfg, tour, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    manifest = {
        "artifact": f"{tour.lower()}_settlements",
        "sport": tour,
        "row_count": int(len(built.settlements)),
        "status_counts": built.status_counts,
        "source_path": built.source_path,
        "input_hashes": built.input_hashes,
        "sha256": sha256_file(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest.with_suffix(".manifest.json"), manifest)
    return manifest


def declare_tennis_orderbook_capability(cfg: RollerConfig, tour: str, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    cap = {
        "sport": tour,
        "availability": "SOURCE_UNAVAILABLE",
        "historical_l2": "SOURCE_UNAVAILABLE",
        "snapshot_rows": 0,
        "snapshot_note": "Canonical tennis orderbook is absent. Not historical L2 and not fills.",
        "depth": "NONE",
        "top_of_book": "NONE",
        "market_data_basis": "ONE_MINUTE_CANDLE",
        "updated_at": now_utc_iso(),
    }
    dest = orderbook_capability_path(cfg, tour, season)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, cap)
    readme = warehouse_v0_readme_path(cfg, tour, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    return cap


def assert_tennis_layout_contract(root: Path) -> None:
    tradable = root / "observations" / "basis=tradable_yes_bid"
    if not tradable.is_dir():
        raise ValueError("tennis warehouse must contain observations/basis=tradable_yes_bid")
    last_trade = root / "observations" / "basis=last_trade_print"
    if not last_trade.is_dir():
        raise ValueError("tennis warehouse must contain observations/basis=last_trade_print")
    if orderbook_partition_exists(root):
        raise ValueError("tennis selected warehouse must not contain an orderbook parquet partition")


def _copy_month_dir(src: Path, dest: Path, *, sort_cols: list[str], fingerprint_cols: list[str]) -> dict[str, int]:
    dest.mkdir(parents=True, exist_ok=True)
    months: dict[str, int] = {}
    for path in list_month_parquets(src):
        month = month_key(path)
        frame = pd.read_parquet(path)
        write_sorted_parquet(frame, month_parquet(dest, month), sort_cols=sort_cols)
        written = pd.read_parquet(month_parquet(dest, month))
        fp, n = fingerprint_frame(frame, [c for c in fingerprint_cols if c in frame.columns])
        fp2, n2 = fingerprint_frame(written, [c for c in fingerprint_cols if c in written.columns])
        if fp != fp2 or n != n2:
            raise ValueError(f"fingerprint mismatch month {month} in {src}")
        months[month] = n
    return months


def write_tennis_warehouse(cfg: RollerConfig, tour: str, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_root(cfg, tour, season)
    dest.mkdir(parents=True, exist_ok=True)
    identity = read_csv_optional(identity_artifact_path(cfg), IDENTITY_ARTIFACT_COLUMNS)
    games = project_games(identity, sport=tour)
    write_sorted_parquet(games, dest / "games" / "games.parquet", sort_cols=GAME_SORT)

    v0 = warehouse_v0_root(cfg, tour, season)
    markets_src = v0 / "markets.parquet"
    markets = pd.read_parquet(markets_src) if markets_src.is_file() else pd.DataFrame()
    write_sorted_parquet(markets, dest / "markets" / "markets.parquet", sort_cols=MARKET_SORT)

    links = load_tennis_crosswalk(cfg, tour)
    write_sorted_parquet(links, dest / "game_market_links" / "links.parquet", sort_cols=LINK_SORT)

    settle_src = v0 / "settlements.parquet"
    settles = pd.read_parquet(settle_src) if settle_src.is_file() else pd.DataFrame()
    write_sorted_parquet(settles, dest / "settlements" / "settlements.parquet", sort_cols=SETTLE_SORT)

    candle_months = _copy_month_dir(
        v0 / "observations" / "basis=tradable_yes_bid",
        dest / "observations" / "basis=tradable_yes_bid",
        sort_cols=OBS_SORT,
        fingerprint_cols=OBS_FINGERPRINT_COLS,
    )
    last_months = _copy_month_dir(
        v0 / "observations" / "basis=last_trade_print",
        dest / "observations" / "basis=last_trade_print",
        sort_cols=OBS_SORT,
        fingerprint_cols=list(LAST_TRADE_OBS_COLUMNS),
    )
    pbp_months = _copy_month_dir(
        v0 / "pbp",
        dest / "pbp",
        sort_cols=PBP_SORT,
        fingerprint_cols=list(PBP_FINGERPRINT_COLS),
    )
    assert_tennis_layout_contract(dest)
    (dest / "README.md").write_text(TENNIS_WAREHOUSE_README, encoding="utf-8")
    manifest = {
        "artifact": f"{tour.lower()}_warehouse",
        "sport": tour,
        "season": season,
        "observation_bases": ["TRADABLE_YES_BID", "LAST_TRADE_PRINT"],
        "observation_resolution": "1_MINUTE",
        "tick_data_available": False,
        "orderbook_data_available": False,
        "candle_pit_available": True,
        "candle_pit_field": "available_at",
        "pbp_pit_aligned_to_candles": False,
        "source_system": source_system_for(tour),
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "link_rule_version": LINK_RULE_VERSION,
        "games": int(len(games)),
        "markets": int(len(markets)),
        "links": int(len(links)),
        "settlements": int(len(settles)),
        "tradable_months": candle_months,
        "tradable_rows": int(sum(candle_months.values())),
        "last_trade_months": last_months,
        "last_trade_rows": int(sum(last_months.values())),
        "observation_rows": int(sum(candle_months.values())),
        "pbp_months": pbp_months,
        "pbp_rows": int(sum(pbp_months.values())),
        "warehouse_root": str(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest / "manifest.json", manifest)
    return manifest


def write_atp_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return write_tennis_warehouse(cfg, "ATP", season=season)


def write_wta_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return write_tennis_warehouse(cfg, "WTA", season=season)


def _observation_report(tour: str, basis: str, stats: ObservationBuild, out_dir: Path) -> dict[str, Any]:
    return {
        "sport": tour,
        "basis": basis,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "unlinked_rows": stats.unlinked_rows,
        "conflict_rows": stats.conflict_rows,
        "duplicate_keys": stats.duplicate_keys,
        "tickers": stats.tickers,
        "linked_tickers": stats.linked_tickers,
        "unlinked_tickers": stats.unlinked_tickers,
        "games_with_observations": stats.games_with_observations,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "canonical_widened": False,
    }


def _ingest_shared_tradable(
    cfg: RollerConfig,
    season: str,
    crosswalks: dict[str, pd.DataFrame],
    suite_months: dict[str, dict[str, pd.DataFrame]],
) -> dict[str, Any]:
    src_dir = cfg.dataset_path("ATP", season, "kalshi_candles")
    months = sorted(
        {month_key(p) for p in list_month_csvs(src_dir)}
        | set(suite_months.get("ATP", {}))
        | set(suite_months.get("WTA", {}))
    )
    stats = {tour: ObservationBuild() for tour in TOURS}
    tickers = {tour: set() for tour in TOURS}
    linked = {tour: set() for tour in TOURS}
    unlinked = {tour: set() for tour in TOURS}
    games = {tour: set() for tour in TOURS}
    out_dirs: dict[str, Path] = {}
    for tour in TOURS:
        out_dirs[tour] = warehouse_v0_root(cfg, tour, season) / "observations" / "basis=tradable_yes_bid"
        out_dirs[tour].mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, tour, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for month in months:
        canon_path = src_dir / f"month={month}.csv"
        shared = read_csv(canon_path) if canon_path.is_file() else pd.DataFrame()
        for tour in TOURS:
            raw = _union_by_key(
                _filter_ticker_prefix(shared, tour),
                _filter_ticker_prefix(suite_months.get(tour, {}).get(month, pd.DataFrame()), tour),
            )
            if raw.empty:
                continue
            projected = project_observation_frame(raw, crosswalks[tour])
            _update_tradable_stats(stats[tour], projected, month)
            tickers[tour].update(projected["ticker"].astype(str))
            linked[tour].update(projected.loc[projected["game_link_status"] == "LINKED", "ticker"].astype(str))
            unlinked[tour].update(projected.loc[projected["game_link_status"] == "UNLINKED", "ticker"].astype(str))
            games[tour].update(g for g in projected["internal_game_id"].astype(str) if g)
            projected.to_parquet(month_parquet(out_dirs[tour], month), index=False)
    reports: dict[str, Any] = {}
    for tour in TOURS:
        stats[tour].tickers = len(tickers[tour])
        stats[tour].linked_tickers = len(linked[tour])
        stats[tour].unlinked_tickers = len(unlinked[tour])
        stats[tour].games_with_observations = len(games[tour])
        stats[tour].markets_with_observations = stats[tour].tickers
        report = _observation_report(tour, ObservationBasis.TRADABLE_YES_BID.value, stats[tour], out_dirs[tour])
        write_json(out_dirs[tour] / "manifest.json", report)
        reports[tour] = report
    return reports


def _ingest_shared_last_trade(
    cfg: RollerConfig,
    season: str,
    crosswalks: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    src_dir = cfg.dataset_path("ATP", season, "kalshi_last_trade")
    stats = {tour: ObservationBuild() for tour in TOURS}
    tickers = {tour: set() for tour in TOURS}
    linked = {tour: set() for tour in TOURS}
    unlinked = {tour: set() for tour in TOURS}
    games = {tour: set() for tour in TOURS}
    out_dirs: dict[str, Path] = {}
    for tour in TOURS:
        out_dirs[tour] = warehouse_v0_root(cfg, tour, season) / "observations" / "basis=last_trade_print"
        out_dirs[tour].mkdir(parents=True, exist_ok=True)
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        shared = read_csv(path)
        for tour in TOURS:
            scoped = _filter_ticker_prefix(shared, tour)
            if scoped.empty:
                continue
            if "last_close_e4" in scoped.columns:
                scoped = scoped.loc[scoped["last_close_e4"].map(_text).ne("")].copy()
            if scoped.empty:
                continue
            projected = project_last_trade_frame(scoped, crosswalks[tour])
            st = stats[tour]
            st.months[month] = int(len(projected))
            st.rows += int(len(projected))
            st.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
            st.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
            st.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
            st.duplicate_keys += int((projected["duplicate_key"] == "1").sum())
            if not projected.empty:
                times = projected["available_at"].astype(str)
                lo, hi = times.min(), times.max()
                if not st.date_min or lo < st.date_min:
                    st.date_min = lo
                if not st.date_max or hi > st.date_max:
                    st.date_max = hi
            tickers[tour].update(projected["ticker"].astype(str))
            linked[tour].update(projected.loc[projected["game_link_status"] == "LINKED", "ticker"].astype(str))
            unlinked[tour].update(projected.loc[projected["game_link_status"] == "UNLINKED", "ticker"].astype(str))
            games[tour].update(g for g in projected["internal_game_id"].astype(str) if g)
            projected.to_parquet(month_parquet(out_dirs[tour], month), index=False)
    reports: dict[str, Any] = {}
    for tour in TOURS:
        stats[tour].tickers = len(tickers[tour])
        stats[tour].linked_tickers = len(linked[tour])
        stats[tour].unlinked_tickers = len(unlinked[tour])
        stats[tour].games_with_observations = len(games[tour])
        stats[tour].markets_with_observations = stats[tour].tickers
        report = _observation_report(tour, ObservationBasis.LAST_TRADE_PRINT.value, stats[tour], out_dirs[tour])
        write_json(out_dirs[tour] / "manifest.json", report)
        reports[tour] = report
    return reports


def _ingest_shared_pbp(cfg: RollerConfig, season: str, identity: pd.DataFrame) -> dict[str, Any]:
    src_dir = cfg.dataset_path("ATP", season, "pbp")
    indexes = {tour: _tennis_gid_index(identity, tour) for tour in TOURS}
    stats = {tour: PbpBuild() for tour in TOURS}
    games = {tour: set() for tour in TOURS}
    out_dirs: dict[str, Path] = {}
    for tour in TOURS:
        out_dirs[tour] = warehouse_v0_root(cfg, tour, season) / "pbp"
        out_dirs[tour].mkdir(parents=True, exist_ok=True)
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        shared = read_csv(path)
        for tour in TOURS:
            projected = project_tennis_pbp_frame(shared, indexes[tour], tour)
            st = stats[tour]
            st.months[month] = int(len(projected))
            st.rows += int(len(projected))
            st.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
            st.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
            st.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
            st.blank_event_timestamp += int(projected["event_timestamp"].astype(str).str.strip().eq("").sum())
            games[tour].update(g for g in projected["internal_game_id"].astype(str) if g)
            projected.to_parquet(month_parquet(out_dirs[tour], month), index=False)
    reports: dict[str, Any] = {}
    for tour in TOURS:
        stats[tour].games_with_pbp = len(games[tour])
        report = {
            "sport": tour,
            "rows": stats[tour].rows,
            "linked_rows": stats[tour].linked_rows,
            "conflict_rows": stats[tour].conflict_rows,
            "unlinked_rows": stats[tour].unlinked_rows,
            "blank_event_timestamp": stats[tour].blank_event_timestamp,
            "games_with_pbp": stats[tour].games_with_pbp,
            "months": stats[tour].months,
            "date_min": stats[tour].date_min,
            "date_max": stats[tour].date_max,
            "output_dir": str(out_dirs[tour]),
            "updated_at": now_utc_iso(),
            "pit_join_performed": False,
            "timestamps_invented": False,
            "pbp_pit_aligned_to_candles": False,
        }
        write_json(out_dirs[tour] / "manifest.json", report)
        reports[tour] = report
    return reports


def _assert_isolation_hashes(cfg: RollerConfig) -> dict[str, str]:
    from roller.warehouse.layout_v0 import crosswalk_path, sport_crosswalk_path

    nba = crosswalk_path(cfg)
    nba_hash = sha256_file(nba) if nba.is_file() else ""
    if nba_hash and nba_hash != NBA_CROSSWALK_SHA256:
        raise ValueError(f"NBA crosswalk hash changed: {nba_hash}")
    for other in ("NCAAB", "MLB"):
        path = sport_crosswalk_path(cfg, other)
        if tennis_crosswalk_path(cfg, "ATP").resolve() == path.resolve():
            raise ValueError("ATP crosswalk must not share another desk path")
        if tennis_crosswalk_path(cfg, "WTA").resolve() == path.resolve():
            raise ValueError("WTA crosswalk must not share another desk path")
    if tennis_crosswalk_path(cfg, "ATP").resolve() == nba.resolve():
        raise ValueError("ATP GameMarketLink must not share the NBA crosswalk path")
    if tennis_crosswalk_path(cfg, "WTA").resolve() == nba.resolve():
        raise ValueError("WTA GameMarketLink must not share the NBA crosswalk path")
    return {"nba_crosswalk_sha256": nba_hash}


def ingest_tennis_warehouses(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """One shared-tree read, then isolated ATP and WTA writes."""
    games_path = _shared_games_path(cfg, season)
    markets_path = _shared_markets_path(cfg, season)
    games = read_csv(games_path) if games_path.is_file() else pd.DataFrame()
    canonical_markets = read_csv(markets_path) if markets_path.is_file() else pd.DataFrame()
    identity = verify_tennis_identities(cfg, tours=TOURS, season=season, games=games, markets=canonical_markets, write=True)
    ident_frame = read_csv_optional(identity_artifact_path(cfg), IDENTITY_ARTIFACT_COLUMNS)

    suite_markets: dict[str, pd.DataFrame] = {}
    try:
        wh = _suite_root(cfg, season)
        from roller.canonical.markets import markets_parquet

        for tour in TOURS:
            src = markets_parquet(wh, tour.lower())
            suite_markets[tour] = pd.read_parquet(src) if src.is_file() else pd.DataFrame()
    except (KeyError, FileNotFoundError, OSError):
        wh = _suite_root(cfg, season)
        suite_markets = {tour: pd.DataFrame() for tour in TOURS}

    links_rep: dict[str, Any] = {}
    crosswalks: dict[str, pd.DataFrame] = {}
    for tour in TOURS:
        links_rep[tour] = build_and_write_tennis_market_links(
            cfg,
            tour,
            season=season,
            identity=ident_frame,
            suite=suite_markets.get(tour),
            canonical=_filter_ticker_prefix(canonical_markets, tour),
        )
        crosswalks[tour] = load_tennis_crosswalk(cfg, tour)

    suite_candle_months = {
        "ATP": _load_suite_candle_months(wh, "atp"),
        "WTA": _load_suite_candle_months(wh, "wta"),
    }
    tradable_rep = _ingest_shared_tradable(cfg, season, crosswalks, suite_candle_months)
    last_rep = _ingest_shared_last_trade(cfg, season, crosswalks)
    pbp_rep = _ingest_shared_pbp(cfg, season, ident_frame)
    settle_rep: dict[str, Any] = {}
    orderbook_rep: dict[str, Any] = {}
    warehouse_rep: dict[str, Any] = {}
    for tour in TOURS:
        settlements = build_tennis_settlements(
            cfg, tour, season=season, markets=suite_markets.get(tour), crosswalk=crosswalks[tour]
        )
        settle_rep[tour] = write_tennis_settlements(cfg, settlements, tour, season=season)
        orderbook_rep[tour] = declare_tennis_orderbook_capability(cfg, tour, season=season)
        warehouse_rep[tour] = write_tennis_warehouse(cfg, tour, season=season)
    isolation = _assert_isolation_hashes(cfg)
    return {
        "sport": "TENNIS",
        "identity": identity,
        "links": links_rep,
        "tradable": tradable_rep,
        "last_trade": last_rep,
        "pbp": pbp_rep,
        "settlements": settle_rep,
        "orderbook": orderbook_rep,
        "warehouse": warehouse_rep,
        "link_audit": {tour: audit_link_frame(crosswalks[tour]) for tour in TOURS},
        "settlement_coverage": {
            tour: coverage_report(
                pd.read_parquet(warehouse_v0_root(cfg, tour, season) / "settlements.parquet")
            )
            for tour in TOURS
        },
        **isolation,
        "nba_crosswalk_sha256_expected": NBA_CROSSWALK_SHA256,
    }


def ingest_atp_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return ingest_tennis_warehouses(cfg, season=season)["warehouse"]["ATP"]


def ingest_wta_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return ingest_tennis_warehouses(cfg, season=season)["warehouse"]["WTA"]


def verify_tennis_desk(cfg: RollerConfig, tour: str, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_root(cfg, tour, season)
    assert_tennis_layout_contract(dest)
    from roller.warehouse.coverage import get_catalog
    from roller.warehouse.layout_v0 import crosswalk_path
    from roller.warehouse.research_compiler import compile_research

    isolation = _assert_isolation_hashes(cfg)
    catalog = get_catalog(cfg, sport=tour, season=season)
    question = ATP_PHASE20_QUESTION if tour == "ATP" else WTA_PHASE20_QUESTION
    plan = compile_research(question, cfg)
    return {
        "sport": tour,
        "warehouse_root": str(dest),
        "tradable_yes_bid_count": catalog.observations.get("tradable_yes_bid_count"),
        "last_trade_print_count": catalog.observations.get("last_trade_print_count"),
        "phase20_status": plan.status.value,
        "phase20_basis": plan.observation_basis,
        "crosswalk": str(tennis_crosswalk_path(cfg, tour)),
        "nba_crosswalk": str(crosswalk_path(cfg)),
        "nba_crosswalk_sha256": isolation["nba_crosswalk_sha256"],
        "orderbook_partition": False,
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "golden_721_rewritten": False,
        "golden_290_rewritten": False,
        "golden_554_rewritten": False,
        "golden_1661_rewritten": False,
    }


def verify_atp_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return verify_tennis_desk(cfg, "ATP", season=season)


def verify_wta_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return verify_tennis_desk(cfg, "WTA", season=season)


def phase20_question(tour: str = "ATP") -> ResearchQuestion:
    return ATP_PHASE20_QUESTION if tour == "ATP" else WTA_PHASE20_QUESTION
