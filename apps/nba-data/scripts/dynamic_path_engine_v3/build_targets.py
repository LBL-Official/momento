#!/usr/bin/env python3
"""Future-only hazard targets. Features must not read these columns."""

from __future__ import annotations

import sys

from common import OUT, read_parquet_rows, utc_now, write_json, write_parquet


def hz(state_ts, barrier_ts, minutes):
    if barrier_ts is None:
        return 0
    dt = int(barrier_ts) - int(state_ts)
    return int(0 < dt <= minutes * 60)


def main() -> int:
    trades = {t["trade_id"]: t for t in read_parquet_rows(OUT / "first80_trades.parquet")}
    panel = read_parquet_rows(OUT / "post_entry_state_panel.parquet")
    rows = []
    for p in panel:
        tr = trades[p["trade_id"]]
        b = tr.get("first_40_close_ts")
        ts = int(p["state_timestamp"])
        rows.append(
            {
                "trade_id": p["trade_id"],
                "state_timestamp": ts,
                "H_40_5M": hz(ts, b, 5),
                "H_40_10M": hz(ts, b, 10),
                "H_40_15M": hz(ts, b, 15),
                "EVENTUAL_40": tr["Y_40_CLOSE"],
                "barrier_event_this_interval": p["barrier_event_this_interval"],
                "minutes_to_barrier": None
                if b is None
                else (int(b) - ts) / 60.0,
                "target_source": "FUTURE_OUTCOME_ONLY",
            }
        )
    write_parquet(OUT / "hazard_targets.parquet", rows)
    n5 = sum(r["H_40_5M"] for r in rows)
    write_json(
        OUT / "target_summary.json",
        {
            "written_utc": utc_now(),
            "n": len(rows),
            "H_40_5M_events": n5,
            "H_40_5M_rate": n5 / len(rows) if rows else None,
            "H_40_10M_rate": sum(r["H_40_10M"] for r in rows) / len(rows) if rows else None,
            "H_40_15M_rate": sum(r["H_40_15M"] for r in rows) / len(rows) if rows else None,
        },
    )
    print(f"targets n={len(rows)} H5_rate={n5/len(rows) if rows else None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
