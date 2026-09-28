"""Generate DRE V2 research reports from computed artifacts. No invented metrics."""

from __future__ import annotations

from . import config as C
from .models import pick
from .target_delta import corner_note


def _f(v, d=3):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _table(model_rows, targets, families, split="OOS"):
    lines = [
        "| Target | " + " | ".join(f"{f} AUC" for f in families) + " | " + " | ".join(f"{f} Brier" for f in families) + " |",
        "|--------|" + "|".join(["-------:"] * len(families) * 2) + "|",
    ]
    for t in targets:
        aucs = [_f(pick(model_rows, f, t, split, "auc")) for f in families]
        briers = [_f(pick(model_rows, f, t, split, "brier")) for f in families]
        lines.append(f"| `{t}` | " + " | ".join(aucs + briers) + " |")
    return "\n".join(lines)


def write_reports(ctx: dict) -> None:
    v = ctx["verdict"]
    g = ctx["gates"]
    c = ctx["counts"]
    mr = ctx["model_rows"]
    fams = ["B0", "B1", "B2", "M3", "M4", "M5"]
    primary = [
        "y_settle_yes",
        "y_rec_ge_10_k5",
        "y_rec_ge_10_end",
        "y_det_ge_10_k5",
        "y_det_ge_10_end",
        "y_min_le_50_k5",
        "y_jump_40",
    ]

    main = _main_report(ctx, v, g, c, mr, fams, primary)
    card = _model_card(ctx, v, mr, fams)
    verdict = _verdict_doc(ctx, v, g)
    asym = _asymmetry_doc(ctx)

    (C.DOCS / "MOMENTO_DYNAMIC_RISK_ENGINE_V2.md").write_text(main)
    (C.DOCS / "DRE_V2_MODEL_CARD.md").write_text(card)
    (C.DOCS / "DRE_V2_RESEARCH_VERDICT.md").write_text(verdict)
    (C.DOCS / "EXPOSURE_ASYMMETRY_REPORT.md").write_text(asym)
    (C.OUT / "15_reports" / "MOMENTO_DYNAMIC_RISK_ENGINE_V2.md").write_text(main)
    (C.OUT / "15_reports" / "DRE_V2_MODEL_CARD.md").write_text(card)
    (C.OUT / "15_reports" / "DRE_V2_RESEARCH_VERDICT.md").write_text(verdict)
    (C.OUT / "15_reports" / "EXPOSURE_ASYMMETRY_REPORT.md").write_text(asym)


def finish_from_artifacts() -> None:
    """Write reports and run_manifest from a completed artifact tree (no model refit)."""
    import json
    import platform
    import subprocess
    import sys

    def load(rel):
        return json.loads((C.OUT / rel).read_text())

    dash = load("16_dashboard/dashboard.json")
    model_rows = C.read_parquet_rows(C.OUT / "08_models" / "model_metrics.parquet")
    incremental = load("08_models/incremental_vs_B0.json")
    leak = load("05_leakage_audit/LEAKAGE_AUDIT.json")
    split_sum = load("02_frozen_universe/split_isolation.json")
    integrity = load("01_input_manifest/pade_integrity.json")
    counts = load("03_state_panel/counts.json")
    try:
        git = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=C.REPO, stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        git = None

    def pick_m(fam, target, split, field):
        for m in model_rows:
            if m["family"] == fam and m["target"] == target and m["split"] == split:
                return m.get(field)
        return None

    ctx = {
        "verdict": dash["verdict"],
        "gates": dash["gates"],
        "counts": counts,
        "universe": dash["unresolved"]["universe"],
        "unresolved": dash["unresolved"],
        "model_rows": model_rows,
        "incremental": incremental,
        "incremental_oos": dash["incremental_oos"],
        "control_oos": {
            "B0_auc": pick_m("B0", "y_min_le_40_k5", "OOS", "auc"),
            "M3_auc": pick_m("M3", "y_min_le_40_k5", "OOS", "auc"),
            "B0_brier": pick_m("B0", "y_min_le_40_k5", "OOS", "brier"),
        },
        "surfaces": dash["surfaces"],
        "asymmetry": dash["asymmetry"],
        "regimes": dash.get("regimes") or [],
        "clusters": dash.get("clusters") or {},
        "selected": dash["selected"],
        "oos_policy": dash["oos_policy"],
        "stability": load("11_exposure_surfaces/target_delta_stability.json"),
        "rem_ablation": dash["rem_ablation"],
        "spotcheck": dash.get("spotcheck") or [],
        "leak": leak,
        "split_sum": split_sum,
        "integrity": integrity,
        "elapsed_s": None,
        "git": git,
    }
    write_reports(ctx)
    C.write_json(
        C.OUT / "summary.json",
        {
            "verdict": dash["verdict"],
            "gates": {k: v.get("status") for k, v in dash["gates"].items()},
            "counts": counts,
            "banner": C.BANNER,
        },
    )
    C.write_json(
        C.OUT / "run_manifest.json",
        {
            "timestamp": dash.get("created_utc"),
            "git_commit": git,
            "python": sys.version,
            "platform": platform.platform(),
            "random_seed": C.RANDOM_SEED,
            "input_paths": {"pade": str(C.PADE_OUT)},
            "row_counts": counts,
            "universe": dash["gates"]["A"]["detail"],
            "split": split_sum,
            "output_path": str(C.OUT),
            "verdict": dash["verdict"],
            "gates": {k: v.get("status") for k, v in dash["gates"].items()},
            "banner": C.BANNER,
            "finished_from_artifacts": True,
            "tuned_on_oos": False,
        },
    )
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    C.write_json(C.DASH_PUBLIC / "dashboard.json", dash)


def _main_report(ctx, v, g, c, mr, fams, primary) -> str:
    un = ctx["unresolved"]
    inc = ctx["incremental_oos"]
    sel = ctx["selected"]
    oos_p = ctx["oos_policy"]
    rem = ctx["rem_ablation"]
    leak = ctx["leak"]
    split = ctx["split_sum"]
    clust = ctx.get("clusters") or {}
    dis = oos_p.get("disagreement_B0_vs_model_family_A") or {}
    notes = "\n".join("- " + n for n in ctx["asymmetry"].get("notes") or ["(no note)"])
    sel_b, sel_c, sel_d = sel.get("B") or {}, sel.get("C") or {}, sel.get("D") or {}
    pa, pb, pc, pd = oos_p.get("A") or {}, oos_p.get("B") or {}, oos_p.get("C") or {}, oos_p.get("D") or {}
    return f"""# MOMENTO — Dynamic Risk Engine V2

**Program:** `{C.PROGRAM}`  
**Short name:** `{C.SHORT_NAME}`  
**Schema:** {C.SCHEMA_VERSION}  
**Date:** {C.RESEARCH_DATE}  
**Live execution changed:** FALSE  
**NCAAB:** not implemented (no joinable PBP)

```
{C.BANNER}
```

---

## 1. Program definition

DRE V2 is an **offline research engine**. It estimates state-conditional future distributions of downside, recovery, and terminal outcome, then derives a **theoretical target delta**: the fraction of original directional exposure the model would *want* to retain given current state `X_n`.

It does **not** answer “what stop price should we use?”

Central question:

> Given the current state, what is the conditional value and conditional risk of retaining directional exposure?

---

## 2. Scope boundaries

DRE V2 is **not**:

- a live trading system
- a stop-loss optimizer
- a new FIRST-80 universe
- an execution engine, fill simulator, or hedge engine
- a modification to FIRST01, Risk, or PADE V1
- authorization for live deployment

PADE V1 is frozen. DRE consumes it. DRE does not overwrite PADE outputs or possession boundaries.

---

## 3. Upstream PADE dependencies

Read-only root:

`Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`

| PADE artifact | Role |
|---------------|------|
| `05_trade_possession_panel.parquet` | Trade × possession as-of state + labels |
| Frozen FIRST-80 loader | Universe gate |
| Remaining-possession R2 | ESTIMATE only (known bias) |

PADE scientific inputs treated as evidence, not re-litigated:

- Time alignment **PASS**
- Possession engine **PASS**
- Leakage **PASS**
- Possession predictive value **INCONCLUSIVE**
- Remaining possessions **WARNING**
- Execution **UNOBSERVED**
- `P(min≤40 within 5 poss)` is **saturated** (B0 AUC ≈ 0.99). It is a **control**, not the DRE headline.

---

## 4. Multi-clock architecture

Three clocks are stored separately and remain queryable:

| Clock | Field | Meaning |
|-------|--------|---------|
| Real time | `real_time_timestamp` | `entry_timestamp + position_age_wall_s` from observed PADE walls |
| Game clock | `game_clock`, `game_seconds_remaining`, `period` | Basketball position |
| Possession time | `possession_index`, `possessions_since_entry` | Discrete state transitions |

Also preserved: `market_age_seconds`. Repeated identical as-of candles are **not** independent market updates. Unique-observation counts and validity flags distinguish possession progression from market-observation progression.

`Possession Time ≠ Game Clock ≠ Real Time`.

---

## 5. State-vector definition

At each eligible PADE possession-state `n`, `X_n` contains only information available then.

Groups: position (entry/current/deterioration, YES side, 80¢ notional proxy), market (bid/ask/spread/age/alignment/unique observations/price changes), deterioration path (current, max-to-date, recovery from max DD, distance from entry/peak), velocity/acceleration **with validity flags** (null is not zero), game state, possession state, temporal clocks.

`estimated_remaining_possessions` is labeled `ESTIMATE_BIASED` / `PADE_V1_R2`.  
`actual_remaining_possessions` is **evaluation-only**.

---

## 6. Leakage rules

Every feature was asked: *could this have been known at state n?*

| Gate | Status | Count |
|------|--------|------:|
| C market lookahead | **{leak['gate_c']}** | {leak['market_lookahead_count']} future candles as features |
| D game lookahead | **{leak['gate_d']}** | {leak['game_lookahead_count']} future PBP as features |

Forbidden as features: future min/max/path, settlement, actual remaining possessions, terminal hold P&L. Artifact: `05_leakage_audit/LEAKAGE_AUDIT.json`.

---

## 7. Forward distributions

Competing objects, not one “danger” probability:

- **A Downside:** `P(FutureMin ≤ L | X, H)` and `P(FutureDet ≥ D | X, H)` for H ∈ {{1,3,5,10,end}} and L ∈ {{70,60,50,40,30}}
- **B Recovery:** `P(FutureMax ≥ current + R)` for R ∈ {{5,10,20}}¢
- **C Terminal:** `P(Settle YES | X_n)` — primary DRE target
- **D Jump proxy:** `y_jump_40` is an **observed one-minute candle-path proxy**. It is **not** “actual jump execution failure” and **not** a fill.

---

## 8. Nested models

| Family | Layer | Features |
|--------|-------|----------|
| B0 | Market price only | current, entry, deterioration |
| B1 | + wall age | + `market_age_seconds`, `position_age_wall_s` |
| B2 | + game state | + period, game clock, score, possession team |
| M3 | Multi-clock | + possession index/since-entry + R2 estimate |
| M3_NO_REM | Ablation | M3 without remaining-possession estimate |
| M4 | Path state | + max DD, recovery from max DD, distances |
| M5 | Dynamic | + valid velocity/acceleration/unique-obs structure |

Estimator (frozen a priori, **not** tuned on OOS): `StandardScaler + LogisticRegression(C=1.0, class_weight=balanced, seed=42)`.

Complete-case exclusions are recorded per family/target/split. Rows are not silently dropped.

### OOS metrics (primary targets)

{_table(mr, primary, fams, "OOS")}

### Saturated control (not the research target)

{_table(mr, ["y_min_le_40_k5"], fams, "OOS")}

---

## 9. OOS methodology

- Splits are **game-level** and chronological: TRAIN `game_date ≤ {C.SPLIT_TRAIN_END}`, VALIDATION `≤ {C.SPLIT_VAL_END}`, OOS after.
- A game appears in exactly one split. GATE E: **{split['status']}**. TRAIN games={split['train_games']} VAL={split['validation_games']} OOS={split['oos_games']}.
- Models fit on TRAIN only.
- Objective-function lambdas selected on **VALIDATION only**, then frozen.
- OOS is evaluation. GATE H: **{g['H']['status']}**.

---

## 10. Downside findings

Incremental OOS AUC vs B0:

- M3 `y_det_ge_10_end`: `{_f(inc.get('M3_y_det_ge_10_end_d_auc'))}`
- B2/M3/M5 on `y_det_ge_10_k5` — see model lab.

PADE already showed game clock (B2) is the first large lift on short-horizon deterioration. DRE treats this as input evidence and asks whether that lift changes **exposure desire**, not whether it beats a 40-cent stop.

The saturated control `y_min_le_40_k5` remains price-dominated (B0 OOS AUC `{_f(ctx['control_oos'].get('B0_auc'))}`). That is expected. It is not a DRE success metric.

---

## 11. Recovery findings

Incremental OOS AUC vs B0:

- M3 `y_rec_ge_10_k5`: `{_f(inc.get('M3_y_rec_ge_10_k5_d_auc'))}`
- M5 `y_rec_ge_10_k5`: `{_f(inc.get('M5_y_rec_ge_10_k5_d_auc'))}`
- B2 `y_rec_ge_10_k5`: `{_f(inc.get('B2_y_rec_ge_10_k5_d_auc'))}`

Recovery is one of the scientifically useful non-saturated targets. Dynamic state (M5) is evaluated only on complete-case rows with valid unique-observation velocity — exclusions are documented.

---

## 12. Settlement findings

Primary terminal object `P(Settle YES | X_n)`.

Incremental OOS AUC vs B0:

- M3: `{_f(inc.get('M3_y_settle_yes_d_auc'))}`
- M5: `{_f(inc.get('M5_y_settle_yes_d_auc'))}`
- M3_NO_REM: `{_f(inc.get('M3_NO_REM_y_settle_yes_d_auc'))}`

Remaining-possessions ablation (settlement OOS): **{rem['settlement_oos_verdict']}**. The R2 estimate is not revised in this experiment.

---

## 13. Exposure asymmetry

Question: do states with the **same current price** have different terminal / recovery / downside distributions once game clock, score, and possession differ?

OOS asymmetry declared: **{str(ctx['asymmetry']['asymmetry_exists_oos']).upper()}**

Notes:

{notes}

Full contrast tables: `docs/research/EXPOSURE_ASYMMETRY_REPORT.md`.

---

## 14. Remaining-alpha methodology

Exploratory theoretical objects. **Not realized alpha. Not tradable.**

For a YES position with candle-proxy entry 80¢:

| Object | Formula | Basis |
|--------|---------|--------|
| Market-implied proxy | `current_price / 100` | As-of yes-bid candle, not a fill |
| Model terminal probability | model P(YES given X_n) from nested logits | TRAIN-fit, split-scored |
| `terminal_probability_edge` | model P(YES) minus current_price/100 | Exploratory |
| `EV_hold_mtm` | `100·P(YES) − current_price` | Mark-to-market vs current bid **proxy** |
| `EV_hold_from_entry` | `100·P(YES) − 80` | Entry accounting; do not mix with MTM |

These assume settlement 100/0 and ignore fees, spreads at exit, and fills.

---

## 15. Exposure-value surface

`h ∈ {{0.00, 0.10, …, 1.00}}` is the **desired theoretical exposure fraction**.

- `h = 1` → retain 100% of original directional exposure
- `h = 0` → retain zero

No fill is invented. The surface is computed from model probabilities × the modular objective. Label: **THEORETICAL — NOT EXECUTION**.

---

## 16. Target-delta methodology

`theoretical_target_delta` = `argmax_h` of a stated objective on the discrete grid.

{corner_note()}

Primary exposure model for the surface: **M3** (more complete-case than M5). M5 is a nested increment, not the default h* engine. B0 h* is retained for disagreement analysis.

---

## 17. Objective-function sensitivity

Lambdas selected on VALIDATION only (`oos_used=false`).

| Family | λ_D | λ_R | γ | VAL score |
|--------|----:|----:|--:|----------:|
| A EV only | 0 | 0 | 0 | (no hyperparameter) |
| B downside-penalized | {_f(sel_b.get('lam_d'), 2)} | 0 | 0 | {_f(sel_b.get('val_score'))} |
| C path-aware | {_f(sel_c.get('lam_d'), 2)} | {_f(sel_c.get('lam_r'), 2)} | 0 | {_f(sel_c.get('val_score'))} |
| D concave regularizer | 0 | 0 | {_f(sel_d.get('gamma'), 2)} | {_f(sel_d.get('val_score'))} |

OOS theoretical score (`h ×` candle-settlement continuation vs current bid; **not** fill P&L):

| Family | n | mean h | frac h=1 | frac interior | mean h×continuation ¢ |
|--------|--:|-------:|---------:|--------------:|----------------------:|
| A | {pa.get('n')} | {_f(pa.get('mean_h'))} | {_f(pa.get('frac_h_eq_1'))} | {_f(pa.get('frac_interior'))} | {_f(pa.get('mean_realized_h_times_continuation_cents'))} |
| B | {pb.get('n')} | {_f(pb.get('mean_h'))} | {_f(pb.get('frac_h_eq_1'))} | {_f(pb.get('frac_interior'))} | {_f(pb.get('mean_realized_h_times_continuation_cents'))} |
| C | {pc.get('n')} | {_f(pc.get('mean_h'))} | {_f(pc.get('frac_h_eq_1'))} | {_f(pc.get('frac_interior'))} | {_f(pc.get('mean_realized_h_times_continuation_cents'))} |
| D | {pd.get('n')} | {_f(pd.get('mean_h'))} | {_f(pd.get('frac_h_eq_1'))} | {_f(pd.get('frac_interior'))} | {_f(pd.get('mean_realized_h_times_continuation_cents'))} |

B0 vs M3 Family-A disagreement: n={dis.get('n')} frac={_f(dis.get('frac_disagree'))}

---

## 18. Regime findings

SAFE / DANGER / ACUTE were **not** hard-coded as truth.

Interpretable buckets: price, deterioration, period, score differential. Optional KMeans (k=5) fit on TRAIN only (price, deterioration, remaining game clock, score differential, possessions since entry); VAL/OOS transformed without refit. Status: **{clust.get('status')}**.

The goal is whether economically different exposure regimes exist at similar prices — see the asymmetry report — not whether clusters look impressive.

---

## 19. Execution limitations

1. One-minute candles. Many possessions share one stale print.
2. No L2. No IOC. No maker fill tape.
3. `y_jump_*` is a candle-path **proxy**.
4. Seven unmatched FIRST-80 events have no NBA game ID; additional matched-but-no-panel trades remain unresolved.
5. Remaining-possession R2 is biased (~30 possessions in PADE). Not a deterministic clock.
6. Theoretical `h` is not achievable just because it is computed.
7. Settlement 100/0 accounting ignores fees and exit microstructure.

```
CANDLE PATH ≠ ACTUAL FILL
THEORETICAL TARGET DELTA ≠ EXECUTED DELTA
THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION
```

---

## 20. Evidence grades

| Claim | Grade |
|-------|-------|
| Frozen universe reproduction | **A** (gate) |
| PADE as-of panel consumed unchanged | **A** |
| No-lookahead feature audit | **A** (structural) |
| Nested logistic AUC/Brier | **C** |
| Remaining-possession R2 as feature | **B** (biased estimate) |
| Jump-through | **B** candle proxy, **not** a fill |
| Theoretical target delta | **C** (research object) |
| Live / IOC / maker fill | **D / UNOBSERVED** |

---

## 21. Gates

| Gate | Status | Notes |
|------|--------|-------|
| A Frozen universe | **{g['A']['status']}** | 1230 / 910 / 320 / 0 |
| B PADE integrity | **{g['B']['status']}** | Expected files + hashes; PADE not modified |
| C Market lookahead | **{g['C']['status']}** | 0 future candles in `X_n` |
| D Game lookahead | **{g['D']['status']}** | 0 future PBP in `X_n` |
| E Split isolation | **{g['E']['status']}** | 0 games in multiple splits |
| F Unresolved preservation | **{g['F']['status']}** | universe={un['universe']} panel={un['panel_eligible_trades']} unresolved={un['unresolved_n']} |
| G Model baseline | **{g['G']['status']}** | Every advanced family vs B0 |
| H OOS discipline | **{g['H']['status']}** | No OOS hyperparameter tuning |
| I Execution claims | **{g['I']['status']}** | Language constraints preserved |

---

## 22. Scientific verdict

| Item | Result |
|------|--------|
| Architecture / incremental state value | **{v['ARCHITECTURE']}** |
| Saturated 40-in-5 control | **{v['SATURATED_40_IN_5_CONTROL']}** |
| Exposure asymmetry | **{v['EXPOSURE_ASYMMETRY']}** |
| Target-delta stability | **{v['TARGET_DELTA_STABILITY']}** |
| Remaining possessions | **{v['REMAINING_POSSESSIONS']}** |
| Execution evidence | **{v['EXECUTION_EVIDENCE']}** |
| Live deployment | **{v['LIVE_DEPLOYMENT']}** |

Panel: {c['panel_rows']} rows / {c['panel_trades']} trades / {c['panel_games']} games.  
Universe: {ctx['universe']} frozen FIRST-80 trades. Unresolved preserved: {un['unresolved_n']}.

This experiment does **not** prove DRE “works” as a trading policy. It asks whether additional state changes the *theoretical* desire to retain exposure. See `DRE_V2_RESEARCH_VERDICT.md`.

---

## 23. Explicit next experiment

Authorized only by a later mandate. Candidates, none of which are live:

1. Isolated remaining-possession model revision (side experiment, not a silent DRE revision).
2. Execution-tape / L2 join so `h*` can be tested against **observed** reduce-only opportunities.
3. Sport expansion only after joinable PBP exists (NCAAB currently cannot).

Until execution evidence exists, DRE V2 cannot leave the research layer.

---

## How to rerun

```
/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v2.py
```

Outputs: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/dynamic_risk_engine_v2/`

Dashboard: `frontend/dre-v2` on http://127.0.0.1:5184/

PADE V1 left untouched.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
"""


def _model_card(ctx, v, mr, fams) -> str:
    return f"""# DRE V2 — Model Card

**Program:** `{C.PROGRAM}`  
**Date:** {C.RESEARCH_DATE}  
**Live execution changed:** FALSE

## Intended use

Offline research: estimate `P(Settle YES | X_n)`, recovery and downside path probabilities, and a **theoretical** exposure fraction `h`.

Not intended for order routing, stop placement, or live risk.

## Training data

- Frozen FIRST-80 NBA 2025–2026 candle-path universe (1230 / 910 / 320 / 0).
- PADE V1 HIGH+MEDIUM trade × possession panel.
- Chronological game-level TRAIN / VALIDATION / OOS.

## Features

See `04_feature_dictionary/feature_dictionary.json`. Nested families B0–M5 plus `M3_NO_REM` ablation.

## Hyperparameters (frozen)

- LogisticRegression `C=1.0`, `class_weight=balanced`, `max_iter=400`, `random_state=42`
- StandardScaler
- Objective lambdas selected on VALIDATION only (see `11_exposure_surfaces/hyperparameters_selected.json`)
- **OOS was not used to tune**

## Metrics (OOS, selected)

{_table(mr, ['y_settle_yes','y_rec_ge_10_k5','y_det_ge_10_end','y_jump_40','y_min_le_40_k5'], fams, 'OOS')}

## Limitations

- Complete-case drops rows with invalid velocity/acceleration (M5) or missing R2 (M3).
- Candle path ≠ fill.
- Class-balanced logits are not probability-calibrated to raw base rates; ECE is reported, not “fixed” on OOS.
- Theoretical `h` is not executable.

## Ethical / trading safety

LIVE DEPLOYMENT: **{v['LIVE_DEPLOYMENT']}**

{C.BANNER}
"""


def _verdict_doc(ctx, v, g) -> str:
    lines = [
        "# DRE V2 — Research Verdict",
        "",
        f"**Program:** `{C.PROGRAM}`  ",
        f"**Date:** {C.RESEARCH_DATE}  ",
        "",
        "Allowed tokens only: PASS, PARTIAL, INCONCLUSIVE, WARNING, FAIL, NOT AUTHORIZED, UNOBSERVED.",
        "",
        "| Item | Verdict |",
        "|------|---------|",
    ]
    for k, val in v.items():
        lines.append(f"| {k} | **{val}** |")
    lines += [
        "",
        "## Gates",
        "",
        "| Gate | Status |",
        "|------|--------|",
    ]
    for k, rec in g.items():
        lines.append(f"| {k} | **{rec['status']}** |")
    lines += [
        "",
        "## Reading",
        "",
        "- **PASS** on gates A–I means the experiment was conducted under the stated constraints.",
        "- **PARTIAL** on architecture means some incremental OOS information or price-matched asymmetry appeared; it is not a trading license.",
        "- **INCONCLUSIVE** means the additional state layer did not clear a pre-declared increment or the contrast sample was too thin.",
        "- **WARNING** is reserved for remaining-possession bias or unstable `h*`.",
        "- Execution remains **UNOBSERVED**.",
        "- Live deployment is **NOT AUTHORIZED**.",
        "",
        C.BANNER,
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)


def _asymmetry_doc(ctx) -> str:
    asym = ctx["asymmetry"]
    lines = [
        "# DRE V2 — Exposure Asymmetry Report",
        "",
        f"**Date:** {C.RESEARCH_DATE}",
        "",
        "Question: do states with similar current prices have different conditional distributions once game clock, score, and possession differ?",
        "",
        f"OOS asymmetry exists (pre-declared: gap ≥ 0.08, n≥40 each side): **{str(asym['asymmetry_exists_oos']).upper()}**",
        "",
        C.BANNER,
        "",
        "## Notes",
        "",
    ]
    for n in asym.get("notes") or []:
        lines.append(f"- {n}")
    lines += [
        "",
        "## Contrasts",
        "",
        "| Split | Band | Slice | n | mean px | P(settle) | P(rec≥10/5) | P(det≥10 end) | P_B0 | P_M3 | h*_B0 A | h*_M3 A |",
        "|-------|------|-------|--:|--------:|----------:|------------:|--------------:|-----:|-----:|--------:|--------:|",
    ]
    for rec in asym.get("contrasts") or []:
        for slice_name in ("early", "late", "leading", "trailing", "offense", "defense"):
            s = rec.get(slice_name) or {}
            if s.get("n", 0) == 0:
                continue
            lines.append(
                "| {split} | {band} | {slice} | {n} | {px} | {st} | {rc} | {dn} | {b0} | {m3} | {h0} | {h3} |".format(
                    split=rec.get("split"),
                    band=rec.get("band"),
                    slice=slice_name,
                    n=s.get("n"),
                    px=_f(s.get("mean_price"), 1),
                    st=_f(s.get("emp_settle")),
                    rc=_f(s.get("emp_rec10_k5")),
                    dn=_f(s.get("emp_det10_end")),
                    b0=_f(s.get("mean_p_settle_B0")),
                    m3=_f(s.get("mean_p_settle_M3")),
                    h0=_f(s.get("mean_h_B0_A")),
                    h3=_f(s.get("mean_h_M3_A")),
                )
            )
    lines += [
        "",
        "Interpretation is observational. Same-price buckets that differ in terminal rate support a state-conditional exposure architecture **in theory**. They do not authorize execution.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines)
