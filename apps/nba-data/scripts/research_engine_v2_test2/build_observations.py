#!/usr/bin/env python3
"""Canonical first-80 observations for Test 2. Reuses audit labels; copies V1 IDs when present."""

from __future__ import annotations

import sys
from pathlib import Path

from common import (
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    HIT40,
    OUT,
    ROOT,
    audit,
    dataset_split,
    iso,
    team_code_from_ticker,
    utc_now,
    write_json,
    write_parquet,
)

V1_OBS = ROOT / "derived" / "nba" / "momento_path_engine_v1" / "first80_path_observations.parquet"


def main() -> int:
    from common import read_parquet_rows

    if V1_OBS.exists():
        rows = read_parquet_rows(V1_OBS)
        n40 = sum(int(r.get("target_close_40") or 0) for r in rows)
        n_surv = len(rows) - n40
        if len(rows) != EXPECTED_FIRST80 or n40 != EXPECTED_STOPS:
            print("V1 observations present but counts mismatch; rebuilding from audit.", file=sys.stderr)
        else:
            out = []
            for r in rows:
                out.append(
                    {
                        "observation_id": r["observation_id"],
                        "event_id": r["event_id"],
                        "ticker": r["ticker"],
                        "team": r.get("team"),
                        "team_code": team_code_from_ticker(r.get("ticker")),
                        "game_date": r.get("game_date"),
                        "dataset_split": r.get("dataset_split") or dataset_split(r.get("game_date")),
                        "entry_decision_time": r["entry_decision_time"],
                        "entry_decision_utc": r.get("entry_decision_utc") or iso(r["entry_decision_time"]),
                        "entry_time_precision": "1m_candle",
                        "Y_40_CLOSE": int(r["target_close_40"]),
                        "SURVIVE_40": 1 - int(r["target_close_40"]),
                        "Y_40_WICK": int(r.get("target_wick_40_post_entry_bar_only") or 0),
                        "expiration_result_yes": bool(r.get("expiration_result_yes")),
                        "maker_fill_confidence": r.get("maker_fill_confidence"),
                        "entry_bid_close_e4": r.get("entry_bid_close_e4"),
                        "entry_ask_close_e4": r.get("entry_ask_close_e4"),
                        "entry_spread_e4": r.get("entry_spread_e4"),
                        "close_ts": r.get("close_ts"),
                        "first_40_close_ts": r.get("first_40_close_ts"),
                        "home_team": r.get("home_team"),
                        "away_team": r.get("away_team"),
                        "source": "path_engine_v1_observations",
                    }
                )
            write_parquet(OUT / "observations.parquet", out)
            write_json(
                OUT / "observations_summary.json",
                {
                    "written_utc": utc_now(),
                    "games": EXPECTED_GAMES,
                    "first80": len(out),
                    "Y_40_CLOSE": n40,
                    "survivors": n_surv,
                    "baseline_ok": True,
                    "source": "path_engine_v1_observations",
                },
            )
            print(f"observations n={len(out)} Y40={n40} from Path Engine V1")
            return 0

    markets = audit.load_markets()
    games = audit.load_games()
    scanned = audit.scan(markets, games)
    cands = audit.build_candidates(markets, games, scanned)
    first = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None
    ]
    n40 = sum(1 for c in first if c["stop_close_triggered"])
    n_surv = sum(1 for c in first if not c["stop_close_triggered"] and c["expiration_result_yes"])
    ok = (
        len(cands) == EXPECTED_GAMES
        and len(first) == EXPECTED_FIRST80
        and n40 == EXPECTED_STOPS
        and n_surv == EXPECTED_SURVIVORS
    )
    if not ok:
        print("FROZEN LABEL MISMATCH", file=sys.stderr)
        return 1
    rows = []
    for c in first:
        rows.append(
            {
                "observation_id": f"{c['event_id']}|{c['ticker']}|first80",
                "event_id": c["event_id"],
                "ticker": c["ticker"],
                "team": c.get("team"),
                "team_code": team_code_from_ticker(c.get("ticker")),
                "game_date": c.get("game_date"),
                "dataset_split": dataset_split(c.get("game_date")),
                "entry_decision_time": c["first_80_timestamp"],
                "entry_decision_utc": iso(c["first_80_timestamp"]),
                "entry_time_precision": "1m_candle",
                "Y_40_CLOSE": 1 if c["stop_close_triggered"] else 0,
                "SURVIVE_40": 0 if c["stop_close_triggered"] else 1,
                "Y_40_WICK": 1 if c.get("stop_low_triggered") else 0,
                "expiration_result_yes": bool(c["expiration_result_yes"]),
                "maker_fill_confidence": c.get("maker_fill_confidence"),
                "entry_bid_close_e4": c.get("entry_bid_close_e4"),
                "entry_ask_close_e4": c.get("entry_ask_close_e4"),
                "entry_spread_e4": c.get("entry_spread_e4"),
                "close_ts": c.get("close_ts"),
                "first_40_close_ts": c.get("first_40_close_ts"),
                "home_team": c.get("home_team"),
                "away_team": c.get("away_team"),
                "source": "audit_rebuild",
            }
        )
    write_parquet(OUT / "observations.parquet", rows)
    write_json(
        OUT / "observations_summary.json",
        {
            "written_utc": utc_now(),
            "games": len(cands),
            "first80": len(rows),
            "Y_40_CLOSE": n40,
            "survivors": n_surv,
            "baseline_ok": True,
        },
    )
    print(f"observations n={len(rows)} Y40={n40}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
