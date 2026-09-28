# Feature store — Test 2 families A–I

All predictors are causal: `source_ts ≤ ENTRY_DECISION_TIME`.
Possession windows `{1,3,5,10,20,30}` are all computed; none is assumed optimal.

| Family | Code | Contents | Resolution |
| --- | --- | --- | --- |
| A | `game_state` | Quarter, official remaining, elapsed, completion %, possession index, estimated remaining possessions, score differential, lead flag | Instantaneous snap |
| B | `possession_path` | Points, net/abs score change, turnovers, OREB, FTA, lead changes, timeouts, scoring variance, directional persist/reversals, offensive efficiency | Rolling possessions |
| C/D/H | `game_dynamics` | Velocity, volatility, acceleration, instability, entropy, named physics (momentum/inertia) as **DERIVED PROXY** | Possession space, not 5-minute stdev |
| E | `market_state` | Yes bid/ask, estimated mid, spread, distance from 80¢ | 1m TOB candle |
| F/I | `market_path` | Possession-normalized market change/range/reversals with alignment-quality shares | Overlay quality labeled |
| G | `coupling` | Market response per score, after turnover/lead-change; robust to near-zero denominators | DERIVED PROXY, not causal proof |

Unavailable (must stay null / false): L2 imbalance, queue, true order-book event velocity.

Pregame: only information available before tip (first valid pre-window tradable mid if present). No future-season stats.

Targets:

- Primary: `Y_40_CLOSE` / `SURVIVE_40`
- Secondary: wick, eventual winner (`TARGET_ONLY`), time-to-40 (1m resolution — do not claim finer precision)
