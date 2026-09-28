#!/usr/bin/env python3
"""Pre-registered H1–H7 bucket tests."""

from __future__ import annotations

import sys

from common import OUT, split_rows, utc_now, write_json
from eval_lib import experiment_row, hmasks, load_analysis_rows, train_stats

HYP = [
    ("H1", "H1", "Stable large leads → lower q"),
    ("H2", "H2", "Volatile games → higher q"),
    ("H3", "H3", "Recent comebacks → higher q"),
    ("H4", "H4", "Collapsing leads → higher q"),
    ("H5", "H5", "Late large leads → lower q"),
    ("H6", "H6", "Market/game disagreement → higher q"),
    ("H7V", "H7_violent", "Violent 50→80 repricing (two-sided)"),
    ("H7G", "H7_gradual", "Gradual 50→80 repricing (two-sided)"),
]


def main() -> int:
    rows = load_analysis_rows()
    train_u = split_rows(rows, "TRAIN", primary_only=True)
    val_u = split_rows(rows, "VALIDATION", primary_only=True)
    oos_u = split_rows(rows, "OOS", primary_only=True)
    stats = train_stats(train_u)
    experiments = []
    for eid, key, hypo in HYP:
        def sel(rs, k=key):
            return [r for r in rs if hmasks(r, stats).get(k)]

        rec = experiment_row(
            experiment_id=f"H|{eid}",
            hypothesis=hypo,
            features_used=key,
            bucket_definition=key,
            train=sel(train_u),
            val=sel(val_u),
            oos=sel(oos_u),
            universe_train=train_u,
        )
        experiments.append(rec)
    write_json(
        OUT / "experiments" / "hypotheses.json",
        {"written_utc": utc_now(), "train_stats": stats, "experiments": experiments},
    )
    print(f"hypotheses n={len(experiments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
