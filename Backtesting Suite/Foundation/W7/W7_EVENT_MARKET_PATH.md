# W7 — Canonical Event / Market Path Engine

**Status:** IMPLEMENTED (research / backtesting infrastructure)  
**Grant:** 2026-08-26  
**Crate:** `momento-research-path`  
**CLI:** `momento-research-w7 --reconstruct`  
**Not:** W8 FIRST01 replay, outcome/trade labeling, Greeks, ML, execution/fill
simulation, Kalshi network, invented L2, inferred bid/ask/mid/open/close.

PLAN-W15 “80% transition + outcome classification” is **not** this waterfall.

---

## Purpose

W7 converts independently reconstructed **W5** market observations and **W6**
canonical MLB game states into a deterministic, point-in-time historical
**EVENT ↔ MARKET PATH**.

It answers:

> For every observable historical Kalshi market observation, what was the
> canonical MLB game state at that exact market timestamp, and what was the
> observable market path leading into and following that point?

```
W3:  PBP → canonical game events
W5:  market timestamp → applicable event (AS-OF)
W6:  canonical game state sequence
W7:  GameId + MarketId/side + chronological TRADE observations
       + W6 state references + causal path descriptors
```

W6 remains authoritative for game truth.  
W5 remains authoritative for event↔market temporal synchronization.  
W7 does **not** re-run AS-OF and does **not** reconstruct PBP.

---

## Join contract

For each W5 observation with a success-class status
(`SYNCHRONIZED`, `AT_EVENT`, `SYNCHRONIZED_WITH_TIMESTAMP_GAP`):

1. Take W5’s already-chosen `prior_event_id`.
2. Look up the W6 `GameState` whose `event_id` equals that prior event
   (post-event state after that play).
3. Require `canonical_timestamp <= market_timestamp`. Future states fail closed
   (`FUTURE_STATE`).
4. Attach previous state + transition from W6 `state_transitions`.
5. Store `next_state_*` as **diagnostic metadata only**. It never assigns the
   current state and never enters causal descriptors.

Non-success W5 classes are retained:

| W5 class | Applicable W6 state |
|----------|---------------------|
| `BEFORE_FIRST_EVENT` | none (coverage/audit only) |
| `AFTER_LAST_EVENT` | none (W5 may set diagnostic `prior_event_id`; W7 does not attach it) |
| `SYNCHRONIZED_WITH_TIMESTAMP_GAP` | yes; quality is **not** upgraded to EXACT |

Exact event timestamps use the W5-defined **post-event** state (`AT_EVENT`).

---

## Observation semantics

The historical cohort is **TRADES_ONLY**.

Each path observation is a `TRADE` with:

- trade price (integer cents)
- trade size: `UNAVAILABLE` in this cohort (W5 sqlite did not persist quantity)

W7 does **not** represent trades as bid, ask, spread, depth, queue, maker
liquidity, executable price, or fill probability. It does not invent L2, quotes,
mid, opening, or closing prices. Future L2 would be a distinct observation kind.

Two contract sides are independent paths on the same GameId / W6 timeline.
Missing prints on one side are not synthesized. `YES + NO = 100` is not assumed.

---

## Causal path descriptors

At observation T, descriptors use only same-side observations with timestamp
`<= T`:

- previous trade price / price change
- cumulative trade count
- time since previous trade
- time since state transition
- observed high/low so far and distances
- prior price-change count
- chronological index

W7 does **not** compute future extrema, future returns, drawdown-after-entry,
outcome labels, or strategy performance.

---

## State segments

Consecutive synchronized observations that share a W6 `state_id` form a
deterministic epoch:

```
state_seq 100 → TRADE path while the game is in S100
   ↓ MLB event
state_seq 101 → TRADE path while the game is in S101
```

Distinct W6 states are never merged because visible fields look identical.

---

## Query API

Read-only (`PRAGMA query_only` on existing sqlite):

- `path_for_game` / `path_for_market` / `path_for_contract`
- `observations_at_state` / `observations_in_state_seq_range`
- `observations_at_or_before`
- `state_at_market_observation`
- `market_observations_before` / `market_observations_after`
- `observations_where_price_equals(80)` — **print observability only**, not FIRST01

---

## Artifacts

`Backtesting Suite/Foundation/W7/`

| File | Role |
|------|------|
| `path.sqlite` | queryable paths (gitignored) |
| `schema.sql` | W7.SCHEMA.1.0.0 |
| `path_report.json` / `coverage_report.json` | cohort metrics |
| `coverage/game_coverage.json` | per GameId |
| `coverage/market_side_coverage.json` | per MarketId × side |
| `examples/representative_event_market_paths.json` | audit examples |
| `validation/w7_validation_report.json` | anti-lookahead checks |
| `manifests/w7_manifest.json` | W5/W6/W7 versions; `generated_at` is manifest-only |

---

## Failure policy

Fail closed. Never interpolate state, shift timestamps, or use nearest-event
matching. Missing W6 timeline → `NO_GAME_STATE`. Corrupted rows → classified,
not deleted.

---

## Measured cohort (run `w7-20260827T070349Z`)

W5 ∩ W6 overlap: **1,684** games; **3,367** contract sides; **2,089,269** TRADE
observations (byte-count reconciliation with W5).

| Class | Count |
|-------|------:|
| SYNCHRONIZED | 65,987 |
| AT_EVENT | 14 |
| SYNCHRONIZED_WITH_TIMESTAMP_GAP | 1,596,031 |
| BEFORE_FIRST_EVENT | 369,484 |
| AFTER_LAST_EVENT | 57,753 |
| applicable W6 state (sum of first three) | 1,662,032 |
| complete W6-state coverage games | 0 (all 1,684 PARTIAL) |
| observational 80¢ prints | 16,020 |

Failures: 0. Anti-lookahead validation: PASS.

---

## W8

FIRST01 observational replay is a **later** waterfall (`momento-research-replay`).
This W7 document does not implement it.
