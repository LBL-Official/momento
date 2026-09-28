#!/usr/bin/env python3
"""Build Path Engine V1 canonical first-80 observations.

Reuses the frozen audit first-80 definition. Aborts unless
games=1362, first80=1230, close-path-40=320, survivors=910.

ENTRY_DECISION_TIME = end of first-80 candle.
Primary Y_40 = first subsequent completed candle with yes_bid_close <= 40.
"""

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
    utc_now,
    write_json,
    write_parquet,
)


def post_entry_wick(series, entry_ts: int) -> tuple[bool, int | None]:
    """Tradable bid_low <= 40 on a candle strictly after ENTRY_DECISION_TIME.

    Uses the same two-sided uncrossed spread ≤ 10¢ quality filter as the
    frozen audit wick path. An unfiltered wick is not a 40-barrier event.
    """
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


def entry_wick(q) -> bool:
    return q["bid_l"] is not None and q["bid_l"] <= HIT40


def main() -> int:
    markets = audit.load_markets()
    games = audit.load_games()
    scanned = audit.scan(markets, games)
    cands = audit.build_candidates(markets, games, scanned)
    quotes, _meta = load_quotes(markets, games)

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
                "target_close_40": n_close40,
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
        entry_q = next((q for q in series if q["ts"] == entry_ts), None)
        wick_incl = wick_post or (entry_q is not None and entry_wick(entry_q))
        wick_incl_ts = None
        if entry_q is not None and entry_wick(entry_q):
            wick_incl_ts = entry_ts
        elif wick_post:
            wick_incl_ts = wick_post_ts

        bid_c = c.get("entry_bid_close_e4")
        ask_c = c.get("entry_ask_close_e4")
        mid = None
        if bid_c is not None and ask_c is not None:
            mid = (bid_c + ask_c) / 2.0

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
                "team": c.get("team"),
                "game_date": c.get("game_date"),
                "dataset_split": split,
                "season_phase": c.get("season_phase"),
                "home_team": c.get("home_team"),
                "away_team": c.get("away_team"),
                "entry_decision_time": entry_ts,
                "entry_decision_utc": iso(entry_ts),
                "entry_time_precision": "1m_candle",
                "entry_decision_convention": "END_OF_FIRST_80_CANDLE",
                "entry_price_e4": c.get("entry_price_e4"),
                "entry_bid_open_e4": c.get("entry_bid_open_e4"),
                "entry_bid_high_e4": c.get("entry_bid_high_e4"),
                "entry_bid_low_e4": c.get("entry_bid_low_e4"),
                "entry_bid_close_e4": bid_c,
                "entry_ask_open_e4": c.get("entry_ask_open_e4"),
                "entry_ask_high_e4": c.get("entry_ask_high_e4"),
                "entry_ask_low_e4": c.get("entry_ask_low_e4"),
                "entry_ask_close_e4": ask_c,
                "entry_last_open_e4": c.get("entry_last_open_e4"),
                "entry_last_high_e4": c.get("entry_last_high_e4"),
                "entry_last_low_e4": c.get("entry_last_low_e4"),
                "entry_last_close_e4": c.get("entry_last_close_e4"),
                "entry_volume_hundredths": c.get("entry_volume_hundredths"),
                "entry_spread_e4": c.get("entry_spread_e4"),
                "entry_mid_e4_estimated": mid,
                "entry_mid_label": "ESTIMATED",
                "maker_fill_confidence": c.get("maker_fill_confidence"),
                "estimated_maker_fill": True,
                "historical_fill_unknown": True,
                "market_data_type": "CANDLESTICK_TOP_OF_BOOK",
                "orderbook_depth_available": False,
                "l2_invented": False,
                "close_ts": c.get("close_ts"),
                "first_40_close_ts": c.get("first_40_close_ts"),
                "target_close_40": y40,
                "target_wick_40_post_entry_bar_only": 1 if wick_post else 0,
                "target_wick_40_including_entry_bar": 1 if wick_incl else 0,
                "target_wick_40_post_entry_ts": wick_post_ts,
                "target_wick_40_including_entry_ts": wick_incl_ts,
                "same_bar_wick_40": bool(c.get("same_bar_80_and_40_low")),
                "expiration_result_yes": bool(c["expiration_result_yes"]),
                "official_nba_quarter": None,
                "official_game_clock": None,
                "score_home": None,
                "score_away": None,
                "quarter_source": "UNAVAILABLE_NO_WALL_CLOCK_JOIN",
                "game_state_status": "UNAVAILABLE",
                "scope": "PATH_ENGINE_V1_MARKET_ONLY",
            }
        )

    n_wick_post = sum(r["target_wick_40_post_entry_bar_only"] for r in rows)
    n_wick_incl = sum(r["target_wick_40_including_entry_bar"] for r in rows)
    splits = {}
    for r in rows:
        splits.setdefault(r["dataset_split"], {"n": 0, "y40": 0})
        splits[r["dataset_split"]]["n"] += 1
        splits[r["dataset_split"]]["y40"] += r["target_close_40"]

    write_parquet(OUT / "first80_path_observations.parquet", rows)
    summary = {
        "written_utc": utc_now(),
        "games": len(cands),
        "first80": len(first),
        "target_close_40": n_close40,
        "survivors": n_surv,
        "target_wick_40_post_entry_bar_only": n_wick_post,
        "target_wick_40_including_entry_bar": n_wick_incl,
        "q_unconditional": n_close40 / len(first),
        "ev_unconditional": 1.0 - 3.0 * (n_close40 / len(first)),
        "splits": splits,
        "baseline_ok": True,
        "entry_decision_convention": "END_OF_FIRST_80_CANDLE",
        "primary_target": "target_close_40",
        "formal_secondary_target": "target_wick_40_post_entry_bar_only",
    }
    write_json(OUT / "observations_summary.json", summary)
    print(
        f"observations n={len(rows)} close40={n_close40} "
        f"wick_post={n_wick_post} wick_incl={n_wick_incl}"
    )
    for k, v in splits.items():
        q = v["y40"] / v["n"] if v["n"] else None
        print(f"  {k}: n={v['n']} y40={v['y40']} q={q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
