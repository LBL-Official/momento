# WATERFALL_ALIAS_CROSSWALK.md

**Authority:** CTO W0–W11 is the **execution / control** numbering.  
**Reference:** Historical Engine Plan W0–W26 is the **detailed planning** numbering.  
**Rule:** Never replace the 0–26 plan. Never use an unprefixed `W#` in a handoff.

Every agent message, ledger row, and PR title must use one of:

```text
CTO-W#   — this control plane
PLAN-W#  — HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md / BACKTEST_ENGINE_WATERFALL.md
```

---

## Canonical alias table

| CTO (execution) | Name | PLAN (reference) | Notes |
|-----------------|------|------------------|-------|
| **CTO-W0** | Repository / Architecture Reconnaissance | **PLAN-W0** | 1:1. Recon A1–A10 + governance A11. COMPLETE. |
| **CTO-W1** | Immutable Raw Data + Canonical Data Foundation | **PLAN-W1** | 1:1. Catalog, provenance, envelope v2, coverage, identity **stub**, PBP **source matrix only**. |
| **CTO-W2** | MLB Event / PBP Reconstruction | **PLAN-W2** + **PLAN-W4** + **PLAN-W5** | Identity graph + official pk mapping (PLAN-W2) + `GameState` (PLAN-W4) + PBP `State(t-1)→Event→State(t)` (PLAN-W5). **Not** Kalshi reconstruction. |
| **CTO-W3** | Kalshi Market Reconstruction | **PLAN-W6** + **PLAN-W7** | Per-contract `MarketState` + coupled Team A/B paths + starting-state **when observed**. |
| **CTO-W4** | Event ↔ Market Synchronization | **PLAN-W3** | **Numbering inversion.** Plan “W3” is time-sync; CTO “W3” is market reconstruction. |
| **CTO-W5** | Canonical State / StateTransition Engine | **PLAN-W8** + **PLAN-W11** + **PLAN-W12** | `StateTransition` (atomic) inside `GameMarketEpisode` (container). Threshold first-touch **tables** live here as data, not FIRST01. |
| **CTO-W6** | FIRST01 Replay / Backtesting Layer | **PLAN-W13** + **PLAN-W14** | Plugin + MODELED execution. Frozen 80/81/83/89/50%. Not the database. |
| **CTO-W7** | 80% Transition + Outcome Classification Research | **PLAN-W15** + **PLAN-W16** (+ consumes PLAN-W11/W12 outputs) | Labels + loser/winner classification. Does not retune FIRST01. |
| **CTO-W8** | Event Greeks / Market Greeks / Feature Research | **PLAN-W9** + **PLAN-W10** + **PLAN-W17-A1** | Empirical, versioned. No formula as OBSERVED truth. |
| **CTO-W9** | Orderbook / Market Microstructure Research | *(no dedicated PLAN-W; slices of PLAN-W6 observability + later microstructure)* | Historical L2 remains UNAVAILABLE unless W1 catalog proves a WS capture artifact. |
| **CTO-W10** | ML / XGB / Monte Carlo / Hyperparameter Research | **PLAN-W17** + **PLAN-W18** + **PLAN-W19** | After deterministic dataset is trustworthy. |
| **CTO-W11** | Production Research-to-Execution Integration | **PLAN-W20 … PLAN-W26** | Drive, Sheets, artifacts, dashboard, model registry, production bridge, live→research feedback. **Separate CEO live-safety auth required to touch production.** |

---

## Inversion warnings (must not be skipped)

```text
PLAN-W2  identity          →  lives inside CTO-W2
PLAN-W3  time sync         →  is CTO-W4          (NOT CTO-W3)
PLAN-W4  MLB GameState     →  lives inside CTO-W2
PLAN-W5  PBP transitions   →  lives inside CTO-W2 (event-trigger stream)
CTO-W5   canonical engine  →  PLAN-W8/W11/W12    (NOT PLAN-W5)
CTO-W3   Kalshi market     →  PLAN-W6/W7         (NOT PLAN-W3)
```

## 2026-08-26 execution override (CEO/CTO W3 grant)

The 2026-08-26 implementation authorization defines:

| This grant | Meaning |
|------------|---------|
| **CTO-W3** | MLB **game/PBP reconstruction layer** (consumes W2 engine + committed ingest) |
| **CTO-W4** | Kalshi **market** reconstruction |
| **CTO-W5** | Event ↔ market time synchronization |

This does **not** rewrite PLAN-W0–W26. Agents following that grant must not implement Kalshi `MarketState` under W3.


---

## PLAN waterfalls with no CTO 1:1 (folded)

| PLAN | Folds into CTO |
|------|----------------|
| PLAN-W20 Drive | CTO-W11 (reporting) |
| PLAN-W21 Sheets | CTO-W11 (reporting) |
| PLAN-W22 Deep artifacts | CTO-W11 (and per-W local artifacts earlier) |
| PLAN-W23 Dashboard | CTO-W11 |
| PLAN-W24 Model registry | CTO-W11 |
| PLAN-W25 Production bridge | CTO-W11 (**FORBIDDEN by default**) |
| PLAN-W26 Live→research feedback | CTO-W11 (**FORBIDDEN by default**) |

---

## Step-ID namespaces (collision already observed)

Three step namespaces exist. They are **not** interchangeable:

| Namespace | Source | Example | Meaning of `W1-A1-S1` |
|-----------|--------|---------|------------------------|
| **PLAN-S** | `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv` | PLAN-W1-A1-S1 | Specify `lake_catalog_v1` schema (docs + fixtures) |
| **W1-LEDGER-S** | `crates/research-data/src/foundation/ledger.rs` `W1_STEPS` | W1-LEDGER W1-A1-S1 | Discover lake roots |
| **CTO-S** | this control plane / per-waterfall `PROGRESS.md` | CTO-W1-A1-S1 | Same intent as PLAN-W1-A1-S1 (schema freeze) |

**FLAG:** W1 implementation ledger IDs collide with PLAN IDs and mean different work. See [CTO_REVIEW_FLAGS.md](CTO_REVIEW_FLAGS.md) FLAG-001.

Until W1 remaps its ledger, control-plane progress cites **both** IDs.
