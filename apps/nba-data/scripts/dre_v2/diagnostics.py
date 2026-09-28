"""Unresolved preservation, remaining-possession ablation, exclusions."""

from __future__ import annotations

from collections import Counter

import numpy as np

from .models import pick


UNMATCHED_FIRST80 = [
    "KXNBAGAME-26JAN24GSWMIN",
    "KXNBAGAME-26APR14MIACHA",
    "KXNBAGAME-26APR14PORPHX",
    "KXNBAGAME-26APR15GSWLAC",
    "KXNBAGAME-26APR15ORLPHI",
    "KXNBAGAME-26APR17CHAORL",
    "KXNBAGAME-26APR17GSWPHX",
]


def unresolved_report(trades: list[dict], panel: list[dict]) -> dict:
    import json

    from . import config as C

    crosswalk_path = C.WAREHOUSE / "normalized" / "nba" / "pbp" / "game_crosswalk.json"
    cw_rows = json.loads(crosswalk_path.read_text()) if crosswalk_path.exists() else []
    cw = {r["event_id"]: r for r in cw_rows if isinstance(r, dict)}
    panel_events = {r["event_id"] for r in panel}
    panel_trades = {r["trade_id"] for r in panel}
    missing = []
    unmatched = set(UNMATCHED_FIRST80)
    for t in trades:
        eid = t.get("event_id")
        tid = t.get("ticker")
        if eid in panel_events or tid in panel_trades:
            continue
        rec = cw.get(eid) or {}
        nba_id = t.get("nba_game_id") or rec.get("nba_game_id")
        match_status = t.get("match_status") or rec.get("match_status")
        if eid in unmatched or match_status == "UNMATCHED" or not nba_id:
            reason = "UNMATCHED_NO_NBA_ID"
        else:
            reason = "MATCHED_BUT_NO_PADE_PANEL"
        missing.append(
            {
                "event_id": eid,
                "ticker": tid,
                "nba_game_id": nba_id,
                "match_status": match_status,
                "dataset_split": t.get("dataset_split"),
                "reason": reason,
            }
        )

    return {
        "gate": "F",
        "status": "PASS",
        "universe": len(trades),
        "panel_eligible_trades": len(panel_trades),
        "unresolved_n": len(missing),
        "unresolved": missing,
        "unmatched_known": UNMATCHED_FIRST80,
        "note": "Unresolved trades are reported, not deleted from the universe.",
    }


def remaining_ablation(model_rows) -> dict:
    """WITH estimated remaining (M3) vs WITHOUT (M3_NO_REM)."""
    out = {"targets": {}}
    for target in ("y_settle_yes", "y_rec_ge_10_k5", "y_det_ge_10_end", "y_min_le_50_k5"):
        rec = {}
        for split in ("TRAIN", "VALIDATION", "OOS"):
            rec[split] = {
                "M3_auc": pick(model_rows, "M3", target, split, "auc"),
                "M3_brier": pick(model_rows, "M3", target, split, "brier"),
                "M3_n": pick(model_rows, "M3", target, split, "n"),
                "M3_NO_REM_auc": pick(model_rows, "M3_NO_REM", target, split, "auc"),
                "M3_NO_REM_brier": pick(model_rows, "M3_NO_REM", target, split, "brier"),
                "M3_NO_REM_n": pick(model_rows, "M3_NO_REM", target, split, "n"),
            }
            a = rec[split]["M3_auc"]
            b = rec[split]["M3_NO_REM_auc"]
            rec[split]["d_auc"] = (a - b) if a is not None and b is not None else None
        out["targets"][target] = rec
    oos = out["targets"]["y_settle_yes"]["OOS"]
    d = oos.get("d_auc")
    if d is None:
        verdict = "INCONCLUSIVE"
    elif d > 0.005:
        verdict = "PARTIAL"
    elif d < -0.005:
        verdict = "WARNING"
    else:
        verdict = "INCONCLUSIVE"
    out["settlement_oos_verdict"] = verdict
    out["note"] = (
        "Primary DRE does not revise the PADE remaining-possession model. "
        "This is an ablation of the frozen R2 ESTIMATE only."
    )
    return out


def asymmetry(rows) -> dict:
    """Similar current prices, different clocks / score / possession."""
    def bucket(rows, pred):
        xs = [r for r in rows if pred(r) and r.get("y_settle_yes") is not None]
        if len(xs) < 25:
            return {"n": len(xs)}
        return {
            "n": len(xs),
            "mean_price": _mean(xs, "current_price"),
            "emp_settle": _mean(xs, "y_settle_yes"),
            "emp_rec10_k5": _mean(xs, "y_rec_ge_10_k5"),
            "emp_det10_end": _mean(xs, "y_det_ge_10_end"),
            "emp_min40_end": _mean(xs, "y_min_le_40_end"),
            "mean_p_settle_B0": _mean(xs, "p_settle_B0"),
            "mean_p_settle_M3": _mean(xs, "p_settle_M3"),
            "mean_h_B0_A": _mean(xs, "target_delta_B0_A"),
            "mean_h_M3_A": _mean(xs, "target_delta_M3_A"),
        }

    def around(lo, hi):
        return lambda r: r.get("current_price") is not None and lo <= r["current_price"] < hi

    def early(r):
        rem = r.get("game_seconds_remaining")
        return (r.get("period") or 99) <= 2 and rem is not None and rem >= 1440

    def late(r):
        rem = r.get("game_seconds_remaining")
        return (r.get("period") or 0) >= 4 and rem is not None and rem <= 360

    contrasts = []
    for split in ("TRAIN", "VALIDATION", "OOS", "ALL"):
        xs = rows if split == "ALL" else [r for r in rows if r["dataset_split"] == split]
        for lo, hi, name in ((58, 63, "price_60"), (48, 53, "price_50"), (68, 73, "price_70")):
            base = [r for r in xs if around(lo, hi)(r)]
            contrasts.append(
                {
                    "split": split,
                    "band": name,
                    "price_lo": lo,
                    "price_hi": hi,
                    "early": bucket(base, early),
                    "late": bucket(base, late),
                    "leading": bucket(base, lambda r: (r.get("score_differential_from_A1") or 0) >= 10),
                    "trailing": bucket(base, lambda r: (r.get("score_differential_from_A1") or 0) <= -10),
                    "offense": bucket(base, lambda r: r.get("is_A1_team_offense") is True),
                    "defense": bucket(base, lambda r: r.get("is_A1_team_offense") is False),
                }
            )

    oos_60 = next((c for c in contrasts if c["split"] == "OOS" and c["band"] == "price_60"), None)
    exists = False
    notes = []
    if oos_60:
        e, l = oos_60["early"], oos_60["late"]
        if e.get("emp_settle") is not None and l.get("emp_settle") is not None:
            gap = abs(e["emp_settle"] - l["emp_settle"])
            notes.append(f"OOS price≈60 early vs late P(settle) gap={gap:.3f}")
            if gap >= 0.08 and e.get("n", 0) >= 40 and l.get("n", 0) >= 40:
                exists = True
        le, tr = oos_60["leading"], oos_60["trailing"]
        if le.get("emp_settle") is not None and tr.get("emp_settle") is not None:
            gap = abs(le["emp_settle"] - tr["emp_settle"])
            notes.append(f"OOS price≈60 lead vs trail P(settle) gap={gap:.3f}")
            if gap >= 0.08 and le.get("n", 0) >= 40 and tr.get("n", 0) >= 40:
                exists = True

    return {
        "contrasts": contrasts,
        "asymmetry_exists_oos": exists,
        "notes": notes,
        "rule": "Same price band, different game/possession/score state.",
        "label": "CANDLE PATH ≠ ACTUAL FILL",
    }


def _mean(rows, key):
    vs = [r.get(key) for r in rows if r.get(key) is not None]
    if not vs:
        return None
    return float(np.mean(np.asarray(vs, dtype=float)))


def alignment_mix(rows) -> dict:
    c = Counter(r.get("alignment_confidence") for r in rows)
    return dict(c)
