#!/usr/bin/env python3
"""Write warehouse reports. One scientific verdict. One production line. No 'production ready'."""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict

from common import (
    BREAKEVEN_Q,
    EV_UNCONDITIONAL,
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    MODELS,
    OBS,
    OUT,
    PORT,
    Q_UNCONDITIONAL,
    REP,
    SPEC_DIR,
    ev_from_q,
    read_parquet_rows,
    utc_now,
    write_json,
)


def load(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def pct(x, d=2):
    if x is None:
        return "—"
    return f"{100.0 * x:.{d}f}%"


def num(x, d=3):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def decide(model, port, uni):
    selected = model.get("selected_model") or "model0"
    oos = model.get("oos_selected") or {}
    oos_m0 = (model.get("oos") or {}).get("model0") or {}
    val = model.get("validation_selected") or {}
    gates = model.get("gates") or {}
    hold_oos = ((port.get("splits") or {}).get("OOS") or {}).get("hold_all") or {}
    skip_oos = ((port.get("splits") or {}).get("OOS") or {}).get("skip_high_p") or {}
    hold_val = ((port.get("splits") or {}).get("VALIDATION") or {}).get("hold_all") or {}
    skip_val = ((port.get("splits") or {}).get("VALIDATION") or {}).get("skip_high_p") or {}
    b0 = oos_m0.get("brier")
    bs = oos.get("brier")
    brier_lift_oos = b0 is not None and bs is not None and bs <= 0.95 * b0
    val_improve = gates.get("brier_improve_vs_m0") is True
    ece_ok = gates.get("ece_ok", False)
    ev_val = skip_val.get("mean_R")
    ev_hold_val = hold_val.get("mean_R")
    ev_oos = skip_oos.get("mean_R")
    ev_hold_oos = hold_oos.get("mean_R")
    ev_lift_val = ev_val is not None and ev_hold_val is not None and ev_val >= ev_hold_val + 0.02
    ev_lift_oos = ev_oos is not None and ev_hold_oos is not None and ev_oos >= ev_hold_oos + 0.02
    acc = skip_oos.get("acceptance_rate") or 0.0
    n_acc = skip_oos.get("n_accepted") or 0
    baseline_only = selected == "model0"

    reasons = {
        "selected": selected,
        "val_improve": val_improve,
        "brier_lift_oos": brier_lift_oos,
        "ece_ok": ece_ok,
        "ev_lift_val": ev_lift_val,
        "ev_lift_oos": ev_lift_oos,
        "oos_acceptance": acc,
        "oos_n_accepted": n_acc,
        "baseline_only": baseline_only,
    }
    if baseline_only or not val_improve:
        return (
            "C — NO ROBUST CONDITIONAL STRUCTURE",
            "NO PRODUCTION CHANGE",
            reasons,
        )
    if (
        val_improve
        and brier_lift_oos
        and ece_ok
        and ev_lift_val
        and ev_lift_oos
        and n_acc >= 80
        and acc >= 0.20
    ):
        return (
            "A — ROBUST CONDITIONAL STRUCTURE",
            "CANDIDATE FOR EXECUTION AUDIT",
            reasons,
        )
    if val_improve and (brier_lift_oos or ev_lift_val):
        return (
            "B — PROMISING BUT UNRESOLVED",
            "RESEARCH-ONLY CANDIDATE",
            reasons,
        )
    return (
        "C — NO ROBUST CONDITIONAL STRUCTURE",
        "NO PRODUCTION CHANGE",
        reasons,
    )


def main() -> int:
    uni_sum = load(OUT / "trade_universe_summary.json")
    state_sum = load(OUT / "state_build_summary.json")
    uni = load(MODELS / "model1_univariate" / "results.json")
    model = load(MODELS / "model_results.json")
    port = load(PORT / "portfolio_simulation.json")
    leak = load(OUT / "leakage_audit.json")
    couple = load(MODELS / "coupling" / "empirical_delta.json")
    regimes = load(MODELS / "regimes" / "boundaries.json")
    edge = load(PORT / "edge_decay.json")
    ruin = load(PORT / "ruin_simulations.json")

    verdict, production, reasons = decide(model, port, uni)

    states = read_parquet_rows(OBS / "first80_game_state.parquet")
    barriers = read_parquet_rows(OBS / "barrier_distribution.parquet")
    align = Counter(r.get("alignment_confidence") for r in states)
    game_ok = sum(1 for r in states if r.get("game_feature_status") == "AVAILABLE")
    reg_c = Counter(r.get("regime") for r in states)

    hit_rates = {}
    for x in (75, 70, 65, 60, 55, 50, 45, 40):
        k = sum(int(r.get(f"hit_{x}") or 0) for r in barriers)
        hit_rates[str(x)] = k / len(barriers) if barriers else None

    # Feature dictionary
    cat_map = {
        "game_": "G_t game",
        "market_": "M_t market",
        "path_": "P_t path",
        "dyn_": "D_t dynamics",
        "econ_": "E_t economics",
        "coupling_": "coupling",
        "ix_": "preregistered interaction",
        "alignment_": "alignment provenance",
        "Y_": "target",
        "H_": "target",
    }
    skip = {
        "trade_id",
        "event_id",
        "ticker",
        "game_date",
        "dataset_split",
        "entry_timestamp",
        "state_timestamp",
        "feature_maximum_source_timestamp",
        "same_bar_limitation",
        "game_phase",
        "per_play_wall_clock_observed",
        "game_feature_status",
        "regime",
        "regime_source",
        "volatility_kind",
    }
    fd_lines = ["# V4 feature dictionary", "", "Prefixes are the state-block identity. Do not flatten.", ""]
    fd_lines.append("| feature | block |")
    fd_lines.append("| --- | --- |")
    keys = sorted({k for r in states[:1] for k in r})
    if states:
        keys = sorted(states[0].keys())
    for k in keys:
        if k in skip:
            fd_lines.append(f"| `{k}` | meta |")
            continue
        block = "other"
        for p, lab in cat_map.items():
            if k.startswith(p):
                block = lab
                break
        fd_lines.append(f"| `{k}` | {block} |")
    (REP / "feature_dictionary.md").parent.mkdir(parents=True, exist_ok=True)
    (REP / "feature_dictionary.md").write_text("\n".join(fd_lines) + "\n")

    if (SPEC_DIR / "MATHEMATICAL_FOUNDATION.md").exists():
        shutil.copyfile(SPEC_DIR / "MATHEMATICAL_FOUNDATION.md", REP / "mathematical_model.md")
    if (SPEC_DIR / "HYPOTHESIS_LEDGER.csv").exists():
        shutil.copyfile(SPEC_DIR / "HYPOTHESIS_LEDGER.csv", REP / "hypothesis_ledger.csv")
        # overlay statuses
        tests = uni.get("tests") or {}
        fields = ["hypothesis_id", "block", "name", "definition", "split_role", "status"]
        rows_csv = []
        with (REP / "hypothesis_ledger.csv").open(newline="") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                hid = (row.get("hypothesis_id") or "").strip()
                rec = {k: (row.get(k) or "") for k in fields}
                rec["hypothesis_id"] = hid
                if hid in tests and tests[hid].get("status"):
                    rec["status"] = tests[hid]["status"]
                if hid:
                    rows_csv.append(rec)
        with (REP / "hypothesis_ledger.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows_csv)

    oos_sel = model.get("oos_selected") or {}
    val_sel = model.get("validation_selected") or {}
    hold_oos = ((port.get("splits") or {}).get("OOS") or {}).get("hold_all") or {}
    skip_oos = ((port.get("splits") or {}).get("OOS") or {}).get("skip_high_p") or {}
    hold_val = ((port.get("splits") or {}).get("VALIDATION") or {}).get("hold_all") or {}
    skip_val = ((port.get("splits") or {}).get("VALIDATION") or {}).get("skip_high_p") or {}
    grad = (model.get("barrier_risk_gradient_at_train_median") or {}).get("partials_per_raw_unit") or []

    a = []
    ap = a.append
    ap("# Game Path Engine V4 — report")
    ap("")
    ap("Research only. Identifier: `MOMENTO_GAME_PATH_ENGINE_V4`.")
    ap("")
    ap("Does not modify live FIRST01, Kalshi execution, Risk, V1, V2, V3, MLB research,")
    ap("or NBA production infrastructure.")
    ap("")
    ap(f"**Scientific verdict: {verdict}**")
    ap("")
    ap(f"**Production line: {production}**")
    ap("")
    ap("The report does not claim production ready. Outcomes A, B, and C are equally valid.")
    ap("A negative result is a successful scientific outcome.")
    ap("")
    ap("LIVE EXECUTION CHANGED: FALSE")
    ap("")
    ap("## Frozen baseline")
    ap("")
    ap(f"- Games: {uni_sum.get('games')} (expected {EXPECTED_GAMES})")
    ap(f"- First-80: {uni_sum.get('first80')} (expected {EXPECTED_FIRST80})")
    ap(f"- Close-path 40: {uni_sum.get('Y_40_CLOSE')} (expected {EXPECTED_STOPS})")
    ap(f"- Survivors: {uni_sum.get('survivors')} (expected {EXPECTED_SURVIVORS})")
    ap(f"- Reproduction: {'PASS' if uni_sum.get('baseline_ok') else 'FAIL'}")
    ap(f"- Unconditional q = {pct(Q_UNCONDITIONAL)} ; EV = 1−3q ≈ {num(EV_UNCONDITIONAL, 4)} R")
    ap(f"- Breakeven barrier rate q* = 1/3 ; Barrier-Risk Margin = {pct(BREAKEVEN_Q - Q_UNCONDITIONAL)}")
    ap("")
    ap("## State construction")
    ap("")
    ap(f"- Entry states: {state_sum.get('n_entry')}")
    ap(f"- Alive-minute panel rows: {state_sum.get('n_panel')}")
    ap(f"- Game-state AVAILABLE at entry: {game_ok}")
    ap(f"- Alignment counts: {dict(align)}")
    ap("- Alignment method: PERIOD_BOUNDED_LINEAR_GAME_CLOCK")
    ap("- Per-play wall clock observed: FALSE. Tip-off is gameTimeUTC, never Kalshi open.")
    ap("- MEDIUM is never upgraded to HIGH.")
    ap("- Volatility kind: 1-MINUTE CANDLE VOLATILITY PROXY")
    ap("")
    ap("## Leakage")
    ap("")
    ap(f"- Status: {leak.get('pipeline_status')}")
    ap(f"- Rows with source timestamp after state: {leak.get('n_rows_source_after_state')}")
    ap("- Same-bar 1-minute limitation is labeled, not hidden.")
    ap("")
    ap("## Empirical coupling (TRAIN OLS)")
    ap("")
    ap("Model: ΔK = β0 + β1 Δd + β2 τ + β3 Δd·τ")
    ap("This is an empirical sensitivity, not a Black–Scholes Greek.")
    ap("")
    ap(f"- TRAIN steps: {couple.get('n_train_steps')}")
    ap(f"- β: {couple.get('beta')}")
    ap("")
    ap("## Barrier curve (unconditional, close path after entry)")
    ap("")
    ap("| barrier ¢ | empirical P(min K ≤ x) |")
    ap("| ---: | ---: |")
    for x, q in hit_rates.items():
        ap(f"| {x} | {pct(q)} |")
    ap("")
    ap("## Interpretable regimes (TRAIN percentile boundaries, frozen)")
    ap("")
    ap(f"- Boundaries: `{regimes}`")
    ap(f"- Counts: {dict(reg_c)}")
    hr1 = ((uni.get("tests") or {}).get("HR1") or {}).get("train") or {}
    ap("")
    ap("| regime | n | q |")
    ap("| --- | ---: | ---: |")
    for k, v in hr1.items():
        ap(f"| {k} | {v.get('n')} | {pct(v.get('q'))} |")
    ap("")
    ap("## Model 1 (univariate, TRAIN discovery)")
    ap("")
    ap("| id | feature | TRAIN spearman | VAL spearman | status |")
    ap("| --- | --- | ---: | ---: | --- |")
    for hid, payload in (uni.get("tests") or {}).items():
        if hid in ("H0", "HR1"):
            continue
        ap(
            f"| {hid} | {payload.get('feature')} | "
            f"{num(payload.get('train_spearman_q_vs_mid'), 3)} | "
            f"{num(payload.get('val_spearman_q_vs_mid'), 3)} | {payload.get('status')} |"
        )
    ap("")
    ap("OOS Spearman is a frozen evaluation, not a discovery statistic.")
    ap("")
    ap("## Models 0–4")
    ap("")
    ap(f"- VALIDATION selected: `{model.get('selected_model')}`")
    ap(f"- GBM built: {model.get('gbm_built')}")
    ap(f"- VAL selected Brier: {num(val_sel.get('brier'), 5)} ; AUC {num(val_sel.get('auc'), 3)}")
    ap(f"- OOS selected Brier: {num(oos_sel.get('brier'), 5)} ; AUC {num(oos_sel.get('auc'), 3)}")
    ap(f"- VAL Model 0 Brier: {num(((model.get('validation') or {}).get('model0') or {}).get('brier'), 5)}")
    ap(f"- OOS Model 0 Brier: {num(oos_m0_brier := ((model.get('oos') or {}).get('model0') or {}).get('brier'), 5)}")
    ap("")
    ap("Gates:")
    ap("")
    ap(f"- `{reasons}`")
    ap("")
    ap("## Barrier-risk gradient (L2 logistic, TRAIN-median finite differences)")
    ap("")
    ap("These are local sensitivities of q̂(S), not causal effects.")
    ap("")
    ap("| coordinate | Δq per raw unit |")
    ap("| --- | ---: |")
    for g in grad:
        ap(f"| {g.get('coordinate')} | {num(g.get('dq_per_unit'), 5)} |")
    ap("")
    ap("## Trade economics")
    ap("")
    ap("Research R-units: survive +1R, close-path 40 −2R, EV=1−3q.")
    ap("Cash map for sizing research: win +0.25, loss −0.50 of allocated notional.")
    ap("Not KalshiFeeModel. Not fills. Sample-size warning: LOW_SHORT_SAMPLE_NON_IID.")
    ap("")
    ap(f"- VAL hold-all EV: {num(hold_val.get('mean_R'), 4)} R (n={hold_val.get('n')})")
    ap(f"- VAL skip-high-p EV: {num(skip_val.get('mean_R'), 4)} R accept={pct(skip_val.get('acceptance_rate'))}")
    ap(f"- OOS hold-all EV: {num(hold_oos.get('mean_R'), 4)} R")
    ap(f"- OOS skip-high-p EV: {num(skip_oos.get('mean_R'), 4)} R accept={pct(skip_oos.get('acceptance_rate'))}")
    ap("")
    ap("## Portfolio / ruin / edge")
    ap("")
    ap(f"- Research bankroll $10,000 ; fraction 2% of **current** equity ; max concurrent 5.")
    ap("- Not live MLB 12.5% sizing. Full Kelly is research-only.")
    ap(f"- Kelly f*: {num((port.get('kelly') or {}).get('f_star_full'), 4)}")
    ap(f"- Same-day dependence: {port.get('dependence')}")
    ap(f"- Edge-decay margin at q0: {pct((edge.get('margin0')))}")
    ap("")
    ap("Ruin uses defined capital-loss thresholds. Finite simulations that never hit zero")
    ap("are not reported as 0% ruin.")
    ap("")
    if ruin:
        hist = ruin.get("historical_block") or ruin.get("0.74") or {}
        ap(f"- Historical/block P(equity < 80%): {pct(hist.get('P_equity_below_80pct'))}")
        ap(f"- Historical/block P(equity < 50%): {pct(hist.get('P_equity_below_50pct'))}")
    ap("")
    ap("## Verdict")
    ap("")
    ap(f"{verdict}")
    ap("")
    ap(f"{production}")
    ap("")
    ap("V4 asked whether observable game/market/path/economic state variables govern the")
    ap("path distribution of an 80¢ NBA binary after FIRST-80, beyond the unconditional")
    ap("26.02% close-path-40 rate. The selected model and frozen OOS pass are the answer.")
    ap("")
    ap("LIVE EXECUTION CHANGED: FALSE")
    ap("")

    (REP / "REPORT.md").write_text("\n".join(a) + "\n")
    (OUT / "REPORT.md").write_text("\n".join(a) + "\n")
    summary = {
        "written_utc": utc_now(),
        "engine": "MOMENTO_GAME_PATH_ENGINE_V4",
        "verdict": verdict,
        "production": production,
        "live_execution_changed": False,
        "reasons": reasons,
        "frozen": {
            "games": uni_sum.get("games"),
            "first80": uni_sum.get("first80"),
            "Y_40_CLOSE": uni_sum.get("Y_40_CLOSE"),
            "survivors": uni_sum.get("survivors"),
            "q": Q_UNCONDITIONAL,
            "ev": EV_UNCONDITIONAL,
            "baseline_ok": uni_sum.get("baseline_ok"),
        },
        "n_entry": state_sum.get("n_entry"),
        "n_panel": state_sum.get("n_panel"),
        "alignment": dict(align),
        "game_available": game_ok,
        "regimes": dict(reg_c),
        "barrier_hit_rates": hit_rates,
        "selected_model": model.get("selected_model"),
        "gbm_built": model.get("gbm_built"),
        "validation_selected": val_sel,
        "oos_selected": oos_sel,
        "oos_model0": (model.get("oos") or {}).get("model0"),
        "val_model0": (model.get("validation") or {}).get("model0"),
        "val_models": {k: v for k, v in (model.get("validation") or {}).items()},
        "oos_models": {k: v for k, v in (model.get("oos") or {}).items()},
        "gradient": grad,
        "coupling_beta": couple.get("beta"),
        "coupling_n": couple.get("n_train_steps"),
        "univariate": {k: {"status": v.get("status"), "rho_train": v.get("train_spearman_q_vs_mid"), "rho_val": v.get("val_spearman_q_vs_mid"), "feature": v.get("feature")} for k, v in (uni.get("tests") or {}).items()},
        "portfolio": {
            "val_hold": hold_val,
            "val_skip": skip_val,
            "oos_hold": hold_oos,
            "oos_skip": skip_oos,
            "kelly_f_star": (port.get("kelly") or {}).get("f_star_full"),
            "kelly_compare": (port.get("kelly") or {}).get("compare"),
            "oos_equity": port.get("oos_equity"),
            "dependence": port.get("dependence"),
        },
        "ruin": {
            k: {
                "P80": (v or {}).get("P_equity_below_80pct") if isinstance(v, dict) else None,
                "P70": (v or {}).get("P_equity_below_70pct") if isinstance(v, dict) else None,
                "P50": (v or {}).get("P_equity_below_50pct") if isinstance(v, dict) else None,
            }
            for k, v in (ruin.items() if isinstance(ruin, dict) else [])
            if k != "beta_posterior_p"
        },
        "beta_posterior_p": ruin.get("beta_posterior_p") if isinstance(ruin, dict) else None,
        "edge_decay": edge,
        "hr1_train": hr1,
        "lsi": {"lambda": regimes.get("lsi_lambda"), "gamma": regimes.get("lsi_gamma")},
        "leakage": leak.get("pipeline_status"),
    }
    write_json(OUT / "summary.json", summary)
    write_json(REP / "summary.json", summary)
    print(f"REPORT {verdict} | {production}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
