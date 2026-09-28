"""MODULE C — joint outcome tree, dependence, sensitivity (not a forecast)."""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
import stats_util as S


def outcome_tree(df: pd.DataFrame) -> dict:
    n = len(df)
    c1 = int(df["win_and_not_T40"].sum())
    c2 = int(df["win_and_T40"].sum())
    c3 = int(df["loss_and_not_T40"].sum())
    c4 = int(df["loss_and_T40"].sum())
    if c1 + c2 + c3 + c4 != n:
        raise RuntimeError("HALT tree does not partition")
    w = int(df["W"].sum())
    t40 = int(df["T40"].sum())
    # contingency: rows W / ~W; cols ~T40 / T40
    a, b, c, d = c1, c2, c3, c4
    tree = {
        "n": n,
        "WIN_NEVER_T40": c1,
        "WIN_TOUCH40": c2,
        "LOSS_NEVER_T40": c3,
        "LOSS_TOUCH40": c4,
        "P_W": w / n,
        "P_not_W": 1 - w / n,
        "P_T40": t40 / n,
        "P_not_T40": (n - t40) / n,
        "P_not_T40_given_W": c1 / w if w else None,
        "P_not_T40_given_not_W": c3 / (n - w) if (n - w) else None,
        "P_W_given_not_T40": c1 / (c1 + c3) if (c1 + c3) else None,
        "P_W_given_T40": c2 / (c2 + c4) if (c2 + c4) else None,
        "joint_P_W_and_not_T40": c1 / n,
        "decomposition": {
            "P_W": w / n,
            "P_not_T40_given_W": c1 / w if w else None,
            "product": (w / n) * (c1 / w) if w else None,
            "observed_joint": c1 / n,
            "identity_holds": True,
        },
        "leak_flag": {
            "LOSS_NEVER_T40_count": c3,
            "note": (
                "Category 3 is logically surprising if prices are continuous. "
                "A count of 0 on this candle sample is an observed measurement, "
                "not a proof that a loser cannot skip 40¢ between minute closes."
            ),
        },
        "dependence": {
            "odds_ratio_W_vs_notT40": S.odds_ratio(a, b, c, d),
            "phi": S.phi_coef(a, b, c, d),
            "mutual_information_nats": S.mutual_information(a, b, c, d),
            "risk_ratio_notT40_W_over_notW": None
            if (n - w) == 0 or c3 / (n - w) == 0
            else (c1 / w) / (c3 / (n - w) if (n - w) else None),
            "table": [[a, b], [c, d]],
            "table_labels": [["W,~T40", "W,T40"], ["~W,~T40", "~W,T40"]],
            "primary_not_pearson": True,
        },
    }
    if tree["dependence"]["risk_ratio_notT40_W_over_notW"] is None and c3 == 0:
        tree["dependence"]["risk_ratio_notT40_W_over_notW"] = "UNDEFINED_ZERO_DENOMINATOR"
        tree["dependence"]["note"] = "All losses touched 40 on close-path candles. RR is undefined."
    return tree


def by_split_tree(df: pd.DataFrame) -> dict:
    out = {"FULL": outcome_tree(df)}
    for s in ("TRAIN", "VALIDATION", "OOS"):
        out[s] = outcome_tree(df[df["dataset_split"] == s])
    return out


def sensitivity() -> pd.DataFrame:
    """Hypothetical. NOT A FORECAST."""
    p_w = np.round(np.linspace(0.70, 0.90, 21), 4)
    p_s = np.round(np.linspace(0.60, 1.00, 21), 4)
    rows = []
    for x in p_w:
        for y in p_s:
            rows.append(
                {
                    "P_W": float(x),
                    "P_not_T40_given_W": float(y),
                    "P_W_and_not_T40": float(x * y),
                    "label": "HYPOTHETICAL SENSITIVITY ANALYSIS — NOT A FORECAST — NOT A TRADING SIGNAL",
                }
            )
    return pd.DataFrame(rows)


def scenarios(tree: dict) -> dict:
    p_w = tree["P_W"]
    p_s = tree["P_not_T40_given_W"]
    return {
        "A_historical": {
            "P_W": p_w,
            "P_not_T40_given_W": p_s,
            "joint": p_w * p_s,
            "note": "Replay of observed product. Not a forecast.",
        },
        "B_terminal_corrected_to_80": {
            "P_W": 0.80,
            "P_not_T40_given_W": p_s,
            "joint": 0.80 * p_s,
            "delta_vs_historical_joint": 0.80 * p_s - p_w * p_s,
            "note": "Sensitivity only. Holds path term fixed. Not a forecast.",
        },
        "mechanical_share": {
            "observed_joint": p_w * p_s,
            "joint_if_pW_80": 0.80 * p_s,
            "fraction_of_joint_attributable_to_pW_above_80": None
            if p_s is None or p_w * p_s == 0
            else ((p_w - 0.80) * p_s) / (p_w * p_s),
            "note": "Algebraic attribution of the product, not a causal claim.",
        },
    }


def run(df: pd.DataFrame) -> dict:
    trees = by_split_tree(df)
    scen = scenarios(trees["FULL"])
    surf = sensitivity()
    C.write_json(C.RESULTS / "joint_outcome_tree.json", {"trees": trees, "scenarios": scen})
    flat = []
    for s, t in trees.items():
        flat.append(
            {
                "split": s,
                "n": t["n"],
                "WIN_NEVER_T40": t["WIN_NEVER_T40"],
                "WIN_TOUCH40": t["WIN_TOUCH40"],
                "LOSS_NEVER_T40": t["LOSS_NEVER_T40"],
                "LOSS_TOUCH40": t["LOSS_TOUCH40"],
                "P_W": t["P_W"],
                "P_T40": t["P_T40"],
                "P_not_T40": t["P_not_T40"],
                "P_not_T40_given_W": t["P_not_T40_given_W"],
                "P_not_T40_given_not_W": t["P_not_T40_given_not_W"],
                "P_W_given_not_T40": t["P_W_given_not_T40"],
                "P_W_given_T40": t["P_W_given_T40"],
                "phi": t["dependence"]["phi"],
                "odds_ratio": t["dependence"]["odds_ratio_W_vs_notT40"],
                "mi": t["dependence"]["mutual_information_nats"],
            }
        )
    C.write_csv(C.RESULTS / "joint_outcome_tree.csv", pd.DataFrame(flat))
    dep = pd.DataFrame(
        [
            {"metric": "phi", "value": trees["FULL"]["dependence"]["phi"]},
            {"metric": "odds_ratio", "value": trees["FULL"]["dependence"]["odds_ratio_W_vs_notT40"]},
            {"metric": "mutual_information_nats", "value": trees["FULL"]["dependence"]["mutual_information_nats"]},
            {"metric": "risk_ratio", "value": trees["FULL"]["dependence"]["risk_ratio_notT40_W_over_notW"]},
        ]
    )
    C.write_csv(C.RESULTS / "dependence_metrics.csv", dep)
    C.write_csv(C.RESULTS / "sensitivity_surface.csv", surf)
    C.write_parquet(C.DATA / "sensitivity_surface.parquet", surf)
    return {"trees": trees, "scenarios": scen, "sensitivity": surf}
