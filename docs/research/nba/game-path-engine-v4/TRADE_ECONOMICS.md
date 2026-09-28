# Trade economics

Predictive metrics \(\neq\) profitability.

Research payoff in R-units: survive \(+1R\), barrier \(-2R\), \(EV=1-3q\).

Cash-flow mapping for sizing research (entry 80¢, stop ~40¢, win +20¢):

```text
win  = +0.25 × allocated notional
loss = −0.50 × allocated notional
```

These are **research assumptions**, not KalshiFeeModel and not fills.
Exit at 40 is the frozen close-path definition, not a verified taker fill.

Policies are evaluated on EV, variance, Sharpe (LOW_SHORT_SAMPLE),
Sortino, CVaR, max DD, acceptance rate. No policy is promoted on
in-sample terminal equity alone.

Log-growth for fraction \(f\) of equity (research):

\[
g(f)=p\log(1+0.25f)+(1-p)\log(1-0.50f).
\]

Full Kelly is sensitivity analysis only. Default comparison is
fraction-of-**current** equity after losses (no chase).
