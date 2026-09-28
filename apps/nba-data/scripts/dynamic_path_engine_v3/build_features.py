#!/usr/bin/env python3
"""Join panel + market + game + targets. Write feature manifest before models."""

from __future__ import annotations

import sys

import pyarrow.parquet as pq

from common import OUT, utc_now, write_json
from lib import join_tables, str_col


def main() -> int:
    needed = [
        "post_entry_state_panel.parquet",
        "post_entry_market_states.parquet",
        "post_entry_game_states.parquet",
        "hazard_targets.parquet",
    ]
    tables = []
    for name in needed:
        p = OUT / name
        if not p.exists():
            print("missing", name, file=sys.stderr)
            return 1
        tables.append(pq.read_table(p))
    t = tables[0]
    for other in tables[1:]:
        t = join_tables(t, other)
    n = t.num_rows
    dfe = t.column("distance_from_entry_cents").to_pylist() if "distance_from_entry_cents" in t.column_names else [None] * n
    net = t.column("net_score_since_entry").to_pylist() if "net_score_since_entry" in t.column_names else [None] * n
    per = []
    agree = []
    for a, b in zip(dfe, net):
        if a is None or b is None or b == 0:
            per.append(None)
            agree.append(None)
        else:
            per.append(float(a) / float(b))
            agree.append(int((a > 0 and b > 0) or (a < 0 and b < 0)))
    import pyarrow as pa

    t = t.append_column("mkt_cents_per_net_point", pa.array(per, type=pa.float64()))
    t = t.append_column("market_game_sign_agree", pa.array(agree, type=pa.int64()))
    OUT.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, OUT / "features_panel.parquet")
    target_only = {
        "H_40_5M",
        "H_40_10M",
        "H_40_15M",
        "EVENTUAL_40",
        "minutes_to_barrier",
        "Y_40_CLOSE",
        "Y_40_WICK",
        "eventual_barrier",
        "censored",
        "barrier_event_this_interval",
        "target_source",
        "first_40_close_ts",
        "time_to_40_s",
    }
    preds = [c for c in t.column_names if c not in target_only]
    write_json(
        OUT / "feature_manifest.json",
        {
            "written_utc": utc_now(),
            "n_rows": t.num_rows,
            "n_columns": len(t.column_names),
            "primary_target": "H_40_5M",
            "predictor_columns": preds,
            "note": "Predictors must have source ≤ state_timestamp. Horizon labels are TARGET_ONLY.",
        },
    )
    print(f"features_panel rows={t.num_rows} cols={len(t.column_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
