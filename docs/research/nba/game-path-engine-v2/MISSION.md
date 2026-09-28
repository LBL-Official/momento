# Mission

Build a **structured experimental engine** for:

> Given the basketball game state, the trajectory of the game, the
> trajectory of the score, and the trajectory of the market — **how** did
> this contract arrive at 80¢, and does that path change
> `P(40 barrier | arrival at 80)`?

## In scope

- Join official NBA PlayByPlayV3 to frozen first-80 observations.
- Document and audit time alignment (hard gate).
- Construct causal `Z_τ80` from game state, score path, lead path,
  game volatility, scoring runs, and market path.
- Hierarchical bucket tests (univariate → pre-specified interactions →
  shallow trees).
- Multiple-testing control and an append-only experiment ledger.
- Economic evaluation `EV = 1 − 3q` against the 26.02% baseline.
- Portfolio / sizing / risk-of-ruin research with configurable parameters.
- Exactly one scientific verdict (A/B/C/D) and exactly one production
  status. No automatic live change.

## Out of scope

- Modifying the 80/40 strategy, execution, frozen audit, or Path Engine V1.
- Inventing per-play wall-clock timestamps.
- Inferring tip-off from Kalshi market open.
- Winner prediction as a research target.
- Unrestricted feature mining on OOS.
- sklearn / deep models. Numpy logistic, elastic net, and depth-2 trees
  only.

## Success is honest

A valid completion is **Verdict D / NO FILTER** if the game-path hypothesis
space is tested and no robust, capacity-adequate, economically meaningful
conditional edge survives validation and a single OOS pass.

Do not make a filter look good.
