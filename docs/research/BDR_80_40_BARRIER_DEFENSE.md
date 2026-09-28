# 80→40 BARRIER DEFENSE & SYNTHETIC EXIT PROGRAM

```text
RESEARCH PROGRAM / DESIGN CONTRACT
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE HEDGE
DOES NOT START W9
DOES NOT CREATE AN 18TH SYSTEM
BDR IS THE HEDGING ANALYSIS FRONTEND ON :5190
CANDLE PATH                     ≠ FILL
PRICE EVENT                     ≠ EXECUTABLE ORDER
L2 / QUEUE / DEPTH              = UNOBSERVED HISTORICALLY
STRATEGY PROPOSES → RISK APPROVES → EXECUTION EXECUTES
OVERHEDGE                       = FORBIDDEN
```

Desk: `BDR # MOMENTO SYSTEMS`  
Route: `http://127.0.0.1:5190/#/bdr`  
Owner system: `hedging_analysis` (not a new top-level system)  
Companion engineer brief: `docs/research/DUAL_LEG_MAKER_LOCK_POSITION_MANAGEMENT.md`

---

## Head Quant Problem Definition

The current 80→40 strategy has an execution asymmetry.

The strategy earns only approximately 20¢ of gross upside per winning contract purchased at 80¢, while a nominal stop at 40¢ assumes that a deteriorating position can actually be liquidated at or near 40¢.

That assumption is structurally dangerous.

A 40¢ stop is presently better understood as a **trigger condition**, not an executable price guarantee. Once the market begins moving violently against the position, waiting until the original contract reaches 40¢ forces the desk to compete for liquidity exactly when liquidity is most valuable, adverse selection is highest, and the probability of crossing below the intended stop is greatest.

The execution problem is therefore:

> **Can Momento transfer or neutralize the position's directional exposure before the original contract reaches the 40¢ barrier, using the opposing contract as a synthetic exit route, while minimizing fees, slippage, adverse selection, and false hedging?**

This is not primarily an alpha-prediction problem.

It is a **dynamic position-management and optimal-execution problem**.

---

# 1. THE ECONOMIC IDENTITY

Assume:

```text
Long 100 Bulls YES @ 80¢
```

The traditional stop says:

```text
If Bulls falls to 40¢:
sell Bulls.
```

If that sale actually occurs at 40¢:

```text
PnL = 40 - 80
    = -40¢ per contract
```

But Bulls and Lakers are opposing outcomes of the same mutually exclusive game.

Instead of selling Bulls, Momento can buy Lakers.

If we own equal quantities of Bulls YES and Lakers YES, exactly one leg settles at $1.

Therefore, if the Lakers hedge is purchased at price H:

```text
Total cost = 80 + H

Settlement value = 100

Locked PnL = 100 - 80 - H
           = 20 - H
```

This identity is already established in the existing hedge research.

The crucial implication is:

```text
Lakers @ 44  → locked loss = -24¢
Lakers @ 50  → locked loss = -30¢
Lakers @ 55  → locked loss = -35¢
Lakers @ 60  → locked loss = -40¢
```

Therefore:

> **Buying Lakers at 60¢ is economically equivalent, before execution costs, to successfully selling Bulls at 40¢.**

Even more importantly:

> **Any completed Lakers hedge below 60¢ gives Momento a better economic outcome than a perfect Bulls exit at 40¢.**

This gives the execution desk an entirely different way to think about the stop.

The target is no longer:

```text
SELL BULLS AT 40
```

The target becomes:

```text
OBTAIN AN ALL-IN SYNTHETIC EXIT
EQUIVALENT TO ≥40¢ BULLS
BEFORE THE MARKET FORCES US THROUGH 40.
```

Define:

```text
Synthetic Bulls Exit = 100 - Lakers Hedge Price
```

Thus:

```text
Lakers @ 44 → synthetic Bulls exit @ 56
Lakers @ 50 → synthetic Bulls exit @ 50
Lakers @ 55 → synthetic Bulls exit @ 45
Lakers @ 60 → synthetic Bulls exit @ 40
```

This is the core of the entire study.

---

# 2. WHY THE CURRENT 80→40 CONSTRUCTION IS FRAGILE

The strategy currently concentrates execution urgency at the worst possible moment.

The bot can behave passively when the trade is healthy, but once Bulls reaches 40 the position suddenly changes from:

```text
hold
```

to:

```text
must liquidate
```

That creates two separate sources of EV destruction.

### Fee asymmetry

The 80¢ entry can often be worked as maker liquidity.

The distressed exit is much more likely to require aggressive liquidity.

The strategy therefore systematically:

```text
earns passively
but exits aggressively.
```

That is an unfavorable microstructure profile.

### Gap and slippage asymmetry

More importantly, 40¢ does not imply that 40¢ is available.

The market may travel:

```text
46
44
41
37
31
```

faster than the execution engine can obtain meaningful size.

The existing research explicitly concluded that candle data cannot reconstruct queue position or IOC slippage, and that the empirical object ultimately required is the actual distribution:

```text
P(P_fill | 80→40 liquidation)
```

rather than an assumed 40¢ fill.

So Momento should stop thinking about the 40 level as the beginning of execution.

**40 should be the point by which execution should ideally already be substantially complete.**

---

# 3. THE PROPOSED SYSTEM: BARRIER DEFENSE ROUTER

The live component should be treated as its own execution subsystem:

```text
BARRIER DEFENSE ROUTER
```

or BDR.

BDR does not decide whether FIRST80 was a good entry.

BDR receives an already-open position and asks:

> What is the cheapest and safest way to remove its unwanted downside exposure from this point forward?

For every position, BDR continuously maintains two executable routes:

```text
ROUTE A — DIRECT EXIT
Sell Bulls YES

ROUTE B — SYNTHETIC EXIT
Buy Lakers YES
```

Those routes are economically interchangeable methods of reducing the same event exposure, but their liquidity, fees, spreads, depth, and fill probabilities can be very different.

Momento should continuously route toward whichever path offers the superior **all-in risk-adjusted liquidation economics**.

---

# 4. INITIAL HIGH-LEVEL POLICY

For the first research version, assume:

```text
ENTRY
Bulls YES @ 80
```

No hedge is needed while the position remains healthy.

Once Bulls deteriorates into a predefined defense region—for example:

```text
Bulls ≈ 55
```

BDR becomes active.

At approximately Bulls 55, Lakers should be trading around the complementary region. Instead of waiting for Bulls 40, the engine begins working passive Lakers liquidity.

Illustratively:

```text
Bulls deteriorates to ~55
        ↓
BDR ARMED
        ↓
rest Lakers maker bid around 44
        ↓
observe fills + book evolution
        ↓
progressively increase urgency
as Bulls continues deteriorating
        ↓
FULL HEDGE
or
DIRECT LIQUIDATION
```

The exact 55¢ activation threshold and the exact 44¢ initial bid are **candidate research parameters**, not values that should simply be hard-coded because they sound reasonable.

But the economic principle is sound:

> begin competing for exit liquidity while time and optionality still exist.

---

# 5. THE EXECUTION WATERFALL

The production implementation should behave as an explicit state machine.

| State         | Meaning                                                   | Primary behavior                  |
| ------------- | --------------------------------------------------------- | --------------------------------- |
| HEALTHY       | Original position materially above defense region         | No hedge orders                   |
| ARMED         | Position enters deterioration region                      | Begin evaluating synthetic route  |
| PASSIVE_HEDGE | Synthetic exit economically superior                      | Rest maker order on opponent      |
| ESCALATING    | Original price continues deteriorating                    | Increase hedge urgency            |
| PARTIAL_HEDGE | Opponent fills received                                   | Manage only residual exposure     |
| FULLY_HEDGED  | Opponent quantity equals remaining original quantity      | Position economically neutral     |
| DIRECT_EXIT   | Hedge route no longer attractive or sufficiently reliable | Sell original leg                 |
| EMERGENCY     | Hard downside boundary reached                            | Immediately flatten residual risk |
| RECONCILE     | Exchange/order state uncertain                            | No new risk until state recovered |
| TERMINAL      | Position completely hedged, exited, or settled            | Cancel every remaining order      |

The execution engine must never reason simply:

```text
price < X → send order
```

It must reason:

```text
current exposure
+
both books
+
outstanding orders
+
partial fills
+
execution costs
+
remaining time
+
market velocity
+
risk boundary
→
next optimal execution action
```

---

# 6. THE CRITICAL ROUTING CALCULATION

At every valid book update, BDR should compute:

```text
DIRECT_EXIT_VALUE
```

from the executable Bulls book.

And:

```text
SYNTHETIC_EXIT_VALUE
```

from the executable Lakers book.

For a Lakers hedge price H:

```text
synthetic Bulls exit = 100 - H
```

The system then adjusts both routes for:

```text
fees
expected slippage
available depth
fill probability
queue uncertainty
partial-fill risk
adverse-selection risk
```

Conceptually:

```text
Net Direct Exit
=
Bulls executable sale
- direct execution costs
```

versus:

```text
Net Synthetic Exit
=
100
- Lakers executable acquisition cost
- hedge execution costs
```

The router should not care which leg performs the flattening.

It should care about:

```text
best attainable economic liquidation.
```

That is how an institutional execution system should view the problem.

---

# 7. THE 60¢ OPPONENT BOUNDARY

For an 80¢ original entry:

```text
Opponent hedge @ 60
```

creates:

```text
80 + 60 = 140 total cost

100 settlement

-40 locked loss
```

Therefore the opponent 60 level is an economically meaningful barrier.

It represents the synthetic equivalent of the idealized 40¢ stop.

This gives us a natural execution budget:

```text
HEDGE < 60
    superior to perfect direct 40 exit before fees

HEDGE = 60
    equivalent to direct 40 exit before fees

HEDGE > 60
    worse than direct 40 exit before fees
```

Fees and execution costs shift the exact break-even level slightly, so the production router must compare **all-in economics**, not raw cents.

---

# 8. URGENCY MUST BE CONTINUOUS

A major mistake would be replacing one binary stop with another.

We do not want:

```text
Bulls >55 → nothing
Bulls <=55 → bid Lakers 44 forever
Bulls <=20 → panic
```

The aggression level should evolve continuously.

The BDR urgency function should respond to variables such as:

```text
distance from 40
distance from emergency boundary
recent price velocity
spread width
opponent depth
original-leg depth
partial hedge completion %
order age
queue position proxy
book imbalance
time remaining in game
number of rapid price-level transitions
```

As deterioration accelerates:

```text
PASSIVE
→ JOIN
→ IMPROVE
→ CROSS
→ DIRECT FLATTEN
```

The closer the position gets to irreversible loss territory, the less value there is in preserving maker economics at the expense of completion probability.

---

# 9. THE 20¢ HARD BOUNDARY

The proposed Bulls 20¢ level makes sense as an initial **catastrophic-risk boundary**.

Its purpose is not alpha.

Its purpose is to say:

> Momento has exhausted the opportunity to economically transfer this exposure. Stop optimizing execution quality and eliminate the residual directional risk.

Thus:

```text
Bulls <= 20
AND residual directional exposure > 0
```

should cause the system to abandon passive hedging and enter emergency liquidation.

But the production implementation should not send a completely unbounded market order.

The institutional implementation is:

```text
cancel stale opponent orders
↓
reconcile fills
↓
calculate exact residual Bulls quantity
↓
send aggressive marketable limit / immediate execution instruction
with explicit worst-price protection
↓
repeat until flat or venue prevents execution
```

The 20¢ threshold itself should ultimately be validated by the study.

It is the initial proposed kill boundary, not yet an empirically optimized one.

---

# 10. PARTIAL FILLS ARE THE REAL PROBLEM

Suppose Momento owns:

```text
100 Bulls
```

and the Lakers hedge fills:

```text
37 Lakers
```

The position is not hedged.

It is:

```text
37 paired contracts
63 directional Bulls contracts
```

BDR therefore needs an exact invariant:

```text
residual_delta_contracts
=
original_open_contracts
- opposing_hedge_filled_contracts
```

Every decision must operate on the residual quantity.

The bot must never assume an order is filled merely because it was accepted.

It must never hedge the original requested quantity twice after cancel/replace races.

It must never overhedge.

It must survive:

```text
partial fills
cancel/replace
late fills after cancel request
duplicate WebSocket messages
disconnect/reconnect
out-of-order acknowledgments
exchange rejection
stale order state
stale market data
position reconciliation
process restart
game settlement during execution
```

This is where "elite execution" actually lives.

Not in a clever threshold.

In state correctness.

---

# 11. ORDER MANAGEMENT STANDARD

Every order must have deterministic identity and be attributable to:

```text
position_id
defense_cycle_id
leg
intent
revision
quantity
limit
creation_time
book_sequence
```

The system must distinguish:

```text
DESIRED POSITION
ACTUAL POSITION
WORKING ORDERS
POSSIBLE LATE FILLS
```

These are not the same object.

The central safety invariant should be:

```text
actual hedge fills
+
maximum possible fills from live orders
<=
original directional exposure
```

unless an explicit overhedging strategy has separately been authorized.

For this program:

```text
OVERHEDGE = FORBIDDEN.
```

---

# 12. CANCEL/REPLACE SHOULD NOT BE NAIVE

Constantly moving the Lakers order destroys queue priority.

Never moving it leaves the order stale.

Therefore BDR needs hysteresis.

An order should be replaced only when the expected improvement from repricing exceeds the cost of abandoning queue position.

Conceptually:

```text
REPRICE BENEFIT
>
QUEUE LOSS
+
ADVERSE-SELECTION COST
+
MESSAGE / EXECUTION RISK
```

That tradeoff must become a measured quantity from prospective order data.

A state-of-the-art system should therefore track:

```text
order resting time
price level
book size ahead if observable
fills received
market movement after placement
market movement after fill
```

and learn empirical fill probabilities by order state.

---

# 13. FALSE HEDGES MUST BE MEASURED

There is a cost to hedging too early.

Suppose Bulls falls from:

```text
80 → 55
```

Momento buys Lakers at 44 and locks:

```text
-24¢
```

but Bulls subsequently recovers and wins.

The hedge saved tail risk but destroyed a winning +20¢ position.

That is a **false hedge cost**.

Therefore the study cannot optimize only:

```text
losses avoided.
```

It must simultaneously measure:

```text
losses avoided
versus
winning PnL sacrificed.
```

The optimal policy will sit between:

```text
hedge everything immediately
```

and:

```text
wait until 40 and pray for liquidity.
```

---

# 14. THIS SHOULD BEGIN AS AN EXECUTION STUDY, NOT A MACHINE-LEARNING PROJECT

The first version should be deterministic, observable, and economically interpretable.

Do not start with reinforcement learning.

Do not let a black box decide when to liquidate.

First build the empirical execution surface.

The policy family should contain understandable candidate parameters:

```text
defense activation price
initial opponent bid
quote offset
minimum dwell time
reprice threshold
aggression schedule
partial-fill escalation
synthetic/direct routing threshold
hard direct-exit boundary
maximum tolerated locked loss
```

Then test those policies prospectively.

Only once Momento has a reliable execution dataset should statistical learning be permitted to optimize urgency or routing.

---

# 15. THE RESEARCH PROGRAM

## Stage I — Historical Path Geometry

Use existing basketball and MLB price paths to reconstruct:

```text
80 entry
→ 70
→ 60
→ 55
→ 50
→ 45
→ 40
→ below 40
```

For every eventual stop, reconstruct both legs wherever available.

At every observation calculate:

```text
original price
opponent price
synthetic exit equivalent
paired cost
locked PnL
time until 40
time until terminal
subsequent recovery
```

Historical candles can identify opportunity geometry.

They cannot prove maker fills.

That distinction is non-negotiable.

Existing Momento hedge research already reached the same conclusion: resting opponent liquidity is a candidate execution improvement, but the actual fill experiment has not been run.

---

# 16. STAGE II — LIVE SHADOW EXECUTION

Before changing actual risk, the live engine should run BDR in:

```text
SHADOW
```

for every eligible trade.

It watches both books and calculates exactly what it *would* do without submitting the hedge.

Capture every state transition and hypothetical order.

Critically, preserve high-resolution live book information unavailable from historical one-minute candles.

This gives Momento the first real dataset for:

```text
When would we have armed?

Where would we have quoted?

Would the quote have been marketable?

How long did that price remain available?

What happened immediately afterward?

How much time existed before 40?

What direct exit was available simultaneously?
```

---

# 17. STAGE III — PROSPECTIVE EXECUTION EXPERIMENT

Then conduct a deliberately bounded live experiment.

The purpose is to measure:

```text
P(fill | quote state)
```

and:

```text
E(fill price | quote state)
```

for the opposing-leg hedge.

For every order record:

```text
decision timestamp
exchange submission timestamp
ack timestamp
first fill timestamp
final fill timestamp
cancel timestamp
requested quantity
filled quantity
price
fees
market before placement
market after placement
original-contract market
opponent-contract market
remaining exposure
```

The existing 80→40 research correctly identified this missing object as the key empirical requirement.

This stage is **NOT_RUN**. It does not authorize Create V2, change FIRST01, or set `ENABLE_LIVE_TRADING`.

---

# 18. PRIMARY COMPARISON

Every stopped trade should be replayed under multiple execution books.

| Policy         | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| BASELINE       | Existing direct 40-trigger liquidation                            |
| EARLY DIRECT   | Sell original position earlier                                    |
| STATIC HEDGE   | Start fixed opponent bid at defense threshold                     |
| ADAPTIVE HEDGE | Escalating opponent execution                                     |
| BDR            | Dynamic best-route execution                                      |
| ORACLE         | Best achievable route with hindsight, used only as an upper bound |

The purpose is not to find the prettiest backtest.

The purpose is to answer:

> How much of the theoretical 80→40 edge can Momento actually retain after real execution?

---

# 19. PRIMARY METRICS

The headline statistic should not simply be win rate.

BDR should report:

```text
mean realized loss on stop trades
median realized loss
P(loss <= 40¢)
P(loss > 40¢)
P(loss > 45¢)
P(loss > 50¢)
worst realized loss

mean synthetic-equivalent exit
mean direct exit
mean locked loss after hedge

maker %
taker %
fee cost
slippage
partial-fill rate
hedge completion rate

time from BDR activation to completion
time remaining before 40
time remaining before 20

false-hedge rate
winning PnL sacrificed
loss PnL saved

overhedge incidents
stale-order incidents
duplicate-order incidents
unreconciled-position incidents
```

For production readiness:

```text
OVERHEDGE INCIDENTS = 0
UNKNOWN POSITION STATE = FAIL CLOSED
STALE BOOK EXECUTION = 0
UNATTRIBUTED FILLS = 0
```

---

# 20. THE REAL OBJECTIVE FUNCTION

The execution engine should ultimately minimize:

```text
Expected Economic Exit Cost
=
realized loss
+ fees
+ slippage
+ adverse selection
+ residual tail-risk penalty
+ false-hedge opportunity cost
```

subject to:

```text
position integrity
max exposure
hard-loss constraints
order correctness
```

This matters because the cheapest-looking order is not necessarily the best order.

A 44¢ Lakers maker bid that almost never fills before Bulls crashes through 40 may be economically inferior to paying 47¢ and reliably completing the hedge.

Execution quality is:

```text
price × probability of completion × timing
```

not price alone.

---

# 21. MOMENTO-LIVE ARCHITECTURE

This should not become another strategy implementation.

The existing authority chain should remain:

```text
Strategy
   ↓
Position exists
   ↓
Risk / Position Manager
   ↓
Barrier Defense Router
   ↓
Order Management
   ↓
Venue Adapter
   ↓
Kalshi
```

BDR belongs to **position management / execution**, not entry research.

Its input is:

```text
we already own Bulls.
```

Its output is:

```text
how should this exposure now be managed?
```

The strategy should not micromanage quote replacement.

The execution layer should.

BDR does not submit. Strategy does not submit. Risk still approves every new exposure, including a complementary B leg. `DuplicateGamePosition` must be replaced by an explicit complementary-pair rule before any paper B order is legal. That Risk RFC is not this frontend.

---

# 22. OBSERVABILITY IS PART OF THE STRATEGY

The current production record cannot yet cleanly answer:

```text
Which entry belongs to which exit?
What was the true stop trigger?
What was the actual VWAP exit?
What fees were paid?
How much slippage occurred?
What position remained after each partial?
```

The current Vital contract is explicitly fill-oriented: logical trades remain `OBSERVATION_UNAVAILABLE`, `trades.jsonl` is absent, and the UI displays individual fill rows rather than reconstructed closed trades.

That is unacceptable for this study.

Every BDR position must generate one auditable execution object:

```text
position_id
entry fills
defense activation
all hedge orders
all direct-exit orders
all partial fills
fees
final paired quantity
residual liquidation
settlement
gross PnL
net PnL
counterfactual baseline PnL
execution improvement
```

Without that ledger, Momento cannot distinguish:

```text
bad strategy
from
bad execution
from
bad observability.
```

---

# 23. NON-NEGOTIABLE PRODUCTION INVARIANTS

The production code must guarantee:

```text
1. Never hedge more contracts than the remaining directional position.

2. Never submit based on stale books.

3. Never assume cancel acknowledgement means no late fill occurred.

4. Never count an accepted order as a fill.

5. Never allow both the direct-exit router and hedge router
   to independently flatten the full position.

6. Reconcile actual exchange position before resuming after restart.

7. Every execution decision must be reproducible from logged state.

8. Emergency liquidation outranks fee optimization.

9. A disconnected or uncertain state fails closed.

10. The execution layer may improve an exit;
    it may not silently create new directional risk.
```

---

# 24. THE CENTRAL QUANT THESIS

The existing 80→40 architecture treats liquidation as a single-market problem:

```text
Long Bulls
→ Bulls deteriorates
→ sell Bulls
```

That is too narrow.

For a mutually exclusive binary event, Momento actually owns access to two economically related liquidity pools:

```text
SELL BULLS
or
BUY LAKERS
```

The desk should treat them as competing liquidation venues for the same risk.

The optimal execution engine therefore does not wait until the position reaches its stop.

It begins working the cheapest route to neutrality while there is still time, liquidity, and optionality.

The institutional version of the 80→40 strategy should therefore become:

```text
ENTER @ 80

        ↓

HOLD WHILE HEALTHY

        ↓

DEFENSE REGION

        ↓

CONTINUOUSLY COMPARE:

DIRECT EXIT
vs
SYNTHETIC OPPONENT HEDGE

        ↓

PASSIVE MAKER FIRST

        ↓

ESCALATE AS LOSS HAZARD RISES

        ↓

COMPLETE FULL HEDGE
OR
FLATTEN RESIDUAL ORIGINAL POSITION

        ↓

HARD EMERGENCY BOUNDARY

        ↓

RISK REMOVAL OVERRIDES EXECUTION OPTIMIZATION
```

That is the shift.

**40¢ should cease being the moment when Momento begins trying to escape.**

It should become the loss level that the execution system was designed, in advance, to defend.

---

## What this document does not do

- Does not change live FIRST01 / 80 / 81 / 83 / 89.
- Does not start W9.
- Does not arm NBA 2026-27 or add a second ticker to `book.json`.
- Does not invent L2, mids, or a 40 that gapped.
- Does not promote A1 / hybrid / Katy candle numbers to fill rates.
- Does not create an 18th Momento system.
