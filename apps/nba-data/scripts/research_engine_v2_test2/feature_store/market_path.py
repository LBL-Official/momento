"""Families F, I — possession-normalized market path and observable market dynamics."""

from __future__ import annotations

from common import POS_WINDOWS, e4_to_cents, mean, stdev


def market_path_features(pre_overlays: list[dict]) -> dict:
    out = {}
    for k in POS_WINDOWS:
        w = pre_overlays[-k:] if pre_overlays else []
        ch = [x.get("market_change_during_cents") for x in w if x.get("market_change_during_cents") is not None]
        rng = [x.get("market_range_during_cents") for x in w if x.get("market_range_during_cents") is not None]
        exact = sum(1 for x in w if x.get("alignment_quality") == "EXACT_ALIGNMENT")
        multi = sum(1 for x in w if x.get("alignment_quality") == "MULTI_POSSESSION_CANDLE")
        signs = [1 if (x or 0) > 0 else (-1 if (x or 0) < 0 else 0) for x in ch]
        rev = sum(1 for a, b in zip(signs, signs[1:]) if a and b and a != b)
        persist = sum(1 for a, b in zip(signs, signs[1:]) if a and a == b)
        v = mean(ch)
        v_prev = mean(ch[:- max(1, k // 2)]) if len(ch) >= 4 else None
        out[f"mkt_change_{k}p"] = None if not ch else sum(ch)
        out[f"mkt_abs_move_{k}p"] = None if not ch else sum(abs(x) for x in ch)
        out[f"mkt_range_mean_{k}p"] = mean(rng)
        out[f"mkt_reversals_{k}p"] = rev
        out[f"mkt_persist_{k}p"] = persist
        out[f"mkt_exact_share_{k}p"] = (exact / len(w)) if w else None
        out[f"mkt_multiposs_share_{k}p"] = (multi / len(w)) if w else None
        out[f"mkt_momentum_{k}p"] = v
        out[f"mkt_accel_{k}p"] = None if v is None or v_prev is None else v - v_prev
        out[f"mkt_instability_{k}p"] = (rev / max(1, len(ch) - 1)) if ch else None
    out["mkt_dynamics_label"] = "OBSERVABLE_MARKET_DYNAMICS"
    out["mkt_not_l2"] = True
    return out
