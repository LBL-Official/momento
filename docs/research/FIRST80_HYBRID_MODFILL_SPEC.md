# FIRST-80 hybrid MOD-fill specification

Research book only. **LIVE EXECUTION CHANGED: FALSE.**

This document is the complete definition of the hybrid strategy measured
on 2026-09-02, the finite P&L identities, the portfolio totals versus
the other three books, and every rule that would be required to *attempt*
a live implementation. It does **not** authorize live trading. It does
**not** change FIRST01, Risk, or Execution.

```text
CANDLE TAXONOMY              ≠  ACTUAL MAKER FILL
V3 class A/B                 =  LOOKAHEAD (persist after first ≥H close)
NCAAB working universe       =  P5 vs P5 only (n = 721)
Full-warehouse NCAAB 4,099   =  historical V1 only — do not use
Fees                         =  UNRESOLVED (all P&L is gross)
L2 / queue / depth           =  UNOBSERVED
```

Code: `apps/ncaab-data/scripts/first80_hybrid_modfill_h37_42.py`  
Data: V3 `opportunity_dataset.parquet` joined to V4 `trade_ledger.parquet`.

---

## 0. What this strategy is

After a FIRST-80 entry on favorite YES, **try** an opponent-YES hedge at
**H = 40¢**. Credit a hedge fill only if the opponent path is V3
**A_STRONG or B_MODERATE** (persist, not a jump/wick). If that
moderate-confidence fill is **not** present, run **80→40** on the
favorite. One trade, one book, two possible exits.

```text
                    FIRST-80 fill on A1 (favorite YES @ 80)
                                    │
                                    ▼
                    A2 (opponent YES) later close ≥ 40
                     and V3 class ∈ {A_STRONG, B_MODERATE} ?
                           │                    │
                          yes                   no
                           │                    │
                           ▼                    ▼
                    lock 20 − 40 = −20     80→40 on A1
                    (both YES owned)       sell A1 @ 40 if A1
                                           close ≤ 40, else hold
```

Working H is **40**. The 37–42 scan was a neighborhood check, not a
reselection of H*.

---

## 1. Universes (hard filters)

A trade is in the book if and only if all of the following hold.

### 1.1 Sport series

| Sport | Kalshi series | Warehouse | n FIRST-80 |
|---|---|---|---:|
| NBA | `KXNBAGAME` | 2025–2026 | 1,230 |
| NCAAB | `KXNCAAMBGAME` | 2025–2026 | **721 (P5 vs P5)** |

Do not mix in NBA/NCAAB other series. Do not use women’s NCAAB.

### 1.2 NCAAB P5 vs P5 (mandatory)

Both `home_team_code` and `away_team_code` on `ncaab_games.parquet`
must be in this 2025–26 set (70 codes). One mid-major ⇒ exclude.

```text
ACC + B1G + Big 12 + SEC + Pac-12(ORST, WSU)

ALA ARIZ ARK ASU AUB BAY BC BYU CAL CIN CLEM COLO
DUKE FLA FSU GT HOU ILL IND IOWA ISU KSU KU LOU LSU
MD MIA MICH MINN MISS MIZZ MSST MSU NCST ND NEB NW
OKLA OKST ORE ORST OSU PITT PSU PUR RUTG SCAR SMU
STAN SYR TCU TENN TEX TTU TXAM UCF UCLA UGA UK UNC
USC UTAH UVA VAN VT WAKE WASH WIS WSU WVU
```

Gonzaga, AAC, MWC, and 2026–27 Pac-12 adds are **out**.  
P5 vs mid-major (270) and mid vs mid (3,108) are **out**.

### 1.3 FIRST-80 membership (frozen)

Reuse `nba_80_40_execution_audit` / NCAAB clone. Do not invent a new 80.

```text
FIRST-80 ⇔ first tradable 1-minute bar in the game-day window such that
  yes_bid_close ≥ 80¢
  after a prior tradable yes_bid_close < 80¢

Tradable bar:
  is_valid
  bid and ask present
  bid ≤ ask
  ask − bid ≤ 10¢          (MAX_SPREAD = 1000 e4)
  volume > 0 or prior quality latch
  end_period_ts ∈ [game_window_start, min(market_close, game_window_end)]
```

Settlement must be known (`expiration_result_yes` is True or False).
`NO_FIRST_80` rows are not trades.

Entry price in the book is **80¢**, not the candle close (which may be
81). Entry **maker fill at 80 is still unobserved**.

---

## 2. Money: finite integer cents

All P&L is integer cents per contract. No `f64` equality on money.

```text
YES settlement ∈ {0, 100}          Kalshi binary
ENTRY          = 80
H              = 40                 working hedge bid
WIN            = 100 − 80 = +20
HOLD_LOSS      = 0 − 80   = −80
STOP_40        = 40 − 80  = −40     sell favorite @ 40
LOCK           = 100 − 80 − H
               = 20 − H
               = −20                when H = 40
LEAK_80_40     = 0                  Model A: favorite never close-40 and lost
```

Kalshi prices and quantities are integer cents and integer contracts.
Desk size `Q` is a positive integer. Dollar P&L:

```text
dollars = Q × (pnl_cents) / 100
```

Research tables below are **Q = 1** unless labeled. User 1,000-lot
dollars = total_cents × 10.

**Fees = 0 in every number in this file.** Two-leg fees would reduce
hedge/hybrid more than 80→40.

---

## 3. The four books (same trades)

Every FIRST-80 trade is scored under all four. No trade is dropped
except by the universe filters in §1.

### 3.1 Hold

```text
pnl_hold = +20  if favorite YES settles 100
         = −80  if favorite YES settles 0
```

Do nothing after the 80 entry.

### 3.2 80→40 (Model A)

```text
stop_close_triggered ⇔ some later tradable A1 yes_bid_close ≤ 40¢

pnl_8040 = −40  if stop_close_triggered
         = +20  if not stop_close_triggered and favorite won
         =  0   if not stop_close_triggered and favorite lost   # leak
```

40 is a **trigger**, not a proven sell fill. Model A assumes the sell
fills at exactly 40.

NBA leaks: 0. NCAAB P5 leaks: 0. Full-warehouse NCAAB had 2 leaks
(historical only).

### 3.3 V1 hedge H=40 (REPLACE)

```text
v1_touch ⇔ first later tradable A2 yes_bid_close ≥ 40¢

pnl_v1 = −20  if v1_touch
       = +20  if not v1_touch and favorite won
       = −80  if not v1_touch and favorite lost
```

**Fake fill:** every `v1_touch` is booked at **exactly 40**, including
closes of 42, 63, 75, 99. That is why this book is labeled fake.

### 3.4 Hybrid MOD H=40 (this strategy)

```text
mod_fill ⇔ v1_touch
         ∧ opportunity_quality_class ∈ {A_STRONG, B_MODERATE}

pnl_hybrid = −20  if mod_fill
           = pnl_8040  otherwise
```

Class is computed on the **opponent** tape at H=40. See §5.

---

## 4. Finite P&L identities (measured)

### 4.1 NBA n = 1,230

| Book | Formula | Total ¢ | EV / contract |
|---|---|---:|---:|
| Hold | 1,019×(+20) + 211×(−80) | +3,500 | +2.8455 |
| 80→40 | 910×(+20) + 320×(−40) | +5,400 | +4.3902 |
| V1 H=40 | 774×(+20) + 456×(−20) | +6,360 | +5.1707 |
| **Hybrid** | **302×(−20) + 92×(−40) + 836×(+20)** | **+7,000** | **+5.6911** |

Hybrid mix: 302 MOD hedges (152 later won, 150 lost), 928 fallback
(92 are 80→40 stops, 836 are hold-wins, 0 leaks).

Check: `302×(−20) + 92×(−40) + 836×(+20) = −6,040 − 3,680 + 16,720 = 7,000`.

Versus 80→40: `7,000 − 5,400 = +1,600¢` on the book (`+1.3008¢` / trade).  
Versus V1: `7,000 − 6,360 = +640¢`.  
Versus Hold: `7,000 − 3,500 = +3,500¢`.

228 trades **better** than 80→40 (A/B losers: −40 → −20).  
74 trades **worse** (A/B winners: +20 → −20).  
928 **equal** (fallback).

### 4.2 NCAAB P5 vs P5 n = 721

| Book | Formula | Total ¢ | EV / contract |
|---|---|---:|---:|
| Hold | 601×(+20) + 120×(−80) | +2,420 | +3.3564 |
| 80→40 | 533×(+20) + 188×(−40) | +3,140 | +4.3551 |
| V1 H=40 | 439×(+20) + 282×(−20) | +3,140 | +4.3551 |
| **Hybrid** | **190×(−20) + 58×(−40) + 473×(+20)** | **+3,340** | **+4.6325** |

Hybrid mix: 190 MOD hedges (107 later won, 83 lost), 531 fallback
(58 stops, 473 hold-wins, 0 leaks).

Check: `190×(−20) + 58×(−40) + 473×(+20) = −3,800 − 2,320 + 9,460 = 3,340`.

Versus 80→40: `+200¢` on the book (`+0.2774¢` / trade).  
Versus V1: `+200¢` (V1 ≡ 80→40 on P5).  
Versus Hold: `+920¢`.

130 better / 60 worse / 531 equal vs 80→40.

### 4.3 Combined working desk (NBA + P5) n = 1,951

| Book | Total ¢ | EV / contract | $ at Q=1,000 |
|---|---:|---:|---:|
| Hold | +5,920 | +3.0343 | $59,200 |
| 80→40 | +8,540 | +4.3772 | $85,400 |
| V1 H=40 | +9,500 | +4.8693 | $95,000 |
| **Hybrid** | **+10,340** | **+5.3009** | **$103,400** |

Do **not** add full NCAAB 4,099 into this combined book.

---

## 5. V3 class algorithm (exact — this is the “moderate fill” test)

Computed on opponent 1-minute tradable quotes after FIRST-80, at a
candidate H (working H = 40). Prices below are **e4** (80¢ = 8000).

Let `hx = H × 100`.  
`quotes[i] = (ts, bid_close, bid_high, bid_low, ask_close, …)`.

### 5.1 First close opportunity

```text
v1_touch ⇔ ∃ first i after entry with tradable bid_close ≥ hx
```

If none: class is empty, `mod_fill = false`.

### 5.2 Jump flag (on that first i)

```text
prev = bid_close[i−1]
jump_10c ⇔ prev is not None
         ∧ prev < hx − 1000          # more than 10¢ below H
         ∧ bid_close[i] ≥ hx
```

A 23 → 75 minute is `jump_10c = true` (CLASS E).

### 5.3 Subsequent persist

Starting at `i+1`, count consecutive later tradable bars with
`bid_close ≥ hx`. Stop at the first bar that fails (after at least the
first subsequent bar). That count is `persist_subsequent_min`.

`close_above_H ⇔ bid_close[i] ≥ hx`.

### 5.4 Class assignment (`classify`)

```text
if not v1_touch and wick_only (high ≥ hx, close never ≥ hx):
    D_WICK_ONLY
elif jump_10c:
    E_JUMP
elif persist ≥ 5 and close_above_H:
    A_STRONG          # MULTI_MINUTE_ABOVE
elif persist ≥ 3 and close_above_H:
    A_STRONG          # PERSISTENT_ABOVE
elif persist ≥ 1 and close_above_H:
    B_MODERATE
else:
    C_WEAK
```

### 5.5 Moderate fill (hybrid)

```text
mod_fill ⇔ class ∈ {A_STRONG, B_MODERATE}
```

Equivalent: `v1_touch ∧ ¬jump_10c ∧ persist ≥ 1 ∧ close_above_H`.

| Class | Hybrid | Then |
|---|---|---|
| A_STRONG | hedge | lock −20 |
| B_MODERATE | hedge | lock −20 |
| C_WEAK | no | 80→40 |
| E_JUMP | no | 80→40 |
| D_WICK_ONLY | no | 80→40 |
| no touch | no | 80→40 |

### 5.6 Lookahead (mandatory warning)

`persist ≥ 1` is counted on bars **after** the first ≥H close. At the
first 40 print you do **not** know A vs C vs E-complete. The research
book peeks. V5 restated “wait K bars then lock at then-price” and
**lost** to 80→40 (NBA +4.12 vs +4.39; full NCAAB +3.56 vs +3.90;
P5 not re-run on V5 H=22).

**The +5.69 / +4.63 numbers are not a T0 or T1 decision.**

---

## 6. Why hybrid beats V1 and 80→40 on the candle book

V1 hedges **all** 456 NBA / 282 P5 close≥40 prints, including C and E.

Hybrid hedges only A+B (NBA 302 / P5 190) and sends C+E+none to 80→40.

- **A** is ~45–52% win rate → locking −20 instead of −40 (or −80) is +EV.
- **C** is ~67–73% win rate → V1 locks −20 on winners; hybrid keeps many
  of those as +20 via 80→40 (they often never print favorite-40).
- **E** is the 23→75 gap. V1 books −20. Hybrid does **not**; 80→40 may
  still stop the favorite at 40.

That mix is why hybrid total > V1 total. It is selection on the
**future** persist path, not a free lunch.

---

## 7. Portfolio math (research, Q parameterized)

### 7.1 Per-trade random variable

Let `X` be hybrid P&L in cents. Support on this book:

```text
X ∈ {−40, −20, +20}
```

(leaks would add 0; none in NBA or P5).

NBA hybrid: 92 × −40, 302 × −20, 836 × +20.  
P5 hybrid: 58 × −40, 190 × −20, 473 × +20.

### 7.2 Pace (operator assumption, not a model)

```text
10 trades / week = 10/7 per day = 520 / year
```

EV / week at Q contracts:

```text
EV_week_dollars = 10 × (mean_cents) × Q / 100
```

| Book | NBA mean | NBA $/week Q=1000 | P5 mean | P5 $/week Q=1000 |
|---|---:|---:|---:|---:|
| Hold | +2.85 | $284.55 | +3.36 | $335.64 |
| 80→40 | +4.39 | $439.02 | +4.36 | $435.51 |
| V1 | +5.17 | $517.07 | +4.36 | $435.51 |
| Hybrid | +5.69 | $569.11 | +4.63 | $463.25 |

### 7.3 Capital

Favorite entry notional = `Q × 80¢`.  
If a hedge fill is reserved up front: `Q × (80+H) = Q × 120¢`.

On a **$6.25** game budget (12.5% of $50 snapshot):

```text
80→40     Q=7   reserved $5.60
hedge/hyb Q=5   reserved $6.00   if both legs reserved
```

Per-contract EV ranking can **flip** on reserved cash. This spec’s
totals are **per contract**, not EV / reserved dollar.

Risk today: **one logical position per game**; opponent YES is not a
bookable second market. Hybrid **cannot** be submitted by FIRST01 as
written.

### 7.4 Drawdown (additive, Q=1,000, no $50 start)

Peak-to-trough of chronological `cumsum(Q × pnl_cents / 100)`.

Previously measured on V1/hold/80→40 (not re-pathed for hybrid in this
file). Hybrid DD will lie between 80→40 and V1 because the −80 tail is
still cut on A/B and on 80→40 fallbacks, but C/E losers that 80→40
misses can still print −80 if they never hit favorite-40 (P5: 0 such
leaks).

Do not report % of $50 at Q=1,000.

### 7.5 Two-outcome Kelly (not a size)

On books where every winner is +20:

```text
f* = mean_cents / 20
```

NBA hybrid 5.6911/20 = **28.46%**. This uses the −20/−40 mix as if the
A/B fill were real. Do not size live from it.

---

## 8. Complement (do not buy A1 at 60)

When A2 first closes ≥ 40, measured A1 bid is **not** 60:

| | NBA | NCAAB P5 |
|---|---:|---:|
| Median A1 bid at A2-40 | 56¢ | 55¢ |
| Median A2 close | 42¢ | 43¢ |
| A1+A2−100 | −1.5¢ | −1.7¢ |

Hybrid does **not** sell A1 at 56. It either (a) buys A2 and keeps A1,
or (b) later sells A1 at 40. Selling A1 at the observed touch is a
**fifth** book (+3.06 NBA / +1.75 P5) and is **worse** than 80→40.

Algebra identity only: `60−80 = 20−40 = −20`. The tape is 56/42.

---

## 9. Comparative scoreboard

Working universes only.

| | NBA total | NBA EV | P5 total | P5 EV | Combined total |
|---|---:|---:|---:|---:|---:|
| Hold | +3,500¢ | +2.85 | +2,420¢ | +3.36 | +5,920¢ |
| 80→40 | +5,400¢ | +4.39 | +3,140¢ | +4.36 | +8,540¢ |
| V1 H=40 | +6,360¢ | +5.17 | +3,140¢ | +4.36 | +9,500¢ |
| Hybrid | **+7,000¢** | **+5.69** | **+3,340¢** | **+4.63** | **+10,340¢** |

**Use hybrid if and only if** you believe A/B minutes **filled at 40**
and you are allowed to **skip** C/E after seeing persist.  
**Otherwise 80→40 is the causal champion.**

Causal V5 (wait, pay T2 bid, full NCAAB not P5): NBA +4.12 < 80→40.

---

## 10. Rules required to program this — research replay

These rules reproduce the **candle book**. They are not live orders.

```text
R0   Q integer ≥ 1. Fees = 0. No L2.
R1   Load FIRST-80 candidates. NBA all. NCAAB both codes ∈ P5_CODES.
R2   For each trade, join V3 opportunity row at H=40 on event_id.
R3   mod_fill = opportunity_close ∧ class ∈ {A_STRONG, B_MODERATE}
R4   if mod_fill: pnl = 20 − 40 = −20
     else:        pnl = −40 if stop_close_triggered
                        else +20 if won else 0
R5   Universe total = Σ pnl. EV = total / n.
R6   Do not peek OOS to pick a new H. Working H = 40.
R7   Log event_id, ticker, opponent_ticker, class, mod_fill,
     pnl_hybrid, pnl_8040, pnl_v1, pnl_hold, game_date.
```

State machine for **replay** (one trade):

```text
IDLE → ENTERED_80 → (watch A2 and A1 in parallel)
  if A1 close≤40 before a completed A/B on A2:  mark 80→40, STOPPED
  if A2 close≥40:
       wait subsequent persist (LOOKAHEAD)
       if jump_10c:               FALLBACK_8040
       elif persist≥1 and close≥H: HEDGED
       else:                      FALLBACK_8040
  if game ends with neither:      HOLD
```

---

## 11. Rules required to program this — live (blockers first)

**Do not enable this in FIRST01 / Risk / Execution from this document.**

### 11.1 Hard blockers (must be false or the live path is illegal)

| ID | Blocker | Status today |
|---|---|---|
| L0 | `mode=live` ∧ `live.enabled=true` ∧ `live.confirmation=ENABLE_LIVE_TRADING` | All three required; default must not be live |
| L1 | Strategy must not submit Kalshi orders | Absolute rule |
| L2 | Risk must approve every intent | Absolute rule |
| L3 | One logical position per game | Risk; **opponent YES is a second market** |
| L4 | Duplicate-market / duplicate-signal | Risk |
| L5 | Paper must not be able to hit live | Absolute |
| L6 | Tests must not need live credentials | Absolute |
| L7 | A/B class needs future bars | **Cannot decide at first 40 print** |
| L8 | Post-only bid @ 40 while A2 ask ≈ 21 | **Rejects**; 40 is through the market |
| L9 | Actual maker fill at 80 and at 40 | **Unobserved historically** |
| L10 | Fees on two legs | **Unresolved** |

Until L3, L7, L8, L9 are solved, a live “hybrid” is a **different
strategy** than the +7,000¢ book.

### 11.2 Objects a live candidate would need (if ever authorized)

Do not invent Kalshi endpoints. Use the existing Create V2 adapter
(maker GTC entry, reduce-only IOC liquidation) after Risk approval.

**Identifiers (every event):**  
`event_id, market_id_A1, market_id_A2, strategy_id, signal_id,
risk_decision_id, client_order_id_A1, client_order_id_A2,
order_id_*, position_id, timestamp`.

**Intent fields (every order):**  
`side, price_cents, qty, order_type, time_in_force, strategy_id,
reason, risk_decision_id`. Client order id required. Idempotent.
UNKNOWN on timeout → reconcile, do not blind retry.

### 11.3 Causal live state machine (not the research EV)

This is the **only** form that does not peek. It will **not** reproduce
+5.69 / +4.63.

```text
S0  IDLE
S1  ELIGIBLE_GAME
      NBA: KXNBAGAME
      NCAAB: KXNCAAMBGAME ∧ both team codes ∈ P5_CODES
S2  WATCH_A1
      first tradable A1 bid_close ≥ 80 after bid_close < 80
S3  ENTER_A1
      TradeIntent: BUY A1 YES, price=80, maker/post-only, qty=Q
      Risk: one position / game, budget, limits, kill switch, hours
      Execution: submit only after approve
      if not ACK fill: do not start hedge; stay flat or UNKNOWN→reconcile
S4  OWN_A1
      A2 ask is typically ~20. Do NOT send buy A2 @ 40 (would take ~21,
      lock ~0). Do NOT rest post-only 40 (reject).
S5  WATCH_BOTH
      A1: if tradable bid_close ≤ 40 and still OWN_A1 only
          → LIQUIDATE_A1 reduce-only IOC (80→40). 40 is a trigger.
          Fill price is live, not 40. Model A is an upper bound.
      A2: if ask_close > 40, a post-only bid @ 40 can *exist*.
          That is a pullback bid, not the V1 “first close ≥ 40” clock.
      A2: if bid_close first ≥ 40 while ask ≤ 40: no resting 40 bid
          exists. This is CLASS E / through-market. Do not book −20.
          Continue 80→40 on A1.
S6  OPTIONAL_PERSIST (only if a 40 bid is actually resting)
      Count subsequent qualifying minutes bid_close ≥ 40.
      Cancel 40 bid if persist fails or A1 already liquidated.
      If filled @ 40: state HEDGED. Lock 20−H only if fill_px = 40.
      If filled at P ≠ 40: lock = 20−P. Do not lie.
S7  HEDGED
      Own A1 and A2. No further entry. Position-manage / settle.
      Do not add size.
S8  FLAT
      After 80→40 complete, or settlement, or kill-switch flatten
      of entries (preserve position-management if already open).
```

Kill switch: no new entries, no new exposure, cancel ready entry
orders (A1 80 and A2 40), keep reduce-only exits, record the event.

### 11.4 Sizing (do not hard-code in strategy)

```text
Q from config / weekly snapshot / Risk
economic budget includes fees when fees exist
max 5 open MLB positions is a live MLB rule — not this research
NBA/NCAAB are not armed
```

Research illustrations used Q=7 on $50 and Q=1,000 for DD. Neither is
a live default.

### 11.5 Risk checks (must not live in strategy)

Maximum position size, portfolio / sport / market exposure, daily
trades, daily loss, open positions, duplicate market, duplicate
signal, stale market, trading hours, kill switch.

Hybrid adds: **second market on the same event**, reserved `80+H`
if the hedge may fill, and “do not double-enter if A1 already
stopped.”

### 11.6 Reconciliation

HTTP timeout on A1 or A2 create = **UNKNOWN**, not FAILED.  
Reconcile with exchange. FOUND / NOT FOUND / AMBIGUOUS.  
If unknown whether the 40 filled: **STOP NEW EXPOSURE.**  
Do not submit a second 40. Do not assume locked −20.

### 11.7 Telemetry required before any fill claim

`T_ENTRY, T_A2_ORDER_SUBMIT, T_ACK, T_FIRST_TOUCH_H, T_FIRST_FILL,
ORDER_PRICE, FILLED_QTY, VWAP, BEST_BID/ASK at submit and touch,
VISIBLE_DEPTH or DEPTH_UNAVAILABLE, CLASS if computed online`.

Target: `P(actual_fill | H, persist, jump, spread)` — **NOT_RUN**.

---

## 12. Tests that must exist before anyone codes this into the host

Do not delete a failing test to make hybrid look good.

1. Identity: NBA hybrid sums to **7,000¢**; P5 to **3,340¢**.
2. P5 filter: 721 trades; 0 missing game joins; mid-majors excluded.
3. Class: jump 23→75 ⇒ E ⇒ fallback 80→40, not −20.
4. Persist 0 after touch ⇒ C ⇒ fallback.
5. Persist ≥ 1 and not jump ⇒ hedge −20.
6. Fallback leak: no favorite-40 and loss ⇒ 0 (Model A), not −80.
7. Favorite-40 during persist wait (V5 race) ⇒ 80→40, not hedge.
8. Post-only 40 while ask < 40 ⇒ reject / no rest (unit on adapter).
9. Timeout on A2 create ⇒ UNKNOWN, no second submit.
10. Risk rejects second market ⇒ no order (today’s expected live).
11. Paper cannot place live.
12. Replay uses only bars ≤ decision time in any **causal** variant.
13. Fees remain 0 or are an explicit second column — never silent.

---

## 13. What you may not do with this spec

- Do not arm NBA or NCAAB live from +5.69 / +4.63.
- Do not treat V3 A/B as a live fill.
- Do not rest 40 while A2 is ~20.
- Do not replace FIRST01 MLB 80/81/83/89 with this.
- Do not change H* from FULL-sample 37–42 wiggles.
- Do not add full NCAAB 4,099 back into the working book.
- Do not report theoretical lock as realized P&L.

**Working causal trade remains 80→40.** Hybrid is a fill-and-persist
experiment. The research total is larger because it peeks at persist
and assumes those A/B prints filled at 40.

---

## 14. Source map

| Object | Location |
|---|---|
| FIRST-80 definition | `apps/nba-data/scripts/nba_80_40_execution_audit.py` |
| V3 class / jump / persist | `apps/ncaab-data/scripts/first80_opponent_hedge_execution_model_v3.py` `classify`, `features_at` |
| V4 hybrid vs 80→40 | `apps/ncaab-data/scripts/first80_opponent_hedge_optimal_v4.py` |
| This book | `apps/ncaab-data/scripts/first80_hybrid_modfill_h37_42.py` |
| V5 causal loss | `docs/research/FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5.md` |
| Live confirmation | `crates/core/src/config.rs` `ENABLE_LIVE_TRADING` |
