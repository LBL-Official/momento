"""Kalshi trades tape as prints. Not fills. Not maker queue position."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.ingest.games import load_sport_games
from roller.ingest.kalshi import team_side
from roller.ingest.pointers import pointer_record, write_manifest
from roller.io_csv import write_csv
from roller.paths import canonical_dir, raw_dir
from roller.timeutil import now_utc_iso

TRADE_COLUMNS = [
    "internal_game_id",
    "trade_id",
    "ticker",
    "team_side",
    "yes_price_e4",
    "no_price_e4",
    "quantity_hundredths",
    "taker_outcome_side",
    "taker_book_side",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "market_data_type",
    "source_dataset",
    "pipeline_version",
    "derived_at",
]


def trades_root(warehouse: Path, sport: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "trades"


def iter_trade_frames(warehouse: Path, sport: str) -> Iterator[tuple[str, pd.DataFrame]]:
    root = trades_root(warehouse, sport)
    if not root.is_dir():
        return
    months = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("month="))
    for month_dir in months:
        month = month_dir.name.split("=", 1)[-1]
        files = sorted(month_dir.glob("*.parquet"))
        if not files:
            continue
        frames = [pd.read_parquet(f) for f in files]
        if frames:
            yield month, pd.concat(frames, ignore_index=True)


def _iso(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        s = pd.to_datetime(series, utc=True)
        return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return series.astype(str)


def _int_str(series: pd.Series) -> pd.Series:
    out = pd.Series([""] * len(series), index=series.index, dtype=object)
    mask = series.notna()
    out.loc[mask] = series.loc[mask].astype("int64").astype(str)
    return out


def canonicalize_trades(
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
    ticker_to_sides: dict[str, tuple[str, str]] = {}
    for r in mapped.to_dict("records"):
        hid, aid = r["home_team_id"], r["away_team_id"]
        for t in (r.get("kalshi_market_yes_home"), r.get("kalshi_market_yes_away")):
            if t:
                ticker_to_id[str(t)] = r["internal_game_id"]
                ticker_to_sides[str(t)] = (hid, aid)

    out_dir = canonical_dir(cfg.root, sport, path_key) / "kalshi_trades"
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    wh_sport = cfg.season_meta(sport, season)["warehouse_sport"]
    pointers = [pointer_record(trades_root(wh, wh_sport), "trades_dir")]
    write_manifest(raw_dir(cfg.root, sport, path_key) / "kalshi" / "trades_manifest.json", pointers)
    total = 0
    for month, frame in iter_trade_frames(wh, wh_sport):
        if frame.empty or "ticker" not in frame.columns:
            continue
        gid = frame["ticker"].astype(str).map(ticker_to_id)
        keep = gid.notna()
        if not keep.any():
            continue
        sub = frame.loc[keep].copy()
        ts = _iso(sub["timestamp"]) if "timestamp" in sub.columns else pd.Series([""] * len(sub), index=sub.index)
        sides = [team_side(t, *ticker_to_sides.get(str(t), ("", ""))) for t in sub["ticker"].tolist()]
        out = pd.DataFrame(
            {
                "internal_game_id": gid.loc[keep].to_numpy(),
                "trade_id": sub.get("trade_id", pd.Series([""] * len(sub), index=sub.index)).astype(str).to_numpy(),
                "ticker": sub["ticker"].astype(str).to_numpy(),
                "team_side": sides,
                "yes_price_e4": _int_str(sub.get("yes_price_e4", pd.Series(index=sub.index))).to_numpy(),
                "no_price_e4": _int_str(sub.get("no_price_e4", pd.Series(index=sub.index))).to_numpy(),
                "quantity_hundredths": _int_str(sub.get("quantity_hundredths", pd.Series(index=sub.index))).to_numpy(),
                "taker_outcome_side": sub.get("taker_outcome_side", pd.Series([""] * len(sub), index=sub.index)).fillna("").astype(str).to_numpy(),
                "taker_book_side": sub.get("taker_book_side", pd.Series([""] * len(sub), index=sub.index)).fillna("").astype(str).to_numpy(),
                "event_timestamp": ts.to_numpy(),
                "available_at": ts.to_numpy(),
                "ingested_at": now,
                "market_data_type": "TRADE_PRINT",
                "source_dataset": "warehouse_trades",
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )
        out = out.sort_values(["internal_game_id", "available_at", "trade_id"], kind="mergesort").reset_index(drop=True)
        write_csv(out_dir / f"month={month}.csv", out, TRADE_COLUMNS)
        total += len(out)
    return total
