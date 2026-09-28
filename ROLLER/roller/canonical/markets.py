"""Kalshi market catalog + ticker expiration. W is not box home_win."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.ingest.games import load_sport_games
from roller.ingest.kalshi import team_side
from roller.ingest.pointers import pointer_record, write_manifest
from roller.io_csv import write_csv
from roller.paths import canonical_dir, raw_dir
from roller.research.first80 import settled_yes
from roller.timeutil import now_utc_iso

MARKET_COLUMNS = [
    "internal_game_id",
    "ticker",
    "event_id",
    "event_ticker",
    "team_side",
    "result",
    "settlement_value_e4",
    "kalshi_yes_settled",
    "close_time",
    "expiration_time",
    "settlement_time",
    "event_timestamp",
    "available_at",
    "result_available_at",
    "ingested_at",
    "source_dataset",
    "pipeline_version",
    "derived_at",
]


def markets_parquet(warehouse: Path, sport: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "markets" / "markets.parquet"


def _iso(value) -> str:
    if value in (None, ""):
        return ""
    if hasattr(value, "strftime"):
        try:
            return pd.Timestamp(value, tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            return str(value)
    text = str(value).strip()
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def canonicalize_markets(
    cfg: RollerConfig,
    sport: str,
    season: str,
    identity: pd.DataFrame,
) -> int:
    _, _, wh = load_sport_games(cfg, sport, season)
    path_key = cfg.season_meta(sport, season)["path_key"]
    now = now_utc_iso()
    mapped = identity[
        (identity["sport"] == sport)
        & (identity["season"] == season)
        & (identity["mapping_status"] == MAPPING_MAPPED)
    ]
    ticker_to_id: dict[str, str] = {}
    ticker_to_event: dict[str, str] = {}
    ticker_to_sides: dict[str, tuple[str, str]] = {}
    for r in mapped.to_dict("records"):
        hid, aid = r["home_team_id"], r["away_team_id"]
        ev = r.get("event_ticker") or ""
        for t in (r.get("kalshi_market_yes_home"), r.get("kalshi_market_yes_away")):
            if t:
                ticker_to_id[str(t)] = r["internal_game_id"]
                ticker_to_event[str(t)] = ev
                ticker_to_sides[str(t)] = (hid, aid)

    src = markets_parquet(wh, cfg.season_meta(sport, season)["warehouse_sport"])
    out = canonical_dir(cfg.root, sport, path_key) / "kalshi_markets.csv"
    pointers = [pointer_record(src, "markets_parquet")] if src.is_file() else []
    write_manifest(raw_dir(cfg.root, sport, path_key) / "kalshi" / "markets_manifest.json", pointers)
    if not src.is_file():
        write_csv(out, pd.DataFrame(columns=MARKET_COLUMNS), MARKET_COLUMNS)
        return 0
    frame = pd.read_parquet(src)
    if frame.empty or "ticker" not in frame.columns:
        write_csv(out, pd.DataFrame(columns=MARKET_COLUMNS), MARKET_COLUMNS)
        return 0
    gid = frame["ticker"].astype(str).map(ticker_to_id)
    keep = gid.notna()
    if not keep.any():
        write_csv(out, pd.DataFrame(columns=MARKET_COLUMNS), MARKET_COLUMNS)
        return 0
    sub = frame.loc[keep].copy()
    rows = []
    for rec in sub.to_dict("records"):
        ticker = str(rec.get("ticker") or "")
        close = _iso(rec.get("close_time"))
        exp = _iso(rec.get("expiration_time"))
        settle = _iso(rec.get("settlement_time"))
        result = rec.get("result") or ""
        sve = rec.get("settlement_value_e4")
        sve_s = "" if sve in (None, "") else str(int(sve))
        result_at = settle or close or exp
        rows.append(
            {
                "internal_game_id": ticker_to_id[ticker],
                "ticker": ticker,
                "event_id": rec.get("event_id") or "",
                "event_ticker": ticker_to_event.get(ticker, ""),
                "team_side": team_side(ticker, *ticker_to_sides.get(ticker, ("", ""))),
                "result": result,
                "settlement_value_e4": sve_s,
                "kalshi_yes_settled": settled_yes(result, sve),
                "close_time": close,
                "expiration_time": exp,
                "settlement_time": settle,
                "event_timestamp": close or exp,
                "available_at": close or exp or now,
                "result_available_at": result_at,
                "ingested_at": now,
                "source_dataset": "warehouse_markets",
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=MARKET_COLUMNS)
    else:
        df = df.sort_values(["internal_game_id", "ticker"], kind="mergesort").reset_index(drop=True)
        df = df[MARKET_COLUMNS]
    write_csv(out, df, MARKET_COLUMNS)
    return len(df)
