"""Load the locked derived-four cohort and T65 touch locks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from . import (
    POOL_N,
    SETTLEMENT_YES_AND_T65,
    SLICE_N,
    STOP_N,
    SURVIVOR_N,
    WANTED,
)

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"
TOUCHES = REPO / "research/choosin_texas/t60_band/touches.json"


def _as_int(value: object, label: str) -> int:
    if value in (None, ""):
        raise ValueError(f"missing {label}")
    return int(float(str(value)))


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(float(str(value)))


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_cohort() -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        raise FileNotFoundError(LEDGER)
    if not TOUCHES.is_file():
        raise FileNotFoundError(TOUCHES)
    touches = {str(row["ticker"]): row for row in json.loads(TOUCHES.read_text())["rows"]}
    rows: list[dict[str, Any]] = []
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        for rec in csv.DictReader(handle):
            key = (rec["sport"].strip(), rec["slice"].strip())
            if key not in WANTED:
                continue
            ticker = rec["ticker"].strip()
            touch = touches.get(ticker)
            if touch is None:
                raise ValueError(f"missing touch {ticker}")
            entry_cents = _as_int(rec["market_yes_bid"], f"{ticker} entry")
            terminal_yes = _truthy(rec.get("terminal_yes") if rec.get("terminal_yes") not in (None, "") else rec.get("W"))
            t65_close = _optional_int(touch.get("t65_close"))
            t65_ts = _optional_int(touch.get("t65_ts"))
            post_min = _as_int(touch["post_min"], f"{ticker} post_min")
            if (t65_close is not None) != (post_min <= 65):
                raise ValueError(f"{ticker} t65 drifted from post_min")
            if (t65_close is None) != (t65_ts is None):
                raise ValueError(f"{ticker} t65 timestamp missing")
            rows.append(
                {
                    "ticker": ticker,
                    "event_id": rec["event_id"].strip(),
                    "sport": key[0],
                    "slice": key[1],
                    "game_date": rec["game_date"].strip(),
                    "dataset_split": rec.get("dataset_split", "").strip(),
                    "entry_ts": _as_int(rec["timestamp"], f"{ticker} entry_ts"),
                    "entry_cents": entry_cents,
                    "ledger_exit_ts": _as_int(rec["exit_timestamp"], f"{ticker} exit_ts"),
                    "ledger_exit_kind": rec["exit_kind"].strip(),
                    "ledger_exit_cents": _as_int(rec["exit_price_cents"], f"{ticker} exit_px"),
                    "terminal_yes": terminal_yes,
                    "t65_ts": t65_ts,
                    "t65_close": t65_close,
                    "post_min": post_min,
                    "t65_exit_period": touch.get("exit_period"),
                    "t65_exit_remaining_s": touch.get("exit_remaining_s"),
                    "t65_clock_bin": touch.get("clock_bin"),
                }
            )
    if len(rows) != POOL_N:
        raise ValueError(f"derived four {len(rows)} != {POOL_N}")
    for slice_id, expected in SLICE_N.items():
        got = sum(1 for row in rows if row["slice"] == slice_id)
        if got != expected:
            raise ValueError(f"{slice_id} {got} != {expected}")
    stops = sum(1 for row in rows if row["t65_close"] is not None)
    survivors = POOL_N - stops
    if stops != STOP_N or survivors != SURVIVOR_N:
        raise ValueError(f"stop lock {stops}/{survivors}")
    settlement_yes_stops = sum(
        1 for row in rows if row["t65_close"] is not None and row["ledger_exit_kind"] == "SETTLEMENT_YES"
    )
    if settlement_yes_stops != SETTLEMENT_YES_AND_T65:
        raise ValueError(f"SETTLEMENT_YES∧T65 {settlement_yes_stops} != {SETTLEMENT_YES_AND_T65}")
    for row in rows:
        if row["t65_close"] is None and row["ledger_exit_kind"] != "SETTLEMENT_YES":
            raise ValueError(f"{row['ticker']} survivor is not SETTLEMENT_YES")
        if row["t65_close"] is None and not row["terminal_yes"]:
            raise ValueError(f"{row['ticker']} survivor terminal_yes false")
    rows.sort(key=lambda row: (row["entry_ts"], row["ticker"]))
    return rows


def cohort_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_slice = {slice_id: sum(1 for row in rows if row["slice"] == slice_id) for slice_id in SLICE_N}
    by_sport = {
        "NBA": sum(1 for row in rows if row["sport"] == "NBA"),
        "NCAAB": sum(1 for row in rows if row["sport"] == "NCAAB"),
    }
    by_split = {}
    for row in rows:
        by_split[row["dataset_split"]] = by_split.get(row["dataset_split"], 0) + 1
    return {
        "cohort_id": "FIRST80_DERIVED_FOUR_936",
        "n": len(rows),
        "by_slice": by_slice,
        "by_sport": by_sport,
        "by_split": by_split,
        "date_min": min(row["game_date"] for row in rows),
        "date_max": max(row["game_date"] for row in rows),
        "entry_signal": "minute_close_yes_bid_first_touch_ge_80",
        "stop_n": STOP_N,
        "survivor_n": SURVIVOR_N,
        "settlement_yes_and_t65": SETTLEMENT_YES_AND_T65,
        "ledger": str(LEDGER.relative_to(REPO)),
        "touches": str(TOUCHES.relative_to(REPO)),
        "live_execution": False,
        "candle_path_not_fill": True,
    }
