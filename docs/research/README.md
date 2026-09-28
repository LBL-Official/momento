# Research documentation index

## Active platform (post-reset)

| Document | Role |
|----------|------|
| [BACKTEST_ENGINE_WATERFALL.md](BACKTEST_ENGINE_WATERFALL.md) | **Authoritative** W/A/S engineering roadmap (maintain continuously) |
| [BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md](BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md) | CEO/CTO technical contract |
| [BACKTEST_ENGINE_WATERFALL_REGISTRY.csv](BACKTEST_ENGINE_WATERFALL_REGISTRY.csv) | Every W/A/S step + status |
| [BACKTEST_ENGINE_CURRENT_STATE.md](BACKTEST_ENGINE_CURRENT_STATE.md) | Living “what is true right now” |
| [BACKTEST_ENGINE_GAP_ANALYSIS.md](BACKTEST_ENGINE_GAP_ANALYSIS.md) | W0-A11 repo audit vs waterfall |
| [architecture-decisions/](architecture-decisions/) | ADRs |
| [templates/WATERFALL_STEP_COMPLETION.md](templates/WATERFALL_STEP_COMPLETION.md) | S-step completion template |
| [completions/](completions/) | Completed S-step records |
| [BACKTESTING_ENGINE_RESET.md](BACKTESTING_ENGINE_RESET.md) | Reset decision: replace candle FIRST01 runner |
| [HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md) | Full blueprint (waterfalls 0–26, phases 1–27) |
| [backtesting_rebuild/README.md](backtesting_rebuild/README.md) | **Waterfall 0 recon** (A1–A10) |

## FIRST01 (strategy plugin / control baseline)

| Document | Role |
|----------|------|
| [FIRST01.md](FIRST01.md) | Frozen 80/81/83/89/50% research model |
| [FIRST01_live_entry_state_machine.md](FIRST01_live_entry_state_machine.md) | Live entry SM (note: one sentence obsolete; see baseline semantics) |
| [FIRST01_live_entry_lifecycle_reset.md](FIRST01_live_entry_lifecycle_reset.md) | One-trade-per-game lifecycle |
| [FIRST01_live_vs_research_audit.md](FIRST01_live_vs_research_audit.md) | Live ≡ research audit |
| [FIRST01_live_entry_gate_audit.md](FIRST01_live_entry_gate_audit.md) | Strategy vs risk vs host gates |
| [backtesting_rebuild/FIRST01_BASELINE_SEMANTICS.md](backtesting_rebuild/FIRST01_BASELINE_SEMANTICS.md) | Frozen plugin control |

## Data / reporting (seed + legacy)

| Document | Role |
|----------|------|
| [data-infrastructure.md](data-infrastructure.md) | Kalshi lake layout (Waterfall 1 seed) |
| [sheets-control-plane.md](sheets-control-plane.md) | LEGACY_V1 Sheets index |
| [backtesting_rebuild/GOOGLE_REPORTING_ARCHITECTURE.md](backtesting_rebuild/GOOGLE_REPORTING_ARCHITECTURE.md) | Drive/Sheets target architecture |

## Desk

| Document | Role |
|----------|------|
| [../desk/2026-08-25-loss-review.md](../desk/2026-08-25-loss-review.md) | Live loss motivation for path reconstruction |

**Current W/A/S:** W0 complete (including governance baseline W0-A11).  
**Next authorized build step (pending CEO authorization):** `W1-A1-S1` — specify `lake_catalog_v1` schema.  
See [backtesting_rebuild/WATERFALL_NEXT_STEP.md](backtesting_rebuild/WATERFALL_NEXT_STEP.md). **Do not implement until authorized.**
