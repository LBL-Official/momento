#!/usr/bin/env python3
"""Join Z_τ80 tables and add GAME_MARKET_ALIGNMENT. No post-entry fields."""

from __future__ import annotations

import sys

from common import OUT, join_maps, read_parquet_rows, write_json, write_parquet, utc_now
from gamepath import game_market_alignment


def main() -> int:
    needed = [
        "observations.parquet",
        "game_state_entry.parquet",
        "score_path_features.parquet",
        "lead_path_features.parquet",
        "game_volatility_features.parquet",
        "market_path_features.parquet",
    ]
    tables = []
    for name in needed:
        path = OUT / name
        if not path.exists():
            print(f"missing {name}", file=sys.stderr)
            return 1
        tables.append(read_parquet_rows(path))
    rows = join_maps(*tables)
    for r in rows:
        r["GAME_MARKET_ALIGNMENT"] = game_market_alignment(
            r.get("net_score_change_last_5m"),
            r.get("momentum_5m_cents"),
        )
        r["feature_maximum_source_timestamp"] = r.get("entry_decision_time")
        r["feature_status"] = "CAUSAL_AT_ENTRY"
    write_parquet(OUT / "features_entry.parquet", rows)
    write_json(
        OUT / "feature_audit.json",
        {
            "written_utc": utc_now(),
            "n": len(rows),
            "n_columns": 0 if not rows else len(rows[0]),
            "primary_n": sum(
                1
                for r in rows
                if r.get("alignment_confidence") in ("HIGH", "MEDIUM")
            ),
            "note": "Predictors use PBP actions with modeled wall ≤ entry and candles with end_period_ts ≤ entry.",
        },
    )
    print(f"features n={len(rows)} cols={0 if not rows else len(rows[0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
