# Dual-leg maker lock — position-management problem brief

```text
RESEARCH STUDY / DESIGN CONTRACT
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE HEDGE
DOES NOT START W9
CANDLE PATH                     ≠ FILL
PRICE EVENT                     ≠ EXECUTABLE ORDER
L2 / QUEUE / DEPTH              = UNOBSERVED HISTORICALLY
STRATEGY PROPOSES → RISK APPROVES → EXECUTION EXECUTES
ONE COMPLEMENTARY PAIR ≠ TWO INDEPENDENT BETS
```

**Audience:** Momento quant / execution engineer.  
**Author intent:** state the live-exit problem, the two-clock lock we want the bot to run, and the state machine that has to survive every outcome. This is not a strategy retune and not a license to submit.

**Teaching pair (read as types, not a scheduled game):**

```text
A  = favorite YES we already own     e.g. Bulls YES  @ 80  (filled, maker)
B  = opponent YES we do not own yet  e.g. Lakers YES
```

Same `event_id`. Opposite YES tickers. Never infer the pair from prices.

---

## 0. Why this exists

The 80→40 identity the research desk quotes is:

```text
EV = 20 · S − L · (1 − S)
L  = 40     on the ledger
```

Two things are false in production, and both are why that identity does not survive contact with Kalshi.

**1. Taker-fee drag on the stop path.**  
Production liquidation is reduce-only IOC on A. On `KXNBAGAME` / `KXNCAAMBGAME` (`fee_type=quadratic`, M=1, verified 2026-09-03 demo API) a taker exit at 40¢ is **1.68¢/contract**. Maker entry at 80 is **$0**. The stop path is therefore **−41.68¢**, not −40¢. Wins stay +20.00¢ if we never take the exit. A maker fill on B, on the same series, is **$0** under current metadata. Buying B as maker is the only stop-path construction that keeps the fee line at zero. Re-verify `GET /series/{ticker}` and `GET /series/fee_changes` before any paper or live use. MLB (`KXMLBGAME`) is M=0.5 — do not copy NBA fee numbers onto MLB tickets.

**2. The 40 print is a trigger, not a fill.**  
Detect-then-IOC on A sells into a book that has already walked through 40. That is how a “−40 stop” becomes −60, −77, or −80. The research ledger labels every asked-six loser `STOP_40` at exactly 40¢. That is a close-path signal. `market_trades` are UNAVAILABLE. Historical L2 is UNAVAILABLE. The live experiment `P(P_fill | 80→40)` is **NOT_RUN**.

If we do not build a working B book *before* A is empty, those two things remain the live exit.

---

## 1. What production actually does today

Live MLB 001 (`apps/trading-engine` + `crates/risk` + `strategies/mlb`):

```text
entry     post-only GTC YES on A, limit ∈ [80, 83], never ≥ ask
stop      YES bid(A) ≤ 50% of entry-fill VWAP
          (81.00¢ → 40.50¢, integer hundredths)
flatten   cancel residual entries, then reduce-only IOC sell A
          at the current best YES bid
89        GAME_LOCK: blocks new entries. Does not flatten.
hedge     none. Risk: DuplicateGamePosition. One market per game.
B         cannot be booked. Live FIRST01 is single-legged.
```

Strategy does not submit. Risk does not invent a second ticker. Execution does not assume the stop threshold was the fill price.

That last sentence is the whole product defect: the host is specified to lift whatever bid remains after the trigger. There is no resting exit, no second book, no max-slippage, no complement lock.

---

## 2. What the live tape already proved

Source: `docs/desk/2026-08-25-loss-review.md`. Production `momento-live` on `i-0f0849d5829476c31`. Bankroll snapshot $50. Day window 2026-08-25 PT. Not a backtest. Fees were **not even on the fills** (`$0.00` recorded).

| | |
|---|---:|
| Realized P&L | **−$31.77** (−63.5% of $50) |
| Filled trades | 9 (7 MLB, 2 WNBA) |
| Wins | **0** |
| IOC stop liquidations | 4 (−$11.52) |
| Settlement losses | 5 (−$20.25) |

Three shapes, all still legal under the current stop:

| Shape | Tape | What the host did |
|---|---|---|
| **Gap through the stop** | CHC YES: lock 89 → later IOC **7 @ 3¢** (−$5.46) | Trigger fired. Book was gone. “−40” was −78 vs 81¢ entry. |
| **Trigger into a thin book** | LAA YES: lock 89 → IOC 7 @ **41¢** | Stop “worked.” Still a full half-premium loss, taker. |
| **Whipsaw** | BOS IOC @ 63¢, ATL @ 54/52¢; both markets later ≥89 | Sold the dip, then the favorite locked without us. |
| **No stop, full premium** | CWS, SEA, PIT + 2 WNBA | GAME_LOCK held. Bid never sustained ≤ ½ VWAP. Settled 0. |

CHC is the existence proof for the founder’s fear. A 50% VWAP trigger plus IOC does **not** lock a 40¢ loss. It sells A at the residual bid. Residual bid can be 3¢.

Later host state (2026-09-15 Vital incident) is a different failure — five stale pending slots, `PositionLimitExceeded`, no Create V2 — and is **not** a P&L argument. Do not mix occupancy bugs into this study. This study is only the exit.

Research candles say the same thing in distribution form (`research/first80_asked_six_80_40_liquidation/`, NBA FIRST80 liquidation V1):

- Asked-six: 245 / 299 first T40 closes already **<40**. Median 37¢, mean 34.5¢. ≤20¢ at the T40 bar: **13**. The crash to 15–20 is mostly **+5 minutes after a missed trigger** (median min-close 26¢; 112 / 298 ≤20).
- NBA stop-minute Model B (bid close): average exit **34.1¢**, not 40. Model C (bid low): **30.6¢**.
- Zero-EV average fill, survival held, before fees: **~23.1¢ NBA / ~25.4¢ NCAAB**.
- A 40 post-only bid on B **at T0 rejects**. At FIRST80, B ≈ 20 (P(B bid ≤20) = 0.985, median delay 1 minute). Complement is already tight. You cannot rest B@40 while B’s ask is ~21.

So: we do **not** have proof that stops fill at 40. We **do** have proof that IOC on A can print 3¢. That is sufficient to open a study. It is not sufficient to arm a second live leg.

---

## 3. Economic object (do not get the clocks mixed)

```text
A1 clock  =  favorite YES falling     (Bulls 80 → 55 → 40 → 20)
A2 clock  =  opponent YES rising      (Lakers 20 → 45 → 60 → 80)
```

Complementary YES + YES on one event, equal contract counts, both held to settlement:

```text
locked cents = 100 − VWAP_A − VWAP_B
```

| A fill | B fill | Lock | vs selling A at 40 |
|---:|---:|---:|---|
| 80 | 44 | **−24** | 16¢ better |
| 80 | 60 | **−40** | same as the advertised stop |
| 80 | 70 | −50 | worse than the stop |
| 80 | — , sell A @ 20 | **−60** | abort |
| 80 | — , A settles 0 | **−80** | the thing we are preventing |

`80 + 60 = 140` and `40 + 60 = 100` is why “Bulls touches 40 ⇒ working limit 60 on Lakers” is the **max-lock identity**, not a clever extra. Buying B at 60 while we still own A is economically the same terminal as selling A at 40 — **if and only if** both quantities match and both survive to settlement. The reason to buy B instead of selling A is **execution**: B can be made as a resting bid on the way up; A’s 40 is often already gone when the trigger fires.

Delta-neutral here means **one-for-one complementary YES**, not a continuous delta. Binary YES(A) + YES(B) = $1.00 certain. Quantity on B must equal remaining filled quantity on A. Partial B is a partial lock; residual A is still naked.

**Do not buy B at T0.** B ≈ 20 when A fills at 80. `80 + 20 = 100` locks ~0 and deletes the +20 on every winner. The hedge is armed only after A has deteriorated. Winners that never print 55 on A stay single-legged and settle +20.

A1 hybrid already measured the fake version of this idea: any later B close ≥40 booked at exactly 40, including `23→75`. NBA: 456 closes ≥40, **92** in-band at 40, **364** gaps. That gap premium is **+0.85¢/trade** and is illegal to promote. Conservative in-band H=40 **loses** to 80→40 (−0.065¢). V5 wait-then-pay the later bid also loses. So this study is **not** “rest B@40 and assume fill.” It is “work B as a maker while A is dying, never pay more than the max lock, abort and flatten A when the B book is no longer a lock.”

---

## 4. Proposed working window (study parameters, not live constants)

Declared here so the engineer can code against names. Promotion to config requires a measured paper tape. Do not hard-code into `strategies/mlb`.

| Name | Meaning | Study default | Why |
|---|---|---|---|
| `ARM_A` | First time we are allowed to touch B | A yes_bid ≤ **55** | B ≈ 45 if complement holds. Earlier = more winner-locks. |
| `BID0_B` | First maker bid on B | **44** | One tick inside a ~45 B book. Lock −24 if it fills. |
| `H_MAX` | Worst B price we will ever pay | **60** | `80 + 60` locks **−40**. The advertised stop. |
| `ABORT_A` | Give up on B, flatten A | A yes_bid ≤ **20** | B ≈ 80. Further B bids are a −60+ lock. IOC A is the less-bad remaining trade. |
| `TOUCH_A_40` | Max-lock quote must be working | A yes_bid ≤ **40** | Working **B limit 60** (or better residual). |
| `Q` | B contracts | `filled_qty(A) − filled_qty(B)` | Never over-hedge. Never under-count residual. |

```text
A > 55                         do nothing on B. A is still the trade.
55 ≥ A > 40                    work B as maker, start 44, never lift through H_MAX
40 ≥ A > 20                    H_MAX limit (60) must be on the B book if residual A > 0
A ≤ 20                         cancel all B. Market / IOC sell residual A. Done.
```

“Logic all the way down to 20” is the **A clock**, not a bid ladder that walks B from 44 toward 20. Bidding B *down* while B is *rising* is how the order goes stale and never fills on the CHC path. The B book is **ascending**, capped.

Complement is measured, not assumed. If A is 55 and B bid is still 28, the 44 bid is through-market and post-only must reject. If A is 55 and B ask is 52, 44 is 8¢ behind and may never trade. Arming is a **join decision**, not a blind 44.

---

## 5. What “elite” execution means on this desk

Not a new microservice. Not a browser. Not Vital inventing fills. A position-management policy the host already has the right to run: **propose → Risk → Execution**, with an explicit state machine and integer money.

The participant we are imitating does five things a retail IOC stop does not:

1. **Makes the exit before it is urgent.** B bids are working while A is 55–41, not after A has printed 3¢.
2. **Pays the spread only at the abort.** Maker B = $0 fee (current NBA/NCAAB metadata). Taker A is the emergency exit, not the plan.
3. **Caps the lock.** Never lifts B above `H_MAX`. A −40 lock is the product. A −55 “hedge” is just a worse stop.
4. **Refuses a 40 that is not there.** `23→75` on B is a gap. Cancel/replace; do not book 40. If B jumps through `H_MAX` in one quote, that is an abort candidate, not a fill at 60.
5. **Flattens when the lock is no longer available.** A ≤ 20, B book crossed/empty, disconnect, UNKNOWN that will not reconcile — sell residual A, cancel B. Prefer a known −60 to an unknown −80.

Kalshi constraints the policy must speak natively:

- post-only GTC on B (maker). Reject or cancel if the limit would cross.
- reduce-only IOC on A at abort (existing liquidation primitive).
- `client_order_id` on every submit. Idempotent. UNKNOWN → reconcile → FOUND / NOT FOUND / AMBIGUOUS. Never blind retry.
- Tick = integer cents. No `f64` on price, qty, fee, or lock.
- Fees: compute from the live series model, not from this memo.

---

## 6. State machine (every outcome)

One `PositionId`. Two `MarketId`s. One `GameId`. Explicit states. Every transition from an event.

```text
A_OPEN
  A filled. B unused. A > ARM_A.
  → ARM                 A yes_bid ≤ ARM_A, quotes valid, B identified
  → ABORT_FLAT          A ≤ ABORT_A before we ever armed (gap)
  → A_SETTLED           A settles 100. B never touched. +20
  → A_SETTLED_0         A settles 0.  B never touched. −80   ← failure of this study

ARM
  Compute join price J on B from live B bid/ask and complement.
  If post-only J would cross → no order (QUOTE_UNJOINABLE). Stay ARM.
  If J > H_MAX             → no B. Watch for TOUCH_A_40 / ABORT.
  Else submit post-only bid B @ J, qty = residual A.
  → B_WORKING

B_WORKING
  Resting maker bid(s) on B. A still open.
  → B_PARTIAL           fill on B, 0 < q_B < q_A
  → LOCKED              q_B == q_A
  → REPLACE             A clock stepped, or B book moved, or TIF/queue lost
  → TOUCH_40            A ≤ 40 and no working B @ ≤ H_MAX
  → ABORT_FLAT          A ≤ ABORT_A, or B unjoinable through H_MAX, or kill
  → CANCEL_B_WIN        A recovers > ARM_A + hysteresis and q_B == 0
  → A_SETTLED / A_SETTLED_0   while B still working: cancel B first

B_PARTIAL
  Residual A is still naked. Residual B working or not.
  Lock so far = 100 − VWAP_A − VWAP_B on the filled pair only.
  → LOCKED              residual A == 0
  → REPLACE             work residual B, same rules
  → ABORT_FLAT          flatten residual A; leave filled B to settlement
                        (do not sell B to “undo” — that reopens A-risk)

LOCKED
  q_A == q_B. Cancel residual B bids. Do not sell A. Do not sell B.
  Terminal = 100 − VWAP_A − VWAP_B − fees. Both settlements pay $1.00 total.
  → DONE

TOUCH_40
  A has printed ≤ 40. Residual A > 0.
  If no working post-only B ≤ H_MAX: submit B @ H_MAX (60) if joinable.
  If H_MAX would cross: this is a taker-or-abort decision.
      Study default: do **not** take B above H_MAX. Go ABORT_FLAT.
  → B_WORKING | LOCKED | ABORT_FLAT

ABORT_FLAT
  Cancel all B orders (working and UNKNOWN-reconcile).
  Reduce-only IOC sell residual A at best bid, existing primitive.
  Partial A retries until flat or UNKNOWN→reconcile.
  Filled B stays. Do not invent a B flatten.
  → DONE

DONE
  No working orders. Residual A = 0 or settled. Audit closed.
```

### Outcome table (what the code must not drop)

| A path | B path | Required action | Terminal (gross, 1 lot, A VWAP 80) |
|---|---|---|---|
| Never ≤55, settles 100 | none | nothing | +20 |
| Never ≤55, settles 0 | none | nothing — this study did not arm | −80 |
| ≤55, B fills 44, A then wins | filled | hold both | **−24** (winner locked; the cost of insurance) |
| ≤55, B fills 44, A then loses | filled | hold both | **−24** |
| ≤40, B fills 60 | filled | hold both | **−40** |
| ≤40, B gaps 45→75, unjoinable | miss | ABORT_FLAT A | A fill whatever is left (can be 3¢) |
| ≤20 before any B fill | miss | ABORT_FLAT A | A @ residual bid |
| B partial 2/7 | — | keep working 5; never pad | mixed |
| B working, A recovers to 70 | unfilled | cancel B, return A_OPEN | +20 if A wins |
| Disconnect / stale / inverted | any | cancel B, STOP NEW B, reconcile. If A ≤ ABORT_A, flatten A | fail closed |
| Kill switch | any | no new B, cancel B entries, preserve abort flatten | existing kill semantics |
| Duplicate B submit | — | idempotent client_order_id | no double B |
| B fill after we already flattened A | late fill | we now own naked B. Flatten B reduce-only. Incident. | do not hold a new directional |

The last row is why B must be cancel-before-A-IOC, and why UNKNOWN B after abort is an incident, not a journal footnote.

Hysteresis on `CANCEL_B_WIN` is required so A oscillating 54/56 does not flicker the B bid. Propose 3¢ and measure; do not invent a live value.

---

## 7. Order tactics on B (the “algorithmic execution”)

One working **join price**, plus optional **passive reserves**, all post-only, all ≤ `H_MAX`.

**Join (primary).**  
Each B quote: `J = min(B_bid, H_MAX)` if `J < B_ask` (post-only legal). If `B_bid ≥ H_MAX` or `B_ask ≤ H_MAX` would cross, do not take. That print is an abort or a wait, not a chase.

**Reserves (optional, same qty budget).**  
Do not multiply quantity. A 7-lot residual may be split across levels that sum to 7, for example 3@44 / 2@49 / 2@54, never 7+7+7. Child orders share one `PositionId` and one residual counter. Replace on each A-clock step or on a B-book move of ≥1 tick.

**Replace discipline.**  
Cancel/replace is a trading event. Rate-limit it. A flickering 1-minute candle must not produce a replace storm. Live quotes are the authority, not candle closes. If the quote is stale, **do not replace toward the market**; cancel and sit in `QUOTE_STALE`.

**What we will not do:**

- VWAP/TWAP slice of B as if this were an equity child order. The window is a dying binary, not a day order.
- Mid. Kalshi has no official mid. Join bid or reject.
- “Peg 40 on B from T0.” Through-market. Already closed on 2026-09-02.
- Take B above `H_MAX` “just this once.” That is a worse stop with extra legs.
- Sell A at 55 to “be safe.” That is Katy clock-trail behavior; it cuts winners (NBA 2Q −1.32¢ vs always-80/40). This study keeps A until lock or abort.

**Abort execution (A).**  
Reuse the existing reduce-only IOC primitive. Add what 2026-08-25 did not have: a **max-slippage record** (requested vs filled, integer cents) and a hard stop on re-IOC if the last fill was ≤ `ABORT_A` and the book is still empty — then residual A rides to settlement rather than paying 1¢ in a loop. That last clause is a **policy choice** and must be tested; do not silently pick it in code.

---

## 8. What must change in Momento before a bot can run this

This is a platform change, not a strategy comment.

| Layer | Today | Required for this study |
|---|---|---|
| Strategy | Single A. `ExecuteStop` on 50% VWAP. | Propose `ArmB`, `ReplaceB`, `AbortFlat`. No Kalshi calls. |
| Risk | `DuplicateGamePosition`. One market / game. Cap 5 slots. | A **complementary pair** on the same `GameId`: B allowed iff it reduces net binary exposure (qty_B ≤ qty_A, opposite YES). B must not consume a second “open position” slot as if it were a new bet. B premium **increases** cash outlay (`80 + 44`); budget math must see that. Reject B if it would exceed remaining snapshot budget. |
| Execution | One working entry + IOC flatten on A. | Two markets, two live orders, cancel-B-before-IOC-A, late-B-fill flatten. |
| Tracker | Fill-authoritative on A. | Fill-authoritative on A **and** B. Residual counters. Lock cents from actual VWAPs, not 40. |
| Audit | signal → risk → order → fill → stop | Plus: arm reason, join price, complement snapshot (A bid, B bid, A+B), gap flag, abort reason, requested vs filled, fees by leg. Append-only. |
| Kill | no new A, flatten A allowed | no new A, no new B, cancel B, flatten residual A |
| Live gate | three live flags for A | B is a **new** live behavior. Paper first. Same three flags, plus an explicit `ENABLE_DUAL_LEG_LOCK` that defaults off. Presence of keys is not enough. |

`crates/risk` is not Austin DRE. Do not implement this inside Austin, Choosin Texas, Katy, or `frontend/roller-terminal`. Algorithmic Execution on the 17-system bracket is still `NOT_IMPLEMENTED`. This document does not open an NBA bot.

Integer types only: cents, contract qty, fees, lock, VWAP.

---

## 9. Measurement the quant must run before anyone calls this optimal

Candles cannot answer fill rate. They can answer **whether the join was legal**.

**Study A — arm legality (warehouse, no fill assumed).**  
On locked FIRST80 books, at first A close ≤ 55 after entry:

- B bid, B ask, A+B, spread, `post_only(44)` joinable? (44 < ask)
- How often is B still ≤ 40 while A is 55? (stale-complement window)
- How often has B already ≥ 60? (arm too late)

If A+B ≈ 100 and B ask ≥ 45, a 44 bid is a real maker join. If B has already gapped to 70, arm is aborted. If B is still 25, 44 is through-market.

**Study B — path occupancy (still not a fill).**  
Between ARM and ABORT, does B’s bid ever occupy {44, 49, 54, 59, 60} on a tradable bar, or only jump through? Report in-band vs gap the same way A1 did. Gaps stay misses.

**Study C — counterfactual lock vs IOC-A.**  
For each trade, four books, **labeled**:

| Book | Rule | Label |
|---|---|---|
| `IOC_A_MODEL_A` | sell A at 40 | SCENARIO (today’s research identity) |
| `IOC_A_MODEL_B` | sell A at stop-minute close | ESTIMATED candle |
| `MAKER_B_INBAND` | first in-band B join ≤ H_MAX at observed close, else abort Model B | ESTIMATED |
| `LIVE_L4` | paper/live VWAP_A, VWAP_B, fees | **NOT_RUN** |

Do not promote B closes to fills. Do not write 40 into the lock unless a fill ticket says 40.

**Study D — paper, 1 lot, not live.**  
Same `book_id` discipline as the 2026-27 research book: 1 contract, reconstruct, do not invent fills. Record T0 (A ≤ ARM_A) … T5 (final B or A fill). That distribution is the only object that can be called “optimal.”

A1 already closed “H=40 exact, causal, fallback 80→40” as **no economic case**. This study is a **different order type** (working join from 44, cap 60, abort 20). It may also lose. If it loses, we keep IOC-A and size as if L ≈ 46–54¢. We do not expand the band.

---

## 10. Invariants

```text
qty_B_working + qty_B_filled  ≤  qty_A_filled
H_working                     ≤  H_MAX
post_only(B)                  ⇒  limit < yes_ask_B
A ≤ ABORT_A                   ⇒  no open B orders
LOCKED                        ⇒  no working orders, both legs held
UNKNOWN                       ⇒  no second submit of the same intent
kill                          ⇒  no new B
fees, prices, qty             ⇒  integers
A and B                       ⇒  same event_id, opposite YES, never inferred
candle close                  ⇒  not a fill
```

Failure modes the tests must name:

- through-market B@40 at T0
- double B (qty_B > qty_A)
- B fill after A flatten (naked B)
- replace storm
- gap `B: 45→75` booked as 60
- abort IOC looping into a 1¢ book
- Risk treating B as a second independent game
- budget ignoring B premium
- promoting this memo into FIRST01
- remounting this inside Choosin Texas / Austin / Katy

Required test classes (existing house rule): unit, state-machine, partial fill, no fill, cancel race, duplicate ack/fill, timeout, UNKNOWN reconcile, reject, restart with A open and B working, settlement of a locked pair, Risk reject of a non-complement B, boundary on `H_MAX` and `ABORT_A` (19 / 20 / 21, 59 / 60 / 61).

---

## 11. What this document does not do

- Does not change live FIRST01 / 80 / 81 / 83 / 89.
- Does not start W9.
- Does not arm NBA 2026-27. That book is `RESEARCH_REGISTERED`, 1 lot, stop 40, **no second ticker**.
- Does not authorize a production liquidation model.
- Does not treat any A1 / hybrid / Katy number as a fill rate.
- Does not claim MLB is “currently unprofitable” as a season total. It claims the **2026-08-25** live day realized −$31.77 with a **3¢** IOC, which is the execution failure this study is for.
- Does not invent L2, mids, or a 40 that gapped.

---

## 12. Pointers

| Object | Path |
|---|---|
| Live day that printed 3¢ | `docs/desk/2026-08-25-loss-review.md` |
| Current stop spec | `docs/architecture/mlb-strategy.md`, `docs/founder/MOMENTO-TRADING-DESK.md` §6.3 |
| 40 is a trigger | `docs/research/ncaab/FIRST80_LIQUIDATION_MODEL_V1.md` |
| Asked-six 40 ≠ fill | `research/first80_asked_six_80_40_liquidation/REPORT.md` |
| A1/A2 clocks, gap fiction | `docs/research/A1_HYBRID_HEDGE_REPORT.md`, `docs/research/DAY_LOG_2026-09-02.md` |
| T0 complement | `docs/research/first80_alpha_decomposition_v1/MODULE_D_HEDGE_STATE_ANALYSIS.md` |
| Fees 2026–27 | `docs/research/KALSHI_SPORTS_FEE_MODEL_2026_2027.md` |
| L1≠L2≠L3≠L4 | `docs/research/EXECUTION_INTEGRITY_ENGINE/EXECUTIVE_SUMMARY.md` |
| Risk one-game | `crates/risk` `DuplicateGamePosition` |

---

## 13. Ask of the engineer

Write the state machine and the measurement harness. Do not write a live order.

First deliverable: Study A/B occupancy on existing FIRST80 tapes — joinable 44 at first A≤55, occupancy of 44–60 on B, gap rate, abort rate — **no fill assumed**. Second: a paper OMS sketch that can hold A+B under the invariants above. Third: a Risk RFC for complementary-pair occupancy and cash. Live Create V2 on B is out of scope until those three exist and a human sets `ENABLE_DUAL_LEG_LOCK`.
