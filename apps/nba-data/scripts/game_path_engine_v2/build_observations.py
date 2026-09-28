#!/usr/bin/env python3
"""Canonical first-80 observations. Frozen audit labels. Does not modify V1."""

from __future__ import annotations

import sys

from common import (
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    HIT40,
    OUT,
    audit,
    dataset_split,
    e4_to_cents,
    iso,
    load_quotes,
    team_code_from_ticker,
    utc_now,
    write_json,
    write_parquet,
)


def post_entry_wick(series, entry_ts: int) -> tuple[bool, int | None]:
    had_q = True
    for q in series:
        if q["ts"] <= entry_ts:
            continue
        if not audit.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        if q["bid_l"] is not None and q["bid_l"] <= HIT40:
            return True, q["ts"]
    return False, None


def main() -> int:
    markets = audit.load_markets()
    games = audit.load_games()
    scanned = audit.scan(markets, games)
    cands = audit.build_candidates(markets, games, scanned)
    quotes, _meta = load_quotes(markets, games)
    games_by_event = {g["event_id"]: g for g in games}

    first = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None
    ]
    n_close40 = sum(1 for c in first if c["stop_close_triggered"])
    n_surv = sum(
        1
        for c in first
        if not c["stop_close_triggered"] and c["expiration_result_yes"]
    )
    baseline_ok = (
        len(cands) == EXPECTED_GAMES
        and len(first) == EXPECTED_FIRST80
        and n_close40 == EXPECTED_STOPS
        and n_surv == EXPECTED_SURVIVORS
    )
    if not baseline_ok:
        print("FROZEN LABEL MISMATCH — refusing to write observations.", file=sys.stderr)
        print(
            {
                "games": len(cands),
                "first80": len(first),
                "Y_40_CLOSE": n_close40,
                "survivors": n_surv,
            },
            file=sys.stderr,
        )
        return 1

    rows = []
    for c in first:
        ticker = c["ticker"]
        series = quotes.get(ticker, [])
        entry_ts = c["first_80_timestamp"]
        wick_post, wick_post_ts = post_entry_wick(series, entry_ts)
        g = games_by_event.get(c["event_id"], {})
        home = c.get("home_team") or g.get("home_team")
        away = c.get("away_team") or g.get("away_team")
        team = c.get("team")
        home_code = g.get("home_team_code")
        away_code = g.get("away_team_code")
        code = team_code_from_ticker(ticker)
        opponent = None
        if code and home_code and away_code:
            if code == str(home_code).upper():
                opponent = away
            elif code == str(away_code).upper():
                opponent = home
        if opponent is None:
            opponent = away if team == home else home
        bid_c = c.get("entry_bid_close_e4")
        ask_c = c.get("entry_ask_close_e4")
        y40 = 1 if c["stop_close_triggered"] else 0
        split = dataset_split(c.get("game_date"))
        rows.append(
            {
                "observation_id": f"{c['event_id']}|{ticker}|first80",
                "event_id": c["event_id"],
                "game_id": c.get("game_id"),
                "event_ticker": c.get("event_ticker"),
                "market_id": c.get("market_id"),
                "ticker": ticker,
                "team": team,
                "team_code": code,
                "opponent": opponent,
                "home_team": home,
                "away_team": away,
                "home_team_code": home_code,
                "away_team_code": away_code,
                "game_date": c.get("game_date"),
                "dataset_split": split,
                "season_phase": c.get("season_phase"),
                "first_80_timestamp": entry_ts,
                "entry_decision_time": entry_ts,
                "entry_decision_utc": iso(entry_ts),
                "entry_time_precision": "1m_candle",
                "entry_decision_convention": "END_OF_FIRST_80_CANDLE",
                "entry_bid_close_e4": bid_c,
                "entry_ask_close_e4": ask_c,
                "entry_spread_e4": c.get("entry_spread_e4"),
                "maker_fill_confidence": c.get("maker_fill_confidence"),
                "close_ts": c.get("close_ts"),
                "first_40_close_ts": c.get("first_40_close_ts"),
                "Y_40_CLOSE": y40,
                "Y_40_WICK": 1 if wick_post else 0,
                "target_close_40": y40,
                "target_wick_40_post_entry_bar_only": 1 if wick_post else 0,
                "target_wick_40_post_entry_ts": wick_post_ts,
                "eventual_winner": bool(c["expiration_result_yes"]),
                "expiration_result_yes": bool(c["expiration_result_yes"]),
                "alignment_confidence": None,
                "scope": "GAME_PATH_ENGINE_V2",
            }
        )

    write_parquet(OUT / "observations.parquet", rows)
    splits = {}
    for r in rows:
        splits.setdefault(r["dataset_split"], {"n": 0, "y40": 0})
        splits[r["dataset_split"]]["n"] += 1
        splits[r["dataset_split"]]["y40"] += r["Y_40_CLOSE"]
    n_wick = sum(r["Y_40_WICK"] for r in rows)
    summary = {
        "written_utc": utc_now(),
        "games": len(cands),
        "first80": len(first),
        "Y_40_CLOSE": n_close40,
        "survivors": n_surv,
        "Y_40_WICK": n_wick,
        "q_unconditional": n_close40 / len(first),
        "ev_unconditional": 1.0 - 3.0 * (n_close40 / len(first)),
        "splits": splits,
        "baseline_ok": True,
        "primary_target": "Y_40_CLOSE",
        "secondary_target": "Y_40_WICK",
    }
    write_json(OUT / "observations_summary.json", summary)
    print(
        f"observations n={len(rows)} close40={n_close40} wick={n_wick} "
        f"q={n_close40/len(first):.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
