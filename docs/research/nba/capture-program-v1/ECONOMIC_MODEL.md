# Economic model

Research identities. Not a performance forecast.

---

## Frozen path economics

Winner = +1R = +20¢ (80 → 100).
Loser = −2R = −40¢ (80 → 40).

```text
EV_gross  =  p(+1) + (1−p)(−2)  =  3p − 2
```

At p = 910/1230:

```text
EV_gross  ≈  +0.2195 R
```

Break-even at zero fees and exact 40¢ stop:

```text
p_BE  =  L / (W + L)  =  2 / 3  ≈  66.67%
```

Do not reinterpret these as executable results.

---

## Realized EV

```text
EV_realized  =  P(F) · EV_filled  −  C_unfilled
```

```text
EV_filled  =  p_survive · W_net  +  (1 − p_survive) · (−L_net)
```

```text
p_BE,net  =  L_net / (W_net + L_net)
```

W_net and L_net include the chosen fee model and the assumed stop print.

Partial fill α scales EV by filled quantity:

```text
Q_filled  =  α · Q_requested
EV_realized(α)  =  P(F) · α · EV_filled  −  C_unfilled
```

Stop prints other than 40¢ change L:

| Assumed stop | L (gross, ¢) | p_BE (zero fee) |
| ---: | ---: | ---: |
| 40 | 40 | 66.67% |
| 39 | 41 | 67.21% |
| 38 | 42 | 67.74% |
| 35 | 45 | 69.23% |
| 30 | 50 | 71.43% |

All non-40 stop prices are `SIMULATED_EXECUTION_SCENARIO`. They are not
historically proven executable without high-resolution data.

---

## Bankroll mapping (research sizing, not live)

Allocated cash at 80¢ is **not** the same as bankroll risked.

```text
allocated  =  f · equity
win        =  +0.25 · allocated   =  +1.25% of bankroll at f=5%
loss@40    =  −0.50 · allocated   =  −2.50% of bankroll at f=5%
```

Equivalently, 1R = 20¢ on 80¢ allocated → 0.25 of allocated capital:

```text
Δ equity / equity  ≈  f · EV_R · 0.25
```

At historical path EV +0.2195 R and f = 5% (full fill assumed):

```text
≈ +0.275% of bankroll / trade
```

This is ESTIMATED path math. Status of actual fills: UNAVAILABLE.

---

## Surface regions (scenario labels)

| Region | Rule | Meaning |
| --- | --- | --- |
| A | EV_realized ≥ +0.10 R | Robust under the stated assumptions |
| B | 0 < EV_realized < +0.10 R | Execution-sensitive |
| C | EV_realized ≤ 0 | Structurally unprofitable under those assumptions |

These are not production claims.

---

## Weekly identity

```text
R_week  ≈  N_fills  ×  EV_realized per trade
```

```text
N_required  =  weekly target  /  EV_realized per trade (bankroll)
```

A 1.5–2% week is this identity, not a property of 74%.
If EV_realized ≤ 0, no N produces a positive week.
