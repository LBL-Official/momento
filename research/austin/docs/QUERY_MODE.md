# Austin query mode

```
DATA MODE          HISTORICAL QUERY
LIVE CHOOSIN FEED  UNAVAILABLE
```

Do not poll a live quote. Do not synthesize a current market from
Dallas charts. Dallas is 604 historical snapshots, not a feed.

## Same pipeline

```
RawState  →  build_feature_vector()  →  fitted scaler  →  fitted PCA  →  KNN
```

Historical snapshots and researcher queries call the same function.
The query never fits a scaler or PCA. The query never enters training.
The query has no outcome.

Feature names must match. Mismatch → `QUERY_REJECTED` /
`FEATURE_SCHEMA_MISMATCH`.

Parity test: take a historical snapshot, copy its raw fields into a
`QueryState`, rebuild features. Values match before outcomes attach.
The query is not a neighbor of itself.

## Required point-in-time fields

```
entry_quarter, current_quarter
entry_clock, current_clock
entry_price, current_price
home_score_at_entry, away_score_at_entry
home_score_current, away_score_current
side (home | away)
```

The engine derives travels, differentials, and time-since-entry.
The UI does not invent its own ML features.

## Optional path fields

Lookbacks at 30 / 60 / 120 / 300 seconds (price, scores, clock).

If absent:

```
PRICE VELOCITY     UNAVAILABLE — QUERY PATH NOT PROVIDED
SCORE VELOCITY     UNAVAILABLE — QUERY PATH NOT PROVIDED
```

Never fill velocity with 0.

## Modes

```
PRE_80     no FIRST80 entry at or before t
INTRA_80   entry observed, not settled
POST_80    any t ≥ entry, including after T40
```

PRE-80 keeps `entry_*`, `price_travel`, and `time_since_entry` as
`UNAVAILABLE` / `NOT_APPLICABLE`. Fitted 604 KNN needs those default_knn
columns. Fabricating them would invent an entry. PRE-80 therefore
returns reconstructed state only:

```
knn_status = INSUFFICIENT_SAMPLE
reason     = NO_ENTRY_IN_FITTED_SPACE
```

No EV. No band.

## Outcomes after t

```
features  = information available at or before t
outcomes  = events strictly after t
```

KNN target is `pnl_hold_after_t` (80¢ held to settlement, +20 / −80).
`pnl_8040_after_t` uses the first favorite close ≤40 after t. If t is
already at or after T40, that field is `NOT_APPLICABLE`.

## Historical reconstruction

```
GET  /austin/games
GET  /austin/games/{id}/moments
POST /austin/query/historical
```

Price join: last 1m `TRADABLE_YES_BID` with `available_at < t`.
Score/clock: last PBP with `event_timestamp <= t`.
PBP remains `PBP_SEQUENCE_NOT_PIT`.

## Future live mode

Not in this delivery. A later adapter may emit the same `RawState`.
Only the source of `RawState` changes.
