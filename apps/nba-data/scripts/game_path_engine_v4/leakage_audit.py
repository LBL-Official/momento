#!/usr/bin/env python3
"""Leakage audit. Any FAIL terminates the pipeline."""

from __future__ import annotations

import sys

import pyarrow.parquet as pq

from common import FEAT, OBS, REP, utc_now, write_json

TARGETS = {
    "Y_40_CLOSE",
    "Y_40_WICK",
    "eventual_winner",
    "H_40_5M",
    "H_40_10M",
    "H_40_20M",
    "H_40_30M",
    "H_40_60M",
    "hit_75",
    "hit_70",
    "hit_65",
    "hit_60",
    "hit_55",
    "hit_50",
    "hit_45",
    "hit_40",
    "hit_90_recover",
    "settle_yes",
    "settle_no",
    "min_post_close_cents",
    "time_to_40_min",
}

META_PREFIXES = (
    "trade_id",
    "event_id",
    "ticker",
    "team",
    "home_",
    "away_",
    "game_date",
    "dataset_split",
    "entry_",
    "close_ts",
    "alignment_",
    "feature_",
    "same_bar",
    "game_phase",
    "game_feature",
    "per_play",
    "volatility_kind",
    "state_timestamp",
    "alive_above",
    "minutes_since",
    "regime",
    "game_lsi_lambda",
    "game_lsi_gamma",
)


def _is_meta(name: str) -> bool:
    if name in TARGETS:
        return True
    return any(name == p or name.startswith(p) for p in META_PREFIXES)


def audit_table(path, source_table):
    t = pq.read_table(path)
    names = list(t.column_names)
    state = t.column("state_timestamp").to_pylist() if "state_timestamp" in names else []
    src_m = (
        t.column("feature_maximum_source_timestamp").to_pylist()
        if "feature_maximum_source_timestamp" in names
        else [None] * t.num_rows
    )
    n_src_gt = 0
    for s, src in zip(state, src_m):
        if s is None or src is None:
            continue
        if int(src) > int(s):
            n_src_gt += 1
    records = []
    for name in names:
        if name in TARGETS:
            status = "TARGET_ONLY"
        elif name in ("same_bar_limitation",) or name.startswith("same_bar"):
            status = "SAME_BAR_LIMITATION"
        elif n_src_gt:
            status = "FAIL"
        else:
            status = "OK"
        records.append(
            {
                "feature_name": name,
                "feature_category": name.split("_", 1)[0] if "_" in name else "meta",
                "source_table": source_table,
                "max_source_timestamp": "feature_maximum_source_timestamp",
                "decision_timestamp": "state_timestamp",
                "n_source_after_state": n_src_gt,
                "leakage_status": status,
            }
        )
    return records, n_src_gt, t.num_rows, names


def main() -> int:
    paths = [
        (OBS / "first80_game_state.parquet", "first80_game_state"),
        (OBS / "dynamic_state_panel.parquet", "dynamic_state_panel"),
        (FEAT / "game_state_features.parquet", "game_state_features"),
        (FEAT / "market_state_features.parquet", "market_state_features"),
        (FEAT / "path_features.parquet", "path_features"),
        (FEAT / "coupling_features.parquet", "coupling_features"),
        (FEAT / "economic_features.parquet", "economic_features"),
    ]
    all_records = []
    fail_rows = 0
    for path, src in paths:
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            return 1
        recs, n_gt, n_rows, _names = audit_table(path, src)
        all_records.extend(recs)
        fail_rows += n_gt
        print(f"audit {src} rows={n_rows} src_after_state={n_gt}")
    fail_flag = fail_rows > 0
    payload = {
        "written_utc": utc_now(),
        "n_records": len(all_records),
        "n_rows_source_after_state": fail_rows,
        "rule": "feature_maximum_source_timestamp <= state_timestamp",
        "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
        "alignment_never_upgraded": True,
        "records": all_records,
        "pipeline_status": "FAIL" if fail_flag else "OK",
    }
    write_json(OBS.parent / "leakage_audit.json", payload)
    write_json(REP / "leakage_audit.json", payload)
    if fail_flag:
        print(f"LEAKAGE FAIL rows={fail_rows}", file=sys.stderr)
        return 1
    print(f"leakage OK records={len(all_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
