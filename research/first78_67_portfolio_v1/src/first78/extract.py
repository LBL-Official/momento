"""Close-proxy FIRST78 scan on the locked 936. Does not rescan to change N."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from first78.clocks import align, window_ok
from first78.timeutil import in_historical_entry_window

REPO = Path(__file__).resolve().parents[4]
CSV_PATH = REPO / "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"
NBA_ROOT = REPO / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"
NCAAB_ROOT = REPO / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"
FOUR = {("NBA", "Q2"), ("NBA", "Q3"), ("NCAAB", "H1_2"), ("NCAAB", "H2_1")}
HIT_E4 = 7800
STOP_E4 = 6700
MAX_SPREAD_E4 = 1000


def parse_ts(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return int(stamp.timestamp())


def _opt_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_universe() -> list[dict]:
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["sport"].strip(), row["slice"].strip())
            if key not in FOUR:
                continue
            rows.append(row)
    if len(rows) != 936:
        raise RuntimeError(f"derived four count {len(rows)} != 936")
    return rows


def _index_candles(root: Path) -> dict[str, Path]:
    return {path.stem: path for path in root.joinpath("candles_1m").rglob("*.parquet")}


def _markets_by_event(path: Path) -> dict[str, list[dict]]:
    table = pq.read_table(
        path,
        columns=[
            "ticker",
            "event_id",
            "game_id",
            "team",
            "opponent",
            "result",
            "settlement_value_e4",
            "close_time",
            "expiration_time",
            "settlement_time",
            "occurrence_datetime",
            "yes_subtitle",
        ],
    )
    out: dict[str, list[dict]] = {}
    for i in range(table.num_rows):
        event = table.column("event_id")[i].as_py()
        rec = {
            "ticker": table.column("ticker")[i].as_py(),
            "event_id": event,
            "game_id": table.column("game_id")[i].as_py(),
            "team": table.column("team")[i].as_py() or table.column("yes_subtitle")[i].as_py(),
            "opponent": table.column("opponent")[i].as_py(),
            "result": table.column("result")[i].as_py(),
            "settlement_value_e4": _opt_int(table.column("settlement_value_e4")[i].as_py()),
            "close_time_ts": parse_ts(table.column("close_time")[i].as_py()),
            "expiration_time_ts": parse_ts(table.column("expiration_time")[i].as_py()),
            "settlement_time_ts": parse_ts(table.column("settlement_time")[i].as_py()),
            "occurrence_ts": parse_ts(table.column("occurrence_datetime")[i].as_py()),
        }
        out.setdefault(event, []).append(rec)
    return out


def _quality(bid: int | None, ask: int | None, vol: int | None, had: bool) -> bool:
    if bid is None or ask is None:
        return False
    if bid > ask:
        return False
    if ask - bid > MAX_SPREAD_E4:
        return False
    if vol is not None and vol > 0:
        return True
    return had


def _read_bars(path: Path) -> list[dict]:
    table = pq.read_table(
        path,
        columns=[
            "end_period_ts",
            "yes_bid_close_e4",
            "yes_bid_low_e4",
            "yes_ask_close_e4",
            "volume_hundredths",
            "is_valid",
            "is_duplicate",
            "orderbook_depth_available",
        ],
    )
    rows = []
    for i in range(table.num_rows):
        if not table.column("is_valid")[i].as_py():
            continue
        if table.column("is_duplicate")[i].as_py():
            continue
        rows.append(
            {
                "ts": int(table.column("end_period_ts")[i].as_py()),
                "bid": _opt_int(table.column("yes_bid_close_e4")[i].as_py()),
                "low": _opt_int(table.column("yes_bid_low_e4")[i].as_py()),
                "ask": _opt_int(table.column("yes_ask_close_e4")[i].as_py()),
                "vol": _opt_int(table.column("volume_hundredths")[i].as_py()),
                "depth": table.column("orderbook_depth_available")[i].as_py(),
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def scan_contract(bars: list[dict]) -> dict:
    had = False
    seen_below = False
    first_i = None
    quality_rows: list[dict] = []
    for bar in bars:
        if not _quality(bar["bid"], bar["ask"], bar["vol"], had):
            continue
        had = True
        quality_rows.append(bar)
        if first_i is None:
            if bar["bid"] is not None and bar["bid"] < HIT_E4:
                seen_below = True
            elif seen_below and bar["bid"] is not None and bar["bid"] >= HIT_E4:
                first_i = len(quality_rows) - 1
    if first_i is None:
        return {"cross_found": False, "tradable": False}
    entry = quality_rows[first_i]
    stop = None
    for bar in quality_rows[first_i + 1 :]:
        if bar["bid"] is not None and bar["bid"] <= STOP_E4:
            stop = bar
            break
    next_bar = quality_rows[first_i + 1] if first_i + 1 < len(quality_rows) else None
    path = [[bar["ts"], None if bar["bid"] is None else bar["bid"] // 100] for bar in quality_rows[max(0, first_i - 5) :]]
    return {
        "cross_found": True,
        "tradable": True,
        "signal_ts": entry["ts"],
        "observed_close_cents": entry["bid"] // 100,
        "overshoot_cents": entry["bid"] // 100 - 78,
        "ask_cents": None if entry["ask"] is None else entry["ask"] // 100,
        "spread_cents": None if entry["ask"] is None else (entry["ask"] - entry["bid"]) // 100,
        "ambiguous_entry_bar": entry["low"] is not None and entry["low"] <= STOP_E4,
        "depth_available": bool(entry["depth"]),
        "stop_ts": None if stop is None else stop["ts"],
        "stop_close_cents": None if stop is None else stop["bid"] // 100,
        "stop_gap_cents": None if stop is None else 67 - (stop["bid"] // 100),
        "next_bar_ts": None if next_bar is None else next_bar["ts"],
        "next_bar_bid_cents": None if next_bar is None else next_bar["bid"] // 100,
        "path": path,
    }


def _outcome(market: dict, scanned: dict) -> str:
    result = str(market.get("result") or "").lower()
    if result not in {"yes", "no"}:
        return "UNRESOLVED"
    if scanned.get("stop_ts") is not None:
        return "STOP"
    return "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT"


def extract(progress=print) -> list[dict]:
    universe = load_universe()
    nba_markets = _markets_by_event(NBA_ROOT / "markets" / "markets.parquet")
    ncaab_markets = _markets_by_event(NCAAB_ROOT / "markets" / "markets.parquet")
    candles = {
        "NBA": _index_candles(NBA_ROOT),
        "NCAAB": _index_candles(NCAAB_ROOT),
    }
    games = []
    for i, row in enumerate(universe, start=1):
        sport = row["sport"].strip()
        event_id = row["event_id"].strip()
        markets = (nba_markets if sport == "NBA" else ncaab_markets).get(event_id, [])
        contracts = []
        for market in markets:
            ticker = market["ticker"]
            path = candles[sport].get(ticker)
            if path is None:
                contracts.append({**market, "cross_found": False, "tradable": False, "reason": "NO_CANDLES"})
                continue
            scanned = scan_contract(_read_bars(path))
            scanned.update(market)
            scanned["sport"] = sport
            scanned["contract_id"] = ticker
            if scanned.get("cross_found"):
                try:
                    clock = align(sport, event_id, int(scanned["signal_ts"]))
                except Exception as exc:  # noqa: BLE001 — clock failure is data, not a crash of the book
                    clock = {
                        "bucket": "UNALIGNED",
                        "clock_quality": "ALIGN_ERROR",
                        "period": None,
                        "period_remaining_s": None,
                        "phase": None,
                        "reason": str(exc),
                    }
                scanned["clock"] = clock
                scanned["window_eligible"] = window_ok(sport, clock.get("bucket") or "")
                scanned["date_eligible"] = in_historical_entry_window(int(scanned["signal_ts"]))
                scanned["exit_reason"] = _outcome(market, scanned)
            contracts.append(scanned)
        games.append(
            {
                "sport": sport,
                "slice": row["slice"].strip(),
                "game_id": row["game_id"].strip(),
                "event_id": event_id,
                "first80_ticker": row["ticker"].strip(),
                "matchup": f"{row['away_team']} at {row['home_team']}",
                "game_date": row["game_date"].strip(),
                "dataset_split": row["dataset_split"].strip(),
                "contracts": contracts,
            }
        )
        if progress and i % 100 == 0:
            progress(f"scanned {i}/{len(universe)}")
    return games
