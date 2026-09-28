"""Build the ex-ante population for one window. Does not tune thresholds."""

from __future__ import annotations

import csv
import gzip
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from first78.clocks import align, window_ok
from first78.extract import _index_candles, _markets_by_event, _read_bars, parse_ts

from oos_adverse.april_clock import align_april
from oos_adverse.diagnostic_first80 import later_threshold_in_window
from oos_adverse.eligibility import WINDOWS, choose_contract, dollars_to_e4, in_window, local_day, scan_bars

LA = ZoneInfo("America/Los_Angeles")
DATE_RX = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})")
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

REPO = Path(__file__).resolve().parents[4]
NBA_2526 = REPO / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"
NCAAB_2526 = REPO / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"
APR_CANDLES = REPO / "Backtesting Suite/Data/NBA/2024-2025/warehouse/raw/kalshi/nba/candlesticks"
APR_MARKETS = REPO / "Backtesting Suite/Data/NBA/2024-2025/warehouse/raw/kalshi/nba/markets/markets.jsonl.gz"
APR_NCAAB_MARKETS = REPO / "Backtesting Suite/Data/NCAAB/2024-2025/warehouse/raw/kalshi/ncaab/markets/markets.jsonl.gz"
LEGACY = REPO / "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"
FOUR = {("NBA", "Q2"), ("NBA", "Q3"), ("NCAAB", "H1_2"), ("NCAAB", "H2_1")}
PREFIX = {"NBA": "KXNBAGAME", "NCAAB": "KXNCAAMBGAME"}


def ticker_date(event_id: str):
    match = DATE_RX.search(str(event_id))
    if not match:
        return None
    month = MONTHS.get(match.group(2))
    if month is None:
        return None
    return datetime(2000 + int(match.group(1)), month, int(match.group(3)), tzinfo=LA)


def inventory_hit(event_id: str, occurrence_ts: int | None, test_id: str) -> str | None:
    """How the event entered the window. A blank occurrence uses the ticker date."""
    start, end = WINDOWS[test_id]
    if occurrence_ts is not None:
        return "OCCURRENCE" if in_window(int(occurrence_ts), test_id) else None
    stamped = ticker_date(event_id)
    if stamped is not None and start <= stamped < end:
        return "TICKER_EVENT_DATE"
    return None


def legacy_event_ids() -> set[str]:
    found = set()
    with LEGACY.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (row["sport"].strip(), row["slice"].strip()) in FOUR:
                found.add(row["event_id"].strip())
    return found


def _candidate(sport: str, event_id: str, market: dict, scanned: dict, test_id: str, stage: str) -> dict | None:
    result = str(market.get("result") or "").lower()
    settlement_ts = market.get("settlement_time_ts")
    if scanned.get("stop_ts") is not None:
        exit_reason = "STOP"
        exit_ts = int(scanned["stop_ts"])
        cash_ts = exit_ts
    elif result in {"yes", "no"} and settlement_ts is not None and int(settlement_ts) >= int(scanned["signal_ts"]):
        exit_reason = "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT"
        exit_ts = int(settlement_ts)
        cash_ts = exit_ts
    else:
        return None
    bars = [
        {"ts": int(bar["ts"]), "bid": bar["bid"], "low": bar.get("low"), "ask": bar["ask"], "vol": bar.get("vol")}
        for bar in scanned.get("quality_bars") or []
    ]
    return {
        "test_id": test_id,
        "sport": sport,
        "event_id": event_id,
        "game_id": event_id,
        "contract_id": market["ticker"],
        "signal_ts": int(scanned["signal_ts"]),
        "exit_ts": exit_ts,
        "cash_ts": cash_ts,
        "exit_reason": exit_reason,
        "terminal_result": result if result in {"yes", "no"} else None,
        "settlement_ts": None if settlement_ts is None else int(settlement_ts),
        "local_day": local_day(int(scanned["signal_ts"])),
        "observed_close_cents": scanned.get("observed_close_cents"),
        "overshoot_cents": scanned.get("overshoot_cents"),
        "stage": stage,
        "cash_label": "HYPOTHETICAL_CASH_AT_SETTLEMENT_TIME" if exit_reason != "STOP" else "ASSUMED_SALE_AT_STOP_SIGNAL",
        "bars": bars,
    }


def _clock(sport: str, event_id: str, ts: int, test_id: str) -> dict:
    if test_id == "APR_2025" and sport == "NBA":
        return align_april(event_id, ts)
    try:
        return align(sport, event_id, ts)
    except Exception as exc:  # noqa: BLE001 — a missed clock is missing data
        return {"bucket": "UNALIGNED", "clock_quality": "ALIGN_ERROR", "reason": str(exc), "stage": "STAGE_UNLABELED"}


def _from_markets(test_id: str, sport: str, markets: dict, candles: dict, reader) -> tuple[list[dict], list[dict], dict]:
    legacy = legacy_event_ids()
    candidates = []
    exclusions = []
    paths = {}
    conditioned_games = set()
    for event_id, mkts in markets.items():
        prepared = []
        bar_sets = []
        stage = "STAGE_UNLABELED"
        for market in mkts:
            bars = reader(candles.get(market["ticker"]))
            if bars is None:
                exclusions.append({"event_id": event_id, "contract_id": market["ticker"], "sport": sport, "reason": "MISSING_CANDLES"})
                continue
            scanned = scan_bars(bars)
            bar_sets.append(bars)
            if not scanned.get("cross_found"):
                prepared.append(
                    {
                        "contract_id": market["ticker"],
                        "cross_found": False,
                        "tradable": False,
                        "window_eligible": False,
                        "date_eligible": False,
                        "reason": scanned.get("reason"),
                        "signal_ts": 0,
                    }
                )
                continue
            clock = _clock(sport, event_id, int(scanned["signal_ts"]), test_id)
            stage = clock.get("stage") or stage
            prepared.append(
                {
                    **market,
                    "contract_id": market["ticker"],
                    "cross_found": True,
                    "tradable": True,
                    "window_eligible": window_ok(sport, clock.get("bucket") or ""),
                    "date_eligible": in_window(int(scanned["signal_ts"]), test_id),
                    "clock_bucket": clock.get("bucket"),
                    "reason": None,
                    "signal_ts": int(scanned["signal_ts"]),
                    "_scanned": scanned,
                    "_clock": clock,
                }
            )
        if bar_sets and _game_conditioned(sport, event_id, bar_sets, test_id):
            conditioned_games.add(event_id)
        choice = choose_contract(prepared)
        chosen = choice.get("chosen")
        if chosen is None:
            exclusions.append(
                {
                    "event_id": event_id,
                    "contract_id": None,
                    "sport": sport,
                    "reason": choice.get("rejection_reason") or "NO_ELIGIBLE_CONTRACT",
                }
            )
            continue
        cand = _candidate(sport, event_id, chosen, chosen["_scanned"], test_id, stage)
        if cand is None:
            exclusions.append({"event_id": event_id, "contract_id": chosen["contract_id"], "sport": sport, "reason": "UNRESOLVED_EXIT"})
            continue
        cand["clock_bucket"] = chosen.get("clock_bucket")
        cand["legacy_lock_intersection"] = event_id in legacy
        cand["diagnostic_conditioned"] = event_id in conditioned_games
        paths[cand["contract_id"]] = [(bar["ts"], bar["bid"] // 100) for bar in cand["bars"]]
        candidates.append(cand)
    return candidates, exclusions, paths


def _game_conditioned(sport: str, event_id: str, bar_sets: list[list[dict]], test_id: str) -> bool:
    def clock_ok(ts: int) -> bool:
        clock = _clock(sport, event_id, ts, test_id)
        return window_ok(sport, clock.get("bucket") or "")

    def date_ok(ts: int) -> bool:
        return in_window(ts, test_id)

    return any(later_threshold_in_window(bars, clock_ok, date_ok) for bars in bar_sets)


def _read_raw_candle(ticker: str) -> list[dict] | None:
    path = APR_CANDLES / f"ticker={ticker}" / "candles.jsonl.gz"
    if not path.exists():
        return None
    bars = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            payload = json.loads(line).get("payload") or {}
            for row in payload.get("candlesticks") or []:
                bid = (row.get("yes_bid") or {}).get("close")
                ask = (row.get("yes_ask") or {}).get("close")
                low = (row.get("yes_bid") or {}).get("low")
                vol = row.get("volume")
                bars.append(
                    {
                        "ts": int(row["end_period_ts"]),
                        "bid": dollars_to_e4(bid),
                        "ask": dollars_to_e4(ask),
                        "low": dollars_to_e4(low),
                        "vol": None if vol in (None, "") else int(float(vol) * 100),
                    }
                )
    bars.sort(key=lambda bar: bar["ts"])
    return bars


def _april_nba_markets(test_id: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    if not APR_MARKETS.exists():
        return grouped
    with gzip.open(APR_MARKETS, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            ticker = str(row.get("ticker") or "")
            event = str(row.get("event_ticker") or "")
            if not ticker.startswith("KXNBAGAME") or not event.startswith("KXNBAGAME"):
                continue
            occ = parse_ts(row.get("occurrence_datetime"))
            if inventory_hit(event, occ, test_id) is None:
                continue
            grouped.setdefault(event, []).append(
                {
                    "ticker": ticker,
                    "event_id": event,
                    "result": row.get("result"),
                    "settlement_time_ts": parse_ts(row.get("settlement_ts") or row.get("settlement_time")),
                    "occurrence_ts": occ,
                }
            )
    return grouped


def _count_ncaab_april_markets(test_id: str) -> int:
    if not APR_NCAAB_MARKETS.exists():
        return 0
    count = 0
    with gzip.open(APR_NCAAB_MARKETS, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            if not str(row.get("ticker") or "").startswith("KXNCAAMBGAME"):
                continue
            occ = parse_ts(row.get("occurrence_datetime"))
            if inventory_hit(str(row.get("event_ticker") or row.get("ticker") or ""), occ, test_id) is not None:
                count += 1
    return count


def extract_window(test_id: str) -> dict:
    if test_id == "OCT_2025":
        pieces = []
        exclusions = []
        paths = {}
        sport_status = {}
        for sport, root in (("NBA", NBA_2526), ("NCAAB", NCAAB_2526)):
            markets = _markets_by_event(root / "markets" / "markets.parquet")
            kept = {}
            for event, mkts in markets.items():
                mkts = [m for m in mkts if str(m["ticker"]).startswith(PREFIX[sport])]
                occs = [m["occurrence_ts"] for m in mkts if m.get("occurrence_ts")]
                source = inventory_hit(str(event), min(occs) if occs else None, test_id)
                if source is not None:
                    for market in mkts:
                        market["inventory_date_source"] = source
                    kept[event] = mkts
            candles = _index_candles(root)
            cands, exc, path = _from_markets(
                test_id,
                sport,
                kept,
                candles,
                lambda path: None if path is None else _read_bars(path),
            )
            pieces.extend(cands)
            exclusions.extend(exc)
            paths.update(path)
            sport_status[sport] = "NO_ELIGIBLE_GAMES" if not kept else ("HAS_CANDIDATES" if cands else "NO_ELIGIBLE_SIGNALS")
            sport_status[sport + "_events_in_window"] = len(kept)
        coverage = "COMPLETE_FOR_NORMALIZED_WAREHOUSE"
    elif test_id == "APR_2025":
        markets = _april_nba_markets(test_id)
        candle_map = {m["ticker"]: m["ticker"] for rows in markets.values() for m in rows}
        cands, exclusions, paths = _from_markets(
            test_id,
            "NBA",
            markets,
            candle_map,
            lambda ticker: None if ticker is None else _read_raw_candle(ticker),
        )
        ncaab_markets = _count_ncaab_april_markets(test_id)
        exclusions.append(
            {
                "event_id": None,
                "contract_id": None,
                "sport": "NCAAB",
                "reason": "CANDLES_ABSENT",
                "markets_in_window": ncaab_markets,
            }
        )
        pieces = cands
        sport_status = {
            "NBA": "NO_ELIGIBLE_GAMES" if not cands else "HAS_CANDIDATES",
            "NBA_events_in_window": len(markets),
            "NCAAB": "COVERAGE_UNKNOWN",
            "NCAAB_markets_in_window": ncaab_markets,
        }
        coverage = "PARTIAL_RAW_TICKER_SUBSET"
    else:
        raise ValueError(test_id)
    return {
        "test_id": test_id,
        "candidates": pieces,
        "exclusions": exclusions,
        "paths": paths,
        "coverage_status": coverage,
        "sport_status": sport_status,
    }
