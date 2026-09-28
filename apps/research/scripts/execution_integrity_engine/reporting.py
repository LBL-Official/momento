"""Write EIE / DRE baseline reports from artifacts. No invented numbers."""

from __future__ import annotations

from pathlib import Path

DOCS = Path("/Users/user/Desktop/Momento/docs/research/EXECUTION_INTEGRITY_ENGINE")


def _ev(s, key, field="gross_expectancy"):
    block = s["expectancy"].get(key) or {}
    v = block.get(field)
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def write_reports(sports: dict, meta: dict) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    nba, p5 = sports["nba"], sports["ncaab"]
    (DOCS / "EXECUTIVE_SUMMARY.md").write_text(_exec(nba, p5, meta))
    (DOCS / "BASELINE_RESULTS.md").write_text(_baseline(nba, p5, meta))
    (DOCS / "PAYOFF_STRUCTURE.md").write_text(_payoff(nba, p5))
    (DOCS / "EXPECTANCY_DECOMPOSITION.md").write_text(_decomp(nba, p5))
    (DOCS / "EVIDENCE_LEVEL_ANALYSIS.md").write_text(_evidence(nba, p5))
    (DOCS / "EXECUTION_MODEL_COMPARISON.md").write_text(_models(nba, p5))
    (DOCS / "DATA_LIMITATIONS.md").write_text(_limits())
    (DOCS / "RESEARCH_INVARIANTS.md").write_text(_inv(nba, p5, meta))
    (DOCS / "REPORT.md").write_text(_report(nba, p5, meta))


def _exec(nba, p5, meta) -> str:
    return f"""# EIE + DRE_BASELINE_V1 — executive summary

Research only. **LIVE_EXECUTION_CHANGED = {meta.get('live_execution_changed')}.**

Universe `{meta.get('universe_version')}` · A1 hash `{meta.get('a1_config_hash')}` · \
EIE hash `{meta.get('config_hash')}`.

## The law

```text
L1 observed state     ≠  L2 observable opportunity
L2 opportunity        ≠  L3 modeled execution
L3 modeled execution  ≠  L4 actual execution
```

A gap-through (`23→75`) is L2 `THRESHOLD_CROSSING` + `GAP_THROUGH`.
It is **not** an E1 fill at 40.

## Answers

**Q1 — Payoff structure (E1, H=40 exact).**  
Hedge only when the first post-entry A2 close **occupies** 40. Otherwise 80→40. \
Path classes and contributions are in `PAYOFF_STRUCTURE.md`.

**Q2 — Expectancy by evidence level (FULL, ¢/trade).**

| Layer | NBA | NCAAB P5 | Strength |
|---|---:|---:|---|
| L1 hold (settlement only) | {_ev(nba,'EV_L1_hold')} | {_ev(p5,'EV_L1_hold')} | Observed resolution |
| L3 fallback 80→40 | {_ev(nba,'EV_80_40')} | {_ev(p5,'EV_80_40')} | Model A stop |
| L3 E1 conservative | {_ev(nba,'EV_L3_E1')} | {_ev(p5,'EV_L3_E1')} | Modeled, not actual |
| L3 theoretical @40 | {_ev(nba,'EV_L3_E_THEO')} | {_ev(p5,'EV_L3_E_THEO')} | Illegal promotion |
| L4 actual | NOT_AVAILABLE | NOT_AVAILABLE | None |

**Q3 — Where EV comes from.** See decomposition. Do not treat V1’s extra EV as hedge alpha.

**Q4 — Sensitivity.** E2 q/partial interpolates E1 toward 80→40. E3/E4 unavailable.

**Q5 — Edge that disappears upward.** NBA theoretical − E1 = gap fiction \
({nba['waterfall']['theo_minus_e1_gap_fiction']}¢). That increment is L2 crossings \
promoted to fills.

**Q6 — Robust enough for deterioration calculus?** \
**80→40 (fallback) is the robust causal book.** E1 at H=40 does not beat it. \
Do not differentiate a fictional V1 lock. L4 does not exist yet.

Do not implement A2 hedging in FIRST01 from this layer.
"""


def _baseline(nba, p5, meta) -> str:
    def repro(s):
        r = s["reproduction"]
        return f"{r['n']} hold={r['hold']} stop={r['stop']} v1={r['v1']} gate={'PASS' if r['ok'] else 'FAIL'}"

    return f"""# DRE_BASELINE_V1 results

This is the **reference state** of the current hybrid / FIRST80 stack. \
It is not a deterioration-rate engine.

| Sport | n | Dates | TRAIN / VAL / OOS | Reproduction |
|---|---:|---|---|---|
| NBA | {nba['n']} | {nba['date_min']}–{nba['date_max']} | {nba['split_n']} | {repro(nba)} |
| NCAAB P5 | {p5['n']} | {p5['date_min']}–{p5['date_max']} | {p5['split_n']} | {repro(p5)} |

P5 OOS is small — treat as `INSUFFICIENT_SAMPLE` when n<40.

## Counterfactuals (FULL mean ¢)

| Book | NBA | P5 |
|---|---:|---:|
| HOLD | {nba['counterfactual']['hold']:.4f} | {p5['counterfactual']['hold']:.4f} |
| 80→40 | {nba['counterfactual']['stop_80_40']:.4f} | {p5['counterfactual']['stop_80_40']:.4f} |
| HYBRID E1 | {nba['counterfactual']['hybrid_e1']:.4f} | {p5['counterfactual']['hybrid_e1']:.4f} |
| THEORETICAL @40 | {nba['counterfactual']['theoretical_threshold']:.4f} | {p5['counterfactual']['theoretical_threshold']:.4f} |
| ACTUAL | NOT_AVAILABLE | NOT_AVAILABLE |

## Waterfall

NBA: hold {nba['waterfall']['hold']} + stop {nba['waterfall']['plus_stop_protection']} \
= 80→40 {nba['waterfall']['equals_80_40']} + E1 Δ {nba['waterfall']['plus_e1_hedge_vs_stop']} \
= E1 {nba['waterfall']['equals_e1']}. Gap fiction {nba['waterfall']['theo_minus_e1_gap_fiction']}.

P5: hold {p5['waterfall']['hold']} + stop {p5['waterfall']['plus_stop_protection']} \
= 80→40 {p5['waterfall']['equals_80_40']} + E1 Δ {p5['waterfall']['plus_e1_hedge_vs_stop']} \
= E1 {p5['waterfall']['equals_e1']}. Gap fiction {p5['waterfall']['theo_minus_e1_gap_fiction']}.
"""


def _payoff(nba, p5) -> str:
    def rows(s):
        lines = ["| class | n | freq | mean | EV contrib |", "|---|---:|---:|---:|---:|"]
        for r in s["decomposition"]["rows"]:
            lines.append(
                f"| {r['path_class']} | {r['n']} | {r['frequency']} | {r['mean_pnl']} | {r['contribution_to_total_ev']} |"
            )
        lines.append(
            f"| TOTAL | {s['n']} | 1 | {s['decomposition']['total_ev']} | recon={s['decomposition']['reconstructed_ev']} err={s['decomposition']['abs_error']} |"
        )
        return "\n".join(lines)

    return f"""# Payoff structure (E1)

Path class is a **dimension**, not a compressed story.

## NBA

{rows(nba)}

Concentration: {nba['concentration']}

## NCAAB P5

{rows(p5)}

Concentration: {p5['concentration']}
"""


def _decomp(nba, p5) -> str:
    return f"""# Expectancy decomposition

Identity: `TOTAL_EV = Σ frequency × conditional_EV`.

NBA identity_ok={nba['decomposition']['identity_ok']} \
error={nba['decomposition']['abs_error']}

P5 identity_ok={p5['decomposition']['identity_ok']} \
error={p5['decomposition']['abs_error']}

L1 hold is settlement-only (no intra-path intervention).
80→40 is Model A (also a fill assumption on A1).
E1 adds a hedge only on exact occupancy of 40.
Theoretical books every close≥40 at 40, including gaps.

E2 scenarios (partial=1) are in the dashboard. They are **not** observed p_fill.
"""


def _evidence(nba, p5) -> str:
    return f"""# Evidence-level analysis

## Opportunity counts (H=40 exact, L2)

| class | NBA | P5 |
|---|---:|---:|
{_count_table(nba, p5, 'opportunity_counts')}

## Occupancy

| status | NBA | P5 |
|---|---:|---:|
{_count_table(nba, p5, 'occupancy_counts')}

## L1 → L2

L1 records the close (e.g. 75). L2 may mark `THRESHOLD_CROSSING` and `GAP_THROUGH`. \
Occupancy of 40 is `INFERRED_POSSIBLE`, not `OBSERVED_EXACT`.

## L2 → L3

E1 refuses gap fills. Theoretical L3 accepts them. The difference is \
NBA {nba['waterfall']['theo_minus_e1_gap_fiction']}¢ and \
P5 {p5['waterfall']['theo_minus_e1_gap_fiction']}¢.

## L3 → L4

L4 = NOT_AVAILABLE. No live fill tape. Modeled E1 must not be labeled actual.
"""


def _count_table(nba, p5, key) -> str:
    keys = sorted(set(nba[key]) | set(p5[key]))
    return "\n".join(f"| {k} | {nba[key].get(k, 0)} | {p5[key].get(k, 0)} |" for k in keys)


def _models(nba, p5) -> str:
    lines = [
        "# Execution model comparison",
        "",
        "Same trades. Different claims.",
        "",
        "| Model | NBA EV | P5 EV | Claim |",
        "|---|---:|---:|---|",
        f"| E0 | — | — | no fill |",
        f"| E1 | {_ev(nba,'EV_L3_E1')} | {_ev(p5,'EV_L3_E1')} | modeled occupancy |",
        f"| E_THEO | {_ev(nba,'EV_L3_E_THEO')} | {_ev(p5,'EV_L3_E_THEO')} | illegal promotion |",
        f"| 80→40 | {_ev(nba,'EV_80_40')} | {_ev(p5,'EV_80_40')} | Model A fallback |",
        f"| E3 | NOT_AVAILABLE | NOT_AVAILABLE | no coefficients |",
        f"| E4 | NOT_AVAILABLE | NOT_AVAILABLE | no L2 |",
        f"| L4 | NOT_AVAILABLE | NOT_AVAILABLE | no tape |",
        "",
        "## E2 q (partial=1)",
        "",
        "| q | NBA | P5 |",
        "|---|---:|---:|",
    ]
    for k in nba["e2"]:
        lines.append(
            f"| {k} | {nba['e2'][k].get('gross_expectancy')} | {p5['e2'][k].get('gross_expectancy')} |"
        )
    return "\n".join(lines) + "\n"


def _limits() -> str:
    return """# Data limitations

- 1-minute candles. Intrabar path is unknown.
- No historical L2, queue, or displayed size.
- No Momento live fill tape in this warehouse (L4 empty).
- Fees unresolved (gross ¢).
- Actual FIRST80 maker entry at 80 is unobserved; nominal 80 used.
- 80→40 Model A is itself a fill assumption on A1.
- persist_subsequent_min is lookahead if used as a fill gate (E1 does not use it).
- NCAAB working universe is P5 vs P5 (721), not warehouse 4099.
- P5 OOS n is small.
- A1 artifacts were not overwritten.
"""


def _inv(nba, p5, meta) -> str:
    def fmt(s):
        return "\n".join(f"- `{i['id']}` ok={i['ok']} {i.get('detail','')}" for i in s["invariants"] if i["id"] != "INV4_DECOMP_RECONCILES")

    return f"""# Research invariants

LIVE_EXECUTION_CHANGED = {meta.get('live_execution_changed')}

## NBA

{fmt(nba)}

INV4 identity_ok={nba['decomposition']['identity_ok']}

## NCAAB P5

{fmt(p5)}

INV4 identity_ok={p5['decomposition']['identity_ok']}

Splits remain TRAIN ≤2025-12-31, VAL ≤2026-03-15, else OOS. \
No parameter was selected on OOS. DRE_BASELINE_V1 uses pre-registered H=40 exact.
"""


def _report(nba, p5, meta) -> str:
    return f"""# Execution Integrity Engine — REPORT

{_exec(nba, p5, meta)}

---

## Question 1 — payoff structure

See `PAYOFF_STRUCTURE.md`. E1 hedge is rare (exact close at 40). \
Most 80→40 expectancy is stop protection vs hold, not A2.

## Question 2 — expectancy by layer

See executive table. L4 is absent. E1 ≤ 80→40 on the full sample \
(NBA {_ev(nba,'EV_L3_E1')} vs {_ev(nba,'EV_80_40')}; \
P5 {_ev(p5,'EV_L3_E1')} vs {_ev(p5,'EV_80_40')}).

## Question 3 — source of EV

Decomposition + waterfall. Stop protection vs hold is the large, \
robust increment. Theoretical hedge EV above E1 is gap fiction.

## Question 4 — execution sensitivity

E2 lowers modeled hedge completion and moves EV toward 80→40. \
E3/E4 cannot be fit.

## Question 5 — hierarchy leakage

L2 crossings that are gaps become V1 fills and disappear under E1.

## Question 6 — what may enter deterioration calculus

**Use 80→40 + L2 path labels as the baseline state space.** \
Do not take the derivative of a V1 locked −20. \
Do not treat E1 fills as L4.

Artifacts: `docs/research/EXECUTION_INTEGRITY_ENGINE/` \
(does not overwrite `docs/research/A1_HYBRID_HEDGE/`).
"""
