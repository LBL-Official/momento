"""Forward labels from future possessions only. Never used as features.

Clock horizons use elapsed_game_seconds (monotonic). Remaining clock increases
in 58/1221 trades and is not used as a horizon constructor.
First-hit order at candle resolution: same-possession dual hit → AMBIGUOUS.
Missing transitions are censored (NaN), not zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def attach_walk_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    n = len(out)
    # possession-horizon objects already on PADE; normalize names
    for hz, tag in (("1", "1"), ("3", "3"), ("5", "5"), ("10", "10"), ("end", "end")):
        fmin = out[f"future_min_{hz}"] if f"{'future_min_' + hz}" in out.columns else out.get(f"future_min_{tag}")
        fmax = out[f"future_max_{hz}"]
        cur = out["current_price"]
        valid = fmin.notna() & fmax.notna() & cur.notna()
        out[f"path_valid_{hz}"] = valid
        out[f"dd_{hz}"] = np.where(valid, np.maximum(0.0, cur - fmin), np.nan)
        out[f"ue_{hz}"] = np.where(valid, np.maximum(0.0, fmax - cur), np.nan)
        out[f"y_rec5_{hz}"] = np.where(valid, (fmax >= cur + 5).astype(float), np.nan)
        out[f"y_rec10_{hz}"] = np.where(valid, (fmax >= cur + 10).astype(float), np.nan)
        out[f"y_rec20_{hz}"] = np.where(valid, (fmax >= cur + 20).astype(float), np.nan)
        out[f"y_det5_{hz}"] = np.where(valid, (fmin <= cur - 5).astype(float), np.nan)
        out[f"y_det10_{hz}"] = np.where(valid, (fmin <= cur - 10).astype(float), np.nan)
        out[f"y_det20_{hz}"] = np.where(valid, (fmin <= cur - 20).astype(float), np.nan)

    # walk each trade for ΔP at horizon, first-hit order, clock horizons, time-to-event
    order = ["clock_hit_60", "clock_hit_180", "clock_hit_300"]
    extras = {
        "dP_1": np.full(n, np.nan),
        "dP_3": np.full(n, np.nan),
        "dP_5": np.full(n, np.nan),
        "dP_10": np.full(n, np.nan),
        "dP_end": np.full(n, np.nan),
        "order_10_5": np.array(["INSUFFICIENT"] * n, dtype=object),
        "poss_to_det10": np.full(n, np.nan),
        "poss_to_rec10": np.full(n, np.nan),
        "wall_to_det10": np.full(n, np.nan),
        "wall_to_rec10": np.full(n, np.nan),
        "censored_det10": np.ones(n, dtype=bool),
        "censored_rec10": np.ones(n, dtype=bool),
    }
    for sec in C.CLOCK_HORIZONS:
        extras[f"path_valid_c{sec}"] = np.zeros(n, dtype=bool)
        extras[f"dd_c{sec}"] = np.full(n, np.nan)
        extras[f"ue_c{sec}"] = np.full(n, np.nan)
        extras[f"dP_c{sec}"] = np.full(n, np.nan)
        extras[f"y_det10_c{sec}"] = np.full(n, np.nan)
        extras[f"y_rec10_c{sec}"] = np.full(n, np.nan)

    idx_arr = np.arange(n)
    out["_i"] = idx_arr
    for _, g in out.groupby("trade_id", sort=False):
        g = g.sort_values("possession_index")
        ii = g["_i"].to_numpy()
        px = g["current_price"].to_numpy(float)
        el = g["elapsed_game_seconds"].to_numpy(float)
        wall = g["market_observation_timestamp"].to_numpy(float)
        m = len(g)
        last = px[-1]
        for k, i in enumerate(range(m)):
            gi = ii[k]
            extras["dP_end"][gi] = last - px[k]
            for hname, h in (("1", 1), ("3", 3), ("5", 5), ("10", 10)):
                j = min(k + h, m - 1)
                if j > k:
                    extras[f"dP_{hname}"][gi] = px[j] - px[k]
            # first-hit 10¢
            rec_k = det_k = None
            for t in range(k + 1, m):
                if det_k is None and px[t] <= px[k] - 10:
                    det_k = t
                if rec_k is None and px[t] >= px[k] + 10:
                    rec_k = t
                if det_k is not None and rec_k is not None:
                    break
            if det_k is None and rec_k is None:
                extras["order_10_5"][gi] = "NEITHER" if k < m - 1 else "INSUFFICIENT"
            elif det_k is not None and rec_k is not None and det_k == rec_k:
                extras["order_10_5"][gi] = "AMBIGUOUS"
            elif det_k is not None and (rec_k is None or det_k < rec_k):
                extras["order_10_5"][gi] = "DOWN_FIRST"
            elif rec_k is not None:
                extras["order_10_5"][gi] = "UP_FIRST"
            if det_k is not None:
                extras["poss_to_det10"][gi] = float(det_k - k)
                extras["wall_to_det10"][gi] = float(wall[det_k] - wall[k])
                extras["censored_det10"][gi] = False
            if rec_k is not None:
                extras["poss_to_rec10"][gi] = float(rec_k - k)
                extras["wall_to_rec10"][gi] = float(wall[rec_k] - wall[k])
                extras["censored_rec10"][gi] = False
            # clock horizons via elapsed
            for sec in C.CLOCK_HORIZONS:
                tgt = el[k] + sec
                hit = None
                for t in range(k + 1, m):
                    if el[t] >= tgt:
                        hit = t
                        break
                if hit is None:
                    continue
                sl = px[k + 1 : hit + 1]
                extras[f"path_valid_c{sec}"][gi] = True
                extras[f"dd_c{sec}"][gi] = float(max(0.0, px[k] - sl.min()))
                extras[f"ue_c{sec}"][gi] = float(max(0.0, sl.max() - px[k]))
                extras[f"dP_c{sec}"][gi] = float(px[hit] - px[k])
                extras[f"y_det10_c{sec}"][gi] = float(sl.min() <= px[k] - 10)
                extras[f"y_rec10_c{sec}"][gi] = float(sl.max() >= px[k] + 10)
    out.drop(columns=["_i"], inplace=True)
    for k, v in extras.items():
        out[k] = v
    out["clock_horizon_basis"] = "elapsed_game_seconds"
    out["clock_horizon_note"] = "Remaining clock not used: increases in 58/1221 trades."
    return out


def attach_path_classes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for hz in C.POSS_HORIZONS:
        cls = []
        for valid, dd, ue, order in zip(
            out[f"path_valid_{hz}"].to_numpy(),
            out[f"dd_{hz}"].to_numpy(),
            out[f"ue_{hz}"].to_numpy(),
            out["order_10_5"].to_numpy() if hz in ("5", "end") else ["NEITHER"] * len(out),
        ):
            if not valid:
                cls.append("INSUFFICIENT_FORWARD_OBSERVATION")
            elif hz in ("5", "end") and order == "AMBIGUOUS" and (dd >= 10 and ue >= 10):
                cls.append("AMBIGUOUS_CANDLE_ORDER")
            elif dd >= 20:
                cls.append("SEVERE_DETERIORATION")
            elif dd >= 10:
                cls.append("MODERATE_DETERIORATION")
            elif ue >= 20:
                cls.append("STRONG_RECOVERY_FIRST")
            elif ue >= 10:
                cls.append("MODERATE_RECOVERY")
            else:
                cls.append("STABLE_RANGE")
        out[f"path_class_{hz}"] = cls
    return out


def path_norm_check(df: pd.DataFrame) -> dict:
    rec = {}
    fails = []
    for hz in C.POSS_HORIZONS:
        vc = df[f"path_class_{hz}"].value_counts(dropna=False)
        n = int(vc.sum())
        rates = {c: float(vc.get(c, 0) / n) if n else None for c in C.PATH_CLASSES}
        sm = sum(v or 0 for v in rates.values())
        ok = abs(sm - 1.0) < 1e-9
        rec[hz] = {"n": n, "rates": rates, "sum": sm, "normalized": ok}
        if not ok:
            fails.append(hz)
    return {"gate": "I", "status": "PASS" if not fails else "FAIL", "horizons": rec, "fails": fails}
