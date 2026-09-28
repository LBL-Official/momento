# MLB Bot 001 — Phase 5 Market → Signal → Risk → Execution

Dated: 2026-09-14.

This file is Phase 5. It exposes the **existing** deterministic path.
It does not retune 80/81/83/89. It does not invent fills.

## Path (FACT)

```text
Kalshi WS
  → strategies/mlb TradeIntent
  → crates/risk PaperRiskEngine.decide_entry
  → apps/trading-engine live.rs submit_approved
  → Kalshi Create V2
  → fill
```

MODEL ≠ RISK ≠ EXECUTION.

- Strategy proposes. It does not submit.
- Risk approves or rejects. It does not submit.
- Only `submit_approved` after `RiskDecision::Approved` reaches the venue.
- Browser and Vital API do not submit.

## Contract

`GET /vital/bots/{id}/pipeline` (`roller.vital.mlb_001.pipeline`) lists
stages:

```text
MARKET_DATA → NORMALIZATION → FEATURE_STATE → SIGNAL
  → RISK → ORDER_DECISION → EXECUTION → FILL
```

Locked signal: `80_to_81_yes_bid` (80 / 81 / 83 / 89).

Honesty:

- Per-stage host dumps stay `OBSERVATION_UNAVAILABLE` until the host
  publishes them
- `does_not_invent_fills = true`
- `catalog_fills_are_not_trades = true`
- `fill_not_trade = true`
- Live EV / Sharpe = `UNAVAILABLE`

A complete documented/API path from observation to execution event now
exists. One-row-per-market reconstruction is Phase 6
(`research/vital/BOT_001_PHASE6.md`).

## Acceptance checklist

- [x] Path documented as facts, not a new engine
- [x] 80/81/83/89 unchanged (`strategies/mlb` not edited)
- [x] Risk remains the only approval gate
- [x] Fills are not invented
- [x] Catalog fills are not grouped into trades
- [x] `apps/trading-engine` / `crates/risk` not edited

## STOP

```text
PHASES 3–5 COMPLETE
        ↓
STOP
        ↓
Phase 6 is implemented separately (`BOT_001_PHASE6.md`).
```
