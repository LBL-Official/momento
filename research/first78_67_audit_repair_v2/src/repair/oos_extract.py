"""Ex-ante windows. Imports OOS readers and applies the repaired close scan."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(ROOT / "research/first78_67_oos_adverse_v1/src"))

from first78.clocks import window_ok
from first78.extract import _index_candles, _read_bars
from first78.select import select_game
from oos_adverse.diagnostic_first80 import later_threshold_in_window
from oos_adverse.eligibility import in_window, local_day
from oos_adverse.population import (
    APR_NCAAB_MARKETS,
    NBA_2526,
    NCAAB_2526,
    PREFIX,
    _april_nba_markets,
    _clock,
    _count_ncaab_april_markets,
    _game_conditioned,
    _markets_by_event,
    _read_raw_candle,
    inventory_hit,
    legacy_event_ids,
)

from repair.chronology import scan_close_cross


def _candidate(sport, event_id, market, scanned, test_id, stage):
    result = str(market.get("result") or "").lower()
    settlement_ts = market.get("settlement_time_ts")
    signal = int(scanned["signal_ts"])
    bars = [
        {"ts": int(bar["ts"]), "bid": bar["bid"], "low": bar.get("low"), "ask": bar["ask"], "vol": bar.get("vol")}
        for bar in scanned.get("quality_bars") or []
    ]
    row = {
        "test_id": test_id,
        "sport": sport,
        "event_id": event_id,
        "game_id": event_id,
        "contract_id": market["ticker"],
        "signal_ts": signal,
        "action_ts": signal,
        "terminal_result": result if result in {"yes", "no"} else None,
        "settlement_ts": None if settlement_ts is None else int(settlement_ts),
        "local_day": local_day(signal),
        "observed_close_cents": scanned.get("observed_close_cents"),
        "intrabar_ambiguity": bool(scanned.get("intrabar_ambiguity")),
        "stage": stage,
        "bars": bars,
        "clock_availability": "MODELED_AVAILABILITY",
        "population_id": "PRIMARY_EX_ANTE_FIRST78",
    }
    if scanned.get("stop_ts") is not None and int(scanned["stop_ts"]) > signal:
        row.update(exit_reason="STOP", exit_ts=int(scanned["stop_ts"]), cash_ts=int(scanned["stop_ts"]))
    elif result in {"yes", "no"} and settlement_ts is not None and int(settlement_ts) >= signal:
        row.update(
            exit_reason="WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT",
            exit_ts=int(settlement_ts),
            cash_ts=int(settlement_ts),
        )
    else:
        row.update(exit_reason="UNRESOLVED", exit_ts=None, cash_ts=None)
    return row


def _choose(prepared: list[dict]) -> dict:
    result = select_game(prepared, "CONTRACT_WISE_FIRST")
    if result["chosen"] is not None:
        return result
    reasons = [row.get("reason") for row in prepared]
    if reasons and all(reason == "UNPROVEN_FIRST" for reason in reasons):
        result["rejection_reason"] = "UNPROVEN_FIRST"
    elif result["rejection_reason"] == "FIRST_OUTSIDE_WINDOW":
        buckets = [row.get("clock_bucket") for row in prepared if row.get("cross_found")]
        if buckets and all(bucket in (None, "", "UNALIGNED") for bucket in buckets):
            result["rejection_reason"] = "CLOCK_UNAVAILABLE"
    return result


def _from_markets(test_id, sport, markets, candles, reader):
    legacy = legacy_event_ids()
    candidates = []
    exclusions = []
    for event_id, mkts in markets.items():
        prepared = []
        bar_sets = []
        stage = "STAGE_UNLABELED"
        for market in mkts:
            bars = reader(candles.get(market["ticker"]))
            if bars is None:
                exclusions.append({"event_id": event_id, "contract_id": market["ticker"], "sport": sport, "reason": "MISSING_CANDLES"})
                continue
            scanned = scan_close_cross(bars)
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
                    "ticker": market["ticker"],
                    "cross_found": True,
                    "tradable": True,
                    "window_eligible": window_ok(sport, clock.get("bucket") or ""),
                    "date_eligible": in_window(int(scanned["signal_ts"]), test_id),
                    "clock_bucket": clock.get("bucket"),
                    "reason": None,
                    "signal_ts": int(scanned["signal_ts"]),
                    "_scanned": scanned,
                    "_bars": bars,
                }
            )
        choice = _choose(prepared)
        chosen = choice.get("chosen")
        if chosen is None:
            exclusions.append({"event_id": event_id, "contract_id": None, "sport": sport, "reason": choice.get("rejection_reason") or "NO_ELIGIBLE_CONTRACT"})
            continue
        cand = _candidate(sport, event_id, chosen, chosen["_scanned"], test_id, stage)
        cand["clock_bucket"] = chosen.get("clock_bucket")
        cand["legacy_lock_intersection"] = event_id in legacy
        cand["diagnostic_conditioned"] = _label_later_threshold(sport, event_id, bar_sets, test_id)
        candidates.append(cand)
    return candidates, exclusions


def _label_later_threshold(sport, event_id, bar_sets, test_id) -> bool:
    def clock_ok(ts: int) -> bool:
        clock = _clock(sport, event_id, ts, test_id)
        return window_ok(sport, clock.get("bucket") or "")

    return any(later_threshold_in_window(bars, clock_ok, lambda ts: in_window(ts, test_id)) for bars in bar_sets)


def extract_window(test_id: str) -> dict:
    if test_id == "OCT_2025":
        pieces, exclusions, status = [], [], {}
        for sport, root in (("NBA", NBA_2526), ("NCAAB", NCAAB_2526)):
            markets = _markets_by_event(root / "markets" / "markets.parquet")
            kept = {}
            for event, mkts in markets.items():
                mkts = [m for m in mkts if str(m["ticker"]).startswith(PREFIX[sport])]
                occs = [m["occurrence_ts"] for m in mkts if m.get("occurrence_ts")]
                source = inventory_hit(str(event), min(occs) if occs else None, test_id)
                if source is None:
                    continue
                for market in mkts:
                    market["inventory_date_source"] = source
                kept[event] = mkts
            cands, exc = _from_markets(test_id, sport, kept, _index_candles(root), lambda path: None if path is None else _read_bars(path))
            pieces.extend(cands)
            exclusions.extend(exc)
            status[sport] = "NO_ELIGIBLE_GAMES" if not kept else ("HAS_CANDIDATES" if cands else "NO_ELIGIBLE_SIGNALS")
            status[sport + "_events_in_window"] = len(kept)
        coverage = "COMPLETE_FOR_NORMALIZED_WAREHOUSE"
    elif test_id == "APR_2025":
        markets = _april_nba_markets(test_id)
        candle_map = {m["ticker"]: m["ticker"] for rows in markets.values() for m in rows}
        pieces, exclusions = _from_markets(test_id, "NBA", markets, candle_map, lambda ticker: None if ticker is None else _read_raw_candle(ticker))
        ncaab_markets = _count_ncaab_april_markets(test_id)
        exclusions.append({"event_id": None, "contract_id": None, "sport": "NCAAB", "reason": "CANDLES_ABSENT", "markets_in_window": ncaab_markets, "market_file_exists": APR_NCAAB_MARKETS.exists()})
        status = {
            "NBA": "HAS_CANDIDATES" if pieces else "NO_ELIGIBLE_GAMES",
            "NBA_events_in_window": len(markets),
            "NCAAB": "COVERAGE_UNKNOWN",
            "NCAAB_markets_in_window": ncaab_markets,
            "NCAAB_note": "no 25APR event dates; candlesticks absent",
        }
        coverage = "PARTIAL_RAW_TICKER_SUBSET"
    else:
        raise ValueError(test_id)
    return {"test_id": test_id, "candidates": pieces, "exclusions": exclusions, "coverage_status": coverage, "sport_status": status}
