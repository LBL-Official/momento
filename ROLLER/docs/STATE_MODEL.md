# State model

```text
S_t  = what was true and observable
Γ_t  = how that state was reached
O_t  = the assembled research object
L_{t→} = what happened afterward (explicit API only)
```

```text
TEMPORAL TABLES → PIT CHOKE POINT → OBSERVATION ASSEMBLER → O_t
```

`O_t` is assembled at query time. V2 does not materialize `everything_at_every_timestamp.csv`.

## Constitutional visibility

```text
visible(row, t)  iff  row.available_at < t
```

`event_time` does not grant visibility. `available_at == t` is hidden.

## Observation identity

```text
observation_id = OBS_{internal_game_id}_{YYYYMMDDTHHMMSSmmmZ}_V{state_schema_version}
```

Same game + same cutoff + same `state_schema_version` → same id. Changing `2.0.0` to `2.1.0` changes the id.

V2 `state_schema_version` is `2.0.0`: score, clock, possessions (NBA), team state, player state, market state, incomplete lineups, schema-only / not-supported information, trajectory.

## Sections on `O_t`

Every family carries `source_availability_status`:

`REAL | PARTIAL | INCOMPLETE | SCHEMA_ONLY | NOT_SUPPORTED`

Never a bare `null` without status.

| Section | NBA | WNBA / NCAAB |
|---------|-----|----------------|
| `GAME_STATE` | REAL when PBP visible | REAL when normalized plays visible |
| `TEAM_STATE` | REAL (`*_pre` + in-game score) | REAL where features exist |
| `PLAYER_STATE` | REAL from `personId` | NOT_SUPPORTED |
| `LINEUP_STATE` | INCOMPLETE (subs, no starters) | SCHEMA_ONLY |
| `MARKET_STATE` | REAL integer E4 candles | REAL where MAPPED |
| `INFORMATION_STATE` | NOT_SUPPORTED | SCHEMA_ONLY |
| `TRAJECTORY` | REAL, backward only | REAL from visible events |
| `POSSESSIONS` | REAL + categorical status | NOT_SUPPORTED |

Labels are not a section of `O_t`.

## State-transition object (schema-only)

V2 defines the contract and does not mine transitions.

```text
transition_id
observation_id_start
observation_id_end
type
sequences
duration
```

No prediction engine. No unsupervised regimes.

## Public API

```python
db.dataset(...)      # PIT-safe tables only
db.observation(...)  # S_t + Γ_t
db.labels(...)       # L_{t→}
db.research(...)     # V3 stub
```

V1 methods remain: `as_of`, `dataset`, `get_team_state`, `game_state`.
