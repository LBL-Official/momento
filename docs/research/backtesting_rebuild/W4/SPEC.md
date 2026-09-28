# CTO-W4 SPEC — Kalshi market reconstruction

**Name:** Kalshi `MarketPath` / `MarketState` reconstruction  
**Status:** IMPLEMENTING  
**Authorization:** 2026-08-26 grant  
**Crate:** `momento-research-market`  
**Not:** `SynchronizedState`, event↔market clock join, theta, FIRST01, L2 invention

W3 reconstructs the **game**. W4 reconstructs the **market**. They are independent
(ADR-0003). A game with no Kalshi path stays `market_state = UNAVAILABLE` (W5
label). A Kalshi market with no PBP stays `event_state = UNAVAILABLE`. **Never
drop raw because the join failed.**

---

## Objective

For each committed Kalshi ticker (MLB `KXMLBGAME` only), reconstruct a
time-ordered `MarketPath` from **observed** artifacts:

1. Ingest `kalshi_discovery` envelopes (payload trades / candles / metadata)
2. Data-Real v1 COMPLETE partitions (read-only) for the requested window
3. W2/W3 / DATA-INGEST identity files (read-only; counts + attach only)

Classify completeness **honestly**. Report gaps. Do not fetch Kalshi on the
network. Do not suffix-match tickers or invent `gamePk`.

---

## Interfaces

| Interface | Role |
|-----------|------|
| `CommittedMarketSet` | Checksum-verified discovery envelopes in the requested date window |
| `IdentityIndex` | ticker → `MAPPED` / `UNMATCHED` / `AMBIGUOUS` + optional `game_pk` from upstream pairs |
| `LakeDayRaw` | Optional COMPLETE `events.jsonl.gz` (candles + trades + PIT books) |
| `reconstruct_market_path` | Envelope (+ optional lake rows) → `MarketPath` |
| `couple_event` | `event_ticker` → `CoupledMarketEpisode` |
| `run_w4_reconstruction` | Bounded window job → Foundation/W4 artifacts |

CLI (`momento-research-w4`) is a thin wrapper. Default window is **one day**.
Full 8k-ticker reconstruct is **not** this step.

---

## Completeness (exclusive; never silently upgrade)

```text
L2_COMPLETE
L2_PARTIAL
TRADES_ONLY
CANDLES_ONLY
MARKET_METADATA_ONLY
UNOBSERVED          // committed identity but no market observations
```

Classifier is the **minimum honest book class**, not the richest observation:

| Condition | Class |
|-----------|--------|
| Written L2_COMPLETE definition holds (game-time snapshot **and** ungapped delta stream) | `L2_COMPLETE` |
| Else any **game-time** L2 snapshot or delta | `L2_PARTIAL` |
| Else any TRADE point on the t_game path | `TRADES_ONLY` |
| Else any CANDLE_1M point | `CANDLES_ONLY` |
| Else ticker/event metadata present | `MARKET_METADATA_ONLY` |
| Else identity committed with no payload | `UNOBSERVED` |

**Combined class:** not invented. If trades **and** candles exist, completeness
is `TRADES_ONLY`. Candle points remain on the path as `CANDLE_1M`. Trades are
prints, not a book. Candles are not TOP_OF_BOOK or L2.

`TRADES_ONLY` is a **valid** research dataset. Missing L2 does not quarantine
or discard it. Downstream L2-dependent work is gated, not implied.

User-facing `UNAVAILABLE` on an observation axis (L2, settlement, candles)
means that axis has no usable evidence. It is not a reason to drop a market
that still has trades or metadata. `UNOBSERVED` is the completeness class when
identity is committed with no market payload.

### L2_COMPLETE (written definition; expected UNAVAILABLE today)

All of:

1. At least one `L2_SNAPSHOT` with a **game-time venue timestamp**
2. An `L2_DELTA` stream for that ticker without sequence gaps over the claimed window
3. Neither candles nor ingest-time REST PIT snapshots counted as (1) or (2)

A single WS/PIT snapshot **must not** upgrade a path or day to `L2_COMPLETE`
or W1 `FULL_L2`. Current corpus: historical L2 = UNAVAILABLE.

---

## Observation kinds

```text
METADATA
TRADE
CANDLE_1M            // preserve raw OHLC bid/ask; never drop the way LEGACY OrderbookEvent did
TOP_OF_BOOK          // only if historically observed at t_game
L2_DELTA / L2_SNAPSHOT  // only if historically observed at t_game
REST_PIT_SNAPSHOT    // ingest-time book; MUST be tagged NOT_GAME_TIME
```

- Candle close bid/ask remains `CANDLE_1M` / CANDLESTICK observability, never
  `TOP_OF_BOOK` or L2.
- `event_type = candlestick` + `l2_snapshot` on one point is **invalid**.
- REST PIT orderbook from collector ingest date ≠ game-time L2. Those points
  are **excluded from the t_game path** and counted as `ingest_only`.
- `received_at` is never `exchange_timestamp`.
- `yes_bid_cents` / `yes_ask_cents` use `None` for UNAVAILABLE, never `0` as a
  sentinel. An observed `"0.0000"` dollar string is `0` cents (real zero).

---

## Money

Integer **cents** (`i32`). No `f64` for prices, quantities, or P&L.

Dollar strings (`"0.0100"`) parse as hundredths of a dollar with fail-closed
extra digits (non-zero beyond two decimal places → skip that field).

Quantities: integer **hundredths of a contract** (`i64`), same parse rule.

Spread is **DERIVED** only when both bid and ask are OBSERVED and `ask >= bid`.
Kalshi has **no official mid**. Never store `(bid+ask)/2` as OBSERVED.

---

## Identity

Consumed, not recomputed:

- `MAPPED` / `UNMATCHED` / `AMBIGUOUS` from ingest `game_market_pairs.json`
  (fallback: envelope `identity_mapping` if no pairs file)
- `game_pk` only if upstream mapped it. W4 never infers it from ticker text.
- UNMATCHED and AMBIGUOUS markets **still** get a `MarketPath`.
- MAPPED is identity, not a quality upgrade.

---

## Lifetime and starting price

- Prefer `open_time → settlement` when both timestamps are **in metadata**.
- If only settlement-day (America/Los_Angeles date of `settlement_ts`) points
  exist: `lifetime_coverage = SETTLEMENT_DAY_ONLY`.
- Else if open and settlement exist and t_game points exist on both calendar
  days (PT): `OPEN_TO_SETTLEMENT`.
- Else: `UNKNOWN`.
- Do **not** interpolate quotes across gaps.
- Starting price: reuse W1 `StartingPriceClass`. First candle/trade is **not**
  `MARKET_OPEN_PRICE`. Default `STARTING_PRICE_UNVERIFIED`.

---

## Coupled episodes

`CoupledMarketEpisode` groups YES contracts that share `event_ticker`.

- `team_a_yes` / `team_b_yes`: lexicographic ticker order (observed labels, not
  inferred MLB abbreviations).
- One contract present: other side is **explicitly missing** (`missing_side`),
  not guessed.
- More than two tickers: first two coupled; extras recorded as anomalies.

---

## Unsorted / duplicate trades

| Input | Behavior |
|-------|----------|
| Missing `created_time` | Skip trade; anomaly; do not use `retrieved_at` |
| Unparseable price | Skip trade; anomaly |
| Unsorted timestamps | Sort by `(exchange_timestamp, trade_id)`; anomaly `UNSORTED_TRADES` |
| Duplicate `trade_id` | Keep first; anomaly `DUPLICATE_TRADE_ID` |
| Empty ticker | Refuse that envelope |

This is **fail-closed on clocks and money**, not fail-closed on sort order.

---

## Inputs (fail closed)

1. Ingest handoff (`w1_handoff.json`) listing `kalshi_discovery` artifacts
2. Those envelopes on disk; SHA-256 must match
3. Optional `game_market_pairs.json` (identity attach only)
4. Optional Data-Real COMPLETE manifest + `events.jsonl.gz` (checksum vs manifest)

Refuse: uncommitted artifacts, checksum mismatch, Kalshi network, Data-Real
writes, mixing WNBA/`KXWNBAGAME` into MLB reconstruction.

If a ticker has no trades/candles: classify `MARKET_METADATA_ONLY` or
`UNOBSERVED` and emit **BLOCKED_ON_INGEST_OBSERVATIONS** on the blocker list.
Do not fabricate points. Do not implement ingest upgrade inside W4.

---

## Outputs

`Backtesting Suite/Foundation/W4/` only:

- reconstruction summary
- completeness / lifetime / identity histograms (counts)
- coupled episodes
- per-ticker paths
- anomalies
- blocker list
- W5 handoff note

`completeness_claimed=false` unless every reconstruction invariant for that
window passed. Never claim `FULL_L2`. Never claim 2024 Kalshi if discovery
observed none.

---

## Failure modes

| Failure | Response |
|---------|----------|
| Checksum mismatch | Refuse run |
| Write under Data-Real | Refuse run |
| Missing trades for mapped tickers | Path + blocker; not a crash |
| PIT book present | Exclude from t_game; anomaly if someone labeled it L2 |
| Crossed book (ask < bid) | Keep points; anomaly `CROSSED_BOOK` |
| Ambiguous identity | Preserve; still reconstruct |

---

## Tests

See [TEST_PLAN.md](TEST_PLAN.md). Mirror W3 discipline. Never delete a failing
test to make W4 look done.

---

## Bounded execution

```text
Prove 2026-06-18 first.
Then 2026-06-18..30.
Then declare how the 4,754 mapped pairs will be batched.
Do not run the full 8k-ticker reconstruct in this step.
```
