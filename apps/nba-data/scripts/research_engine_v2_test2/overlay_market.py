#!/usr/bin/env python3
"""Overlay Kalshi 1m candles onto possessions. Label alignment quality."""

from __future__ import annotations

import sys
from collections import defaultdict

from common import (
    OUT,
    audit,
    e4_to_cents,
    load_quotes,
    read_parquet_rows,
    utc_now,
    write_json,
    write_parquet,
)


def overlapping_candles(series, t0, t1):
    if t0 is None or t1 is None:
        return []
    lo, hi = min(t0, t1), max(t0, t1)
    out = []
    for c in series:
        c0, c1 = c["ts"] - 60, c["ts"]
        if c1 > lo and c0 < hi:
            out.append(c)
    return out


def last_close_at_or_before(series, t):
    last = None
    for c in series:
        if t is None:
            break
        if c["ts"] <= t:
            last = c
        else:
            break
    return last


def first_close_at_or_after(series, t):
    if t is None:
        return None
    for c in series:
        if c["ts"] >= t:
            return c
    return None


def classify(n_candles, n_poss_sharing, t0, t1) -> str:
    if t0 is None or t1 is None:
        return "PARTIAL_ALIGNMENT"
    if n_candles == 0:
        return "PARTIAL_ALIGNMENT"
    if n_candles >= 2:
        return "MULTI_CANDLE_POSSESSION"
    if n_poss_sharing > 1:
        return "MULTI_POSSESSION_CANDLE"
    return "EXACT_ALIGNMENT"


def main() -> int:
    obs = {r["observation_id"]: r for r in read_parquet_rows(OUT / "observations.parquet")}
    snaps = read_parquet_rows(OUT / "entry_snaps.parquet")
    poss = read_parquet_rows(OUT / "possessions.parquet")
    by_nba = defaultdict(list)
    for p in poss:
        by_nba[p["nba_game_id"]].append(p)

    markets = audit.load_markets()
    games = audit.load_games()
    quotes, _ = load_quotes(markets, games)

    # Pre-count possessions per candle for MULTI_POSSESSION_CANDLE.
    # Approximate: for each game ticker we need a mapping. Use first observation ticker per nba game.
    ticker_by_nba = {}
    for s in snaps:
        o = obs.get(s["observation_id"])
        if o and s.get("nba_game_id") and s["nba_game_id"] not in ticker_by_nba:
            ticker_by_nba[s["nba_game_id"]] = o["ticker"]

    # Per-possession overlay (game ticker from first snap).
    poss_overlay = []
    quality_counts = defaultdict(int)
    for nba_id, plist in by_nba.items():
        ticker = ticker_by_nba.get(nba_id)
        series = quotes.get(ticker, []) if ticker else []
        # candle ts -> possession ids overlapping
        candle_share = defaultdict(set)
        ov_map = {}
        for p in plist:
            t0, t1 = p.get("wall_start_ts"), p.get("wall_end_ts")
            ov = overlapping_candles(series, t0, t1)
            ov_map[p["possession_id"]] = (p, ov, t0, t1)
            for c in ov:
                candle_share[c["ts"]].add(p["possession_id"])
        for pid, (p, ov, t0, t1) in ov_map.items():
            share = set()
            for c in ov:
                share |= candle_share[c["ts"]]
            code = classify(len(ov), len(share), t0, t1)
            quality_counts[code] += 1
            before = last_close_at_or_before(series, t0)
            after = first_close_at_or_after(series, t1)
            bids = [c["bid_c"] for c in ov if c.get("bid_c") is not None]
            vols = [c["vol"] or 0 for c in ov]
            poss_overlay.append(
                {
                    "nba_game_id": nba_id,
                    "possession_id": pid,
                    "alignment_quality": code,
                    "n_overlapping_candles": len(ov),
                    "n_possessions_sharing_candles": len(share),
                    "market_bid_before_e4": None if before is None else before.get("bid_c"),
                    "market_ask_before_e4": None if before is None else before.get("ask_c"),
                    "market_bid_after_e4": None if after is None else after.get("bid_c"),
                    "market_ask_after_e4": None if after is None else after.get("ask_c"),
                    "market_change_during_cents": None
                    if before is None
                    or after is None
                    or before.get("bid_c") is None
                    or after.get("bid_c") is None
                    else e4_to_cents(after["bid_c"] - before["bid_c"]),
                    "market_range_during_cents": None
                    if len(bids) < 1
                    else e4_to_cents(max(bids) - min(bids)),
                    "market_volume_during": int(sum(vols)),
                    "spread_before_cents": None
                    if before is None or before.get("bid_c") is None or before.get("ask_c") is None
                    else e4_to_cents(before["ask_c"] - before["bid_c"]),
                    "spread_after_cents": None
                    if after is None or after.get("bid_c") is None or after.get("ask_c") is None
                    else e4_to_cents(after["ask_c"] - after["bid_c"]),
                }
            )

    # Observation-level join to snapped possession.
    overlay = []
    by_pid = {r["possession_id"]: r for r in poss_overlay}
    for s in snaps:
        o = obs.get(s["observation_id"])
        row = dict(by_pid.get(s.get("possession_id")) or {})
        row["observation_id"] = s["observation_id"]
        if o:
            row["entry_bid_close_e4"] = o.get("entry_bid_close_e4")
            row["entry_ask_close_e4"] = o.get("entry_ask_close_e4")
        overlay.append(row)

    write_parquet(OUT / "possession_market.parquet", poss_overlay)
    write_parquet(OUT / "possession_market_overlay.parquet", overlay)
    write_json(
        OUT / "overlay_summary.json",
        {"written_utc": utc_now(), "n": len(overlay), "quality_counts": dict(quality_counts)},
    )
    print("overlay", dict(quality_counts), "n", len(overlay))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
