# WNBA FIRST80 80→40 — Q2 and Q3 only

Research only. Same frozen FIRST80 / close-40 rule, restricted to
ESPN-aligned **2nd-quarter and 3rd-quarter** entries.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

Universe: **246** FIRST80 prints (Q2=127, Q3=119) out of the frozen settled FIRST80 tape (n=589). Excluded from this cut: Q1=127, Q4=83, OT=2, UNALIGNED=131 (no ESPN quarter tag; not treated as Q2 or Q3).

## 1. Observed 80→40 path (Q2 ∪ Q3)

| | Q2 | Q3 | Q2 ∪ Q3 |
|---|---:|---:|---:|
| FIRST80 | 127 | 119 | 246 |
| Wins (Kalshi yes) | 105 | 100 | 205 |
| WIN ∧ ¬T40 | 89 | 94 | 183 |
| WIN ∧ T40 | 16 | 6 | 22 |
| LOSS ∧ ¬T40 | 0 | 0 | 0 |
| LOSS ∧ T40 | 22 | 19 | 41 |
| T40 close | 38 | 25 | 63 |

Strategy win rate (hold unless close-stop): **74.3902%**  
95% Wilson CI: **68.5899% – 79.4405%** (n = 246)

P(Kalshi yes \| FIRST80, Q2∪Q3) = **83.3333%**  
Gross EV (+20¢ / −40¢ candle path) = **0.2317 R**

### Splits (a priori; not retuned)

- **IN_SAMPLE**: n=120 win=75.0% CI [66.5587, 81.8903] EV_R=0.25
- **VALIDATION**: n=77 win=77.9221% CI [67.4567, 85.7337] EV_R=0.3377
- **OOS**: n=49 win=67.3469% CI [53.3789, 78.7927] EV_R=0.0204

## 2. 40-losers in the last 5 minutes

A **40-loser** is a FIRST80 that expired no and close-touched 40
(LOSS ∧ T40). Clock is **4Q remaining** at the first tradable
`yes_bid_close ≤ 40¢`. OT is not last-5 regulation.

| Entry | 40-losers | T40 in last 5:00 of 4Q | % of losers |
|---|---:|---:|---:|
| Q2 | 22 | 13 | 59.09% |
| Q3 | 19 | 13 | 68.42% |
| **Q2 ∪ Q3** | **41** | **26** | **63.41%** |

Cumulative 4Q remaining at the 40 print (Q2 ∪ Q3 losers):

- ≤6:00 4Q remaining: **27** (65.85% of losers)
- ≤5:00 4Q remaining: **26** (63.41% of losers)
- ≤4:00 4Q remaining: **25** (60.98% of losers)
- ≤3:00 4Q remaining: **19** (46.34% of losers)
- ≤2:00 4Q remaining: **15** (36.59% of losers)
- ≤1:00 4Q remaining: **14** (34.15% of losers)

Discrete bins (Q2 ∪ Q3 losers):

- BEFORE_LAST_6: 13 (31.71%)
- 5:01–6:00: 1 (2.44%)
- 4:01–5:00: 1 (2.44%)
- 3:01–4:00: 6 (14.63%)
- 2:01–3:00: 4 (9.76%)
- 1:01–2:00: 1 (2.44%)
- 0:00–1:00: 14 (34.15%)
- OT: 1 (2.44%)

## 3. What this is not

- Not a live order, fill, or realized P&L.
- Not Q1 / Q4 / OT / unaligned FIRST80.
- Not MLB FIRST01.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

