# FIRST01 — Current Live Strategy Research Model

> **Platform note (2026-08-26):** The candle-era FIRST01 backtester is **LEGACY_V1**.
> The new research platform is the historical event–market engine
> ([plan](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md), [reset](BACKTESTING_ENGINE_RESET.md)).
> FIRST01 remains the frozen **strategy plugin / control baseline** (80/81/83/89/50%),
> not the definition of the backtesting platform.

`FIRST01` is the versioned research representation of Momento's **current** live MLB
(`KXMLBGAME`) and WNBA (`KXWNBAGAME`) desk strategy. It does not submit orders and does
not modify production trading.

- **Name:** `FIRST01`
- **Version:** `1`
- **Crate:** `momento-research-strategies`

## Architecture

```
StrategyModel (FIRST01 v1)
    ├── default EntryParameters  (immutable baseline)
    ├── default ExitParameters   (immutable baseline)
    ├── supported_series: KXMLBGAME, KXWNBAGAME
    │
    ├── EntryEngine  → EntrySignal (maker-only research signal)
    └── ExitEngine   → ExitSignal  (loss-trigger research signal)

ExperimentOverrides (per backtest)
    ├── entry thresholds (optional)
    ├── exit fraction (optional)
    └── universe / season / dates (optional)
```

**Strategy = WHAT** (FIRST01 rules, versioned)  
**Parameters = HOW THIS EXPERIMENT RUNS IT** (overrides)

## ENTRY (default parameters)

1. Observe authoritative **YES bid** (not mid, not last trade).
2. Reject quotes with `sequence_gap = true`.
3. Record **first** observation `>= 80¢` on the same `GameId` + `MarketId` + `Side`.
4. Confirm same `MarketId` + `Side` subsequently reaches `>= 81¢`.
5. If bid reaches `>= 89¢` on the bound market/side → **GAME_LOCKED** (no new entry).
6. After confirmation, qualifying bid must remain in **80–83¢** band.
7. **Maker limit** = qualifying YES bid; require `bid < ask`.
8. Emit `EntrySignal` when maker-eligible. No order simulation.

### Default entry parameters

| Parameter | Value |
|-----------|-------|
| `first_threshold_cents` | 80 |
| `confirmation_threshold_cents` | 81 |
| `maximum_entry_price_cents` | 83 |
| `lock_threshold_cents` | 89 |
| `require_bid_below_ask` | true |
| `maker_only` | true |

## EXIT (default parameters)

1. Compute **actual entry VWAP** from entry fills (not submitted limit/qty).
2. Stop threshold = **50%** of VWAP basis (integer division on hundredths-of-cent).
3. Monitor **PositionId → MarketId → Side** only.
4. Trigger when authoritative YES bid crosses threshold (`bid_cents * 100 <= stop_hundredths`).
5. Sharp gaps trigger at first observed crossing (e.g. 81 → 24 triggers at 24).
6. Once triggered → `LIQUIDATION_ACTIVE`; recovery above stop does **not** return to OPEN.
7. Partial fills reduce `remaining_quantity`; zero-fill keeps liquidation active.
8. Emit `ExitSignal`; no fill simulation.

### Default exit parameters

| Parameter | Value |
|-----------|-------|
| `loss_numerator` / `loss_denominator` | 1 / 2 (50%) |

## Market identity

Every signal carries independent:

- `game_id`
- `market_id`
- `ticker`
- `side`

Two YES markets per game (e.g. WSH vs COL) never share entry sequence or stop scope.

## Live code alignment

FIRST01 mirrors:

- `strategies/mlb/src/quote.rs` — thresholds, maker limit
- `strategies/mlb/src/strategy.rs` — 80/81/89 sequencing
- `strategies/mlb/src/stop.rs` — position-scoped 50% stop
- `strategies/wnba/src/lib.rs` — same machine, `StrategyId::WNBA`
- `crates/core/src/basis.rs` — VWAP + half-stop math

### Known structural note

Live entry state is stored **per GameId** with the bound `MarketId` recorded in
`first_80`. FIRST01 research signals key identity as `EntryStateKey { game_id, market_id, side }`
while preserving the same sequencing rules (only the first bound market/side progresses).

## Reproducibility metadata

`StrategyRunMetadata::for_first01(overrides)` records:

- `strategy_name`, `strategy_version`
- effective parameter set
- series / season / date range
- optional dataset schema version and manifest checksum (filled by future runner)

## What FIRST01 does NOT do

- Order submission
- Fill simulation
- P&L
- Risk desk caps (5-position limit enforced live by Risk, not in FIRST01)
- Google Sheets integration

## Future Google Sheet mapping (not implemented)

| Sheet field | Maps to |
|-------------|---------|
| Entry Condition - Model | `FIRST01` |
| Entry Condition - Price Range | `ExperimentOverrides.entry` |
| Exit Condition - Model | `FIRST01` |
| Ticker | `ExperimentOverrides.series` |
| Season / Time Frame | `ExperimentOverrides.season` / dates |
