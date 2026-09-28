# 77 Arms · Confirmation States · Liquidation Manifold

```text
RESEARCH ADDENDUM / THESIS
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE ENTRY
DOES NOT START W9
DOES NOT CREATE AN 18TH SYSTEM
NOT_ARMED
RESEARCH_REGISTERED             ≠ LIVE_ARMED
CANDLE PATH                     ≠ FILL
NATURAL BOOKS                   = SEPARATE τ POPULATIONS
FIRST75 913 ≠ FIRST77 933 ≠ FIRST80 936 ≠ FIRST81 940 ≠ FIRST83 973
COMMON-INTERSECTION LADDER      = NOT_RUN
ASKED-SIX                       ≠ DERIVED FOUR
74 / 76 / 78 / 79 BOOKS         = NOT_RUN
EXITS 27 / 53                   = NOT_RUN
MISSING L2                      = SOURCE_UNAVAILABLE
P_acq / FILL% / MISSED >85      = NOT_RUN
```

Desk: `BDR # MOMENTO SYSTEMS`  
Route: `http://127.0.0.1:5190/#/bdr/staged-acquisition`  
Owner system: `hedging_analysis`

Follow-on to [`BDR_77_RIDGE.md`](BDR_77_RIDGE.md), [`BDR_ACQUISITION_CORRIDOR.md`](BDR_ACQUISITION_CORRIDOR.md), and [`BDR_LIQUIDATION_CORRIDOR.md`](BDR_LIQUIDATION_CORRIDOR.md). Integer sources: Choosin Texas `#/`, `#/texas-75`, `#/texas-77`, FIRST81/83 companion tiles, `#/asked-six`. Ledger EV ≠ fill ≠ live EV.

This page is more revealing than the earlier grids because it separates **signal strength**, **entry execution**, **exit robustness**, and **game-state heterogeneity**.

---

## Biggest finding

**77 is almost indistinguishable from 80 on theoretical EV. 81–83 buy only a few additional tenths of a cent.** Waiting for the higher trigger is hard to justify if it materially worsens the actual fill.

Best **full-book** candle-path cell on each **natural** derived-four τ book (verified `/choosin-texas/universe`, `universe-75`, `universe-77`, `universe-81`, `universe-83`):

| FIRST threshold | Best full-book exit | Best theoretical EV | Increment vs 77/40 |
| ---: | ---: | ---: | ---: |
| 75 | 33 | +4.7459¢ | −0.3763¢ |
| **77** | **40** | **+5.1222¢** | — |
| 80 | 43 | +5.1410¢ | **+0.0188¢** |
| 81 | 33 | +5.4574¢ | +0.3352¢ |
| 83 | 37 | +5.6043¢ | +0.4821¢ |

These are **different N**. They are not one population with only τ changed.

The **77→80 difference on those best cells is 0.0188¢ per trade**.

If waiting for FIRST80 worsens average acquisition by even **0.1¢**, starting execution at 77 already wins economically. If waiting for 80 means live fills commonly become 81–83, or the book runs through 85–86 before a fill, the execution value of 77 can dwarf that 0.019¢ theoretical edge.

FIRST83 only buys:

```text
5.6043 − 5.1222  =  0.4821¢
```

of additional candle-path EV versus FIRST77's boxed 77/40 cell.

Live question (not answered here; `P_acq` is `NOT_RUN`):

```text
Does waiting from 77 to 83 cost more than 0.48¢ in realized acquisition quality?
```

If yes, the theoretically "better" 83 state is economically worse to trade.

---

## 83 may be confirmation, not entry

```text
75    too early / meaningful signal dilution

77    phenomenon largely established
      + execution runway

80    almost no additional theoretical EV vs 77
      (best-cell gap +0.0188¢ on different N)

81    stronger confirmation

83    strongest theoretical full-book state shown
      but likely much harder to acquire at 83 in reality
```

Do not ask which one is *the* entry. Research concept, `NOT_ARMED`:

```text
FIRST77
   │
   ├── acquisition begins
   │   passive maker
   │   small/partial position allowed
   │
78–79
   │
80
   ├── increase target completion
   │
81
   ├── stronger confirmation
   │
82–83
   ├── position should ideally already be established
   │
84–86
   └── DO NOT CHASE
```

**77 solves execution. 80 / 81 / 83 provide increasing confirmation.**

The research threshold and the execution start do not have to be the same number.

78 / 79 / 82 remain `NOT_RUN` as FIRST books. They are waypoints in the sketch, not locked τ objects.

---

## Exit: high-EV liquidation manifold

Lots of intermediate barriers are now locked. There is no single global "correct" stop.

FIRST80 (N=936, gain 20):

```text
33  +5.0395¢
35  +5.0694¢
37  +5.0577¢
40  +4.8718¢
43  +5.1410¢
45  +4.9573¢
```

From **33 through 45**, most of that surface sits around ~5¢ / trade.

The market gives Momento a **region** in which to execute. It does not force one precise point.

FIRST81 (N=940, gain 19) repeats it:

```text
30  +5.4468¢
33  +5.4574¢
35  +5.4468¢
37  +5.3947¢
43  +5.4170¢
```

FIRST83 (N=973, gain 17):

```text
33  +5.3628¢
35  +5.5098¢
37  +5.6043¢
40  +5.4687¢
43  +5.5766¢
```

Do not spend intellectual energy asking whether the "true stop" is 37, 40, or 43. There probably isn't one.

The object is the **high-EV liquidation manifold**. Momento Live should transact opportunistically inside it. That is a research concept. `LIVE EXECUTION = FALSE`.

---

## Slice heterogeneity — a global 40 leaves money on the table

A single global exit rule is probably wrong. Derived-four slices, candle-path only.

**NBA 2Q** likes roughly the mid-30s to low-40s.

```text
80/37  +5.7548¢   n=314
83/35  +6.3478¢   n=299
```

**NBA 3Q** tolerates later liquidation.

```text
80/47  +4.8310¢   n=290
80/50  +4.8276¢   n=290
81/50  +5.9128¢   n=298
```

Path geometry for a 3Q entry is not the 2Q entry.

**NCAAB H1 second 10** often wants more room or the ~43 region (FIRST80 80/43 +4.6425¢ vs 80/40 +4.1451¢ on n=193).

**NCAAB H2 first 10** is a different book:

```text
80/47  +7.0360¢   n=139
80/40  +6.6187¢   n=139
```

So:

```text
Exit Policy  =  f(sport, period, clock, path, liquidity)
```

not

```text
Exit Policy  =  40
```

That is where a position-management engine belongs. It is not an authorization to submit.

---

## T40 clocks — when the engine needs to care

FIRST80 NBA path (`/choosin-texas/nba-path`). Modeled `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`. Not warehouse PBP↔candle PIT. PIT stays `OPERATION_REQUIRED`.

Q2 entries: **75** T40 events. **46** occur in Q4.

```text
46/75  =  61.3%
Q4 mean remaining  06:36
```

Q3 entries: **79** T40 events. **64** occur in Q4.

```text
64/79  ≈  81.0%
Q4 mean remaining  05:48
```

The adverse event is not uniform over the rest of the game. A large share of serious deterioration sits in **middle-to-late Q4**.

Architecture sketch, `NOT_ARMED`:

```text
FIRST77 acquisition
        ↓
healthy hold
        ↓
Q4 approaches
        ↓
position-management urgency rises
        ↓
begin working both books
        ↓
35–45 liquidation corridor
```

A hedge order does not have to work aggressively from the second of a Q2 entry. Optionality can stay open until the hazard window.

---

## QA — common-intersection ladder is NOT_RUN

Natural-book N:

```text
75 → 913
77 → 933
80 → 936
81 → 940
83 → 973
```

Texas already labels these as separate τ books. That is not a bug.

It means **77/40** and **83/37** are **not** the same games with only the entry threshold changed. First-touch and `seen_below` change which events exist.

Required next view — **do not invent it here**:

```text
COMMON-INTERSECTION ENTRY LADDER  =  NOT_RUN
FIRST75 ∩ FIRST77 ∩ FIRST80 ∩ FIRST81 ∩ FIRST83
```

Rerun every entry × exit on that exact locked game set.

| View | Question |
|---|---|
| Natural book | What does each strategy actually trade? |
| Common intersection | Holding game identity fixed, what did τ itself do? |

Natural book determines production economics. Intersection tells you whether the threshold caused the improvement or population composition moved.

Until that lock exists, treat 0.0188¢ (77 vs 80 best cells) and 0.4821¢ (77 vs 83 best cells) as **cross-book** gaps, not within-game τ effects.

---

## Where this is heading

Not `80 / 40`. Not even `77 / 40`.

```text
                 MOMENTO BASKETBALL POSITION

                     ACQUIRE
                       │
                 FIRST77 ARMS
                       │
             maker accumulation
                       │
              80 / 81 / 83
              confirmation states
                       │
                       ▼
                  HEALTHY HOLD
                       │
                 state evolves
                       │
        ┌──────────────┴──────────────┐
        │                             │
    NORMAL PATH                 DISTRESS PATH
                                      │
                           execution engine activates
                                      │
                          BOTH COMPLEMENTARY BOOKS
                                      │
                       ┌──────────────┴──────────────┐
                       │                             │
                 SELL ORIGINAL               BUY OPPONENT
                       │                             │
                       └──────────────┬──────────────┘
                                      │
                          35–45-ish EV corridor
                                      │
                            optimal completion
```

Sport / period / state then alter the corridor and the urgency schedule.

The single most important **entry** quantitative result on the locked natural books:

```text
77_max  =  +5.1222¢   (77/40, N=933)
80_max  =  +5.1410¢   (80/43, N=936)
```

Only **0.0188¢** separates them theoretically.

If that gap survives a common-intersection audit (`NOT_RUN`), waiting until 80 would need essentially **perfectly free execution** to justify giving up the runway from starting at 77.

Candle-path theoretical EV ≠ fill EV. Path survival ≠ settlement ≠ fills. Missing L2 = `SOURCE_UNAVAILABLE`. Do not fabricate Kalshi depth.

Strategy still proposes. Risk still approves. Execution still executes.
