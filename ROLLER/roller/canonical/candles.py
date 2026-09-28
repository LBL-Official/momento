"""Canonical monthly Kalshi candle CSVs. Observations only — never fills."""

from __future__ import annotations

import pandas as pd

from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.ingest.games import load_sport_games
from roller.ingest.kalshi import candles_root, iter_candle_frames, team_side
from roller.ingest.pointers import pointer_record, write_manifest
from roller.io_csv import write_csv
from roller.paths import canonical_dir, raw_dir
from roller.research.quality import candle_quality_fields
from roller.timeutil import now_utc_iso

CANDLE_COLUMNS = [
    "internal_game_id",
    "ticker",
    "team_side",
    "candle_timestamp",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
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


def canonicalize_candles(
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

    out_dir = canonical_dir(cfg.root, sport, path_key) / "kalshi_candles"
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()

    pointers = [pointer_record(candles_root(wh, sport), "candles_1m_dir")]
    total = 0
    wh_sport = cfg.season_meta(sport, season)["warehouse_sport"]
    for month, frame in iter_candle_frames(wh, wh_sport):
        if frame.empty or "ticker" not in frame.columns:
            continue
        gid = frame["ticker"].astype(str).map(ticker_to_id)
        keep = gid.notna()
        if not keep.any():
            continue
        sub = frame.loc[keep].copy()
        sub["internal_game_id"] = gid.loc[keep].to_numpy()
        ends = _iso(sub["end_time"]) if "end_time" in sub.columns else pd.Series([""] * len(sub), index=sub.index)
        sides = [
            team_side(t, *ticker_to_sides.get(str(t), ("", "")))
            for t in sub["ticker"].tolist()
        ]
        bid_c = _int_str(sub.get("yes_bid_close_e4", pd.Series(index=sub.index)))
        ask_c = _int_str(sub.get("yes_ask_close_e4", pd.Series(index=sub.index)))
        vol = _int_str(sub.get("volume_hundredths", pd.Series(index=sub.index)))
        valid_src = sub["is_valid"] if "is_valid" in sub.columns else pd.Series([None] * len(sub), index=sub.index)
        qfields = [
            candle_quality_fields(b, a, v, iv)
            for b, a, v, iv in zip(bid_c.tolist(), ask_c.tolist(), vol.tolist(), valid_src.tolist())
        ]
        out = pd.DataFrame(
            {
                "internal_game_id": sub["internal_game_id"].to_numpy(),
                "ticker": sub["ticker"].astype(str).to_numpy(),
                "team_side": sides,
                "candle_timestamp": ends.to_numpy(),
                "event_timestamp": ends.to_numpy(),
                "available_at": ends.to_numpy(),
                "ingested_at": now,
                "yes_bid_open": _int_str(sub.get("yes_bid_open_e4", pd.Series(index=sub.index))),
                "yes_bid_high": _int_str(sub.get("yes_bid_high_e4", pd.Series(index=sub.index))),
                "yes_bid_low": _int_str(sub.get("yes_bid_low_e4", pd.Series(index=sub.index))),
                "yes_bid_close": bid_c,
                "yes_ask_open": _int_str(sub.get("yes_ask_open_e4", pd.Series(index=sub.index))),
                "yes_ask_high": _int_str(sub.get("yes_ask_high_e4", pd.Series(index=sub.index))),
                "yes_ask_low": _int_str(sub.get("yes_ask_low_e4", pd.Series(index=sub.index))),
                "yes_ask_close": ask_c,
                "volume": vol,
                "is_valid": [q["is_valid"] for q in qfields],
                "spread_e4": [q["spread_e4"] for q in qfields],
                "uncrossed": [q["uncrossed"] for q in qfields],
                "spread_ok": [q["spread_ok"] for q in qfields],
                "volume_positive": [q["volume_positive"] for q in qfields],
                "tradable_cross": [q["tradable_cross"] for q in qfields],
                "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                "source_dataset": "warehouse_candles_1m",
                "source_file_hash": "",
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )
        out = out.sort_values(
            ["internal_game_id", "ticker", "candle_timestamp"], kind="mergesort"
        ).reset_index(drop=True)
        write_csv(out_dir / f"month={month}.csv", out, CANDLE_COLUMNS)
        total += len(out)

    write_manifest(raw_dir(cfg.root, sport, path_key) / "kalshi" / "manifest.json", pointers)
    return total
