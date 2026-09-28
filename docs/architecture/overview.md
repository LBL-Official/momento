# Architecture overview

Founder print briefing: [`docs/founder/MOMENTO-TRADING-DESK.md`](../founder/MOMENTO-TRADING-DESK.md).

## Module boundaries

| Crate | Owns | Must not |
|---|---|---|
| `momento-core` | Money, IDs, snapshot, position, order, fill, audit, intents, venue traits | I/O, MLB signals, Kalshi HTTP |
| `momento-risk` | Exposure approval, incremental budget vs snapshot | Venue transport |
| `momento-execution` | Order lifecycle, paper venue | Approving exposure |
| `momento-positions` | Fill-authoritative tracker, one GameId → one PositionId, reconciliation | Strategy signals, venue HTTP |
| `momento-kalshi` | Adapter mapping, demo HTTP/WS, production **read-only** auth | Live order submission, PositionId creation |
| `momento-pnl` | P&L ledger from fills/fees/settlement | Invented Kalshi economics |
| `momento-sports` | Sport modules (`mlb`, …) | Execution/risk copies |
| `momento-strategy-mlb` | MLB 80/81/89, TradeIntent | Kalshi, execution, bankroll math |
| `apps/*` | Composition roots | Silent live arming |

`apps/prod-auth-validate` may authenticate to Kalshi production for
read-only M9 checks. It must not submit orders.

Dependencies flow inward to `core`. Strategy does not depend on `kalshi` or `execution`.

## Domain ownership

- Strategy proposes desired exposure (`BuildPositionIntent`).
- Risk approves against the weekly snapshot and remaining **filled** budget.
- Execution accepts only `ApprovedTradeIntent`.
- Position tracker is fill-authoritative.
- `GAME_LOCKED` is an entry lock, not a flatten.
- Stop/liquidation is independent of 89% lockout.
- No take-profit. No discretionary exit.

## Exact financial representation

- `Money`: integer USD cents (`$6.25 = 625`).
- `Price`: integer contract cents (`80` = 80¢). Range `0..=100`.
- `Contracts`: integer quantity.
- `Bps`: basis points (`12.5% = 1250`).
- `EconomicExposure`: fill premium in cents; fees are separate (`FeeKind::Entry` vs `Liquidation`).
- `BasisPrice`: hundredths of a cent for stop math (`40.50¢ = 4050`). 50% stop uses integer division of VWAP hundredths.

No `f64` for money, price, qty, fees, P&L, or stops.

`$50 × 12.5% = $6.25` uses `Money::checked_mul_bps`.

## Position identity

`GamePositionIndex`: one `(StrategyId, GameId)` → one `PositionId`.

Remaining target = approved budget − actual fill premium − entry fees.

Never remaining = budget − submitted.

## Risk authority

Every incremental entry is checked against the **original** snapshot budget.
`ApprovedTradeIntent` is the only type execution will submit.

## Execution authority

Paper venue: ack, partial fill, cancel, replace, unknown, liquidation, settlement hook (settlement is a position transition).

`UNKNOWN` ≠ failed. It requires reconciliation (`Found` / `NotFound` / `Ambiguous`).

## Reconciliation

`ReconciliationState::{Required, Reconciling, Ambiguous}` block new exposure.
Only `Healthy` permits new exposure, and only after risk gates pass.

Outcomes: `FOUND` / `NOT_FOUND` / `AMBIGUOUS`. Timeout is `UNKNOWN`, not failure.

See `docs/architecture/positions.md`.

## Audit model

Append-only `AuditEvent` enum + `InMemoryAuditLog`. No overwrite API.

## State machines

See `docs/architecture/state-machines.md`.

## Research engine (historical)

Research crates (`momento-research-*`) reconstruct MLB event/PBP and Kalshi
market history. They must not submit live orders.

W5 event↔market time synchronization: [`w5-synchronization.md`](w5-synchronization.md).
W6 canonical MLB state: [`w6-state-engine.md`](w6-state-engine.md).
W7 EventMarketPath: [`w7-event-market-path.md`](w7-event-market-path.md).
W8 FIRST01 replay: [`w8-first01-replay.md`](w8-first01-replay.md).
B1 price features: [`b1-price-features.md`](b1-price-features.md).
Research Engine v1: [`current-state.md`](current-state.md),
[`target-state.md`](target-state.md).
Do not start W9 (outcome labeling / Greeks) from this overview.

Systems roadmap (dependency-ordered; Oct 1 = dual-market ingest +
Autoingest): [`MOMENTO_SYSTEMS_ROADMAP.md`](MOMENTO_SYSTEMS_ROADMAP.md).
