# Momento Systems — Dataflow

Point-in-time integrity is mandatory. Missing is never `$0`.
Candle path is not a fill.

## FIRST80 V0 target

```text
DATA INGESTION
      ↓
DATABASE / ROLLER
      ↓
PATH EFFICIENCY ← DATA ANALYSIS / SUPERASI

DATA INGESTION
      ↓
FAIR ODDS          (NOT IMPLEMENTED)
      +
IN-HOUSE ODDS      (XIB frozen; market residual blocked)
      ↓
TERMINAL EFFICIENCY

PATH EFFICIENCY
      +
TERMINAL EFFICIENCY
      ↓
SIGNAL GENERATION  (research touch-80; no NBA live)
      ↓
FIRST80 ENTRY
      ↓
TRADE BREAKDOWN
      +
POSITION STRATIFICATION
      ↓
OPEN POSITION
      ↓
AUSTIN / DRE       (research; Choosin+Austin feed; αP>0 then ΔP→ΔP*(Xt); not policy)
      ↓
HEDGING ANALYSIS   (PARTIAL · Ballhog :5192; BDR library)
      +
RELATIVE VALUE     (PARTIAL · TK Ultra formula, not truth)
      ↓
POSITION MANAGEMENT (NOT IMPLEMENTED)
      ↓
TARGET EXPOSURE
      ↓
ALGORITHMIC EXECUTION  (MLB exists; NBA bot absent)
      ↓
ORDERS / HEDGES / FILLS
      ↓
DATABASE
      ↺
```

A complete deterministic lifecycle object is Phase 4.
Do not invent missing hops.

## N universes (do not mix)

- asked-six 1182
- derived four 936
- barrier-55 905
- NBA 2Q∪3Q 604
- NBA FULL 1230
- path-FE 797
- NBA 2Q RS book baseline 280

## Known honest gaps

- Fair odds has no source.
- Game Modeling cannot consume F_t vs K_t.
- Signal Generation has no NBA live feed.
- Relative Value Hedging has `GENERIC_RV` (`tk_relative_value_v1`) and `BINARY_COMPLEMENT_V0` on TK Ultra `#/tk-ultra`. The formula is not market truth. Missing = UNAVAILABLE. Ballhog is an optional sibling, not upstream evidence.
- Position Management has no current-vs-target object.
- Algorithmic Execution has no NBA bot.
- DRE must not be treated as a live reduce/hedge/exit policy.
  V1 objective (`research/dre/PORTFOLIO_OBJECTIVE_V1.md`) is a
  research memo. Do not invent `Λα` or `ΔP*(Xt)`.
