"""DRE V5 research reports from computed artifacts."""

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
    ledger = _ledger(ctx)
    verd = _verdict(ctx)
    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V5.md").write_text(main)
    (C.DOCS / "DRE_V5_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V5_TRADE_LEDGER.md").write_text(ledger)
    (C.DOCS / "DRE_V5_RESEARCH_VERDICT.md").write_text(verd)
    for name, text in (
        ("MOMENTO_DYNAMIC_RISK_ENGINE_V5.md", main),
        ("DRE_V5_MODEL_CARD.md", card),
        ("DRE_V5_TRADE_LEDGER.md", ledger),
        ("DRE_V5_RESEARCH_VERDICT.md", verd),
    ):
        (C.OUT / name).write_text(text)


def _tok(rep, cid):
    for c in (rep.get("contrasts") or []):
        if c.get("id") == cid:
            return c
    return {}


def _main(ctx) -> str:
    v = ctx["verdict"]
    g = ctx["gates"]
    u = ctx["universe"]
    counts = ctx["counts"]
    m01 = ctx["m01"]
    pace = ctx["pace_audit"]
    lam = ctx["lambda"]
    rep = ctx["replication"]
    lines = [
        "# MOMENTO — Dynamic Risk Engine V5",
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
        "## Central question",
        "",
        "Does the historical FIRST-80 payoff distribution contain reproducible conditional structure that can be identified using only information observable during the life of the position?",
        "",
        "V5 is **not** asking whether we can make more money by exiting, hedging, or trading. V6 (later) asks that.",
        "",
        "## Headline",
        "",
        f"**Verdict {v.get('HEADLINE')}**",
        "",
        f"| Flag | On |",
        f"|------|----|",
        f"| A Strong state segmentation | **{v.get('flags', {}).get('A')}** |",
        f"| B Price dominates | **{v.get('flags', {}).get('B')}** |",
        f"| C Prior-informed remaining adds information | **{v.get('flags', {}).get('C')}** |",
        f"| D Nothing replicates OOS | **{v.get('flags', {}).get('D')}** |",
        "",
        "TRAIN interestingness is not a discovery. OOS decided the headline under a protocol written before OOS tables.",
        "",
        "## Terminology",
        "",
        r"V5 Conditional Alpha is the **conditional expected payoff** of frozen \(\Pi_{\mathrm{terminal}}=100Y-80\). It is not benchmark-relative financial alpha.",
        "",
        r"Because that payoff takes only \(\{+20,-80\}\), \(\alpha_{\mathrm{frozen}}(X)=100P(Y=1\mid X)-80\). A cell of +7¢ means historical settle probability \(\approx 0.87\). P10/P50/P90 are empirical; a realized 0 never occurs.",
        "",
        "## Frozen inputs",
        "",
        "| Gate | Status |",
        "|------|--------|",
        f"| A Frozen FIRST-80 | **{(g.get('A') or {}).get('status')}** |",
        f"| B PADE integrity | **{(g.get('B') or {}).get('status')}** |",
        f"| C DRE V4 integrity | **{(g.get('C') or {}).get('status')}** |",
        f"| D Leakage | **{(g.get('D') or {}).get('status')}** |",
        f"| E Split isolation | **{(g.get('E') or {}).get('status')}** |",
        f"| F Prior-only " + r"\(\widehat N\)" + f" | **{(g.get('F') or {}).get('status')}** |",
        f"| G Path/label normalization | **{(g.get('G') or {}).get('status')}** |",
        f"| H No OOS tuning + protocol first | **{(g.get('H') or {}).get('status')}** |",
        f"| I TRADE_BALANCED labeled | **{(g.get('I') or {}).get('status')}** |",
        "",
        "## Universe",
        "",
        (
            f"Universe **{u.get('universe')}**. Panel-eligible **{u.get('panel_eligible')}**. "
            f"Unresolved **{u.get('unresolved_n')}** (preserved). Panel rows **{counts.get('rows')}**. "
            r"Q=100 research inventory. \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,\mathrm{cents}}\). \(\Delta^{\mathrm{inv}}=100\)."
        ),
        "",
        "## Prior-informed remaining",
        "",
        (
            "One `03_possessions` row = one offensive possession. "
            r"\(R_x=\widehat{\mathrm{pace}}_{A1}+\widehat{\mathrm{pace}}_{A2}\). "
            f"Chronology: `{pace.get('chronology')}`. TRAIN league mean team pace **{_f(pace.get('train_league_mean_team_poss'), 2)}**. "
            f"Observed " + r"\(R_x\)" + f" mean **{_f((pace.get('r_x') or {}).get('mean'), 2)}** (352 was an identity illustration, not used)."
        ),
        "",
        r"## Pre-registered OOS contrasts (trade-balanced \(\alpha_{\mathrm{frozen}}\))",
        "",
    ]
    for cid in ("L3_clock_early_late_60", "L3_score_lead_trail_60", "L3_nhat_high_low_60"):
        c = _tok(rep, cid)
        lines.append(
            f"- `{cid}`: token **{c.get('token')}** · TRAIN {_f(c.get('train_effect'))} · VAL {_f(c.get('val_effect'))} · OOS {_f(c.get('oos_effect'))} · ratio {_f(c.get('ratio_oos_over_train'))}"
        )
    oos_m = (m01.get("by_split") or {}).get("OOS") or {}
    lines += [
        "",
        "## M0 vs M1 (Lock 5)",
        "",
        f"OOS TRADE_BALANCED MAE M0 **{_f(oos_m.get('mae_m0_trade_balanced'))}** · M1 **{_f(oos_m.get('mae_m1_trade_balanced'))}** · "
        + r"\(\Delta\)"
        + f" **{_f(oos_m.get('delta_mae_m0_minus_m1'))}**. M1 beats M0: **{m01.get('m1_beats_m0')}**.",
        "",
        "Occupancy MAE is a STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC, not the economic comparison.",
        "",
        "## Path Lambda",
        "",
        f"Scientific OOS Lambda (TRAIN-frozen α, OOS paths): mean trade-balanced **{_f((lam.get('scientific_oos_lambda') or {}).get('mean_trade_balanced'))}**.",
        f"Descriptive OOS Lambda is **not** a verdict input: **{_f((lam.get('descriptive_oos_lambda') or {}).get('mean_trade_balanced'))}**.",
        "",
        "## What this is not",
        "",
        "Not an action. Not a fill. Not production size. Not live. Not isolated time decay.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines) + "\n"


def _card(ctx) -> str:
    return "\n".join(
        [
            "# DRE V5 — Model Card",
            "",
            f"**Program:** `{C.PROGRAM}`",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "## Intended use",
            "",
            "Offline research into whether observable state reproducibly segments the frozen FIRST-80 terminal payoff distribution.",
            "",
            "Not for order routing, stops, hedges, exposure, or live risk.",
            "",
            "## Data",
            "",
            "Frozen FIRST-80 + PADE V1 panel + `03_possessions.parquet`. Chronological game-level TRAIN/VAL/OOS.",
            "",
            "## Primary estimand",
            "",
            r"\(\alpha_{\mathrm{frozen}}(X)=E[100Y-80\mid X]=100P(Y=1\mid X)-80\).",
            "",
            "Primary weighting: TRADE_BALANCED. Secondary: STATE_OCCUPANCY_WEIGHTED.",
            "",
            "## Units",
            "",
            r"Cents per contract. \(P_{A1}\in[0,100]\). \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,\mathrm{cents}}\).",
            "",
            "## Limitations",
            "",
            "Candle path ≠ fill. Clustered rows. Binary payoff quantiles are coarse. OT clock is separately flagged. No L2 book. No execution.",
            "",
            "## Safety",
            "",
            "LIVE DEPLOYMENT: **NOT AUTHORIZED**",
            "",
        ]
    )


def _ledger(ctx) -> str:
    u = ctx["universe"]
    return "\n".join(
        [
            "# DRE V5 — Trade Ledger",
            "",
            "Every frozen FIRST-80 trade is documented as a **buy at 80¢, Q=100** research card.",
            "",
            f"Universe **{u.get('universe')}**. Unresolved **{u.get('unresolved_n')}** preserved.",
            "",
            "- `entry_price_cents=80`",
            "- `contracts_research=100`",
            f"- `V_mtm_entry_cents={C.V_MTM_ENTRY_CENTS}` (= 100 × 80 cents)",
            "- `fill_status=CANDLE_PATH_PROXY_NOT_PROVEN_FILL`",
            "- Disclaimer on every card: OBSERVED CANDLE PATH — NOT FILL HISTORY",
            "",
            "This does not change the $50 / 12.5% production allocation.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )


def _verdict(ctx) -> str:
    v = ctx["verdict"]
    names = {"A": "Strong state segmentation", "B": "Price dominates", "C": "Prior-informed remaining adds information", "D": "Nothing replicates OOS"}
    h = v.get("HEADLINE")
    return "\n".join(
        [
            "# DRE V5 — Research Verdict",
            "",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            f"| Item | Result |",
            f"|------|--------|",
            f"| HEADLINE | **{h} — {names.get(h, h)}** |",
            f"| A | **{v.get('flags', {}).get('A')}** |",
            f"| B | **{v.get('flags', {}).get('B')}** |",
            f"| C | **{v.get('flags', {}).get('C')}** |",
            f"| D | **{v.get('flags', {}).get('D')}** |",
            f"| LIVE_DEPLOYMENT | **NOT AUTHORIZED** |",
            "",
            (v.get("note") or ""),
            "",
            C.BANNER,
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
