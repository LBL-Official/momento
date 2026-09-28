#!/usr/bin/env python3
"""Leakage audit: predictors must not use post-entry possessions or settlement."""

from __future__ import annotations

import sys

from common import OUT, read_parquet_rows, utc_now, write_json

TARGETS = {
    "Y_40_CLOSE",
    "SURVIVE_40",
    "Y_40_WICK",
    "expiration_result_yes",
    "time_to_40_minutes",
}


def main() -> int:
    rows = read_parquet_rows(OUT / "features.parquet")
    snaps = {r["observation_id"]: r for r in read_parquet_rows(OUT / "entry_snaps.parquet")}
    fails = []
    n_future = sum(1 for r in rows if r.get("z_uses_future_possession"))
    if n_future:
        fails.append({"rule": "z_uses_future_possession", "n": n_future})
    n_l2 = sum(1 for r in rows if r.get("l2_invented"))
    if n_l2:
        fails.append({"rule": "l2_invented", "n": n_l2})
    n_wall = sum(1 for r in rows if r.get("wall_clock_claimed_observed"))
    if n_wall:
        fails.append({"rule": "wall_clock_claimed_observed", "n": n_wall})
    n_snap_leak = sum(1 for s in snaps.values() if s.get("leakage_post_entry_in_z"))
    if n_snap_leak:
        fails.append({"rule": "snap_post_entry", "n": n_snap_leak})
    ok = not fails
    write_json(
        OUT / "leakage_audit.json",
        {
            "written_utc": utc_now(),
            "pass": ok,
            "fails": fails,
            "n_rows": len(rows),
            "targets": sorted(TARGETS),
        },
    )
    print("LEAKAGE AUDIT:", "PASS" if ok else "FAIL", fails)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
