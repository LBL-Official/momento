#!/usr/bin/env python3
"""Level-2 pre-specified two-way interactions only. No N-choose-K search."""

from __future__ import annotations

import sys

from common import MIN_BUCKET_N_TRAIN, OUT, split_rows, utc_now, write_json
from eval_lib import experiment_row, load_analysis_rows

PAIRS = [
    ("quarter_bucket", "score_diff_frozen_bucket", "I1"),
    ("quarter_bucket", "score_differential_stdev_qbucket", "I2"),
    ("score_diff_frozen_bucket", "number_of_lead_changes_qbucket", "I3"),
    ("path_state", "vol_5m_cents_qbucket", "I4"),
    ("comeback_magnitude_qbucket", "quarter_bucket", "I5"),
    ("momentum_5m_cents_qbucket", "net_score_sign", "I6"),
]


def net_sign(r):
    v = r.get("net_score_change_last_5m")
    if v is None:
        return None
    if v >= 3:
        return "SCORE_UP"
    if v <= -3:
        return "SCORE_DOWN"
    return "SCORE_FLAT"


def main() -> int:
    rows = load_analysis_rows()
    for r in rows:
        r["net_score_sign"] = net_sign(r)
    train_u = split_rows(rows, "TRAIN", primary_only=True)
    val_u = split_rows(rows, "VALIDATION", primary_only=True)
    oos_u = split_rows(rows, "OOS", primary_only=True)
    experiments = []
    skipped = 0
    for a, b, iid in PAIRS:
        seen = {}
        for r in train_u:
            ka, kb = r.get(a), r.get(b)
            if ka is None or kb is None:
                continue
            seen.setdefault((str(ka), str(kb)), 0)
            seen[(str(ka), str(kb))] += 1
        for (ka, kb), n in seen.items():
            if n < MIN_BUCKET_N_TRAIN:
                skipped += 1
                continue

            def sel(rs, aa=a, bb=b, ka=ka, kb=kb):
                return [r for r in rs if str(r.get(aa)) == ka and str(r.get(bb)) == kb]

            rec = experiment_row(
                experiment_id=f"IX|{iid}|{ka}|{kb}",
                hypothesis=f"{iid}: {a}={ka} AND {b}={kb}",
                features_used=f"{a}*{b}",
                bucket_definition=f"{a}=={ka} AND {b}=={kb}",
                train=sel(train_u),
                val=sel(val_u),
                oos=sel(oos_u),
                universe_train=train_u,
            )
            experiments.append(rec)
    write_json(
        OUT / "experiments" / "interactions.json",
        {
            "written_utc": utc_now(),
            "n_experiments": len(experiments),
            "n_skipped_small": skipped,
            "experiments": experiments,
        },
    )
    print(f"interactions n={len(experiments)} skipped_small={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
