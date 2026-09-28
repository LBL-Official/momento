"""Read-only checks against the original run. This module does not write there."""

from __future__ import annotations

import csv
import json
from pathlib import Path


TARGETS = {
    "trades": 647,
    "wins": 330,
    "stops": 317,
    "gross_cents": 25_612_015,
    "fees_cents": 2_063_197,
    "net_cents": 23_548_818,
    "ending_equity_cents": 25_548_818,
    "paired_stop_minus_hold_cents": -5_107_503,
    "financed_difference_cents": 3_238_004,
}


def reconcile(run: Path) -> dict:
    trades = list(csv.DictReader((run / "01_trade_logs/trades.csv").open()))
    wins = sum(1 for row in trades if row["exit_reason"] == "WIN_SETTLEMENT")
    stops = sum(1 for row in trades if row["exit_reason"] == "STOP")
    gross = sum(int(row["gross_pnl_cents"]) for row in trades)
    fees = sum(int(row["entry_fee_cents"]) + int(row["exit_fee_cents"]) for row in trades)
    net = sum(int(row["net_pnl_cents"]) for row in trades)
    summary = json.loads((run / "summary.json").read_text())
    paired = int(summary["paired_diff_sum_cents"])
    hold_net = int(summary["hold_net_pnl_cents"])
    checks = {
        "trades": (len(trades), TARGETS["trades"]),
        "wins": (wins, TARGETS["wins"]),
        "stops": (stops, TARGETS["stops"]),
        "gross_cents": (gross, TARGETS["gross_cents"]),
        "fees_cents": (fees, TARGETS["fees_cents"]),
        "net_cents": (net, TARGETS["net_cents"]),
        "identity_gross_minus_fees": (gross - fees, net),
        "paired_stop_minus_hold_cents": (paired, TARGETS["paired_stop_minus_hold_cents"]),
        "financed_stop_minus_saved_hold_cents": (net - hold_net, TARGETS["financed_difference_cents"]),
        "saved_ending_equity": (int(summary["ending_equity_cents"]), TARGETS["ending_equity_cents"]),
    }
    nba = sum(int(row["net_pnl_cents"]) for row in trades if row["sport"] == "NBA")
    ncaab = sum(int(row["net_pnl_cents"]) for row in trades if row["sport"] == "NCAAB")
    return {
        "checks": {name: {"actual": actual, "expected": expected, "ok": actual == expected} for name, (actual, expected) in checks.items()},
        "all_ok": all(actual == expected for actual, expected in checks.values()),
        "nba_net_cents": nba,
        "ncaab_net_cents": ncaab,
        "sport_sum_ok": nba + ncaab == net,
        "ending_cash_matches_equity": TARGETS["ending_equity_cents"] == 2_000_000 + net,
        "hold_book_source": "summary.json hold_net_pnl_cents and hold_admitted",
        "admitted_only_note": "The saved trade file contains the 647 admitted trades. Rejected opportunities are in candidate_audit.csv and are not a complete ex-ante resample frame.",
    }
