# CTO-W5 SPEC — Event ↔ market time synchronization

**Name:** Join reconstructed EVENT and MARKET clocks with explicit confidence  
**Status:** IMPLEMENTED (join layer)  
**Authorization:** Implementation grant 2026-08-26. W6 not included.  
**PLAN alias:** PLAN-W3 (time sync). **Not** PLAN-W8 `StateTransition` (later).

## Objective

Align W3 PBP/`MlbGameState` timestamps with W4 `MarketPath` venue timestamps.
Emit sync metadata. Never drop a domain because the join failed (ADR-0003).

The north-star **path-aware `S(t)`** (full PBP prefix + price prefix + starting-price
class + sync meta) is specified in [S_OF_T_FIELD_CONTRACT.md](S_OF_T_FIELD_CONTRACT.md).
That vector is the **product** of W4 + W5 + later path packaging. W5 owns **only**
the join: clocks, `time_delta`, `sync_confidence`.

## Inputs

- W3 reconstructed game/PBP (or `event_state = UNAVAILABLE`)
- MATCHED Kalshi historical **trades** (or `market_state = UNAVAILABLE`). This cohort is TRADES_ONLY; L2 remains UNAVAILABLE.
- Identity as consumed (`MAPPED` / `UNMATCHED` / `AMBIGUOUS`) — do not re-guess

## Outputs (when implemented)

- Per observation: `event_timestamp`, `market_timestamp`, `synchronization_delta`,
  `synchronization_method`, `synchronization_confidence`
- Quality report: counts by confidence class; unmatched retained
- **Not** a fabricated 1-second tape. **Not** L2. **Not** `struct` Greeks.

## Confidence (ADR-0003; do not shrink)

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING | AMBIGUOUS | UNMATCHED | UNAVAILABLE
```

Never silently upgrade. `EXACT` requires a tested clock contract.

## Explicitly not this waterfall

- Kalshi market reconstruction (W4)
- Rebuilding `MlbGameState` (W2/W3)
- FIRST01 replay, theta, XGB
- Filling `opening_spread_depth` / `orderbook_path` without game-time books
