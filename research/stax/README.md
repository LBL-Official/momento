# STAX

Multi-strategy research stack. ROLLER-native composition, versioning,
and recurring re-execution.

```
LIVE EXECUTION = FALSE
RESEARCH AUTOMATION ≠ EXECUTION
AGGREGATION_METHOD = NONE
STRATEGY INDEPENDENCE ≠ STATISTICAL INDEPENDENCE
CANDLE PATH ≠ ACTUAL FILL
DO NOT CHANGE LIVE FIRST01 / 80/81/83/89
```

STAX is not a trading system, not a portfolio optimizer, not a second
query compiler, and not a SuperASI replacement.

```
ROLLER
  ONE RESEARCH OBJECT
  ONE QUESTION
  ONE MEASUREMENT

STAX
  MULTIPLE RESEARCH OBJECTS
  ONE COMMON UNIVERSE
  INDEPENDENT MEASUREMENTS

SUPERASI
  DOWNSTREAM ANALYSIS
```

## V1 locks

1. **Fixed timeframe.** Automation re-runs the saved
   `sport + league_set + seasons + date_from + date_to`. It does not
   slide the window forward.
2. **`member_id` ≠ position.** `STXM-0007` is durable. `position` is
   order. `STX01-S01` is presentation only.

## Homes

- Package: `ROLLER/roller/stax/`
- Disk library: `research/stax/library/`
- API: `/stax/*` on the ROLLER terminal (`:8791`)
- UI: `frontend/roller-terminal/src/stax/` (same Vite app, ROLLER shell)

## Status

STAX V1.1. Live authorized: False. STAX does not submit orders.

Create path: `POST /stax/{stax_id}/strategies` compiles a ROLLER draft,
writes a real research-library save, then adds a STAX member. Cancel
persists nothing. Universe lock is enforced before membership.
