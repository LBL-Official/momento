# EXPERIMENT_DATA_AUDIT — FIRST80 alpha decomposition v1

> RESEARCH ONLY — OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY — TERMINAL ALPHA ≠ PATH ALPHA — PATH SURVIVAL ≠ INDEPENDENT EDGE — CONDITIONAL INFORMATION ≠ EXECUTABLE PROFIT — HISTORICAL CANDLE PATH ≠ ACTUAL FILL — HEDGE OPPORTUNITY ≠ LOCKED-IN ALPHA — LIVE EXECUTION = FALSE

Audit completed before scientific tables. FIRST80 and TOUCH40 are **not** redefined.

## Canonical definition source

- Code: `apps/nba-data/scripts/nba_80_40_execution_audit.py`
- Artifacts: `warehouse/derived/nba/first80_execution_audit/`
- FIRST80: first tradable `yes_bid_close ≥ 80¢` after a prior tradable close < 80¢, spread ≤ 10¢, game-day window, one per event.
- Primary T40: later tradable `yes_bid_close ≤ 40¢` (`stop_close_triggered`). Wick is secondary.
- Sampling: 1-minute Kalshi yes_bid OHLC. `end_period_ts` is candle end. Intraminute path unknown.

## Counts (frozen candidates, not recomputed here)

- Games in candidates file: 1362
- FIRST80 settled: 1230
- W: 1019  T40: 320
- Date range: 2025-10-10 → 2026-06-13
- Splits: {'IN_SAMPLE': 504, 'OOS': 243, 'VALIDATION': 483}

## Files

- 1m candle parquet files: 2724
- markets.parquet rows: 2724
- nba_games.parquet rows: 1362
- Game Path Engine V2 features_entry rows: 1230 (causal-at-entry labels; alignment HIGH/MEDIUM/LOW/UNUSABLE)
- PADE 05 panel present: True

## Ambiguities (not silently resolved)

- ADR-0006 (MLB live) uses YES **bid sticky**. This NBA frozen study uses **candle yes_bid_close** tradable cross. They are related but not identical. This experiment uses the NBA frozen audit definition.
- LOSS ∧ ¬T40 can be non-zero if the market skips 40¢ between minute closes. Frozen sample count is an observation, not a continuity proof.
- Game-state features use PERIOD_BOUNDED_LINEAR_GAME_CLOCK; 69 rows lack score/clock (UNUSABLE/unaligned). Matching drops them and counts them.
- PADE panel does not cover every FIRST80 game. Alpha persistence drops unmatched games.

## Not used as fills

Candles are not maker fills, not IOC fills, and not L2.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
