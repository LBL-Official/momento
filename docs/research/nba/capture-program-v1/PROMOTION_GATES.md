# Promotion gates

The historical path statistic alone cannot promote the strategy.

No strategy becomes a production candidate unless every gate is
explicitly evaluated. A gate that cannot be evaluated is **OPEN /
UNAVAILABLE**, not a pass.

---

## Gate 1 — Entry capture

Must demonstrate **observed**:

- maker fill rate
- partial-fill distribution
- time-to-fill
- missed-signal rate

Current: **FAIL / UNAVAILABLE** (no live episodes).

---

## Gate 2 — Stop capture

Must demonstrate:

- stop trigger behavior
- actual fill-price distribution
- slippage
- partial exit behavior

Current: **FAIL / UNAVAILABLE**. Candle close-40 and wick-40 remain
separate proxies, not this gate.

---

## Gate 3 — Fees

Must have a verified production fee model.

Current: **FAIL / UNRESOLVED**.
`OBSERVED_PRODUCTION_MODEL` is UNAVAILABLE.

---

## Gate 4 — Net EV

```text
EV_realized,observed
```

with confidence intervals or posterior intervals.

Current: **FAIL / UNAVAILABLE**. Scenario surfaces are not this gate.

---

## Gate 5 — Capacity

Demonstrate enough **executable** opportunities for the target
economics.

Current: **FAIL / UNAVAILABLE**. Frozen overlap (cap 1/5/unlimited) is
signal capacity only.

---

## Gate 6 — Risk

Demonstrate acceptable:

- maximum drawdown
- portfolio concentration
- concurrent exposure
- execution-failure risk

Current: **NOT EVALUATED ON LIVE DATA**. Monte Carlo files are
`SCENARIO ANALYSIS / NOT A PERFORMANCE FORECAST`.

---

## Initial verdict

```text
VERDICT = QUESTION B OPEN
```

Do not emit VERDICT A/B/C until observed execution exists.
