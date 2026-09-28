"""Sole module that classifies V6-A/B/C/D. Consumes frozen measurements only."""

from __future__ import annotations

from . import config as C
from . import replication as R


def classify(dist: dict, conc: dict, rank: dict, residual: dict, persistence: dict) -> dict:
    oos_p5 = ((dist.get("by_split") or {}).get("OOS") or {}).get("TRADE_BALANCED", {}).get("P_abs_ge", {}).get("5")
    oos_top10 = ((conc.get("by_split") or {}).get("OOS") or {}).get("top10_share")
    rank_rep = rank.get("replication") or {}
    res_rep = residual.get("replication") or {}
    rank_spread_oos = ((rank.get("by_split") or {}).get("OOS") or {}).get("spread_hi_minus_lo")
    pers_oos = ((persistence.get("by_split") or {}).get("OOS") or {})
    med_dur = pers_oos.get("median_duration_k5")

    rank_zero = R.zero_compatible(rank.get("bootstrap_oos"))
    res_zero = R.zero_compatible(residual.get("bootstrap_oos"))
    p5_small = oos_p5 is not None and float(oos_p5) < 0.05
    p5_large = oos_p5 is not None and float(oos_p5) >= 0.05
    conc_large = oos_top10 is not None and float(oos_top10) >= C.CONCENTRATION_VERDICT_SHARE
    conc_small = oos_top10 is not None and float(oos_top10) < C.CONCENTRATION_VERDICT_SHARE
    not_concentrated = conc_small or p5_small
    concentrated_geom = conc_large or p5_large
    rank_dir = bool(rank_rep.get("ok"))
    res_dir = bool(res_rep.get("ok"))
    spread_ge5 = rank_spread_oos is not None and abs(float(rank_spread_oos)) >= C.MATERIAL_CENTS
    persist_ok = med_dur is not None and float(med_dur) >= C.PERSISTENCE_MEDIAN_MIN

    a = bool(rank_zero) and bool(res_zero) and p5_small
    b = res_dir and not_concentrated
    c = concentrated_geom and (rank_dir or res_dir)
    d = c and spread_ge5 and rank_dir and res_dir and persist_ok

    flags = {"A": a, "B": b, "C": c, "D": d}
    headline = None
    for tok in C.OOS_REPLICATION_PROTOCOL["headline_priority"]:
        if flags[tok]:
            headline = tok
            break
    if headline is None:
        raise RuntimeError("UNCLASSIFIED_PRE_REGISTERED_OUTCOME")

    names = {
        "A": "No meaningful state information",
        "B": "Statistical state information",
        "C": "Concentrated state information",
        "D": "Potential economic signal",
    }
    return {
        "HEADLINE": headline,
        "name": names[headline],
        "flags": flags,
        "inputs": {
            "oos_P_abs_ge_5": oos_p5,
            "oos_top10_share": oos_top10,
            "rank_ZERO_COMPATIBLE": rank_zero,
            "residual_ZERO_COMPATIBLE": res_zero,
            "rank_replication_ok": rank_dir,
            "residual_replication_ok": res_dir,
            "oos_rank_spread": rank_spread_oos,
            "oos_median_duration_k5": med_dur,
            "concentrated_geom": concentrated_geom,
            "not_concentrated": not_concentrated,
        },
        "note": "TRAIN interestingness is not a discovery. OOS decides A/B/C/D.",
        "d_ceiling": C.OOS_REPLICATION_PROTOCOL["d_ceiling"],
        "concentration_not_evidence": C.CONCENTRATION_NOT_EVIDENCE,
        "live_deployment": "NOT AUTHORIZED",
        "not": ["edge", "executable action", "fill", "tradable strategy"],
    }


def halt_record(dist: dict, conc: dict, rank: dict, residual: dict, persistence: dict) -> dict:
    """Document why A/B/C/D none fired. Not a fifth scientific category."""
    oos_p5 = ((dist.get("by_split") or {}).get("OOS") or {}).get("TRADE_BALANCED", {}).get("P_abs_ge", {}).get("5")
    oos_top10 = ((conc.get("by_split") or {}).get("OOS") or {}).get("top10_share")
    rank_rep = rank.get("replication") or {}
    res_rep = residual.get("replication") or {}
    rank_spread_oos = ((rank.get("by_split") or {}).get("OOS") or {}).get("spread_hi_minus_lo")
    pers_oos = ((persistence.get("by_split") or {}).get("OOS") or {})
    return {
        "HEADLINE": "UNCLASSIFIED_PRE_REGISTERED_OUTCOME",
        "name": "HARD HALT — A/B/C/D none fired. Not a fifth scientific category.",
        "flags": {"A": False, "B": False, "C": False, "D": False},
        "halt": True,
        "verdict_status": "UNCLASSIFIED_PRE_REGISTERED_OUTCOME",
        "inputs": {
            "oos_P_abs_ge_5": oos_p5,
            "oos_top10_share": oos_top10,
            "rank_ZERO_COMPATIBLE": R.zero_compatible(rank.get("bootstrap_oos")),
            "residual_ZERO_COMPATIBLE": R.zero_compatible(residual.get("bootstrap_oos")),
            "rank_replication_token": rank_rep.get("token"),
            "residual_replication_token": res_rep.get("token"),
            "rank_replication_ok": bool(rank_rep.get("ok")),
            "residual_replication_ok": bool(res_rep.get("ok")),
            "oos_rank_spread": rank_spread_oos,
            "oos_rank_n_lo": ((rank.get("by_split") or {}).get("OOS") or {}).get("n_lo"),
            "oos_rank_n_hi": ((rank.get("by_split") or {}).get("OOS") or {}).get("n_hi"),
            "oos_median_duration_k5": pers_oos.get("median_duration_k5"),
            "why_A_false": "requires P(|mean_SIR|>=5¢)<0.05 AND both OOS spreads ZERO_COMPATIBLE",
            "why_B_false": "requires residual replication_directional (adequate coverage on both compared sides)",
            "why_C_false": "requires rank or residual replication_directional; concentration alone is insufficient",
            "why_D_false": "requires C",
        },
        "note": (
            "HARD HALT. The pre-registered taxonomy did not classify this OOS realization. "
            "Do not silently call it A. Do not invent a fifth scientific letter."
        ),
        "d_ceiling": C.OOS_REPLICATION_PROTOCOL["d_ceiling"],
        "concentration_not_evidence": C.CONCENTRATION_NOT_EVIDENCE,
        "live_deployment": "NOT AUTHORIZED",
        "not": ["edge", "executable action", "fill", "tradable strategy", "fifth scientific category"],
    }
