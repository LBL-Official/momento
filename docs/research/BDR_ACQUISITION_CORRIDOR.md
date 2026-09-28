# 75 → Acquisition Corridor

```text
RESEARCH ADDENDUM / THESIS
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE ENTRY
DOES NOT START W9
DOES NOT CREATE AN 18TH SYSTEM
CANDLE PATH                     ≠ FILL
FIRST80 THEORETICAL EV          = DERIVED FOUR  N=936
FIRST75 THEORETICAL EV          = DERIVED FOUR  N=913
                                ≠ ASKED-SIX
                                ≠ THE SAME POPULATION
75/25–75/50                     = SAME N=913
75/55                           = ENTRY <81 ONLY  N=868  NOT APPLES-TO-APPLES
VWAP / FILL% / MISSED >85       = NOT_RUN
82¢ AND 76¢ EXAMPLES BELOW      = ILLUSTRATIVE  NOT OBSERVED
```

Desk: `BDR # MOMENTO SYSTEMS`  
Route: `http://127.0.0.1:5190/#/bdr/acquisition-corridor`  
Owner system: `hedging_analysis`

Companion: `docs/research/BDR_LIQUIDATION_CORRIDOR.md` (exit). Follow-on: `docs/research/BDR_77_RIDGE.md` (77 ridge / EV surface), `docs/research/BDR_STAGED_ACQUISITION.md` (77 arms / confirmation). This note is the 75 vs wait-80 entry dual. It does not replace FIRST80 as the research phenomenon. It does not arm live trading.

Texas `#/` and Texas (75) `#/texas-75` are the locked integer sources. Ledger EV ≠ fill ≠ live EV.

---

## The comparison is policy versus policy

The wrong question is whether the FIRST75 research object has a higher candle-path EV than the FIRST80 research object at their nominal entries:

```text
EV(75)  ?≥  EV(80)
```

Those are two different populations (913 vs 936) measured at two different τ. Comparing them as if they were the same trade is a category error.

The production question is:

```text
EV_realized(start working at 75)
  ?≥
EV_realized(wait until FIRST80)
```

Candle-path theoretical EV is an input to that comparison. It is not the comparison.

---

## Theoretical books on the useful 35–45 corridor

FIRST80 integers are the locked Texas derived four (N=936). FIRST75 integers are the locked Texas (75) derived four (N=913). Both are candle-path ledger EV, not fills.

| Exit | 80 theoretical EV | 75 theoretical EV | 75 gives up |
| ---: | ----------------: | ----------------: | ----------: |
| 35 | +5.0694¢ | +4.4962¢ | **0.5732¢** |
| 40 | +4.8718¢ | +4.4962¢ | **0.3756¢** |
| 45 | +4.9573¢ | +4.4578¢ | **0.4995¢** |

The early-entry research object only needs to improve real entry execution by roughly **0.4–0.6¢ per contract** to offset the weaker FIRST75 path population on these exits.

That hurdle is tiny next to live acquisition delay.

It is also not a proven live edge. Fees, queue, gap, and missed trades are not in either column.

---

## Why the wait-until-80 policy may be late

The operational complaint is not “buy at 75 instead of 80.” It is that waiting for the FIRST80 *signal* before the desk is allowed to work inventory makes the *execution* late:

```text
WAIT FOR 80 SIGNAL

market reaches 80
↓
we now begin trying to buy
↓
actual acquisition often 81–83
↓
sometimes jumps to 85–86
↓
trade missed entirely because max entry is breached
```

The nominal 80 backtest gives the wait-until-80 policy an 80¢ entry assumption that live maker-only acquisition may not reproduce.

Starting the acquisition engine at 75 gives runway:

```text
START WORKING AT 75

75 → maker bid
76 → work
77 → work
78 → work
79 → work
80 → already partially/fully positioned
```

That is five cents of corridor to acquire inventory. It is not a fill tape. It is not a live rule.

---

## Hypothetical: put actual entry prices into the comparison

These are **illustrative arithmetic**, not observed VWAP and not a fill study. `P_acq` is `NOT_RUN`.

Take exit 35.

Theoretical books:

```text
EV_80/35 = 5.0694¢
EV_75/35 = 4.4962¢
```

Suppose the wait-until-80 policy is filled at an average of 82¢ (2¢ worse than the research entry):

```text
EV_wait80,illustrative ≈ 5.0694 − 2 = 3.0694¢
```

Suppose the start-at-75 policy builds at an average of 76¢ (1¢ worse than its nominal 75 book):

```text
EV_start75,illustrative ≈ 4.4962 − 1 = 3.4962¢
```

Then 3.4962 > 3.0694 and **75 wins despite the weaker raw path population**.

If delayed 80 execution averaged 83:

```text
5.0694 − 3 = 2.0694¢
```

the advantage of beginning at 75 would be large.

None of those average fills is measured. Do not treat 82 or 76 as warehouse facts. Do not invent L2.

The missed-opportunity term is also unmeasured: markets that print

```text
79
81
84
86
```

and never offer a legally acceptable entry under a wait-until-80 + max-entry rule. That term belongs in the study. It is not in the theoretical books.

---

## FIRST75 opens the window. FIRST80 remains the phenomenon.

Do not read this as “FIRST75 replaced FIRST80.”

```text
FIRST75 opens the acquisition window.
FIRST80 is the state originally identified as having the strong phenomenon.
```

Architecture sketch — research concept, not an armed policy:

```text
75
│
│ ACQUISITION ENGINE ARMED
│
│ maker-only / passive
│ accumulate inventory
│
76
77
78
79
│
80 ───── ORIGINAL FIRST80 CONFIRMATION STATE
│
│ target position ideally already acquired
│
81
82
83
│
84/85+ ── DON'T CHASE
```

That is different from “buy at 75.”

It is: **start trying to acquire the position at 75 because waiting for 80 makes the execution desk late.**

Texas (77) `#/texas-77` is a measured FIRST77 book on the same four clock slices (N=933). It is a corridor waypoint, not a replacement signal and not a live trigger.

---

## The metric is VWAP, not 5.0694 vs 4.4962

For every eligible game, the study that would decide the production winner is:

```text
P_acq = (Σ q_i p_i) / (Σ q_i)
```

for an acquisition algorithm that begins at 75, versus the achievable VWAP of an algorithm that does not begin until 80.

| Policy | Signal | Acquisition begins | Avg VWAP | Fill % | Missed >85 | Exit EV | Net realized EV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Wait80 | 80 | 80 | NOT_RUN | NOT_RUN | NOT_RUN | 5.07¢ theoretical | NOT_RUN |
| Work75 | 75 | 75 | NOT_RUN | NOT_RUN | NOT_RUN | 4.50¢ theoretical | NOT_RUN |

**That** table determines the production winner. Not 5.0694 vs 4.4962 by itself.

Missing L2 remains `SOURCE_UNAVAILABLE`. A candle path is not a fill. Do not fabricate Kalshi depth to close `NOT_RUN`.

---

## Entry and exit are the same shape

**Entry**

```text
Don't demand an exact 80 fill.
Use 75–80 as an acquisition corridor.
```

**Exit** (liquidation-corridor addendum)

```text
Don't demand an exact 40 fill.
Use roughly 45–35 as a liquidation corridor.
```

```text
          ACQUISITION CORRIDOR
               75 → 80
                  │
                  ▼
             OPEN POSITION
                  │
                  ▼
               HEALTHY
                  │
                  ▼
          LIQUIDATION CORRIDOR
               45 → 35
```

The backtest discovers economic regions. The execution engine's job is to exploit those regions.

Given the locked books, the hurdle for beginning acquisition at 75 is about **half a cent of execution cost versus waiting for FIRST80** across the important exit books.

If live FIRST80 orders really tend to cost 81–83 or get missed entirely, the nominal ~0.4–0.6¢ theoretical EV sacrifice at 75 could be a bargain.

That “if” is not yet a measurement.

---

## Head-quant conclusion

> **Do not rank FIRST75 against FIRST80 as competing research objects at nominal entry. Rank start-working-at-75 against wait-until-FIRST80 as execution policies. On the locked 35–45 corridor the theoretical EV FIRST75 gives up is only 0.38–0.57¢ per contract. That is a small hurdle if waiting for 80 forces 81–83 fills or missed max-entry trades. FIRST75 is the proposed acquisition-window open. FIRST80 remains the confirmation state. The deciding metrics are acquisition VWAP, fill rate, and missed >85 — all currently NOT_RUN. This does not arm live trading and does not change 80/81/83/89.**

Strategy still proposes. Risk still approves. Execution still executes.
