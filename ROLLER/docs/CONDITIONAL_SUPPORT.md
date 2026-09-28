# Conditional support

Every baseline, residual, and surface carries support metadata:

```text
n_observations
n_unique_games
n_unique_dates
n_unique_teams
n_unique_seasons
first_observation_time
last_observation_time
repeated_observation_warning
effective_n = null
effective_n_status = NOT_IMPLEMENTED
```

Floors live in `config/conditioning.json` (`min_unique_games`, `min_observations`).

```text
1,000 observations ≠ 1,000 independent basketball games
```

Possessions nest in games. Observations nest in possessions and games. Games nest in seasons.

If support is below the floor:

```text
baseline expected value is omitted
residual_status = INSUFFICIENT_SUPPORT
value is undefined
undefined ≠ 0
```
