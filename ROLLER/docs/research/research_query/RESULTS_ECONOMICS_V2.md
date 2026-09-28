# Results Economics v2

Research measurement and inference for ROLLER Results.

Package: `ROLLER/roller/results_math/`  
(`research_query/` is not modified. Results Math consumes the existing result envelope.)

Versions:

- `RESULTS_MATH_SEMANTICS_VERSION = 2.0.0`
- `RESULTS_MATH_SCHEMA_VERSION = 2.0.0`
- `RESULTS_MATH_CODE_VERSION = results_math_v2.0.0`

## 1. Purpose

Translate a measured research population into finite-sample economic analysis.

This is not a trading strategy, alpha score, execution simulator, live P&L engine,
Risk Decision Engine, predictive probability model, or Bayesian posterior.

## 2. Observed path EV

```text
π_i = exit_close_i − entry_close_i
OBSERVED PATH EV = mean(π)
```

CANDLE PATH ≠ FILL. Missing exit is not 0.

## 3. Book-price EV

Only when WIN/LOSS chips are explicit:

```text
EV_book = P(WIN)×(WIN_price − entry) + P(LOSS)×(LOSS_price − entry)
        = l + p(w − l)
```

P(WIN) ≠ EV.

## 4. Settlement EV

Only when measured Kalshi YES/NO exist:

```text
EV_settlement = P(YES)×(100 − entry) + P(NO)×(0 − entry)
```

PATH WIN ≠ SETTLEMENT YES. PATH LOSS ≠ SETTLEMENT NO.  
Missing terminal is not NO and is not 0.

## 5. Wilson inference

Wilson 95% interval for the binary WIN rate.

When payoffs exist, transform:

```text
EV_low  = l + p_low(w − l)
EV_high = l + p_high(w − l)
```

Reverse endpoints if `w < l`.  
The economic question is whether the EV interval excludes zero.

## 6. Exact-binomial inference

Clopper–Pearson 95% interval for p, then the same EV transform.

Not Bayesian. Not P(EV > 0).

## 7. Continuous EV inference

Student-t interval on the observed return vector:

```text
SE = s / √N
t  = mean / SE
df = N − 1
H0: EV = 0
```

## 8. Bootstrap

Deterministic percentile bootstrap, 10,000 iterations, envelope seed.

Reports EV / median / Sharpe / ending capital / drawdown percentile intervals
and the **derived resample fraction** of means > 0.

BOOTSTRAP SHARE ≠ POSTERIOR. Not P(EV > 0).

## 9. Game clustering

Group by `internal_game_id`.  
If one observation per game: **COINCIDENT** with the observation result.  
Do not invent extra independence.

N ≠ INDEPENDENT SAMPLE SIZE.

## 10. Date clustering

Resample dates as clusters when `N_dates ≥ 2` and dates collapse observations.

Insufficient clusters → UNAVAILABLE.

## 11. Sharpe

```text
UNANNUALIZED OBSERVED PATH SHARPE = mean(π) / sample_std(π)
```

Never annualized. Games are not a fixed-frequency IID series.

## 12. Sortino

```text
Sortino = mean(π) / downside_deviation(π, 0)
```

UNAVAILABLE if downside deviation is 0.

## 13. Drawdown

Three objects:

1. Per-contract chronological path drawdown
2. Fixed-allocation sequence drawdown
3. Bankroll share of that sequence

HISTORICAL DD ≠ FUTURE DD.

## 14. $1,000 capitalization

MODEL-ASSUMED overlay: $20,000 bankroll, 5%, $1,000 allocation.

Contracts = floor(allocation / sizing_price).  
Sizing uses the explicit query reference, never the silent mean touch.

CAPITALIZED OBSERVED RETURN ≠ EXECUTED P&L.

## 15. Cost sensitivity

`net EV = gross EV − cost` on 0 / 0.25 / 0.5 / 1 / 2 / 3 / 5¢.

Break-even total cost = gross EV. Not a measured platform fee.

## 16. Entry-price sensitivity

Hypothetical binary 100/0 at 50–85¢ and a 1¢ continuum 1–99¢.

`EV = 100p − entry`. Increasing entry 1¢ decreases EV 1¢.

## 17. Risk of ruin

NOT COMPUTED without an explicit stochastic bankroll model.

## 18. Missingness

Every unavailable statistic has a reason. Never substitute 0 for missing.

## 19. Interpretation rules

- Point estimate ≠ proof of edge
- Zero inside CI is stated explicitly
- No TRADE QUALITY / ALPHA / BUY / SELL
- No P(EV > 0)

## 20. Non-goals

Does not change FIRST80, generic query semantics, Base Terminal Efficiency,
Kalshi settlement inference, Risk, Execution, or live trading.
