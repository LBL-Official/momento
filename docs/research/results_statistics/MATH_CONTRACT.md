# MATH_CONTRACT

**semantics_version:** 1.0.0  
**code_version:** results_math_v1.0.0

| Object | Definition | Unavailable when |
|--------|------------|------------------|
| Rate | successes / denominator (that statistic’s N) | denominator = 0 |
| Wilson 95% | Score interval, z = 1.959963984540054 | n = 0 |
| Clopper–Pearson | Exact binomial, optional | n = 0 |
| Observed return | `(exit_e4 − entry_e4) // 100` = existing `hyp_pnl_cents` | missing exit |
| Mean / median | arithmetic / midpoint | empty set |
| Sample std / var | `N−1` | N < 2 |
| Quantiles | Hyndman-Fan type 7 | empty set |
| Skew G1 / excess kurtosis G2 | bias-adjusted | N < 3 / N < 4 |
| Trade Sharpe | mean / s · **unannualized** | N < 2 or s = 0 |
| EV t-interval | `mean ± t_{0.975,N−1} s/√N` | N < 2 |
| Bootstrap | percentile, 10 000, seed 20260909 | N < 2 |
| MAE / MFE | min/max later-bar Δ¢ after entry | no later bars |
| Drawdown | peak-to-trough, chronological `entry_ts` | no returns |
| Breakeven | `L / (W+L)` for W>0, L>0 | payoffs invalid |

Wilson is a CI for a binomial proportion. It is not a CI for edge.
