# Momento Backtesting Suite

## Status: engine reset (2026-08-26)

This suite’s **north star has changed**.

We are **not** continuing the candle-era FIRST01 backtester as the research platform.

We are building:

> **MLB Historical Event–Market Reconstruction & Simulation Engine**

FIRST01 is the first **strategy plugin** on that platform.

| Doc | Path |
|-----|------|
| Authoritative waterfall | `docs/research/BACKTEST_ENGINE_WATERFALL.md` |
| System spec | `docs/research/BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md` |
| Current state | `docs/research/BACKTEST_ENGINE_CURRENT_STATE.md` |
| Reset | `docs/research/BACKTESTING_ENGINE_RESET.md` |
| Full development plan | `docs/research/HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md` |
| Research index | `docs/research/README.md` |

### Layout (current)

```text
Backtesting Suite/
  Data / Data-Real/     # immutable lake seed (extend; do not rewrite raw)
  Strategies/FIRST01/   # strategy plugin artifacts (legacy runs)
  Runs/                 # historical run packages
  Google Sheets/        # LEGACY_V1 control-plane mirrors
```

### Rules

- Atomic research object: `StateTransition` inside container `GameMarketEpisode`
- Do not fabricate L2 from candles
- Do not auto-mutate production from research
- Waterfall 0 recon: `docs/research/backtesting_rebuild/`
- Next work (pending CEO): **`W1-A1-S1`** lake catalog schema — do not implement yet
