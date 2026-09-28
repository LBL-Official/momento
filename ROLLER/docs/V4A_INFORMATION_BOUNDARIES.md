# V4A information boundaries

```text
visible(row, t) iff available_at < t
```

`roller/timeutil.py` is unchanged. Equality is hidden.

## Two clocks for F_t

A historical row is eligible only when **both** hold:

```text
state_available_at < observation_cutoff
result_available_at < observation_cutoff
```

`state_available_at` is the PBP `available_at` of the comparable intra-game state.

`result_available_at` is the last scored PBP wall time on `games.csv`. It is **not** `games.available_at` (identity / start proxy).

`db.labels()` exposes the same outcome clock as `label_available_only_after`.

## Current game

Excluded by `internal_game_id`, not only by timestamps.

## Observation vs fundamental

```text
db.observation(...)   → I_t / O_t
db.fundamental(...)   → F_t using prior Y
db.labels(...)        → current-game future labels
db.response(...)      → forward market/score responses
```

`O_t` does not contain F_t. After a game ends, V1 may unmask `GAME_STATE.game.home_win` because `result_available_at < cutoff`. That V1 behavior is preserved. `fundamental()` still drops the current `game_id`.

## Dataset firewall

`dataset()` rejects `fundamental`, `fundamental_*`, `*_fundamental`, and `v4a_fundamental*`. The error says `use db.fundamental()`.

## No cache

F_t is assembled at query time. A derived corpus, if present, is re-filtered with the observation cutoff. Results are not cached across cutoffs.

## `db.fundamental` time source

Cutoff comes from `parse_observation_id`, the same pattern as `response` / `baseline`. `InformationSet.cutoff` is not used.
