# Tennis state model

Research observation only. Not a trading system. Not a fill. Not live execution.

```
SEQUENCE-ONLY PBP ≠ PIT PBP
LAST TRADE ≠ YES BID
CANDLE PATH ≠ FILL
OFFICIAL W = KALSHI SETTLEMENT
```

## Row contract

Canonical PBP is produced by `roller.tennis.pbp`. Snap (`roller.tennis.snap`) and
state (`roller.tennis.state`) consume that row. They do not re-parse MCP `Pts`.

| field | meaning |
|---|---|
| `points_server_raw` / `points_returner_raw` | Verbatim MCP `Pts`, server-first, score **before** the point |
| `points_p1_raw` / `points_p2_raw` | Same score re-oriented to player 1 / player 2. `None` if server unknown |
| `point_score_raw` | Verbatim `Pts` string |
| `point_score_orientation` | `SERVER_FIRST` |
| `is_tiebreak` | Derived per game from score tokens. **Not** `TbSet` |
| `source_tb_set` | MCP `TbSet` retained; ignored for state |
| `game_number` | Within-set game |
| `source_game_number` | MCP `Gm#` (match-cumulative) |
| `event_timestamp` | Always `None` on MCP rows |
| `pbp_basis` | `SEQUENCE_ONLY` on MCP; `TIMESTAMPED_OBSERVED` only from a future timestamped feed |
| `pit_joinable` | `False` on MCP |

`AD` is the token `"AD"`. It is never `50`, `4`, or a boolean.

Missing is `None`. Missing is not `False`, `0`, or `""`.

## PIT snap

ASOF backward: latest timestamped, `pit_joinable` row with `event_timestamp <= market_ts`.

| input | snap status |
|---|---|
| `TIMESTAMPED_OBSERVED` + prior point | `REAL` |
| only `SEQUENCE_ONLY` | `NO_POINT_DATA` |
| no prior timestamped point | `NO_POINT_DATA` |
| empty PBP | `NO_POINT_DATA` / `NO_PBP_EVENTS` |

No nearest-future. No interpolation. No `Time` column. No even spacing.

Set/game windows (`S1`, `G1-3`, `G10+`, …) fail closed when set/game is missing.
A basketball clock window on tennis is rejected.

## Three leads — never collapsed

`set_lead`, `game_lead`, and `point_lead` are independent signed integers
(player-1 view, then flipped for `yes_player`). They are never summed.

`point_lead` uses ordinal ranks `{0,15,30,40,AD} → {0,1,2,3,4}` in a game and
raw counts in a tiebreak. Unknown `is_tiebreak` → `None` (the scales do not mix).

Break point is `False` inside a tiebreak (determinate: there is no service game
to break), `None` when server or score is missing.

Best-of-3 / best-of-5 is `sets_to_win = best_of // 2 + 1`. No tournament name
branching. Tiebreak target defaults to 7 and is a parameter (10-point match TB
is not inferred from a point row).

## Contract-relative view

`yes_player` is which MCP slot (1 or 2) the Kalshi YES side refers to.

`yes_serving` / `yes_returning` / `yes_set_lead` / `yes_game_lead` / `yes_point_lead`
are that orientation. Unknown server or unknown yes-slot → `None`, and TE
filters fail closed.

Basketball `home_score` / `away_score` / a single point differential are not
invented from tennis state.
