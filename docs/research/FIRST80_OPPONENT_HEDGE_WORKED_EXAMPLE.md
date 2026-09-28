# FIRST-80 opponent hedge — worked example (Lakers vs Bulls)

Research illustration only. **LIVE EXECUTION CHANGED: FALSE.**

This document is a teaching walkthrough of the frozen hedge tests
(`FIRST80_OPPONENT_40_HEDGE_V1`, `FRONTIER_V2`, `EXECUTION_MODEL_V3`).
It does not change FIRST01, Risk, Execution, or live order logic.

```text
CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL
L2 / queue / depth        =  UNOBSERVED
Fees                      =  UNRESOLVED
```

Teams used here are labels only. The counts and EVs below are from the
frozen NBA / NCAAB FIRST-80 universes, not from one Lakers–Bulls game.

---

## 1. The starting book

Lakers are the favorite. FIRST-80 fills:

```text
BUY  7  Lakers YES  @ 80¢
Cost = 7 × $0.80 = $5.60
```

Seven contracts is the $50 desk sketch (12.5% of $50 ≈ $6.25, so 7 × 80¢
= $5.60). Strategy code does not hard-code this size.

### Settlement matrix — unhedged FIRST-80

| | Lakers win | Bulls win |
|---|---:|---:|
| Lakers YES pays | 100¢ | 0¢ |
| You paid | 80¢ | 80¢ |
| **P&L / contract** | **+20¢** | **−80¢** |
| **P&L × 7** | **+$1.40** | **−$5.60** |

That is the basic long-favorite book.

---

## 2. Immediately rest the opponent hedge

Bulls YES is the mutually exclusive contract. After the Lakers 80¢ fill
is confirmed, rest a **maker bid** on the other side. Do **not** sell
Lakers YES at 40.

```text
You own:     7 Lakers YES @ 80¢
You bid:     7 Bulls YES  @ H
```

Working example: **H = 40¢** (V1). You do not necessarily buy the Bulls
immediately. The order sits.

Locked P&L if both legs later fill:

```text
100 − 80 − H  =  20 − H
```

| Hedge bid H | Paired cost | Locked P&L / contract | × 7 |
|---:|---:|---:|---:|
| 20¢ | 100¢ | 0¢ | $0.00 |
| 28¢ | 108¢ | −8¢ | −$0.56 |
| 40¢ | 120¢ | −20¢ | −$1.40 |
| 50¢ | 130¢ | −30¢ | −$2.10 |

Lower H is a better lock **if you get filled**. A lower bid is also less
likely to fill.

---

## 3. Payoff matrices once the hedge fills (H = 40)

Both legs owned:

```text
7 Lakers YES @ 80¢
7 Bulls YES  @ 40¢
Cost = 120¢ per pair  =  $8.40 for seven pairs
```

Exactly one contract settles at $1.

| | Lakers win | Bulls win |
|---|---:|---:|
| Lakers YES | +100¢ | 0¢ |
| Bulls YES | 0¢ | +100¢ |
| You paid | 120¢ | 120¢ |
| **P&L / pair** | **−20¢** | **−20¢** |
| **P&L × 7** | **−$1.40** | **−$1.40** |

Same dollar result either way. That is a complete hedge.

---

## 4. Path matrix — hedge vs 80→40 vs hold

80→40 is a **reactive sell of Lakers YES** after Lakers bid-close ≤ 40.
The hedge is a **passive buy of Bulls YES** at H, usually earlier.

Assume, for this table only:

- 80→40 fills at exactly 40¢ (Model A / candle upper bound)
- the H = 40 Bulls bid fills at exactly 40¢ if the opponent close later prints ≥ 40

Neither assumption is a live fill.

| Path | What happens in the game | Hold | 80→40 sell @ 40 | Hedge H=40 |
|---|---|---:|---:|---:|
| **A. Clean win** | Lakers 80→100. Bulls never reach 40. Hedge never fills. | **+20¢** | **+20¢** | **+20¢** |
| **B. False hedge** | Scare. Bulls print 40. Lakers still win. | **+20¢** | +20¢ if Lakers never hit 40; **−40¢** if they did | **−20¢** |
| **C. True reversal** | Lakers collapse. Bulls go 20→40→100. | **−80¢** | **−40¢** if the 40 sell fills; **−80¢** if it misses | **−20¢** |

### Dollars on 7 contracts

| Path | Hold | 80→40 @ 40 | Hedge H=40 |
|---|---:|---:|---:|
| A. Clean win | +$1.40 | +$1.40 | +$1.40 |
| B. False hedge (Lakers never printed 40) | +$1.40 | +$1.40 | **−$1.40** |
| B′. False hedge after Lakers also printed 40 | +$1.40 | **−$2.80** | **−$1.40** |
| C. True reversal, 40-stop fills | −$5.60 | **−$2.80** | **−$1.40** |
| C′. True reversal, 40-stop misses | −$5.60 | −$5.60 | **−$1.40** |

### The insurance trade (H = 40)

| | Per contract | × 7 |
|---|---:|---:|
| False hedge: give up +20, lock −20 | **−40¢** | **−$2.80** |
| Successful insurance: avoid −80, lock −20 | **+60¢** | **+$4.20** |

In general:

```text
false-hedge cost      = H          ( +20  →  20−H )
insurance benefit     = 100 − H    ( −80  →  20−H )
```

The hedge has positive EV only if protected catastrophes outweigh
unnecessary locks — **and** only if the resting bid actually fills.

---

## 5. Why the hedge can fire before the stop

Typical adverse path (V1 complement check, not one game):

```text
Lakers YES:   80 → 70 → 60 → 55
Bulls YES:    20 → 30 → 40     ← hedge opportunity
```

At the first later minute where Bulls `yes_bid_close ≥ 40`, the held
Lakers bid in that same minute was:

| | NBA | NCAAB |
|---|---:|---:|
| Median Lakers (held) bid | **56¢** | **55¢** |
| Mean held + opponent bid | 98.5¢ | 97.8¢ |

So the candle often offers a Bulls-40 fill while Lakers are still in the
mid-50s, not at the 40¢ liquidation trigger. Those are related events,
not the same event.

```text
Opponent close ≥ H   ≠   your resting bid filled
```

Price can jump `38 → 47`, or sit behind other 40¢ bids.

---

## 6. Mixture EV (how the tests score a book)

One FIRST-80 trade is classified into exactly one terminal bucket.

### Unhedged hold

| Bucket | P&L |
|---|---:|
| Lakers settle YES | +20¢ |
| Lakers settle NO | −80¢ |

### 80→40 (Model A: stop fills at 40)

| Bucket | P&L |
|---|---:|
| Never close-40, Lakers win | +20¢ |
| Close-40 stop | −40¢ |
| Leak (close-40 missed, loss) | 0¢ in the frozen identity |

```text
EV_80/40 = (N_win × 20 − N_stop × 40 + N_leak × 0) / N
```

### Opponent hedge, close-path proxy (V1)

Hedge “fills” in the test iff a **later tradable** opponent
`yes_bid_close ≥ H`. That is an opportunity count, not a maker fill.

| Bucket | P&L at H=40 |
|---|---:|
| No hedge, Lakers win | +20¢ |
| Hedge opportunity (lock) | −20¢ |
| No hedge, Lakers lose | −80¢ |

```text
EV_hedge = (N_win_unhedged × 20 + N_lock × (20−H) + N_miss × (−80)) / N
```

---

## 7. Test results vs 80→40

Frozen universes: **NBA 1,230** FIRST-80 entries, **NCAAB 4,099**.
Close path. Wick path is worse and is not the working rule.

### V1 — H = 40 close proxy vs 80→40 Model A

| | NBA | NCAAB |
|---|---:|---:|
| n | 1,230 | 4,099 |
| 80→40 survivors / stops / leaks | 910 / 320 / 0 | 2,998 / 1,099 / 2 |
| **80→40 EV / contract** | **+4.39¢** | **+3.90¢** |
| Hedge locks (opp close ≥ 40) | 456 (37.07%) | 1,546 (37.72%) |
| No hedge, win | 774 | 2,552 |
| No hedge, lose (miss) | 0 | 1 |
| False hedges (lock, Lakers still won) | 245 / 456 (53.7%) | 842 / 1,546 (54.5%) |
| **Hedge EV / contract** | **+5.17¢** | **+4.89¢** |
| Hedge − 80→40 | **+0.78¢** | **+0.99¢** |
| Hold-to-settlement EV | +2.85¢ | +2.80¢ |

NBA identity (cents, 1,230 trades):

```text
hold     = 1,019×(+20) + 211×(−80)           = +3,500    → +2.85¢
80/40    =   910×(+20) + 320×(−40)           = +5,400    → +4.39¢
hedge    =   774×(+20) + 456×(−20) + 0×(−80) = +6,360    → +5.17¢
```

NCAAB identity (cents, 4,099 trades):

```text
hold     = 3,394×(+20) + 705×(−80)           = +11,480   → +2.80¢
80/40    = 2,998×(+20) + 1,099×(−40) + 2×(0) = +16,000   → +3.90¢
hedge    = 2,552×(+20) + 1,546×(−20) + 1×(−80)= +20,040  → +4.89¢
```

Why hedge beats 80→40 **per contract** on this proxy (NCAAB):

| Effect | n | Δ vs 80→40 | Total ¢ |
|---|---:|---|---:|
| Overlap stops: −40 → −20 | 1,096 | +20 each | +21,920 |
| Extra hedges on winners: +20 → −20 | 449 | −40 each | −17,960 |
| Other leak / miss residuals | | | +80 |
| **Net** | | | **+4,040** |

NBA analog: 320 overlap stops (+20 each) minus 136 extra winner hedges
(−40 each) ≈ **+960¢** on the book (**+0.78¢** / contract).

Almost every eventual loser printed opponent-40 first (NBA miss 0;
NCAAB miss 1). The cost is the false hedges — including 136 NBA / 450
NCAAB locks that **never even printed favorite-40**.

### Same numbers on the 7-contract Lakers book (per-contract EV × 7)

This ignores the extra cash needed to fund the Bulls bid.

| Book | NBA $ / trade | NCAAB $ / trade |
|---|---:|---:|
| Hold | +$0.20 | +$0.20 |
| 80→40 | **+$0.31** | **+$0.27** |
| Hedge H=40 close proxy | **+$0.36** | **+$0.34** |

### V1 wick path (do not use)

| | NBA | NCAAB |
|---|---:|---:|
| Hedge EV | +3.87¢ | +3.76¢ |
| vs 80→40 | worse | worse |

### Capital can reverse the ranking

If both legs must be reserved up front on a $6.25 game budget:

```text
80→40 book    7 × 80¢  = $5.60   →  NBA 7 × 4.39¢ = +30.7¢
hedge H=40    5 × 120¢ = $6.00   →  NBA 5 × 5.17¢ = +25.9¢
```

On **reserved** capital, 80→40 still makes more money per game at H=40
on both sports. If the 40¢ bid is funded only when it fills, 7-contract
sizing can stay — but fade days need spare cash, and live Risk cannot
book a second market today.

---

## 8. V2 — hedge price frontier vs 80→40

Locked P&L remains `20 − H`. H* chosen on **VALIDATION candle EV /
reserved capital only**, then OOS once. Not a fill-aware optimum.

| Strategy | NBA EV ¢ | NBA EV/reserved | NCAAB EV ¢ | NCAAB EV/reserved |
|---|---:|---:|---:|---:|
| Hold | 2.85 | 0.036 | 2.80 | 0.035 |
| **80→40** | **4.39** | **0.055** | **3.90** | **0.049** |
| Hedge H=40 | 5.17 | 0.043 | 4.89 | 0.041 |
| Hedge H=28 (NBA H*) | 5.04 | 0.047 | 5.16 | 0.048 |
| Hedge H=20 (NCAAB H*) | 4.57 | 0.046 | **5.51** | **0.055** |

NBA VAL picked **H\* = 28**. NCAAB VAL picked **H\* = 20** (grid floor).
NCAAB OOS n = 84 is too small to overweight.

$50 path sim (Architecture A, reserve 80+H at entry):

| Book | NBA terminal | NCAAB terminal |
|---|---:|---:|
| Hold | 29,500¢ | 84,940¢ |
| **80→40** | **42,800¢** | 116,020¢ |
| H=40 reserved | 36,800¢ | 104,700¢ |
| H* reserved | 36,020¢ (H=28) | **140,240¢ (H=20)** |

NBA: 5 contracts at 108¢ lose to 7 contracts at 80¢ on the stop book.
NCAAB H=20: lock is 0¢, unit 100¢ → 6 contracts, and this **candle**
dollar path beats 80→40. Still not a fill.

---

## 9. V3 — the same EVs if the bid only sometimes fills

`p_fill` is a **scenario**, not an estimate.

```text
EV(p) = EV_hold  +  p × mean( I_opportunity × (lock − hold) )
```

At H=40, `EV(p=1)` is the V1 number. `EV(p=0)` is hold-to-settlement.

| Sport | H | Hold EV | 80→40 EV | EV(p=0.5) | EV(p=1) | Assumed p to beat 80→40 |
|---|---:|---:|---:|---:|---:|---:|
| NBA | 40 | 2.85 | **4.39** | 4.01 | **5.17** | **66.4%** |
| NBA | 28 | 2.85 | 4.39 | 3.94 | 5.04 | 70.3% |
| NCAAB | 40 | 2.80 | **3.90** | 3.84 | **4.89** | **52.8%** |
| NCAAB | 20 | 2.80 | 3.90 | 4.16 | 5.51 | 40.7% |

If only CLASS A (multi-minute persist at H) fills, the H=40 bar is
**54.9% NBA / 55.5% NCAAB**. Median persist after first close touch at
H=40 is **4 minutes**; about **47%** persist ≥ 5 minutes.

Those thresholds are “how often would the resting Bulls bid have to
fill, among candle opportunities, for the hedge book to beat Model A
80→40.” They are not measured fill rates.

---

## 10. What a Lakers–Bulls tape would need to show

After Lakers 80 fills:

```text
STATE 1  Lakers YES long @ 80
STATE 2  Bulls YES bid resting @ H
STATE 3a never fills     → Path A matrix
STATE 3b full fill       → locked 20−H
STATE 3c partial fill    → mixed inventory (not in V1–V3)
```

The historical tests stop at “did opponent close later print ≥ H?”
They do not observe queue position, depth, or whether Momento’s order
would have been the one that traded.

---

## Sources

- V1: `docs/research/ncaab/FIRST80_OPPONENT_40_HEDGE_V1.md`
- V2: `docs/research/FIRST80_OPPONENT_HEDGE_FRONTIER_V2.md`
- V3: `docs/research/FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3.md`
- 80→40 Model A: `docs/research/ncaab/FIRST80_LIQUIDATION_MODEL_V1.md`
