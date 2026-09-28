# Day-to-day information states

D2D materializes views of `I(t)`. The CSVs are snapshots. The choke point remains `as_of`.

## Feature-engine invariant

For team `i` entering game `g`, ordered by `result_available_at` (not merely game date):

```text
X_pre(i, g) = f(G_i,1 … G_i,g-1)
```

Never include `G_i,g`. Process: sort by `result_available_at` → group by team → shift → roll.

Required `*_pre` fields: games, wins, losses, `win_pct_pre` (integer E4, `5000` = 0.5000), home/away splits, last-5, last-10, `rest_days`.

## Layers

### L1 — `d2d_daily.csv`

Team state entering date `d`, using completed games with `result_available_at < UTCStart(d)`.

`available_at` on the daily row is the last prior `result_available_at` so `as_of(d)` includes the entering-`d` snapshot under the half-open filter.

### L2 — `team_game_features.csv`

Pre-tipoff state per team per game. Feature `available_at` is the prior game's `result_available_at`, or `scheduled_start` if there is no prior result.

Query “state immediately before tip” with `as_of=scheduled_start`.

NCAAB research features default to `P5_vs_P5` via `config/conferences.json`. Identity still stores non-P5 warehouse games.

### L3 — `Roller.game_state(internal_game_id, as_of)`

Returns:

- latest PBP row with `available_at < as_of`
- attached L2 pre-game features from `I(as_of)`
- latest mapped candle with `available_at < as_of`

`game_state_features.csv` stores **terminal** labels only (`*_terminal`). Do not confuse them with `*_pre`.

## Alignment

```text
state(t) = latest PBP where available_at < t
```

Implemented as `pandas.merge_asof(..., direction="backward", allow_exact_matches=False)`. A PBP row at exactly `t` is not attached to a candle that closes at `t`.
