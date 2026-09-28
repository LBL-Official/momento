"""One-shot MLB canonical ingest.

Reads StatsAPI PBP + game_crosswalk + Data-Real parquet + landing
Kalshi trades / 1-minute candles / Suite candles_1m / catalog settlement.
Writes ROLLER/data/mlb/2025_2026/canonical/*.
Never invents yes_bid from a print. Never forward-fills missing minutes.
Does not restart the terminal API.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import write_csv
from roller.mlb.last_print import (
    CANDLE_COLUMNS,
    LAST_TRADE_COLUMNS,
    aggregate_last_prints,
    aggregate_last_prints_frame,
    cents_to_e4,
    dollars_to_e4,
    iso_z,
    trade_yes_cents,
)
from roller.mlb.pbp import PBP_COLUMNS, parse_file
from roller.timeutil import now_utc_iso, parse_utc

DEFAULT_PBP_ROOTS = (
    Path("Backtesting Suite/Data/MLB/2025-2026/warehouse/raw/mlb_statsapi/pbp"),
    Path("Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi"),
)
DEFAULT_CROSSWALK = Path(
    "Backtesting Suite/Data/MLB/2025-2026/warehouse/normalized/mlb/pbp/game_crosswalk.json"
)
DEFAULT_MARKET_ROOT = Path("Backtesting Suite/Data-Real/MLB/2025-2026")
DEFAULT_TRADE_ROOTS = (
    Path("Backtesting Suite/Data-Real/MLB/2025-2026"),
    Path("Backtesting Suite/Data/MLB/2025-2026"),
)
DEFAULT_LANDING_KALSHI = Path("Backtesting Suite/Foundation/Ingest/landing/kalshi_discovery")
DEFAULT_LANDING_TRADES = Path("Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_trades")
DEFAULT_LANDING_CANDLES = Path("Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_candles")
DEFAULT_SUITE_CANDLES = Path(
    "Backtesting Suite/Data/MLB/2025-2026/warehouse/normalized/mlb/candles_1m"
)
DEFAULT_LANDING_PBP = Path("Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi")
DEFAULT_LANDING_SETTLEMENT = Path(
    "Backtesting Suite/Foundation/Ingest/landing/kalshi_market_settlement"
)
DEFAULT_INGEST_RUNS = Path("Backtesting Suite/Foundation/Ingest/runs")
VOLUME_KEYS = ("volume", "volume_hundredths", "volume_fp")
TRADE_SCHEMA_COLS = frozenset({"ticker", "yes_price_cents", "exchange_timestamp"})

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
    "kalshi_market_yes_home",
    "kalshi_market_yes_away",
    "final_home_score",
    "final_away_score",
    "home_win",
    "away_win",
    "p5_vs_p5",
    "identity_available_at",
    "availability_quality",
    "result_available_at",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "source_dataset",
    "source_file_hash",
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


def _repo_root(cfg: RollerConfig) -> Path:
    return cfg.repo_root


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_pbp_path(row: dict[str, Any], repo: Path) -> Path | None:
    raw = str(row.get("pbp_path") or "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p
        alt = repo / raw
        if alt.is_file():
            return alt
    game_pk = str(row.get("game_pk") or "")
    date = str(row.get("official_date") or "")
    if not game_pk or not date:
        return None
    candidates = [
        repo / "Backtesting Suite/Data/MLB/2025-2026/warehouse/raw/mlb_statsapi/pbp" / f"date={date}" / f"gamePk={game_pk}.json",
        repo / "Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi" / f"date={date}" / f"gamePk={game_pk}.envelope.json",
        repo / "Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi" / f"date={date}" / f"gamePk={game_pk}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def internal_game_id(row: dict[str, Any]) -> str:
    date = str(row.get("official_date") or "").replace("-", "")
    away = str(row.get("away_abbreviation") or "UNK")
    home = str(row.get("home_abbreviation") or "UNK")
    pk = str(row.get("game_pk") or "")
    return f"MLB_{date}_{away}_{home}_{pk}"


def team_side_from_ticker(ticker: str, home: str, away: str) -> str:
    suffix = str(ticker).rsplit("-", 1)[-1]
    if suffix == home:
        return "home"
    if suffix == away:
        return "away"
    return ""


def event_tickers_from_crosswalk(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ev = str(row.get("event_ticker") or "")
        if ev:
            out[ev] = row
    return out


def write_month_frames(out_dir: Path, rows: list[dict[str, str]], columns: list[str], ts_key: str) -> int:
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        month = str(row.get(ts_key) or "")[:7]
        if month:
            by_month[month].append(row)
    n = 0
    for month, chunk in sorted(by_month.items()):
        write_csv(out_dir / f"month={month}.csv", pd.DataFrame(chunk), columns)
        n += len(chunk)
    return n


def _iso_any(value: Any) -> str:
    if value in (None, ""):
        return ""
    ts = parse_utc(value)
    if ts is None:
        text = str(value)
        return text.replace("+00:00", "Z") if text.endswith("+00:00") else text
    return iso_z(ts)


def load_crosswalk(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def volume_from_record(rec: dict[str, Any], columns: set[str] | None = None) -> str:
    """Copy volume only from an existing parquet column. Never from print count."""
    keys = VOLUME_KEYS if columns is None else tuple(k for k in VOLUME_KEYS if k in columns)
    for key in keys:
        if columns is not None and key not in columns:
            continue
        raw = rec.get(key)
        if raw in (None, ""):
            continue
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            continue
        return str(value)
    return ""


def trades_schema_matches(frame: pd.DataFrame) -> bool:
    return TRADE_SCHEMA_COLS <= set(frame.columns)


def candles_have_quality_volume(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        raw = row.get("volume")
        if raw in (None, ""):
            continue
        try:
            if int(float(raw)) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dist_e4(dist: Any, field: str) -> str:
    if not isinstance(dist, dict):
        return ""
    raw = dist.get(field)
    if raw in (None, ""):
        raw = dist.get(f"{field}_dollars")
    e4 = dollars_to_e4(raw)
    return "" if e4 is None else str(e4)


def _candle_ts(rec: dict[str, Any]) -> str:
    raw = rec.get("end_period_ts")
    if raw in (None, ""):
        return ""
    try:
        ts = pd.Timestamp(int(float(raw)), unit="s", tz="UTC")
    except (TypeError, ValueError):
        return ""
    return iso_z(ts.to_pydatetime())


def official_from_pbp_envelope(path: Path) -> dict[str, Any] | None:
    try:
        env = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    payload = env.get("payload") if isinstance(env, dict) else None
    if not isinstance(payload, dict):
        payload = env if isinstance(env, dict) else {}
    game = ((payload.get("gameData") or {}).get("game") or {})
    teams = ((payload.get("gameData") or {}).get("teams") or {})
    home = ((teams.get("home") or {}).get("abbreviation") or (teams.get("home") or {}).get("team") or {})
    away = ((teams.get("away") or {}).get("abbreviation") or (teams.get("away") or {}).get("team") or {})
    if isinstance(home, dict):
        home = home.get("abbreviation") or (home.get("team") or {}).get("abbreviation")
    if isinstance(away, dict):
        away = away.get("abbreviation") or (away.get("team") or {}).get("abbreviation")
    date = str(((payload.get("gameData") or {}).get("datetime") or {}).get("officialDate") or "")
    pk = str(payload.get("gamePk") or game.get("pk") or env.get("source_game_id") or "")
    if not pk or not date:
        parent = path.parent.name
        if parent.startswith("date="):
            date = parent.split("=", 1)[-1]
        stem = path.name
        if stem.startswith("gamePk=") and ".envelope" in stem:
            pk = pk or stem.split("=", 1)[-1].split(".", 1)[0]
    if not pk or not date:
        return None
    return {
        "game_pk": str(pk),
        "official_date": date,
        "home_abbreviation": str(home or ""),
        "away_abbreviation": str(away or ""),
        "event_ticker": "",
        "mapping": "UNMATCHED",
        "method": "landing_pbp",
        "has_pbp": True,
        "pbp_path": str(path),
    }


def load_latest_pairs(repo: Path) -> list[dict[str, Any]]:
    runs = repo / DEFAULT_INGEST_RUNS
    if not runs.is_dir():
        return []
    files = sorted(runs.glob("*/game_market_pairs.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            return data
    return []


def merge_crosswalk(
    crosswalk: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    landing_games: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_pk: dict[str, dict[str, Any]] = {}
    for row in crosswalk:
        pk = str(row.get("game_pk") or "")
        if pk:
            by_pk[pk] = dict(row)
    for pair in pairs:
        mapping = str(pair.get("mapping") or "").upper()
        if mapping != "MAPPED":
            continue
        pk = str(pair.get("game_pk") or "")
        ev = str(pair.get("event_ticker") or "")
        if not pk:
            continue
        row = by_pk.get(pk) or {
            "game_pk": pk,
            "official_date": str(pair.get("official_date") or ""),
            "home_abbreviation": "",
            "away_abbreviation": "",
            "has_pbp": False,
            "pbp_path": "",
        }
        if ev and not row.get("event_ticker"):
            row["event_ticker"] = ev
            row["mapping"] = "MAPPED"
            row["method"] = str(row.get("method") or "ingest_rejoin")
        by_pk[pk] = row
    for game in landing_games:
        pk = str(game.get("game_pk") or "")
        if not pk:
            continue
        existing = by_pk.get(pk)
        if existing is None:
            by_pk[pk] = dict(game)
            continue
        if not existing.get("pbp_path") and game.get("pbp_path"):
            existing["pbp_path"] = game["pbp_path"]
            existing["has_pbp"] = True
        if not existing.get("home_abbreviation") and game.get("home_abbreviation"):
            existing["home_abbreviation"] = game["home_abbreviation"]
            existing["away_abbreviation"] = game.get("away_abbreviation") or ""
        if not existing.get("official_date") and game.get("official_date"):
            existing["official_date"] = game["official_date"]
        by_pk[pk] = existing
    return list(by_pk.values())


def collect_landing_pbp_games(repo: Path) -> list[dict[str, Any]]:
    root = repo / DEFAULT_LANDING_PBP
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("date=*/gamePk=*.envelope.json")):
        row = official_from_pbp_envelope(path)
        if row:
            out.append(row)
    return out


def collect_landing_trades(repo: Path, *, dates: set[str] | None = None) -> list[dict[str, Any]]:
    """Kalshi historical trade prints from trade sidecars. yes_bid is never written."""
    out: list[dict[str, Any]] = []
    root = repo / DEFAULT_LANDING_TRADES
    if not root.is_dir():
        return out
    for path in sorted(root.glob("date=*/ticker=*.trades.json")):
        day = path.parent.name.split("=", 1)[-1]
        if dates is not None and day not in dates:
            continue
        out.extend(_landing_trades_from_file(path))
    return out


def _landing_trades_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        data = _json_load(path)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    trades = data.get("trades")
    if not isinstance(trades, list):
        return []
    ticker = str(data.get("ticker") or "")
    out: list[dict[str, Any]] = []
    for rec in trades:
        if not isinstance(rec, dict):
            continue
        if trade_yes_cents(rec) is None:
            continue
        row = dict(rec)
        row.setdefault("ticker", ticker)
        out.append(row)
    return out


def collect_landing_last_prints(
    repo: Path,
    *,
    dates: set[str] | None = None,
    ingested_at: str,
    pipeline_version: str,
    ticker_meta: dict[str, dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], int]:
    """Aggregate one sidecar at a time so raw prints are not held in memory."""
    root = repo / DEFAULT_LANDING_TRADES
    rows: list[dict[str, str]] = []
    n_prints = 0
    if not root.is_dir():
        return rows, n_prints
    for path in sorted(root.glob("date=*/ticker=*.trades.json")):
        day = path.parent.name.split("=", 1)[-1]
        if dates is not None and day not in dates:
            continue
        trades = _landing_trades_from_file(path)
        n_prints += len(trades)
        if not trades:
            continue
        rows.extend(
            aggregate_last_prints(
                trades,
                ingested_at=ingested_at,
                pipeline_version=pipeline_version,
                source_dataset="kalshi_historical_trades",
                ticker_meta=ticker_meta,
            )
        )
    return rows, n_prints


def collect_landing_candles(
    repo: Path,
    *,
    ticker_meta: dict[str, dict[str, str]],
    ingested_at: str,
    pipeline_version: str,
    dates: set[str] | None = None,
) -> list[dict[str, str]]:
    """Genuine yes_bid OHLC from landed Kalshi 1m candles. Never from a print."""
    out: list[dict[str, str]] = []
    root = repo / DEFAULT_LANDING_CANDLES
    if not root.is_dir():
        return out
    seen: set[tuple[str, str]] = set()
    for path in sorted(root.glob("date=*/ticker=*.candles.json")):
        day = path.parent.name.split("=", 1)[-1]
        if dates is not None and day not in dates:
            continue
        try:
            data = _json_load(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("candles_status") or "") == "UNAVAILABLE":
            continue
        candles = data.get("candlesticks")
        if isinstance(candles, dict):
            if candles.get("unavailable"):
                continue
            candles = candles.get("candlesticks") or []
        if not isinstance(candles, list):
            continue
        ticker = str(data.get("ticker") or "")
        info = ticker_meta.get(ticker) or {}
        cols = {"volume", "volume_fp", "volume_hundredths"}
        for rec in candles:
            if not isinstance(rec, dict):
                continue
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
            vol_rec = {
                "volume": rec.get("volume"),
                "volume_fp": rec.get("volume_fp"),
                "volume_hundredths": rec.get("volume_hundredths"),
            }
            out.append(
                {
                    "internal_game_id": str(info.get("internal_game_id") or ""),
                    "ticker": ticker,
                    "team_side": str(info.get("team_side") or ""),
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
                    "yes_ask_close": _dist_e4(ask, "close"),
                    "volume": volume_from_record(vol_rec, cols),
                    "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                    "source_dataset": "kalshi_rest_candlestick",
                    "source_file_hash": "",
                    "pipeline_version": pipeline_version,
                    "derived_at": ingested_at,
                }
            )
    return out


def _e4_str(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return ""


def collect_suite_candles_1m(
    repo: Path,
    *,
    ticker_meta: dict[str, dict[str, str]],
    ingested_at: str,
    pipeline_version: str,
    dates: set[str] | None = None,
    candles_root: Path | None = None,
    skip_tickers: set[str] | None = None,
) -> list[dict[str, str]]:
    """Genuine yes_bid/yes_ask E4 from Suite candles_1m parquet. Never from a print."""
    root = Path(candles_root) if candles_root is not None else repo / DEFAULT_SUITE_CANDLES
    if not root.is_dir():
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for month_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("month=")):
        for path in sorted(month_dir.glob("*.parquet")):
            ticker_name = path.stem
            if skip_tickers is not None and ticker_name in skip_tickers:
                continue
            try:
                frame = pd.read_parquet(path)
            except Exception:
                continue
            if frame is None or frame.empty or "yes_bid_close_e4" not in frame.columns:
                continue
            cols = set(frame.columns)
            for rec in frame.to_dict("records"):
                close = _e4_str(rec.get("yes_bid_close_e4"))
                if not close:
                    continue
                ts_iso = _iso_any(rec.get("end_time"))
                if not ts_iso:
                    continue
                if dates is not None and ts_iso[:10] not in dates:
                    continue
                ticker = str(rec.get("ticker") or "")
                if not ticker:
                    continue
                key = (ticker, ts_iso)
                if key in seen:
                    continue
                seen.add(key)
                info = ticker_meta.get(ticker) or {}
                vol_rec = {
                    "volume": rec.get("volume"),
                    "volume_fp": rec.get("volume_fp"),
                    "volume_hundredths": rec.get("volume_hundredths"),
                }
                out.append(
                    {
                        "internal_game_id": str(info.get("internal_game_id") or ""),
                        "ticker": ticker,
                        "team_side": str(info.get("team_side") or ""),
                        "candle_timestamp": ts_iso,
                        "event_timestamp": ts_iso,
                        "available_at": ts_iso,
                        "ingested_at": ingested_at,
                        "yes_bid_open": _e4_str(rec.get("yes_bid_open_e4")),
                        "yes_bid_high": _e4_str(rec.get("yes_bid_high_e4")),
                        "yes_bid_low": _e4_str(rec.get("yes_bid_low_e4")),
                        "yes_bid_close": close,
                        "yes_ask_open": _e4_str(rec.get("yes_ask_open_e4")),
                        "yes_ask_high": _e4_str(rec.get("yes_ask_high_e4")),
                        "yes_ask_low": _e4_str(rec.get("yes_ask_low_e4")),
                        "yes_ask_close": _e4_str(rec.get("yes_ask_close_e4")),
                        "volume": volume_from_record(vol_rec, cols | set(vol_rec)),
                        "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                        "source_dataset": "warehouse_candles_1m",
                        "source_file_hash": "",
                        "pipeline_version": pipeline_version,
                        "derived_at": ingested_at,
                    }
                )
    return out


def _index_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (str(row.get("ticker") or ""), str(row.get("candle_timestamp") or ""))
        if key[0] and key[1]:
            out[key] = row
    return out


def collect_metadata(market_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted((market_root / "orderbook").glob("date=*/metadata.parquet")):
        try:
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def official_market_result(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"yes", "no"}:
        return value
    return value if value not in {"none", "null", "nan"} else ""


def collect_landing_settlement(repo: Path) -> pd.DataFrame:
    """Kalshi catalog result from Foundation landing. Missing stays missing."""
    root = repo / DEFAULT_LANDING_SETTLEMENT
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return pd.DataFrame()
    for path in sorted(root.glob("date=*/ticker=*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ticker = str(rec.get("ticker") or "")
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "event_ticker": str(rec.get("event_ticker") or ""),
                "result": official_market_result(rec.get("result")),
                "settlement_ts": str(rec.get("settlement_ts") or ""),
                "settlement_time": str(rec.get("settlement_ts") or ""),
                "open_time": str(rec.get("open_time") or ""),
                "close_time": str(rec.get("close_time") or ""),
                "status": str(rec.get("status") or ""),
                "settlement_value_dollars": rec.get("settlement_value_dollars"),
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def merge_market_metadata(canonical: pd.DataFrame, landing: pd.DataFrame) -> pd.DataFrame:
    """Existing kalshi_markets / Data-Real result wins. Landing fills only missing result."""
    if landing is None or landing.empty:
        return canonical if canonical is not None else pd.DataFrame()
    if canonical is None or canonical.empty:
        return landing
    by_ticker: dict[str, dict[str, Any]] = {}
    for rec in canonical.to_dict("records"):
        ticker = str(rec.get("ticker") or "")
        if ticker:
            by_ticker[ticker] = rec
    for rec in landing.to_dict("records"):
        ticker = str(rec.get("ticker") or "")
        if not ticker:
            continue
        existing = by_ticker.get(ticker)
        if existing is None:
            by_ticker[ticker] = rec
            continue
        have = official_market_result(existing.get("result"))
        incoming = official_market_result(rec.get("result"))
        if have in {"yes", "no"}:
            continue
        if incoming in {"yes", "no"} or (incoming and not have):
            merged = dict(existing)
            merged.update({k: v for k, v in rec.items() if v not in (None, "")})
            by_ticker[ticker] = merged
    return pd.DataFrame(list(by_ticker.values()))


def collect_trades_frame(market_root: Path, *, dates: set[str] | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted((market_root / "trades").glob("date=*/trades.parquet")):
        day = path.parent.name.split("=", 1)[-1]
        if dates is not None and day not in dates:
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        if not trades_schema_matches(frame):
            continue
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _resolve_market_roots(
    repo: Path,
    market_root: Path,
    extra_market_roots: list[Path] | None,
) -> list[Path]:
    roots = [Path(market_root)]
    extras: list[Path]
    if extra_market_roots is None:
        extras = [repo / p for p in DEFAULT_TRADE_ROOTS]
    else:
        extras = [Path(p) for p in extra_market_roots]
    seen = {roots[0].resolve() if roots[0].exists() else roots[0]}
    for extra in extras:
        path = extra if extra.is_absolute() else repo / extra
        key = path.resolve() if path.exists() else path
        if key in seen:
            continue
        if path.is_dir():
            seen.add(key)
            roots.append(path)
    return roots


def collect_frames_from_roots(
    roots: list[Path],
    collector,
    **kwargs: Any,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        if not root.is_dir():
            continue
        part = collector(root, **kwargs)
        if part is None or getattr(part, "empty", True):
            continue
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def collect_genuine_candles(
    market_root: Path,
    *,
    ticker_meta: dict[str, dict[str, str]],
    ingested_at: str,
    pipeline_version: str,
    dates: set[str] | None = None,
) -> list[dict[str, str]]:
    """Only rows that already contain yes_bid. Never derived from a print."""
    out: list[dict[str, str]] = []
    for path in sorted((market_root / "orderbook").glob("date=*/orderbook.parquet")):
        day = path.parent.name.split("=", 1)[-1]
        if dates is not None and day not in dates:
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        if "event_type" not in frame.columns or "yes_bid_cents" not in frame.columns:
            continue
        keep = frame[frame["event_type"].astype(str) == "candlestick_close"]
        if keep.empty:
            continue
        cols = set(keep.columns)
        for rec in keep.to_dict("records"):
            bid = rec.get("yes_bid_cents")
            ask = rec.get("yes_ask_cents")
            bid_e4 = cents_to_e4(bid)
            if bid_e4 is None:
                continue
            ask_e4 = cents_to_e4(ask)
            ms = rec.get("exchange_timestamp_ms")
            ts = None
            try:
                if ms not in (None, ""):
                    ts = pd.Timestamp(int(float(ms)), unit="ms", tz="UTC")
            except (TypeError, ValueError):
                ts = None
            if ts is None:
                continue
            ticker = str(rec.get("ticker") or "")
            info = ticker_meta.get(ticker) or {}
            ts_iso = iso_z(ts.to_pydatetime())
            out.append(
                {
                    "internal_game_id": str(info.get("internal_game_id") or ""),
                    "ticker": ticker,
                    "team_side": str(info.get("team_side") or ""),
                    "candle_timestamp": ts_iso,
                    "event_timestamp": ts_iso,
                    "available_at": ts_iso,
                    "ingested_at": ingested_at,
                    "yes_bid_open": str(bid_e4),
                    "yes_bid_high": str(bid_e4),
                    "yes_bid_low": str(bid_e4),
                    "yes_bid_close": str(bid_e4),
                    "yes_ask_open": "" if ask_e4 is None else str(ask_e4),
                    "yes_ask_high": "" if ask_e4 is None else str(ask_e4),
                    "yes_ask_low": "" if ask_e4 is None else str(ask_e4),
                    "yes_ask_close": "" if ask_e4 is None else str(ask_e4),
                    "volume": volume_from_record(rec, cols),
                    "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                    "source_dataset": "kalshi_rest_candlestick",
                    "source_file_hash": "",
                    "pipeline_version": pipeline_version,
                    "derived_at": ingested_at,
                }
            )
    return out


def build_games(
    crosswalk: list[dict[str, Any]],
    *,
    markets: pd.DataFrame,
    ingested_at: str,
    pipeline_version: str,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    ticker_meta: dict[str, dict[str, str]] = {}
    games: list[dict[str, str]] = []
    seen: set[str] = set()
    market_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if markets is not None and not markets.empty:
        for rec in markets.to_dict("records"):
            ev = str(rec.get("event_ticker") or "")
            if ev:
                market_by_event[ev].append(rec)
    for row in crosswalk:
        ev = str(row.get("event_ticker") or "")
        gid = internal_game_id(row)
        if gid in seen:
            continue
        seen.add(gid)
        home = str(row.get("home_abbreviation") or "")
        away = str(row.get("away_abbreviation") or "")
        home_t = ""
        away_t = ""
        for rec in market_by_event.get(ev, []):
            ticker = str(rec.get("ticker") or "")
            side = team_side_from_ticker(ticker, home, away)
            if side == "home":
                home_t = ticker
            elif side == "away":
                away_t = ticker
            ticker_meta[ticker] = {
                "internal_game_id": gid,
                "team_side": side,
                "event_ticker": ev,
            }
        if not home_t or not away_t:
            # Crosswalk ticker + team codes. No display-name fuzzy match.
            if ev and home:
                home_t = home_t or f"{ev}-{home}"
            if ev and away:
                away_t = away_t or f"{ev}-{away}"
            if home_t:
                ticker_meta.setdefault(
                    home_t,
                    {"internal_game_id": gid, "team_side": "home", "event_ticker": ev},
                )
            if away_t:
                ticker_meta.setdefault(
                    away_t,
                    {"internal_game_id": gid, "team_side": "away", "event_ticker": ev},
                )
        date = str(row.get("official_date") or "")
        games.append(
            {
                "internal_game_id": gid,
                "sport": "MLB",
                "season": "2025-2026",
                "league": "MLB",
                "game_date": date,
                "scheduled_start": "",
                "actual_start": "",
                "home_team_id": home,
                "away_team_id": away,
                "home_team_name": home,
                "away_team_name": away,
                "source_game_id": str(row.get("game_pk") or ""),
                "warehouse_game_id": str(row.get("game_pk") or ""),
                "event_ticker": ev,
                "kalshi_market_yes_home": home_t,
                "kalshi_market_yes_away": away_t,
                "final_home_score": "",
                "final_away_score": "",
                "home_win": "",
                "away_win": "",
                "p5_vs_p5": "",
                "identity_available_at": f"{date}T00:00:00Z" if date else "",
                "availability_quality": "OBSERVED",
                "result_available_at": "",
                "event_timestamp": f"{date}T00:00:00Z" if date else "",
                "available_at": f"{date}T00:00:00Z" if date else "",
                "ingested_at": ingested_at,
                "source_dataset": "mlb_game_crosswalk",
                "source_file_hash": "",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    return games, ticker_meta


def build_markets(
    metadata: pd.DataFrame,
    ticker_meta: dict[str, dict[str, str]],
    *,
    ingested_at: str,
    pipeline_version: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if metadata is None or metadata.empty:
        return rows
    seen: set[str] = set()
    for rec in metadata.to_dict("records"):
        ticker = str(rec.get("ticker") or "")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        info = ticker_meta.get(ticker) or {}
        result = str(rec.get("result") or "").strip().lower()
        sve = ""
        yes = ""
        if result == "yes":
            sve, yes = "10000", "1"
        elif result == "no":
            sve, yes = "0", "0"
        close = _iso_any(rec.get("close_time"))
        settle = _iso_any(rec.get("settlement_ts") or rec.get("settlement_time"))
        rows.append(
            {
                "internal_game_id": str(info.get("internal_game_id") or ""),
                "ticker": ticker,
                "event_id": str(rec.get("event_ticker") or info.get("event_ticker") or ""),
                "event_ticker": str(rec.get("event_ticker") or info.get("event_ticker") or ""),
                "team_side": str(info.get("team_side") or ""),
                "result": result,
                "settlement_value_e4": sve,
                "kalshi_yes_settled": yes,
                "close_time": close,
                "expiration_time": close,
                "settlement_time": settle,
                "event_timestamp": close or settle,
                "available_at": close or settle,
                "result_available_at": settle or close,
                "ingested_at": ingested_at,
                "source_dataset": "kalshi_metadata",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    return rows


def ingest_mlb(
    *,
    cfg: RollerConfig | None = None,
    dest: Path | None = None,
    crosswalk_path: Path | None = None,
    market_root: Path | None = None,
    pbp_limit: int | None = None,
    market_dates: set[str] | None = None,
    require_market_for_pbp: bool = False,
    extra_market_roots: list[Path] | None = None,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    repo = _repo_root(cfg)
    now = now_utc_iso()
    version = cfg.pipeline_version
    dest = dest or (cfg.root / "data" / "mlb" / "2025_2026" / "canonical")
    dest.mkdir(parents=True, exist_ok=True)
    xw_path = Path(crosswalk_path) if crosswalk_path else repo / DEFAULT_CROSSWALK
    mroot = Path(market_root) if market_root else repo / DEFAULT_MARKET_ROOT
    market_roots = _resolve_market_roots(repo, mroot, extra_market_roots)
    crosswalk = load_crosswalk(xw_path) if xw_path.is_file() else []
    crosswalk = merge_crosswalk(
        crosswalk,
        load_latest_pairs(repo),
        collect_landing_pbp_games(repo),
    )
    metadata = merge_market_metadata(
        collect_frames_from_roots(market_roots, collect_metadata),
        collect_landing_settlement(repo),
    )
    games, ticker_meta = build_games(crosswalk, markets=metadata, ingested_at=now, pipeline_version=version)
    write_csv(dest / "games.csv", pd.DataFrame(games), GAMES_COLUMNS)

    market_rows = build_markets(metadata, ticker_meta, ingested_at=now, pipeline_version=version)
    write_csv(dest / "kalshi_markets.csv", pd.DataFrame(market_rows), MARKET_COLUMNS)

    market_game_ids = {r["internal_game_id"] for r in market_rows if r.get("internal_game_id")}
    pbp_rows: list[dict[str, str]] = []
    pbp_games = 0
    pbp_files = 0
    for row in crosswalk:
        gid = internal_game_id(row)
        if require_market_for_pbp and market_game_ids and gid not in market_game_ids:
            continue
        path = resolve_pbp_path(row, repo)
        if path is None:
            continue
        parsed = parse_file(
            path,
            internal_game_id=gid,
            ingested_at=now,
            pipeline_version=version,
            source_file_hash=_sha256_file(path)[:16],
        )
        if not parsed:
            continue
        pbp_rows.extend(parsed)
        pbp_games += 1
        pbp_files += 1
        if pbp_limit is not None and pbp_games >= pbp_limit:
            break
    write_month_frames(dest / "pbp", pbp_rows, PBP_COLUMNS, "event_timestamp")

    trades_df = collect_frames_from_roots(
        market_roots, collect_trades_frame, dates=market_dates
    )
    last_print = aggregate_last_prints_frame(
        trades_df,
        ingested_at=now,
        pipeline_version=version,
        ticker_meta=ticker_meta,
    )
    landing_last, landing_print_count = collect_landing_last_prints(
        repo,
        dates=market_dates,
        ingested_at=now,
        pipeline_version=version,
        ticker_meta=ticker_meta,
    )
    last_by_key = _index_rows(last_print)
    last_by_key.update(_index_rows(landing_last))
    last_print = list(last_by_key.values())
    write_month_frames(dest / "kalshi_last_trade", last_print, LAST_TRADE_COLUMNS, "candle_timestamp")

    candles: list[dict[str, str]] = []
    for root in market_roots:
        candles.extend(
            collect_genuine_candles(
                root,
                ticker_meta=ticker_meta,
                ingested_at=now,
                pipeline_version=version,
                dates=market_dates,
            )
        )
    landing_candles = collect_landing_candles(
        repo,
        ticker_meta=ticker_meta,
        ingested_at=now,
        pipeline_version=version,
        dates=market_dates,
    )
    candle_by_key = _index_rows(candles)
    candle_by_key.update(_index_rows(landing_candles))
    suite_candles = collect_suite_candles_1m(
        repo,
        ticker_meta=ticker_meta,
        ingested_at=now,
        pipeline_version=version,
        dates=market_dates,
        skip_tickers={key[0] for key in candle_by_key},
    )
    for key, row in _index_rows(suite_candles).items():
        candle_by_key.setdefault(key, row)
    candles = list(candle_by_key.values())
    if candles:
        write_month_frames(dest / "kalshi_candles", candles, CANDLE_COLUMNS, "candle_timestamp")

    quality_ready = candles_have_quality_volume(candles)
    observation_basis = (
        "TRADABLE_YES_BID_AVAILABLE+LAST_TRADE_PRINT" if quality_ready else "LAST_TRADE_PRINT"
    )
    manifest = {
        "sport": "MLB",
        "season": "2025-2026",
        "source": {
            "pbp": "mlb_statsapi",
            "crosswalk": str(xw_path),
            "markets": [str(r) for r in market_roots],
            "suite_candles_1m": str(repo / DEFAULT_SUITE_CANDLES),
        },
        "counts": {
            "games": len(games),
            "pbp_rows": len(pbp_rows),
            "pbp_games": pbp_games,
            "pbp_files": pbp_files,
            "markets": len(market_rows),
            "last_trade_bars": len(last_print),
            "genuine_candles": len(candles),
            "trade_prints_read": (0 if trades_df is None else int(len(trades_df))) + landing_print_count,
        },
        "coverage": {
            "pbp_with_market": len(market_game_ids & {r["internal_game_id"] for r in pbp_rows}),
            "markets_with_game": sum(1 for r in market_rows if r.get("internal_game_id")),
        },
        "observation_basis": observation_basis,
        "notes": [
            "LAST TRADE ≠ YES BID",
            "CANDLE/PRINT PATH ≠ FILL",
            "Minutes without a print are absent, not forward-filled.",
            "Genuine yes_bid candles are emitted only when Kalshi candlesticks contain yes_bid.",
            "Volume is copied from parquet or landed Kalshi volume / volume_fp / volume_hundredths only when present.",
            "Landing 1m candles and historical trade prints are read from Foundation/Ingest/landing.",
            "Suite candles_1m parquet fills ticker+minute keys not already in landing or Data-Real. Never from a print.",
            "Volume is never derived from print count.",
            "Settlement is Kalshi market result when present; never inferred from PBP.",
            (
                "Candles pass frozen quality()."
                if quality_ready
                else "Candles cannot pass frozen quality() (no positive volume). LAST TRADE is the runnable path."
            ),
        ],
        "candles_quality_ready": quality_ready,
        "candle_volume_present": quality_ready,
        "generated_at": now,
        "pipeline_version": version,
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["dataset_version"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    (dest / "dataset_version.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def ticker_meta_from_games(games: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if games is None or games.empty:
        return out
    for rec in games.to_dict("records"):
        gid = str(rec.get("internal_game_id") or "")
        home = str(rec.get("kalshi_market_yes_home") or "")
        away = str(rec.get("kalshi_market_yes_away") or "")
        if home:
            out[home] = {"internal_game_id": gid, "team_side": "home"}
        if away:
            out[away] = {"internal_game_id": gid, "team_side": "away"}
    return out


def refresh_mlb_candles(
    *,
    cfg: RollerConfig | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Rebuild the candle partition from landing + Data-Real + Suite gap fill.

    Does not remint games, rewrite PBP, or convert last-trade into yes-bid.
    Existing ticker+minute rows stay; Suite fills only missing keys.
    """
    cfg = cfg or RollerConfig()
    repo = _repo_root(cfg)
    now = now_utc_iso()
    version = cfg.pipeline_version
    dest = dest or (cfg.root / "data" / "mlb" / "2025_2026" / "canonical")
    games = pd.read_csv(dest / "games.csv", dtype=str, keep_default_na=False)
    ticker_meta = ticker_meta_from_games(games)
    candle_dir = dest / "kalshi_candles"
    existing_tickers: set[str] = set()
    existing_rows = 0
    month_files = sorted(candle_dir.glob("month=*.csv")) if candle_dir.is_dir() else []
    for path in month_files:
        part = pd.read_csv(path, usecols=["ticker"])
        existing_rows += len(part)
        existing_tickers.update(part["ticker"].dropna().astype(str))
    suite = collect_suite_candles_1m(
        repo,
        ticker_meta=ticker_meta,
        ingested_at=now,
        pipeline_version=version,
        skip_tickers=existing_tickers,
    )
    added = 0
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in suite:
        month = str(row.get("candle_timestamp") or "")[:7]
        if month:
            by_month[month].append(row)
    for month, chunk in sorted(by_month.items()):
        path = candle_dir / f"month={month}.csv"
        frame = pd.DataFrame(chunk)
        if path.exists():
            old = pd.read_csv(path, dtype=str, keep_default_na=False)
            merged = pd.concat([old, frame], ignore_index=True)
            merged = merged.drop_duplicates(["ticker", "candle_timestamp"], keep="first")
            added += int(len(merged) - len(old))
            write_csv(path, merged, CANDLE_COLUMNS)
        else:
            added += len(chunk)
            write_csv(path, frame, CANDLE_COLUMNS)
    total = existing_rows + added
    quality_ready = candles_have_quality_volume(suite) or existing_rows > 0
    manifest_path = dest / "dataset_version.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = dict(manifest.get("counts") or {})
    counts["genuine_candles"] = total
    counts["suite_candles_added"] = added
    manifest["counts"] = counts
    source = dict(manifest.get("source") or {})
    source["suite_candles_1m"] = str(repo / DEFAULT_SUITE_CANDLES)
    manifest["source"] = source
    notes = list(manifest.get("notes") or [])
    gap_note = (
        "Suite candles_1m parquet fills ticker+minute keys not already in landing or Data-Real. Never from a print."
    )
    if gap_note not in notes:
        notes.append(gap_note)
    manifest["notes"] = notes
    manifest["candles_quality_ready"] = bool(manifest.get("candles_quality_ready") or quality_ready)
    manifest["candle_volume_present"] = bool(manifest.get("candle_volume_present") or quality_ready)
    manifest["observation_basis"] = "TRADABLE_YES_BID_AVAILABLE+LAST_TRADE_PRINT"
    manifest["generated_at"] = now
    manifest["pipeline_version"] = version
    raw = json.dumps({k: v for k, v in manifest.items() if k != "dataset_version"}, sort_keys=True, separators=(",", ":"))
    manifest["dataset_version"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    import sys

    if "--candles-only" in sys.argv:
        manifest = refresh_mlb_candles()
    else:
        manifest = ingest_mlb()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
