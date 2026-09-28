# Frozen 80/40 baseline (do not rebuild)

Path Engine V1 **imports** the first-80 definition from
`apps/nba-data/scripts/nba_80_40_execution_audit.py`. It does not fork it.

If observation counts do not match, the pipeline exits 1.

## Game-window tradable first-80

First valid two-sided uncrossed spread ≤ 10¢ with `yes_bid_close ≥ 8000`
after a prior tradable close < 80, inside the game-day window.

## Close-path 40 (primary Y_40)

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

Wilson 95% CI on survival (from the frozen audit): 71.46% – 76.36%.

First-80 team eventually Kalshi YES: 1,019 / 1,230 = 82.8%. That is **not**
the Path Engine target.

## Execution-realism audit (read-only; do not overwrite)

| Scenario | Survival | n |
| --- | ---: | ---: |
| Original close-path | 74.0% | 1,230 |
| Drop LOW fills | 73.9% | 1,146 |
| HIGH only, close-stop | 73.3% | 1,071 |
| Wick-stop, all fills | 69.0% | 1,230 |
| Conservative HIGH + wick | 69.3% | 1,071 |

Payoff used by Path Engine V1 economics: survive **+1R** (+20¢), stop **−2R**
(−40¢). Fees are not in `EV_gross`. Production KalshiFeeModel is unresolved.

## Canonical wick labels (V1)

| Column | Role |
| --- | --- |
| `target_close_40` | PRIMARY Y_40. Post-entry completed candle only. Must count 320. |
| `target_wick_40_post_entry_bar_only` | Formal secondary. |
| `target_wick_40_including_entry_bar` | Diagnostic. Same-bar wick allowed. |
