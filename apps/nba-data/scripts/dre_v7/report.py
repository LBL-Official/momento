"""V7 research reports from frozen measurements."""

from __future__ import annotations

from . import config as C


def _f(v, d=3):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _ov(obj, split, *keys):
    cur = (obj.get("by_split") or {}).get(split) or {}
    for k in keys:
        cur = (cur or {}).get(k) if isinstance(cur, dict) else None
    return cur or {}


def write_reports(ctx: dict) -> None:
    main = _main(ctx)
    card = _card(ctx)
    syn = _syn(ctx)
    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V7.md").write_text(main)
    (C.DOCS / "DRE_V7_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V7_RESEARCH_SYNTHESIS.md").write_text(syn)
    for name, text in (
        ("MOMENTO_DYNAMIC_RISK_ENGINE_V7.md", main),
        ("DRE_V7_MODEL_CARD.md", card),
        ("DRE_V7_RESEARCH_SYNTHESIS.md", syn),
    ):
        (C.OUT / name).write_text(text)


def _main(ctx) -> str:
    s = ctx["synthesis"]
    g = ctx["gates"]
    a = ctx["rel_a"]
    b = ctx["rel_b"]
    sh = ctx["shift"]
    exp = ctx["exposure"]
    st = ctx["stability"]
    boot = ((ctx.get("bootstrap") or {}).get("oos_spearman_mean_da_r_bar") or {})
    inp = s.get("inputs") or {}
    flags = s.get("flags") or {}
    counts = ctx.get("counts") or {}
    prov = ctx.get("provenance") or {}
    oos_a = _ov(a, "OOS", "overall")
    tr_a = _ov(a, "TRAIN", "overall")
    val_a = _ov(a, "VALIDATION", "overall")
    oos_b5 = _ov(b, "OOS", "abs_ge_5")
    oos_b10 = _ov(b, "OOS", "abs_ge_10")
    oos_base = _ov(b, "OOS", "baseline_abs_lt_1")
    oos_exp = _ov(exp, "OOS")
    tr_exp = _ov(exp, "TRAIN")
    oos_st = _ov(st, "OOS", "overall")
    tr_st = _ov(st, "TRAIN", "overall")
    val_st = _ov(st, "VALIDATION", "overall")
    oos_sh = _ov(sh, "OOS")
    val_sh = _ov(sh, "VALIDATION")
    hj = (oos_st.get("high_low") or {})
    lines = [
        "# MOMENTO — Dynamic Risk Engine V7",
        "",
        f"**Program:** `{C.PROGRAM}`",
        f"**Schema:** {C.SCHEMA_VERSION}",
        f"**Date:** {C.RESEARCH_DATE}",
        "**Live execution changed:** FALSE",
        f"**Descriptive token:** `{s.get('token')}` — not a V7-A/B/C/D letter.",
        "",
        "```",
        C.BANNER,
        "```",
        "",
        f"> {C.PROMINENT}",
        "",
        "```",
        C.SUPPORT_NOT_INDEPENDENCE,
        "```",
        "",
        "## Central question",
        "",
        C.CENTRAL_QUESTION,
        "",
        "V7 is a structural diagnostic of the frozen V5/V6 state surface. It does not fit a new M0 or M1. It does not rescue V6. It does not declare tradability.",
        "",
        "## What this is not",
        "",
        "- Not edge.",
        "- Not a claim that M1 is wrong.",
        "- Not an exploitable signal.",
        "- Not a trading rule.",
        "- Not statistical independence.",
        "- Not a newly cleaned causal pipeline.",
        "",
        "## Residual formula (TRADE_BALANCED)",
        "",
        C.R_BAR_FORMULA,
        "",
        "```",
        "r_bar_i = Pi_i - mean_t(alpha_M0_it)",
        "mean_t(alpha_M0_it) = (1/T_i) * sum_t alpha_M0_it",
        "```",
        "",
        "One residual per trade. Repeated possessions from the same trade are not independent terminals.",
        "",
        "## Reconstruction provenance",
        "",
        f"Builders: `{prov.get('builders')}`. `m0_m1_calls = {prov.get('m0_m1_calls', 0)}`. Quietly improved: `{prov.get('quietly_improved')}`.",
        "",
        f"Panel after scoring: **{counts.get('rows')}** rows / **{counts.get('trades')}** trades. Before-scoring counts matched after-scoring counts in the first scientific pass.",
        "",
        str(prov.get("causal_note") or ""),
        "",
        "`Reproduce V5 exactly ≠ quietly improve V5 during reconstruction.`",
        "",
        "## Gates",
        "",
        "| Gate | Status |",
        "|------|--------|",
    ]
    for k in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"):
        lines.append(f"| {k} | **{(g.get(k) or {}).get('status')}** |")
    lines += [
        "",
        "Gate J records V6 decile source = TRAIN `mean_SIR_i` qcut, unit = trade, `CLIP_TO_TRAIN_EXTREMA`. High-versus-low on `mean_da_i` is therefore applicable. OOS high-versus-low coverage was still inadequate (n_hi = 12 < 15) and is recorded as INCONCLUSIVE.",
        "",
        "## Map integrity",
        "",
        f"Persisted V6 maps only. M0 **{C.V5_PUBLISHED['n_m0_cells']}** · M1 **{C.V5_PUBLISHED['n_m1_cells']}**. `m0_m1_calls = 0`.",
        "",
        "## Four fields that never collapse",
        "",
        "| Field | Meaning |",
        "|-------|---------|",
        "| `EXACT_CELL_EXISTS` | Frozen M1 key is present in the persisted map |",
        "| `TRAIN_UNIQUE_TRADE_SUPPORT` | Unique TRAIN `trade_id` count in that cell (0 if missing) |",
        "| `N_EFF_TRADE` | Occupancy-concentration effective trade count |",
        "| `SCORING_PATH` | `M1_EXACT` / `M0_FALLBACK` / `GLOBAL_FALLBACK` |",
        "",
        "A cell that exists with one TRAIN trade is not the same as missing → M0.",
        "",
        "## Relationship A — STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
        "",
        "| Split | n rows | mean \\|da\\| | Spearman(\\|da\\|, unique TRAIN trades) | P(\\|da\\|≥5¢) |",
        "|-------|-------:|------------:|----------------------------------------:|---------------:|",
        f"| TRAIN | {tr_a.get('n')} | {_f(tr_a.get('mean_abs_da'))} | {_f(tr_a.get('spearman_abs_da_vs_unique_trades'))} | {_f((tr_a.get('P_abs_ge') or {}).get('5'))} |",
        f"| VALIDATION | {val_a.get('n')} | {_f(val_a.get('mean_abs_da'))} | {_f(val_a.get('spearman_abs_da_vs_unique_trades'))} | {_f((val_a.get('P_abs_ge') or {}).get('5'))} |",
        f"| OOS | {oos_a.get('n')} | {_f(oos_a.get('mean_abs_da'))} | {_f(oos_a.get('spearman_abs_da_vs_unique_trades'))} | {_f((oos_a.get('P_abs_ge') or {}).get('5'))} |",
        "",
        "OOS occupancy-weighted mean \\|da\\| declines as unique-trade support rises (stratum 1 mean 37.9¢ → 50+ mean 2.7¢). This is a location statement, not a tradability statement.",
        "",
        "## Relationship B — CELL_GEOMETRY_DIAGNOSTIC",
        "",
        f"OOS \\|da\\|≥5¢: n_rows **{oos_b5.get('n_rows')}** · n_trades **{oos_b5.get('n_trades')}** · median TRAIN unique trades **{_f(oos_b5.get('median_TRAIN_unique_trades'))}** · median N_eff **{_f(oos_b5.get('median_N_EFF_TRADE'))}** · scoring path M1_EXACT **{(oos_b5.get('scoring_path') or {}).get('M1_EXACT')}** / M0_FALLBACK **{(oos_b5.get('scoring_path') or {}).get('M0_FALLBACK')}**.",
        "",
        f"OOS \\|da\\|≥10¢: n_rows **{oos_b10.get('n_rows')}** · median TRAIN unique trades **{_f(oos_b10.get('median_TRAIN_unique_trades'))}** · median N_eff **{_f(oos_b10.get('median_N_EFF_TRADE'))}**.",
        "",
        f"OOS baseline \\|da\\|<1¢: median TRAIN unique trades **{_f(oos_base.get('median_TRAIN_unique_trades'))}** · median N_eff **{_f(oos_base.get('median_N_EFF_TRADE'))}**.",
        "",
        "Extreme disagreement rows are exactly scored (M1_EXACT) more often than they are well supported. Exact scoring and robust support are not the same object.",
        "",
        "## Relationship C — TRADE_BALANCED",
        "",
        f"TRAIN mean fraction sparse **{_f(tr_exp.get('mean_fraction_sparse'))}** · Spearman(\\|mean_da\\|, min support) **{_f(tr_exp.get('spearman_abs_da_vs_min_support'))}**.",
        "",
        f"OOS mean fraction sparse **{_f(oos_exp.get('mean_fraction_sparse'))}** · Spearman(\\|mean_da\\|, min support) **{_f(oos_exp.get('spearman_abs_da_vs_min_support'))}**.",
        "",
        "## Distribution shift — STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
        "",
        f"TV(TRAIN, VAL) **{_f(sh.get('tv_train_val'))}**. TV(TRAIN, OOS) **{_f(sh.get('tv_train_oos'))}**.",
        "",
        f"OOS on TRAIN-observed M1 cells **{_f(oos_sh.get('pct_on_train_observed_m1'))}**. OOS M1_EXACT **{_f((oos_sh.get('scoring_path_rates') or {}).get('M1_EXACT'))}** · M0_FALLBACK **{_f((oos_sh.get('scoring_path_rates') or {}).get('M0_FALLBACK'))}** · GLOBAL **{_f((oos_sh.get('scoring_path_rates') or {}).get('GLOBAL_FALLBACK'))}**.",
        "",
        f"VALIDATION M0_FALLBACK **{_f((val_sh.get('scoring_path_rates') or {}).get('M0_FALLBACK'))}**.",
        "",
        "## Temporal stability — TEMPORAL_STABILITY_DIAGNOSTIC",
        "",
        "| Split | Spearman(mean_da, r_bar) | high–low status |",
        "|-------|-------------------------:|-----------------|",
        f"| TRAIN | {_f(tr_st.get('spearman_mean_da_r_bar'))} | {(tr_st.get('high_low') or {}).get('status')} |",
        f"| VALIDATION | {_f(val_st.get('spearman_mean_da_r_bar'))} | {(val_st.get('high_low') or {}).get('status')} |",
        f"| OOS | {_f(oos_st.get('spearman_mean_da_r_bar'))} | {hj.get('status')} |",
        "",
        f"OOS cluster-bootstrap Spearman mean **{_f(boot.get('mean'))}** · 5th **{_f(boot.get('p05'))}** · 95th **{_f(boot.get('p95'))}**. This is variation under resampling of observed game-level clusters, not a population causal CI.",
        "",
        "## Descriptive synthesis",
        "",
        f"Token: `{s.get('token')}`. Flags S1–S5: `{flags}`.",
        "",
        f"- S1 (large \\|da\\| associated with lower unique-trade support): **{flags.get('S1')}**. TRAIN Spearman {_f(inp.get('spearman_abs_da_vs_support_TRAIN'))}; OOS {_f(inp.get('spearman_abs_da_vs_support_OOS'))}. OOS \\|da\\|≥5 median TRAIN trades {_f(inp.get('oos_extreme5_median_train_trades'))} vs baseline {_f(inp.get('oos_baseline_median_train_trades'))}.",
        f"- S2 (occupancy inflation of independence): **{flags.get('S2')}**. OOS extreme median rows/trade {_f(inp.get('oos_extreme5_median_rows_per_trade'))}; median N_eff {_f(inp.get('oos_extreme5_median_n_eff'))}. The locked occupancy-inflation rule did not fire.",
        f"- S3 (VAL/OOS rare-cell or TV shift): **{flags.get('S3')}**. Rare-row share TRAIN {_f(inp.get('rare_row_share_train'))} vs OOS {_f(inp.get('rare_row_share_oos'))}. TV(TRAIN,OOS) {_f(inp.get('tv_train_oos'))} is below the locked 0.15 token threshold.",
        f"- S4 (high-support Spearman larger in magnitude than low-support): **{flags.get('S4')}**. OOS 20–49 {_f(inp.get('spearman_r_high_support_oos'))} vs 2–4 {_f(inp.get('spearman_r_low_support_oos'))}. Point estimates differ; high–low coverage is INCONCLUSIVE.",
        f"- S5 (well-supported extremes still degrade TRAIN→OOS): **{flags.get('S5')}**. Overall Spearman TRAIN {_f(inp.get('spearman_r_overall_train'))} → OOS {_f(inp.get('spearman_r_overall_oos'))} while OOS extreme-cell median unique trades is {_f(inp.get('oos_extreme5_median_train_trades'))}.",
        "",
        "Allowed reading: extreme disagreement is disproportionately associated with lower unique-trade support, and TRAIN→OOS residual association still weakens after that association is visible.",
        "",
        "Forbidden reading: therefore M1 is wrong; therefore there is an exploitable signal; therefore trade it.",
        "",
        "## Bootstrap meaning",
        "",
        C.SPECIFICATION_LOCKS["bootstrap"]["meaning"],
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)


def _card(ctx) -> str:
    s = ctx["synthesis"]
    g = ctx["gates"]
    return "\n".join(
        [
            "# DRE V7 — Model Card",
            "",
            f"**Program:** `{C.PROGRAM}`",
            f"**Schema:** {C.SCHEMA_VERSION}",
            f"**Date:** {C.RESEARCH_DATE}",
            f"**Descriptive token:** `{s.get('token')}`",
            "",
            "```",
            C.BANNER,
            "```",
            "",
            f"> {C.PROMINENT}",
            "",
            "## Intended use",
            "",
            "Offline structural diagnosis of the frozen V5/V6 state surface.",
            "",
            "V7 does not establish tradability.",
            "",
            "V7 does not fit a new predictive state model.",
            "",
            "V7 diagnoses support and stability properties of the existing frozen V5/V6 state surface.",
            "",
            "A state cell with many possession rows may still have low independent terminal-outcome support.",
            "",
            "Repeated observations from the same trade do not constitute independent terminal outcomes.",
            "",
            "## Support language (verbatim)",
            "",
            C.SUPPORT_NOT_INDEPENDENCE,
            "",
            "Unique trade count is a support unit, not proof of statistical independence.",
            "",
            "N_eff,trade measures concentration of row occupancy across trades; it does not estimate the number of statistically independent terminal experiments.",
            "",
            "One trade per game on this panel does not make trades i.i.d.",
            "",
            "## Residual",
            "",
            C.R_BAR_FORMULA,
            "",
            "## Four fields",
            "",
            "`EXACT_CELL_EXISTS` · `TRAIN_UNIQUE_TRADE_SUPPORT` · `N_EFF_TRADE` · `SCORING_PATH`",
            "",
            "These fields must never be collapsed into one “support” chip.",
            "",
            "## Bootstrap",
            "",
            C.SPECIFICATION_LOCKS["bootstrap"]["meaning"],
            "",
            "## Gates",
            "",
            " ".join(f"{k}={(g.get(k) or {}).get('status')}" for k in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")),
            "",
            "## Safety",
            "",
            "LIVE DEPLOYMENT: **NOT AUTHORIZED**",
            "",
        ]
    )


def _syn(ctx) -> str:
    s = ctx["synthesis"]
    inp = s.get("inputs") or {}
    flags = s.get("flags") or {}
    q = s.get("questions") or {}
    return "\n".join(
        [
            "# DRE V7 — Research Synthesis",
            "",
            f"**Date:** {C.RESEARCH_DATE}",
            "",
            "```",
            C.BANNER,
            "```",
            "",
            f"> {C.PROMINENT}",
            "",
            f"**Token:** `{s.get('token')}`",
            "",
            "This is a descriptive synthesis state, not a scientific verdict letter and not a trading signal.",
            "",
            f"S1–S5 flags: `{flags}`",
            "",
            C.SUPPORT_NOT_INDEPENDENCE,
            "",
            "## Q1 — Are large SIR values disproportionately associated with low unique-trade TRAIN support?",
            "",
            f"{q.get('Q1')}",
            "",
            f"Structural measurement: yes, as an association. TRAIN Spearman(|da|, unique TRAIN trades) = {_f(inp.get('spearman_abs_da_vs_support_TRAIN'))}; OOS = {_f(inp.get('spearman_abs_da_vs_support_OOS'))}. OOS |da|≥5¢ rows have median TRAIN unique trades {_f(inp.get('oos_extreme5_median_train_trades'))} versus {_f(inp.get('oos_baseline_median_train_trades'))} for |da|<1¢. This does not imply M1 is wrong.",
            "",
            "## Q2 — Does raw possession-row support overstate unique-trade support?",
            "",
            f"{q.get('Q2')}",
            "",
            f"S2 did not fire. OOS extreme median rows/trade = {_f(inp.get('oos_extreme5_median_rows_per_trade'))}; unique-trade median = {_f(inp.get('oos_extreme5_median_train_trades'))}; N_eff median = {_f(inp.get('oos_extreme5_median_n_eff'))}. Occupancy concentration is visible (N_eff < unique trades) but is not the locked occupancy-inflation pattern.",
            "",
            "## Q3 — Did VAL/OOS encounter more rare or weakly supported cells?",
            "",
            f"{q.get('Q3')}",
            "",
            f"S3 did not fire. Rare-row share TRAIN {_f(inp.get('rare_row_share_train'))} versus OOS {_f(inp.get('rare_row_share_oos'))}. TV(TRAIN,OOS) = {_f(inp.get('tv_train_oos'))}, below the locked 0.15 token threshold. Fallback remains small (OOS M0_FALLBACK ≈ 0.5%).",
            "",
            "## Q4 — Is temporal stability stronger for well-supported cells?",
            "",
            f"{q.get('Q4')}",
            "",
            f"S4 fired on point estimates: OOS Spearman in 20–49 = {_f(inp.get('spearman_r_high_support_oos'))} versus 2–4 = {_f(inp.get('spearman_r_low_support_oos'))}. OOS high–low coverage is INCONCLUSIVE (n_hi < 15). Do not read this as a tradable high-versus-low rule.",
            "",
            "## Q5 — Does support plausibly relate to TRAIN→VAL→OOS degradation?",
            "",
            f"{q.get('Q5')}",
            "",
            f"S5 fired. Overall Spearman TRAIN {_f(inp.get('spearman_r_overall_train'))} → OOS {_f(inp.get('spearman_r_overall_oos'))} while OOS extreme-cell median unique trades remains {_f(inp.get('oos_extreme5_median_train_trades'))} (above the sparse cutoff of 4). Support geometry is associated with disagreement location; it does not, by itself, exhaust the TRAIN→OOS attenuation.",
            "",
            "## Q6 — If not, what architectural uncertainty remains?",
            "",
            f"{q.get('Q6')}",
            "",
            "Remaining structural uncertainty includes game-cluster dependence, season/regime sharing across trades, the M0/M1 architecture itself, and thin OOS high–low coverage. Unique trades are not i.i.d. experiments. Bootstrap intervals are cluster-resampling variation, not causal CIs.",
            "",
            str(s.get("note") or ""),
            "",
            "```",
            "Δα_state ≠ EDGE",
            "CONDITIONAL INFORMATION ≠ EXECUTION",
            "REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES",
            "LIVE DEPLOYMENT = NOT AUTHORIZED",
            "```",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
