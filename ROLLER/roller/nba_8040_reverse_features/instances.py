"""Load locked NBA asked-six FIRST80 instances. Population authority is the CSV."""

from __future__ import annotations

import csv
import hashlib
from typing import Any

from roller.choosin_texas.dallas import PREGAME_SOURCE, _pregame_cents
from roller.choosin_texas.ev import book_cents
from roller.choosin_texas.nba_path import _int_value
from roller.choosin_texas.sources import _as_bool, _cents_field, default_asked_six_csv
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.locks import (
    GAIN_CENTS,
    LOSS_CENTS,
    NBA_Q2_N,
    NBA_Q2_RS_BOOK,
    NBA_Q2_RS_L_T40,
    NBA_Q2_RS_N,
    NBA_Q2_RS_S,
    NBA_Q2_RS_W_T40,
    NBA_Q2Q3_BOOK,
    NBA_Q2Q3_L_T40,
    NBA_Q2Q3_N,
    NBA_Q2Q3_S,
    NBA_Q2Q3_W_T40,
    NBA_Q3_N,
    RULE,
    SLICES,
    SPORT,
    STOP_CENTS,
)


def instance_id(event_id: str, ticker: str, timestamp_utc: str) -> str:
    raw = f"{event_id}|{ticker}|{timestamp_utc}|{RULE}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _optional_cents(value: Any, *, field: str, ticker: str) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _cents_field(value, field=field, ticker=ticker)


def load_instances() -> list[dict[str, Any]]:
    wanted = set(SLICES)
    rows: list[dict[str, Any]] = []
    with default_asked_six_csv().open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            if str(rec.get("sport") or "").strip() != SPORT:
                continue
            slice_id = str(rec.get("slice") or "").strip()
            if slice_id not in wanted:
                continue
            ticker = str(rec.get("ticker") or "").strip()
            event_id = str(rec.get("event_id") or rec.get("game_id") or ticker)
            side = str(rec.get("side") or "").strip()
            if side not in {"home", "away"}:
                raise ReverseFeaturesError("LOCK_MISMATCH", f"bad side {side!r} for {ticker}")
            source = str(rec.get("pregame_source") or "").strip()
            if source != PREGAME_SOURCE:
                raise ReverseFeaturesError(
                    "LOCK_MISMATCH", f"{ticker}: pregame_source {source!r}"
                )
            stamp = str(rec.get("timestamp_utc") or "").strip()
            if not stamp:
                raise ReverseFeaturesError("DATA_REQUIRED", f"missing timestamp_utc for {ticker}")
            t40 = _as_bool(rec.get("T40"), field="T40", ticker=ticker)
            win = _as_bool(rec.get("W"), field="W", ticker=ticker)
            post = _cents_field(
                rec.get("post_entry_min_yes_bid_cents"),
                field="post_entry_min_yes_bid_cents",
                ticker=ticker,
            )
            if t40 != (post <= STOP_CENTS):
                raise ReverseFeaturesError(
                    "LOCK_MISMATCH", f"{ticker}: T40 {t40} != post_min {post} ≤ {STOP_CENTS}"
                )
            entry = _cents_field(rec.get("market_yes_bid"), field="market_yes_bid", ticker=ticker)
            if entry < 80:
                raise ReverseFeaturesError("LOCK_MISMATCH", f"{ticker}: entry {entry} < 80")
            rows.append(
                {
                    "instance_id": instance_id(event_id, ticker, stamp),
                    "event_id": event_id,
                    "game_id": str(rec.get("game_id") or ""),
                    "ticker": ticker,
                    "sport": SPORT,
                    "league": "NBA",
                    "slice": slice_id,
                    "period": slice_id,
                    "game_date": str(rec.get("game_date") or ""),
                    "calendar_month": str(rec.get("calendar_month") or ""),
                    "dataset_split": str(rec.get("dataset_split") or ""),
                    "season_phase": str(rec.get("season_phase") or ""),
                    "regular_season": str(rec.get("season_phase") or "") == "REGULAR_SEASON",
                    "timestamp_utc": stamp,
                    "timestamp_unix": str(rec.get("timestamp") or ""),
                    "game_clock": str(rec.get("game_clock") or ""),
                    "entry_phase": str(rec.get("entry_phase") or ""),
                    "alignment_confidence": str(rec.get("alignment_confidence") or ""),
                    "home_team": str(rec.get("home_team") or ""),
                    "away_team": str(rec.get("away_team") or ""),
                    "bought_team": str(rec.get("bought_team") or ""),
                    "opponent_team": str(rec.get("opponent_team") or ""),
                    "side": side,
                    "score_home": _int_value(rec.get("score_home"), field="score_home", ticker=ticker),
                    "score_away": _int_value(rec.get("score_away"), field="score_away", ticker=ticker),
                    "bought_margin": _int_value(
                        rec.get("bought_team_margin"), field="bought_team_margin", ticker=ticker
                    ),
                    "period_remaining_s": float(rec.get("period_remaining_s") or 0),
                    "game_seconds_remaining": float(rec.get("game_seconds_remaining") or 0),
                    "entry_bid_cents": entry,
                    "entry_ask_cents": _optional_cents(
                        rec.get("market_yes_ask"), field="market_yes_ask", ticker=ticker
                    ),
                    "entry_last_cents": _optional_cents(
                        rec.get("market_last_price"), field="market_last_price", ticker=ticker
                    ),
                    "entry_volume": rec.get("market_volume"),
                    "pregame_cents": _pregame_cents(rec, side, ticker=ticker),
                    "pregame_source": source,
                    "possession_status": str(rec.get("possession_status") or "UNAVAILABLE"),
                    "fouls_timeouts_status": str(rec.get("fouls_timeouts_status") or "UNAVAILABLE"),
                    "t40": t40,
                    "w": win,
                    "post_entry_min": post,
                    "terminal_yes": _as_bool(
                        rec.get("terminal_yes"), field="terminal_yes", ticker=ticker
                    ),
                    "exit_kind": str(rec.get("exit_kind") or ""),
                    "exit_timestamp_utc": str(rec.get("exit_timestamp_utc") or ""),
                    "exit_period": str(rec.get("exit_period") or ""),
                    "exit_game_clock": str(rec.get("exit_game_clock") or ""),
                    "exit_score_home": rec.get("exit_score_home"),
                    "exit_score_away": rec.get("exit_score_away"),
                    "final_score_home": rec.get("final_score_home"),
                    "final_score_away": rec.get("final_score_away"),
                    "rule": RULE,
                }
            )
    _assert_population(rows)
    ids = [row["instance_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ReverseFeaturesError("LOCK_MISMATCH", "instance_id collision")
    events = [row["event_id"] for row in rows]
    if len(events) != len(set(events)):
        raise ReverseFeaturesError("LOCK_MISMATCH", "not one FIRST80 per event")
    return rows


def _cohorts(rows: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    n = len(rows)
    s_n = sum(1 for row in rows if not row["t40"])
    w_t40 = sum(1 for row in rows if row["t40"] and row["w"])
    l_t40 = sum(1 for row in rows if row["t40"] and not row["w"])
    if s_n + w_t40 + l_t40 != n:
        raise ReverseFeaturesError("LOCK_MISMATCH", "cohort identity failed")
    return n, s_n, w_t40, l_t40


def _assert_tape(
    rows: list[dict[str, Any]],
    *,
    n: int,
    s_n: int,
    w_t40: int,
    l_t40: int,
    book: int,
    label: str,
) -> None:
    got_n, got_s, got_w, got_l = _cohorts(rows)
    got_book = book_cents(got_s, got_n, gain=GAIN_CENTS, loss=LOSS_CENTS)
    if (got_n, got_s, got_w, got_l, got_book) != (n, s_n, w_t40, l_t40, book):
        raise ReverseFeaturesError(
            "LOCK_MISMATCH",
            f"{label} {(got_n, got_s, got_w, got_l, got_book)} != {(n, s_n, w_t40, l_t40, book)}",
        )


def _assert_population(rows: list[dict[str, Any]]) -> None:
    _assert_tape(
        rows,
        n=NBA_Q2Q3_N,
        s_n=NBA_Q2Q3_S,
        w_t40=NBA_Q2Q3_W_T40,
        l_t40=NBA_Q2Q3_L_T40,
        book=NBA_Q2Q3_BOOK,
        label="NBA Q2∪Q3",
    )
    q2 = [row for row in rows if row["slice"] == "Q2"]
    q3 = [row for row in rows if row["slice"] == "Q3"]
    if len(q2) != NBA_Q2_N or len(q3) != NBA_Q3_N:
        raise ReverseFeaturesError(
            "LOCK_MISMATCH", f"Q2/Q3 N {len(q2)}/{len(q3)} != {NBA_Q2_N}/{NBA_Q3_N}"
        )
    q2_rs = [row for row in q2 if row["regular_season"]]
    _assert_tape(
        q2_rs,
        n=NBA_Q2_RS_N,
        s_n=NBA_Q2_RS_S,
        w_t40=NBA_Q2_RS_W_T40,
        l_t40=NBA_Q2_RS_L_T40,
        book=NBA_Q2_RS_BOOK,
        label="NBA Q2 regular season",
    )
