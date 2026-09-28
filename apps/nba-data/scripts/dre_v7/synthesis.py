"""S1–S5 from measurements only. Descriptive tokens. Not V7-A/B/C/D."""

from __future__ import annotations

from . import config as C


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def synthesize(rel_a, rel_b, exposure, shift, stability) -> dict:
    oos_a = ((rel_a.get("by_split") or {}).get("OOS") or {})
    train_a = ((rel_a.get("by_split") or {}).get("TRAIN") or {})
    oos_b = ((rel_b.get("by_split") or {}).get("OOS") or {})
    train_exp = ((exposure.get("by_split") or {}).get("TRAIN") or {})
    oos_exp = ((exposure.get("by_split") or {}).get("OOS") or {})
    oos_shift = ((shift.get("by_split") or {}).get("OOS") or {})
    train_shift = ((shift.get("by_split") or {}).get("TRAIN") or {})
    oos_stab = ((stability.get("by_split") or {}).get("OOS") or {})
    train_stab = ((stability.get("by_split") or {}).get("TRAIN") or {})

    spear_a_oos = _num((oos_a.get("overall") or {}).get("spearman_abs_da_vs_unique_trades"))
    spear_a_tr = _num((train_a.get("overall") or {}).get("spearman_abs_da_vs_unique_trades"))
    ext = oos_b.get("abs_ge_5") or {}
    base = oos_b.get("baseline_abs_lt_1") or {}
    med_ext = _num(ext.get("median_TRAIN_unique_trades"))
    med_base = _num(base.get("median_TRAIN_unique_trades"))

    s1 = bool(
        (spear_a_oos is not None and spear_a_oos < 0)
        or (med_ext is not None and med_base is not None and med_ext < med_base)
    )
    # S2: occupancy inflation — TRAIN cells implied via extreme median rows/trade
    rows_pt = _num(ext.get("median_rows_per_trade"))
    n_eff = _num(ext.get("median_N_EFF_TRADE"))
    s2 = bool(rows_pt is not None and rows_pt >= 10 and n_eff is not None and med_ext is not None and n_eff + 1e-9 < med_ext)
    rare_oos = ((oos_shift.get("rare_cell_row_share_by_stratum") or {}).get("2-4") or 0) + (
        (oos_shift.get("rare_cell_row_share_by_stratum") or {}).get("1") or 0
    ) + ((oos_shift.get("rare_cell_row_share_by_stratum") or {}).get("0") or 0)
    rare_tr = ((train_shift.get("rare_cell_row_share_by_stratum") or {}).get("2-4") or 0) + (
        (train_shift.get("rare_cell_row_share_by_stratum") or {}).get("1") or 0
    ) + ((train_shift.get("rare_cell_row_share_by_stratum") or {}).get("0") or 0)
    tv = _num(shift.get("tv_train_oos"))
    s3 = bool((rare_oos > rare_tr + 0.02) or (tv is not None and tv >= 0.15))
    # S4: high-support Spearman more consistent than low-support
    hi = ((oos_stab.get("by_min_support_stratum") or {}).get("20-49") or {})
    lo = ((oos_stab.get("by_min_support_stratum") or {}).get("2-4") or {})
    sp_hi = _num(hi.get("spearman_mean_da_r_bar"))
    sp_lo = _num(lo.get("spearman_mean_da_r_bar"))
    s4 = bool(sp_hi is not None and (sp_lo is None or abs(sp_hi) > abs(sp_lo)))
    well = med_ext is not None and med_ext >= 20
    oos_sp = _num((oos_stab.get("overall") or {}).get("spearman_mean_da_r_bar"))
    tr_sp = _num((train_stab.get("overall") or {}).get("spearman_mean_da_r_bar"))
    s5 = bool(well and oos_sp is not None and tr_sp is not None and (abs(oos_sp) + 0.05 < abs(tr_sp)))

    flags = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5}
    on = [k for k, v in flags.items() if v]
    if len(on) == 0:
        token = "UNRESOLVED"
    elif len(on) == 1:
        token = {
            "S1": "SUPPORT_SPARSE_PATTERN",
            "S2": "SUPPORT_SPARSE_PATTERN",
            "S3": "DISTRIBUTION_SHIFT_PATTERN",
            "S4": "SUPPORT_STABLE_PATTERN",
            "S5": "UNRESOLVED",
        }[on[0]]
    elif set(on) <= {"S1", "S2"}:
        token = "SUPPORT_SPARSE_PATTERN"
    elif set(on) <= {"S3"}:
        token = "DISTRIBUTION_SHIFT_PATTERN"
    elif set(on) <= {"S4"}:
        token = "SUPPORT_STABLE_PATTERN"
    else:
        token = "MIXED_EVIDENCE"

    return {
        "token": token,
        "flags": flags,
        "inputs": {
            "spearman_abs_da_vs_support_TRAIN": spear_a_tr,
            "spearman_abs_da_vs_support_OOS": spear_a_oos,
            "oos_extreme5_median_train_trades": med_ext,
            "oos_baseline_median_train_trades": med_base,
            "oos_extreme5_median_rows_per_trade": rows_pt,
            "oos_extreme5_median_n_eff": n_eff,
            "rare_row_share_train": rare_tr,
            "rare_row_share_oos": rare_oos,
            "tv_train_oos": tv,
            "spearman_r_high_support_oos": sp_hi,
            "spearman_r_low_support_oos": sp_lo,
            "spearman_r_overall_train": tr_sp,
            "spearman_r_overall_oos": oos_sp,
            "exposure_spearman_oos": oos_exp.get("spearman_abs_da_vs_min_support"),
            "exposure_spearman_train": train_exp.get("spearman_abs_da_vs_min_support"),
        },
        "questions": {
            "Q1": "Are large SIR values disproportionately associated with low unique-trade TRAIN support?",
            "Q2": "Does raw possession-row support overstate unique-trade support?",
            "Q3": "Did VAL/OOS encounter more rare or weakly supported cells?",
            "Q4": "Is temporal stability stronger for well-supported cells?",
            "Q5": "Does support plausibly relate to TRAIN→VAL→OOS degradation?",
            "Q6": "If not, what architectural uncertainty remains?",
        },
        "answers_are_structural_only": True,
        "not": ["edge", "M1 is wrong", "exploitable signal", "tradable strategy", "V7-A/B/C/D"],
        "prominent": C.PROMINENT,
        "support_not_independence": C.SUPPORT_NOT_INDEPENDENCE,
        "note": "Descriptive synthesis. Do not force sparsity to be the explanation.",
        "live_deployment": "NOT AUTHORIZED",
    }
