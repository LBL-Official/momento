# Future labels

`L_{t→}` is not part of `I(t)`.

```python
db.labels(observation_id=...)
# or explicit research access:
db.labels(internal_game_id=..., as_of=...)
```

```python
db.dataset(..., dataset="terminal_labels", as_of=...)  # fails
db.dataset(..., dataset="game_state_features", as_of=...)  # fails
```

`db.observation(...)` never includes labels.

## Provenance (every label)

```text
label_name
label_version
observation_id
observation_time
horizon_definition
label_available_only_after
contains_future_information = true
```

## V2 labels

| Name | Horizon | `label_available_only_after` |
|------|---------|------------------------------|
| `home_win` | terminal | `result_available_at` |
| `away_win` | terminal | `result_available_at` |
| `home_score_terminal` | terminal | `result_available_at` |
| `home_score_change_next_60_seconds` | 60s | `observation_time + 60s` (or later event availability) |
| `home_score_change_next_300_seconds` | 300s | `observation_time + 300s` (or later event availability) |
| `score_path_next_60_seconds` | path | same as the 60s horizon |
| `score_path_next_300_seconds` | path | same as the 300s horizon |
| `home_score_change_next_{1,3,5}_possession` | NBA / WNBA / NCAAB possessions when reconstructed | end availability of the Nth later possession |
| `kalshi_yes_settled` | Kalshi ticker expiration (W) | market `result_available_at` |
| `first80_trigger` | Frozen FIRST80 status | first-80 candle time |
| `first80_t40` | First later tradable close ≤40 | T40 candle time |
| `first80_entry_slice` | Clock snap at entry | first-80 candle time |

Horizons come from `config/labels.json`. No `FIRST75`. FIRST80 names are research labels only and stay off `O_t`. Use `db.first80()` for the frozen book. See [RESEARCH_OBJECTS.md](RESEARCH_OBJECTS.md).

Barrier labels remain research-supplied generic `operator` + `value`. T40 is an explicit FIRST80 label, not a generic barrier row.

V1 `game_state_features.csv` still exists for pipeline compatibility. It is tagged `contains_future_information=true` and is rejected by public `dataset()`.
