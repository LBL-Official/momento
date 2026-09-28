# W2 Architecture

## Boundary

```text
W1 lake (Kalshi raw, immutable)
        │  RawArtifactRef / RawMarketIdentity / ObservabilityKind
        ▼
W2 momento-research-event
        │  CanonicalMlbEvent + MlbGameState + EventTimeState + PbpSequence
        ▼
W3 market reconstruction (NOT IN THIS WATERFALL)
        ▼
W4 synchronization (NOT IN THIS WATERFALL)
```

W2 never writes into `Backtesting Suite/Data-Real/**`. Outputs go to `Backtesting Suite/Foundation/W2/`.

## Multi-sport

Generic concepts: Game, Event, EventSequence, GameState, MlbPbpTransition, EventTimeState, Outcome, Provenance.

Trait: `EventStateAdapter` (`remaining_opportunities` is sport-agnostic).

W5 owns canonical `StateTransition` / `GameMarketEpisode`. W2 does not define those types.

W1 `RawArtifactRef` / `RawMarketIdentity` are **consumed** from `momento_research_data::foundation` (no W2 struct fork). See [W2_CTO_DECISIONS.md](W2_CTO_DECISIONS.md).

MLB adapter: `outs_remaining` / 54-out regulation definition v1 (`ADR-0005`).

NBA / NCAAB / NHL: adapter stubs only. Not implemented.

## Clocks (not interchangeable)

| Clock | Meaning |
|-------|---------|
| `source_event_timestamp` | Official PBP time when present |
| `source_received_timestamp` | Vendor received (rare) |
| `collector_timestamp` | Momento ingest |
| `game_clock` | inning / half / outs |
| `canonical_order` | sequence number |

Kalshi trade `created_time` is a **market** clock (W3/W4).

## State machine

`STATE_before + EVENT = STATE_after`

Invariants fail closed (no silent repair): score/inning cannot go backward; outs cannot decrease in the same half-inning unless `Amendment`; outs cannot exceed 3; walk-off requires bottom ≥ 9 and home ahead.

Lookahead: `MlbGameState` has no winner / final_score / future events. `GameOutcome` is a separate OUTCOME_LABEL object.

## Identity

Official canonical GameId = SHA-256(`research.mlb.game.v1` ‖ source ‖ source_game_id) when an official source id is observed.

Kalshi GameId (live hash of event_ticker) is an alias via W1 stub, `mlb_game_pk = null`, `UNMAPPED`.

Mappings are explicit `MappingRecord`s. Ticker parse is not a mapping.

## Storage (design, not a deployed DB)

See `crates/research-event/src/schema_sql.rs` and `W2_DATA_DICTIONARY.md`.

Intended later join (W4): `mlb_game_states` ↔ market path on explicit sync keys, never by pretending PBP time equals trade time.
