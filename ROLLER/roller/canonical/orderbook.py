"""Canonical forward-only Kalshi orderbook snapshots. No historical L2 backfill."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.ingest.kalshi import team_side
from roller.ingest.orderbook import parse_orderbook_payload
from roller.io_csv import write_csv
from roller.paths import canonical_dir, raw_dir
from roller.timeutil import now_utc_iso

ORDERBOOK_COLUMNS = [
    "internal_game_id",
    "ticker",
    "team_side",
    "captured_at",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "best_yes_bid_e4",
    "best_no_bid_e4",
    "yes_levels",
    "no_levels",
    "yes_dollars_json",
    "no_dollars_json",
    "market_data_type",
    "source_dataset",
    "pipeline_version",
    "derived_at",
    "note",
]


def raw_orderbook_dir(cfg: RollerConfig, sport: str, season: str) -> Path:
    path_key = cfg.season_meta(sport, season)["path_key"]
    return raw_dir(cfg.root, sport, path_key) / "kalshi" / "orderbook"


def snapshot_row(
    cfg: RollerConfig,
    *,
    sport: str,
    season: str,
    ticker: str,
    captured_at: str,
    payload: dict,
    identity: pd.DataFrame | None = None,
) -> dict[str, str]:
    parsed = parse_orderbook_payload(payload)
    gid = ""
    sides = ("", "")
    if identity is not None and not identity.empty:
        mapped = identity[(identity["sport"] == sport) & (identity["season"] == season)]
        if "mapping_status" in mapped.columns:
            mapped = mapped[mapped["mapping_status"] == MAPPING_MAPPED]
        for r in mapped.to_dict("records"):
            if ticker in {r.get("kalshi_market_yes_home"), r.get("kalshi_market_yes_away")}:
                gid = r["internal_game_id"]
                sides = (r.get("home_team_id") or "", r.get("away_team_id") or "")
                break
    return {
        "internal_game_id": gid,
        "ticker": ticker,
        "team_side": team_side(ticker, *sides) if sides[0] or sides[1] else "",
        "captured_at": captured_at,
        "event_timestamp": captured_at,
        "available_at": captured_at,
        "ingested_at": now_utc_iso(),
        "best_yes_bid_e4": parsed["best_yes_bid_e4"],
        "best_no_bid_e4": parsed["best_no_bid_e4"],
        "yes_levels": str(parsed["yes_levels"]),
        "no_levels": str(parsed["no_levels"]),
        "yes_dollars_json": parsed["yes_dollars_json"],
        "no_dollars_json": parsed["no_dollars_json"],
        "market_data_type": "ORDERBOOK_SNAPSHOT",
        "source_dataset": "live_orderbook_snapshot",
        "pipeline_version": cfg.pipeline_version,
        "derived_at": now_utc_iso(),
        "note": parsed["note"],
    }


def append_snapshot_csv(cfg: RollerConfig, sport: str, season: str, row: dict[str, str]) -> Path:
    path_key = cfg.season_meta(sport, season)["path_key"]
    out_dir = canonical_dir(cfg.root, sport, path_key) / "kalshi_orderbook_snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    month = str(row.get("captured_at") or "")[:7] or "unknown"
    path = out_dir / f"month={month}.csv"
    frame = pd.DataFrame([row])
    if path.is_file():
        prior = pd.read_csv(path, dtype=str).fillna("")
        frame = pd.concat([prior, frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=["ticker", "captured_at"], keep="last")
    write_csv(path, frame, ORDERBOOK_COLUMNS)
    return path


def canonicalize_orderbook(
    cfg: RollerConfig,
    sport: str,
    season: str,
    identity: pd.DataFrame,
) -> int:
    raw = raw_orderbook_dir(cfg, sport, season)
    path_key = cfg.season_meta(sport, season)["path_key"]
    out_dir = canonical_dir(cfg.root, sport, path_key) / "kalshi_orderbook_snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(raw.glob("**/*.json")) if raw.is_dir() else []
    rows: list[dict[str, str]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        ticker = str(payload.get("ticker") or path.stem.split("_")[0])
        captured = str(payload.get("captured_at") or payload.get("available_at") or "")
        if not ticker or not captured:
            continue
        book = payload.get("orderbook_fp") or payload
        rows.append(
            snapshot_row(
                cfg,
                sport=sport,
                season=season,
                ticker=ticker,
                captured_at=captured,
                payload=book if isinstance(book, dict) else payload,
                identity=identity,
            )
        )
    if not rows:
        if not any(out_dir.glob("*.csv")):
            write_csv(out_dir / "month=empty.csv", pd.DataFrame(columns=ORDERBOOK_COLUMNS), ORDERBOOK_COLUMNS)
        return 0
    df = pd.DataFrame(rows)
    total = 0
    for month, grp in df.groupby(df["captured_at"].astype(str).str[:7], sort=True):
        path = out_dir / f"month={month or 'unknown'}.csv"
        if path.is_file():
            prior = pd.read_csv(path, dtype=str).fillna("")
            grp = pd.concat([prior, grp], ignore_index=True)
            grp = grp.drop_duplicates(subset=["ticker", "captured_at"], keep="last")
        write_csv(path, grp, ORDERBOOK_COLUMNS)
        total += len(grp)
    return total
