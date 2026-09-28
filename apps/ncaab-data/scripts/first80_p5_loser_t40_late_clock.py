#!/usr/bin/env python3
"""P5 FIRST80→40 losers in 1H second 10 and 2H first 10: late 2H clock.

Among frozen P5 vs P5 FIRST80 losers in those entry bins (every loser
close-touches 40), report the share whose first yes_bid_close ≤ 40
happened with 6/5/4/3/2/1 minutes of second-half remaining.

Research only. Does not change live FIRST01. Uses the half-barrier T40
clock (HALF_BOUNDED_OBSERVED_WALLCLOCK). Regulation is 2 × 20:00.
Period ≥ 3 is OT. Future OT is not invented.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import first80_p5_half_barrier_survival as P5  # noqa: E402
import first80_q2_40_loser_late_clock as L  # noqa: E402

OUT = P5.OUT.parent / "first80_p5_loser_t40_late_clock"
TRADES_PATH = P5.OUT / "trades.parquet"
NCAAB_CLOSING_PERIOD = 2
NCAAB_OT_MIN_PERIOD = 3
SLICES = {
    "H1_2": {"n": 193, "losers": 30, "t40": 51, "label": "1H second 10"},
    "H2_1": {"n": 139, "losers": 21, "t40": 31, "label": "2H first 10"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_trades() -> list[dict]:
    import pyarrow.parquet as pq

    if not TRADES_PATH.exists():
        print("trades.parquet missing — rebuilding P5 half-barrier ledger", flush=True)
        result = P5.analyze()
        P5.write_outputs(result)
    return pq.read_table(TRADES_PATH).to_pylist()


def analyze(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else _read_trades()
    slices = []
    for bucket, spec in SLICES.items():
        slices.append(
            L.analyze_slice(
                rows,
                entry_field="entry_half_bucket",
                bucket=bucket,
                expected_n=spec["n"],
                expected_losers=spec["losers"],
                expected_t40=spec["t40"],
                closing_period=NCAAB_CLOSING_PERIOD,
                ot_min_period=NCAAB_OT_MIN_PERIOD,
                closing_label="2H",
                label=spec["label"],
            )
        )
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "universe": "P5 vs P5 KXNCAAMBGAME 2025-26 FIRST80, H1_2 and H2_1 losers",
        "clock": (
            "2H remaining at first tradable yes_bid_close <= 40. "
            "Period >= 3 is OT. Future OT not invented."
        ),
        "alignment_model": "HALF_BOUNDED_OBSERVED_WALLCLOCK",
        "slices": slices,
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", OUT / "summary.json")
    for block in summary["slices"]:
        print(
            block["bucket"],
            block["label"],
            "losers",
            block["n_losers"],
            "before last 6",
            block["n_t40_before_last_6"],
            f"({block['pct_losers_before_last_6']}%)",
            "last 6 or OT",
            block["n_t40_last_6_or_ot"],
            f"({block['pct_losers_last_6_or_ot']}%)",
        )
        for row in block["cumulative_at_most_k_min"]:
            print(" ", row["label"], row["n"], f"{row['pct_of_losers']}% of losers")
        for row in block["discrete_bins"]:
            print("   ", row["bin"], row["n"], f"{row['pct_of_losers']}%")


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
