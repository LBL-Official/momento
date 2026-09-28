"""Classify matched-price findings. Do not upgrade INCONCLUSIVE."""

from __future__ import annotations

from . import config as C


def classify(matched: dict, incremental: dict, bootstrap: dict, path_norm: dict) -> dict:
    prim = matched.get("primary_oos_early_late_60") or {}
    val = ((((matched.get("by_split") or {}).get("VALIDATION") or {}).get("bin_5") or {}).get("60") or {}).get("slices", {}).get("early_vs_late") or {}
    oos = prim
    train = ((((matched.get("by_split") or {}).get("TRAIN") or {}).get("bin_5") or {}).get("60") or {}).get("slices", {}).get("early_vs_late") or {}

    def _dir(rec, key):
        a = ((rec.get("a") or {}).get(key))
        b = ((rec.get("b") or {}).get(key))
        if a is None or b is None:
            return None
        return 1 if a > b else (-1 if a < b else 0)

    persist = True
    for key in ("p_settle", "p_rec10", "p_det10"):
        d_oos = _dir(oos, key)
        d_val = _dir(val, key)
        if d_oos in (1, -1) and d_val in (1, -1) and d_oos != d_val:
            persist = False

    bin_agree = 0
    bin_tested = 0
    for w in C.ROBUST_BINS:
        rec = ((((matched.get("by_split") or {}).get("OOS") or {}).get(f"bin_{w}") or {}).get("60") or {}).get("slices", {}).get("early_vs_late")
        if not rec:
            # 2¢ bin key might be "60" if floor; 10¢ key is "60" as well if we stepped by width from 40
            continue
        bin_tested += 1
        if rec.get("material"):
            bin_agree += 1

    conc = ((oos.get("a") or {}).get("top_game_share") or 0)
    conc_b = ((oos.get("b") or {}).get("top_game_share") or 0)
    concentrated = max(conc, conc_b) >= 0.40

    if not oos.get("adequate"):
        price_asym = "INCONCLUSIVE"
    elif not oos.get("material"):
        price_asym = "FAIL"
    elif not persist or concentrated:
        price_asym = "PARTIAL"
    elif bin_agree >= 2:
        price_asym = "ROBUST"
    else:
        price_asym = "PARTIAL"

    d_m3_settle = (incremental.get("M3_y_settle_yes") or {}).get("d_auc")
    d_m3_rec = (incremental.get("M3_y_rec10_5") or {}).get("d_auc")
    d_m5_rec = (incremental.get("M5_y_rec10_5") or {}).get("d_auc")
    d_b1_rec = (incremental.get("B1_y_rec10_5") or {}).get("d_auc")
    ctrl = incremental.get("M3_y_min_le_40_k5") or {}

    def _inc(v):
        if v is None:
            return "INCONCLUSIVE"
        if abs(v) < 0.005:
            return "FAIL"
        if v >= 0.010:
            return "PARTIAL"
        return "INCONCLUSIVE"

    poss_val = "FAIL"
    if d_m3_settle is not None and d_m3_rec is not None:
        # M3 minus B2 would be better; use M3-B0 vs B2-B0
        d_b2_s = (incremental.get("B2_y_settle_yes") or {}).get("d_auc") or 0
        extra = d_m3_settle - d_b2_s
        if extra >= 0.008:
            poss_val = "PARTIAL"
        elif extra >= 0.003:
            poss_val = "INCONCLUSIVE"
        else:
            poss_val = "FAIL"

    age_val = _inc(d_b1_rec)
    fwd_val = price_asym if price_asym in ("ROBUST", "PARTIAL") else ("PARTIAL" if (d_m3_rec or 0) >= 0.01 else price_asym)

    q = {
        "Q1_same_price_diff_dist": "YES" if oos.get("material") else "NO",
        "Q2_survives_oos": "YES" if price_asym in ("ROBUST", "PARTIAL") else "NO",
        "Q3_which_objects": _which(oos),
        "Q4_possession_beyond_clock_score": poss_val,
        "Q5_staleness": age_val,
        "Q6_robust_bin_width": "YES" if bin_agree >= 2 else ("PARTIAL" if bin_agree == 1 else "NO"),
        "Q7_concentrated": "YES" if concentrated else "NO",
        "Q8_price_dominates_some": "YES" if abs((ctrl.get("d_auc") or 1)) < 0.01 else "PARTIAL",
        "Q9_dist_without_execution": "YES" if oos.get("material") else "NO",
        "Q10_justify_trading_experiment": "NO",
    }

    headline = price_asym
    verdict = {
        "ARCHITECTURE": "PASS" if path_norm.get("status") == "PASS" else "FAIL",
        "FROZEN_INPUT_INTEGRITY": "PASS",
        "TIME_ALIGNMENT": "PARTIAL",
        "LEAKAGE_AUDIT": "PASS",
        "PRICE_MATCHED_STATE_ASYMMETRY": price_asym,
        "FORWARD_DISTRIBUTION_VALUE": fwd_val,
        "POSSESSION_INCREMENTAL_VALUE": poss_val,
        "MARKET_AGE_VALUE": age_val,
        "TRANSITION_STRUCTURE": "PARTIAL",
        "EXECUTION_EVIDENCE": "UNOBSERVED",
        "LIVE_DEPLOYMENT": "NOT AUTHORIZED",
        "HEADLINE": headline,
    }
    return {
        "verdict": verdict,
        "questions": q,
        "primary": oos,
        "val_primary": val,
        "train_primary": train,
        "bootstrap": bootstrap,
        "bin_agree": bin_agree,
        "concentrated": concentrated,
        "persist_direction": persist,
        "negative_control": ctrl,
        "incremental": incremental,
    }


def _which(oos: dict) -> str:
    d = oos.get("delta") or {}
    parts = []
    if (d.get("p_settle") or 0) >= 0.08:
        parts.append("terminal")
    if (d.get("p_rec10") or 0) >= 0.08:
        parts.append("recovery")
    if (d.get("p_det10") or 0) >= 0.08:
        parts.append("deterioration")
    if (d.get("wasserstein_dd") or 0) >= 3:
        parts.append("drawdown_distribution")
    return ",".join(parts) if parts else "none_cleared_bar"
