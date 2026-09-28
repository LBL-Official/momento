# 80 → Dynamic Exit Corridor

```text
RESEARCH ADDENDUM / THESIS REVISION
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE HEDGE
DOES NOT START W9
DOES NOT CREATE AN 18TH SYSTEM
CANDLE PATH                     ≠ FILL
UNIVERSE                        = DERIVED FOUR  N=936
                                ≠ ASKED-SIX     N=1182
80/25–80/50                     = SAME N=936
80/55                           = ENTRY <86 ONLY  N=905  NOT APPLES-TO-APPLES
BARRIER GRID BELOW              = DESK-STATED CANDLE-PATH LEDGER
                                 NOT A FILL TAPE
                                 NOT A LIVE RULE
```

Desk: `BDR # MOMENTO SYSTEMS`  
Route: `http://127.0.0.1:5190/#/bdr/liquidation-corridor`  
Owner system: `hedging_analysis`

This revises the earlier 35-vs-40 comparison. It does not replace the program or the dual-leg engineer brief. Follow-on entry ridge: `docs/research/BDR_77_RIDGE.md`. Staged acquisition / manifold: `docs/research/BDR_STAGED_ACQUISITION.md`. The historical research object can stay labeled 80/40. The production execution concept is **80 → Dynamic Exit Corridor**.

---

This is **DERIVED FOUR, not ASKED-SIX**, with **936 settled FIRST80 trigger events**. Terminal win rate is **786/936 = 83.97%**. The 80/40 survival object is **700/936 = 74.79%**. 80/25 through 80/50 are measured on the same N=936 universe. **80/55 is not directly apples-to-apples** because it uses the entry `< 86` book and only N=905.

The striking result is that the stop surface is basically an **EV plateau**:

| Barrier | EV / trade | Survivors |
| ---: | ---: | ---: |
| 25 | +4.7756¢ | 746 |
| 30 | **+5.0427¢** | 736 |
| 35 | **+5.0694¢** | 721 |
| 40 | +4.8718¢ | 700 |
| 45 | **+4.9573¢** | 680 |
| 50 | +4.7222¢ | 650 |
| 55* | +3.7901¢ | 579/905 |

The maximum is 35¢ at +5.0694¢, but look at how little theoretical EV separates the economically interesting region. Relative to 35¢:

| Barrier | Δ vs 35 |
| ---: | ---: |
| 30 | −0.0267¢ |
| 45 | −0.1121¢ |
| 40 | −0.1976¢ |
| 25 | −0.2938¢ |
| 50 | −0.3472¢ |

That is the major finding.

These integers are desk-stated candle-path ledger EV on the locked derived four. They are not fills. Ledger EV ≠ fill ≠ live EV.

---

## There is no meaningful “40¢ stop”

At least from this candle-path study, **40 is not special**.

The system appears to have a broad region where two forces offset each other:

```text
lower stop  ⇒  more positions recover
lower stop  ⇒  larger loss when they do not recover
```

Those two effects nearly cancel over a huge range.

That is why EV does this:

```text
4.78,  5.04,  5.07,  4.87,  4.96,  4.72
```

instead of collapsing as the stop moves.

So the live problem is no longer:

> “How do we make sure we get out at 40?”

It is:

> **How do we exploit the wide 30–45¢ liquidation-EV plateau to obtain the highest-quality real execution possible?**

That is a much better problem for an algorithmic execution engine.

---

## This gives Momento Live enormous freedom

Suppose exact 40 liquidation costs you taker fees, crossing spread, queue loss, adverse selection, and 5–10¢ of gap/slippage on fast deterioration.

Why sacrifice all of that to preserve **0.1976¢ of candle-path theoretical EV** versus the 35 barrier?

You should not.

Likewise, you do not necessarily need to panic at 45. The theoretical penalty from 35 to 45 is only **0.1121¢ per trade**.

So the live engine can choose execution based on the actual book.

At one moment maybe 45 is available cleanly as maker liquidity. Take the excellent execution.

Another time there is no clean exit at 45, but you can work the opponent leg and neutralize around an equivalent 41–42.

Another time both books are ugly and the system can afford to let the position travel through 40 toward 35 while continuing to work liquidity.

That becomes the advantage:

```text
price flexibility  →  execution flexibility
```

---

## Three regions — execution regimes, not hard stops

```text
80
│
│ HOLD / NORMAL POSITION MANAGEMENT
│
55
│
│ PREPARE / OBSERVE LIQUIDITY
│ Start tracking both liquidation routes aggressively
│ Potentially stage passive orders
│
50
│
├──────── OPTIMAL EXECUTION REGION ────────┐
│                                          │
45                                         │
│                                          │
40      NO SPECIAL MAGIC HERE              │
│                                          │
35                                         │
│                                          │
30                                         │
├──────────────────────────────────────────┘
│
│ URGENCY BECOMES DOMINANT
│
25
│
│ TAIL / EMERGENCY MANAGEMENT
│
0
```

Treat **30–45 as the core working region** initially.

Not because 25 is unprofitable — it is not. But once residual exposure travels toward 25, the cost of a failed execution event becomes increasingly large. The research question becomes whether whatever extra recovery optionality you get is worth the live tail-execution risk.

That needs actual book/fill data. `P(P_fill | quote state)` remains **NOT_RUN**.

Twenty can remain a catastrophe / fail-safe. It is not the ordinary emergency. The ordinary system should try to have **zero meaningful residual delta left by the bottom of the 30–45 zone**.

---

## The optimizer should NOT maximize exit price

Momento Live should optimize **Expected Net Liquidation Value**, not the highest possible stop price.

```text
J(a_t)
=
E[final strategy P&L | a_t]
− E[fees]
− E[slippage]
− λ E[uncompleted exposure]
```

The action `a_t` can be:

```text
do nothing
rest Bulls sell
improve Bulls sell
cross Bulls

rest opponent buy
improve opponent buy
cross opponent

cancel
replace
partially hedge
finish hedge
```

Now the execution engine has genuine optionality.

### Example

Long Bulls from 80. Bulls hits 43.

```text
BULLS     40 bid / 44 ask
LAKERS    55 bid / 57 ask

direct     sell Bulls ≈ 40
synthetic  buy Lakers 57  →  100 − 57 = 43
```

The hedge route is better.

Ten seconds later:

```text
BULLS     41 bid
LAKERS    61 ask

direct     41
synthetic  100 − 61 = 39
```

Sell Bulls.

**The system should not have a religious attachment to either leg.**

It owns one economic risk and has two ways of extinguishing it.

Complement is measured, not assumed. A printed bid is not a fill. Missing L2 is `SOURCE_UNAVAILABLE`.

---

## Recovery counts explain why patience has value

```text
50 → 650
45 → 680   +30 recovered
40 → 700   +20
35 → 721   +21
30 → 736   +15
25 → 746   +10
```

Every extra 5¢ of room rescues additional positions.

The marginal recovery benefit is diminishing.

That is exactly the structure an execution controller should exploit.

```text
45:   maker-first, preserve queue, seek favorable hedge
35:   completion probability matters much more
30/25: consuming the final portion of the empirical EV plateau
```

Aggression should rise continuously as the remaining **EV budget** disappears.

---

## The metric to give the live engine

Define `EV*(b)` as measured candle-path EV at barrier `b`.

The maximum observed here is:

```text
EV*_max = 5.0694¢
```

Then an **execution budget**:

```text
B(b) = EV*_max − EV*(b)
```

Approximately:

```text
35 → 0.0000¢ budget consumed
30 → 0.0267¢
45 → 0.1121¢
40 → 0.1976¢
25 → 0.2938¢
50 → 0.3472¢
```

That is astonishingly small.

Meaning Momento can potentially spend a few tenths of a cent of **theoretical barrier-selection EV** to gain multiple cents of **actual execution quality**.

That is the trade the execution system should make.

This budget is a candle-path identity on N=936. It is not a live P&L forecast. Fees, slippage, and gap risk are not in `EV*(b)`.

---

## Head-quant conclusion

> **DERIVED FOUR does not identify a point-optimal 40¢ liquidation rule. It identifies a broad and unusually flat liquidation-EV surface. Across 25–50¢, theoretical candle-path EV varies by only about 0.35¢ per trade around the 35¢ maximum, despite materially different survival counts. The production opportunity is therefore not precise barrier selection. It is execution optimization within an economically forgiving corridor. Momento Live should use the corridor as an execution budget: work passive liquidity early, dynamically route between direct liquidation and the complementary contract, escalate according to completion risk rather than a fixed price trigger, and consume the remaining barrier-EV budget only when doing so improves expected realized execution.**

That is a significantly better system than **80→40**.

Stop calling the live strategy “80/40.”

The research object can remain 80/40 historically. The production execution concept is:

**80 → Dynamic Exit Corridor.**

It does not arm live trading. It does not change 80/81/83/89. It does not invent a 40 fill. Overhedge remains forbidden. Strategy still proposes. Risk still approves. Execution still executes.
