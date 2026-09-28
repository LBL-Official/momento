"""V6 research reports from frozen measurements."""

from __future__ import annotations

from . import config as C


def _f(v, d=3):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def write_halt_reports(ctx: dict) -> None:
    write_reports(ctx)


def write_reports(ctx: dict) -> None:
    main = _main(ctx)
    card = _card(ctx)
    verd = _verdict(ctx)
    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V6.md").write_text(main)
    (C.DOCS / "DRE_V6_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V6_RESEARCH_VERDICT.md").write_text(verd)
    for name, text in (
        ("MOMENTO_DYNAMIC_RISK_ENGINE_V6.md", main),
        ("DRE_V6_MODEL_CARD.md", card),
        ("DRE_V6_RESEARCH_VERDICT.md", verd),
    ):
        (C.OUT / name).write_text(text)


def _main(ctx) -> str:
    v = ctx["verdict"]
    g = ctx["gates"]
    dist = ctx["distribution"]
    conc = ctx["concentration"]
    rank = ctx["rank"]
    resid = ctx["residual"]
    pers = ctx["persistence"]
    oos_tb = ((dist.get("by_split") or {}).get("OOS") or {}).get("TRADE_BALANCED") or {}
    oos_c = ((conc.get("by_split") or {}).get("OOS") or {})
    oos_r = ((rank.get("by_split") or {}).get("OOS") or {})
    oos_res = ((resid.get("by_split") or {}).get("OOS") or {})
    oos_p = ((pers.get("by_split") or {}).get("OOS") or {})
    ident = ctx.get("identity") or {}
    obs = ident.get("observed") or {}
    lines = [
        "# MOMENTO — Dynamic Risk Engine V6",
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
        "```",
        "Δα_state ≠ EDGE",
        "CONDITIONAL INFORMATION ≠ EXECUTION",
        "CANDLE PATH ≠ FILL",
        "LIVE DEPLOYMENT = NOT AUTHORIZED",
        "```",
        "",
        "## Central question",
        "",
        C.CENTRAL_QUESTION,
        "",
        "V5 Verdict B is historical. V6 does not reopen the 0.5¢ MAE test.",
        "",
        "## Headline",
        "",
        f"**{v.get('HEADLINE')} — {v.get('name')}**",
        "",
        *(
            [
                "This is a **HARD HALT**, not a fifth scientific letter. The frozen A/B/C/D conjunctions were applied once. None fired. Thresholds were not moved.",
                "",
            ]
            if v.get("halt")
            else []
        ),
        f"| Flag | On |",
        f"|------|----|",
        f"| A No meaningful state information | **{v.get('flags', {}).get('A')}** |",
        f"| B Statistical state information | **{v.get('flags', {}).get('B')}** |",
        f"| C Concentrated state information | **{v.get('flags', {}).get('C')}** |",
        f"| D Potential economic signal | **{v.get('flags', {}).get('D')}** |",
        "",
        "Even V6-D is not expected trading profit. `POTENTIAL ECONOMIC SIGNAL ≠ TRADABLE STRATEGY`.",
        "",
        "## Gates",
        "",
        "| Gate | Status |",
        "|------|--------|",
        f"| A V5 locks | **{(g.get('A') or {}).get('status')}** |",
        f"| B Predecessors | **{(g.get('B') or {}).get('status')}** |",
        f"| C Map identity | **{(g.get('C') or {}).get('status')}** |",
        f"| D Maps persisted first | **{(g.get('D') or {}).get('status')}** |",
        f"| E Splits | **{(g.get('E') or {}).get('status')}** |",
        f"| F Protocol first | **{(g.get('F') or {}).get('status')}** |",
        f"| G V5 untouched | **{(g.get('G') or {}).get('status')}** |",
        f"| H No path/40 in headline | **{(g.get('H') or {}).get('status')}** |",
        f"| I Weighting labeled | **{(g.get('I') or {}).get('status')}** |",
        "",
        "## Map recovery identity",
        "",
        f"OOS MAE M0 **{_f(obs.get('mae_m0_oos'))}** · M1 **{_f(obs.get('mae_m1_oos'))}** · Δ **{_f(obs.get('delta_mae_oos'))}**. Cells M0 **{obs.get('n_m0_cells')}** · M1 **{obs.get('n_m1_cells')}**.",
        "",
        "## TRADE_BALANCED distribution of mean_SIR",
        "",
        "| split | weighting | mean | P50 | max |P| | P≥1¢ | P≥2¢ | P≥5¢ | P≥10¢ |",
        "|-------|-----------|------|-----|--------|------|------|------|-------|",
    ]
    for split in C.SPLITS:
        tb = ((dist.get("by_split") or {}).get(split) or {}).get("TRADE_BALANCED") or {}
        p = tb.get("P_abs_ge") or {}
        lines.append(
            f"| {split} | TRADE_BALANCED | {_f(tb.get('mean'))} | {_f(tb.get('p50'))} | {_f(tb.get('max_abs'))} | "
            f"{_f(p.get('1'))} | {_f(p.get('2'))} | {_f(p.get('5'))} | {_f(p.get('10'))} |"
        )
    lines += [
        "",
        f"OOS P(|mean_SIR|≥5¢) **{_f(oos_tb.get('P_abs_ge', {}).get('5'))}**.",
        "",
        "## Concentration (geometry, not evidence) — TRADE_BALANCED",
        "",
        "| split | weighting | top 1% | top 5% | top 10% | top 25% | top10 ≥ 40% |",
        "|-------|-----------|--------|--------|---------|---------|-------------|",
    ]
    for split in C.SPLITS:
        c = ((conc.get("by_split") or {}).get(split) or {})
        shares = {s.get("frac"): s.get("share") for s in (c.get("shares") or [])}
        lines.append(
            f"| {split} | TRADE_BALANCED | {_f(shares.get(0.01))} | {_f(shares.get(0.05))} | "
            f"{_f(shares.get(0.10))} | {_f(shares.get(0.25))} | {c.get('top10_meets_40')} |"
        )
    lines += [
        "",
        C.CONCENTRATION_NOT_EVIDENCE,
        "",
        "## Rank (TRADE_BALANCED)",
        "",
        "| split | weighting | n | spread 10−1 E[Π] | n_lo | n_hi | adequate | Spearman(SIR, Π) |",
        "|-------|-----------|---|------------------|------|------|----------|------------------|",
    ]
    for split in C.SPLITS:
        r = ((rank.get("by_split") or {}).get(split) or {})
        lines.append(
            f"| {split} | TRADE_BALANCED | {r.get('n_trades')} | {_f(r.get('spread_hi_minus_lo'))} | "
            f"{r.get('n_lo')} | {r.get('n_hi')} | {r.get('adequate')} | {_f(r.get('spearman_sir_pi'))} |"
        )
    lines += [
        "",
        f"OOS top−bottom decile E[Π] **{_f(oos_r.get('spread_hi_minus_lo'))}**. Replication token **{(rank.get('replication') or {}).get('token')}**.",
        "",
        "Candle path does not enter this table, V6-D, or rank replication.",
        "",
        "## Residual-on-residual (primary TRADE_BALANCED)",
        "",
        "| split | weighting | n | spread 10−1 E[R̄] | Spearman(SIR, R̄) |",
        "|-------|-----------|---|-------------------|-------------------|",
    ]
    for split in C.SPLITS:
        rr = ((resid.get("by_split") or {}).get(split) or {})
        lines.append(
            f"| {split} | TRADE_BALANCED | {rr.get('n_trades')} | {_f(rr.get('spread_hi_minus_lo'))} | {_f(rr.get('spearman_sir_r'))} |"
        )
    lines += [
        "",
        f"OOS top−bottom decile E[R̄] **{_f(oos_res.get('spread_hi_minus_lo'))}**. Replication token **{(resid.get('replication') or {}).get('token')}**.",
        "",
        "Occupancy residual-on-residual is a STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC and is not the primary test.",
        "",
        "## Persistence — TRADE_BALANCED",
        "",
        f"OOS median duration among trades ever |da|≥5¢: **{_f(oos_p.get('median_duration_k5'), 1)}** possessions. `PERSISTENCE ≠ EXECUTABILITY`.",
        "",
        "## Forward path (diagnostic only)",
        "",
        "CANDLE PATH ≠ FILL. Forbidden in headline, V6-D, residual replication, and rank replication.",
        "",
        "## What this is not",
        "",
        "Not edge. Not a fill. Not production size. Not live. Not microstructure. Not monetization.",
        "",
        "Economic scale: 5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines) + "\n"


def _card(ctx) -> str:
    return "\n".join(
        [
            "# DRE V6 — Model Card",
            "",
            f"**Program:** `{C.PROGRAM}`",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "## Intended use",
            "",
            "Offline attribution of V5's 0.429¢ OOS MAE improvement: where TRAIN-frozen M1 disagrees with TRAIN-frozen M0, and whether that disagreement predicts M0 residuals.",
            "",
            "If A/B/C/D none fire, the recorded status is UNCLASSIFIED_PRE_REGISTERED_OUTCOME. That is a halt, not a fifth scientific category.",
            "",
            "Not for order routing, stops, hedges, exposure, or live risk.",
            "",
            "## Primary estimand",
            "",
            r"TRADE_BALANCED \(\overline{\Delta\alpha}_i \longrightarrow \bar R_i\).",
            "",
            "Row-level residual-on-residual is STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC.",
            "",
            "## Concentration",
            "",
            C.CONCENTRATION_NOT_EVIDENCE,
            "",
            "## Units / inventory",
            "",
            "Cents per contract. 5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.",
            "",
            "## Limitations",
            "",
            "Δα_state ≠ EDGE. CONDITIONAL INFORMATION ≠ EXECUTION. CANDLE PATH ≠ FILL. No microstructure. No fees. No fills.",
            "",
            "## Safety",
            "",
            "LIVE DEPLOYMENT: **NOT AUTHORIZED**",
            "",
        ]
    )


def _verdict(ctx) -> str:
    v = ctx["verdict"]
    return "\n".join(
        [
            "# DRE V6 — Research Verdict",
            "",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "| Item | Result |",
            "|------|--------|",
            f"| STATUS | **{v.get('HEADLINE')} — {v.get('name')}** |",
            f"| A | **{v.get('flags', {}).get('A')}** |",
            f"| B | **{v.get('flags', {}).get('B')}** |",
            f"| C | **{v.get('flags', {}).get('C')}** |",
            f"| D | **{v.get('flags', {}).get('D')}** |",
            "| LIVE_DEPLOYMENT | **NOT AUTHORIZED** |",
            "",
            "```",
            "Δα_state ≠ EDGE",
            "CONDITIONAL INFORMATION ≠ EXECUTION",
            "CANDLE PATH ≠ FILL",
            "LIVE DEPLOYMENT = NOT AUTHORIZED",
            "```",
            "",
            str(v.get("note") or ""),
            "",
            str(v.get("d_ceiling") or ""),
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
