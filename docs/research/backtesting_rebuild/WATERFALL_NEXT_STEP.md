# Waterfall Next Step

**Waterfall 0:** reconnaissance (this package, A1–A10) + governance baseline
(W0-A11: master waterfall, spec, registry, ADRs, current-state) — **COMPLETE as documentation.**  
**Do not start coding Waterfall 1 until the CEO authorizes it.**

First S-step after authorization: **`W1-A1-S1`** (lake_catalog_v1 schema + fixtures).
Then STOP unless the execution instruction continues. Registry:
[`../BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`](../BACKTEST_ENGINE_WATERFALL_REGISTRY.csv).

This maps to the existing plan’s Waterfall 1 / Phases 1–2 **data foundation**, with a stricter “no production change” fence.

The existing `HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md` listed “Phase 1 contracts” as immediate work. **This recon supersedes that as the first delivered artifact.** Contracts that belong **inside** Waterfall 1 are listed below as outputs of W1, not as a skip-ahead to PBP or FIRST01 replay.

---

## WATERFALL 1 — Immutable Raw Data / Canonical Data Foundation

**Goal:** Make historical truth **catalogued, provenance-complete, non-destructive, and extensible** so EVENT and MARKET reconstruction can proceed later without rewriting June 2026 gzip.

**Not in W1:** PBP parsers as a finished event engine, sync engine, FIRST01 retune, ML, Drive automation, live/risk/strategy edits, fabricating missing Kalshi days.

---

### Prerequisites

1. CEO sign-off on this reconnaissance package.
2. Freeze: no writes to `strategies/mlb`, risk, execution, live config, Data-Real **overwrites**.
3. Working copy of Data-Real left bit-identical unless W1 **adds** new date partitions or a parallel `raw_v2/` tree.
4. Kalshi public historical docs re-read at implementation time (do not invent endpoints).
5. Decision recorded: default research root for real work is **Data-Real**, not demo `Data/`.

---

### Inputs

| Input | Path / source |
|-------|----------------|
| Existing lake | `Backtesting Suite/Data-Real/{MLB,WNBA}/2025-2026/` |
| Demo lake (tests only) | `Backtesting Suite/Data/` |
| Collector + schema v1.0.0 | `crates/research-data` |
| Public client | `crates/kalshi/src/public_data.rs` |
| This recon | `docs/research/backtesting_rebuild/*` |
| Kalshi cutoff/list/trades/candles | Official REST only |
| MLB/PBP | **Catalog candidate sources only** unless CEO also authorizes acquisition |

---

### Outputs (W1 done when these exist)

1. **Lake catalog** (machine-readable) of every immutable file: sport, date, status, checksum, byte size, ticker counts, observability notes.
2. **Coverage report** distinguishing `PROBE_EMPTY` vs `PARTITION_COMPLETE` vs `LIFETIME_INCOMPLETE` vs `NOT_ATTEMPTED`.
3. **Raw envelope spec v2** (documented + tests) additive to v1 gzip — no rewrite of existing JSONL.
4. **Register** of v1 files as `immutable_raw_kalshi_v1` with checksum verification job.
5. **Schema candidates checked in as docs/fixtures** (and Rust types **only** if they cannot change production crates).
6. **Source matrix** for MLB PBP (official vs licensed) with “not downloaded” until authorized — no invented sample PBP.
7. **Identity stub**: existing GameId/MarketId hashes + empty official-game-id field; no fake MLB pks.
8. **Tests** listed below, all green.
9. **Updated docs** pointing W1 complete / W2 identity next.

Optional **if authorized** in the same waterfall (still non-destructive):

- Re-query Kalshi historical for 2025 and 2026 dates `NOT_ATTEMPTED` or `PROBE_EMPTY`, append **new** date partitions only when discovery returns markets.
- If API still returns 0, persist the cutoff/list response as raw evidence (`UNAVAILABLE` with timestamp), do not fill synthetic days.

---

### Schema candidates (design; implement in W1)

#### A. `lake_catalog_v1` (JSON)

```text
catalog_version
generated_at
lake_root
entries[]:
  sport, season_label, partition_date, layer (raw|metadata|orderbook|trades|manifest)
  path, sha256, bytes
  completeness_v1          # existing enum, unmodified meaning
  coverage_v2              # new: see below
  markets, games_est, trades, ob_events
  notes[]
```

#### B. `coverage_v2`

```text
NOT_ATTEMPTED | PROBE_EMPTY | PARTITION_COMPLETE_V1 | INVALID
LIFETIME_UNVERIFIED          # v1 complete but open_time not proven in partition
HISTORICAL_API_UNAVAILABLE   # cutoff/list returned none at query_time
```

Do not redefine v1 `COMPLETE`.

#### C. `raw_envelope_v2` (new files, e.g. `events.v2.jsonl.gz`)

v1 fields plus:

```text
source_record_id
source_timestamp           # nullable
source_timestamp_kind      # trade_created | candle_end | ingest_only | …
ingestion_timestamp
raw_file / line
payload_sha256
schema_version = "2.x"
observability              # OBSERVED for payload presence
```

v1 gzip remains the immutable original.

#### D. `identity_stub_v1`

```text
game_id, market_id, ticker, event_ticker, series
mlb_game_pk = null
match_status = UNMAPPED
```

#### E. Explicitly **out of** W1 schemas

`EventState`, `StateTransition`, theta, first-touch tables — Waterfalls 2+.

---

### Tests required

| Test | Asserts |
|------|---------|
| Checksum replay | Recompute SHA-256 of Data-Real COMPLETE files = manifest |
| v1 schema round-trip | Existing gzip/parquet still parse with schema 1.0.0 |
| no_synthetic_rows | Unchanged: candles not labeled `l2_snapshot` |
| Demo ≠ Real | Catalog marks `Data/` as DEMO; validation default refuses it for “real MLB” claims |
| Envelope v2 | Round-trip; missing source_timestamp allowed with reason |
| Non-overwrite | W1 job cannot replace an existing `events.jsonl.gz` with different hash (fail closed) |
| Observability enum | PIT `RestSnapshot` tagged ingest-time; candles tagged CANDLESTICK |
| Production fence | Unit/compile test or crate graph test: new W1 crate does not depend on `momento-risk`, `momento-execution`, `momento-strategy-mlb` |
| No lookahead fixture | Catalog does not invent 2025 games |

Do **not** delete failing production tests to make W1 pass.

---

### Acceptance criteria

1. Data-Real June 2026 COMPLETE partitions still verify checksums.
2. Empty 2025 and Jun 1–17 probes remain; they are classified, not deleted.
3. v1 and v2 can coexist.
4. A third party can answer from catalog: how many games, markets, files, what is missing, what is UNAVAILABLE vs not attempted.
5. No production binary behavior change; no FIRST01 parameter change.
6. Documentation states remaining Kalshi gaps without filling them.

---

### Failure conditions (stop the waterfall)

- Any overwrite of an existing raw gzip/parquet hash
- Invented L2, mids, PBP, or timestamps
- Silent imputation of missing minutes or missing 2025 days
- Collector pointed at live order endpoints
- Research crate taking a dependency on live strategy/risk/execution
- Treating demo `Data/` as 2025–2026 MLB
- Redefining v1 COMPLETE to mean lifetime-complete
- Downloading PBP under a license/ToS that has not been approved
- Changing 80/81/83/89/50% or `can_attempt_entry`

---

### Reproducibility requirements

- Catalog includes generator version, schema version, UTC generation time.
- Checksums of inputs and outputs.
- Same catalog job on unchanged lake → identical catalog (sort-stable JSON).
- Query-time of any new Kalshi GET stored on the raw envelope.
- Timezone for partition dates remains America/Los_Angeles, documented.

---

### Suggested implementation shape (when authorized)

Prefer a **new** research module/crate (e.g. `momento-research-lake` or `research-data` `catalog` expansion) over editing live crates. Extend `research-data` only with additive modules. LEGACY collector remains the Kalshi fetch implementation until a versioned successor is proven.

---

## After W1 (preview only)

**Waterfall 2 — Canonical identity engine** (MLB pk ↔ Kalshi event_ticker), still no FIRST01 retune.

Do not skip to strategy replay, ML, or production bridge.

---

## Explicit stop

```text
IMPLEMENTATION OF WATERFALL 1: NOT STARTED
PRODUCTION ORDERS TRANSMITTED BY THIS RECON: 0
FIRST01 BEHAVIOR CHANGES: 0
```
