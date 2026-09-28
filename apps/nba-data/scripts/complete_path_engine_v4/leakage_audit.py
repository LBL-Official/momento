#!/usr/bin/env python3
"""Leakage: path source timestamp must be ≤ first-80. Exit 1 on FAIL."""

from __future__ import annotations

import sys

from common import OUT, read_parquet_rows, utc_now, write_json

TARGETS = {"Y_40_CLOSE", "Y_40_WICK", "eventual_winner"}


def main() -> int:
    rows = read_parquet_rows(OUT / "path_functionals.parquet")
    n_fail = 0
    for r in rows:
        src = r.get("feature_maximum_source_timestamp")
        entry = r.get("entry_decision_time")
        if src is None or entry is None:
            continue
        if int(src) > int(entry):
            n_fail += 1
    names = sorted(rows[0].keys()) if rows else []
    recs = []
    for name in names:
        recs.append(
            {
                "feature_name": name,
                "leakage_status": "TARGET_ONLY" if name in TARGETS else ("FAIL" if n_fail else "OK"),
                "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
            }
        )
    write_json(
        OUT / "leakage_audit.json",
        {
            "written_utc": utc_now(),
            "n_rows_source_after_entry": n_fail,
            "rule": "feature_maximum_source_timestamp <= entry_decision_time",
            "records": recs,
        },
    )
    if n_fail:
        print(f"LEAKAGE FAIL n={n_fail}", file=sys.stderr)
        return 1
    print(f"leakage OK n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
