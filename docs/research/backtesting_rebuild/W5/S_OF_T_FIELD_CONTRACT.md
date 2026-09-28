# W5 field contract — Enriched `S(t)` (design only)

**Status:** DESIGNED. **Not authorized to implement.**  
**Date:** 2026-08-26  
**Source:** Layer-4 brief (time sync + path-aware `S(t)`).  
**Does not authorize:** skipping W4, inventing L2/mids/open prices, merging W6/W7 into this crate. W5 **join layer is implemented**; the full denormalized `S(t)` product still requires later path packaging.

This note maps the proposed **enriched synchronized state vector `S(t)`** onto
Momento objects and observability. It does **not** create `struct SynchronizedState`
in Rust.

---

## Numbering lock (2026-08-26 grant)

| This brief’s name | Grant / execution | Already exists? |
|-------------------|-------------------|-----------------|
| Raw Kalshi ticks + MLB PBP | DATA-INGEST + W1 lake + W2/W3 | Partial. L2 **UNAVAILABLE**. Most mapped Kalshi still metadata-only; June 18 has trades. |
| *(missing in brief)* **Market reconstruction** | **CTO-W4** | Docs started; **crate not shipped**. Independent of PBP (ADR-0003). |
| W5 Time Synchronization | **CTO-W5** | Design only. ADR-0003 confidence enum. |
| W6 Canonical MLB State Engine | Instantaneous `GameState` is **CTO-W2/W3** (CLOSED). Joined `EventState+MarketState` at `t` is **after W4+W5**. | Do not rebuild W2. |
| W7 Event/Market Path Engine | Path attachment into `GameMarketEpisode` — **later** (grant W6+ / PLAN-W8). ADR-0016. | Do not skip W4/W5. |
| `GameMarketEpisode` vector | Container (ADR-0016) | Docs only. No Rust type yet. |

The brief’s pipeline `RAW → W5 → W6 → W7` **omits W4**. Correct pipeline:

```text
IMMUTABLE RAW (PBP envelopes + Kalshi envelopes/lake)
        │
        ├─► W2/W3  GameState / PBP sequence          (CLOSED)
        └─► W4     MarketPath / MarketState          (THIS is not sync)
                │
                ▼
        W5     Time sync + confidence + delta        (NOT STARTED)
                │
                ▼
        later  StateTransition inside GameMarketEpisode
               (prefix ≤ t of BOTH paths; not an 80% snapshot)
```

**Do not merge W5+W6+W7 in code** until W4 can emit an honest `MarketPath` and
W5 can join clocks without upgrading confidence. Product *shape* of `S(t)` can
be specified now; implementation cannot skip waterfalls.

---

## Architectural intent (accepted as *goal*, not as data claim)

| Claim | Momento position |
|-------|------------------|
| `S(t)` is path-aware, not only a PIT snapshot | **Yes** (ADR-0016). FIRST01 at 80¢ must see the prefix, not a reconstructed fill. |
| Leakage-proof: fields at `t` cut off at timestamp `t` | **Yes**. No future PBP, quotes, or settlement as features. |
| Zero memory loss = copy full history onto every tick | **Logical** prefix ≤ `t` is required. **Physical** copy of `pbp_history` + `price_trajectory` onto every second is an encoding choice (cursor into append-only sequences is allowed). Do not invent extra ticks to fill 1-second holes. |
| Unified unit for Greeks / FIRST01 / XGB | **Yes**, after paths exist. Plugins consume episodes; they do not define the schema. |

---

## `S(t)` field map (honesty)

Observability: OBSERVED / DERIVED / INFERRED / MODELED / UNAVAILABLE.
Never promote INFERRED → OBSERVED. Never fill UNAVAILABLE with interpolation.

### Initial context

| Proposed field | Allowed meaning | Current truth |
|----------------|-----------------|---------------|
| `starting_odds_team_a` / `b` | W1 `StartingPriceClass`: `MARKET_OPEN_PRICE` only if venue `open_time` **and** an observed book/trade at that instant. Else `FIRST_OBSERVED_PRICE` or `STARTING_PRICE_UNVERIFIED`. Integer cents. `None` ≠ 0. | **Almost always UNVERIFIED.** First candle/trade is **not** market open. Two YES contracts come from W4 `CoupledMarketEpisode` after reconstruction. |
| `opening_spread_depth` | Depth, spread, creation timestamps **only if** a game-time book exists. Spread is DERIVED iff both bid and ask OBSERVED and ask ≥ bid. | **UNAVAILABLE.** Historical L2 does not exist. PIT REST ingest books are **NOT_GAME_TIME**. Candles are not depth. Do **not** put candle close bid/ask here. |

### Instantaneous game state

These are **W2 `MlbGameState`** (already implemented). W5 must **reference** them, not fork them.

| Proposed field | W2/W3 object | Notes |
|----------------|--------------|--------|
| `inning`, `half_inning` | `inning`, `half` | Top/bottom = batting team, not Kalshi “possession”. |
| `outs`, `balls`, `strikes` | `outs`, `balls`, `strikes` | Missing pitch → UNAVAILABLE on the event, not guessed. |
| `runners_on_base` | `runners: DataField<BaseOccupancy>` | Bitmask only if OBSERVED from PBP. |
| `score_home` / `away` | `score` + DERIVED differential / `lead` | Cumulative at that event; not settlement. |
| `batter` / `pitcher` | `batter`, `pitcher` | UNAVAILABLE when StatsAPI omits matchup. |

W5 must not invent game state from trades.

### Cumulative PBP path

| Proposed field | W2/W3 object | Notes |
|----------------|--------------|--------|
| `pbp_history` | Ordered `CanonicalMlbEvent` sequence, causal prefix ≤ `t` | W3 reconstruction. Synthetic labeled and excluded from historical coverage. |
| `event_sequence_id` | `sequence` / `state_seq` | Deterministic. No lookahead. |

Game-tree items in the brief (plate appearance, pitch, play, substitutions, reviews, delays, game status) are **W2/W3 ingestion/replay**, not W5. Do not re-parse PBP in the sync crate.

### Cumulative price path

| Proposed field | Allowed meaning | Current truth |
|----------------|-----------------|---------------|
| `price_trajectory` | Time-ordered **OBSERVED** W4 `MarketPoint`s with `kind ∈ {TRADE, CANDLE_1M, TOP_OF_BOOK, L2_*}` and venue `exchange_timestamp` ≤ `t`. | **Trades** where ingest/lake has them (e.g. 2026-06-18). **1-minute candles** where present (still CANDLESTICK, not ticks). **Not** a 1-second grid. Do not interpolate seconds. |
| `orderbook_path` | Bid/ask/size/depth **only** from game-time TOP_OF_BOOK / L2 points | **UNAVAILABLE** as a book path. Candle OHLC bid/ask may appear on the **candle** trajectory with kind `CANDLE_1M`, never as `orderbook_path`. Volume **velocity** is DERIVED later from OBSERVED prints/candles; forbidden as OBSERVED microstructure. |

### Synchronization metadata

ADR-0003 enum (**do not shrink**):

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING | AMBIGUOUS | UNMATCHED | UNAVAILABLE
```

The brief’s `{EXACT, WITHIN_1S, WITHIN_3S, AMBIGUOUS}` is a **subset**. Keep `WITHIN_5S`, `WITHIN_INNING`, `UNMATCHED`, `UNAVAILABLE`.

| Proposed field | Rule |
|----------------|------|
| `sync_confidence` | INFERRED. Never upgraded to EXACT because a trade is “close”. EXACT only if a written, tested clock contract proves equal timestamps. |
| `time_delta` | `market_timestamp - event_timestamp` when **both** venue/official clocks exist. If either clock is missing: `UNAVAILABLE`, do not use ingest `received_at`. |
| One-sided games | PBP without Kalshi: `market_state = UNAVAILABLE`, event path retained. Kalshi without PBP: `event_state = UNAVAILABLE`, market path retained. **Never drop raw.** |

Failed identity (`UNMATCHED` / `AMBIGUOUS`) is **not** a sync class upgrade. Identity is upstream of W5.

---

## Game identification block (brief appendix)

| Brief item | Owner | Status |
|------------|--------|--------|
| Game identification | W2 identity + ingest pairs | CLOSED / consumed |
| Team normalization | W2 match (abbr suffix); no guess in W4/W5 | CLOSED |
| PBP / pitch / PA / bases / outs / inning / score / batter / pitcher | W2 parser + state machine | CLOSED |
| PBP sequence, prev/next linkage | W2 replay | CLOSED |
| Game completion, settlement outcome | Outcome **label** only; forbidden as feature at `t` < settlement | W1 `OUTCOME_LABEL` |
| PBP validation | W3 reconstruction | CLOSED |

W5 consumes these; it does not re-implement them.

---

## What would be illegal to implement from this brief as-is

1. Fill `opening_spread_depth` or `orderbook_path` from candles or PIT REST.
2. Treat first trade/candle as `starting_odds` / market open.
3. Build a 1-second `price_trajectory` by interpolating.
4. Assign `EXACT` sync without a clock contract + tests.
5. Skip W4 and join raw ticks to PBP in one crate.
6. Store settlement winner on `S(t)` for replay at `t`.
7. Retune FIRST01 80/81/83/89 as part of this layer.

---

## Minimum honest `S(t)` schema (when W5 is authorized)

Logical record (names indicative):

```text
S(t):
  identity          # MAPPED | UNMATCHED | AMBIGUOUS (consumed)
  event_state       # MlbGameState | UNAVAILABLE
  pbp_prefix        # events with official_ts ≤ t   (ref or cursor)
  market_a          # MarketPath prefix ≤ t | UNAVAILABLE
  market_b          # same; missing_side explicit
  starting_price    # StartingPriceEvidence (usually UNVERIFIED)
  book              # UNAVAILABLE unless game-time L2/TOB exists
  sync              # confidence + delta + method + both clocks
  cutoff            # t  (hard leakage fence)
```

`GameMarketEpisode` holds the two full paths + outcome labels. Each `S(t)` /
`StateTransition` is a **cut** of that episode at `t`, not a second warehouse
of invented ticks.

---

## Next W/A/S (do not start unless authorized)

1. **Finish CTO-W4** market reconstruction on 2026-06-18 (crate still missing).
2. **W5-A1** (when granted): sync spec + fixtures using ADR-0003 enum; no L2.
3. W6/W7 path packaging only after W4 paths + W5 confidence exist.

**STOP.** No `SynchronizedState` implementation in this note.
