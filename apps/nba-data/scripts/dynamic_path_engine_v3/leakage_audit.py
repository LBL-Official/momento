#!/usr/bin/env python3
"""Leakage audit: max source timestamp ≤ state timestamp. Exit 1 on FAIL."""

from __future__ import annotations

import sys

import pyarrow.parquet as pq

from common import OUT, utc_now, write_json

TARGETS = {
    "H_40_5M",
    "H_40_10M",
    "H_40_15M",
    "EVENTUAL_40",
    "minutes_to_barrier",
    "Y_40_CLOSE",
    "Y_40_WICK",
    "eventual_barrier",
    "censored",
    "barrier_event_this_interval",
    "target_source",
    "first_40_close_ts",
    "time_to_40_s",
    "eventual_winner",
}

META_PREFIXES = (
    "trade_id",
    "event_id",
    "game_id",
    "nba_game_id",
    "ticker",
    "team",
    "home_",
    "away_",
    "game_date",
    "dataset_split",
    "season_phase",
    "entry_",
    "close_ts",
    "maker_fill",
    "alignment_",
    "snap_",
    "feature_",
    "same_bar",
    "panel_",
    "n_alive",
    "is_last",
    "alive_above",
    "game_phase",
    "game_feature",
    "per_play",
    "volatility_kind",
    "window_",
    "path_archetype",
)


def _is_meta(name: str) -> bool:
    return any(name == p or name.startswith(p) for p in META_PREFIXES)


def main() -> int:
    path = OUT / "features_panel.parquet"
    if not path.exists():
        print("missing features_panel.parquet", file=sys.stderr)
        return 1
    t = pq.read_table(path)
    names = list(t.column_names)
    state = t.column("state_timestamp").to_pylist() if "state_timestamp" in names else []
    src_m = (
        t.column("feature_maximum_source_timestamp").to_pylist()
        if "feature_maximum_source_timestamp" in names
        else [None] * t.num_rows
    )
    fails = 0
    n_src_gt = 0
    for s, src in zip(state, src_m):
        if s is None or src is None:
            continue
        if int(src) > int(s):
            n_src_gt += 1
    records = []
    for name in names:
        if name in TARGETS:
            records.append(
                {
                    "feature_name": name,
                    "source_table": "hazard_targets",
                    "leakage_status": "TARGET_ONLY",
                    "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
                }
            )
            continue
        status = "FAIL" if n_src_gt else "OK"
        if _is_meta(name) and not n_src_gt:
            status = "OK"
        if n_src_gt:
            fails += 1
        records.append(
            {
                "feature_name": name,
                "source_table": "features_panel",
                "n_source_after_state": n_src_gt,
                "leakage_status": status,
                "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
            }
        )
    # Fail only once (global source check), not per column.
    fail_flag = n_src_gt > 0
    write_json(
        OUT / "leakage_audit.json",
        {
            "written_utc": utc_now(),
            "n_features": len(names),
            "n_fail_columns": fails if fail_flag else 0,
            "n_rows_source_after_state": n_src_gt,
            "rule": "feature_maximum_source_timestamp <= state_timestamp",
            "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
            "records": records,
        },
    )
    if fail_flag:
        print(f"LEAKAGE FAIL rows={n_src_gt}", file=sys.stderr)
        return 1
    print(f"leakage OK features={len(names)} rows={t.num_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
