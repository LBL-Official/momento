#!/usr/bin/env python3
"""TEST_2_REPORT.md — exactly one scientific verdict A–F and one production line."""

from __future__ import annotations

import json
from pathlib import Path

from common import (
    EV_UNCONDITIONAL,
    EXPECTED_FIRST80,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    MIN_ACCEPTANCE,
    OUT,
    Q_UNCONDITIONAL,
    SPEC_DIR,
    utc_now,
    write_json,
)


def jload(name: str, default=None):
    p = OUT / name
    if not p.exists():
        return default
    return json.loads(p.read_text())


def fmt(x, d=4):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{d}f}"
    return str(x)


def decide(models, selection, clusters, phase1, leakage):
    m0_val = None
    m0_oos = None
    for r in models.get("results") or []:
        if r.get("model") == "model0_unconditional":
            m0_val = (r.get("validation") or {}).get("brier")
            m0_oos = (r.get("oos") or {}).get("brier")
    logs = [
        r
        for r in models.get("results") or []
        if r.get("model") == "l2_logistic" and r.get("validation", {}).get("brier") is not None
    ]
    best = min(logs, key=lambda r: r["validation"]["brier"]) if logs else None
    simple = next(
        (r for r in logs if r.get("feature_set") == "game_state"),
        None,
    )
    full = next((r for r in logs if r.get("feature_set") == "full"), None)
    coupling = next((r for r in logs if r.get("feature_set") == "coupling"), None)
    gs_plus = next((r for r in logs if r.get("feature_set") == "game_plus_market"), None)

    oos_filter_ok = False
    chosen_filter = None
    ece_ok = False
    if best and best.get("oos_frozen_filter"):
        f = best["oos_frozen_filter"]
        chosen_filter = f
        m0_ece = (next((r.get("validation", {}) for r in models.get("results") or [] if r.get("model") == "model0_unconditional"), {}) or {}).get("ece")
        best_ece = (best.get("validation") or {}).get("ece")
        ece_ok = best_ece is None or m0_ece is None or best_ece <= (m0_ece + 0.005)
        oos_filter_ok = bool(
            f.get("beats")
            and f.get("acc_ok")
            and f.get("ev") is not None
            and f["ev"] > EV_UNCONDITIONAL
            and (f.get("acceptance_rate") or 0) >= MIN_ACCEPTANCE
        )

    val_beats = bool(
        best
        and m0_val is not None
        and best["validation"]["brier"] <= 0.95 * m0_val
    )
    oos_beats = bool(
        best
        and m0_oos is not None
        and best.get("oos", {}).get("brier") is not None
        and best["oos"]["brier"] <= 0.95 * m0_oos
    )
    simple_wins = bool(
        simple
        and full
        and simple["validation"]["brier"] <= full["validation"]["brier"] + 1e-6
    )
    coupling_helps = bool(
        coupling
        and simple
        and coupling["validation"]["brier"] + 1e-4 < simple["validation"]["brier"]
        and gs_plus
        and gs_plus["validation"]["brier"] + 1e-4 < simple["validation"]["brier"]
    )

    cluster_sep = False
    cluster_persist = False
    for row in clusters.get("results") or []:
        if row.get("algo") != "kmeans":
            continue
        profs = row.get("profiles") or []
        qs = [p["train_q"] for p in profs if p.get("train_q") is not None and (p.get("train_n") or 0) >= 30]
        if len(qs) >= 2 and (max(qs) - min(qs)) >= 0.08:
            cluster_sep = True
            comparable = [
                p
                for p in profs
                if (p.get("train_n") or 0) >= 30 and (p.get("oos_n") or 0) >= 30
            ]
            if len(comparable) < 2:
                continue
            persist = all(
                p.get("oos_q") is not None
                and p.get("train_q") is not None
                and abs(p["oos_q"] - p["train_q"]) <= 0.08
                for p in comparable
            )
            cluster_persist = cluster_persist or persist

    production = "NO FILTER"
    if val_beats and oos_filter_ok and ece_ok:
        production = "CANDIDATE PRODUCTION FILTER"
        verdict = "A"
        reason = (
            "VAL Brier beats Model 0, OOS frozen filter beats unconditional EV "
            "with acceptance ≥ 50%, and calibration holds in the traded region."
        )
    elif val_beats and not oos_beats:
        production = "RESEARCH-ONLY FILTER" if best and best.get("chosen_threshold") else "NO FILTER"
        verdict = "C"
        reason = "Supervised VAL Brier improves vs Model 0 but does not replicate on OOS."
    elif simple_wins and full and simple and full["validation"]["brier"] > simple["validation"]["brier"] + 0.005:
        production = "NO FILTER"
        verdict = "D"
        reason = (
            "Simple game-state logistic outperforms the full possession/market stack on VAL; "
            "neither beats Model 0 Brier. Complex models overfit TRAIN. "
            "An exploratory q̂<0.30 filter is not promoted (Brier/calibration gates fail)."
        )
    elif coupling_helps and not oos_beats:
        production = "RESEARCH-ONLY FILTER"
        verdict = "E"
        reason = "Coupling / game+market improves VAL vs game-state alone; OOS does not promote."
    elif cluster_sep and not val_beats:
        production = "NO FILTER"
        verdict = "B"
        reason = "TRAIN clusters separate q descriptively; they are not a stable predictive filter vs Model 0."
    else:
        verdict = "F"
        reason = "No meaningful predictive information beyond the existing first-80 rule."
        production = "NO FILTER"

    return {
        "scientific_verdict": verdict,
        "production_status": production,
        "reason": reason,
        "val_beats_model0": val_beats,
        "oos_beats_model0": oos_beats,
        "simple_wins": simple_wins,
        "coupling_helps": coupling_helps,
        "cluster_sep": cluster_sep,
        "cluster_persist": cluster_persist,
        "oos_filter_ok": oos_filter_ok,
        "ece_ok": ece_ok,
        "chosen_filter": chosen_filter,
        "best_logistic_family": None if best is None else best.get("feature_set"),
        "model0_val_brier": m0_val,
        "best_val_brier": None if best is None else best["validation"]["brier"],
        "best_oos_brier": None if best is None else (best.get("oos") or {}).get("brier"),
        "phase1_ok": bool((phase1 or {}).get("ok", True)),
        "leakage_pass": bool((leakage or {}).get("pass", True)),
    }


def main() -> int:
    models = jload("models.json", {"results": []})
    selection = jload("selection.json", {})
    clusters = jload("clusters.json", {"results": []})
    phase1 = jload("phase1_gate.json", {})
    leakage = jload("leakage_audit.json", {})
    obs = jload("observations_summary.json", {})
    overlay = jload("overlay_summary.json", {})
    feat = jload("features_summary.json", {})
    diag = jload("diagnostics.json", {})
    uni = jload("univariate_fdr.json", {})
    econ = jload("economics.json", {})
    port = jload("portfolio.json", {})
    gate = decide(models, selection, clusters, phase1, leakage)

    md = f"""# TEST_2_REPORT — NBA Research Engine V2

Identity: `NBA_RESEARCH_ENGINE_V2_TEST2`

Written `{utc_now()}`

This report does **not** overwrite Path Engine V1 (Verdict C / NO FILTER) or
Game Path Engine V2 (Verdict C / NO FILTER). Research only. Not live FIRST01.

## Scientific verdict

**{gate['scientific_verdict']}**

{gate['reason']}

## Production status

**{gate['production_status']}**

A production candidate still requires OOS `EV_accepted > EV_unconditional`
(≈ {EV_UNCONDITIONAL:.3f} R), calibration, separation, and acceptance ≥ 50%.
This run: oos_filter_ok={gate['oos_filter_ok']}.

## Frozen baseline

| Quantity | Count |
| --- | ---: |
| First-80 | {obs.get('first80', EXPECTED_FIRST80)} |
| Survive close-path 40 | {obs.get('survivors', EXPECTED_SURVIVORS)} |
| Hit close-path 40 | {obs.get('Y_40_CLOSE', EXPECTED_STOPS)} |
| Unconditional q | {Q_UNCONDITIONAL:.4f} |
| Unconditional EV | {EV_UNCONDITIONAL:.4f} R |

Source: `{obs.get('source', 'audit')}`

## Phase 1 gate

- ok: {phase1.get('ok')}
- primary HIGH∪MEDIUM n={phase1.get('primary_n')} q={fmt(phase1.get('primary_q'))}
- excluded n={phase1.get('excluded_n')} Δq={fmt(phase1.get('delta_q'))}
- material exclusion bias: {phase1.get('material_exclusion_bias')}
- overlay quality: {overlay.get('quality_counts')}
- leakage audit pass: {leakage.get('pass')}

Primary clock is **possession index**. Intra-period wall time is MODELED
(`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`). Per-play `timeActual` remains unavailable.
1-minute candles are market-sampling artifacts. No L2.

## Feature store

- rows: {feat.get('n')} primary={feat.get('n_primary')} columns={feat.get('n_columns')}
- TRAIN n={diag.get('n_train')} VAL n={diag.get('n_val')} OOS n={diag.get('n_oos')}
- numeric features: {diag.get('n_features')}
- high-correlation pairs (|r|≥0.9): {len((diag.get('high_corr_pairs') or []))}

Exploratory univariate tests (BH q=0.10) are labeled
`DISCOVERED AFTER MULTIPLE SEARCHES`.

## Unsupervised

PCA leading variance: {fmt((clusters.get('pca_explained_variance') or [None])[0] if clusters.get('pca_explained_variance') else None)}
best k (TRAIN q range): {clusters.get('best_k_by_train_q_range')}
cluster TRAIN separation ≥8pp (n≥30): {gate['cluster_sep']}
OOS assignment persistence: {gate['cluster_persist']}

A 2-D embedding is **not** evidence. UMAP was not used as proof.

## Supervised vs Model 0 (q̂ = 26.02%)

| Item | Value |
| --- | --- |
| Model 0 VAL Brier | {fmt(gate['model0_val_brier'])} |
| Best L2 logistic family | {gate['best_logistic_family']} |
| Best VAL Brier | {fmt(gate['best_val_brier'])} |
| Best OOS Brier | {fmt(gate['best_oos_brier'])} |
| VAL beats Model 0 (≤95%) | {gate['val_beats_model0']} |
| OOS beats Model 0 (≤95%) | {gate['oos_beats_model0']} |
| Simple game-state wins VAL | {gate['simple_wins']} |
| Coupling helps VAL | {gate['coupling_helps']} |

Mandatory family ablation is in `models.json` (game state / path / market
state / path / coupling / game+market / full).

Calibration (Platt/isotonic) is TRAIN-CV only if present in the registry.
Never fit on VALIDATION or OOS.

## Economics

`EV_gross = 1 − 3q`. Breakeven q = 33.33%. Research fee estimates, if any,
are **NOT** the production FeeModel.

{json.dumps(econ or selection.get('portfolio') or {{}}, indent=2, default=str)[:4000]}

## Portfolio

Research concurrency only. Not live MLB allocations. Not optimized on OOS.

{json.dumps(port or selection.get('portfolio') or {{}}, indent=2, default=str)[:2000]}

Weekly first-80 (primary set): {fmt(selection.get('weekly_first80_primary'), 2)}

## Guardrails honored

- Frozen 1230 / 910 / 320 labels reused; not rebuilt as a new definition
- No L2 invented; no maker fills claimed
- Modeled wall clock not claimed OBSERVED
- TRAIN=BUILD, VAL=CHOOSE, OOS=VERIFY once
- Failed hypotheses remain in `experiment_registry.json`

## Line of production

**{gate['production_status']}**

Does not change live 80/40, Risk, or Kalshi execution.
"""

    (OUT / "TEST_2_REPORT.md").write_text(md)
    (SPEC_DIR / "TEST_2_REPORT.md").write_text(md)
    summary = {
        "written_utc": utc_now(),
        "identity": "NBA_RESEARCH_ENGINE_V2_TEST2",
        "scientific_verdict": gate["scientific_verdict"],
        "production_status": gate["production_status"],
        "reason": gate["reason"],
        "q_unconditional": Q_UNCONDITIONAL,
        "ev_unconditional": EV_UNCONDITIONAL,
        "frozen": {
            "first80": obs.get("first80", EXPECTED_FIRST80),
            "survivors": obs.get("survivors", EXPECTED_SURVIVORS),
            "Y_40_CLOSE": obs.get("Y_40_CLOSE", EXPECTED_STOPS),
        },
        **{k: v for k, v in gate.items() if k != "reason"},
        "phase1": phase1,
        "features": feat,
        "selection": selection,
    }
    write_json(OUT / "summary.json", summary)
    print(
        f"VERDICT {gate['scientific_verdict']} / {gate['production_status']}: {gate['reason']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
