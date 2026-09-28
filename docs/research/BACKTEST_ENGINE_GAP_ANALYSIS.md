# BACKTEST_ENGINE_GAP_ANALYSIS.md

**W0-A11 repository audit vs approved waterfall.**  
**Date:** 2026-08-26  
**Method:** inspect source, manifests, recon package, and this governance set.  
**No engine implementation was performed.**

This document is the gap analysis required by the CEO/CTO waterfall directive.
It does not authorize skipping to later waterfalls.

---

## A. Documentation created / updated (this delivery)

Created:

- `docs/research/BACKTEST_ENGINE_WATERFALL.md`
- `docs/research/BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md`
- `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`
- `docs/research/BACKTEST_ENGINE_CURRENT_STATE.md`
- `docs/research/BACKTEST_ENGINE_GAP_ANALYSIS.md` (this file)
- `docs/research/templates/WATERFALL_STEP_COMPLETION.md`
- `docs/research/architecture-decisions/` (README + ADR-0001 … ADR-0020)
- `docs/research/completions/` (W0-A11 step records)

Updated (indexes / pointers only): research README, AGENTS.md, agent rule
`11-historical-research-engine.mdc`, recon README, Backtesting Suite README,
reset/next-step pointers as needed.

Already existed (W0-A1–A10): `docs/research/backtesting_rebuild/*`,
`HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`, `BACKTESTING_ENGINE_RESET.md`.

**Did not exist before W0-A11:** master waterfall file, system spec, W/A/S
registry, ADR system, step-completion template, living current-state doc.

---

## B. Repository findings

- Workspace is a Rust workspace (`edition 2024`, resolver 2) with production
  trading apps and isolated research crates.
- **No git metadata** in this copy (`fatal: not a git repository` per W0 recon).
- Research crates do **not** depend on risk, execution, or `strategies/mlb`.
- `momento-research-data` depends on `momento-kalshi` public client only.
- `apps/replay-engine` is a stub (`foundation only. No live venue.`).
- `crates/prediction` is a `Forecast` placeholder.
- `crates/sports` has `SportId` plus empty mlb/nba/ncaab/nfl/wnba modules.
- Default research data dir is demo `Backtesting Suite/Data` if env unset.

---

## C. Existing relevant architecture

Production (UNTOUCHED): strategy → risk → execution → Kalshi; positions; pnl;
live.rs; `config/live.toml` triple gate; integer money/price/qty.

Intended research architecture (design only): dual EVENT/MARKET domains,
synchronized state, `StateTransition` + `GameMarketEpisode`, versioned
transforms, strategy plugins, labels, Drive/Sheets as human archive.

These types **are not in Rust**. Architecture docs exist; implementation does not.

Shared sensitive surface: `momento-core` (`GameId`, `MarketEvent`,
`Position::can_attempt_entry`, money types).

---

## D. Existing backtesting components (LEGACY_V1)

| Component | Path | Honest capability |
|-----------|------|-------------------|
| Collector | `crates/research-data`, `apps/research-collector` | Kalshi public REST → gzip/parquet/manifests |
| Replay | `ReplayDataset` / `ReplayCursor` | Trades + OrderbookEvent (candles) chronological |
| FIRST01 copy | `crates/research-strategies` | Entry/exit engines, lifecycle flag |
| Fill model | `crates/research-execution` | CONSERVATIVE_MAKER; **0 fills** on candles |
| Control plane | `crates/research-backtest`, `apps/backtest-runner` | Sheets Input/Results, validate-mlb, frequency recon |
| Catalog v1 | `research-data` `catalog.rs` | Sport-level Notion handoff counts — **not** per-file lake_catalog_v1 |

This is **not** a game-state reconstruction platform.

---

## E. Existing historical data

See `backtesting_rebuild/DATA_INVENTORY.md`.

| Dataset | Status |
|---------|--------|
| MLB Kalshi Data-Real Jun 18–30 2026 | 13 COMPLETE days, 172 games, 344 contracts |
| MLB 2025 | Empty probes only |
| Rest of 2026 | Not in this lake (Jun 1–17 empty probes) |
| MLB PBP | **Absent** |
| Historical L2 | **Absent / UNAVAILABLE from Kalshi** |
| Demo Data/ | Synthetic; easy to misuse |
| Root `Data/` `data/` | Empty placeholders |

v1 `COMPLETE` ≠ lifetime-complete, ≠ L2, ≠ PBP, ≠ starting price guaranteed.

---

## F. Existing Google Drive / Sheets integration

**LEGACY_V1 only.** IDs in `crates/research-backtest/src/config.rs`.

- Suite folder, Backtesting Input, Backtesting Results, FIRST01 Runs, README Doc.
- Local CSV mirrors.
- Drive MCP = documented write path; Sheets cell OAuth optional / often unauthenticated.
- No secrets in repo.
- **Not** the W20/W21 research archive. Candle P&L rows ≠ MLB reconstruction done.

New-engine Drive tree and Sheets index: **not implemented**.

---

## G. Existing FIRST01 components

| Layer | Path |
|-------|------|
| Live | `strategies/mlb/src/{quote,strategy,state,stop}.rs` |
| Research copy | `crates/research-strategies/src/first01.rs` (v1) |
| Semantics freeze | `docs/research/backtesting_rebuild/FIRST01_BASELINE_SEMANTICS.md` |
| Audits | `docs/research/FIRST01_*.md` |
| Runs | `Backtesting Suite/Runs/FIRST01/` |

Frozen: 80 / 81 / 83 / 89 / 50% VWAP stop; YES bid only; one lifecycle per GameId.

Do not retune. Do not change live as part of engine work.

Known doc bug: `FIRST01_live_entry_state_machine.md` still says TRADE_COMPLETE
may allow a new opportunity — **obsolete**; `can_attempt_entry` forbids it.

---

## H. Architectural gaps (approved waterfall vs repo)

| Waterfall need | Repo status |
|----------------|-------------|
| W0 contracts + governance | **Just closed** (this delivery) |
| W1 lake catalog v2 / envelope v2 / coverage vocab | Missing (v1 catalog is sport aggregates) |
| W1 provenance tuple | Partial (`received_at`, endpoint, file SHA-256; no source_record_id on envelope) |
| W2 identity graph + MLB pk | Hash only; UNMAPPED |
| W3 sync engine | Missing |
| W4–W5 event/PBP | Missing (no data, no types) |
| W6 honest market state | Candles in `OrderbookEvent`; PIT snapshot hazard |
| W7 starting prices both sides | Not guaranteed (close-day window) |
| W8 complete paths | Trades+candles on close-day only; no episode object |
| W9–W10 Greeks | Missing (prediction stub) |
| W11–W12 first-touch / 80% vector | FIRST01 first_80 on candle bid only |
| W13 plugin on reconstructed state | LEGACY runner on candles |
| W14 execution sim as historical fact | Unsupported on candles (correct refusal) |
| W15–W19 labels/ML/validation platform | Missing (LEGACY reports are candle-era) |
| W20–W22 new reporting | Design only |
| W23 dashboard | Missing |
| W24–W26 governance/live bridge/feedback | Missing |

**Rust gap:** `GameMarketEpisode` and `StateTransition` do not exist.

**Data gap:** PBP = 0; L2 historical = 0; 2025 = 0; most of 2026 = 0 locally.

---

## I. Risks

1. Implementing W4+ without W1 catalog would freeze an unproven lake.
2. Editing `momento-core` can change production financial behavior.
3. Demo lake as default env is a foot-gun.
4. Candle-as-orderbook naming will leak into naive feature code.
5. Inventing 2025 days or L2 would invalidate the program.
6. FIRST01 threshold fishing before path truth (explicitly forbidden).
7. Drive/Sheets becoming the warehouse.
8. PBP scrape without license approval.
9. Silent identity mapping with fake MLB pks.
10. No git in this copy → weak reproducibility until a real repo is used.

---

## J. Recommended first implementation step

After CEO authorization of Waterfall 1, implement **only**:

**W1-A1-S1 — Specify `lake_catalog_v1` schema (docs + checked-in fixtures).**

Then checkpoint and STOP.

Do not start PBP parsers, sync, FIRST01 replay, ML, or Drive automation.

---

## K. Exact proposed W/A/S for next authorized implementation

```text
W1-A1-S1
  title: Specify lake_catalog_v1 schema
  status: NOT_STARTED
  authorization: REQUIRED from CEO before any code
  dependencies: W0 complete (satisfied)
  out of scope: Data-Real overwrites, PBP download, production crates,
                FIRST01 parameters, fabricating missing Kalshi days
```

Registry: `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv` row `W1-A1-S1`.  
Spec: `docs/research/backtesting_rebuild/WATERFALL_NEXT_STEP.md`.

---

```text
IMPLEMENTATION OF HISTORICAL DATA ENGINE: NOT STARTED
PRODUCTION ORDERS: 0
FIRST01 BEHAVIOR CHANGES: 0
```
