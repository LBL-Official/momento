#!/usr/bin/env python3
"""Frozen FIRST-80 universe. Abort unless 1362 / 1230 / 320 / 910."""

from __future__ import annotations

import pickle
import sys

from common import (
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    HIT40,
    OBS,
    OUT,
    ROOT,
    audit,
    dataset_split,
    iso,
    load_quotes,
    team_code_from_ticker,
    utc_now,
    write_json,
    write_parquet,
)


def main() -> int:
    markets = audit.load_markets()
    games = audit.load_games()
    scanned = audit.scan(markets, games)
    cands = audit.build_candidates(markets, games, scanned)
    v3_cache = ROOT / "derived" / "nba" / "momento_dynamic_path_engine_v3" / "_quotes_cache.pkl"
    quotes_source = "load_quotes"
    if v3_cache.exists():
        quotes = pickle.loads(v3_cache.read_bytes())
        quotes_source = "V3_QUOTES_CACHE_READ_ONLY"
    else:
        quotes, _ = load_quotes(markets, games)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_quotes_cache.pkl").write_bytes(pickle.dumps(dict(quotes), protocol=4))
    games_by = {g["event_id"]: g for g in games}
    first = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None
    ]
    n_close40 = sum(1 for c in first if c["stop_close_triggered"])
    n_surv = sum(
        1 for c in first if not c["stop_close_triggered"] and c["expiration_result_yes"]
    )
    ok = (
        len(cands) == EXPECTED_GAMES
        and len(first) == EXPECTED_FIRST80
        and n_close40 == EXPECTED_STOPS
        and n_surv == EXPECTED_SURVIVORS
    )
    if not ok:
        print("FROZEN LABEL MISMATCH", file=sys.stderr)
        print({"games": len(cands), "first80": len(first), "close40": n_close40, "surv": n_surv}, file=sys.stderr)
        return 1
    rows = []
    for c in first:
        ticker = c["ticker"]
        series = quotes.get(ticker, [])
        entry = int(c["first_80_timestamp"])
        wick = False
        had_q = True
        for q in series:
            if q["ts"] <= entry:
                continue
            if not audit.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
                continue
            had_q = True
            if q["bid_l"] is not None and q["bid_l"] <= HIT40:
                wick = True
                break
        g = games_by.get(c["event_id"], {})
        rows.append(
            {
                "trade_id": f"{c['event_id']}|{ticker}|first80",
                "event_id": c["event_id"],
                "ticker": ticker,
                "team": c.get("team"),
                "team_code": team_code_from_ticker(ticker),
                "home_team_code": g.get("home_team_code"),
                "away_team_code": g.get("away_team_code"),
                "game_date": c.get("game_date"),
                "dataset_split": dataset_split(c.get("game_date")),
                "entry_decision_time": entry,
                "entry_decision_utc": iso(entry),
                "close_ts": c.get("close_ts"),
                "first_40_close_ts": c.get("first_40_close_ts"),
                "Y_40_CLOSE": 1 if c["stop_close_triggered"] else 0,
                "Y_40_WICK": 1 if wick else 0,
                "eventual_winner": bool(c["expiration_result_yes"]),
                "entry_bid_close_e4": c.get("entry_bid_close_e4"),
                "entry_ask_close_e4": c.get("entry_ask_close_e4"),
            }
        )
    write_parquet(OBS / "first80_trades.parquet", rows)
    write_json(
        OUT / "trade_universe_summary.json",
        {
            "written_utc": utc_now(),
            "games": len(cands),
            "first80": len(first),
            "Y_40_CLOSE": n_close40,
            "survivors": n_surv,
            "baseline_ok": True,
            "quotes_source": quotes_source,
        },
    )
    print(f"trades n={len(rows)} close40={n_close40}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
