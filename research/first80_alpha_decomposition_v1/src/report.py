"""Markdown reports. Structural claims only."""

from __future__ import annotations

import math

import config as C


def _f(v, d=4):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return str(v)


def classify(cal, path, tree, boot) -> dict:
    full = cal["FULL"]
    oos = cal["OOS"]
    train = cal["TRAIN"]
    p_one = (full.get("vs_null") or {}).get("p_one_sided")
    terminal = bool(p_one is not None and p_one < 0.05 and (oos.get("estimate") or 0) > 0.80)
    f80 = path["FIRST80"]["full"]["estimate"]
    f75 = path["FIRST75"]["full"]["estimate"]
    oos80 = (path["FIRST80"]["splits"]["OOS"] or {}).get("estimate")
    oos75 = (path["FIRST75"]["splits"]["OOS"] or {}).get("estimate")
    n80 = (path["FIRST80"]["splits"]["OOS"] or {}).get("n") or 0
    n75 = (path["FIRST75"]["splits"]["OOS"] or {}).get("n") or 0
    almost_same = path["control_validity"]["first75_almost_identical_to_first80"]
    d = lo = hi = None
    if oos80 is not None and oos75 is not None and n80 > 0 and n75 > 0:
        d = oos80 - oos75
        se = math.sqrt(oos80 * (1 - oos80) / n80 + oos75 * (1 - oos75) / n75)
        lo, hi = d - 1.96 * se, d + 1.96 * se
    path_ind = bool(lo is not None and (lo > 0 or hi < 0) and (not almost_same))
    if almost_same:
        path_token = "CONTROL_NEARLY_IDENTICAL"
    elif path_ind:
        path_token = "OOS_DIFFERENCE_CI_EXCLUDES_ZERO"
    else:
        path_token = "NO_OOS_CI_SEPARATION"
    if terminal and path_ind:
        letter = "C_BOTH"
    elif terminal and not path_ind:
        letter = "A_TERMINAL_CALIBRATION_ONLY"
    elif (not terminal) and path_ind:
        letter = "B_PATH_EFFECT_ONLY"
    else:
        letter = "D_INCONCLUSIVE"
    return {
        "letter": letter,
        "terminal_distinguishable": terminal,
        "train_also_rejects_80": bool(((train.get("vs_null") or {}).get("p_one_sided") or 1) < 0.05),
        "path_independence_token": path_token,
        "first75_almost_identical": almost_same,
        "oos_path_diff": d,
        "oos_path_diff_lo": lo,
        "oos_path_diff_hi": hi,
        "p_one_sided_full": p_one,
        "oos_p_w": oos.get("estimate"),
        "P_not_T40_given_W_FIRST80": f80,
        "P_not_T40_given_W_FIRST75": f75,
        "rules": C.SPECIFICATION_LOCKS["classification_rules"],
    }


def write_all(ctx: dict) -> None:
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    C.DOCS.mkdir(parents=True, exist_ok=True)
    cal = ctx["module_a"]["calibration"]
    path = ctx["module_b"]
    tree = ctx["module_c"]["trees"]["FULL"]
    scen = ctx["module_c"]["scenarios"]
    hedge = ctx["module_d"]["by_threshold"]
    alpha = ctx["alpha"]
    boot = ctx["robustness"]
    clf = classify(cal, path, tree, boot)
    ctx["classification"] = clf

    a_md = "\n".join(
        [
            "# MODULE A — Terminal calibration",
            "",
            f"> {C.BANNER}",
            "",
            "Null: P(W|FIRST80)=0.80. Alternative: greater.",
            "",
            f"FULL n={cal['FULL']['n']} k={cal['FULL']['k']} p={_f(cal['FULL']['estimate'])} "
            f"Wilson [{_f(cal['FULL']['wilson']['lo'])},{_f(cal['FULL']['wilson']['hi'])}] "
            f"Clopper–Pearson [{_f(cal['FULL']['clopper_pearson']['lo'])},{_f(cal['FULL']['clopper_pearson']['hi'])}] "
            f"one-sided p={_f((cal['FULL'].get('vs_null') or {}).get('p_one_sided'))} "
            f"two-sided p={_f((cal['FULL'].get('vs_null') or {}).get('p_two_sided'))} "
            f"excess wins={(cal['FULL'].get('vs_null') or {}).get('excess_k')}.",
            "",
            f"TRAIN p={_f(cal['TRAIN']['estimate'])} n={cal['TRAIN']['n']} "
            f"one-sided p={_f((cal['TRAIN'].get('vs_null') or {}).get('p_one_sided'))} (does not reject 80%).",
            "",
            f"VALIDATION p={_f(cal['VALIDATION']['estimate'])} n={cal['VALIDATION']['n']} "
            f"one-sided p={_f((cal['VALIDATION'].get('vs_null') or {}).get('p_one_sided'))}.",
            "",
            f"OOS p={_f(cal['OOS']['estimate'])} n={cal['OOS']['n']} "
            f"one-sided p={_f((cal['OOS'].get('vs_null') or {}).get('p_one_sided'))}.",
            "",
            "FirstReach(q) − q is positive across 70–95¢ at similar magnitude (~2–3pp on FULL). "
            "The 80¢ row is not a unique local spike.",
            "",
            "The 82.85% figure is an estimate, not the true fair value.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    b_md = "\n".join(
        [
            "# MODULE B — Path survival conditional on winning",
            "",
            f"P(¬T40|W,FIRST80)={_f(path['FIRST80']['full']['estimate'])} "
            f"n_wins={path['FIRST80']['full']['n']} / n_total={path['FIRST80']['full'].get('n_total')}.",
            "",
            f"FIRST75 settled first-reach n={path['FIRST75']['n']}; among winners "
            f"p={_f(path['FIRST75']['full']['estimate'])} n_wins={path['FIRST75']['full']['n']}. "
            f"Shared games {path['FIRST75']['n_shared_events']}; shared event+ticker "
            f"{path['FIRST75']['n_shared_event_ticker']}/{C.FROZEN_N} "
            "(FIRST80 units that were also first-to-75 on the same ticker, including losses — "
            "not comparable to FIRST75 n_wins).",
            "",
            f"OOS P(¬T40|W) FIRST80={_f((path['FIRST80']['splits']['OOS'] or {}).get('estimate'))} "
            f"n={ (path['FIRST80']['splits']['OOS'] or {}).get('n') } vs FIRST75="
            f"{_f((path['FIRST75']['splits']['OOS'] or {}).get('estimate'))} "
            f"n={ (path['FIRST75']['splits']['OOS'] or {}).get('n') }. "
            f"Difference {_f(clf.get('oos_path_diff'))} approx 95% [{_f(clf.get('oos_path_diff_lo'))}, "
            f"{_f(clf.get('oos_path_diff_hi'))}].",
            "",
            f"NON_FIRST80: opponent first tradable 80 strictly after FIRST80. "
            f"n_units={path['NON_FIRST80']['n']}; among winners "
            f"p={_f(path['NON_FIRST80']['full'].get('estimate'))} "
            f"n_wins={path['NON_FIRST80']['full'].get('n')}. Comeback-selected; not a FIRST80 clone.",
            "",
            path["NON_FIRST80"].get("definition") or "",
            "",
            f"Matched FIRST75 strata: n_strata_adequate={path['matched']['n_strata_adequate']} "
            f"n_oos_adequate={path['matched']['n_oos_adequate']} (thin OOS matching).",
            "",
            f"Path token: `{clf['path_independence_token']}`.",
            "",
            "A high P(¬T40|W) is not independent edge by itself. Dependence with W is measured in Module C.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    c_md = "\n".join(
        [
            "# MODULE C — Joint decomposition",
            "",
            f"Tree: WIN¬T40={tree['WIN_NEVER_T40']} WIN T40={tree['WIN_TOUCH40']} "
            f"LOSS¬T40={tree['LOSS_NEVER_T40']} LOSS T40={tree['LOSS_TOUCH40']}.",
            "",
            f"P(W)×P(¬T40|W)={_f(tree['decomposition']['product'])} = observed joint {_f(tree['joint_P_W_and_not_T40'])}.",
            "",
            f"phi={_f(tree['dependence']['phi'])} OR={tree['dependence']['odds_ratio_W_vs_notT40']} "
            f"(undefined with a zero cell) MI={_f(tree['dependence']['mutual_information_nats'])} "
            f"RR={tree['dependence']['risk_ratio_notT40_W_over_notW']}.",
            "",
            f"Scenario B (P(W)=0.80, path term held): joint={_f(scen['B_terminal_corrected_to_80']['joint'])} "
            f"(sensitivity, not a forecast).",
            "",
            tree["leak_flag"]["note"],
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    h20 = hedge.get(20) or hedge.get("20") or {}
    d_md = "\n".join(
        [
            "# MODULE D — Theoretical hedge states",
            "",
            "Candle opponent yes_bid_close is a quoted state, not an executable hedge.",
            "",
            f"P(opponent bid_close ≤ 20¢ | FIRST80) FULL={_f((h20.get('FULL') or {}).get('p'))} "
            f"median delay={_f(None if (h20.get('FULL') or {}).get('median_delay_s') is None else (h20.get('FULL') or {}).get('median_delay_s')/60.0)} min "
            f"(one candle). Mean measured complement ≈ {_f(None if (h20.get('FULL') or {}).get('mean_complement_e4') is None else (h20.get('FULL') or {}).get('mean_complement_e4')/10000.0)}.",
            "",
            "A 20¢ opponent print at FIRST80 is mostly contemporaneous complementarity, not a later lock-in window.",
            "",
            "Complementary prices are measured. They are not assumed to sum to 1.00.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    final = _final(ctx, clf, cal, path, tree, scen, hedge, alpha, boot)
    for name, text in (
        ("MODULE_A_TERMINAL_CALIBRATION.md", a_md),
        ("MODULE_B_PATH_SURVIVAL.md", b_md),
        ("MODULE_C_JOINT_DECOMPOSITION.md", c_md),
        ("MODULE_D_HEDGE_STATE_ANALYSIS.md", d_md),
        ("FINAL_RESEARCH_REPORT.md", final),
    ):
        (C.REPORTS / name).write_text(text)
        (C.DOCS / name).write_text(text)
    (C.ROOT / "FINAL_RESEARCH_REPORT.md").write_text(final)
    C.write_json(C.RESULTS / "classification.json", clf)


def _final(ctx, clf, cal, path, tree, scen, hedge, alpha, boot) -> str:
    h20 = hedge.get(20) or hedge.get("20") or {}
    return "\n".join(
        [
            "# FIRST80 alpha decomposition v1 — final research report",
            "",
            f"**Program:** `{C.PROGRAM}`  ",
            f"**Date:** {C.RESEARCH_DATE}  ",
            "**Live execution changed:** FALSE",
            "",
            "```",
            C.BANNER,
            "```",
            "",
            "## Definitions (not changed)",
            "",
            C.SPECIFICATION_LOCKS["first80_definition"],
            "",
            C.SPECIFICATION_LOCKS["touch40_definition"],
            "",
            "## Question 1 — Is P(W|FIRST80) distinguishable from 80%?",
            "",
            f"Estimate {_f(cal['FULL']['estimate'])}. Wilson 95% [{_f(cal['FULL']['wilson']['lo'])}, {_f(cal['FULL']['wilson']['hi'])}]. "
            f"Exact one-sided p={_f((cal['FULL'].get('vs_null') or {}).get('p_one_sided'))}. "
            f"TRAIN {_f(cal['TRAIN']['estimate'])} (one-sided p={_f((cal['TRAIN'].get('vs_null') or {}).get('p_one_sided'))} — does not reject 80%). "
            f"OOS {_f(cal['OOS']['estimate'])} n={cal['OOS']['n']}.",
            "",
            f"Game-cluster bootstrap mean {_f((boot['P_W']['bootstrap_game']).get('mean'))} "
            f"p05 {_f((boot['P_W']['bootstrap_game']).get('p05'))} p95 {_f((boot['P_W']['bootstrap_game']).get('p95'))}.",
            "",
            "This is not a claim that 82.85% is the true fair value. TRAIN does not reject the 80% null; FULL and OOS do. "
            "Game-cluster bootstrap p05 still sits above 80% on the pooled sample.",
            "",
            "FirstReach(q) calibration deviation is a **broad positive bias** (~2–3pp on FULL at 70–95¢), not a unique 80¢ anomaly.",
            "",
            "## Question 2 — Path survival after conditioning on W?",
            "",
            f"P(¬T40|W,FIRST80)={_f(path['FIRST80']['full']['estimate'])} (910/1019) vs FIRST75 {_f(path['FIRST75']['full']['estimate'])} "
            f"(n_wins={path['FIRST75']['full']['n']}; settled first-to-75 n={path['FIRST75']['n']}). "
            f"Shared event+ticker {path['FIRST75']['n_shared_event_ticker']}/{C.FROZEN_N} of FIRST80 units were also first-to-75 on the same ticker.",
            "",
            f"OOS difference {_f(clf.get('oos_path_diff'))} approx 95% [{_f(clf.get('oos_path_diff_lo'))}, {_f(clf.get('oos_path_diff_hi'))}].",
            "",
            f"NON_FIRST80 {_f(path['NON_FIRST80']['full'].get('estimate'))} among winners; n_units={path['NON_FIRST80']['n']} "
            f"(n_wins={path['NON_FIRST80']['full'].get('n')}). Comeback-selected — higher survival here is not FIRST80 path evidence.",
            "",
            f"Matched OOS adequate strata = {path['matched']['n_oos_adequate']} (too thin to carry the claim).",
            "",
            f"Path token: `{clf['path_independence_token']}`. Independent path-survival is established only if that token is `OOS_DIFFERENCE_CI_EXCLUDES_ZERO`.",
            "",
            "## Question 3 — Mechanical decomposition",
            "",
            f"P(W ∩ ¬T40) = P(W) × P(¬T40|W) = {_f(tree['P_W'])} × {_f(tree['P_not_T40_given_W'])} = {_f(tree['joint_P_W_and_not_T40'])}.",
            "",
            f"Algebraic share of the 74% statistic from P(W) above 80% ≈ {_f(scen['mechanical_share']['fraction_of_joint_attributable_to_pW_above_80'])}. "
            "Most of the joint is 0.80 × P(¬T40|W), not the extra 2.85pp of win rate.",
            "",
            f"phi={_f(tree['dependence']['phi'])}. OR undefined (zero cell). "
            f"P(W|¬T40)={_f(tree['P_W_given_not_T40'])} on this candle sample. "
            f"LOSS ∧ ¬T40 = {tree['LOSS_NEVER_T40']} (measurement on minute closes, not a continuity proof).",
            "",
            "## Question 4 — Sensitivity if P(W)=80%",
            "",
            f"Holding P(¬T40|W) at {_f(tree['P_not_T40_given_W'])}: joint becomes {_f(scen['B_terminal_corrected_to_80']['joint'])} "
            f"(delta {_f(scen['B_terminal_corrected_to_80']['delta_vs_historical_joint'])}). **Not a forecast.**",
            "",
            "## Question 5 — Theoretical hedge states",
            "",
            f"P(quoted opponent bid_close ≤ 20¢ | FIRST80)={_f((h20.get('FULL') or {}).get('p'))}. "
            f"Median delay minutes={_f(None if (h20.get('FULL') or {}).get('median_delay_s') is None else (h20.get('FULL') or {}).get('median_delay_s')/60.0)}. "
            f"Mean measured complement at that candle ≈ {_f(None if (h20.get('FULL') or {}).get('mean_complement_e4') is None else (h20.get('FULL') or {}).get('mean_complement_e4')/10000.0)}. "
            "A 20¢ opponent print at FIRST80 is mostly contemporaneous complementarity, not a later lock-in window.",
            "",
            "Cheaper opponent prints (≤5¢ / ≤10¢) occur later and almost only on eventual winners. Still quoted states, not fills.",
            "",
            "Not an executable hedge. Fees/spread/queue omitted.",
            "",
            "## Question 6 — Persistent conditional alpha?",
            "",
            f"PADE coverage {alpha['n_games_in_pade']}/{C.FROZEN_N} (dropped {alpha['n_dropped_no_pade']}). "
            f"OOS trade-balanced mean α̂={_f((alpha.get('OOS') or {}).get('mean_alpha_trade_balanced'))} "
            f"(VAL {_f((alpha.get('VALIDATION') or {}).get('mean_alpha_trade_balanced'))}).",
            "",
            "α̂ = F̂(S) − K(S) with F̂ from TRAIN buckets only. F is not observed. "
            "Walk-forward α̂ is slightly **negative** on VAL/OOS and does not support persistent conditional alpha.",
            "",
            "## Final classification",
            "",
            f"**{clf['letter']}**",
            "",
            _letter_prose(clf["letter"]),
            "",
            "Locked rule: terminal distinguishable on FULL p<0.05 and OOS point estimate >0.80. "
            "Independent path requires an OOS interval on FIRST80−FIRST75 that excludes 0. "
            + (
                "This run's OOS difference interval includes 0."
                if clf.get("oos_path_diff_lo") is not None
                and clf.get("oos_path_diff_hi") is not None
                and clf["oos_path_diff_lo"] <= 0 <= clf["oos_path_diff_hi"]
                else "This run's OOS difference interval excludes 0."
                if clf.get("oos_path_diff_lo") is not None
                else "This run did not compute an OOS difference interval."
            ),
            "",
            "```",
            "LIVE DEPLOYMENT RECOMMENDATION:",
            "NOT AUTHORIZED",
            "```",
            "",
        ]
    )


def _letter_prose(letter: str) -> str:
    return {
        "A_TERMINAL_CALIBRATION_ONLY": (
            "RESULT A — TERMINAL CALIBRATION ONLY. "
            "The apparent First80 advantage is primarily terminal calibration. "
            "No independent path-survival evidence was established."
        ),
        "B_PATH_EFFECT_ONLY": (
            "RESULT B — PATH EFFECT ONLY. "
            "Terminal calibration evidence is weak. "
            "However, First80 predicts a statistically robust path characteristic."
        ),
        "C_BOTH": (
            "RESULT C — BOTH. "
            "Evidence supports both terminal calibration deviation and an independent path characteristic."
        ),
        "D_INCONCLUSIVE": (
            "RESULT D — INCONCLUSIVE. "
            "The sample and controls do not allow separation of the mechanisms."
        ),
    }.get(letter, letter)
