# FIRST01 Live Entry Gate Audit

**Scope:** Source inspection only. No production modifications.
**Sources:** `strategies/mlb/src/{quote,strategy,state}.rs`, `crates/core/src/position.rs`
(`can_attempt_entry`), `crates/risk/src/engine.rs` (`decide_entry`),
`crates/execution/src/engine.rs`, `apps/trading-engine/src/live.rs` (host wiring).

**Invariant:** Risk and host gates are **not** FIRST01 strategy rules. They belong in
`LIVE_EXECUTION_CONTEXT` for frequency reconciliation.

---

## Call path: 80→81 → live Build

```
MarketEvent (L2 quote)
  → live.rs builds MlbContext { kill_switch, recon, has_working_entry,
      unknown_entry_order, position, assigned_position_id, data_stale, … }
  → MlbStrategy::on_market_event
      → validate_quote (stale / missing / inverted)
      → fingerprint dedupe
      → ≥89 → GameLocked (no Build; may CancelRemainingEntries)
      → first_80 sticky on (GameId, MarketId, Side)
      → same-key ≥81 → confirmed_81
      → maybe_pause_or_enter:
           stop? pause above 83? kill/recon/unknown?
           has_working_entry? terminal position lifecycle?
           maker_limit in 80–83 with bid < ask?
           phase EntryEligible | PositionBuilding?
           assigned/existing position_id?
           → MlbDirective::Build(TradeIntent)
  → live host submit_approved
      → RiskEngine::decide_entry (can_attempt_entry, budget, desk slots, …)
      → ExecutionEngine::submit_entry (can_attempt_entry again)
```

---

## Gate table

| Gate | Live condition | Research condition | Applied? | Discrepancy | Classification |
|------|----------------|---------------------|----------|-------------|----------------|
| Quote stale | `data_stale` → `QuoteReject::Stale`; no entry | Sequence-gap / invalid quote reject | Yes (data) | Candlestick has no L2 staleness | DATA RULE |
| Missing bid/ask/side | `validate_quote` fails | Same | Yes | None material | STRATEGY RULE |
| Bid > ask | Reject inverted | Same | Yes | None | STRATEGY RULE |
| Fingerprint debounce | Same bid/ask/side skip re-eval | Same last ms+bid+ask skip | Yes | None | STRATEGY RULE |
| First ≥80 | `reaches_first_80` sticky | Same; research returns after first (confirm needs later quote) | Partial | Live can confirm on same quote if already ≥81 | STRATEGY RULE (minor timing) |
| Confirm ≥81 same market+side | Required | Required | Yes | None | STRATEGY RULE |
| Opponent market | Ignored for confirm/entry | Suppressed | Yes | None | STRATEGY RULE |
| Price >83 pause | `PauseEntry`; no Build | Pause; no opportunity until band | Yes | None | STRATEGY RULE |
| Maker band 80–83 + bid < ask | `maker_limit` | Same | Yes | None | STRATEGY RULE |
| GAME_LOCK ≥89 | Permanent no entry; cancel working | Same | Yes | None | STRATEGY RULE |
| Kill switch | Blocks Build in strategy | Not simulated in validation | Research N/A | Host-only | HOST/OPERATIONAL RULE |
| Recon blocks new exposure | Blocks Build | Not simulated | Research N/A | Host-only | HOST/OPERATIONAL RULE |
| Unknown entry order | Blocks Build | Not simulated | Research N/A | Host-only | HOST/OPERATIONAL RULE |
| Working entry order | `has_working_entry` blocks Build | Context + sticky opportunity | Yes | None | STRATEGY / EXECUTION RULE |
| Position lifecycle terminal | Settled/Stop/Liq/SettlementPending block Build | `position_entry_closed` / filled→consumed | Yes | Naming differs; same intent | STRATEGY RULE |
| Phase PositionOpen | No Build | Canonical consumed after fill | Yes (research fills=0 so rare) | None | STRATEGY RULE |
| Assigned position id | Build requires position_id | Research creates opportunity without host position | Partial | Host assigns before Build | EXECUTION RULE |
| `can_attempt_entry` | Risk + execution refuse if false | Mirrored via lifecycle consumed / lock / pause | Yes (semantic) | See section below | RISK / POSITION RULE |
| Entry price vs risk min/max | Risk rejects outside config band | FIRST01 band only | Risk not in FIRST01 count | — | RISK RULE |
| Per-game economic budget | 12.5% / $6.25 snapshot | Not applied to opportunity count | Risk not in FIRST01 | — | RISK RULE |
| Desk `max_open_positions=5` | `open_slot_count() >= 5` → PositionLimitExceeded | **Not** applied to FIRST01 opportunities | **Missing from raw FIRST01** | Explains ~8.46→~3–5 | RISK RULE |
| Capacity / bankroll | InsufficientAvailableCapacity | Not applied | Research N/A | — | RISK RULE |
| ReconciliationRequired (risk) | Unknown reservations / global recon | Not applied | Research N/A | — | RISK RULE |
| Session / trading hours | **None found in MLB strategy** | None | N/A | No session window gate | — |
| Entry cooldown / min time | **None found** | None | N/A | — | — |
| Pregame-only | **None found** | None | N/A | — | — |

---

## `can_attempt_entry` (authoritative)

**Definition:** `crates/core/src/position.rs`

Returns `false` when any of:

- `game_lock.is_locked()`
- `entry_abandoned`
- `entry_price_gate == PausedAboveMaxPrice`
- lifecycle ∈ { StopTriggered, LiquidationActive, SettlementPending, Settled, Flat, OpenComplete, Holding }

Otherwise `true` (including Building / OpenPartial while remainder may still be actionable).

**Callers:**

| Caller | Behavior when false |
|--------|---------------------|
| `risk::decide_entry` | Reject (`GameLocked` reason path) |
| `execution::submit_entry` | `EntryNotPermitted`; cancel risk reservation |
| `Position::record_submission` | `EntryNotPermitted` |
| `positions::tracker` | Surfaces `can_enter` for host |

**Scope:** **Position-level** (bound to a `PositionId` / game assignment), not desk-wide.
**Permanence:** Terminal lifecycles and game lock do not reset for re-entry on that position.
PauseAboveMax can clear via `resume_entry_if_unlocked` when price returns to band and unlocked.
**Reset:** New position assignment for a new game can attempt entry; same game after Flat/OpenComplete does not re-enter under live MLB sticky `first_80` + host wiring.

Desk-wide concurrency is **not** `can_attempt_entry`; it is risk `max_open_positions` when `would_open_new_slot`.

---

## Classification for frequency work

| Metric | Includes |
|--------|----------|
| RAW / Canonical FIRST01 opportunities | Strategy price + sticky game lifecycle only |
| Live gate pass (strategy/host) | Kill/recon/unknown/working/position phase — research already applies working/lifecycle; kill/recon assumed PASS offline |
| LIVE_EXECUTION_CONTEXT after risk | Apply desk `max_open_positions=5` (+ capacity if modeled) |
| Execution block | Maker fill model / L2 — **not** opportunity count |

**Do not fold risk caps into FIRST01.**
