"""Project NBA Kalshi 1m candles into warehouse_v0. Phase 4.

Reads published canonical CSV. Resolves internal_game_id only through
GameMarketLink. Does not interpolate, forward-fill, or convert last trade
into yes bid. Not a Confirm & Run source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import read_csv, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.entities import ObservationBasis
from roller.warehouse.layout_v0 import observations_dir, warehouse_v0_readme_path
from roller.warehouse.market_link import load_nba_crosswalk
from roller.warehouse.partitioning import list_month_csvs, month_key, month_parquet

PHASE4_SPORT = "NBA"
BASIS = ObservationBasis.TRADABLE_YES_BID
LAST_TRADE_COLS = (
    "last_open_e4",
    "last_high_e4",
    "last_low_e4",
    "last_close_e4",
)
YES_BID_COLS = (
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
)
OBSERVATION_COLUMNS = [
    "ticker",
    "market_id",
    "internal_game_id",
    "source_internal_game_id",
    "game_link_status",
    "basis",
    "available_at",
    "event_timestamp",
    "candle_timestamp",
    "ingested_at",
    *YES_BID_COLS,
    "volume",
    "source",
    "duplicate_key",
]


@dataclass
class ObservationBuild:
    months: dict[str, int] = field(default_factory=dict)
    rows: int = 0
    linked_rows: int = 0
    unlinked_rows: int = 0
    conflict_rows: int = 0
    duplicate_keys: int = 0
    missing_yes_bid_close: int = 0
    rejected_last_trade_files: int = 0
    tickers: int = 0
    linked_tickers: int = 0
    unlinked_tickers: int = 0
    date_min: str = ""
    date_max: str = ""
    games_with_observations: int = 0
    markets_with_observations: int = 0


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _int_or_none(value: object) -> int | None:
    text = _text(value)
    if text == "":
        return None
    return int(text)


def candle_csv_dir(cfg: RollerConfig, season: str = "2025-2026") -> Path:
    return cfg.dataset_path(PHASE4_SPORT, season, "kalshi_candles")


def assert_no_last_trade_columns(columns: Iterable[str], *, path: Path | None = None) -> None:
    present = [c for c in LAST_TRADE_COLS if c in set(columns)]
    if present:
        where = f" in {path}" if path else ""
        raise ValueError(f"TRADABLE_YES_BID candles must not carry last-trade columns{where}: {present}")


def project_observation_frame(
    frame: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    path: Path | None = None,
) -> pd.DataFrame:
    """Stamp gid from the crosswalk only. Absent minutes stay absent."""
    if frame.empty:
        return pd.DataFrame(columns=OBSERVATION_COLUMNS)
    assert_no_last_trade_columns(frame.columns, path=path)
    work = frame.copy()
    work["ticker"] = work["ticker"].map(_text)
    work["available_at"] = work["available_at"].map(_text)
    work["source_internal_game_id"] = work.get("internal_game_id", pd.Series("", index=work.index)).map(_text)
    lookup = crosswalk.loc[:, ["ticker", "internal_game_id", "link_status"]].drop_duplicates("ticker")
    lookup = lookup.rename(columns={"internal_game_id": "link_gid", "link_status": "link_status"})
    merged = work.merge(lookup, on="ticker", how="left")
    link_gid = merged["link_gid"].map(_text) if "link_gid" in merged.columns else pd.Series("", index=merged.index)
    link_status = merged["link_status"].map(_text) if "link_status" in merged.columns else pd.Series("", index=merged.index)
    source_gid = merged["source_internal_game_id"].map(_text)
    status = []
    resolved = []
    for gid, src, st in zip(link_gid.tolist(), source_gid.tolist(), link_status.tolist()):
        if st == "AMBIGUOUS":
            status.append("AMBIGUOUS")
            resolved.append("")
        elif st == "LINKED" and gid and src and gid != src:
            status.append("CONFLICT")
            resolved.append("")
        elif st == "LINKED" and gid:
            status.append("LINKED")
            resolved.append(gid)
        else:
            status.append("UNLINKED")
            resolved.append("")
    merged["internal_game_id"] = resolved
    merged["game_link_status"] = status
    merged["market_id"] = merged["ticker"]
    merged["basis"] = BASIS.value
    key = merged["ticker"] + "\0" + merged["available_at"] + "\0" + merged["basis"]
    dup = key.duplicated(keep=False)
    merged["duplicate_key"] = dup.map(lambda v: "1" if bool(v) else "0")
    merged["source"] = merged.get("source_dataset", pd.Series("warehouse_candles_1m", index=merged.index)).map(_text)
    if "event_timestamp" not in merged.columns:
        merged["event_timestamp"] = merged["available_at"]
    if "candle_timestamp" not in merged.columns:
        merged["candle_timestamp"] = merged.get("event_timestamp", merged["available_at"])
    if "ingested_at" not in merged.columns:
        merged["ingested_at"] = ""
    if "volume" not in merged.columns:
        merged["volume"] = ""
    for col in YES_BID_COLS:
        if col not in merged.columns:
            merged[col] = ""
    out = merged[OBSERVATION_COLUMNS].copy()
    return out.sort_values(["ticker", "available_at"], kind="mergesort").reset_index(drop=True)


def _update_stats(stats: ObservationBuild, frame: pd.DataFrame, month: str) -> None:
    stats.months[month] = int(len(frame))
    stats.rows += int(len(frame))
    stats.linked_rows += int((frame["game_link_status"] == "LINKED").sum())
    stats.unlinked_rows += int((frame["game_link_status"] == "UNLINKED").sum())
    stats.conflict_rows += int((frame["game_link_status"] == "CONFLICT").sum())
    stats.duplicate_keys += int((frame["duplicate_key"] == "1").sum())
    stats.missing_yes_bid_close += int(frame["yes_bid_close"].astype(str).str.strip().eq("").sum())
    if not frame.empty:
        times = frame["available_at"].astype(str)
        lo, hi = times.min(), times.max()
        if not stats.date_min or lo < stats.date_min:
            stats.date_min = lo
        if not stats.date_max or hi > stats.date_max:
            stats.date_max = hi


def project_nba_observations(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    crosswalk: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_nba_crosswalk(cfg)
    if crosswalk.empty:
        raise ValueError("NBA GameMarketLink crosswalk is empty; run Phase 3 first")
    src_dir = candle_csv_dir(cfg, season)
    out_dir = observations_dir(cfg, PHASE4_SPORT, season)
    stats = ObservationBuild()
    tickers: set[str] = set()
    linked_tickers: set[str] = set()
    unlinked_tickers: set[str] = set()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, PHASE4_SPORT, season)
        if not readme.is_file():
            readme.write_text(
                "Provisional NBA warehouse_v0. Not Confirm & Run. Phase 8 will relocate.\n",
                encoding="utf-8",
            )
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        raw = read_csv(path)
        try:
            projected = project_observation_frame(raw, crosswalk, path=path)
        except ValueError:
            stats.rejected_last_trade_files += 1
            raise
        _update_stats(stats, projected, month)
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
        "sport": PHASE4_SPORT,
        "basis": BASIS.value,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "unlinked_rows": stats.unlinked_rows,
        "conflict_rows": stats.conflict_rows,
        "duplicate_keys": stats.duplicate_keys,
        "missing_yes_bid_close": stats.missing_yes_bid_close,
        "rejected_last_trade_files": stats.rejected_last_trade_files,
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
