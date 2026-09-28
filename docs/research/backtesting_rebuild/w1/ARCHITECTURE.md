# W1 Architecture

W1 is the **raw-data control plane**. Downstream waterfalls must cite artifacts by path + SHA-256. They must not overwrite `Backtesting Suite/Data-Real/**`.

```text
IMMUTABLE LAKE (v1)
  raw/events.jsonl.gz
  orderbook/{metadata,orderbook}.parquet
  trades/trades.parquet
  manifests/date=YYYY-MM-DD.json
        ↓  read-only scan
W1 FOUNDATION (derived)
  lake_catalog.json
  integrity_report.json
  coverage_matrix.csv
  starting_price_evidence.json
  raw_artifact_refs.json
  provenance_index.json
        ↓  human archive
Google Drive / Sheets (not the database)
```

## Owners

| Concern | Owner |
|---------|--------|
| gzip/parquet bytes, checksums, v1 manifests | W1 |
| Envelope v2 **sample** (Foundation only) | W1 |
| Coverage / observability / provenance vocab for **raw** | W1 |
| MLB PBP, game-state, event time | **W2** (do not implement here) |
| Sync, StateTransition | later waterfalls |

## Immutability

- W1 never `File::create`s under the lake root (`LakeWriteGuard`).
- Repairs belong in a **new** normalized version, not in-place raw edits.
- v1 `COMPLETE` is not redefined.

## Generic raw kinds (labels only)

Game, Market, Contract, Source, Observation, Trade, Quote, OrderbookObservation, RawArtifact, Provenance, Coverage, Settlement — as **catalog kinds**, not reconstructed domain objects.
