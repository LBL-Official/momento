"""One-shot tennis canonical ingest.

Identity-join Kalshi ATP/WTA match-winner events to MCP play-by-play.
Writes ROLLER/data/tennis/2025_2026/canonical/* and warehouse crosswalk sidecars.

RESEARCH ONLY. No orders.

Does not invent point timestamps (MCP Time is never a clock).
Does not derive yes_bid from a print.
Does not infer official W from PBP. Settlement is Kalshi result yes/no only.
Does not treat unmatched / SEQUENCE_ONLY as N=0.
Does not start W9 or change FIRST01 / 80/81/83/89.

The runtime query path never calls the network. Re-run this after candle
ingest finishes to refresh market-path coverage.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import write_csv
from roller.mlb.ingest import CANDLE_COLUMNS as MLB_CANDLE_COLUMNS
from roller.mlb.ingest import _candle_ts, _dist_e4
from roller.mlb.last_print import LAST_TRADE_COLUMNS, aggregate_last_prints
from roller.tennis.crosswalk import (
    CROSSWALK_COLUMNS,
    STATUS_MATCHED,
    build_competitor_registry,
    build_crosswalk,
    crosswalk_summary,
    normalize_kalshi_events,
    row_to_csv_row as crosswalk_csv_row,
)
from roller.tennis.pbp import (
    LICENSE_FIELDS,
    PBP_COLUMNS,
    match_records,
    parse_points_file,
    read_match_index,
    row_to_csv_row as pbp_csv_row,
)
from roller.timeutil import now_utc_iso

PIPELINE = "tennis-warehouse-1"
SEASON_LABEL = "2025-2026"
WINDOW_START = date(2025, 6, 18)
WINDOW_END = date(2026, 9, 11)
DEFAULT_WAREHOUSE = Path("Backtesting Suite/Data/TENNIS/2025-2026/warehouse")
CANONICAL_REL = Path("data/tennis/2025_2026/canonical")

TOUR_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("atp", "ATP", "M", "KXATPMATCH"),
    ("wta", "WTA", "W", "KXWTAMATCH"),
)

GAMES_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "league",
    "game_date",
    "scheduled_start",
    "actual_start",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "source_game_id",
    "warehouse_game_id",
    "event_ticker",
    "kalshi_market_yes_p1",
    "kalshi_market_yes_p2",
    "kalshi_market_yes_home",
    "kalshi_market_yes_away",
    "p1_name",
    "p2_name",
    "surface",
    "tournament",
    "round",
    "best_of",
    "tour",
    "pbp_linked",
    "pbp_basis",
    "pit_joinable",
    "crosswalk_status",
    "crosswalk_method",
    "mcp_match_id",
    "tennis_match_id",
    "date_status",
    "ingested_at",
    "source_dataset",
    "pipeline_version",
    "derived_at",
]

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

CANDLE_COLUMNS = [
    *MLB_CANDLE_COLUMNS,
    "game_date",
    "is_valid",
]

CANONICAL_PBP_COLUMNS = [
    "internal_game_id",
    "kalshi_event_ticker",
    "crosswalk_status",
    *PBP_COLUMNS,
]


def _momento_root(cfg: RollerConfig) -> Path:
    return Path(cfg.repo_root).resolve()


def _as_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    head = text[:10]
    try:
        year, month, day = (int(part) for part in head.split("-"))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def in_requested_window(value: Any) -> bool:
    parsed = _as_date(value)
    if parsed is None:
        return False
    return WINDOW_START <= parsed <= WINDOW_END


def load_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
    return out


def event_date_from_markets(markets: Iterable[Mapping[str, Any]]) -> date | None:
    """Kalshi events have no event_date. Use market occurrence, then expected expiry, then close.

    Majority vote. Never parsed from the event-ticker code blob.
    """
    votes: list[date] = []
    for market in markets:
        parsed = None
        for key in ("occurrence_datetime", "expected_expiration_time", "close_time"):
            parsed = _as_date(market.get(key))
            if parsed is not None:
                break
        if parsed is not None:
            votes.append(parsed)
    if not votes:
        return None
    counts = Counter(votes)
    top, _ = counts.most_common(1)[0]
    return top


def first_iso(markets: Iterable[Mapping[str, Any]], *keys: str) -> str:
    for market in markets:
        for key in keys:
            raw = market.get(key)
            if raw not in (None, ""):
                return str(raw)
    return ""


def attach_markets(
    events: list[dict[str, Any]],
    markets: list[dict[str, Any]],
    *,
    series: str,
) -> list[dict[str, Any]]:
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for market in markets:
        et = str(market.get("event_ticker") or "").strip()
        if et:
            by_event[et].append(market)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for event in events:
        ticker = str(event.get("event_ticker") or "").strip()
        if not ticker:
            continue
        seen.add(ticker)
        attached = list(by_event.get(ticker) or [])
        row = dict(event)
        row["markets"] = attached
        row["series_ticker"] = row.get("series_ticker") or series
        row["event_date"] = event_date_from_markets(attached)
        row["occurrence_datetime"] = first_iso(attached, "occurrence_datetime")
        row["open_time"] = first_iso(attached, "open_time")
        out.append(row)
    for et, attached in by_event.items():
        if et in seen:
            continue
        seed = attached[0]
        out.append(
            {
                "event_ticker": et,
                "series_ticker": seed.get("series_ticker") or series,
                "title": seed.get("title"),
                "sub_title": seed.get("yes_sub_title"),
                "product_metadata": {},
                "markets": attached,
                "event_date": event_date_from_markets(attached),
                "occurrence_datetime": first_iso(attached, "occurrence_datetime"),
                "open_time": first_iso(attached, "open_time"),
                "synthesized_from_markets": True,
            }
        )
    return out


def load_tour_kalshi(warehouse: Path, layer: str, series: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = warehouse / "raw" / "kalshi" / layer
    events = load_jsonl_gz(raw / "events" / "events.jsonl.gz")
    markets = load_jsonl_gz(raw / "markets" / "markets.jsonl.gz")
    return attach_markets(events, markets, series=series), markets


def load_window_mcp(warehouse: Path) -> list[dict[str, Any]]:
    mcp = warehouse / "raw" / "mcp"
    matches: list[dict[str, Any]] = []
    for filename in ("charting-m-matches.csv", "charting-w-matches.csv"):
        path = mcp / filename
        if not path.is_file():
            continue
        for record in match_records(read_match_index(path)):
            if in_requested_window(record.get("match_date")):
                matches.append(record)
    matches.sort(key=lambda row: (str(row.get("match_date") or ""), str(row.get("source_match_id") or "")))
    return matches


def league_for_series(series: str | None) -> str:
    if series == "KXWTAMATCH":
        return "WTA"
    return "ATP"


def official_result(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if text in {"yes", "no"}:
        return text
    return ""


def settlement_e4(raw: Any) -> str:
    from roller.mlb.last_print import dollars_to_e4

    value = dollars_to_e4(raw)
    return "" if value is None else str(value)


def _blank(value: Any) -> str:
    return "" if value in (None, "") else str(value)


def build_games_and_ticker_meta(
    attached_events: list[dict[str, Any]],
    crosswalk_by_event: Mapping[str, Mapping[str, Any]],
    mcp_by_source: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    ingested_at: str,
    pipeline_version: str,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    games: list[dict[str, str]] = []
    ticker_meta: dict[str, dict[str, str]] = {}
    for event in attached_events:
        et = str(event.get("event_ticker") or "")
        if not et:
            continue
        event_date = _as_date(event.get("event_date"))
        linked = crosswalk_by_event.get(et)
        keep = event_date is None or in_requested_window(event_date) or linked is not None
        if not keep:
            continue
        league = league_for_series(str(event.get("series_ticker") or ""))
        xw = linked or {}
        mcp = (mcp_by_source or {}).get(str(xw.get("source_match_id") or "")) or {}
        p1_ticker = _blank(xw.get("kalshi_p1_market_ticker"))
        p2_ticker = _blank(xw.get("kalshi_p2_market_ticker"))
        p1_uuid = _blank(xw.get("kalshi_p1_competitor_uuid"))
        p2_uuid = _blank(xw.get("kalshi_p2_competitor_uuid"))
        linked_flag = "1" if xw.get("crosswalk_status") == STATUS_MATCHED else "0"
        date_status = "OBSERVED" if event_date is not None else "UNAVAILABLE"
        competition = ""
        metadata = event.get("product_metadata")
        if isinstance(metadata, Mapping):
            competition = _blank(metadata.get("competition"))
        game = {
            "internal_game_id": et,
            "sport": league,
            "season": SEASON_LABEL,
            "league": league,
            "game_date": event_date.isoformat() if event_date else "",
            "scheduled_start": _blank(event.get("occurrence_datetime")),
            "actual_start": "",
            "home_team_id": "",
            "away_team_id": "",
            "home_team_name": "",
            "away_team_name": "",
            "source_game_id": et,
            "warehouse_game_id": et,
            "event_ticker": et,
            "kalshi_market_yes_p1": p1_ticker,
            "kalshi_market_yes_p2": p2_ticker,
            "kalshi_market_yes_home": "",
            "kalshi_market_yes_away": "",
            "p1_name": _blank(xw.get("p1_name") or mcp.get("p1_name")),
            "p2_name": _blank(xw.get("p2_name") or mcp.get("p2_name")),
            "surface": _blank(mcp.get("surface")),
            "tournament": _blank(xw.get("tournament") or xw.get("kalshi_competition") or competition),
            "round": _blank(xw.get("round") or mcp.get("round")),
            "best_of": _blank(mcp.get("best_of")),
            "tour": _blank(xw.get("tour")),
            "pbp_linked": linked_flag,
            "pbp_basis": "SEQUENCE_ONLY" if linked_flag == "1" else "",
            "pit_joinable": "0",
            "crosswalk_status": _blank(xw.get("crosswalk_status")) or "UNMATCHED",
            "crosswalk_method": _blank(xw.get("crosswalk_method")),
            "mcp_match_id": _blank(xw.get("source_match_id")),
            "tennis_match_id": _blank(xw.get("tennis_match_id")),
            "date_status": date_status,
            "ingested_at": ingested_at,
            "source_dataset": "kalshi_kxmatch+tennis_mcp",
            "pipeline_version": pipeline_version,
            "derived_at": ingested_at,
        }
        games.append(game)
        markets = event.get("markets") or []
        for market in markets:
            ticker = str(market.get("ticker") or "")
            if not ticker:
                continue
            competitor = ""
            strike = market.get("custom_strike")
            if isinstance(strike, Mapping):
                competitor = _blank(strike.get("tennis_competitor"))
            side = ""
            if (p1_ticker and ticker == p1_ticker) or (p1_uuid and competitor == p1_uuid):
                side = "1"
            elif (p2_ticker and ticker == p2_ticker) or (p2_uuid and competitor == p2_uuid):
                side = "2"
            ticker_meta[ticker] = {
                "internal_game_id": et,
                "team_side": side,
                "game_date": game["game_date"],
                "event_ticker": et,
            }
    games.sort(key=lambda row: (row.get("game_date") or "", row.get("internal_game_id") or ""))
    return games, ticker_meta


def build_markets(
    attached_events: list[dict[str, Any]],
    ticker_meta: Mapping[str, Mapping[str, str]],
    *,
    ingested_at: str,
    pipeline_version: str,
) -> list[dict[str, str]]:
    by_ticker: dict[str, tuple[str, dict[str, Any]]] = {}
    for event in attached_events:
        et = str(event.get("event_ticker") or "")
        for market in event.get("markets") or []:
            ticker = str(market.get("ticker") or "")
            if ticker:
                by_ticker[ticker] = (et, market)
    rows: list[dict[str, str]] = []
    for ticker, info in ticker_meta.items():
        found = by_ticker.get(ticker)
        if found is None:
            continue
        et, market = found
        result = official_result(market.get("result"))
        settle = _blank(market.get("settlement_ts"))
        close = _blank(market.get("close_time"))
        rows.append(
            {
                "internal_game_id": info["internal_game_id"],
                "ticker": ticker,
                "event_id": et,
                "event_ticker": et,
                "team_side": info.get("team_side") or "",
                "result": result,
                "settlement_value_e4": settlement_e4(market.get("settlement_value_dollars")),
                "kalshi_yes_settled": "1" if result == "yes" else ("0" if result == "no" else ""),
                "close_time": close,
                "expiration_time": _blank(market.get("expiration_time")),
                "settlement_time": settle,
                "event_timestamp": "",
                "available_at": close or settle or _blank(market.get("open_time")),
                "result_available_at": settle or close,
                "ingested_at": ingested_at,
                "source_dataset": "kalshi_rest_markets",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    rows.sort(key=lambda row: (row.get("event_ticker") or "", row.get("ticker") or ""))
    return rows


def _complete_tickers(manifest_path: Path, dataset_type: str) -> set[str]:
    if not manifest_path.is_file():
        return set()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    jobs = raw.get("jobs") if isinstance(raw, dict) else raw
    if not isinstance(jobs, list):
        return set()
    out: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if str(job.get("dataset_type") or "") != dataset_type:
            continue
        if str(job.get("status") or "") != "COMPLETE":
            continue
        ticker = str(job.get("ticker") or "")
        if ticker:
            out.add(ticker)
    return out


class _MonthWriter:
    def __init__(self, out_dir: Path, columns: list[str]) -> None:
        self.out_dir = out_dir
        self.columns = columns
        self._handles: dict[str, Any] = {}
        self.counts: dict[str, int] = {}
        if out_dir.exists():
            for old in out_dir.glob("*.csv"):
                old.unlink()
        out_dir.mkdir(parents=True, exist_ok=True)

    def write_row(self, row: Mapping[str, Any], month: str) -> None:
        if not month:
            return
        handle = self._handles.get(month)
        if handle is None:
            path = self.out_dir / f"month={month}.csv"
            fh = path.open("w", newline="", encoding="utf-8")
            writer = csv.DictWriter(fh, fieldnames=self.columns, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            handle = (fh, writer)
            self._handles[month] = handle
            self.counts[month] = 0
        handle[1].writerow({col: "" if row.get(col) in (None, "") else str(row.get(col)) for col in self.columns})
        self.counts[month] += 1

    @property
    def n(self) -> int:
        return sum(self.counts.values())

    def close(self) -> None:
        for fh, _ in self._handles.values():
            fh.close()
        self._handles.clear()


def _candles_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        rows = load_jsonl_gz(path)
    except (OSError, json.JSONDecodeError, EOFError, gzip.BadGzipFile):
        return []
    out: list[dict[str, Any]] = []
    for env in rows:
        payload = env.get("payload") if isinstance(env.get("payload"), dict) else env
        sticks = payload.get("candlesticks") if isinstance(payload, dict) else None
        ticker = str((payload or {}).get("ticker") or env.get("ticker") or "")
        if not isinstance(sticks, list):
            continue
        for rec in sticks:
            if isinstance(rec, dict):
                if ticker and not rec.get("ticker"):
                    rec = {**rec, "ticker": ticker}
                out.append(rec)
    return out


def write_candles(
    warehouse: Path,
    ticker_meta: Mapping[str, Mapping[str, str]],
    dest: Path,
    *,
    ingested_at: str,
    pipeline_version: str,
) -> dict[str, int]:
    writer = _MonthWriter(dest / "kalshi_candles", CANDLE_COLUMNS)
    seen: set[tuple[str, str]] = set()
    files_read = 0
    skipped_incomplete = 0
    try:
        for layer, _league, _tour, _series in TOUR_SPECS:
            complete = _complete_tickers(
                warehouse / "manifests" / layer / f"{layer}_ingestion_manifest.json",
                "candles",
            )
            root = warehouse / "raw" / "kalshi" / layer / "candlesticks"
            if not root.is_dir():
                continue
            jobs: list[tuple[Path, str, Mapping[str, str]]] = []
            for path in sorted(root.glob("ticker=*/candles.jsonl.gz")):
                ticker = path.parent.name.split("=", 1)[-1]
                if complete and ticker not in complete:
                    skipped_incomplete += 1
                    continue
                info = ticker_meta.get(ticker)
                if info is None:
                    continue
                jobs.append((path, ticker, info))
            files_read += len(jobs)
            with ThreadPoolExecutor(max_workers=8) as pool:
                futs = {pool.submit(_candles_from_file, path): (ticker, info) for path, ticker, info in jobs}
                for fut in as_completed(futs):
                    ticker, info = futs[fut]
                    try:
                        sticks = fut.result()
                    except (OSError, json.JSONDecodeError, EOFError):
                        continue
                    for rec in sticks:
                        bid = rec.get("yes_bid")
                        close = _dist_e4(bid, "close")
                        if not close:
                            continue
                        ts_iso = _candle_ts(rec)
                        if not ts_iso:
                            continue
                        key = (ticker, ts_iso)
                        if key in seen:
                            continue
                        seen.add(key)
                        ask = rec.get("yes_ask")
                        ask_close = _dist_e4(ask, "close")
                        vol_raw = rec.get("volume")
                        volume = ""
                        if vol_raw not in (None, ""):
                            try:
                                volume = str(int(float(vol_raw)))
                            except (TypeError, ValueError):
                                volume = ""
                        row = {
                            "internal_game_id": info.get("internal_game_id") or "",
                            "ticker": ticker,
                            "team_side": info.get("team_side") or "",
                            "candle_timestamp": ts_iso,
                            "event_timestamp": ts_iso,
                            "available_at": ts_iso,
                            "ingested_at": ingested_at,
                            "yes_bid_open": _dist_e4(bid, "open"),
                            "yes_bid_high": _dist_e4(bid, "high"),
                            "yes_bid_low": _dist_e4(bid, "low"),
                            "yes_bid_close": close,
                            "yes_ask_open": _dist_e4(ask, "open"),
                            "yes_ask_high": _dist_e4(ask, "high"),
                            "yes_ask_low": _dist_e4(ask, "low"),
                            "yes_ask_close": ask_close,
                            "volume": volume,
                            "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                            "source_dataset": "kalshi_rest_candlestick",
                            "source_file_hash": "",
                            "pipeline_version": pipeline_version,
                            "derived_at": ingested_at,
                            "game_date": info.get("game_date") or "",
                            "is_valid": "1" if close and ask_close else "0",
                        }
                        writer.write_row(row, ts_iso[:7])
    finally:
        writer.close()
    return {
        "genuine_candles": writer.n,
        "candle_files_read": files_read,
        "candle_files_skipped_incomplete": skipped_incomplete,
    }


def _trades_from_pages(ticker_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(ticker_dir.glob("page-*.jsonl.gz")):
        try:
            rows = load_jsonl_gz(path)
        except (OSError, json.JSONDecodeError, EOFError, gzip.BadGzipFile):
            continue
        for rec in rows:
            if isinstance(rec, dict):
                out.append(rec)
    return out


def write_last_trade(
    warehouse: Path,
    ticker_meta: Mapping[str, Mapping[str, str]],
    dest: Path,
    *,
    ingested_at: str,
    pipeline_version: str,
) -> dict[str, int]:
    writer = _MonthWriter(dest / "kalshi_last_trade", LAST_TRADE_COLUMNS)
    files_read = 0
    prints = 0
    try:
        for layer, _league, _tour, _series in TOUR_SPECS:
            complete = _complete_tickers(
                warehouse / "manifests" / layer / f"{layer}_ingestion_manifest.json",
                "trades",
            )
            root = warehouse / "raw" / "kalshi" / layer / "trades"
            if not root.is_dir():
                continue
            for ticker_dir in sorted(root.glob("ticker=*")):
                ticker = ticker_dir.name.split("=", 1)[-1]
                if complete and ticker not in complete:
                    continue
                info = ticker_meta.get(ticker)
                if info is None:
                    continue
                trades = _trades_from_pages(ticker_dir)
                if not trades:
                    continue
                files_read += 1
                prints += len(trades)
                bars = aggregate_last_prints(
                    trades,
                    ingested_at=ingested_at,
                    pipeline_version=pipeline_version,
                    source_dataset="kalshi_public_trades",
                    ticker_meta={ticker: dict(info)},
                )
                for bar in bars:
                    if bar.get("yes_bid_close") not in (None, "") or bar.get("yes_bid") not in (None, ""):
                        raise RuntimeError("last-trade ingest invented yes_bid from a print")
                    ts = str(bar.get("candle_timestamp") or "")
                    writer.write_row(bar, ts[:7])
    finally:
        writer.close()
    return {
        "last_trade_bars": writer.n,
        "trade_tickers_read": files_read,
        "trade_prints_read": prints,
    }


def write_pbp(
    warehouse: Path,
    window_matches: list[dict[str, Any]],
    crosswalk_by_source: Mapping[str, Mapping[str, Any]],
    dest: Path,
    *,
    ingested_at: str,
    dataset_version: str,
    pipeline_version: str,
) -> dict[str, int]:
    only_ids = {str(m.get("source_match_id")) for m in window_matches if m.get("source_match_id")}
    mcp = warehouse / "raw" / "mcp"
    writer = _MonthWriter(dest / "pbp", CANONICAL_PBP_COLUMNS)
    points = 0
    matches_with_points = 0
    try:
        for matches_name, points_name in (
            ("charting-m-matches.csv", "charting-m-points-2020s.csv"),
            ("charting-w-matches.csv", "charting-w-points-2020s.csv"),
        ):
            matches_path = mcp / matches_name
            points_path = mcp / points_name
            if not matches_path.is_file() or not points_path.is_file():
                continue
            index = read_match_index(matches_path)
            source_hash = hashlib.sha256(points_path.read_bytes()).hexdigest()[:16]
            seen_match: set[str] = set()
            for row in parse_points_file(
                points_path,
                index,
                ingested_at=ingested_at,
                dataset_version=dataset_version,
                pipeline_version=pipeline_version,
                source_file_hash=source_hash,
                only_match_ids=only_ids,
            ):
                if row.get("event_timestamp") not in (None, ""):
                    raise RuntimeError(
                        "MCP ingest refused an invented point timestamp. "
                        "SEQUENCE-ONLY rows must keep event_timestamp empty."
                    )
                source_id = str(row.get("source_match_id") or "")
                xw = crosswalk_by_source.get(source_id) or {}
                linked = xw.get("crosswalk_status") == STATUS_MATCHED
                serialized = pbp_csv_row(row)
                serialized["internal_game_id"] = _blank(xw.get("kalshi_event_ticker")) if linked else ""
                serialized["kalshi_event_ticker"] = serialized["internal_game_id"]
                serialized["crosswalk_status"] = _blank(xw.get("crosswalk_status")) or "UNMATCHED"
                month = str(row.get("match_date") or "")[:7]
                writer.write_row(serialized, month)
                points += 1
                if source_id and source_id not in seen_match:
                    seen_match.add(source_id)
                    matches_with_points += 1
    finally:
        writer.close()
    return {"pbp_rows": points, "pbp_matches": matches_with_points}


def _write_crosswalk_sidecars(
    warehouse: Path,
    rows: list[dict[str, Any]],
    dest: Path,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    write_csv(dest / "crosswalk.csv", pd.DataFrame([crosswalk_csv_row(r) for r in rows]), list(CROSSWALK_COLUMNS))
    for layer, _league, tour, _series in TOUR_SPECS:
        subset = [r for r in rows if str(r.get("tour") or "") == tour]
        path = warehouse / "normalized" / layer / "crosswalk" / f"{layer}_mcp_kalshi_crosswalk.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(subset, indent=2, default=str) + "\n", encoding="utf-8")


def _coverage(
    rows: list[dict[str, Any]],
    games: list[dict[str, str]],
    market_rows: list[dict[str, str]],
    candle_stats: Mapping[str, int],
    trade_stats: Mapping[str, int],
    mcp_window: int,
) -> dict[str, Any]:
    summary = crosswalk_summary(rows)
    by_reason: Counter[str] = Counter()
    by_tour: dict[str, Counter[str]] = defaultdict(Counter)
    by_tournament: Counter[str] = Counter()
    for row in rows:
        status = str(row.get("crosswalk_status") or "")
        tour = str(row.get("tour") or "?")
        by_tour[tour][status] += 1
        if status != STATUS_MATCHED:
            by_reason[str(row.get("unmatched_reason") or "UNKNOWN")] += 1
        else:
            by_tournament[str(row.get("tournament") or row.get("kalshi_competition") or "")] += 1
    kalshi_in_window = sum(1 for g in games if in_requested_window(g.get("game_date")))
    linked_games = sum(1 for g in games if g.get("pbp_linked") == "1")
    settled = sum(1 for m in market_rows if m.get("result") in {"yes", "no"})
    scalar_or_blank = sum(1 for m in market_rows if m.get("result") not in {"yes", "no"})
    return {
        "window": {"start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat()},
        "mcp_matches_in_window": mcp_window,
        "crosswalk": summary,
        "unmatched_reasons": dict(by_reason),
        "by_tour": {k: dict(v) for k, v in sorted(by_tour.items())},
        "matched_by_tournament": dict(by_tournament.most_common()),
        "kalshi_games_written": len(games),
        "kalshi_games_dated_in_window": kalshi_in_window,
        "kalshi_games_linked_to_pbp": linked_games,
        "markets_written": len(market_rows),
        "markets_with_official_yes_no": settled,
        "markets_without_binary_settlement": scalar_or_blank,
        **dict(candle_stats),
        **dict(trade_stats),
        "notes": [
            "SEQUENCE-ONLY PBP ≠ PIT PBP",
            "LAST TRADE ≠ YES BID",
            "CANDLE PATH ≠ FILL",
            "OFFICIAL W = KALSHI SETTLEMENT yes/no only. scalar is not coerced.",
            "Identity join only. MCP Time is never a point timestamp.",
            "Missing PBP is UNMATCHED / NO_POINT_DATA, never N=0.",
            "Candle/trade counts are whatever Kalshi ingest has marked COMPLETE.",
        ],
        **LICENSE_FIELDS,
    }


def ingest_tennis(
    *,
    cfg: RollerConfig | None = None,
    warehouse: Path | None = None,
    dest: Path | None = None,
    include_candles: bool = True,
    include_last_trade: bool = True,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    repo = Path(cfg.root).resolve()
    momento = _momento_root(cfg)
    wh = Path(warehouse) if warehouse else momento / DEFAULT_WAREHOUSE
    out = Path(dest) if dest else repo / CANONICAL_REL
    out.mkdir(parents=True, exist_ok=True)
    now = now_utc_iso()
    version = f"{cfg.pipeline_version}:{PIPELINE}"

    attached: list[dict[str, Any]] = []
    raw_markets_n = 0
    for layer, _league, _tour, series in TOUR_SPECS:
        events, markets = load_tour_kalshi(wh, layer, series)
        attached.extend(events)
        raw_markets_n += len(markets)

    window_matches = load_window_mcp(wh)
    normalized = normalize_kalshi_events(attached)
    registry = build_competitor_registry(normalized)
    xw_rows = build_crosswalk(window_matches, normalized, competitor_registry=registry)

    by_event = {
        str(row["kalshi_event_ticker"]): row
        for row in xw_rows
        if row.get("crosswalk_status") == STATUS_MATCHED and row.get("kalshi_event_ticker")
    }
    by_source = {
        str(row["source_match_id"]): row
        for row in xw_rows
        if row.get("source_match_id")
    }

    mcp_by_source = {
        str(row["source_match_id"]): row
        for row in window_matches
        if row.get("source_match_id")
    }
    games, ticker_meta = build_games_and_ticker_meta(
        attached,
        by_event,
        mcp_by_source,
        ingested_at=now,
        pipeline_version=version,
    )
    write_csv(out / "games.csv", pd.DataFrame(games), GAMES_COLUMNS)
    market_rows = build_markets(attached, ticker_meta, ingested_at=now, pipeline_version=version)
    write_csv(out / "kalshi_markets.csv", pd.DataFrame(market_rows), MARKET_COLUMNS)
    _write_crosswalk_sidecars(wh, xw_rows, out)

    pbp_stats = write_pbp(
        wh,
        window_matches,
        by_source,
        out,
        ingested_at=now,
        dataset_version="pending",
        pipeline_version=version,
    )
    candle_stats: dict[str, int] = {
        "genuine_candles": 0,
        "candle_files_read": 0,
        "candle_files_skipped_incomplete": 0,
    }
    trade_stats: dict[str, int] = {
        "last_trade_bars": 0,
        "trade_tickers_read": 0,
        "trade_prints_read": 0,
    }
    if include_candles:
        candle_stats = write_candles(
            wh, ticker_meta, out, ingested_at=now, pipeline_version=version
        )
    if include_last_trade:
        trade_stats = write_last_trade(
            wh, ticker_meta, out, ingested_at=now, pipeline_version=version
        )

    coverage = _coverage(xw_rows, games, market_rows, candle_stats, trade_stats, len(window_matches))
    manifest = {
        "sport": "tennis",
        "season": SEASON_LABEL,
        "pipeline": PIPELINE,
        "generated_at": now,
        "pipeline_version": version,
        "warehouse": str(wh),
        "canonical": str(out),
        "raw_kalshi_events": len(attached),
        "raw_kalshi_markets": raw_markets_n,
        "counts": {
            "games": len(games),
            "markets": len(market_rows),
            **pbp_stats,
            **candle_stats,
            **trade_stats,
        },
        "coverage": coverage,
        "observation_basis": "TRADABLE_YES_BID_AVAILABLE+SEQUENCE_ONLY_PBP",
        "license": LICENSE_FIELDS,
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), default=str)
    manifest["dataset_version"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    (out / "dataset_version.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    coverage_path = wh / "derived" / "tennis" / "coverage" / "coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage, indent=2, default=str) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest tennis Kalshi+MCP into ROLLER canonical.")
    parser.add_argument("--warehouse", type=Path, default=None)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--skip-candles", action="store_true")
    parser.add_argument("--skip-last-trade", action="store_true")
    parser.add_argument(
        "--window-end",
        default=None,
        help="Inclusive YYYY-MM-DD for Kalshi↔MCP identity window. Default: module WINDOW_END.",
    )
    args = parser.parse_args()
    if args.window_end:
        global WINDOW_END
        WINDOW_END = date.fromisoformat(args.window_end)
    manifest = ingest_tennis(
        warehouse=args.warehouse,
        dest=args.dest,
        include_candles=not args.skip_candles,
        include_last_trade=not args.skip_last_trade,
    )
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
