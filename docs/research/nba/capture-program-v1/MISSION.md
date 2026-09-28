# Mission — Momento NBA Capture Program V1

Identifier: `MOMENTO_NBA_CAPTURE_PROGRAM_V1`

Research only. This program does not enable live NBA trading, does not
create an NBA strategy crate, and does not change Risk or FIRST01.

**LIVE EXECUTION CHANGED: FALSE.**

---

## The question this program answers

```text
QUESTION A:
Does the FIRST-80 conditional path exist statistically?

ANSWER:
YES — as a historical candle-path phenomenon.
CLOSED.
```

```text
QUESTION B:
Can Momento capture that path with real executable orders,
real fills, real stops, real fees, and sufficient capacity?

ANSWER:
UNKNOWN.
THIS PROGRAM ANSWERS QUESTION B.
```

The objective is **not** to improve the historical 74% statistic.

Do not build another entry-selection model.
Do not optimize the FIRST-80 rule.
Do not add ML filters attempting to predict which FIRST-80 trades survive.

V1–V4 already investigated conditional selection and found no robust
production filter.

The research focus is:

```text
CAN WE ACTUALLY CAPTURE THE ECONOMICS
OF THE TRADE WE ALREADY FOUND?
```

---

## Primary equation

```text
Momento Edge  =  Path Edge  ×  Execution Capture  −  Execution Costs
```

```text
EV_realized  =  P(F) · E[R | F]  +  P(¬F) · E[R | ¬F]
```

A 74% candle statistic with negative realized execution EV is not a
strategy. Conversely, a historical path statistic below 74% may still be
economically viable if execution improves the payoff structure.

The strategy is economically viable only if `EV_realized > 0` under
**observed** execution, not under assumed fills.

---

## Dual engines

| Engine | Role |
| --- | --- |
| A | Frozen trade definition. Rule, not optimizer. Not live. |
| B | Append-only execution ledger. Measures capture. |

See [ENGINE_A_RULE.md](ENGINE_A_RULE.md) and
[LIVE_LEDGER_SCHEMA.md](LIVE_LEDGER_SCHEMA.md).

---

## What success looks like for V1

V1 succeeds when it can **measure** whether the historical path edge
survives contact with market microstructure.

V1 does **not** succeed by making the backtest look better.

The next useful product decision — not made here — is the initial
live-capture mode: `paper ledger`, `tiny real orders`, or
`full simulated execution`. That decision requires explicit later
authorization. This program does not arm any of them.
