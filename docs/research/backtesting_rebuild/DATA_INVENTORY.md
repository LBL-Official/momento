# Data Inventory (local, 2026-08-26)

**Constraint honored:** no external downloads. Counts below are from files on disk.  
**Primary lake:** `Backtesting Suite/Data-Real/`  
**Not real:** `Backtesting Suite/Data/` (demo fixtures).

Season folder label is `2025-2026` for both sports. That label is a collector constant, not proof that 2025 games are present.

---

## 1. Executive coverage

| Dataset | Dates with real content | Games | Markets (contracts) | Files | Bytes (approx) |
|---------|-------------------------|-------|---------------------|-------|----------------|
| MLB Kalshi Data-Real | **2026-06-18 … 2026-06-30** (13 COMPLETE days) | **172** event-tickers | **344** tickers (exactly 2 per game) | 175 (35 gz + 105 parquet + 35 json) | ~236 MB |
| MLB Kalshi 2025 | **No content.** Five probe dates exist as MISSING empty archives | 0 | 0 | empty gz (20 bytes) + empty parquet + manifests | negligible |
| MLB PBP / game-state | **None** | — | — | 0 | 0 |
| Historical L2 / WS | **None** | — | — | 0 | 0 |
| WNBA Kalshi Data-Real (out of MLB-first scope) | 12 COMPLETE days Jun 18–28 & Jun 30 2026; Jun 29 MISSING | not MLB | 66 collected markets on complete days | present | present |

**2025 MLB: not reconstructed locally.** Probe manifests exist for 2025-06-15, 2025-07-15, 2025-08-01, 2025-09-10, 2025-10-05 — all `completeness_status = MISSING`, `markets_discovered = 0`.

**2026 MLB: only 13 of ~182 regular-season days** (and none of March–May, July–October) are locally complete. Jun 1–17 2026 were attempted and returned 0 markets.

---

## 2. MLB Data-Real day table

Source: `Backtesting Suite/Data-Real/MLB/2025-2026/manifests/date=*.json` (35 files).

### MISSING (22 days) — zero markets discovered

2025-06-15, 2025-07-15, 2025-08-01, 2025-09-10, 2025-10-05,  
2026-06-01 … 2026-06-17 inclusive.

Each still has: empty `events.jsonl.gz` (~20 B), empty parquet, a manifest, and the standard L2-limitation note. These are **honest empty attempts**, not deleted history.

Validation audit (`june_data_discovery_audit.csv`) states: Kalshi `/markets` + `/historical/markets` returned 0 `KXMLBGAME` markets for the LA close_time window; earliest tickers seen start `26JUN18`. Treat as **API coverage limitation as of collection time 2026-08-25**, not as proof that those games never existed on Kalshi.

### COMPLETE (13 days)

| Date | Markets | Trades | Orderbook events (mostly 1-min candles) | Raw events |
|------|---------|--------|------------------------------------------|------------|
| 2026-06-18 | 8 | 56,837 | 7,092 | 56,853 |
| 2026-06-19 | 28 | 283,612 | 26,145 | 283,668 |
| 2026-06-20 | 28 | 327,202 | 26,590 | 327,258 |
| 2026-06-21 | 30 | 231,089 | 22,282 | 231,149 |
| 2026-06-22 | 24 | 243,033 | 23,069 | 243,081 |
| 2026-06-23 | 30 | 336,271 | 27,385 | 336,331 |
| 2026-06-24 | 32 | 358,159 | 28,430 | 358,223 |
| 2026-06-25 | 18 | 221,888 | 14,240 | 221,924 |
| 2026-06-26 | 30 | 232,078 | 30,269 | 232,138 |
| 2026-06-27 | 30 | 311,661 | 26,803 | 311,721 |
| 2026-06-28 | 30 | 326,911 | 22,547 | 326,971 |
| 2026-06-29 | 26 | 252,162 | 27,845 | 252,214 |
| 2026-06-30 | 30 | 215,138 | 30,190 | 215,198 |
| **Sum** | **344** | **3,396,041** | **312,887** | **3,396,729** |

All 13: `invalid_records = 0`, `sequence_gaps = 0`, `markets_collected = markets_discovered`. Pairing on disk: **172 games × 2 YES contracts**.

Jun 18 is a short slate (8 markets / 4 games). Jun 24 is a full slate (32 / 16). Jun 25 is 18 markets (9 games) — do not assume “~15 games every day.”

---

## 3. Formats and resolution

| Layer | Format | Resolution | Honest content |
|-------|--------|------------|----------------|
| Raw | `events.jsonl.gz` | One JSON object per REST payload row | Trades (vast majority), one candlesticks blob per ticker, one PIT orderbook per ticker, plus collector-synthesized metadata rows |
| Trades parquet | `trades.parquet` | Per public trade | `yes_price_cents`, qty hundredths, `created_time` as `exchange_timestamp` |
| “Orderbook” parquet | `orderbook.parquet` | **1-minute candlestick close** of YES bid/ask; plus one REST snapshot at **collection time** | Not L2 history. Depth on candles = `None`. Levels empty on candles |
| Metadata parquet | `metadata.parquet` | One row per ticker/day | Includes `open_time`, `close_time`, `settlement_ts`, `result` when Kalshi sent them |
| Manifest | JSON | One per attempted date | Completeness, counts, SHA-256 of the four published files |

Sample raw trade payload keys: `count_fp`, `created_time`, `is_block_trade`, `no_price_dollars`, `taker_*`, `ticker`, `trade_id`, `yes_price_dollars`.

Sample candle: `end_period_ts`, `yes_bid`/`yes_ask` OHLC in dollars, `price` OHLC (often null), `volume_fp`, `open_interest_fp`. First Jun 18 candle in archive is **2026-06-18 00:00 PT** with YES bid close **46¢**, ask **47¢** — that is the **start of the close-day window**, not necessarily market creation.

Collector versions recorded: `collector_version = 0.1.0`, `schema_version = 1.0.0`. Collection timestamps on June partitions: **2026-08-25T17:50–17:51Z**.

---

## 4. Coverage dimensions

| Dimension | Status |
|-----------|--------|
| Market coverage (Kalshi `KXMLBGAME` on COMPLETE days) | 344/344 discovered collected; pairing 2/2 |
| Trade coverage | Present and large (~3.4M trades) on those 13 days |
| Candle coverage | 1-minute YES bid/ask OHLC for the **PT close/settled day window** |
| Order-book L2 coverage | **UNAVAILABLE historically.** Manifest note is explicit |
| PIT REST book | Stored at backfill time; **not** the book at game time. Observability: `RestSnapshot` mixed into same parquet |
| Settlement coverage | Metadata `result` / `settlement_ts` fields exist; not separately inventoried per game in this recon (requires parquet reader). Do not assume 100% until Waterfall 1 catalog job |
| PBP coverage | **0%** |
| Starting-price coverage | **Not guaranteed.** Partition ≠ market lifetime |
| Path to 80% | Trades exist across the collected window; first-touch engine does not |
| 2025 season | **0 games locally** |
| 2026 outside Jun 18–30 | **0 games locally** (Jun 1–17 attempted empty; rest never collected in this lake) |

---

## 5. `Backtesting Suite/Data` (demo — do not treat as MLB history)

15 MLB days 2026-05-01 … 2026-05-15, each `COMPLETE` with **1 synthetic market**, **0 trades**, notes: `DEMO FIXTURE: synthetic COMPLETE partition for Sheets control-plane e2e`. Same pattern for WNBA. **No raw gzip tree** (no `raw/date=*` directories).

Default env `MOMENTO_RESEARCH_DATA_DIR` points here if unset (`crates/research-data/src/paths.rs`).

---

## 6. Other local data (searched, not in the suite)

| Path | Finding |
|------|---------|
| `Data/`, `data/` at repo root | Empty raw/normalized/replay dirs |
| `Algorithmic Execution/MLB` | Empty |
| Live host state | Not in this workspace (production is on EC2 `/var/lib/momento/state/` per prior desk work). **Not copied here.** |
| PBP / Savant / StatsAPI | No files, no crates, no scripts |

---

## 7. LEGACY_V1 run artifacts (derived, not raw)

Under `Backtesting Suite/Runs/FIRST01/2026/08/`:

| Run | Role |
|-----|------|
| `2026-08-25_mlb-validation-20260825-185643` | 13 eligible days, 110 FIRST01 opportunities, 0 fills, `CANDLESTICK_ONLY` |
| `2026-08-25_mlb-frequency-reconcile-20260825-215535` | 8.46 opportunities/day canonical; 4.69 after desk cap=5 (risk, not FIRST01) |

These are **mutable research outputs**. They must not be confused with immutable raw.

---

## 8. What “COMPLETE” does and does not mean

`CompletenessStatus::Complete` means: discovered markets for that **close/settled PT day** were all collected without invalid records.

It does **not** mean:

- full 2025–2026 MLB universe
- L2 history
- PBP
- market-open → settlement path
- starting prices for both contracts
- that candles are ticks
- that REST snapshots are historical

Waterfall 1 must introduce a stricter coverage vocabulary (`PARTITION_COMPLETE` vs `EPISODE_COMPLETE` vs `LIFETIME_COMPLETE`).

---

## 9. Gaps the CEO should treat as facts, not TODOs to invent

1. Local Kalshi MLB truth = **13 days in June 2026**, 172 games, 344 contracts, trades + 1-min candles.
2. **2025 is absent** from the lake; empty probes are not 2025 data.
3. Kalshi historical discovery, as of 2026-08-25, did not return pre-Jun-18-2026 `KXMLBGAME` markets to this collector. Waterfall 1 must **re-query and document** cutoff/retention without fabricating days.
4. No sports PBP exists to synchronize.
5. Do not download in this reconnaissance step; acquiring the rest of 2025–2026 is Waterfall 1 **after** CEO authorization and after a non-destructive catalog of what Kalshi still serves.
