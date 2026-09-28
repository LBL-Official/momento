# Austin Conditional EV Query Engine — engineering report

Research only. Numbers measured after `python -m roller.austin`
(2026-09-18T04:22:23+00:00). No live capability.

```
LIVE FEED         UNAVAILABLE
EXECUTION         DISABLED
submits           false
CANDLE PATH    ≠  FILL
TRAINING N        604
QUERY GAMES    ≠  TRAINING N
```

## Files

Package: `ROLLER/roller/austin/`

Added or extended: `outcomes.py`, `raw_state.py`, `features.py`,
`knn.py`, `analyze.py`, `dataset.py`, `hedge.py`, `walkforward.py`,
`games.py`, `reconstruct.py`, `query.py`, `integrity.py`, `api.py`,
`build.py`, `fort_worth.py`, `snapshots.py`, `config.py`, `paths.py`.

Mounted on existing ROLLER `:8791`:

```
GET  /austin/games
GET  /austin/games/{id}/moments
GET  /austin/calibration
GET  /austin/integrity
POST /austin/query
POST /austin/query/historical
```

UI: `frontend/choosin-texas` `#/austin` on `:5182`. Same Vite app.
Fort Worth stays a read-only contract. No remount in
`frontend/roller-terminal`.

SSOT: `research/austin/features/registry.yaml`.
Artifacts: `research/austin/artifacts/`.

## Modes

```
PRE_80     no FIRST80 entry at or before t
           entry_* / price_travel / time_since_entry = NOT_APPLICABLE
           knn_status = INSUFFICIENT_SAMPLE
           reason     = NO_ENTRY_IN_FITTED_SPACE
INTRA_80   entry observed, not settled
POST_80    any t ≥ entry, including after T40
```

ENTRY_SOURCE ∈ {CHOOSIN_604_CSV, ASKED_SIX_FIRST80,
WAREHOUSE_FIRST_GE_80, NONE}.

Warehouse first close ≥80 is reconstruction only — not a live FIRST80
rule.

## Model

```
model_version     austin_v2
dataset_version   choosin_nba_2q3q_604
pca_version       austin_pca_v1
feature_schema    austin_features_v1
PCA k             5
PCA n             48752
explained         0.386, 0.177, 0.144, 0.143, 0.060
cumulative        0.911
K                 25
distance          euclidean_pca
weight            1 / (d + ε)
```

Queries never fit PCA. Queries never enter training.

## EV and CI

```
EV_DEFINITION     hold_80_to_settlement
formula           20S − 80(1−S)
KNN target        pnl_hold_after_t
secondary         pnl_8040_after_t when applicable
                  20S − 40(1−T40_after)
if t ≥ T40        pnl_8040_after_t = NOT_APPLICABLE
                  pnl_hold_after_t still settles
CI                95% weighted bootstrap
B                 1000
seed              80
label             95% CI — weighted bootstrap
```

A mean is not a probability.

UI/API labels only: CONDITIONAL EV FROM CURRENT STATE, 95% CI,
HISTORICAL SUPPORT, STATE CHANGE FROM ENTRY.

Forbidden: EXIT NOW, SELL, HOLD, CONFIDENCE, BUY, SKIP.

## Walk-forward (entry, locked)

```
TRAIN months      2025-10 … 2026-01    n=351
VAL months        2026-02 … 2026-03    n=182
OOS months        2026-04 … 2026-06    n=71
VAL mean actual   +5.71 ¢
VAL mean KNN EV   +3.45 ¢
OOS mean actual   +3.10 ¢
OOS mean KNN EV   +3.06 ¢
```

## Snapshot OOS (paper query, added beside entry WF)

```
n                 6040
mean abs error    20.61 ¢
```

## Ladder (mid-path recognition)

42¢ POST-80 fixture: query current=42, travel=−38, neighbor median
current=41, travel=−39. Not an ~80¢ neighborhood.

See `INTEGRITY_AUDIT.md` for the full 80/70/60/50/42/41/40 table.

## Path coverage

```
N_trades              604
N_path_complete       520
N_path_partial        84
N_path_unavailable    0
N_knn_observations    48752
```

## 41 vs 42

```
TRIGGER_RESOLUTION    1m_close
n_first_le_42         443
n_first_le_41         443
n_42_without_41       18
n_same_bar_42_and_41  425
```

## Calibration

```
status            INSUFFICIENT_SAMPLE
reason            OOS top/mid/bot 20.000 / −15.714 / 0.000 do not separate
default band      3%
role on POST-80   ENTRY_SIZING_REFERENCE
```

Decile table is on disk and on the page. n=71 stays visible.

## Query universe

Warehouse: 1362 games / 2724 markets. `in_austin_604` is a flag, not a
filter. Games outside 604 are queryable when bars exist.

Price join: last 1m TRADABLE_YES_BID with `available_at < t`.
Score/clock: last PBP with `event_timestamp <= t`.
PBP_SEQUENCE_NOT_PIT. L2/fills unavailable.

Self-neighbor: exclude `snapshot_id` and `trade_id` when the query is a
known historical observation.

## Tests

`ROLLER/tests/test_austin.py` keeps the original 13 and adds stored-snapshot
→ QueryState default_knn parity / ladder travel / PRE-80 / T40-already /
after-t KNN target / self-neighbor / future-mutation clocks / CI seed /
submits=false / catalog 1362 / ZERO_VARIANCE / path classes / outside-604
reconstruct / after-t columns / freeze. **26 passed.**

## Data limits

- LIVE FEED UNAVAILABLE. No Choosin quote. No submit.
- Candle path ≠ fill. Missing is never $0.
- PBP is not candle PIT.
- PRE-80 has no EV in the fitted 604 space.
- Calibration does not separate 4/5 from 3 on OOS n=71.
- 41¢ ladder neighborhood is weaker than 42¢ (measured).
- Do not mix N=1230 hedge V1 cents into 604 N/EV.

No live FIRST01 / 80/81/83/89 change. `first80.py` untouched.
`book.json` untouched. W9 not started. Warehouse Phase 21 not started.
`apps/trading-engine` untouched.
