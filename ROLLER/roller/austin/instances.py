"""Load the locked 604 Choosin Texas NBA 2Q/3Q trades."""

from __future__ import annotations

from typing import Any

from roller.austin.clock import clock_to_seconds, period_to_quarter
from roller.austin.errors import AustinError
from roller.austin.locks import (
    BOOK_CENTS,
    L_T40,
    N_Q2,
    N_Q3,
    N_TRADES,
    S_N,
    W_T40,
)
from roller.nba_8040_reverse_features.instances import load_instances


def load_trades() -> list[dict[str, Any]]:
    rows = load_instances()
    if len(rows) != N_TRADES:
        raise AustinError("LOCK_MISMATCH", f"N_trades {len(rows)} != {N_TRADES}")
    q2 = sum(1 for row in rows if row["slice"] == "Q2")
    q3 = sum(1 for row in rows if row["slice"] == "Q3")
    if q2 != N_Q2 or q3 != N_Q3:
        raise AustinError("LOCK_MISMATCH", f"Q2/Q3 {q2}/{q3} != {N_Q2}/{N_Q3}")
    s_n = sum(1 for row in rows if not row["t40"])
    w_t40 = sum(1 for row in rows if row["t40"] and row["w"])
    l_t40 = sum(1 for row in rows if row["t40"] and not row["w"])
    if (s_n, w_t40, l_t40) != (S_N, W_T40, L_T40):
        raise AustinError("LOCK_MISMATCH", f"cells {(s_n, w_t40, l_t40)} != {(S_N, W_T40, L_T40)}")
    out: list[dict[str, Any]] = []
    for row in rows:
        quarter = period_to_quarter(row.get("period") or row.get("slice"))
        out.append(
            {
                "trade_id": row["instance_id"],
                "event_id": row["event_id"],
                "game_id": row["game_id"],
                "ticker": row["ticker"],
                "sport": "NBA",
                "season": "2025_2026",
                "game_date": row["game_date"],
                "calendar_month": row["calendar_month"],
                "dataset_split": row.get("dataset_split"),
                "quarter": quarter,
                "slice": row["slice"],
                "entry_timestamp": row["timestamp_utc"],
                "entry_game_clock": row.get("game_clock"),
                "entry_seconds_remaining": clock_to_seconds(row.get("game_clock"))
                if clock_to_seconds(row.get("game_clock")) is not None
                else row.get("period_remaining_s"),
                "entry_price_cents": int(row["entry_bid_cents"]),
                "entry_side": row["side"],
                "team": row["bought_team"],
                "opponent": row["opponent_team"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score_entry": row["score_home"],
                "away_score_entry": row["score_away"],
                "score_differential_at_entry": row["bought_margin"],
                "t40": bool(row["t40"]),
                "w": bool(row["w"]),
                "terminal_yes": bool(row["terminal_yes"]),
                "post_entry_min": int(row["post_entry_min"]),
                "exit_timestamp_utc": row.get("exit_timestamp_utc"),
                "exit_period": row.get("exit_period"),
                "exit_game_clock": row.get("exit_game_clock"),
                "exit_score_home": row.get("exit_score_home"),
                "exit_score_away": row.get("exit_score_away"),
                "final_score_home": row.get("final_score_home"),
                "final_score_away": row.get("final_score_away"),
                "period_remaining_s": row.get("period_remaining_s"),
                "game_seconds_remaining": row.get("game_seconds_remaining"),
            }
        )
    book = 20 * s_n - 40 * (len(out) - s_n)
    if book != BOOK_CENTS:
        raise AustinError("LOCK_MISMATCH", f"book {book} != {BOOK_CENTS}")
    return out
