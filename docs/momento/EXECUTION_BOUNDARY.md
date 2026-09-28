# Momento Systems — Execution Boundary

```text
LIVE EXECUTION = FALSE
```

This architecture project must not authorize trading.

## Do not

- Start or stop `momento-live.service`
- Set `VITAL_AWS_CONTROL`
- Place a production or demo test order
- Modify MLB 001 behavior
- Modify live FIRST01 / 80/81/83/89
- Create an NBA live bot unit
- Start W9 or warehouse Phase 21
- Treat candle path as a fill
- Bypass `crates/risk`

## NBA bot

```text
NO NBA SUBMISSION IMPLEMENTATION
bot_id: nba-001 (alias nba-first80-001), strategy FIRST78_67
worker: momento-nba-001.service (apps/nba-001, strategies/nba)
submission adapter linked (deployed build): false
submission adapter in source: fixture + demo only; production orders compiled out
submits: false
```

Owner-authorized exception (2026-09-26) to "Create an NBA live bot unit":
`momento-nba-001.service` may run on the production host. It reads
production market data and GET-only account state, records local intents
and blockers, and runs a SHADOW hedge path. It links no submission
adapter, so it cannot place, amend, or cancel orders or move funds. It
is not a live bot unit. Deploying a build that carries the order adapter,
or compiling production orders in, is outside this exception and needs a
resolved execution contract plus explicit owner approval. How-to: `docs/operations/NBA_001.md`.

Vital `:5180` is not the Algorithmic Execution frontend.

## Existing MLB live path (reference only; do not modify)

```text
Kalshi WS
  → strategies/mlb (80 → 81, max 83, lock 89)
  → crates/risk
  → apps/trading-engine live.rs
  → Kalshi Create V2
```

Triple gate: `mode=live` AND `live.enabled=true` AND
`confirmation=ENABLE_LIVE_TRADING`.

[`config/live.toml`](../../config/live.toml) already contains those gates
for MLB. Architecture work does not read that file as permission.

Browser never submits. Vital does not submit. Jump does not submit.

## Hooks (names only)

Reserved for a future NBA bot identity, not enabled:

- `capital_limit`
- `max_position`
- `kill_switch`
- `stale_data_guard`
- `duplicate_order_guard`
- `reconciliation_guard`

`crates/risk` remains the live Risk Decision Engine.
Austin DRE is research post-entry hold-reason.

## Registry

Every system has `live_capability: false`.
`feature_flags` includes `LIVE_EXECUTION=FALSE`.
Tests assert both.
