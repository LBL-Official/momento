# DRE [R] V1 — Greek stack and deterioration

Companion to [`PORTFOLIO_OBJECTIVE_V1.md`](PORTFOLIO_OBJECTIVE_V1.md).
Research objects only. **Do not calculate these derivatives yet.**

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
THEORETICAL HEDGE ≠ EXECUTABLE HEDGE ≠ ECONOMICALLY BENEFICIAL HEDGE
Δ↓ ⇏ α↑
Λα ≠ Δ ≠ Γ ≠ β
```

The missing concept is not market beta. It is closer to a
**hazard rate** plus an **alpha deterioration rate**.

---

## 1. Delta — directional exposure

Suppose the original FIRST80 position is:

```
Buy A1 YES @ 80¢
```

Payoff changes as the probability of A1 winning changes.
That is directional exposure.

At a simplified level:

```
Δ_A1 = ∂V / ∂S
```

- `V` = value of the strategy
- `S` = underlying probability / state variable driving the
  game outcome

DRE’s first problem:

```
How exposed am I to further deterioration in the underlying
game state?
```

The goal is not necessarily literally zero delta at every
instant. That would likely destroy alpha.

The optimization is closer to:

```
min |ΔP|  subject to  E[ΠP] ≥ α_min
```

You don’t want a perfectly hedged portfolio that makes no money.
You want the minimum economically necessary directional
exposure required to preserve established alpha.

---

## 2. Alpha — the frozen empirical payoff advantage

In this research framework, alpha does **not** mean
“the trade made money.”

```
α = E[Π | frozen state, regime, execution assumptions]
    − E[Π_benchmark]
```

Example — conservative FIRST80 distribution:

```
80 entry
      ↓
A1 does not deteriorate to 40
      → winner
      → +20¢

A1 deteriorates to 40
      → assumed stop
      → −40¢
```

That creates an empirical payoff distribution.
The alpha comes from the observed historical asymmetry:

```
Frequency of +20 outcomes
        versus
Frequency of −40 outcomes
```

If the conservative frozen universe establishes positive
expectancy, then `E[Π] > 0`. That is the asset DRE is trying
to protect. The hedge cannot be evaluated independently of
that alpha.

This is exactly what the A1 research taught.

A hedge can reduce directional exposure while simultaneously
destroying expectancy.

```
THEORETICAL HEDGE
    ≠
EXECUTABLE HEDGE
    ≠
ECONOMICALLY BENEFICIAL HEDGE
```

The A2 @40 research is the citation:

| Object | Research EV (¢) |
|---|---|
| V1 theoretical | +5.17 |
| 80 → 40 | +4.39 |
| Conservative hedge (jump-throughs = misses) | +4.33 |

The theoretical version appeared to improve EV versus 80→40.
Once jump-throughs became execution misses, the conservative
hedge was +4.33¢ against 80→40 at +4.39¢. The hedge reduced
some theoretical risk while **destroying 0.07¢ of expected
value**.

Therefore:

```
Δ↓ ⇏ α↑
```

That is a foundational Momento Systems principle.
These cents are frozen research citations. They are not live
EV and not a fill.

---

## 3. Beta is probably not the missing Greek

Traditionally:

```
β = Cov(R_i, R_m) / Var(R_m)
```

Stock return relative to market return.

The FIRST80 position is not primarily exposed to the S&P 500.
It is exposed to **changes in a latent sporting game state**:

- Score differential
- Time remaining
- Possession
- Lineup quality
- Injury information
- Foul situation
- Game momentum
- Market repricing
- Liquidity deterioration

An empirical **state beta** could be written:

```
β_state = ∂P_Kalshi / ∂S_game state
```

That still does not describe deterioration.

Beta asks: what tends to move with what?
Deterioration asks: how quickly is the distribution supporting
my alpha disappearing?

Those are different.

---

## 4. The missing concept is closer to a hazard rate

The intuition about a “deterioration Greek” is real.
The better starting point is not beta.

```
λ_stop(t) = lim_{Δt→0}
  P(hit damaging state in [t, t+Δt] | alive at t) / Δt
```

Given that the position has survived so far, how quickly is
the probability of catastrophic deterioration increasing?

For FIRST80:

```
Position entered @ 80
        ↓
Still alive
        ↓
What is the conditional rate of eventually reaching 40?
```

That is relevant to DRE. It is **not yet a computed series**.
Austin Phase 3 / hazard artifacts are research language, not
this derivative.

---

## 5. Deterioration rate is broader than hazard

The true object:

```
The rate at which the remaining expected alpha of the
position is decaying.
```

That is different from simple price movement.

Empirical quantity:

```
D_t = − dα_t / dt
```

Call it the **Alpha Deterioration Rate**.

```
α_t = E[Π | X_t]
D_t = − d/dt E[Π | X_t]
```

| Sign | Meaning |
|---|---|
| `D_t < 0` | Alpha is improving |
| `D_t ≈ 0` | Alpha is stable |
| `D_t ≫ 0` | Alpha is rapidly disappearing |

This is closer to what the desk has been calling deterioration
rate.

**Do not pretend we know how to calculate that derivative.**

---

## 6. Three (actually more) separate sensitivities

### Delta — directional sensitivity

```
Δ = ∂V / ∂S
```

If the game-state probability moves against me, how much does
the position suffer?

### Gamma — convexity / acceleration

```
Γ = ∂²V / ∂S²
```

Does directional risk accelerate as the game deteriorates?

A decline from 80 → 70 may not be economically equivalent to
50 → 40, even though both are ten-cent moves. Near the stop
region the distribution may change nonlinearly. That is
gamma-like.

### Deterioration sensitivity — alpha decay

Proposed empirical Greek. Use **Lambda**, not beta:

```
Λ_α = − dα / dt
```

The instantaneous rate of decay of the conditional alpha
supporting the position.

```
Λα ≠ Δ ≠ Γ ≠ β
```

---

## 7. Where volatility enters

Volatility is not automatically beta.

Two FIRST80 positions can both show:

```
Delta ≈ 0
Expected alpha ≈ +4¢
```

and still be different.

**Position A:** stable game state, small fluctuations, low
stop probability, alpha distribution stable.

**Position B:** violent repricing, repeated 10¢ swings, rapid
probability transitions, increasing stop hazard, alpha
distribution unstable.

Both might be delta-neutral at an instant.
Position B is more dangerous.

Empirical vega-like object:

```
ν_α = ∂α / ∂σ_state
```

What happens to remaining expected alpha when the volatility
of the underlying state increases?

```
VOLATILITY     measures movement dispersion
DETERIORATION  measures destruction of expected payoff advantage
```

High volatility does not necessarily mean alpha is
deteriorating. Alpha might decay steadily without particularly
high volatility.

The +4¢ figure above is an illustration, not a locked EV and
not a live number.

---

## 8. The Greek stack (research layers)

```
Layer 1 — Alpha
  α_t = E[Π | X_t]
  Do I still have an edge?

Layer 2 — Delta
  Δ_t = ∂V / ∂S
  How exposed am I to directional movement?

Layer 3 — Gamma
  Γ_t = ∂²V / ∂S²
  Does directional exposure accelerate as the state changes?

Layer 4 — Empirical Vega
  ν_t = ∂α / ∂σ
  How sensitive is remaining alpha to state / market volatility?

Layer 5 — Alpha deterioration
  Λ_t = − dα_t / dt
  How quickly is the empirical edge itself disappearing?

Layer 6 — Tail hazard
  h_t = P(damaging event | X_t)
  or dynamically:
  λ_t = instantaneous hazard of entering a damaging state
  How close is the position to the destructive payoff branch?
```

None of these layers are live calculator outputs on `:5191`.

---

## 9. The interesting optimization

The naive objective `Δ = 0` is not sufficient.

Closer form:

```
max_actions  α_t − C_execution − C_risk
subject to
  |Δ_t| ≤ Δ_max
  Λ_t   ≤ Λ_max
  λ_t   ≤ λ_max
```

and critically:

```
Every action must pass the execution hierarchy.
```

```
OBSERVED STATE
       ↓
OBSERVABLE OPPORTUNITY
       ↓
EXECUTABLE OPPORTUNITY
       ↓
ACTUAL EXECUTION
```

A1 hedge research is why the last constraint is
non-negotiable. A model cannot reduce delta using a hedge
whose fill exists only at:

- Level 1 — price threshold
- or even Level 2 — observable quote

when Level 3 — executable fill — has not been established.

---

## 10. Manage alpha, not merely price

DRE should not fundamentally ask:

```
Has the price gone down enough that we should hedge?
```

It should ask:

```
Given everything we now know, how much of the original
conditional payoff advantage remains, how exposed is that
remaining advantage to further state change, and what
action maximizes its expected retained value?
```

```
                 POSITION ENTERED
                       │
                       ▼
              FROZEN INITIAL ALPHA
                       │
                       ▼
              LIVE STATE EVOLUTION
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      DELTA         VOLATILITY      HAZARD
    exposure        of state      of damage
         │             │             │
         └─────────────┼─────────────┘
                       ▼
              ALPHA DETERIORATION
                 Λ = −dα/dt
                       │
                       ▼
                DRE DECISION
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
   HOLD               HEDGE              EXIT
    │                  │                  │
    └──────────── EXECUTION GATE ─────────┘
                       │
                       ▼
              ACTUAL EXECUTABLE ACTION
```

HOLD / HEDGE / EXIT here are research labels.
They are not BUY / SKIP and not a live order.

---

## Answer on “is deterioration beta?”

No. Do not define the deterioration rate as beta.

The idea contains elements of:

| Object | Question |
|---|---|
| Delta | Current directional exposure |
| Gamma | Acceleration / nonlinearity of that exposure |
| Vega-like | How state volatility affects the payoff distribution |
| Hazard rate | Probability of entering a damaging payoff regime |
| Alpha deterioration rate | Rate at which the established empirical edge is disappearing |

The last one is the central object:

```
Λ_{α,t} = − d/dt E[Π | X_t]
```

---

## Build order (protects against execution fiction)

Do **not** invent the derivative first.

Establish, from the frozen conservative distribution:

1. What exactly is `α_t`?
2. What state variables condition it?
3. How does the payoff distribution evolve after entry?
4. What is genuine deterioration versus normal volatility?
5. What observable signals precede a transition into the −40
   branch?
6. Which signals are causally available at time `t`?
7. Which proposed interventions are actually executable under
   the four-level hierarchy?

Only then develop deterioration-rate calculus.

```
Frozen Alpha Distribution
  → Conditional Alpha Surface
  → Delta Surface
  → State Volatility Surface
  → Tail Hazard Surface
  → THEN derive the Alpha Deterioration Rate
```

That order is the A1 lesson: do not build beautiful calculus
on top of execution fiction.

Choosin Texas supplies the frozen alpha / payoff identities.
Austin supplies the conditional neighborhood / stratum.
DRE consumes both. It does not invent a third universe.
