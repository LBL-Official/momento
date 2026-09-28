#!/usr/bin/env python3
"""Model 0 / 0b / 2. Discrete-time hazard. TRAIN fit only."""

from __future__ import annotations

import sys

import numpy as np

from common import OUT, utc_now, write_json
from lib import (
    DIST_BINS,
    MINUTE_BINS,
    MODEL2_COLS,
    add_intercept,
    bin_lookup,
    fit_l2,
    impute_scale,
    load_panel,
    metrics_block,
    split_mask,
    train_bin_rates,
)

def fill_rates(rates, default):
    return [default if r is None else r for r in rates]


def main() -> int:
    d = load_panel()
    tr = split_mask(d["split"], "TRAIN")
    y = d["y"]
    default = float(y[tr].mean()) if tr.any() else 0.0
    min_rates, min_n = train_bin_rates(d["minutes"][tr], y[tr], MINUTE_BINS)
    dist_rates, dist_n = train_bin_rates(d["dist40"][tr], y[tr], DIST_BINS)
    min_rates = fill_rates(min_rates, default)
    dist_rates = fill_rates(dist_rates, default)

    p0 = np.array(
        [bin_lookup(MINUTE_BINS, min_rates, x, default) for x in d["minutes"]],
        dtype=float,
    )
    p0b = np.array(
        [bin_lookup(DIST_BINS, dist_rates, x, default) for x in d["dist40"]],
        dtype=float,
    )

    Xs, med, mean, std = impute_scale(d["X"][tr], fit=True)
    w = fit_l2(add_intercept(Xs), y[tr])
    Xall, _, _, _ = impute_scale(d["X"], medians=med, means=mean, stds=std)
    from common import sigmoid

    p2 = sigmoid(add_intercept(Xall) @ w)

    (OUT / "models" / "model0").mkdir(parents=True, exist_ok=True)
    (OUT / "models" / "logistic").mkdir(parents=True, exist_ok=True)
    write_json(
        OUT / "models" / "model0" / "params.json",
        {
            "written_utc": utc_now(),
            "kind": "unconditional_hazard_by_minutes_since_entry",
            "bins": MINUTE_BINS,
            "rates": min_rates,
            "n": min_n,
            "train_default": default,
        },
    )
    write_json(
        OUT / "models" / "model0" / "distance.json",
        {
            "kind": "hazard_by_distance_to_40",
            "bins": DIST_BINS,
            "rates": dist_rates,
            "n": dist_n,
        },
    )
    write_json(
        OUT / "models" / "logistic" / "params.json",
        {
            "written_utc": utc_now(),
            "kind": "discrete_time_l2_logistic",
            "features": MODEL2_COLS,
            "weights": w.tolist(),
            "medians": med.tolist(),
            "means": mean.tolist(),
            "stds": std.tolist(),
            "note": "Rows are minutes; effective sample is trades. Clustered metrics required.",
        },
    )
    np.savez(
        OUT / "models" / "logistic" / "predictions_cache.npz",
        p0=p0,
        p0b=p0b,
        p2=p2,
    )
    tr_ids = [d["trade_id"][i] for i in np.where(tr)[0]]
    write_json(
        OUT / "models" / "logistic" / "train_metrics.json",
        {
            "model0": metrics_block(y[tr], p0[tr], tr_ids),
            "model0b": metrics_block(y[tr], p0b[tr], tr_ids),
            "model2": metrics_block(y[tr], p2[tr], tr_ids),
        },
    )
    print("fit_hazard model0/0b/2 TRAIN clustered_brier", metrics_block(y[tr], p2[tr], tr_ids)["clustered_brier"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
