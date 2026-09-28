# Dependence

V2 observations are not i.i.d. draws. Treat them as dependent.

## Known dependence

- Multiple `O_t` from the same game share one score path and one market path.
- Team `*_pre` features share completed games.
- Possession segments from one game are sequential, not independent.
- Horizon labels from nearby cutoffs overlap.

## What V2 does not do

- Effective-n theater
- Train / validation / OOS splits (`db.research` is a V3 stub)
- Unsupervised regime clustering
- Claiming that more timestamps mean more independent samples

Deterministic buckets in `config/regimes.json` (`period`, minute, progress, margin) are labels for slicing, not independence corrections.

When a later research layer samples `O_t`, it must state the clustering unit (game, team-game, possession) explicitly.
