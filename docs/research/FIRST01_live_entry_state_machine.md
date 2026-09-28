# LIVE ENTRY STATE MACHINE (FIRST01 / MLB)

Source: `strategies/mlb/src/strategy.rs`, `strategies/mlb/src/quote.rs`

```
IDLE (Watching)
  | YES bid >= 80 on (GameId, MarketId, Side)
  v
FIRST_80 (First80Triggered)
  | same market+side, YES bid >= 81
  v
CONFIRMED_81 (EntryEligible)
  | maker_limit valid AND NOT has_working_entry AND NOT position blocks
  v
ENTRY_INTENT (Build TradeIntent) — ONE per opportunity cycle
  | execution submits order → has_working_entry=true
  v
ENTRY_WORKING — blocks duplicate intents
  | fill(s)
  v
POSITION_BUILDING / POSITION_OPEN — blocks duplicate intents
  | YES bid <= 50% entry VWAP (position-scoped)
  v
LIQUIDATION_ACTIVE — blocks duplicate intents
  | flat
  v
TRADE_COMPLETE — may allow new opportunity if not GameLocked

Parallel terminal: YES bid >= 89 → GAME_LOCKED (permanent for game)
```

## Concurrency

- **Trade scope:** one active FIRST01 trade per `GameId`
- **Opportunity identity:** `GameId` + `MarketId` + `Side` + opportunity sequence
- **Exit identity:** `PositionId` + `MarketId` + `Side`

## Research mapping

Research `EntryEngine` now mirrors live entry gating via `EntryContext`:
`has_working_entry`, `position_net_qty`, `liquidation_active`.
