# Weekly capacity (research identity, not a forecast)

Do **not** read this as a promise of 1.5–2% per week.

```text
Weekly return  ≈  N_fills  ×  EV_realized per trade
```

Both factors are **open** under Question B.

- \(N_{\text{fills}}\) is not the 1,230 FIRST-80 prints. Prints ≠ fills.
- \(EV_{\text{realized}}\) is not +0.2195 R. That is gross path EV under
  close-stop +1R/−2R, not cash after fills, fees, and slippage.

---

## Historical print count (OBSERVED in warehouse)

1,230 FIRST-80 settled trades in the 2025–26 KXNBAGAME research window
(`first80_execution_audit`). Fillable subset: **UNAVAILABLE**.

---

## Research sizing scenario (not live)

The brief’s 5% of **current** equity per trade is a **research scenario**.
It is not live MLB 12.5%. It is not written into Risk or `config/` here.

Cash-flow mapping for that scenario (entry 80¢, full winner to 100¢, full
loser to 40¢), **before** fees and slippage:

```text
allocated = 0.05 × equity
win  = +0.25 × allocated  = +1.25% of bankroll
loss = −0.50 × allocated  = −2.50% of bankroll
```

At close-stop survival 73.98% (~74%):

```text
EV_trade ≈ 0.7398×1.25% − 0.2602×2.50% ≈ +0.275% of bankroll
```

At conservative HIGH+wick 69.28%:

```text
EV_trade ≈ 0.6928×1.25% − 0.3072×2.50% ≈ +0.099% of bankroll
```

These are **ESTIMATED** gross bankroll fractions under assumed full fills
at 80 and 40. Status of actual fills: UNAVAILABLE.

---

## What a 2% week would require (identity only)

Before costs, concurrency, and partial fills:

| Assumed EV / trade | Fills needed for +2% week |
| --- | ---: |
| +0.275% (74% world, 5% fraction) | ≈ 7.3 |
| +0.099% (69.3% world, 5% fraction) | ≈ 20.3 |

If Engine B later measures \(EV_{\text{realized}} \le 0\), no N produces a
positive week. If fills are 2/week, even the 74% world is ~0.55%/week
before costs.

Concurrent cap=1 on the frozen gross sim booked only 505 / 1,230 signals.
Capacity and edge are joint.

---

## What this document forbids

- Stating “2% weekly is expected”
- Using 5% as production NBA or MLB sizing
- Treating 1,230 prints as 1,230 fills
- Optimizing N by lowering fill quality
