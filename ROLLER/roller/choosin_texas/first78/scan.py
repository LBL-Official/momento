"""Ex-ante FIRST78 scan. Membership does not require a later FIRST80 print."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from roller.choosin_texas.first78.artifact import load_strategy, repo_root, strategy_sha256
from roller.choosin_texas.first78.eligibility import find_entry, stop_after, window_bucket
from roller.choosin_texas.first78.summarize import assemble

STOPS = (67, 65, 60)


def _research():
    src = repo_root() / "research/first78_67_portfolio_v1/src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from first78.clocks import align
    from first78.extract import _index_candles, _markets_by_event, _read_bars
    from first78.timeutil import in_historical_entry_window

    return align, _index_candles, _markets_by_event, _read_bars, in_historical_entry_window


def _terminal(market: dict) -> str | None:
    result = str(market.get("result") or "").lower()
    if result in {"yes", "no"}:
        return result
    return None


def run_derived(progress=print) -> Path:
    from roller.choosin_texas.first78.derived_scan import run_derived as _run

    return _run(progress)


def run(progress=print) -> Path:
    align, index_candles, markets_by_event, read_bars, in_window = _research()
    root = repo_root()
    nba_root = root / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"
    ncaab_root = root / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"
    if not (nba_root / "markets/markets.parquet").is_file() or not (ncaab_root / "markets/markets.parquet").is_file():
        raise FileNotFoundError("normalized NBA or NCAAB markets parquet is missing")
    strategy = load_strategy()
    nba_markets = markets_by_event(nba_root / "markets/markets.parquet")
    ncaab_markets = markets_by_event(ncaab_root / "markets/markets.parquet")
    candles = {"NBA": index_candles(nba_root), "NCAAB": index_candles(ncaab_root)}
    exclusions: Counter[str] = Counter()
    coverage = {
        "nba_events": len(nba_markets),
        "ncaab_events": len(ncaab_markets),
        "nba_candle_files": len(candles["NBA"]),
        "ncaab_candle_files": len(candles["NCAAB"]),
        "p5_filter": False,
        "conditioned_on_first80": False,
        "window": strategy["development_window"]["label"],
    }
    chosen: list[dict] = []
    sports = (("NBA", nba_markets), ("NCAAB", ncaab_markets))
    seen_events = 0
    for sport, events in sports:
        for event_id, markets in events.items():
            seen_events += 1
            if seen_events % 400 == 0 and progress:
                progress(f"events {seen_events}")
            prepared = []
            for market in markets:
                ticker = market["ticker"]
                path = candles[sport].get(ticker)
                if path is None:
                    exclusions["NO_CANDLES"] += 1
                    continue
                entry = find_entry(read_bars(path))
                if not entry.get("cross_found"):
                    exclusions[str(entry.get("reason") or "NO_CROSS")] += 1
                    continue
                signal = int(entry["signal_ts"])
                if not in_window(signal):
                    exclusions["DATE_WINDOW"] += 1
                    continue
                try:
                    clock = align(sport, event_id, signal)
                except Exception as exc:  # noqa: BLE001 — alignment failure is coverage, not a crash
                    clock = {"bucket": "UNALIGNED", "reason": str(exc)}
                bucket = clock.get("bucket")
                if not bucket or bucket == "UNALIGNED":
                    exclusions["CLOCK_UNAVAILABLE"] += 1
                    continue
                if not window_bucket(sport, str(bucket)):
                    exclusions["OUTSIDE_SLICE"] += 1
                    continue
                stops = {}
                for stop in STOPS:
                    found = stop_after(entry, stop)
                    stops[str(stop)] = found
                if sport == "NBA" and stops["67"].get("stop_ts") is not None:
                    try:
                        stop_clock = align(sport, event_id, int(stops["67"]["stop_ts"]))
                    except Exception as exc:  # noqa: BLE001 — stop-clock failure stays missing
                        stop_clock = {"period": None, "period_remaining_s": None, "reason": str(exc)}
                    stops["67"]["period"] = stop_clock.get("period")
                    stops["67"]["period_remaining_s"] = stop_clock.get("period_remaining_s")
                prepared.append(
                    {
                        "game_id": event_id,
                        "contract_id": ticker,
                        "sport": sport,
                        "slice": str(bucket),
                        "signal_ts": signal,
                        "observed_entry_close_cents": entry.get("observed_close_cents"),
                        "terminal": _terminal(market),
                        "settlement_ts": market.get("settlement_time_ts"),
                        "clock_reason": clock.get("reason"),
                        "entry_period": clock.get("period"),
                        "entry_remaining_s": clock.get("period_remaining_s"),
                        "stops": stops,
                    }
                )
            if not prepared:
                continue
            prepared.sort(key=lambda row: (int(row["signal_ts"]), str(row["contract_id"])))
            chosen.append(prepared[0])
            exclusions["NOT_SELECTED_LATER_CONTRACT"] += len(prepared) - 1
    coverage["events_seen"] = seen_events
    coverage["entries"] = len(chosen)
    run_id = "first78_active_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    body = assemble(
        chosen,
        strategy=strategy,
        coverage=coverage,
        exclusions=dict(exclusions),
        run_id=run_id,
        strategy_sha256=strategy_sha256(),
    )
    out_dir = root / "research/first78_active_v1/runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.json"
    summary.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    latest = root / "research/first78_active_v1/LATEST.json"
    latest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "summary": f"research/first78_active_v1/runs/{run_id}/summary.json",
                "strategy_sha256": body["strategy_sha256"],
                "population_id": "PRIMARY_EX_ANTE_FIRST78",
            },
            indent=2,
        )
        + "\n"
    )
    if progress:
        progress(f"wrote {summary} entries={len(chosen)}")
    return summary


def main() -> None:
    run()


if __name__ == "__main__":
    main()
