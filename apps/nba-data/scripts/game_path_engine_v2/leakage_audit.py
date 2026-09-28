#!/usr/bin/env python3
"""Leakage audit: predictors must not use timestamps after ENTRY_DECISION_TIME."""

from __future__ import annotations

import sys

from common import OUT, read_parquet_rows, utc_now, write_json

TARGETS = {
    "Y_40_CLOSE",
    "Y_40_WICK",
    "target_close_40",
    "target_wick_40_post_entry_bar_only",
    "target_wick_40_post_entry_ts",
    "first_40_close_ts",
    "eventual_winner",
    "expiration_result_yes",
}

METADATA_PREFIXES = (
    "observation_id",
    "event_id",
    "game_id",
    "nba_game_id",
    "ticker",
    "team",
    "opponent",
    "home_",
    "away_",
    "game_date",
    "dataset_split",
    "season_phase",
    "entry_",
    "first_80",
    "close_ts",
    "maker_fill",
    "alignment_",
    "snap_",
    "scope",
    "feature_",
    "event_ticker",
    "market_id",
    "team_code",
    "game_phase",
    "path_state",
    "GAME_MARKET",
    "last_scoring_run_team",
    "largest_prior_run_team",
)


def _is_meta(name: str) -> bool:
    if name in TARGETS:
        return False
    return any(name == p or name.startswith(p) for p in METADATA_PREFIXES)


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
                    "leakage_status": "TARGET_ONLY",
                }
            )
            continue
        max_src = None
        max_entry = None
        leak = False
        for r in rows:
            entry = r.get("entry_decision_time")
            src = r.get("feature_maximum_source_timestamp")
            if entry is not None:
                max_entry = entry if max_entry is None else max(max_entry, entry)
            if src is not None:
                max_src = src if max_src is None else max(max_src, src)
                if entry is not None and src > entry:
                    leak = True
        status = "FAIL" if leak else "OK"
        if leak:
            fails += 1
        records.append(
            {
                "feature_name": name,
                "maximum_source_timestamp": max_src,
                "entry_timestamp": max_entry,
                "leakage_status": "METADATA" if _is_meta(name) and not leak else status,
            }
        )
    write_json(
        OUT / "leakage_audit.json",
        {
            "written_utc": utc_now(),
            "n_features": len(names),
            "n_fail": fails,
            "records": records,
        },
    )
    if fails:
        print(f"LEAKAGE FAIL n={fails}", file=sys.stderr)
        return 1
    print(f"leakage OK features={len(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
