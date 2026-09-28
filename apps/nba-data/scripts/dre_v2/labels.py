"""Forward-label catalog. Labels are evaluation-only. Not features."""

from __future__ import annotations

from . import config as C


LABEL_GROUPS = {
    "downside": [
        "y_min_le_70_k1",
        "y_min_le_60_k1",
        "y_min_le_50_k1",
        "y_min_le_40_k1",
        "y_min_le_30_k1",
        "y_min_le_70_k3",
        "y_min_le_60_k3",
        "y_min_le_50_k3",
        "y_min_le_40_k3",
        "y_min_le_30_k3",
        "y_min_le_70_k5",
        "y_min_le_60_k5",
        "y_min_le_50_k5",
        "y_min_le_40_k5",
        "y_min_le_30_k5",
        "y_min_le_70_k10",
        "y_min_le_60_k10",
        "y_min_le_50_k10",
        "y_min_le_40_k10",
        "y_min_le_30_k10",
        "y_min_le_70_end",
        "y_min_le_60_end",
        "y_min_le_50_end",
        "y_min_le_40_end",
        "y_min_le_30_end",
        "y_det_ge_10_k1",
        "y_det_ge_10_k3",
        "y_det_ge_10_k5",
        "y_det_ge_10_k10",
        "y_det_ge_10_end",
    ],
    "recovery": [
        "y_rec_ge_5_k1",
        "y_rec_ge_10_k1",
        "y_rec_ge_20_k1",
        "y_rec_ge_5_k3",
        "y_rec_ge_10_k3",
        "y_rec_ge_20_k3",
        "y_rec_ge_5_k5",
        "y_rec_ge_10_k5",
        "y_rec_ge_20_k5",
        "y_rec_ge_5_k10",
        "y_rec_ge_10_k10",
        "y_rec_ge_20_k10",
        "y_rec_ge_10_end",
        "y_max_ge_entry_k5",
    ],
    "terminal": ["y_settle_yes", "terminal_pnl_hold"],
    "jump_proxy": ["y_jump_40", "y_jump_30", "jump_label_kind"],
}


def catalog() -> dict:
    return {
        "source": "PADE V1 07_forward_labels / panel columns",
        "note": "Labels use future candle-path observations. They are not features.",
        "execution": "CANDLE PATH ≠ ACTUAL FILL",
        "saturated_control": "y_min_le_40_k5 is a CONTROL. PADE B0 AUC ≈ 0.99. Not the DRE headline.",
        "groups": LABEL_GROUPS,
        "horizons": list(C.HORIZONS),
        "downside_thresholds": list(C.DOWN_THRESHOLDS),
        "recovery_thresholds_cents": list(C.RECOVERY_THRESHOLDS_CENTS),
    }


def spotcheck(panel: list[dict], n: int = 8) -> list[dict]:
    """Manual verification samples: future min should be <= current along the path."""
    by_trade = {}
    for r in panel:
        by_trade.setdefault(r["trade_id"], []).append(r)
    checks = []
    # Prefer variety: one early TRAIN, one late OOS, one mid-price, one deteriorated.
    picks = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        cands = [tid for tid, rs in by_trade.items() if rs[0].get("dataset_split") == split]
        cands.sort()
        if cands:
            picks.append(cands[len(cands) // 3])
            picks.append(cands[(2 * len(cands)) // 3])
    for tid in picks[:n]:
        rows = sorted(by_trade[tid], key=lambda x: x.get("possessions_since_entry") or 0)
        mid = rows[len(rows) // 2]
        later = rows[len(rows) // 2 + 1 :]
        fut_min = None
        prices = [r.get("current_price") for r in later if r.get("current_price") is not None]
        if prices:
            fut_min = min(prices)
        label_min5 = mid.get("future_min_5")
        ok_min = True
        if label_min5 is not None and prices:
            window = prices[:5] if len(prices) >= 5 else prices
            ok_min = abs(min(window) - float(label_min5)) < 1e-6 or min(window) == float(label_min5)
        checks.append(
            {
                "trade_id": tid,
                "split": mid.get("dataset_split"),
                "possession_index": mid.get("possession_index"),
                "current_price": mid.get("current_price"),
                "label_future_min_5": label_min5,
                "observed_next5_min": min(prices[:5]) if prices else None,
                "label_y_settle_yes": mid.get("y_settle_yes"),
                "path_future_min_to_end": fut_min,
                "spotcheck_min5_consistent": ok_min,
                "note": "Consistency vs later panel rows. Labels remain PADE-owned.",
            }
        )
    return checks
