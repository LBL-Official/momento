# Risk model (research only)

Do not write these rules into the live Risk Decision Engine.
Do not modify `config/` live gates.

---

## Proportional sizing

Default: fraction `f` of **current** equity allocated as cash at 80¢.

```text
B_{t+1}  =  B_t (1 + r_t)
r_t      =  f_t · R_t
```

`R_t` is the percentage return on allocated capital, not on face
notional. After a loss, dollar size shrinks automatically.

```text
Bankroll $10,000, f=5% → $500 allocated
After a 1% portfolio loss → $9,900, 5% = $495
```

Do not chase losses by holding dollar exposure constant.

Research fractions: 1%, 2%, 3%, 5% of current equity.
5% allocated is not 5% bankroll risked (risked at a 40¢ stop is about
2.5% of bankroll when f=5%).

---

## Governors (research)

### Governor 0

Pure fractional sizing.

### Governor 1

| Drawdown | Size vs normal |
| --- | ---: |
| 0–5% | 100% |
| 5–10% | 75% |
| 10–15% | 50% |
| 15–20% | 25% |
| 20%+ | halt new entries |

### Governor 2

Posterior-edge sizing:

```text
size  proportional to  P(p_t > p_BE,net | D_t)
```

Prior for research: p ≈ 72.5% (haircut, not a claim of the true rate),
Beta(α, β) with strength 40 → α=29, β=11.

After S survivors and F failures:

```text
p | D  ~  Beta(α+S, β+F)
```

Report posterior mean, median, 95% interval, and
`P(p > p_BE,net | D)`.

Do not treat a short losing streak as proof the edge disappeared.

---

## Non-stationarity

- Rolling windows: last 25 / 50 / 100 trades
- Historical posterior vs recent live posterior
- CUSUM and beta-binomial predictive probability

Distinguish **NORMAL VARIANCE** from a **STATISTICALLY MEANINGFUL
REGIME CHANGE**. Do not auto-declare edge decay.

---

## Drawdown / ruin

Proportional sizing approaches zero rather than conventional ruin.
Report `P(capital decline > X)` for X in {5%, 10%, 20%, 30%}, max-DD
distribution, time underwater, recovery time, terminal wealth.

Methods:

- A: IID Bernoulli (mathematical baseline only)
- B: weekly / monthly block bootstrap (preserves clustering)
- C: regime stress at p in {74%, 72.5%, 70%, 68%, 67%, 66%, 65%}
  plus fill / fee / stop / capacity deterioration

Monte Carlo: at least 100,000 paths. Label:

```text
SCENARIO ANALYSIS
NOT A PERFORMANCE FORECAST
```
