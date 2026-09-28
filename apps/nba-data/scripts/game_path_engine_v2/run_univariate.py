#!/usr/bin/env python3
"""Level-1 univariate bucket tests on TRAIN; VAL/OOS reported, not used to retune."""

from __future__ import annotations

import sys

from common import (
    OUT,
    benjamini_hochberg,
    split_rows,
    utc_now,
    write_json,
)
from eval_lib import experiment_row, group_by, load_analysis_rows

UNIVARIATE_KEYS = [
    "quarter_bucket",
    "score_diff_frozen_bucket",
    "pace_bucket",
    "path_state",
    "GAME_MARKET_ALIGNMENT",
    "score_differential_qbucket",
    "number_of_lead_changes_qbucket",
    "current_lead_duration_s_qbucket",
    "score_differential_stdev_qbucket",
    "comeback_magnitude_qbucket",
    "lead_decay_qbucket",
    "vol_5m_cents_qbucket",
    "momentum_5m_cents_qbucket",
    "minutes_from_50_to_80_qbucket",
]


def main() -> int:
    rows = load_analysis_rows()
    train_u = split_rows(rows, "TRAIN", primary_only=True)
    val_u = split_rows(rows, "VALIDATION", primary_only=True)
    oos_u = split_rows(rows, "OOS", primary_only=True)
    experiments = []
    pvals = []
    for key in UNIVARIATE_KEYS:
        g_tr = group_by(train_u, key)
        g_va = group_by(val_u, key)
        g_oo = group_by(oos_u, key)
        for lab in sorted(g_tr.keys()):
            rec = experiment_row(
                experiment_id=f"UNI|{key}|{lab}",
                hypothesis=f"Univariate {key}={lab}",
                features_used=key,
                bucket_definition=f"{key}=={lab}",
                train=g_tr[lab],
                val=g_va.get(lab, []),
                oos=g_oo.get(lab, []),
                universe_train=train_u,
            )
            experiments.append(rec)
            pvals.append(rec["train_p_vs_complement"])
    bh = benjamini_hochberg(pvals)
    for rec, sig in zip(experiments, bh):
        rec["bh_fdr_0_10"] = bool(sig)
        rec["raw_p"] = rec["train_p_vs_complement"]
    write_json(
        OUT / "experiments" / "univariate.json",
        {
            "written_utc": utc_now(),
            "n_experiments": len(experiments),
            "n_bh_selected": int(sum(bh)),
            "experiments": experiments,
        },
    )
    print(f"univariate experiments={len(experiments)} BH={sum(bh)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
