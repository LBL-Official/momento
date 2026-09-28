#!/usr/bin/env python3
"""Post-entry market states. Candles with end_period_ts ≤ state_timestamp only."""

from __future__ import annotations

import pickle
import sys
from collections import defaultdict

from common import OUT, read_parquet_rows, write_parquet
from market_feat import market_at


def main() -> int:
    trades = {t["trade_id"]: t for t in read_parquet_rows(OUT / "first80_trades.parquet")}
    panel = read_parquet_rows(OUT / "post_entry_state_panel.parquet")
    cache = OUT / "_quotes_cache.pkl"
    if not cache.exists():
        print("missing quotes cache", file=sys.stderr)
        return 1
    quotes = pickle.loads(cache.read_bytes())
    by_trade = defaultdict(list)
    for p in panel:
        by_trade[p["trade_id"]].append(p)
    rows = []
    for tid, plist in by_trade.items():
        tr = trades[tid]
        series = quotes.get(tr["ticker"], [])
        et = int(tr["entry_decision_time"])
        eidx = next((i for i, q in enumerate(series) if q["ts"] == et), None)
        ts_to_i = {q["ts"]: i for i, q in enumerate(series)}
        for p in plist:
            ts = int(p["state_timestamp"])
            idx = ts_to_i.get(ts)
            if idx is None:
                rows.append(
                    {
                        "trade_id": tid,
                        "state_timestamp": ts,
                        "feature_status": "MISSING_CANDLE",
                    }
                )
                continue
            feat = market_at(series, idx, eidx, tr.get("entry_bid_close_e4"))
            feat["trade_id"] = tid
            feat["state_timestamp"] = ts
            feat["entry_decision_time"] = et
            feat["feature_maximum_source_timestamp"] = ts
            feat["feature_status"] = "CAUSAL_AT_STATE"
            feat["same_bar_limitation"] = "SAME_BAR_1M_LIMITATION"
            rows.append(feat)
    write_parquet(OUT / "post_entry_market_states.parquet", rows)
    print(f"market_states n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
