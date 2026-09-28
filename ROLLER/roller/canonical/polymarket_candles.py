"""Canonical Polymarket 1-minute last-trade samples.

market_data_type = PRICE_HISTORY_LAST
Never copies last price into yes_bid / yes_ask.
Never writes unmapped events into candle partitions.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from roller.admin import load_identity
from roller.canonical.polymarket_match import (
    MAP_COLUMNS,
    crosswalk_to_json,
    mapped_token_jobs,
    match_events,
)
from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.ingest.games import load_sport_games
from roller.ingest.pointers import pointer_record, write_manifest
from roller.ingest.polymarket import (
    fetch_prices_history,
    load_raw_events,
    load_raw_prices,
    load_sport_warehouse,
    price_to_e4,
    sample_iso,
    sample_window,
    warehouse_polymarket_candles,
    warehouse_polymarket_crosswalk,
    write_raw_events,
    write_raw_prices,
)
from roller.io_csv import write_csv, write_json
from roller.paths import canonical_dir, raw_dir
from roller.timeutil import now_utc_iso, parse_utc

CANDLE_COLUMNS = [
    "internal_game_id",
    "token_id",
    "ticker",
    "team_side",
    "kalshi_ticker",
    "candle_timestamp",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "last_open_e4",
    "last_high_e4",
    "last_low_e4",
    "last_close_e4",
    "volume",
    "is_valid",
    "spread_e4",
    "uncrossed",
    "spread_ok",
    "volume_positive",
    "tradable_cross",
    "market_data_type",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]

MARKET_COLUMNS = [
    "internal_game_id",
    "token_id",
    "ticker",
    "team_side",
    "kalshi_ticker",
    "polymarket_event_id",
    "polymarket_event_slug",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "mapping_status",
    "mapping_method",
    "source_dataset",
    "pipeline_version",
    "derived_at",
]


def _empty_candles() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDLE_COLUMNS)


def points_to_rows(
    points: list[dict[str, Any]],
    job: dict[str, str],
    *,
    ingested_at: str,
    pipeline_version: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pt in points:
        ts = sample_iso(int(pt["t"]))
        px = price_to_e4(pt.get("p"))
        if not px:
            continue
        rows.append(
            {
                "internal_game_id": job["internal_game_id"],
                "token_id": job["token_id"],
                "ticker": job["ticker"],
                "team_side": job["team_side"],
                "kalshi_ticker": job.get("kalshi_ticker") or "",
                "candle_timestamp": ts,
                "event_timestamp": ts,
                "available_at": ts,
                "ingested_at": ingested_at,
                "last_open_e4": px,
                "last_high_e4": px,
                "last_low_e4": px,
                "last_close_e4": px,
                "volume": "",
                "is_valid": "",
                "spread_e4": "",
                "uncrossed": "0",
                "spread_ok": "0",
                "volume_positive": "0",
                "tradable_cross": "0",
                "market_data_type": "PRICE_HISTORY_LAST",
                "source_dataset": "polymarket_prices_history_1m",
                "source_file_hash": "",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    return rows


def write_month_frames(out_dir: Path, rows: list[dict[str, str]], columns: list[str]) -> int:
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()
        for old in out_dir.glob("*.parquet"):
            old.unlink()
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        month = str(row.get("candle_timestamp") or "")[:7]
        if month:
            by_month[month].append(row)
    total = 0
    for month, items in sorted(by_month.items()):
        frame = pd.DataFrame(items)
        frame = frame.sort_values(
            ["internal_game_id", "token_id", "candle_timestamp"], kind="mergesort"
        ).reset_index(drop=True)
        write_csv(out_dir / f"month={month}.csv", frame, columns)
        total += len(frame)
    return total


def write_warehouse_parquet(warehouse: Path, sport: str, rows: list[dict[str, str]]) -> int:
    root = warehouse_polymarket_candles(warehouse, sport)
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        month = str(row.get("candle_timestamp") or "")[:7]
        if month:
            by_month[month].append(row)
    total = 0
    for month, items in sorted(by_month.items()):
        dest = root / f"month={month}"
        dest.mkdir(parents=True, exist_ok=True)
        for old in dest.glob("*"):
            old.unlink()
        frame = pd.DataFrame(items)
        frame = frame.sort_values(
            ["internal_game_id", "token_id", "candle_timestamp"], kind="mergesort"
        ).reset_index(drop=True)
        frame.to_parquet(dest / "candles.parquet", index=False)
        total += len(frame)
    return total


def build_crosswalk(
    cfg: RollerConfig,
    sport: str,
    season: str,
    events: list[dict[str, Any]],
    identity: pd.DataFrame | None = None,
) -> pd.DataFrame:
    ident = identity if identity is not None else load_identity(cfg)
    ident = _attach_scheduled_start(cfg, sport, season, ident)
    return match_events(cfg, sport, season, events, ident)


def _attach_scheduled_start(
    cfg: RollerConfig, sport: str, season: str, identity: pd.DataFrame
) -> pd.DataFrame:
    if identity.empty:
        return identity
    try:
        from roller.admin import load_dataset

        games = load_dataset(cfg, sport, season, "games")
    except (FileNotFoundError, KeyError):
        return identity
    if games.empty or "scheduled_start" not in games.columns:
        return identity
    starts = games[["internal_game_id", "scheduled_start"]].drop_duplicates("internal_game_id")
    out = identity.merge(starts, on="internal_game_id", how="left")
    return out


def persist_crosswalk(cfg: RollerConfig, sport: str, season: str, crosswalk: pd.DataFrame) -> Path:
    _, _, wh = load_sport_games(cfg, sport, season)
    path_key = cfg.season_meta(sport, season)["path_key"]
    wh_path = warehouse_polymarket_crosswalk(wh, sport)
    merged = _merge_map_frames(_read_json_map(wh_path), crosswalk)
    write_json(wh_path, crosswalk_to_json(merged))
    write_csv(cfg.root / "meta" / "polymarket_game_map.csv", _merge_map(cfg, crosswalk), MAP_COLUMNS)
    write_csv(
        canonical_dir(cfg.root, sport, path_key) / "polymarket_markets.csv",
        _markets_frame(crosswalk, cfg),
        MARKET_COLUMNS,
    )
    return wh_path


def _read_json_map(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=MAP_COLUMNS)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        return pd.DataFrame(columns=MAP_COLUMNS)
    df = pd.DataFrame(raw)
    for col in MAP_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[MAP_COLUMNS]


def _merge_map_frames(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if incoming.empty:
        return existing if not existing.empty else pd.DataFrame(columns=MAP_COLUMNS)
    keys = set(zip(incoming["sport"].astype(str), incoming["season"].astype(str)))
    if not existing.empty:
        mask = existing.apply(lambda r: (str(r["sport"]), str(r["season"])) not in keys, axis=1)
        existing = existing.loc[mask]
    out = pd.concat([existing, incoming[MAP_COLUMNS]], ignore_index=True)
    return out.sort_values(["sport", "game_date", "internal_game_id", "polymarket_event_id"]).reset_index(drop=True)


def _merge_map(cfg: RollerConfig, incoming: pd.DataFrame) -> pd.DataFrame:
    path = cfg.root / "meta" / "polymarket_game_map.csv"
    existing = pd.DataFrame(columns=MAP_COLUMNS)
    if path.is_file():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False)
        for col in MAP_COLUMNS:
            if col not in existing.columns:
                existing[col] = ""
        existing = existing[MAP_COLUMNS]
    return _merge_map_frames(existing, incoming)


def _markets_frame(crosswalk: pd.DataFrame, cfg: RollerConfig) -> pd.DataFrame:
    now = now_utc_iso()
    rows: list[dict[str, str]] = []
    mapped = crosswalk[crosswalk["mapping_status"] == MAPPING_MAPPED] if not crosswalk.empty else crosswalk
    for rec in mapped.to_dict("records"):
        start = str(rec.get("polymarket_start_time") or rec.get("game_date") or now)
        for side, token_key, kalshi_key, team_key in (
            ("home", "token_yes_home", "kalshi_market_yes_home", "home_team_id"),
            ("away", "token_yes_away", "kalshi_market_yes_away", "away_team_id"),
        ):
            token = str(rec.get(token_key) or "")
            if not token:
                continue
            rows.append(
                {
                    "internal_game_id": str(rec.get("internal_game_id") or ""),
                    "token_id": token,
                    "ticker": f"{rec.get('polymarket_event_slug')}-{rec.get(team_key)}",
                    "team_side": side,
                    "kalshi_ticker": str(rec.get(kalshi_key) or ""),
                    "polymarket_event_id": str(rec.get("polymarket_event_id") or ""),
                    "polymarket_event_slug": str(rec.get("polymarket_event_slug") or ""),
                    "event_timestamp": start,
                    "available_at": start,
                    "ingested_at": now,
                    "mapping_status": str(rec.get("mapping_status") or ""),
                    "mapping_method": str(rec.get("mapping_method") or ""),
                    "source_dataset": "polymarket_gamma_moneyline",
                    "pipeline_version": cfg.pipeline_version,
                    "derived_at": now,
                }
            )
    if not rows:
        return pd.DataFrame(columns=MARKET_COLUMNS)
    return pd.DataFrame(rows)[MARKET_COLUMNS]


def canonicalize_polymarket_candles(
    cfg: RollerConfig,
    sport: str,
    season: str,
    *,
    identity: pd.DataFrame | None = None,
    download: bool = False,
    http_get=None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _, _, wh = load_sport_games(cfg, sport, season)
    path_key = cfg.season_meta(sport, season)["path_key"]
    raw_events = events if events is not None else load_raw_events(wh, sport)
    ident = identity if identity is not None else load_identity(cfg)
    crosswalk = build_crosswalk(cfg, sport, season, raw_events, ident)
    persist_crosswalk(cfg, sport, season, crosswalk)
    jobs = mapped_token_jobs(crosswalk)
    now = now_utc_iso()
    rows: list[dict[str, str]] = []
    downloaded = 0
    for job in jobs:
        points = load_raw_prices(wh, sport, job["token_id"])
        if download and not points:
            start = parse_utc(job.get("start_time"))
            if start is None:
                continue
            win_start, win_end = sample_window(start, cfg=cfg)
            points = fetch_prices_history(
                job["token_id"], win_start, win_end, cfg=cfg, http_get=http_get
            )
            write_raw_prices(wh, sport, job["token_id"], points)
            downloaded += 1
        rows.extend(points_to_rows(points, job, ingested_at=now, pipeline_version=cfg.pipeline_version))
    out_dir = canonical_dir(cfg.root, sport, path_key) / "polymarket_candles"
    n = write_month_frames(out_dir, rows, CANDLE_COLUMNS)
    write_warehouse_parquet(wh, sport, rows)
    write_manifest(
        raw_dir(cfg.root, sport, path_key) / "polymarket" / "manifest.json",
        [pointer_record(warehouse_polymarket_crosswalk(wh, sport), "polymarket_crosswalk")],
    )
    mapped_n = int((crosswalk["mapping_status"] == MAPPING_MAPPED).sum()) if not crosswalk.empty else 0
    return {
        "events": len(raw_events),
        "mapped": mapped_n,
        "tokens": len(jobs),
        "candles": n,
        "downloaded_tokens": downloaded,
    }


def ingest_polymarket_sport(
    cfg: RollerConfig,
    sport: str,
    season: str,
    *,
    discover: bool = True,
    download: bool = True,
    canonicalize: bool = True,
    http_get=None,
    max_events: int | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from roller.ingest.polymarket import events_by_slugs, identity_slugs, list_events

    _, _, wh = load_sport_games(cfg, sport, season)
    report: dict[str, Any] = {"sport": sport, "season": season}
    found = events
    if discover and found is None:
        ident = load_identity(cfg)
        sub = ident[(ident["sport"] == sport) & (ident["season"] == season)]
        slugs: list[str] = []
        for rec in sub.to_dict("records"):
            slugs.extend(
                identity_slugs(
                    sport,
                    str(rec.get("game_date") or ""),
                    str(rec.get("away_team_id") or ""),
                    str(rec.get("home_team_id") or ""),
                )
            )
        seen: set[str] = set()
        uniq = []
        for s in slugs:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        found = []
        batch = 8
        for i in range(0, len(uniq) if max_events is None else min(len(uniq), max_events * 4), batch):
            chunk = uniq[i : i + batch]
            if not chunk:
                break
            try:
                found.extend(events_by_slugs(chunk, cfg=cfg, http_get=http_get))
            except Exception:
                continue
            if max_events is not None and len(found) >= max_events:
                found = found[:max_events]
                break
        if not found:
            found = list_events(cfg, sport, season, http_get=http_get, max_events=max_events)
        write_raw_events(wh, sport, found)
    elif found is not None:
        write_raw_events(wh, sport, found)
    report["discovered"] = len(found or load_raw_events(wh, sport))
    if canonicalize or download:
        stats = canonicalize_polymarket_candles(
            cfg,
            sport,
            season,
            download=download,
            http_get=http_get,
            events=found,
        )
        report.update(stats)
    return report
