#!/usr/bin/env python3
"""Market-path features at first-80. Pre-entry candles only."""

from __future__ import annotations

import sys

from common import OUT, audit, load_quotes, read_parquet_rows, write_parquet
from market import market_features


def main() -> int:
    obs = read_parquet_rows(OUT / "observations.parquet")
    if not obs:
        print("missing observations", file=sys.stderr)
        return 1
    markets = audit.load_markets()
    games = audit.load_games()
    quotes, _meta = load_quotes(markets, games)
    games_by = {g["event_id"]: g for g in games}
    rows = []
    for o in obs:
        ticker = o["ticker"]
        series = quotes.get(ticker, [])
        entry_ts = int(o["entry_decision_time"])
        feat = market_features(series, entry_ts)
        close_ts = o.get("close_ts")
        mtc = None
        if close_ts is not None:
            mtc = (int(close_ts) - entry_ts) / 60.0
        feat["minutes_to_close"] = mtc
        feat["feat_minutes_to_close"] = mtc
        rec = {
            "observation_id": o["observation_id"],
            "entry_decision_time": entry_ts,
            "alignment_confidence": o.get("alignment_confidence"),
            **feat,
        }
        rows.append(rec)
    write_parquet(OUT / "market_path_features.parquet", rows)
    # also write market_entry_state subset
    entry_cols = [
        "observation_id",
        "entry_decision_time",
        "distance_above_80_cents",
        "spread_cents",
        "volume_hundredths",
        "range_1m_cents",
        "minutes_to_close",
    ]
    write_parquet(
        OUT / "market_entry_state.parquet",
        [{k: r.get(k) for k in entry_cols} for r in rows],
    )
    print(f"market_paths n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
