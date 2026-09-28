# Parquet contract (v1.0.0)

Confirm & Run **still reads monthly CSV** via `admin.load_dataset`. This contract defines the
canonical analytical representation that dual-writes and later loader cuts must obey.

`dataset_fingerprint` / `scope_fingerprint` hash canonical CSV (and other source files)
only. Sibling `month=YYYY-MM.parquet` and `.manifest.json` dual-write artifacts are ignored
so a copy beside CSV cannot stale `rq_index_v1.0.0`.

## Observation bases (not interchangeable)

| Basis | Dataset | Price field | Meaning |
| --- | --- | --- | --- |
| `TRADABLE_YES_BID` | `kalshi_candles` | `yes_bid_close` | Quote you could have hit |
| `LAST_TRADE_PRINT` | `kalshi_last_trade` | `last_close_e4` | Print that already happened |

`TradableBar.bid` on a last-trade series is last print, not yes bid.

## Clocks (do not collapse)

- observed / event timestamp (`event_timestamp`, `candle_timestamp`, `captured_at`)
- source timestamp (when the source stamped the row, if present)
- `available_at` (PIT visibility)
- `ingested_at` (warehouse arrival)

Basketball TE: `available_at < observation_ts`. MLB snap: `event_timestamp <= snap_ts`.

## Identity

Every dataset has a name, schema version, source, sport, league, season. Row-level
`internal_game_id` / `ticker` / `available_at` when the source provides them.
`source_revision` lives on the partition manifest when a file hash exists.

Do not fabricate fields.

## Partition grain

Same as today: `month=YYYY-MM.csv` plus optional sibling `month=YYYY-MM.parquet`.
Do not explode into per-game files without a recorded size benchmark.

## Indexes

`rq_index_v1.0.0` remains the observation fact index. It is derived, not a second
meaning of Cross.

## Forbidden

- Serving tradable bars as last-trade
- Forward-filling missing minutes
- Inferring Kalshi settlement from PBP or Polymarket
- Inventing NHL
- Changing FIRST80 / detectors / Results math
