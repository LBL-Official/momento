# Proposed Canonical Domain Model

**Status:** Design only. No Rust types in this step.  
**Sport-first:** MLB is the reference adapter. Core names are sport-agnostic.  
**Financial types:** reuse `momento-core` integer `Money` / `Price` / `Contracts`. Do not introduce `f64` money.

This document reconciles two north-star statements:

1. Existing reset: primary object = `GameMarketEpisode`
2. This rebuild brief: fundamental research object = `StateTransition` (not a trade)

**Resolution:** a trade is never the unit of truth.  
`StateTransition` is the **atomic** reconstructable observation.  
`GameMarketEpisode` is the **container** (one game, both contracts, full paths, outcomes).  
FIRST01 is a **plugin** that walks transitions; it does not define the schema.

---

## 1. Immutability layers

| Layer | Mutability | Examples |
|-------|------------|----------|
| **IMMUTABLE** | Never rewrite | Raw Kalshi JSONL, raw PBP payloads, raw settlement blobs, file checksums |
| **REPRODUCIBLE** | Versioned replace-by-new-version only | Normalize vN, event reconstruction vN, sync vN |
| **MUTABLE** | Experiment-scoped | Features, labels, hyperparameters, plugin params (except frozen FIRST01 baseline), reports |

Invariant: a new parser never overwrites `raw/`. It writes `normalized/schema=N/` (or equivalent).

---

## 2. Observability (required on every important field)

```text
OBSERVED     — present in an immutable raw record
DERIVED      — deterministic function of observed data at ≤ t (no lookahead)
INFERRED     — join/sync that can be wrong; must carry confidence
MODELED      — simulation (fills, fees, queue, theta formula later)
UNAVAILABLE  — not in source; null + reason; never fabricated
```

Never promote INFERRED → OBSERVED. Never fill UNAVAILABLE with interpolated L2.

---

## 3. Generic core concepts (interfaces)

```text
Sport
League
Season
Team
Game                         — sport event instance (MLB game)
Event                        — discrete PBP/game event
Market                       — Kalshi market (one YES contract)
Contract                     — alias of Market for two-sided game packs
EventState                   — sport clock + score + situation
MarketState                  — book/trade/status at t
OrderBookState               — levels if OBSERVED, else UNAVAILABLE
SynchronizedState            — EventState + MarketState + SyncMeta
StateTransition              — atomic research object
GameMarketEpisode            — full game × both contracts × paths
Signal / Order / Fill / Position   — strategy/execution plugin outputs
Outcome                      — settlement / official result
Experiment / DatasetVersion / Model / ModelVersion
Artifact / Provenance
```

MLB-specific fields live behind `MlbEventAdapter` / `MlbStateView`. NBA/WNBA/NHL/NCAAB get empty adapter traits only — **not implemented** until MLB is end-to-end.

---

## 4. Provenance (every raw and normalized row)

Minimum tuple:

```text
source                  # kalshi_rest, kalshi_ws, mlb_statsapi, …
source_record_id        # trade_id, pbp play id, candle period key, …
source_timestamp        # exchange or official event time (nullable + reason)
ingestion_timestamp     # collector receive
raw_file                # path + offset/line if applicable
checksum                # payload hash and/or file hash
schema_version
observability           # OBSERVED/DERIVED/…
```

Current `RawMarketEvent` has only `received_at`, `source`, `endpoint`, `ticker`, `payload`. Waterfall 1 must specify v2 envelope **without rewriting v1 gzip**.

---

## 5. EVENT DOMAIN (MLB adapter view)

Logical `EventState` at time θ_event (not wall clock alone):

```text
game_id                  # internal canonical
mlb_game_pk              # official, when mapped
timestamp_event          # official PBP time if any
timestamp_wall           # UTC
inning, half_inning
outs, remaining_outs_approx   # remaining_outs is DERIVED; exact extra innings rules versioned
score_home, score_away, score_diff
runners                    # occupancy; runner ids if OBSERVED
batter_id, pitcher_id
pitch_count, plate_appearance_index
pitch_state                # if pitch-by-pitch OBSERVED
play_result, previous_play_id
pbp_sequence
game_status
home_away
eventual_outcome           # FORBIDDEN on any state used for replay at t
                           # stored only on Outcome / terminal episode fields
```

**Event theta (architecture, not formula):**

```text
EventThetaInputs {
  remaining_opportunities,   # outs-centric for MLB, plus inning/half/base
  information_rate_proxy,    # slot for later empirical model
  state_significance_proxy,  # slot; e.g. leverage-like, not a hardcoded Greek
}
```

Do **not** ship a universal theta equation in Waterfall 1. Preserve the inputs.

---

## 6. MARKET DOMAIN

Logical `MarketState` per contract at t:

```text
market_id, ticker, contract_side (Team A YES / Team B YES)
timestamp_exchange, timestamp_received
yes_bid, yes_ask, bid_size, ask_size
last_trade, last_trade_size
spread                     # DERIVED if bid+ask OBSERVED
depth / levels             # OBSERVED only if source has them
volume (session / lifetime as source defines)
market_status
```

**StartingMarketState** (mandatory when available; else UNAVAILABLE with reason):

```text
team_a_yes_start { bid, ask, spread, ts, liquidity }
team_b_yes_start { … }
first_observed_state
market_open_ts             # from metadata if OBSERVED
time_from_open_to_first_obs
source_of_start            # first trade vs first candle vs metadata open
```

Every later state must point at `starting_state_ref` for that contract.

**Market theta (architecture, not formula):** path of price, velocity, acceleration, spread, liquidity, depth, imbalance, volatility, event-to-market lag — all **DERIVED/MODELED later** from stored path. Waterfall 1 only preserves the path.

---

## 7. SYNCHRONIZED STATE

```text
SynchronizedState {
  timestamp_anchor,          # declared clock
  event_state,
  market_state_team_a,
  market_state_team_b,
  sync_meta: {
    confidence,              # EXACT | WITHIN_1S | WITHIN_5S | WITHIN_INNING | UNALIGNED | UNAVAILABLE
    method,                  # timestamp join, inning join, …
    event_lag, market_lag,
  }
}
```

Confidence is never silently upgraded.

---

## 8. StateTransition (atomic research object)

```text
StateTransition {
  game_id
  market_ids                 # both contracts
  timestamp

  event_state_before
  event_state_after          # after this event, if event-triggered
  market_state_before
  market_state_after

  trigger                    # PBP_EVENT | TRADE | CANDLE_CLOSE | BOOK_UPDATE | TIMER

  event_path_ref             # pointer into immutable path store (not only snapshot)
  market_path_ref

  strategy_state             # optional; plugin-owned; empty in data layer
  execution_state            # optional; MODELED if present
  outcome_state              # only if t is terminal OR stored separately with leak guard

  provenance
  observability
  dataset_version
}
```

Lookahead invariant: fields visible to a strategy plugin at t must not include future PBP, future book, or eventual winner.

---

## 9. GameMarketEpisode (container)

```text
GameMarketEpisode {
  identity                   # GameId + MLB pk + both MarketIds
  starting_market_state      # BOTH sides
  event_path                 # ordered PBP/state
  market_path_a, market_path_b
  synchronized_path
  first_touches              # 20,30,40,50,60,70,80,90,95 if they occur
  outcome
  coverage                   # which layers OBSERVED vs UNAVAILABLE
  provenance
}
```

Threshold definition: **FIRST TOUCH** of YES bid (same qualifying price as live), not average time above threshold.

At each first-touch, persist: market state, event state, PBP, path refs, starting price, event-time vars, market-time vars, liquidity, book (or UNAVAILABLE), sync confidence, eventual outcome (label store, not replay input).

---

## 10. Path requirement

Do not store only the 80% snapshot. Persist (by reference to raw/normalized streams):

```text
START → trajectory → first 50 → 60 → 70 → 80 → 81 confirm
      → entry (plugin) → 89 lock → adverse/favorable → stop/exit/settlement
```

If a node never occurs, record `DID_NOT_OCCUR` rather than omitting the field.

---

## 11. Strategy / execution / risk (plugin boundary)

```text
HistoricalStateEngine  →  StrategyPlugin (FIRST01)  →  ExecutionModelPlugin
                       →  Labeler
                       →  (later) Prediction
                       →  (later, UNTOUCHED live) Risk Decision Engine
```

The data layer must compile **without** FIRST01. FIRST01 consumes transitions.

Risk and live execution remain UNTOUCHED. A future waterfall may feed **the same state schema** live; that is not Waterfall 1.

---

## 12. Multi-sport

Core crate (name TBD) knows `Sport` and adapter traits.  
`ResearchSport::{Mlb,Wnba}` today is too small and WNBA-coupled; wrap rather than delete.

NBA / WNBA / NHL / NCAAB: trait bounds only. MLB must complete before those adapters are implemented.

---

## 13. Schema candidates (for Waterfall 1, not implemented here)

See [WATERFALL_NEXT_STEP.md](WATERFALL_NEXT_STEP.md) for raw-envelope JSON candidates. Normalized event/market state schemas belong to later waterfalls; Waterfall 1 only needs:

- `raw_envelope_v2` (additive)
- `lake_catalog_v1` (inventory of immutable files)
- `coverage_record_v1` (what is missing, honestly)
- `identity_stub_v1` (Kalshi ticker ↔ GameId/MarketId as today, plus empty MLB pk slot)
