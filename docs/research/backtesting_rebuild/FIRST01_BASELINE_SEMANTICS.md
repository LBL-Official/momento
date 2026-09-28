# FIRST01 Baseline Semantics (READ-ONLY)

**Status:** FROZEN production baseline for the research rebuild.  
**Do not change** live code, research FIRST01 parameters, or this behavior as part of engine work.  
**Authoritative sources (in order):** `strategies/mlb/src/{quote,strategy,state,stop}.rs`, `crates/core/src/{position,basis}.rs`, then `docs/research/FIRST01_live_entry_lifecycle_reset.md` and `FIRST01_live_vs_research_audit.md`.

A known contradiction: `FIRST01_live_entry_state_machine.md` still says TRADE_COMPLETE “may allow new opportunity if not GameLocked.” That is **obsolete**. Live `can_attempt_entry` returns false for `Flat` and `OpenComplete`. Use this document.

---

## 1. What FIRST01 is

FIRST01 is the versioned name of the **current live MLB (and WNBA) desk strategy**, not the historical engine.

- Qualifying observation: **YES bid only**. Not mid, not last, not ask.
- Ask is used only to refuse crossing (`bid < ask` for maker).
- Kalshi has no official mid; production does not invent one.

Constants (`strategies/mlb/src/quote.rs`):

| Name | Cents |
|------|-------|
| `FIRST_80_CENTS` | 80 |
| `CONFIRM_81_CENTS` | 81 |
| `MAX_ENTRY_CENTS` | 83 |
| `LOCK_89_CENTS` | 89 |

Research copy: `crates/research-strategies/src/first01.rs` (`FIRST01` version 1). Same numbers.

---

## 2. first_80

1. On a valid quote, if YES bid ≥ 80, record `first_80` for `(GameId, MarketId, Side)`.
2. **Sticky forever** for that game. Never cleared.
3. Opponent market/side cannot confirm or enter after bind.
4. This is first **qualifying bid ≥ 80**, not “average time above 80,” not last trade.

Research later needs a **generic first-touch engine** (20, 30, … 95). FIRST01’s first_80 is one consumer of that engine, still defined as first timestamp where **YES bid** reaches/crosses 80.

Minor live vs research timing: live can confirm 81 on the **same** quote if the first observation is already ≥ 81. Research historically returned after recording first_80 and confirmed on a later quote (`FIRST01_live_entry_gate_audit.md`). Do not “fix” live to match research. Document the difference; plugin tests should state which clock they use.

---

## 3. 81 confirmation

Same bound `(GameId, MarketId, Side)` must subsequently (or same-quote in live) show YES bid ≥ 81 → `confirmed_81`.

Opponent markets never confirm the bound sequence.

---

## 4. Maker entry (80–83)

After confirmation:

- Maker limit = qualifying YES bid.
- Limit must be in **80–83 inclusive**.
- Require `bid < ask`.
- Bid > 83 → pause entry (`PausedAboveMaxPrice` / research pause). Not GAME_LOCK.
- Emit `Build` / `EntryIntent` only when other gates clear.

No taker entry in FIRST01. No inventing fills from candle closes.

---

## 5. GAME_LOCK (≥ 89)

YES bid ≥ 89 on the **bound** market+side → `GameLocked`:

- Permanent for the game.
- Cancel eligible working **entry** orders.
- **Does not flatten** an open position.
- Independent of the 50% stop.

---

## 6. 50% stop

- Basis = **actual entry-fill VWAP**, not submitted limit.
- Stop = 50% of VWAP via integer hundredths (`half_entry_stop_from_fills` in `crates/core/src/basis.rs`).
- Trigger: YES bid on the **position’s** MarketId+Side with `bid_cents * 100 <= stop_hundredths`.
- Sharp gaps trigger at first observed crossing.
- Once triggered → `StopTriggered` / `LiquidationActive`. Recovery above stop does **not** reopen entry.
- Liquidation is reduce-only IOC in live; research models this only when book quality supports it.
- No take-profit. No discretionary exit.

---

## 7. One trade per GameId

Canonical: **one FIRST01 opportunity / entry lifecycle per GameId**.

What prevents a second independent trade:

| Mechanism | Effect |
|-----------|--------|
| Sticky `first_80` | Opponent never becomes the trade |
| `has_working_entry` | No duplicate Build while resting entry exists |
| Phase `PositionOpen` | No further entry when filled and remaining budget ≤ 0 |
| `can_attempt_entry == false` | `Flat`, `OpenComplete`, `Holding`, `StopTriggered`, `LiquidationActive`, `SettlementPending`, `Settled`, game lock, abandoned, paused-above-max |

Research flag: `canonical_lifecycle_consumed` — sticky once the first opportunity is created.

---

## 8. Re-Build after unfilled cancel

If an entry is submitted and later **canceled unfilled**:

- Live may emit **another Build** for the **same** opportunity / same `PositionId` when `has_working_entry=false` and phase returns to `EntryEligible`.
- This is **not** a new FIRST01 trade and **not** a new sequence number in the canonical sense.

Do not count remainder Builds as additional opportunities in research frequency.

---

## 9. Settlement

Live host applies venue settlement proceeds (`apply_settlement_if_any` in `live.rs`). Strategy does not invent settlement prices or P&L.

Research must label eventual contract outcome from **observed** Kalshi settlement/result when present; otherwise `UNAVAILABLE`.

Desk note (2026-08-25): some ledger settlement proceeds looked wrong vs Kalshi. Reconstruction must not copy that bug into historical labels.

---

## 10. What is NOT FIRST01

These affect live **frequency and P&L** but are **not** FIRST01 rules:

| Gate | Owner |
|------|--------|
| `max_open_positions = 5` | Risk (desk-wide MLB+WNBA) |
| 12.5% / $6.25 economic budget | Risk + weekly snapshot config |
| Kill switch, recon, unknown order | Host / execution |
| Bankroll / capacity | Risk |
| Trading hours / pregame-only | **Not present** in MLB strategy |

Frequency recon: 8.46 opportunities/day is FIRST01-on-candles; 4.69/day after desk cap is `LIVE_EXECUTION_CONTEXT`.

---

## 11. Canonical lifecycle consumed (research)

Once the first canonical opportunity exists for a GameId:

- Further qualifying quotes on the opponent are suppressed.
- Unfilled cancel → more intents on **same** opportunity.
- After fill / flat / open-complete → no second independent opportunity.

This matches live `can_attempt_entry` after the position leaves Building/OpenPartial.

---

## 12. How the new engine must treat FIRST01

- Data/state/path layers **must not** hard-code 80/81/83/89/50%.
- FIRST01 is the first **strategy plugin** consuming reconstructed `StateTransition`s.
- Baseline plugin parameters stay these numbers until a later, separately authorized experiment.
- Changing these numbers is a **strategy** change, not an engine change.

---

## 13. Live phases (reference)

`MlbGamePhase`: Watching → First80Triggered → WaitingFor81Confirmation → EntryEligible → PositionBuilding → PositionOpen, or GameLocked / NotEligible.

Quote validation rejects: stale, missing side/bid/ask, inverted book, receipt before exchange.
