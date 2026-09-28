#!/usr/bin/env python3
"""Assign frozen and TRAIN-fitted buckets. Edges never refit on VAL/OOS."""

from __future__ import annotations

import sys

from buckets import assign, fit_edges
from common import OUT, read_parquet_rows, split_rows, utc_now, write_json, write_parquet


def _serializable_edges(edges: dict) -> dict:
    q = {}
    for col, (ed, labs) in (edges.get("quantiles") or {}).items():
        q[col] = {"edges": ed, "labels": labs}
    return {"quantiles": q, "pace": edges.get("pace")}


def main() -> int:
    path = OUT / "features_entry.parquet"
    if not path.exists():
        print("missing features_entry.parquet", file=sys.stderr)
        return 1
    rows = read_parquet_rows(path)
    train = split_rows(rows, "TRAIN", primary_only=True)
    edges = fit_edges(train)
    assigned = assign(rows, edges)
    write_parquet(OUT / "bucket_assignments.parquet", assigned)
    write_json(
        OUT / "models" / "bucket_edges.json",
        {
            "written_utc": utc_now(),
            "fitted_on": "TRAIN primary HIGH+MEDIUM",
            "n_train": len(train),
            "edges": _serializable_edges(edges),
        },
    )
    print(f"buckets n={len(assigned)} train_primary={len(train)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
