"""DRE V4 research reports from computed artifacts."""

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
    card = _card()
    dist = _dist(ctx)
    verd = _verdict(ctx)
    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V4.md").write_text(main)
    (C.DOCS / "DRE_V4_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V4_STATE_DISTRIBUTION_REPORT.md").write_text(dist)
    (C.DOCS / "DRE_V4_RESEARCH_VERDICT.md").write_text(verd)
    for name, text in (
        ("MOMENTO_DYNAMIC_RISK_ENGINE_V4.md", main),
        ("DRE_V4_MODEL_CARD.md", card),
        ("DRE_V4_STATE_DISTRIBUTION_REPORT.md", dist),
        ("DRE_V4_RESEARCH_VERDICT.md", verd),
    ):
        (C.OUT / name).write_text(text)


def _pstat(rec, side, key):
    return ((rec.get(side) or {}).get(key))


def _main(ctx) -> str:
    v = ctx["disc"]["verdict"]
    q = ctx["disc"]["questions"]
    g = ctx["gates"]
    u = ctx["universe"]
    counts = ctx["counts"]
    prim = ctx["disc"].get("primary") or {}
    dlt = prim.get("delta") or {}
    inc = ctx.get("incremental") or {}
    lines = [
        "# MOMENTO — Dynamic Risk Engine V4",
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
        "DRE V3 showed that forcing predictive state through a theoretical utility function does not produce a meaningful exposure surface. V4 therefore **does not optimize `h*`**. It estimates **forward conditional distributions**.",
        "",
        "```",
        "PREDICTIVE STATE INFORMATION ≠ THEORETICAL EXPOSURE POLICY ≠ EXECUTABLE TRADING POLICY",
        "```",
        "",
        "## 1. Motivation",
        "",
        "Hypothesis: current price does not completely characterize the forward distribution of candle-path movement and terminal outcomes.",
        "",
        "## 2. Scope",
        "",
        "Offline research. No sell/stop/hedge/fill/exposure recommendation. Does not modify PADE, DRE V2, DRE V3, FIRST01, Risk, frozen FIRST-80, hedges, or fee models.",
        "",
        "## 3. Frozen inputs",
        "",
        "| Gate | Status |",
        "|------|--------|",
        f"| A Frozen FIRST-80 | **{(g.get('A') or {}).get('status')}** |",
        f"| B PADE integrity | **{(g.get('B') or {}).get('status')}** |",
        f"| C DRE V2 integrity | **{(g.get('C') or {}).get('status')}** |",
        f"| D DRE V3 integrity | **{(g.get('D') or {}).get('status')}** |",
        f"| E/F/G Leakage | **{(g.get('E') or {}).get('status')}** |",
        f"| H Split isolation | **{(g.get('H') or {}).get('status')}** |",
        f"| I Path normalization | **{(g.get('I') or {}).get('status')}** |",
        f"| J No OOS tuning | **{(g.get('J') or {}).get('status')}** |",
        "",
        "## 4. Universe accounting",
        "",
        f"Universe **{u.get('universe')}**. Panel-eligible **{u.get('panel_eligible')}**. Unresolved **{u.get('unresolved_n')}** (preserved). Panel rows **{counts.get('rows')}**. Path-label-eligible (end) **{u.get('path_label_eligible_end')}**.",
        "",
        "UNRESOLVED ≠ MODEL-ELIGIBLE. Universe is not redefined to 1221.",
        "",
        "## 5. State and three clocks",
        "",
        "One row = FIRST-80 trade × HIGH/MEDIUM PADE possession. Wall clock = `market_observation_timestamp` / `position_age_wall_s`. Game clock = `game_clock` / remaining / elapsed. Possession clock = `possession_index`. They are not collapsed.",
        "",
        "Clock-horizon labels use **elapsed game seconds** because remaining clock increases in 58/1221 trades.",
        "",
        "## 6. Forward labels",
        "",
        "Possession horizons 1/3/5/10/end: ΔP, min, max, DD, UE, recover ≥5/10/20, deteriorate ≥5/10/20, exclusive path class, first 10¢ order (UP_FIRST / DOWN_FIRST / NEITHER / AMBIGUOUS / INSUFFICIENT). Missing hits are censored, not zero. Jump-through remains `CANDLE_PATH_PROXY`.",
        "",
        "## 7. Matched-price experiment (pre-registered)",
        "",
        "Primary: 5¢ bins, band `[60,65)`, early vs late, 5-possession horizon. Minimum 50 rows and 15 trades. Robustness: 2¢, 10¢, NN ±1¢.",
        "",
        f"OOS primary early vs late: n={_pstat(prim,'a','n')}/{_pstat(prim,'b','n')} trades={_pstat(prim,'a','trades')}/{_pstat(prim,'b','trades')} "
        f"P(settle) {_f(_pstat(prim,'a','p_settle'))} vs {_f(_pstat(prim,'b','p_settle'))} "
        f"P(rec≥10) {_f(_pstat(prim,'a','p_rec10'))} vs {_f(_pstat(prim,'b','p_rec10'))} "
        f"P(det≥10) {_f(_pstat(prim,'a','p_det10'))} vs {_f(_pstat(prim,'b','p_det10'))} "
        f"median DD {_f((prim.get('a') or {}).get('dd',{}).get('median'))} vs {_f((prim.get('b') or {}).get('dd',{}).get('median'))} "
        f"Wasserstein DD {_f(dlt.get('wasserstein_dd'))}. material={prim.get('material')} adequate={prim.get('adequate')}.",
        "",
        "RESEARCH DISTRIBUTION — NOT A TRADING INSTRUCTION.",
        "",
        "## 8. Nested models",
        "",
        "B0 price-only → B1 market quality → B2 game state → M3 multi-clock → M4 path state → M5 dynamics. TRAIN fit. C=1.0 pre-registered. Incremental OOS vs B0 is reported but is **not** the discovery bar.",
        "",
        f"OOS ΔAUC M3 settle={_f((inc.get('M3_y_settle_yes') or {}).get('d_auc'))} rec10_5={_f((inc.get('M3_y_rec10_5') or {}).get('d_auc'))} det10_5={_f((inc.get('M3_y_det10_5') or {}).get('d_auc'))} min≤40 k5 (control)={_f((inc.get('M3_y_min_le_40_k5') or {}).get('d_auc'))}.",
        "",
        "## 9. Questions",
        "",
        "| Q | Answer |",
        "|---|--------|",
        f"| Q1 Same-price different distributions? | **{q.get('Q1_same_price_diff_dist')}** |",
        f"| Q2 Survives OOS? | **{q.get('Q2_survives_oos')}** |",
        f"| Q3 Which objects? | **{q.get('Q3_which_objects')}** |",
        f"| Q4 Possession beyond clock/score? | **{q.get('Q4_possession_beyond_clock_score')}** |",
        f"| Q5 Staleness? | **{q.get('Q5_staleness')}** |",
        f"| Q6 Robust to bin width? | **{q.get('Q6_robust_bin_width')}** |",
        f"| Q7 Concentrated in few games? | **{q.get('Q7_concentrated')}** |",
        f"| Q8 Price dominates some objects? | **{q.get('Q8_price_dominates_some')}** |",
        f"| Q9 Dist. difference without execution assumption? | **{q.get('Q9_dist_without_execution')}** |",
        f"| Q10 Justify a trading experiment? | **{q.get('Q10_justify_trading_experiment')}** |",
        "",
        "## 10. Limitations",
        "",
        "One-minute candles. Repeated candles are observed outcomes, not independent updates. First-hit order is AMBIGUOUS when both thresholds occur on the same possession. Clock horizons use elapsed time. Rows within a trade are clustered; bootstrap is game-level. No L2. No fills.",
        "",
        "## 11. Verdict",
        "",
        "| Item | Result |",
        "|------|--------|",
        f"| ARCHITECTURE | **{v.get('ARCHITECTURE')}** |",
        f"| FROZEN INPUT INTEGRITY | **{v.get('FROZEN_INPUT_INTEGRITY')}** |",
        f"| TIME ALIGNMENT | **{v.get('TIME_ALIGNMENT')}** |",
        f"| LEAKAGE AUDIT | **{v.get('LEAKAGE_AUDIT')}** |",
        f"| PRICE-MATCHED STATE ASYMMETRY | **{v.get('PRICE_MATCHED_STATE_ASYMMETRY')}** |",
        f"| FORWARD DISTRIBUTION VALUE | **{v.get('FORWARD_DISTRIBUTION_VALUE')}** |",
        f"| POSSESSION INCREMENTAL VALUE | **{v.get('POSSESSION_INCREMENTAL_VALUE')}** |",
        f"| MARKET-AGE VALUE | **{v.get('MARKET_AGE_VALUE')}** |",
        f"| TRANSITION STRUCTURE | **{v.get('TRANSITION_STRUCTURE')}** |",
        f"| EXECUTION EVIDENCE | **{v.get('EXECUTION_EVIDENCE')}** |",
        f"| LIVE DEPLOYMENT | **{v.get('LIVE_DEPLOYMENT')}** |",
        "",
        f"**Headline:** **{v.get('HEADLINE')}**",
        "",
        "## How to rerun",
        "",
        "```",
        "/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v4.py",
        "```",
        "",
        "Dashboard: `frontend/dre-v4` on http://127.0.0.1:5186/",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)


def _card() -> str:
    return "\n".join(
        [
            "# DRE V4 — Model Card",
            "",
            f"**Program:** `{C.PROGRAM}`",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "## Intended use",
            "",
            "Offline research into state-conditional forward candle-path distributions.",
            "",
            "Not for order routing, stops, hedges, exposure, or live risk.",
            "",
            "## Data",
            "",
            "Frozen FIRST-80 + PADE V1 panel + DRE V2 comparison probabilities. Chronological game-level TRAIN/VAL/OOS.",
            "",
            "## Features",
            "",
            "Nested B0–M5 as-of families. No future labels. No `h*`. No `target_delta`.",
            "",
            "## Limitations",
            "",
            "Candle resolution. Clustered rows. Elapsed-time clock horizons. Last-possession path labels absent.",
            "",
            "## Safety",
            "",
            "LIVE DEPLOYMENT: **NOT AUTHORIZED**",
            "",
        ]
    )


def _dist(ctx) -> str:
    prim = ctx["disc"].get("primary") or {}
    return "\n".join(
        [
            "# DRE V4 — State Distribution Report",
            "",
            "Primary pre-registered contrast: 5¢ bin `[60,65)`, early vs late, 5-possession horizon.",
            "",
            f"Adequate: {prim.get('adequate')} Material: {prim.get('material')}",
            "",
            f"P(settle) {_f(_pstat(prim,'a','p_settle'))} vs {_f(_pstat(prim,'b','p_settle'))}",
            f"P(rec≥10 / 5p) {_f(_pstat(prim,'a','p_rec10'))} vs {_f(_pstat(prim,'b','p_rec10'))}",
            f"P(det≥10 / 5p) {_f(_pstat(prim,'a','p_det10'))} vs {_f(_pstat(prim,'b','p_det10'))}",
            f"Wasserstein(DD_5) {_f((prim.get('delta') or {}).get('wasserstein_dd'))}",
            "",
            "These are observed candle-path distributions, not fills.",
            "",
        ]
    )


def _verdict(ctx) -> str:
    v = ctx["disc"]["verdict"]
    lines = [
        "# DRE V4 — Research Verdict",
        "",
        f"**Date:** {C.RESEARCH_DATE}",
        "",
        "| Item | Result |",
        "|------|--------|",
    ]
    for k, val in v.items():
        lines.append(f"| {k} | **{val}** |")
    lines += [
        "",
        "Q10 default remains **NO**. Execution evidence is UNOBSERVED.",
        "",
        C.BANNER,
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)
