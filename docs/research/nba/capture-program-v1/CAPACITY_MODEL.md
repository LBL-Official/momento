# Capacity model

```text
R_week  ≈  N_fills  ×  EV_realized per trade
```

The 1.5–2% weekly target is this identity. It is not a property of 74%.

---

## Two different capacities

| Object | Meaning | Status |
| --- | --- | --- |
| SIGNAL CAPACITY | How many FIRST-80 prints overlap | OBSERVED in frozen gross sim |
| EXECUTABLE CAPITAL CAPACITY | How many maker fills fit bankroll, liquidity, and risk | UNAVAILABLE |

Do not treat overlap statistics as live fillable capacity.

---

## Frozen signal-overlap inputs

From `first80_execution_audit` portfolio (gross +1R/−2R path sim):

| Cap | Accepted | Skipped | Max open observed |
| ---: | ---: | ---: | ---: |
| 1 | 505 | 725 | 1 |
| 5 | 1,192 | 38 | 5 |
| Unlimited | 1,230 | 0 | 8 |

Maximum observed concurrent FIRST-80s: **8**.

---

## Constraints the engine must carry (even when UNAVAILABLE)

- maximum concurrent positions
- available bankroll
- position sizing (research fractions 1/2/3/5% of current equity)
- order fill probability
- market liquidity
- partial fills
- missed signals
- correlated game outcomes

```text
N_fillable  =  N_signals · P_fill   (then cut by concurrent cap)
```

Increasing the number of signals does not automatically increase
deployable capital.

---

## N required for a weekly target

```text
N_required  =  weekly target return  /  EV_realized per trade
```

Research 5% of **current** equity, full 80/40 fills assumed, before
costs (ESTIMATED):

| Assumed world | EV / trade (bankroll) | N for +2% week |
| --- | ---: | ---: |
| 73.98% path, P_fill=1 | +0.275% | ≈ 7.3 |
| 69.28% conservative proxy, P_fill=1 | +0.099% | ≈ 20.3 |

If EV_realized ≤ 0, N_required is undefined.

5% is **not** live MLB 12.5%. It is not written into Risk.
