#!/usr/bin/env python3
"""Post-entry alive panel. Risk set exits at the close-path 40 candle."""

from __future__ import annotations

import sys

from common import (
    MAX_ALIVE_MINUTES,
    OUT,
    load_quotes,
    read_parquet_rows,
    utc_now,
    write_json,
    write_parquet,
)
import pickle


def main() -> int:
    trades = read_parquet_rows(OUT / "first80_trades.parquet")
    if len(trades) != 1230:
        print("need 1230 trades", file=sys.stderr)
        return 1
    cache = OUT / "_quotes_cache.pkl"
    if cache.exists():
        quotes = pickle.loads(cache.read_bytes())
    else:
        from common import audit

        quotes, _ = load_quotes(audit.load_markets(), audit.load_games())
    rows = []
    n_traj = 0
    lengths = []
    for tr in trades:
        series = quotes.get(tr["ticker"], [])
        entry = int(tr["entry_decision_time"])
        barrier = tr.get("first_40_close_ts")
        close_ts = tr.get("close_ts")
        alive = [q for q in series if q["ts"] > entry]
        if barrier is not None:
            alive = [q for q in alive if q["ts"] < int(barrier)]
        if close_ts is not None:
            alive = [q for q in alive if q["ts"] <= int(close_ts)]
        alive = alive[:MAX_ALIVE_MINUTES]
        if not alive:
            continue
        n_traj += 1
        lengths.append(len(alive))
        last_ts = alive[-1]["ts"]
        for i, q in enumerate(alive):
            nxt = alive[i + 1]["ts"] if i + 1 < len(alive) else None
            event_1m = 0
            if barrier is not None:
                # next interval hits barrier
                lo = q["ts"]
                hi = lo + 60 if nxt is None else nxt
                if lo < int(barrier) <= hi or (nxt is None and int(barrier) > lo and int(barrier) - lo <= 90):
                    # If we stopped before barrier candle, the event is after last row:
                    # mark last row if barrier is the next candle in the raw series.
                    pass
            # Prefer: barrier is the first candle after this state in the *full* series.
            event_1m = int(
                barrier is not None
                and int(barrier) > q["ts"]
                and int(barrier) <= q["ts"] + 60
            )
            mtc = None if close_ts is None else (int(close_ts) - q["ts"]) / 60.0
            rows.append(
                {
                    "trade_id": tr["trade_id"],
                    "event_id": tr["event_id"],
                    "ticker": tr["ticker"],
                    "team": tr["team"],
                    "game_date": tr["game_date"],
                    "dataset_split": tr["dataset_split"],
                    "entry_decision_time": entry,
                    "state_timestamp": q["ts"],
                    "minutes_since_entry": (q["ts"] - entry) / 60.0,
                    "minutes_to_contract_close": mtc,
                    "alive_above_40": 1,
                    "barrier_event_this_interval": event_1m,
                    "eventual_barrier": tr["Y_40_CLOSE"],
                    "censored": tr["censored"],
                    "yes_bid_close_e4": q["bid_c"],
                    "yes_ask_close_e4": q["ask_c"],
                    "yes_bid_high_e4": q["bid_h"],
                    "yes_bid_low_e4": q["bid_l"],
                    "volume_hundredths": q["vol"],
                    "panel_index": i,
                    "n_alive_minutes": len(alive),
                    "is_last_alive": int(i == len(alive) - 1),
                }
            )
        # If the barrier is the next candle after last alive row (ts < barrier),
        # set last row event if barrier within 1-2 minutes of last state.
        if barrier is not None and rows and rows[-1]["trade_id"] == tr["trade_id"]:
            last = rows[-1]
            b = int(barrier)
            if last["state_timestamp"] < b <= last["state_timestamp"] + 120:
                last["barrier_event_this_interval"] = 1
    write_parquet(OUT / "post_entry_state_panel.parquet", rows)
    write_json(
        OUT / "panel_summary.json",
        {
            "written_utc": utc_now(),
            "n_trades": len(trades),
            "n_trajectories_with_panel": n_traj,
            "n_panel_rows": len(rows),
            "median_alive_minutes": sorted(lengths)[len(lengths) // 2] if lengths else None,
            "max_alive_minutes_cap": MAX_ALIVE_MINUTES,
            "risk_set_rule": "candles with entry < ts < first_40_close_ts (or until close if no barrier)",
        },
    )
    print(f"panel rows={len(rows)} traj={n_traj}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
