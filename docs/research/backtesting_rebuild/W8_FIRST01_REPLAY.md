# W8 — FIRST01 Strategy Replay

**Status:** IMPLEMENTED (research / backtesting infrastructure)  
**Grant:** 2026-08-27  
**Crate:** `momento-research-replay`  
**CLI:** `momento-research-w8 --replay`  
**Not:** outcome/trade labeling, feature engineering, Greeks, ML, execution/fill
simulation, orderbook reconstruction, Kalshi network, AWS, production trading
changes, W9.

PLAN-W9 Greeks and PLAN-W15 outcome classification are **not** this waterfall.
Older `docs/research/backtesting_rebuild/W8/` drafts described Greeks; this
grant remaps CTO-W8 to observational FIRST01 replay over accepted W7 paths.

---

## Purpose

Replay the existing FIRST01 strategy deterministically over the accepted W7
EventMarketPath dataset.

It answers:

> WHEN would FIRST01 have triggered on historically observable TRADE prints?

It does **not** answer whether a trade made money, whether an order would have
filled, future return, which game states predict success, or which parameters
maximize performance. Those belong to W9+.

```
W7:  EventMarketPath (TRADE observations + W6 state refs + sync class)
W8:  FIRST01 observational state machine → replay ledger + opportunities
```

W7 remains the sole historical input. W8 does not reconstruct PBP, GameState,
AS-OF synchronization, market timestamps, or market identity.

---

## FIRST01 semantics used

Authoritative live machine (UNTOUCHED; read-only):
`strategies/mlb/src/{quote,strategy,state}.rs`.

Frozen constants: `crates/research-strategies` (`FIRST01` v1):

| Constant | Cents |
|----------|-------|
| first threshold | 80 |
| confirmation | 81 |
| maximum maker entry | 83 |
| GAME_LOCK | 89 |

Live sequencing mirrored by `replay_path`:

1. **89 is checked before first-80.** A first print ≥ 89 GAME_LOCKS with no FIRST80.
2. `first_80` is sticky and binds **one GameId + MarketId + side**.
3. Opponent market/side cannot confirm or enter.
4. Qualifying threshold is **≥ 80**, not “exactly 80”.
5. Same-observation 81 confirm is allowed (live clock). Research
   `EntryEngine` historically returns after recording first_80; W8 does **not**
   use that clock.
6. Entry band **80–83 inclusive**. **>83 pause**, not GAME_LOCK. Pause may resume.
7. First ≥ 89 permanently GAME_LOCKS entry. It does **not** liquidate.
8. One canonical opportunity per GameId (sticky first_80 / `can_attempt_entry`).
9. No take-profit. No discretionary exit.

Replay phases (mapped from live `MlbGamePhase`; fill-only phases omitted):

| ReplayPhase | Live analogue |
|-------------|----------------|
| `WATCHING` | `Watching` |
| `FIRST_80` | `First80Triggered` |
| `WAITING_FOR_81` | `WaitingFor81Confirmation` |
| `ENTRY_ELIGIBLE` | `EntryEligible` |
| `PRICE_PAUSED` | `paused_above_max` (flag, not a live phase) |
| `GAME_LOCKED` | `GameLocked` |

`PositionBuilding` / `PositionOpen` are **not** entered. They require fills.
W8 never simulates fills.

---

## Documented observability discrepancy (not a new strategy)

| Live FIRST01 | W7 data | W8 choice |
|--------------|---------|-----------|
| Qualifying price = YES **bid** | TRADE prints only | Qualifying price = W7 TRADE print; observability `TRADE_PRINT_NOT_YES_BID` |
| Maker requires `bid < ask` | No ask | Constraint **UNAVAILABLE**; not invented |
| `Build` requires PositionId | No execution | `ENTRY_INTENT_PROPOSED` is a **replay artifact** only |
| Remainder Builds after partial fill | No fills | **One** proposed intent per opportunity |

W8 does **not** call live `MlbStrategy::observe()` (needs bid/ask `MarketEvent`).
W8 does **not** feed a fake ask into research `EntryEngine`.
W8 implements a dedicated replay machine that mirrors live **sequencing** using
research-strategies constants.

This is not a silent redefinition of FIRST01. It is the only honest mapping
onto TRADES_ONLY history.

---

## Observation vs opportunity vs order

A historical TRADE print at 80¢ is an **observation**, not an executable order.

W8 records:

- `FIRST80_OBSERVED`
- `CONFIRM81_OBSERVED`
- `ENTRY_ELIGIBLE`
- `ENTRY_INTENT_PROPOSED`

W8 never records or implies:

- `ORDER_SUBMITTED`
- `ORDER_FILLED`
- `POSITION_OPEN`

Intents are **not** sent to Risk or Execution.

80¢ **prints** (price == 80) are counted separately from **FIRST80 events**
(first observation with price **≥ 80** on an unbound game that is not already
GAME_LOCKED). Many prints can exist for one FIRST80. One GameId produces at
most one opportunity.

---

## Ordering contract

Observations are processed in:

```text
market_timestamp_utc, observation_id
```

Never retrieval order, never database insertion order, never wall-clock.

If FIRST80, confirmation, and GAME_LOCK share a timestamp, source observation
order (`observation_id` after timestamp) decides. Backward timestamps combined
with a lock print are classified `AMBIGUOUS_REPLAY_ORDER` and still apply the
lock (live still locks).

---

## Causal / anti-lookahead

For every observation at market timestamp T the machine may consume only
information available at or before T:

- No future TRADE print.
- No future W6 state (`next_state_*` is never read).
- No settlement / outcome / P&L.

Required gate: replay of a path truncated at T matches the full-path events
with timestamp ≤ T. Appending later observations cannot alter events ≤ T.

Exact event timestamps use the W5/W7 **post-event** state already stored on
the path (`AT_EVENT`). W8 does not re-join.

`SYNCHRONIZED_WITH_TIMESTAMP_GAP` is never upgraded to `EXACT` / `SYNCHRONIZED`.

A TRADE without an applicable W6 state remains a market observation. It may
still move the FIRST01 machine. It is not presented as a fully state-linked
strategy event (`state_id` is left unset; class is carried from W7).

---

## GAME_LOCK

First qualifying ≥ 89 print permanently locks **entry** on that GameId
(relevant to the bound market/side, or unbound if no first_80 yet).

GAME_LOCK does **not** mean liquidation, position closure, settlement, loss,
or profit.

| Ordering | Result |
|----------|--------|
| Lock before first 80 | `GAME_LOCKED` ledger only; no FIRST80; no opportunity |
| Lock between 80 and 81 | FIRST80 recorded; no confirmation; no entry |
| Lock after eligibility | Eligibility and lock both recorded; terminal `GAME_LOCKED` |

---

## Storage

`Backtesting Suite/Foundation/W8/` (not Data-Real):

| Artifact | Role |
|----------|------|
| `replay.sqlite` | Event ledger + opportunities (gitignored) |
| `replay_report.json` | Cohort counts |
| `coverage_report.json` / `coverage/w8_counts.json` | Same counts |
| `validation/w8_validation_report.json` | Anti-lookahead / no-fill / no-P&L / no-W9 |
| `manifests/w8_manifest.json` | Versions; `generated_at` is manifest-only |
| `examples/representative_first01_replay.json` | First seen event of each type |
| `schema.sql` | `W8.SCHEMA.1.0.0` |

Lake writes are refused (`LakeWriteGuard`).

---

## Real-data cohort

Accepted W7 input only (not the 8,428-market catalog; not W6-only games).
Run `w8-20260827T074300Z` against W7 `w7-20260827T070349Z` /
`W7.EVENT_MARKET_PATH.1`.

| Measure | Count |
|---------|------:|
| games processed | 1,684 |
| markets/sides processed | 3,367 |
| observations processed | 2,089,269 |
| W7 observation count | 2,089,269 |
| 80¢ prints | 16,020 |
| FIRST80 events | 1,558 |
| 81 confirmations | 1,483 |
| entry-eligible events | 1,306 |
| proposed replay intents | 1,306 |
| GAME_LOCK events | 1,528 |
| >83¢ price pauses | 19,384 |
| opportunities | 1,558 |
| ambiguous timestamp cases | 0 |
| skipped | 0 |
| replay failures | 0 |
| state-linked triggers | 5,792 |
| triggers without W6 state | 83 |
| SYNCHRONIZED | 266 |
| AT_EVENT | 0 |
| SYNCHRONIZED_WITH_TIMESTAMP_GAP | 5,526 |

16,020 80¢ prints ≠ 16,020 trades. FIRST80 is the first qualifying ≥80
observation per GameId (and is zero when 89 prints first).

Gate: `COMPLETE`. W7 observations reconciled. W9 not started.

---

## W9

**Not started.** No outcome labels, future returns, drawdowns, Greeks, 80%
transition classification, or statistical discovery.
