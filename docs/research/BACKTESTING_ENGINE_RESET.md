# Backtesting Engine Reset — 2026-08-26

**Status:** ACTIVE RESET  
**Supersedes:** Candle-era FIRST01 validation backtester (`momento-research-backtest` +
`CONSERVATIVE_MAKER` candlestick replay as the primary research path)  
**Does not touch:** Production live trading (`strategies/mlb`, `live.rs`, risk, config/live.toml)

---

## Decision

We are **not** extending the old FIRST01 candlestick backtester with more features.

We are **replacing** it with a new platform:

> **MLB Historical Event–Market Reconstruction & Simulation Engine**

FIRST01 becomes the **first strategy plugin** on that platform — not the definition of the platform.

The fundamental research object is:

```text
GameMarketEpisode
```

A trade is one possible downstream consequence of a reconstructed state — not the primary unit of research.

---

## What is reset

| Layer | Action |
|-------|--------|
| **Research north star** | Replaced: P&L tables → full event/market reconstruction questions |
| **Primary artifact** | Replaced: entry-signal CSV → `GameMarketEpisode` + complete paths |
| **Data contract** | Reset: never silently treat candles as ticks; classify observability |
| **Build order** | Reset: Phase 1 contracts first; no skipping to ML / FIRST01 tuning |
| **Governance** | Affirmed: research never auto-mutates production |

## What is preserved (read-only reference)

| Asset | Why keep |
|-------|----------|
| `FIRST01` v1 rule definition (80/81/83/89/50%) | Canonical live strategy baseline / plugin control |
| Live vs research lifecycle audits | Correct one-trade-per-game semantics for the plugin |
| `research-data` raw lake layout / manifests | Seed for Waterfall 1 (extend, do not rewrite truth) |
| Desk loss review `docs/desk/2026-08-25-loss-review.md` | Motivation for path reconstruction (“why did we lose?”) |
| Sheets/Drive control-plane experience | Evolves into Waterfalls 20–22 reporting |

## What is frozen / legacy

Treat as **LEGACY_V1** until the new engine can replay FIRST01 equivalently:

- `crates/research-backtest` candle validation path as *primary* research answer
- `validate-mlb` / frequency reconciliation as *completion* criteria for MLB research
- Any claim that `CANDLESTICK_ONLY` + maker model equals historical live equivalence

Legacy crates may remain for regression of FIRST01 *rule* tests. They must not be
extended as the platform.

---

## Absolute rules during the rebuild

1. **Do not rewrite immutable raw history.** New parsers → new normalized versions.
2. **Do not fabricate L2 / mid / fees.** Mark `observability` and `MODELED` explicitly.
3. **Do not tune FIRST01** because a loser pattern looks interesting before state/path truth exists.
4. **Do not skip waterfalls.** Interesting later layers wait for proven earlier layers.
5. **Do not auto-deploy research into production.** Governance: RESEARCH → … → APPROVED → PRODUCTION.
6. **Do not change live 80/81/83/89/50%** as part of this reset.
7. **Ticker strings are not primary identity.** Internal `GameId` is canonical.

---

## Canonical plan document

Full blueprint (waterfalls 0–26, phases 1–27, MLB completion criteria):

→ [`docs/research/HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md)

Agent rule:

→ `.cursor/rules/11-historical-research-engine.mdc`

---

## Immediate next work (only)

**Waterfall 0 is delivered:** reconnaissance (`docs/research/backtesting_rebuild/`)
plus governance baseline (`BACKTEST_ENGINE_WATERFALL.md`, system spec, W/A/S
registry, ADRs, current-state, gap analysis).

**Next (not started, needs CEO authorization):** `W1-A1-S1` — specify
`lake_catalog_v1` schema, then the rest of Waterfall 1 (immutable raw /
canonical data foundation) one S-step at a time.

See `docs/research/backtesting_rebuild/WATERFALL_NEXT_STEP.md` and
`docs/research/BACKTEST_ENGINE_WATERFALL.md`.

Do not skip to FIRST01 retune, PBP engines, ML, or production mutation.

---

## Production safety

```text
PRODUCTION ORDERS TRANSMITTED BY THIS RESET: 0
```
