# 9/2 DRE [R] V1 Portfolio Objective

**Memo date:** 2026-09-02
**Stored:** 2026-09-19
**System:** `dynamic_risk_engine`
**Status:** RESEARCH MEMO. Not an execution policy. Not `crates/risk`.
**Live execution changed:** FALSE
**Calculus implemented:** FALSE

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
THEORETICAL HEDGE ≠ EXECUTABLE HEDGE ≠ ECONOMICALLY BENEFICIAL HEDGE
Δ↓ ⇏ α↑
PRESERVE POSITIVE ALPHA FIRST. THEN OPTIMIZE DIRECTIONAL EXPOSURE.
```

This is the V1 north star for the Dynamic Risk Engine. It states
**what DRE is aiming to do**. It does not authorize a live rule, a
fill, or a computed `Λα`.

Forward feed is only:

```
Choosin Texas  →  TradeBreakdown   (derived four N=936)
Austin         →  PositionStratum  (NBA 2Q∪3Q N=604)
               →  DRE
```

See [`README.md`](README.md) for the desk map.
See [`GREEK_STACK_V1.md`](GREEK_STACK_V1.md) for delta / gamma /
vega / lambda / hazard. Do not calculate those objects from this file.

---

## What we are aiming to do

Maintain a position whose **unwanted directional exposure** is
driven toward the amount that is justified by remaining
demonstrated alpha — not toward literal zero at every instant.

The first written objective is:

```
ΔP → 0 | αP > 0
```

Read the vertical bar as **subject to** / **conditional on**.
It does **not** mean alpha is another hedge ratio.

In words:

> Drive portfolio directional exposure toward zero, **conditional
> on the portfolio continuing to possess positive alpha**.

That is already more sophisticated than “hedge until flat.”

The eventual objective is stricter:

```
ΔP → ΔP*(Xt)
```

where `ΔP*(Xt)` is the **optimal** portfolio directional exposure
given the current state `Xt`.

Delta neutrality is not necessarily the objective.
**Optimal exposure** is the objective.

---

## The architecture you are actually building

Subject to retaining the expected alpha of the position, minimize
unwanted directional exposure.

```
Portfolio objective:  ΔP → 0 | αP > 0
```

Then evolve beyond forcing `ΔP → 0`:

```
ΔP → ΔP*(Xt)
```

Sometimes the optimal portfolio is nearly delta-neutral.
Sometimes it is correct to retain directional exposure because
the expected alpha justifies the additional risk.

The Dynamic Risk Engine should eventually answer:

> Given everything we currently know about the position, what
> amount of directional exposure is optimal right now?

---

## The current state: Xt

`Xt` is the complete relevant state of the position at time `t`.

Eventually `Xt` could include:

- Current market price
- Game state
- Score differential
- Time remaining
- Possession or other sport-specific state variables
- Current estimated fair probability
- Distance between market price and fair value
- Market volatility
- Path volatility since entry
- Current portfolio delta
- Cross-market relationships
- Liquidity conditions
- Spread conditions
- Execution quality
- Remaining expected alpha
- Evidence of alpha deterioration

Conceptually:

```
Xt = everything relevant that describes the current state
     of the position.
```

**Today DRE does not construct `Xt`.** The only honest inputs are
Choosin Texas trade-breakdown integers and Austin stratum /
experiment artifacts. Live feed is `UNAVAILABLE`. Missing is
`UNAVAILABLE`, never `$0`. Do not invent Kalshi L2, PIT game
state, or a live fair probability to fill this list.

The engine observes whatever `Xt` is actually available and
determines the appropriate research exposure statement.
It does not submit.

---

## The optimization objective

The eventual problem is:

```
MAXIMIZE
  E[P&L] − λ × Risk
SUBJECT TO
  αP > 0
```

Where:

- `E[P&L]` = expected future profit and loss
- `λ` = importance / penalty assigned to risk
- `Risk` = relevant risk of maintaining the current position
- `αP` = the portfolio’s remaining expected alpha

This is a research specification. `λ` here is a risk-penalty
symbol, not a live calibrated number, and not the deterioration
Greek `Λα` in [`GREEK_STACK_V1.md`](GREEK_STACK_V1.md).

A minimum-delta form of the same idea:

```
min |ΔP|  subject to  E[ΠP] ≥ α_min
```

You do not want a perfectly hedged portfolio that makes no money.
You want the **minimum economically necessary directional
exposure required to preserve established alpha**.

---

## The core principle

Do not eliminate risk blindly.

- Hold risk when we are being compensated for it.
- Reduce risk when deterioration makes that exposure inefficient.
- Eliminate directional exposure when the marginal alpha no
  longer justifies the marginal risk.

```
Risk is not inherently bad. Uncompensated risk is bad.
```

---

## The most important evolution in the framework

Original idea:

```
Make delta equal zero.
```

More sophisticated idea:

```
Find the optimal amount of delta for the current state.
```

A perfectly delta-neutral position can be inferior to a slightly
directional position if:

- The directional exposure is compensated by substantial alpha.
- The additional risk is acceptable.
- The alpha remains statistically demonstrated.
- The execution assumptions remain realistic.

A highly directional position may become inefficient when:

- Alpha begins deteriorating.
- The probability distribution worsens.
- Volatility increases without additional compensation.
- Execution conditions deteriorate.
- The marginal risk becomes greater than the marginal expected
  reward.

---

## The conditional portfolio objective

Foundational Momento Systems principle:

```
PRESERVE POSITIVE ALPHA FIRST.
THEN OPTIMIZE DIRECTIONAL EXPOSURE.
```

```
αP > 0
  ↓
Determine current state Xt
  ↓
Estimate optimal exposure ΔP*(Xt)
  ↓
Move portfolio exposure toward:
ΔP → ΔP*(Xt)
```

The system should not ask:

```
How do we make delta zero?
```

The system should ask:

```
Given the current state, how much directional risk should
we rationally own?
```

---

## The role of the Dynamic Risk Engine

DRE eventually answers four questions:

1. **WHY DO WE OWN THIS POSITION?**
   Positive demonstrated alpha.
2. **HOW MUCH RISK ARE WE CURRENTLY TAKING?**
   Current portfolio exposure, including delta and other risk
   dimensions.
3. **IS THAT RISK STILL EFFICIENT?**
   Compare marginal expected alpha against marginal risk.
4. **HOW SHOULD WE CHANGE THE POSITION?**
   Hold, hedge, reduce, restructure, or exit.

Today those answers are research / `UNKNOWN` unless an artifact
states otherwise. Phase 3 downfall language is not question 4.

---

## The future decision framework

```
ENTER
  ↓
ESTABLISH ALPHA
  ↓
VERIFY EXECUTABILITY
  ↓
MEASURE CURRENT STATE Xt
  ↓
ESTIMATE REMAINING ALPHA
  ↓
MEASURE CURRENT RISK
  ↓
DETERMINE OPTIMAL EXPOSURE ΔP*(Xt)
  ↓
COMPARE:
  CURRENT EXPOSURE
  VERSUS
  OPTIMAL EXPOSURE
  ↓
HOLD / HEDGE / REDUCE / RESTRUCTURE / EXIT
```

Every action must still pass the execution hierarchy in
[`GREEK_STACK_V1.md`](GREEK_STACK_V1.md). A model cannot reduce
delta with a hedge whose fill exists only as a price threshold.

---

## The critical relationship between alpha and risk

Every additional unit of risk is a marginal question:

```
What additional alpha am I receiving for accepting this
additional risk?
```

```
Marginal Alpha / Marginal Risk
```

If additional directional exposure produces meaningful additional
expected value, retaining that exposure may be rational.
If it produces little or no additional alpha, reduce it.

---

## The role of deterioration

This is where future deterioration-rate calculus enters.
It is **not** “is the price moving against us?”

At entry the position has an established conservative alpha
distribution. As time passes the system asks:

```
Does the current position still belong to that original
positive-alpha distribution?
```

| Answer | Research action |
|---|---|
| Yes | Maintain the position and optimize exposure |
| Distribution deteriorating | Reduce exposure |
| Positive expected alpha destroyed | Exit or fundamentally restructure |

The deterioration engine eventually measures:

```
Is the reason we originally owned this position disappearing?
```

That reason arrives from Choosin Texas (frozen payoff / S / EV
identities) and Austin (whether the current stratum still looks
like the neighborhood that supported the hold). DRE does not
invent a third N.

Do not yet pretend we know how to calculate `dα/dt`.
See the build order at the end of
[`GREEK_STACK_V1.md`](GREEK_STACK_V1.md).

---

## The full Momento Systems objective

1. Identify empirically demonstrated alpha.
2. Verify that the payoff can be realistically executed.
3. Enter the position.
4. Continuously estimate the current state `Xt`.
5. Determine how much alpha remains.
6. Measure current portfolio risk.
7. Calculate the optimal exposure for the current state:
   `ΔP*(Xt)`.
8. Move current exposure toward that optimal exposure.
9. Reduce or eliminate exposure when the remaining marginal
   alpha no longer justifies the remaining marginal risk.
10. Exit when the original positive-alpha thesis has materially
    deteriorated.

Steps 3 and 8–10 are **not live**. Algorithmic Execution is
`NOT_IMPLEMENTED` for NBA. DRE does not submit.

---

## One-sentence version

Do not eliminate risk blindly; hold risk when compensated by
demonstrated alpha, reduce risk when deterioration makes that
exposure inefficient, and eliminate directional exposure when
the marginal alpha no longer justifies the marginal risk.

---

## What this memo does not authorize

- A live hold / hedge / reduce / restructure / exit policy.
- A computed `ΔP*(Xt)`, `Λα`, hazard rate, or vega.
- Treating Austin Phase 3 as that policy.
- Treating candle-path ledger EV as a fill or live EV.
- Inventing L2, fair odds, or a live `Xt`.
- Mixing N=604 / 936 / 1182.
- Changing live FIRST01 / 80/81/83/89.
- Calling `crates/risk` this engine.

Formalize `Xt`, `ΔP*(Xt)`, and marginal alpha / marginal risk
only after the frozen conservative distribution and the
four-level execution hierarchy can support them. That work is
not started by storing this memo.
