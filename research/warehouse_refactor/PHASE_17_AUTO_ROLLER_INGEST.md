# Phase 17 — Auto Roller warehouse ingest

Measured: **2026-09-13**. Fixture results only. The live
`ROLLER/data/nba/2025_2026/derived/warehouse/` tree was **not** written by
these tests.

`ROLLER/roller/auto_roller/ingest.py` (rq_index rebuild) was **not** changed.
Phase 18 verify was **not** started.

Module: `ROLLER/roller/warehouse/auto_ingest.py`.

---

## Architecture

```text
DISCOVER (source fingerprints vs last ingest_run.json)
  → NORMALIZE (existing Phase 3–8 publishers)
  → VALIDATE
  → IDENTITY / LINK
  → COVERAGE
  → FINGERPRINT
  → stage (warehouse.staging)
  → atomic publish (rename + backup)
  → get_catalog
```

Reuse, not rewrite:

- `identity.extend_identity_artifact`
- `market_link.build_and_write_nba_market_links`
- `observations.project_nba_observations`
- `pbp_events.project_nba_pbp`
- `settlement.build_and_write_nba_settlements`
- `orderbook.declare_nba_orderbook_capability` (capability only)
- `layout.write_nba_warehouse` (optional `dest=` for staging)

---

## Sources (NBA, source-driven)

What exists / is missing — not what FIRST80 needs:

| Kind | Path contract |
| --- | --- |
| Canonical games | `dataset_path(NBA, season, games)` |
| Canonical candles | monthly `kalshi_candles/month=YYYY-MM.csv` |
| Canonical PBP | monthly `pbp/month=YYYY-MM.csv` |
| Canonical markets | `kalshi_markets.csv` |
| Identity | `meta/game_identity.csv` |
| Suite settlements | Suite `normalized/nba/markets/markets.parquet` (`kalshi_rest`) |
| Orderbook | inspect + `SOURCE_UNAVAILABLE`; no parquet |

No network fetch. No L2/tick fabrication.

---

## Incremental / idempotent / atomic

- Source fingerprint = file hashes + transform versions.
- Unchanged fingerprint + valid published tree → `UNCHANGED` (no rewrite).
- Stage skip when that stage’s source hashes match the last successful record.
- Failed validate / interrupted publish → `INGEST_FAILED`; staging removed;
  published tree left intact (`.tmp` / `.staging` + `replace`/`rename` pattern).
- Run 1 = run 2 on unchanged sources (same identities, no duplicate rows,
  same fingerprints).

---

## Provenance

`ingest_run.json` on the published tree:

- source paths
- acquire time
- source hashes
- transform versions
- output fingerprints
- `pbp_pit_aligned_to_candles: false`
- `observation_basis: TRADABLE_YES_BID`

Source files are not overwritten.

Settlement remains Suite/source only. PBP is identity-linked only. No
persisted PBP↔candle join. Observations are not forward-filled.

---

## Fixture measurements (`ROLLER/tests/test_warehouse_auto_ingest.py`)

10 tests on tmp `RollerConfig` trees. Published dest ≠ live warehouse.

Additional timed fixture run (tmp tree, **not** the live warehouse),
2026-09-13T07:40:58Z, raw JSON:
`research/warehouse_refactor/phase15_measurements/p17_fixture_measure.json`.

```text
run 1  PUBLISHED   0.099513 s
run 2  UNCHANGED   0.001596 s
published_is_live  false
source_fingerprint_equal  true
output_fingerprints_equal true
source_fingerprint  ad047b4e76a82f8b4b14d3dce90376068f6c21f844dac652d16185457b67cab0
observation_basis   TRADABLE_YES_BID
pbp_pit_aligned_to_candles  false
```

`ingest_run.json` keys present: `acquire_time`, `source_paths`,
`source_hashes`, `transform_versions`, `output_fingerprints`,
`source_fingerprint`, `pbp_pit_aligned_to_candles`, `observation_basis`.

Fixture `output_fingerprints` (run 1 = run 2):

```text
games          2705e523dab5716d8fdedae9010420422359d5944920218a5ad37e08bd01a588
markets        6129c70ea89ae313e4d06a6b6b3b52ee9483a15cf25b5a04e15673366d52e190
links          0241f9aefec4005c95c7ae4c5b9770ca8101e91c7d50de927f78ca825e30915b
settlements    754beced874f946bf7fac36663479a68e94e2749ead0c224eaf959535e046549
observations   cb939ff7b370dbd8258923a2b931ecb3fbde33bb52fed24db069db1ed673dca1
pbp            9a419d2c9bb07b2c880eb8c0423c7a050bc361f5e73ca9afd2b947841050b369
observations_rows  2
pbp_rows           2
settlements_rows   2
```

| Case | Result |
| --- | --- |
| Discover present/missing | PASS |
| Run 1 PUBLISHED / run 2 UNCHANGED, 1 game | PASS |
| New game then existing-game UNCHANGED | PASS |
| New market/observations (2 → 3 candle rows) | PASS |
| Missing observations publish empty months; later PBP + settlement arrive | PASS |
| Duplicate identity/games → FAILED, no manifest | PASS |
| Missing games / malformed price / blank `available_at` / ambiguous ticker / conflicting Suite result → FAILED | PASS |
| Interrupted `write_nba_warehouse` leaves published manifest bytes unchanged | PASS |
| Provenance file present; READY / DATA_REQUIRED (tick) / OPERATION_REQUIRED (PBP PIT); orderbook `SOURCE_UNAVAILABLE` | PASS |
| Fingerprint changes when games.csv bytes change | PASS |

---

## Failure handling

`INGEST_FAILED` is explicit. Half-written staging is deleted. Published
canonical tree is not replaced unless staging validates.

Phase 17 complete. Next authorized phase is **18**. Do not start it from this report.
