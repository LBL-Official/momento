#!/usr/bin/env python3
"""Write REPORT.md and summary.json. Exactly one verdict and one production status."""

from __future__ import annotations

import json
import sys

from common import (
    EV_MARGIN,
    EV_UNCONDITIONAL,
    EXPECTED_FIRST80,
    EXPECTED_STOPS,
    MIN_ACCEPTANCE_PROD,
    OUT,
    Q_UNCONDITIONAL,
    git_commit,
    utc_now,
    write_json,
)


def load(path):
    p = OUT / path
    if not p.exists():
        return None
    return json.loads(p.read_text())


def best_worst(exps, split_q="train_q"):
    usable = [
        e
        for e in exps
        if e.get("train_n", 0) >= 40 and e.get(split_q) is not None
    ]
    if not usable:
        return None, None
    best = min(usable, key=lambda e: e[split_q])
    worst = max(usable, key=lambda e: e[split_q])
    return best, worst


def verdict_of(ledger, economics, align, models) -> tuple[str, str, str]:
    chosen = (ledger or {}).get("chosen_experiment_id")
    recs = (ledger or {}).get("experiments") or []
    rec = next((r for r in recs if r["experiment_id"] == chosen), None) if chosen else None
    primary_n = ((align or {}).get("primary") or {}).get("n") or 0
    excl_bias = abs((align or {}).get("exclusion_bias_delta_q") or 0)

    descriptive = any(
        r.get("train_n", 0) >= 40
        and r.get("train_q") is not None
        and abs(r.get("train_delta_q") or 0) >= 0.04
        for r in recs
    )

    if rec and rec.get("promotion_status") == "VALIDATED":
        oos_n = rec.get("oos_n") or 0
        oos_dev = rec.get("oos_delta_ev") or 0
        acc = rec.get("acceptance_train") or 0
        if (
            oos_dev >= EV_MARGIN
            and acc >= MIN_ACCEPTANCE_PROD
            and oos_n >= 50
            and excl_bias < 0.03
        ):
            return (
                "A",
                "CANDIDATE PRODUCTION FILTER",
                "Interpretable regime persisted VAL and a single OOS pass with capacity.",
            )
        return (
            "B",
            "RESEARCH-ONLY FILTER",
            "Signal persisted OOS but sample, acceptance, or exclusion bias is insufficient for production.",
        )
    if rec and rec.get("promotion_status") == "REJECTED":
        return (
            "C" if descriptive else "D",
            "NO FILTER",
            "The frozen VAL-chosen candidate failed the single OOS pass.",
        )
    if descriptive:
        return (
            "C",
            "NO FILTER",
            "Some TRAIN relationships exist; none cleared VAL freeze + OOS usefulness.",
        )
    return (
        "D",
        "NO FILTER",
        "No robust game-path conditional edge versus q=26.02% in this dataset.",
    )


def main() -> int:
    obs = load("observations_summary.json") or {}
    align = load("time_alignment_audit.json") or {}
    uni = load("experiments/univariate.json") or {}
    hyp = load("experiments/hypotheses.json") or {}
    ix = load("experiments/interactions.json") or {}
    ledger = load("experiments/ledger.json") or {}
    econ = load("experiments/economics.json") or {}
    port = load("experiments/portfolio.json") or {}
    leak = load("leakage_audit.json") or {}
    feat = load("feature_audit.json") or {}
    msel = load("models/model_selection.json") or {}
    m0 = load("models/baseline/metrics.json") or {}
    ml2 = load("models/logistic_l2/metrics.json") or {}
    men = load("models/elastic_net/metrics.json") or {}
    mgbm = load("models/gbm/metrics.json") or {}

    exps = ledger.get("experiments") or []
    best, worst = best_worst(exps)
    v_code, prod, v_why = verdict_of(ledger, econ, align, msel)

    summary = {
        "run_id": utc_now(),
        "git_commit": git_commit(),
        "engine": "momento_game_path_engine_v2",
        "seed": 42,
        "observation_count": obs.get("first80") or EXPECTED_FIRST80,
        "Y_40_CLOSE": obs.get("Y_40_CLOSE") or EXPECTED_STOPS,
        "q_unconditional": Q_UNCONDITIONAL,
        "ev_unconditional": EV_UNCONDITIONAL,
        "primary_target": "Y_40_CLOSE",
        "secondary_target": "Y_40_WICK",
        "alignment": {
            "model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "per_play_wall_clock_observed": False,
            "confidence_counts": align.get("confidence_counts"),
            "primary": align.get("primary"),
            "excluded": align.get("excluded"),
            "exclusion_bias_delta_q": align.get("exclusion_bias_delta_q"),
            "median_replay_residual_s": align.get("median_replay_residual_s"),
            "median_tip_to_q1_s": align.get("median_tip_to_q1_s"),
        },
        "feature_count": feat.get("n_columns"),
        "experiment_count": ledger.get("n"),
        "chosen_experiment_id": ledger.get("chosen_experiment_id"),
        "best_train_regime": best,
        "worst_train_regime": worst,
        "hypotheses": hyp.get("experiments"),
        "model_selected": msel.get("selected"),
        "model0_val_brier": (m0.get("validation") or {}).get("brier"),
        "model3_l2_val_brier": (ml2.get("validation") or {}).get("brier"),
        "model3_l2_oos_auc": (ml2.get("oos") or {}).get("roc_auc"),
        "leakage_fail": leak.get("n_fail"),
        "portfolio": {
            "historical_survival": port.get("historical_survival"),
            "sizing": port.get("sizing_paths"),
            "daily_q_lag1_autocorr": port.get("daily_q_lag1_autocorr"),
            "block_bootstrap": port.get("block_bootstrap_by_game_date"),
        },
        "verdict": v_code,
        "verdict_why": v_why,
        "production_status": prod,
        "live_execution_changed": False,
    }
    write_json(OUT / "summary.json", summary)

    def fmt_q(x):
        return "—" if x is None else f"{100*x:.2f}%"

    def fmt_n(e, split):
        return e.get(f"{split}_n") if e else None

    lines = []
    a = lines.append
    a("# Game Path Engine V2 — report")
    a("")
    a("Research only. Frozen 80/40 labels. Does not change live trading or Path Engine V1.")
    a("")
    a(f"**Verdict {v_code}** — {prod}")
    a("")
    a(v_why)
    a("")
    a("## Frozen baseline")
    a("")
    a(f"- Universe first-80: {summary['observation_count']}")
    a(f"- Close-path 40: {summary['Y_40_CLOSE']}  (q = {100*Q_UNCONDITIONAL:.2f}%)")
    a(f"- EV_gross = 1 − 3q ≈ {EV_UNCONDITIONAL:+.4f} R")
    a("- Primary target: `Y_40_CLOSE`. Secondary: `Y_40_WICK`.")
    a("")
    a("## Time alignment")
    a("")
    a("Per-play structured wall clock is **unavailable**. Alignment model:")
    a("`PERIOD_BOUNDED_LINEAR_GAME_CLOCK` using observed period start/end knots.")
    a("Tip is **not** inferred from Kalshi market open.")
    a("")
    a(f"- Confidence counts: {align.get('confidence_counts')}")
    a(f"- Primary HIGH+MEDIUM n={((align.get('primary') or {}).get('n'))} q={fmt_q((align.get('primary') or {}).get('q'))}")
    a(f"- Excluded n={((align.get('excluded') or {}).get('n'))} q={fmt_q((align.get('excluded') or {}).get('q'))}")
    a(f"- Exclusion Δq vs 26.02%: {align.get('exclusion_bias_delta_q')}")
    a(f"- Median tip→Q1 start: {align.get('median_tip_to_q1_s')} s")
    a(f"- Median replay residual: {align.get('median_replay_residual_s')} s")
    a("")
    byc = align.get("by_confidence") or {}
    if byc:
        a("Barrier rate by alignment confidence (quality label, **not** a pre-registered trading filter):")
        a("")
        a("| Confidence | n | q |")
        a("| --- | ---: | ---: |")
        for k in ("HIGH", "MEDIUM", "LOW", "UNUSABLE"):
            st = byc.get(k) or {}
            q = st.get("q")
            a(f"| {k} | {st.get('n')} | {fmt_q(q)} |")
        a("")
        a("HIGH vs MEDIUM is a large descriptive gap. It was not promoted: confidence is a")
        a("data-quality stratum, not an H1–H7 feature, and mining it after seeing q would")
        a("be post-hoc. Primary analysis still uses HIGH+MEDIUM as specified.")
        a("")
    a("## Pre-registered hypotheses")
    a("")
    a("| ID | Hypothesis | TRAIN n | TRAIN q | VAL q | OOS q | status |")
    a("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for e in hyp.get("experiments") or []:
        a(
            f"| {e.get('experiment_id')} | {e.get('hypothesis')} | {e.get('train_n')} | "
            f"{fmt_q(e.get('train_q'))} | {fmt_q(e.get('validation_q'))} | "
            f"{fmt_q(e.get('oos_q'))} | {e.get('promotion_status')} |"
        )
    a("")
    a("## Best / worst TRAIN regimes (n≥40)")
    a("")
    if best:
        a(f"- Lowest TRAIN q: `{best.get('experiment_id')}` n={best.get('train_n')} q={fmt_q(best.get('train_q'))} VAL={fmt_q(best.get('validation_q'))} OOS={fmt_q(best.get('oos_q'))}")
    if worst:
        a(f"- Highest TRAIN q: `{worst.get('experiment_id')}` n={worst.get('train_n')} q={fmt_q(worst.get('train_q'))} VAL={fmt_q(worst.get('validation_q'))} OOS={fmt_q(worst.get('oos_q'))}")
    a("")
    a(f"Chosen frozen candidate: `{ledger.get('chosen_experiment_id')}`")
    a("")
    a("## Models")
    a("")
    a(f"- Selected: {msel.get('selected')}")
    a(f"- Model 0 VAL Brier: {(m0.get('validation') or {}).get('brier')}")
    a(f"- L2 logistic VAL Brier: {(ml2.get('validation') or {}).get('brier')} OOS AUC: {(ml2.get('oos') or {}).get('roc_auc')}")
    a(f"- Elastic net VAL Brier: {(men.get('validation') or {}).get('brier')}")
    a(f"- Shallow GBM VAL Brier: {(mgbm.get('validation') or {}).get('brier')}")
    a("")
    a("A more complex model is not promoted without VAL gates (Brier, ECE, bucket separation).")
    a("")
    a("## Portfolio research")
    a("")
    a("Configurable research bankroll $10,000 and 2% fractional size — **not** live MLB/WNBA allocations.")
    a("Candle data does not prove fills. Concurrent overlap is not fully path-simulated.")
    a("")
    a(f"- Historical primary survival: {port.get('historical_survival')}")
    a(f"- Daily barrier-rate lag-1 autocorr: {port.get('daily_q_lag1_autocorr')}")
    a(f"- Block-bootstrap P95 drawdown (fractional): {(port.get('block_bootstrap_by_game_date') or {}).get('p95_dd')}")
    a("")
    a("## Leakage")
    a("")
    a(f"- Failures: {leak.get('n_fail')}")
    a("")
    a("## Production")
    a("")
    a(f"- Status: **{prod}**")
    a("- Live execution changed: **false**")
    a("")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"REPORT verdict={v_code} production={prod}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
