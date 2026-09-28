#!/usr/bin/env python3
"""TRAIN-only univariate hazard relationships. Do not retune on VAL/OOS."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict

import numpy as np

from common import OUT, SPEC_DIR, utc_now, wilson, write_json
from lib import (
    DIST_BINS,
    MINUTE_BINS,
    load_panel,
    quintile_edges,
    spearman,
    split_mask,
    train_bin_rates,
)


def bucket_table(x, y, edges, trade_ids):
    rows = []
    for lo, hi in edges:
        m = np.isfinite(x) & (x >= lo) & (x < hi)
        n = int(m.sum())
        k = int(y[m].sum()) if n else 0
        p, lo_ci, hi_ci = wilson(k, n)
        n_tr = len({trade_ids[i] for i in np.where(m)[0]}) if n else 0
        rows.append(
            {
                "lo": lo,
                "hi": hi,
                "n_rows": n,
                "n_trades": n_tr,
                "k": k,
                "rate": p,
                "wilson_lo": lo_ci,
                "wilson_hi": hi_ci,
            }
        )
    return rows


def main() -> int:
    d = load_panel()
    tr = split_mask(d["split"], "TRAIN")
    y = d["y"][tr]
    tids = [d["trade_id"][i] for i in np.where(tr)[0]]
    minutes = d["minutes"][tr]
    dist = d["dist40"][tr]
    mom = d["mom5"][tr]
    vol = d["vol5"][tr]
    mae = d["mae"][tr]
    net = d["net_score"][tr]
    arch = [d["archetype"][i] for i in np.where(tr)[0]]

    global_rate = float(y.mean()) if len(y) else None
    min_rates, min_n = train_bin_rates(minutes, y, MINUTE_BINS)
    dist_rates, dist_n = train_bin_rates(dist, y, DIST_BINS)

    tests = {
        "H0_minutes_since_entry": {
            "family": "baseline",
            "buckets": bucket_table(minutes, y, MINUTE_BINS, tids),
            "spearman_mid_vs_rate": spearman(
                [0.5 * (a + b) for a, b in MINUTE_BINS],
                [r if r is not None else np.nan for r in min_rates],
            ),
        },
        "H0b_distance_to_40": {
            "family": "baseline",
            "buckets": bucket_table(dist, y, DIST_BINS, tids),
            "spearman_mid_vs_rate": spearman(
                [0.5 * (a + b) for a, b in DIST_BINS],
                [r if r is not None else np.nan for r in dist_rates],
            ),
        },
    }
    for hid, arr, name in (
        ("H1_momentum_5m", mom, "momentum_5m_cents"),
        ("H2_vol_5m", vol, "vol_5m_cents"),
        ("H3_mae", mae, "mae_since_entry_cents"),
        ("H6_net_score", net, "net_score_since_entry"),
    ):
        edges = quintile_edges(arr)
        if not edges:
            tests[hid] = {"status": "INSUFFICIENT", "feature": name}
            continue
        tests[hid] = {
            "feature": name,
            "buckets": bucket_table(arr, y, edges, tids),
            "spearman_mid_vs_rate": spearman(
                [0.5 * (a + b) for a, b in edges],
                [
                    r["rate"] if r["rate"] is not None else np.nan
                    for r in bucket_table(arr, y, edges, tids)
                ],
            ),
        }

    by_arch = defaultdict(list)
    for a, yi in zip(arch, y):
        by_arch[a or "MISSING"].append(int(yi))
    tests["H7_path_archetype_rule"] = {
        "buckets": {
            k: {
                "n_rows": len(v),
                "k": int(sum(v)),
                "rate": float(np.mean(v)),
            }
            for k, v in sorted(by_arch.items(), key=lambda x: -len(x[1]))
        }
    }

    # H5 velocity
    vel = d["table"].column("velocity_toward_40_cents").to_pylist() if "velocity_toward_40_cents" in d["table"].column_names else [None] * d["n"]
    vel_tr = np.array(
        [
            float(vel[i]) if vel[i] is not None else np.nan
            for i in np.where(tr)[0]
        ]
    )
    vedges = quintile_edges(vel_tr)
    if vedges:
        tests["H5_velocity_toward_40"] = {
            "buckets": bucket_table(vel_tr, y, vedges, tids),
        }

    # Drawdown
    if "drawdown_from_post_entry_high_cents" in d["table"].column_names:
        dd_all = d["table"].column("drawdown_from_post_entry_high_cents").to_pylist()
        dd = np.array(
            [float(dd_all[i]) if dd_all[i] is not None else np.nan for i in np.where(tr)[0]]
        )
        dedges = quintile_edges(dd)
        if dedges:
            tests["H4_drawdown_from_high"] = {"buckets": bucket_table(dd, y, dedges, tids)}

    # Promote rule: TRAIN only, n_rows>=200, |Δrate| vs global >= 0.02, monotonic |spearman|>=0.6
    promoted = []
    for hid, payload in tests.items():
        bucks = payload.get("buckets")
        if not isinstance(bucks, list):
            continue
        rates = [b["rate"] for b in bucks if b["rate"] is not None and b["n_rows"] >= 200]
        if len(rates) < 3:
            payload["status"] = "INSUFFICIENT_SAMPLE"
            continue
        spread = max(rates) - min(rates)
        sp = payload.get("spearman_mid_vs_rate")
        if spread >= 0.02 and sp is not None and abs(sp) >= 0.6:
            payload["status"] = "TRAIN_SIGNAL"
            promoted.append(hid)
        else:
            payload["status"] = "WEAK_OR_NONMONOTONE"

    write_json(
        OUT / "univariate_results_train.json",
        {
            "written_utc": utc_now(),
            "split": "TRAIN",
            "target": "H_40_5M",
            "n_rows": int(tr.sum()),
            "n_trades": len(set(tids)),
            "unconditional_H5": global_rate,
            "tests": tests,
            "promoted_train": promoted,
            "note": "Promotion is TRAIN discovery only. VAL chooses. OOS verifies once.",
        },
    )

    # Hypothesis ledger update
    ledger_path = SPEC_DIR / "HYPOTHESIS_LEDGER.csv"
    if ledger_path.exists():
        rows = list(csv.DictReader(ledger_path.open()))
        status_map = {
            "H0": tests.get("H0_minutes_since_entry", {}).get("status", "FIT"),
            "H0b": tests.get("H0b_distance_to_40", {}).get("status", "FIT"),
            "H1": tests.get("H1_momentum_5m", {}).get("status"),
            "H2": tests.get("H2_vol_5m", {}).get("status"),
            "H3": tests.get("H3_mae", {}).get("status"),
            "H4": tests.get("H4_drawdown_from_high", {}).get("status"),
            "H5": tests.get("H5_velocity_toward_40", {}).get("status"),
            "H6": tests.get("H6_net_score", {}).get("status"),
            "H7": "TRAIN_DESCRIBED",
        }
        for r in rows:
            hid = r.get("hypothesis_id")
            if hid in status_map and status_map[hid]:
                r["status"] = status_map[hid]
        fieldnames = list(rows[0].keys()) if rows else []
        with ledger_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f"univariate TRAIN rows={int(tr.sum())} promoted={promoted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
