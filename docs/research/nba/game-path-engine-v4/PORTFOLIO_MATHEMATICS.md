# Portfolio mathematics

Do not treat the week’s trades as IID.

Compare:

- fixed notional
- fraction of current equity
- high-water-mark fraction
- drawdown schedule (TRAIN/VAL examples, freeze on VAL): 0–5% → 1.0,
  5–10% → 0.75, 10–15% → 0.50, 15–20% → 0.25, 20%+ → 0
- quarter / half / full Kelly of the 80/40 cash map (research only)

Constrained view: growth vs drawdown vs CVaR. Pareto table, not one winner.

Capital utilization: committed / equity, peak concurrent (cap 5 as a
research constraint, not live MLB 12.5%).

Same-day and same-week barrier clustering is measured and used in
block bootstrap.

Starting bankroll $10,000 and 2% fraction are **research defaults**,
not production allocations.
