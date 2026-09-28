"""NBA 2Q/3Q trades with a 78¢ up-cross. N is observed. It is not 604."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from roller.austin.paths import repo_root
from roller.choosin_texas.first78.eligibility import find_entry, stop_after
from roller.choosin_texas.first78.membership import load_membership
from roller.austin_first78.config import ENTRY_CENTS, STOP_CENTS


def load_nba_trades(*, progress=None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    src = repo_root() / "research/first78_67_portfolio_v1/src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from first78.extract import _index_candles, _read_bars

    root = repo_root()
    candles = _index_candles(root / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba")
    exclusions: dict[str, int] = {}
    trades: list[dict[str, Any]] = []
    members = [row for row in load_membership() if row["sport"] == "NBA" and row["slice"] in {"Q2", "Q3"}]
    for index, member in enumerate(members, start=1):
        if progress and index % 100 == 0:
            progress(f"membership {index}/{len(members)}")
        if member["side"] not in {"home", "away"}:
            exclusions["SIDE_UNAVAILABLE"] = exclusions.get("SIDE_UNAVAILABLE", 0) + 1
            continue
        path = candles.get(member["ticker"])
        if path is None:
            exclusions["NO_CANDLES"] = exclusions.get("NO_CANDLES", 0) + 1
            continue
        entry = find_entry(_read_bars(path), hit_cents=ENTRY_CENTS)
        if not entry.get("cross_found"):
            reason = str(entry.get("reason") or "NO_CROSS")
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        stop = stop_after(entry, STOP_CENTS)
        stamp = datetime.fromtimestamp(int(entry["signal_ts"]), tz=timezone.utc)
        terminal = member["terminal"]
        won = terminal == "yes"
        trades.append(
            {
                "trade_id": f"f78-{member['ticker']}",
                "event_id": member["event_id"],
                "ticker": member["ticker"],
                "sport": "NBA",
                "slice": member["slice"],
                "quarter": 2 if member["slice"] == "Q2" else 3,
                "entry_side": member["side"],
                "entry_timestamp": stamp.isoformat(),
                "entry_price_cents": int(entry["observed_close_cents"]),
                "game_date": stamp.date().isoformat(),
                "calendar_month": stamp.strftime("%Y-%m"),
                "w": won,
                "terminal_yes": won,
                "t67": stop.get("stop_ts") is not None,
                "t40": stop.get("stop_ts") is not None,
                "final_score_home": member["final_home"],
                "final_score_away": member["final_away"],
                "home_score_entry": None,
                "away_score_entry": None,
                "entry_seconds_remaining": None,
            }
        )
    return trades, exclusions
