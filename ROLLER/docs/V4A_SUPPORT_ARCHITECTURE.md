# V4A support architecture

```text
INDEPENDENT SUPPORT > RAW OBSERVATION COUNT
```

10,000 observations from 100 games are not 10,000 independent games. Every F_t carries:

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

Floors live in [`config/fundamental_conditioning.json`](../config/fundamental_conditioning.json), not in Python literals:

```text
minimum_observations
minimum_unique_games
minimum_unique_dates
minimum_unique_seasons
```

The warehouse has one NBA season, so `minimum_unique_seasons = 1`. If any floor fails:

```text
value = null
status = INSUFFICIENT_SUPPORT
```

No 0.50, no market price, no global average, no nearest-neighbor fill.

`pbp_last_per_clock_bucket_v1` usually yields one row per game per cell, so `n_observations` often equals `n_unique_games`. Repeated observations still set `repeated_observation_warning` when a game contributes more than once.
