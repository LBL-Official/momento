# FIRST80 V0 Lifecycle

Attribution of the target lifecycle to named systems.
This is as-is, not as-claimed.

```text
ingest scripts / research-ingest     → data_ingestion          PARTIAL
ROLLER warehouse                     → database                COMPLETE
SuperASI + Choosin ladder + path-FE  → data_modeling           PARTIAL
                                       ← data_analysis         COMPLETE
XIB/MCD frozen; F_t vs K_t blocked   → in_house_odds /
                                       game_modeling           PARTIAL
fair odds                            → fair_odds_modeling      NOT IMPLEMENTED
first80.py touch-80 + Fort Worth     → signal_generation       research only
Choosin 80/40 ledger + 40 benchmark  → trade_breakdown         COMPLETE
Austin PCA+KNN                       → position_stratification PARTIAL
Austin Risk / DRE experiments        → dynamic_risk_engine     research; not policy; V1 objective in research/dre/
hedge research + Austin hedge        → hedging_analysis        PARTIAL
tk_relative_value_v1 + TK Ultra     → relative_value_hedging  PARTIAL (formula, not truth)
current vs target exposure           → position_management     NOT IMPLEMENTED
execution contracts / dry-run        → algorithmic_execution   NOT IMPLEMENTED (no NBA bot)
fills / ledger                       → trade_reconciliation    NOT IMPLEMENTED (observe-only; not Vital)
runtime orchestration                → system_orchestration    NOT IMPLEMENTED (not champion Momento Systems)
architecture façade                  → momento_systems         PARTIAL (registry + bracket)
```

## Legacy 40-stop

Preserve as `legacy_benchmark` on Trade Breakdown.
Do not delete it to make dynamic exposure look cleaner.

## Hedge semantics

Original: LONG YES @ ~80, SELL/STOP around YES 40.

New direction: dynamic exposure, including BUY NO as taker, possibly partial.

Existing Austin/Fort Worth research: rest opponent YES @ 40 as maker.

Track separately when implemented: `yes_quantity`, `no_quantity`,
`gross_cost`, `net_terminal_exposure`, locked economics, fees, slippage.

Buying complementary NO can resemble reducing YES. It does not create
free economics. Calculate locked/remaining payoff explicitly.

A complete offline lifecycle traverse is Phase 4.
Execution stays disabled.
