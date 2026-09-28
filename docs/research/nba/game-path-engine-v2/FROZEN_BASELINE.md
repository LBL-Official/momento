# Frozen 80/40 baseline (do not rebuild)

Game Path Engine V2 **imports** the first-80 definition from
`apps/nba-data/scripts/nba_80_40_execution_audit.py`. It does not fork it.
If counts do not match, the pipeline exits 1.

## Game-window tradable first-80

First valid two-sided uncrossed spread ≤ 10¢ with `yes_bid_close ≥ 8000`
after a prior tradable close < 80, inside the game-day window.

## Close-path 40 (primary `Y_40_CLOSE`)

First subsequent completed candle **after** the first-80 candle end with
tradable `yes_bid_close ≤ 4000`.

| Quantity | Count |
| ---: | ---: |
| Games | 1,362 |
| First-80 (settled) | 1,230 |
| Survive close-path 40 | 910 |
| Hit close-path 40 | 320 |
| Never crossed 80 | 132 |

```text
q_unconditional = 320 / 1230 = 26.0163%
survival        = 910 / 1230 = 73.9837%
EV_gross        = 1 − 3q     ≈ +0.2195 R
breakeven q     = 33.3333%
```

Wilson 95% CI on survival (frozen audit): 71.46% – 76.36%.

First-80 team eventually Kalshi YES is a **settlement diagnostic**, not the
V2 target.

## Wick (secondary `Y_40_WICK`)

`yes_bid_low ≤ 4000` on a completed candle **after** entry (same quality
filter as the audit). Execution-stress object. Must not replace close-path
as the primary research target.

Payoff used by V2 economics: survive **+1R** (+20¢), stop **−2R** (−40¢).
Fees are not in `EV_gross`. Production KalshiFeeModel is unresolved.
Candle data does not prove maker fills.

## Splits (copied from the frozen audit)

```text
TRAIN       game_date ≤ 2025-12-31
VALIDATION  2026-01-01 .. 2026-03-15
OOS         game_date > 2026-03-15
```
