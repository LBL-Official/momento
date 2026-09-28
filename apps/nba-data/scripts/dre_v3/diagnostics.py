"""Q1–Q7 answers and family comparison."""

from __future__ import annotations


def compare_families(interior: dict, temporal: dict, local: dict, contrast: list) -> dict:
    q1 = "NO"
    q2 = "INCONCLUSIVE"
    interiors_oos = {f: (interior.get(f) or {}).get("OOS", {}).get("interior_rate") for f in ("N1", "N2", "N3", "N4")}
    if any((v or 0) >= 0.10 for v in interiors_oos.values()):
        q1 = "YES"
    elif any((v or 0) >= 0.05 for v in interiors_oos.values()):
        q1 = "PARTIAL"
    stabs = [(interior.get(f) or {}).get("stability") for f in ("N1", "N2", "N3", "N4")]
    if any(s == "STABLE" and (interiors_oos.get(f) or 0) >= 0.05 for f, s in zip(("N1", "N2", "N3", "N4"), stabs)):
        q2 = "YES"
    elif any(s == "UNSTABLE" for s in stabs):
        q2 = "NO"
    elif any((v or 0) >= 0.05 for v in interiors_oos.values()):
        q2 = "PARTIAL"

    oos60 = next((c for c in contrast if c.get("split") == "OOS" and c.get("band") == "price_60"), None)
    q3 = "INCONCLUSIVE"
    if oos60:
        e = (oos60.get("early") or {}).get("mean_h_N1")
        l = (oos60.get("late") or {}).get("mean_h_N1")
        if e is not None and l is not None and abs(e - l) >= 0.05:
            q3 = "YES"
        elif e is not None and l is not None:
            q3 = "NO"

    n3_int = interiors_oos.get("N3")
    n1_int = interiors_oos.get("N1")
    q4 = "PARTIAL" if (n3_int is not None and n1_int is not None and abs(n3_int - n1_int) >= 0.05) else "INCONCLUSIVE"

    n4_int = interiors_oos.get("N4")
    q5 = "YES" if (n4_int or 0) >= 0.10 else ("PARTIAL" if (n4_int or 0) >= 0.03 else "NO")

    n1_tmp = ((temporal.get("N1") or {}).get("OOS") or {}).get("median_abs_dh")
    q6 = "INCONCLUSIVE"
    if n1_tmp is not None:
        q6 = "YES" if n1_tmp <= 0.10 else ("PARTIAL" if n1_tmp <= 0.25 else "NO")

    rates = [v for v in interiors_oos.values() if v is not None]
    q7 = "INCONCLUSIVE"
    if len(rates) >= 3:
        q7 = "NO" if max(rates) - min(rates) >= 0.20 else "PARTIAL"

    flip = (local or {}).get("flip_01_rate")
    return {
        "Q1_interior_exist": q1,
        "Q2_oos_stable": q2,
        "Q3_same_price_differs": q3,
        "Q4_recovery_optionality": q4,
        "Q5_nonlinear_downside": q5,
        "Q6_smooth_evolution": q6,
        "Q7_robust_across_families": q7,
        "oos_interior_rates": interiors_oos,
        "local_flip_01_rate": flip,
    }


def overall_verdict(gates: dict, qs: dict, interior: dict) -> dict:
    hard = all(gates[g]["status"] == "PASS" for g in gates)
    oos_int = [((interior.get(f) or {}).get("OOS") or {}).get("interior_rate") or 0 for f in ("N1", "N2", "N3", "N4")]
    stabs = [(interior.get(f) or {}).get("stability") for f in ("N1", "N2", "N3", "N4")]
    if not hard:
        arch = "FAIL"
    elif max(oos_int) < 0.05:
        arch = "FAIL"
    elif any(s == "UNSTABLE" for s in stabs) and max(oos_int) >= 0.10:
        arch = "PARTIAL"
    elif qs["Q1_interior_exist"] == "YES" and qs["Q2_oos_stable"] == "YES" and qs["Q3_same_price_differs"] == "YES":
        arch = "PASS"
    elif qs["Q1_interior_exist"] in ("YES", "PARTIAL"):
        arch = "PARTIAL"
    elif qs["Q7_robust_across_families"] == "NO":
        arch = "INCONCLUSIVE"
    else:
        arch = "INCONCLUSIVE"
    return {
        "ARCHITECTURE": "PASS" if hard else "FAIL",
        "NONLINEAR_OBJECTIVES": arch,
        "INTERIOR_EXPOSURE": "PASS" if qs["Q1_interior_exist"] == "YES" else ("PARTIAL" if max(oos_int) >= 0.03 else "FAIL"),
        "OOS_STABILITY": {"YES": "PASS", "PARTIAL": "PARTIAL", "NO": "FAIL"}.get(qs["Q2_oos_stable"], "INCONCLUSIVE"),
        "RECOVERY_OPTIONALITY": {"YES": "PASS", "PARTIAL": "PARTIAL", "NO": "FAIL"}.get(qs["Q4_recovery_optionality"], "INCONCLUSIVE"),
        "TAIL_RISK_VALUE": {"YES": "PASS", "PARTIAL": "PARTIAL", "NO": "FAIL"}.get(qs["Q5_nonlinear_downside"], "INCONCLUSIVE"),
        "STATE_ASYMMETRY": {"YES": "PASS", "PARTIAL": "PARTIAL", "NO": "FAIL"}.get(qs["Q3_same_price_differs"], "INCONCLUSIVE"),
        "EXECUTION_EVIDENCE": "UNOBSERVED",
        "LIVE_DEPLOYMENT": "NOT AUTHORIZED",
        "HEADLINE": arch,
    }
