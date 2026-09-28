# Austin dataset contract

Research only. Candle path is not a fill. PBP is not candle PIT.

## Trade universe

Authority: `research/first80_asked_six_chatgpt_export/first80_asked_six.csv`

Filter: sport NBA, slice Q2 or Q3.

```
N_trades = 604
Q2 = 314
Q3 = 290
S = not T40 = 450
W and T40 = 55
L and T40 = 99
book = 20*450 - 40*154 = 2840 cents
```

`LOCK_MISMATCH` if any of those integers fail.

```
trade_id = sha256(event_id|ticker|timestamp_utc|FIRST80)[:16]
```

One FIRST80 trigger per event. Same identity as reverse-features.

## What is a trade vs a snapshot

`N_trades = 604` is the Choosin lock. It does not change.

KNN rows are path-state snapshots at time t >= entry:

- entry: FIRST80 print, travel = 0
- path: each post-entry 1m yes_bid_close
- hedge_42: first favorite close <= 42 after entry
- hedge_41: first favorite close <= 41 after entry

FINAL settlement price (0 / 100) never enters the feature matrix.

A 42 cent query is matched to historical mid-path states, not only the
604 entry prints and not only T40 prints.

Display `N_trades`, `N_path_complete`, `N_path_partial`,
`N_path_unavailable`, `N_knn_observations`. Fail closed if
`N_trades ≠ 604`.

```
PATH_COMPLETE     favorite 1m path from entry to last tradable bar,
                  opponent joined, PBP present, no gap > 300s
PATH_PARTIAL      some post-entry bars, missing opponent and/or PBP
                  and/or a gap > 300s
PATH_UNAVAILABLE  no post-entry bars (ledger row kept)
```

Do not drop a trade from `N_trades` because bars failed to join. Mark
path features UNAVAILABLE and exclude that trade from PCA/KNN.

## Join sources

- asked-six CSV: identity, entry state, T40/W labels (authority)
- warehouse 1m TRADABLE_YES_BID: favorite + opponent path after entry
- warehouse markets: opposite ticker
- warehouse PBP: score/clock after entry (`PBP_SEQUENCE_NOT_PIT`)
- L2 / queue / fills: `SOURCE_UNAVAILABLE` / `FILL_UNAVAILABLE`

Join key for bars: ticker. Opponent: other team_side on the same
internal_game_id. PBP: internal_game_id, merge_asof backward on
event_timestamp <= snapshot time.

available_at is the candle PIT field for bars. PBP timestamps are not
aligned to candles. PIT alignment stays OPERATION_REQUIRED.

## Outcome space (not features)

After snapshot t only:

- settlement YES / NO
- ledger 80/40 PnL if the first favorite close ≤40 after t (`hit_40_after`)
- if t is already at/after T40: `pnl_8040_after_t = NOT_APPLICABLE`
- hold-to-settlement PnL (`pnl_hold_after_t`, +20 / −80) even after T40
- hit_40 after t, first price <= 40
- MAE / MFE after t (replay) vs MAE / MFE to t (feature)
- hedge path events 41 / 42 then opponent close >= 40

price <= 40 is a path event. It is not a fill.

## Books Austin must not mix

- 604 NBA 2Q union 3Q: default universe
- 936 derived four: out
- 1182 asked-six: out
- 1230 NBA FULL FIRST80 / hedge V1: REFERENCE_ONLY
- 797 path-FE WF pool: out

## Reuse map

- Identities: `roller.nba_8040_reverse_features.instances.load_instances`
- Bars: `roller.nba_8040_reverse_features.bars`
- Ledger EV: `roller.choosin_texas.ev`
- Locks: NBA_PATH_N / reverse-features Q2 union Q3 integers

Do not reuse reverse-features PCA (not a signal).
Do not reuse path-FE enter_skip or Family E.
