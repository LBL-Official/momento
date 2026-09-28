"""Forward candle-path after first |da_state|>=5. DIAGNOSTIC. Forbidden in headline and V6-D."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def measure(state_df: pd.DataFrame, candles: pd.DataFrame, trades: pd.DataFrame | None = None) -> dict:
    first = []
    for tid, g in state_df.sort_values("possession_index").groupby("trade_id", sort=False):
        da = pd.to_numeric(g["da_state"], errors="coerce").to_numpy(float)
        above = np.isfinite(da) & (np.abs(da) >= C.PATH_K)
        if not above.any():
            continue
        i = int(np.flatnonzero(above)[0])
        row = g.iloc[i]
        first.append(
            {
                "trade_id": tid,
                "event_id": row.get("event_id"),
                "dataset_split": row.get("dataset_split"),
                "signal_pidx": row.get("possession_index"),
                "signal_da": float(da[i]),
            }
        )
    sig = pd.DataFrame(first)
    by_split = {}
    if candles is None or candles.empty or sig.empty:
        for split in C.SPLITS:
            by_split[split] = {"n_signals": 0, "label": "CANDLE_PATH_PROXY_NOT_PROVEN_FILL"}
        return {
            "k": C.PATH_K,
            "role": "DIAGNOSTIC_ONLY",
            "forbidden_in": ["headline", "V6-D", "residual_replication", "rank_replication"],
            "by_split": by_split,
            "disclaimer": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
        }

    c = candles.copy()
    c["possession_index"] = pd.to_numeric(c.get("possession_index"), errors="coerce")
    c["A1_yes_bid_cents"] = pd.to_numeric(c.get("A1_yes_bid_cents"), errors="coerce")
    summaries = []
    for r in sig.to_dict("records"):
        sub = c[c["trade_id"] == r["trade_id"]]
        p0 = r.get("signal_pidx")
        if p0 is not None and pd.notna(p0):
            sub = sub[sub["possession_index"].isna() | (sub["possession_index"] >= float(p0))]
        px = sub["A1_yes_bid_cents"].dropna()
        if px.empty:
            continue
        summaries.append(
            {
                "trade_id": r["trade_id"],
                "dataset_split": r["dataset_split"],
                "n_candles_after": int(len(px)),
                "min_p": float(px.min()),
                "last_p": float(px.iloc[-1]),
                "signal_da": r["signal_da"],
            }
        )
    sm = pd.DataFrame(summaries)
    for split in C.SPLITS:
        xs = sm[sm["dataset_split"] == split] if len(sm) else sm
        by_split[split] = {
            "n_signals": int(len(xs)),
            "mean_min_p": float(xs["min_p"].mean()) if len(xs) else None,
            "mean_last_p": float(xs["last_p"].mean()) if len(xs) else None,
            "label": "CANDLE_PATH_PROXY_NOT_PROVEN_FILL",
            "weighting": C.OCCUPANCY_LABEL,
        }
    return {
        "k": C.PATH_K,
        "role": "DIAGNOSTIC_ONLY",
        "forbidden_in": ["headline", "V6-D", "residual_replication", "rank_replication"],
        "by_split": by_split,
        "disclaimer": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
        "note": "Must not enter headline or V6-D.",
    }
