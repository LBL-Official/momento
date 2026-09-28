# Question B — execution capture

Open. This is the program.

---

## The object

```text
EV_realized  =  P(entry fill) · EV(trade | actual fill)  −  C_execution
```

More completely:

```text
EV_realized
  = P(entry fill)
    · [ P(survival | fill) · W_net  +  P(stop | fill) · L_net ]
  − C_entry
```

Eventually:

```text
EV_realized = f(
  P_fill, P_stop, P_survival, P_stop_fill,
  entry price, exit price, fees, slippage,
  partial fills, capacity
)
```

Viable only if `EV_realized > 0` on **observed** execution.

---

## Never collapse these events

| Print | Is not |
| --- | --- |
| PRICE PRINTED 80 | ORDER FILLED AT 80 |
| PRICE PRINTED 40 | POSITION EXITED AT 40 |
| yes_bid_close ≥ 80 | maker queue fill |
| yes_bid_low ≤ 40 | 40.00 IOC fill |
| last-trade through 80 | our resting bid was hit |

---

## Current observation status

| Quantity | Status |
| --- | --- |
| Historical FIRST-80 survival | OBSERVED candle path |
| Historical maker fill at 80 | UNAVAILABLE |
| Historical stop fill at 40 | UNAVAILABLE |
| Fill-probability stress grid | SIMULATED |
| Production fee model | UNAVAILABLE (UNRESOLVED) |
| Published fee schedule | ESTIMATED |
| Live maker fill | OBSERVED only after an exchange fill |
| Live episode count | 0 |

---

## Engine A vs Engine B

Engine A freezes the intended rule (first valid 80 → maker rest →
monitor → stop or settle). It does not submit orders.

Engine B records every stage of an attempted trade. Missing stages stay
`UNAVAILABLE`. See [LIVE_LEDGER_SCHEMA.md](LIVE_LEDGER_SCHEMA.md).

---

## Candle proxies already on the frozen scoreboard

Copied, not relabeled, from `first80_execution_audit`:

| Proxy | n | Survival | Gross EV | What it is |
| --- | ---: | ---: | ---: | --- |
| Close-stop | 1,230 | 73.98% | +0.2195 R | Path label |
| HIGH fill, close-stop | 1,071 | 73.30% | +0.1989 R | Fill-confidence filter |
| Wick-stop | 1,230 | 69.02% | +0.0707 R | bid_low ≤ 40 |
| Conservative HIGH+wick | 1,071 | 69.28% | +0.0784 R | Combined proxy |

The 74% → 73% drop is noise. The drop to ~69% is treating a wick as a
stop. Neither is an observed fill distribution.

---

## Verdict rule

Until observed execution exists, the report verdict is:

```text
VERDICT = QUESTION B OPEN
```

The report must never claim the strategy is profitable.
