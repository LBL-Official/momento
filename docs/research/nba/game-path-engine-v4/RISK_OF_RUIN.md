# Risk of ruin

Ruin is not “zero in 400 paths.”

Report \(P(\min Equity_t < \alpha Equity_0)\) for
\(\alpha\in\{0.80,0.70,0.50\}\) (20%, 30%, 50% capital loss).

Methods:

- IID Bernoulli with \(p\) stressed at 74, 72.5, 70, 68, 67, 66%
- Beta posterior predictive: \(p\sim\mathrm{Beta}(910+\alpha,320+\beta)\)
  with weak \(\alpha=\beta=1\), then simulate (parameter uncertainty)
- Month-block bootstrap of historical trade R (dependence)

Trades are not assumed independent. Finite-sample zeros are labeled
**not observed in this Monte Carlo**, not \(P=0\).
