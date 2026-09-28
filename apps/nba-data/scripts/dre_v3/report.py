"""DRE V3 research reports from computed artifacts."""

from __future__ import annotations

from . import config as C


def _f(v, d=3):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def write_reports(ctx: dict) -> None:
    main = _main(ctx)
    card = _card(ctx)
    objs = _objectives(ctx)
    verd = _verdict(ctx)
    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V3.md").write_text(main)
    (C.DOCS / "DRE_V3_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V3_EXPOSURE_OBJECTIVES.md").write_text(objs)
    (C.DOCS / "DRE_V3_RESEARCH_VERDICT.md").write_text(verd)
    for name, text in (
        ("MOMENTO_DYNAMIC_RISK_ENGINE_V3.md", main),
        ("DRE_V3_MODEL_CARD.md", card),
        ("DRE_V3_EXPOSURE_OBJECTIVES.md", objs),
        ("DRE_V3_RESEARCH_VERDICT.md", verd),
    ):
        (C.OUT / name).write_text(text)


def _int_row(interior, fam):
    rec = interior.get(fam) or {}
    lines = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        s = rec.get(split) or {}
        lines.append(
            f"| {fam} | {split} | {s.get('n', '—')} | {_f(s.get('mean_h'))} | {_f(s.get('median_h'))} | {_f(s.get('corner_zero'))} | {_f(s.get('corner_one'))} | {_f(s.get('interior_rate'))} |"
        )
    return "\n".join(lines)


def _stab(interior, fam):
    return (interior.get(fam) or {}).get("stability")


def _q3_note(contrast) -> str:
    hit = next((c for c in contrast if c.get("split") == "OOS" and c.get("band") == "price_60"), None)
    if not hit:
        return "Same-price contrast: insufficient OOS 60¢ sample."
    e = hit.get("early") or {}
    l = hit.get("late") or {}
    return (
        f"OOS 60¢ early vs late: emp settle {_f(e.get('emp_settle'))} vs {_f(l.get('emp_settle'))} "
        f"(n={e.get('n')}/{l.get('n')}), but mean theoretical h* N1 "
        f"{_f(e.get('mean_h_N1'))} vs {_f(l.get('mean_h_N1'))}. "
        "The +20/−80 entry-proxy gamble is EV-positive only for p>0.80. "
        "Predictive state asymmetry therefore need not appear as an exposure-policy asymmetry. "
        "PREDICTIVE INFORMATION ≠ THEORETICAL EXPOSURE POLICY."
    )


def _n1_sens_rows(rows):
    if not rows:
        return ["| — | — | — | — | — |"]
    out = []
    for r in rows:
        out.append(
            f"| {r.get('kind')} | {r.get('param')} | {_f(r.get('val_interior'))} | {_f(r.get('oos_interior'))} | {_f(r.get('oos_mean_h'))} |"
        )
    return out


def _pred_line(pred, key):
    rec = pred.get(key) or {}
    extra = rec.get("brier")
    if extra is None:
        extra = rec.get("logloss")
    return f"| {key} | {rec.get('n', '—')} | {_f(rec.get('auc'))} | {_f(extra)} |"


def _main(ctx) -> str:
    v = ctx["verdict"]
    g = ctx["gates"]
    q = ctx["questions"]
    interior = ctx["interior"]
    sel = ctx["selected"]
    counts = ctx["counts"]
    pred = ctx["pred_oos"]
    local = ctx.get("local") or {}
    temporal = ctx.get("temporal") or {}
    loc_over = local.get("overall") or {}
    n1_tmp = (temporal.get("N1") or {}).get("OOS") or {}
    n1 = sel.get("N1") or {}
    n2 = sel.get("N2") or {}
    n3 = sel.get("N3") or {}
    n4 = sel.get("N4") or {}
    rows = [
        "# MOMENTO — Dynamic Risk Engine V3",
        "",
        f"**Program:** `{C.PROGRAM}`",
        f"**Schema:** {C.SCHEMA_VERSION}",
        f"**Date:** {C.RESEARCH_DATE}",
        "**Live execution changed:** FALSE",
        "",
        "```",
        C.BANNER,
        "```",
        "",
        "DRE V2 showed that a linear mark-to-market objective collapses to corner solutions `h=0` or `h=1`. V3 asks whether a **nonlinear** state-conditional valuation of terminal payoff, recovery optionality, and path risk can produce **stable theoretical interior exposure** without assuming fills.",
        "",
        "---",
        "",
        "## 1. Scientific motivation",
        "",
        "V2 optimized (approximately) `h × Value`. A linear objective on `[0,1]` has corner solutions except in degeneracies. That did **not** prove intermediate exposure is useless. It proved the previous math had no interior mechanism.",
        "",
        "## 2. Scope",
        "",
        "Offline research. Does not modify PADE V1, DRE V2, FIRST01, Risk, frozen FIRST-80, hedge engines, or fee models. All prior artifacts are read-only.",
        "",
        "## 3. Frozen inputs",
        "",
        "| Gate | Status |",
        "|------|--------|",
        f"| A PADE integrity | **{(g.get('A') or {}).get('status')}** |",
        f"| B DRE V2 integrity | **{(g.get('B') or {}).get('status')}** |",
        f"| C Frozen universe 1230/910/320/0 | **{(g.get('C') or {}).get('status')}** |",
        f"| Market lookahead | **{(g.get('market') or {}).get('status')}** |",
        f"| Game lookahead | **{(g.get('game') or {}).get('status')}** |",
        f"| Label leakage | **{(g.get('label') or {}).get('status')}** |",
        f"| Split isolation | **{(g.get('split') or {}).get('status')}** |",
        f"| Path-bin normalization | **{(g.get('path_norm') or {}).get('status')}** |",
        "",
        f"Panel: {counts.get('rows')} rows / {counts.get('trades')} trades. Path-valid to end: {counts.get('path_valid_end')}. Invalid (typically last possession): {counts.get('path_invalid_end')}.",
        "",
        "## 4. Accounting basis",
        "",
        "Theoretical retained exposure `h` scales residual directional size of the original YES contract.",
        "",
        "```",
        "W(h) = W0 + h × X_terminal",
        "X_terminal = +20¢ if settle YES, −80¢ if settle NO",
        "W0 = 5000¢ ($50 experimental bankroll snapshot)",
        "```",
        "",
        "This does **not** assume `(1−h)` can be sold at the current bid. `h=0` is not a liquidation. `h=0.5` is not a hedge.",
        "",
        "## 5. Path distribution",
        "",
        "Exclusive downside-first bins on the observed candle path (5 / 10 / end). If a path both drops ≥10¢ and later recovers ≥10¢, it is classified as downside. `Σ P(bins) = 1` is gated. Jump-through remains `CANDLE_PATH_PROXY`.",
        "",
        "## 6. Predictive information (not a policy)",
        "",
        "OOS (selected):",
        "",
        "| Model | n | AUC | Brier / logloss |",
        "|-------|--:|----:|----------------:|",
        _pred_line(pred, "p_terminal"),
        _pred_line(pred, "p_terminal_v3"),
        _pred_line(pred, "p_rec10_end"),
        _pred_line(pred, "p_rec30_end"),
        _pred_line(pred, "p_det10_end"),
        _pred_line(pred, "path_end"),
        "",
        "Primary `p_terminal` is inherited frozen DRE V2 `p_settle_M3`. `p_terminal_v3` is a V3 as-of logit diagnostic. A good recovery model does **not** imply a good exposure policy.",
        "",
        "Hyperparameters are selected on VALIDATION by realized CRRA γ=2 of the implied `h*`. Raw utilities are not compared across γ. Cents are not compared to utils.",
        "",
        "## 7. Theoretical exposure policy",
        "",
        "Hyperparameters selected on VALIDATION only.",
        "",
        "| Family | Selection |",
        "|--------|-----------|",
        f"| N1 EU | {n1.get('kind')} param={n1.get('param')} |",
        f"| N2 tail | kind={n2.get('kind')} q={n2.get('q')} λ={n2.get('lam')} |",
        f"| N3 recovery | λ_R={n3.get('lam_r')} λ_D={n3.get('lam_d')} |",
        f"| N4 asymmetric | p={n4.get('p')} a={n4.get('a')} b={n4.get('b')} |",
        "",
        "Baselines: E0 `h=1`, E1 `h=0`, E2 frozen DRE V2 `target_delta_M3_A`, E3 VAL-selected constant `h` per 5¢ price bin.",
        "",
        "## 8. Interior solutions",
        "",
        "| Family | Split | n | mean h | median h | P(h=0) | P(h=1) | Interior |",
        "|--------|-------|--:|-------:|---------:|-------:|-------:|---------:|",
        _int_row(interior, "N1"),
        _int_row(interior, "N2"),
        _int_row(interior, "N3"),
        _int_row(interior, "N4"),
        _int_row(interior, "N2_LINEAR"),
        _int_row(interior, "E2"),
        _int_row(interior, "E3"),
        "",
        f"Stability flags: N1={_stab(interior, 'N1')} N2={_stab(interior, 'N2')} N3={_stab(interior, 'N3')} N4={_stab(interior, 'N4')}",
        "",
        "## 8b. N1 risk-aversion sensitivity (not a preference recommendation)",
        "",
        "| kind | param | VAL interior | OOS interior | OOS mean h |",
        "|------|------:|-------------:|-------------:|-----------:|",
        *_n1_sens_rows(n1.get("sensitivity") or []),
        "",
        "High-γ CRRA on a $50 snapshot makes the absolute utility surface extremely flat. Rows with a numerically flat objective are not counted as corner solutions.",
        "",
        "## 9. Primary questions",
        "",
        "| Q | Answer |",
        "|---|--------|",
        f"| Q1 Interior exist? | **{q.get('Q1_interior_exist')}** |",
        f"| Q2 OOS stable? | **{q.get('Q2_oos_stable')}** |",
        f"| Q3 Same price, different state? | **{q.get('Q3_same_price_differs')}** |",
        f"| Q4 Recovery optionality? | **{q.get('Q4_recovery_optionality')}** |",
        f"| Q5 Nonlinear downside? | **{q.get('Q5_nonlinear_downside')}** |",
        f"| Q6 Smooth evolution? | **{q.get('Q6_smooth_evolution')}** |",
        f"| Q7 Robust across families? | **{q.get('Q7_robust_across_families')}** |",
        "",
        _q3_note(ctx.get("contrast") or []),
        "",
        "## 10. Local / temporal stability",
        "",
        f"Local N1 (OOS sample): median |Δh*|={_f(loc_over.get('median'))} p90={_f(loc_over.get('p90'))} flip 0↔1={_f(local.get('flip_01_rate'))}",
        "",
        f"Temporal N1 OOS: median |Δh*|={_f(n1_tmp.get('median_abs_dh'))} p90={_f(n1_tmp.get('p90_abs_dh'))} reversals={n1_tmp.get('reversals')}",
        "",
        "No smoothing was applied to the primary `h*` path.",
        "",
        "## 11. Execution limitations",
        "",
        "```",
        "CANDLE PATH ≠ ACTUAL FILL",
        "THEORETICAL EXPOSURE ≠ EXECUTED EXPOSURE",
        "MODELED STATE VALUE ≠ TRADABLE EDGE",
        "```",
        "",
        "Utility parameters are **not** Momento's risk preferences. They are a sensitivity grid.",
        "",
        "## 12. Verdict",
        "",
        "| Item | Result |",
        "|------|--------|",
        f"| ARCHITECTURE | **{v.get('ARCHITECTURE')}** |",
        f"| NONLINEAR OBJECTIVES | **{v.get('NONLINEAR_OBJECTIVES')}** |",
        f"| INTERIOR EXPOSURE | **{v.get('INTERIOR_EXPOSURE')}** |",
        f"| OOS STABILITY | **{v.get('OOS_STABILITY')}** |",
        f"| RECOVERY OPTIONALITY | **{v.get('RECOVERY_OPTIONALITY')}** |",
        f"| TAIL-RISK VALUE | **{v.get('TAIL_RISK_VALUE')}** |",
        f"| STATE ASYMMETRY | **{v.get('STATE_ASYMMETRY')}** |",
        f"| EXECUTION EVIDENCE | **{v.get('EXECUTION_EVIDENCE')}** |",
        f"| LIVE DEPLOYMENT | **{v.get('LIVE_DEPLOYMENT')}** |",
        "",
        f"**Headline (nonlinear-exposure hypothesis):** **{v.get('HEADLINE')}**",
        "",
        "## How to rerun",
        "",
        "```",
        "/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v3.py",
        "```",
        "",
        "Dashboard: `frontend/dre-v3` on http://127.0.0.1:5185/",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(rows)


def _card(ctx) -> str:
    return "\n".join(
        [
            "# DRE V3 — Model Card",
            "",
            f"**Program:** `{C.PROGRAM}`",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "## Intended use",
            "",
            "Offline research into theoretical retained-exposure surfaces under nonlinear objectives.",
            "",
            "Not for order routing, stops, hedges, or live risk.",
            "",
            "## Data",
            "",
            "Frozen FIRST-80 + PADE V1 + DRE V2 predictions. Chronological game-level TRAIN/VAL/OOS.",
            "",
            "## Features",
            "",
            "As-of only: current price, deterioration, market age, period, game clock, score differential, offense flag, possessions since entry.",
            "",
            "## Models",
            "",
            "TRAIN-only logistic / multinomial. Hyperparameters for **objectives** selected on VALIDATION only.",
            "",
            "## Limitations",
            "",
            "Complete-case feature rows. Last-possession path labels absent. Representative bin midpoints, not full continuous path densities. No L2. No fills.",
            "",
            "## Safety",
            "",
            "LIVE DEPLOYMENT: **NOT AUTHORIZED**",
            "",
        ]
    )


def _objectives(ctx) -> str:
    sel = ctx["selected"]
    n1 = sel.get("N1") or {}
    n2 = sel.get("N2") or {}
    n3 = sel.get("N3") or {}
    n4 = sel.get("N4") or {}
    return "\n".join(
        [
            "# DRE V3 — Exposure Objectives",
            "",
            "All objects are **theoretical retained exposure**. They are not executable policies.",
            "",
            "## Accounting",
            "",
            "W(h) = 5000 + h × X cents, X ∈ {+20, −80} from the 80¢ entry proxy. No sale at the current bid is assumed.",
            "",
            "## N1 — Expected utility",
            "",
            "EU(h) = p U(W0+20h) + (1−p) U(W0−80h)",
            "",
            "CRRA γ ∈ {0.5, 1, 2, 3, 5, 10} (log at 1). CARA α per dollar ∈ {0.005, 0.01, 0.02, 0.05}.",
            "",
            "VALIDATION selects the (kind, param) whose h* maximizes realized CRRA γ=2 — not raw U of the candidate utility.",
            "",
            f"Selected: **{n1.get('kind')}** param=**{n1.get('param')}** (VALIDATION).",
            "",
            "## N2 — Tail risk",
            "",
            "CVaR_q of representative candle-path drawdown from exclusive bins.",
            "",
            "- N2_LINEAR = h×E[X] − λ h CVaR — control; still linear → corners expected.",
            "- N2_EU = EU(h) minus a utility-unit penalty for a sure candle-path CVaR hit of size λ h CVaR.",
            "",
            f"Selected: kind=**{n2.get('kind')}** q=**{n2.get('q')}** λ=**{n2.get('lam')}**",
            "",
            "## N3 — Recovery optionality",
            "",
            "Path moments adjust theoretical wealth, then CRRA γ=2 is applied:",
            "",
            "W_yes = W0 + 20h + λ_R h E[UU]",
            "W_no  = W0 − 80h − λ_D h E[DD]",
            "",
            "Bin representatives, not fills. λ_R / λ_D are weights, not premia.",
            "",
            f"Selected λ_R=**{n3.get('lam_r')}** λ_D=**{n3.get('lam_d')}**",
            "",
            "## N4 — Asymmetric power",
            "",
            "h E[X] − a h^p E[DD^p] + b h E[UU], p ∈ {2, 3}.",
            "",
            f"Selected p=**{n4.get('p')}** a=**{n4.get('a')}** b=**{n4.get('b')}**",
            "",
            "## Grid and ties",
            "",
            f"h ∈ {{0.00, 0.05, …, 1.00}}. Near-optimal set within {C.NEAR_OPT_ABS}. Ties preserve higher h. Plateaus are recorded, not hidden.",
            "",
            "## Forbidden language",
            "",
            "These are not optimal exits, hedges, or fills.",
            "",
        ]
    )


def _verdict(ctx) -> str:
    v = ctx["verdict"]
    lines = [
        "# DRE V3 — Research Verdict",
        "",
        f"**Date:** {C.RESEARCH_DATE}",
        "",
        "Allowed tokens: PASS, PARTIAL, INCONCLUSIVE, FAIL, UNOBSERVED, NOT AUTHORIZED.",
        "",
        "| Item | Verdict |",
        "|------|---------|",
    ]
    for k, val in v.items():
        lines.append(f"| {k} | **{val}** |")
    lines += [
        "",
        "Question: does replacing the linear V2 objective with nonlinear state-conditional objectives produce stable, economically interpretable theoretical interior exposure preferences?",
        "",
        f"**Answer: {v.get('HEADLINE')}**",
        "",
        C.BANNER,
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)
