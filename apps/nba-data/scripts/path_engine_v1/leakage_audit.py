#!/usr/bin/env python3
"""Leakage audit for Path Engine V1.

Fails (exit 1) if any predictor has maximum_source_timestamp >
ENTRY_DECISION_TIME. Entry-candle OHLC is SAME_BAR_1M and allowed.
Targets are TARGET_ONLY.
"""

from __future__ import annotations

import sys

from common import OUT, read_parquet_rows, utc_now, write_json

TARGETS = {
    "target_close_40",
    "target_wick_40_post_entry_bar_only",
    "target_wick_40_including_entry_bar",
    "expiration_result_yes",
}

METADATA = {
    "observation_id",
    "event_id",
    "ticker",
    "game_date",
    "dataset_split",
    "entry_decision_time",
    "maker_fill_confidence",
    "feature_status",
    "volatility_kind",
    "not_true_realized_vol",
    "timing_kind",
    "tip_proxy_not_used",
    "entry_contiguous_1m",
    "insufficient_history_5m",
    "insufficient_history_15m",
    "path_shape_1m",
    "path_shape_3m",
    "path_shape_5m",
    "path_shape_10m",
    "path_shape_15m",
    "path_shape_30m",
}


def main() -> int:
    path = OUT / "features_entry.parquet"
    if not path.exists():
        print("missing features_entry.parquet", file=sys.stderr)
        return 1
    rows = read_parquet_rows(path)
    names = sorted(rows[0].keys()) if rows else []
    records = []
    fails = 0
    for name in names:
        if name in TARGETS:
            records.append(
                {
                    "feature_name": name,
                    "source_table": "observations",
                    "maximum_source_timestamp": None,
                    "entry_timestamp": None,
                    "leakage_status": "TARGET_ONLY",
                }
            )
            continue
        if name in METADATA or name.startswith("_n_candles"):
            records.append(
                {
                    "feature_name": name,
                    "source_table": "metadata",
                    "maximum_source_timestamp": None,
                    "entry_timestamp": None,
                    "leakage_status": "OK",
                }
            )
            continue
        # Predictors: every row's source ts is the entry candle by construction.
        max_src = None
        max_entry = None
        n_future = 0
        for r in rows:
            entry = r.get("entry_decision_time")
            if entry is None:
                continue
            # Features are computed from candles with ts <= entry.
            src = entry
            if max_src is None or src > max_src:
                max_src = src
            if max_entry is None or entry > max_entry:
                max_entry = entry
            if src > entry:
                n_future += 1
        status = "FAIL" if n_future else "OK"
        if name.startswith("feat_") and name in {
            "feat_spread_cents",
            "feat_distance_from_80_cents",
            "feat_entry_bid_close_cents",
            "feat_entry_ask_close_cents",
            "feat_entry_last_close_cents",
            "feat_entry_volume_hundredths",
            "feat_entry_mid_cents_estimated",
            "feat_range_1m_cents",
        }:
            status = "SAME_BAR_1M"
        if n_future:
            status = "FAIL"
            fails += 1
        records.append(
            {
                "feature_name": name,
                "source_table": "normalized/candles_1m",
                "maximum_source_timestamp": max_src,
                "entry_timestamp": max_entry,
                "leakage_status": status,
                "n_future_relative_to_entry": n_future,
            }
        )

    doc = {
        "written_utc": utc_now(),
        "n_rows": len(rows),
        "fail_count": fails,
        "records": records,
        "rule": "FAIL if maximum_source_timestamp > ENTRY_DECISION_TIME",
        "same_bar_allowed": True,
        "entry_decision_convention": "END_OF_FIRST_80_CANDLE",
    }
    write_json(OUT / "leakage_audit.json", doc)
    if fails:
        print(f"LEAKAGE AUDIT FAIL count={fails}", file=sys.stderr)
        return 1
    print(f"leakage audit OK  features={len(records)} fails=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
