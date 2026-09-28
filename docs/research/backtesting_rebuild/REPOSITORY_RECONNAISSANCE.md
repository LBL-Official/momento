# Repository Reconnaissance

**Scope:** Read-only inspection of `/Users/user/Desktop/Momento` on 2026-08-26.  
**Method:** Source files, manifests, raw archives, and docs — not filenames alone.  
**Result:** The repo already contains a production MLB trading stack and a **LEGACY_V1** Kalshi candle/trade research lake. It does **not** contain a dual-domain historical event–market engine.

---

## 1. What this repository is

Momento is a production-grade Kalshi sports trading platform. MLB is the first live sport. Architecture is:

```text
Strategy proposes → Risk approves → Execution executes
→ Position Tracker reconciles → PNL calculates → Dashboard observes
```

Workspace members (from root `Cargo.toml`): trading-engine, replay-engine, research-collector, backtest-runner, sandbox-validate, prod-auth-validate, plus crates `core`, `kalshi`, `market-data`, `research-*`, `execution`, `risk`, `prediction`, `positions`, `pnl`, `sports`, and strategy crates `strategies/mlb`, `strategies/wnba`.

There is **no git metadata** in this workspace copy (`fatal: not a git repository`). Recon cannot report remotes, commits, or migrations history from git.

---

## 2. Production stack (must remain untouched by this rebuild)

| Area | Path | Role |
|------|------|------|
| MLB FIRST01 live | `strategies/mlb/src/{quote,strategy,state,stop}.rs` | 80→81→maker 80–83, lock ≥89, 50% VWAP stop |
| WNBA live | `strategies/wnba/` | Same machine, `StrategyId::WNBA` |
| Risk | `crates/risk/` | Snapshot budget, `max_open_positions=5`, exposure |
| Execution | `crates/execution/` | Paper + submit path for approved intents |
| Positions | `crates/positions/` | Fill-authoritative tracker; one GameId → one PositionId |
| PNL | `crates/pnl/` | Ledger from fills/fees/settlement |
| Live host | `apps/trading-engine/src/live.rs` | Wires strategy → risk → execution |
| Live config | `config/live.toml` | Triple live gate (`mode`, `live.enabled`, `confirmation`) |
| Paper config | `config/paper.toml` | Must not be able to submit live |
| Live deploy | `deploy/momento-live.service`, `m10-fetch-secret.sh` | Production unit |
| Paper deploy | `deploy/momento-paper.service`, `user-data.sh` | Milestone 7 |
| Kalshi trading | `crates/kalshi/src/{production,venue,transport,auth,ws}.rs` | Live venue adapter |
| Core domain | `crates/core/` | Money, Price, GameId, MarketEvent, Position, intents |

`momento-core` is shared with research. Changing financial types or `can_attempt_entry` is a **production** change. Research must consume these types, not mutate them.

---

## 3. Research / backtesting stack (LEGACY_V1)

| Crate / app | Path | What it actually does |
|-------------|------|------------------------|
| `momento-research-data` | `crates/research-data/` | Kalshi public REST collect → gzip JSONL + Parquet + manifests |
| `momento-research-strategies` | `crates/research-strategies/` | Parallel FIRST01 state machine (not linked to `strategies/mlb`) |
| `momento-research-execution` | `crates/research-execution/` | `CONSERVATIVE_MAKER` v1 fill model; refuses maker sim on candles |
| `momento-research-backtest` | `crates/research-backtest/` | Sheets control plane, `validate-mlb`, frequency reconcile |
| Collector | `apps/research-collector` | `reconcile`, `collect-date`, `catalog`, `export-csv` |
| Runner | `apps/backtest-runner` | `process`, `validate-mlb`, `reconcile-mlb-frequency` |
| Replay app | `apps/replay-engine` | Stub: prints “foundation only” |
| Research collector deploy | `deploy/momento-research-collector.{service,timer}` | Daily 03:00 America/Los_Angeles |

Research crates **do not** depend on `momento-risk`, `momento-execution`, `momento-strategy-mlb`, or `apps/trading-engine`. Isolation is real and must be preserved.

`research-data` **does** depend on `momento-kalshi` (`PublicMarketClient`, identity hashes). That is public-data HTTP only, not order submission.

---

## 4. Current backtesting engine (what it is, honestly)

The current engine is **not** a game-state reconstruction platform.

It is:

1. Discover Kalshi `KXMLBGAME` / `KXWNBAGAME` markets whose **close or settlement timestamp** falls in an America/Los_Angeles calendar day.
2. Download public **trades**, **1-minute candlesticks**, market **metadata**, and a **point-in-time REST orderbook** (at collection time).
3. Store candles in a type named `OrderbookEvent` with `NormalizedSource::RestCandlestick`.
4. Replay trades + those “orderbook” rows chronologically.
5. Run a copied FIRST01 state machine on YES bid (from candle close bid/ask).
6. Attempt maker-fill simulation only when quality is `FullL2` or `TopOfBookOnly`. Historical days classify as **`CANDLESTICK_ONLY` → 0 fills**.

Primary artifacts today: opportunity/intent CSVs, Sheets P&L rows, validation reports. Primary object is **not** a `StateTransition` or `GameMarketEpisode`. Those types **do not exist in Rust**.

---

## 5. Data locations (local)

| Location | Reality |
|----------|---------|
| `Backtesting Suite/Data-Real/` | Real Kalshi lake used by `validate-mlb` |
| `Backtesting Suite/Data/` | **DEMO FIXTURES** (synthetic COMPLETE partitions for Sheets e2e). Default `MOMENTO_RESEARCH_DATA_DIR` if unset |
| `Backtesting Suite/Runs/FIRST01/` | LEGACY_V1 run packages (validation + frequency reconcile, 2026-08-25) |
| `Backtesting Suite/Google Sheets/` | CSV mirrors of Input/Results |
| `Backtesting Suite/Strategies/FIRST01/` | Strategy plugin artifact folder |
| `/Users/user/Desktop/Momento/Data/` and `data/` | Empty placeholders (`raw/`, `normalized/`, `replay/`) |
| `Algorithmic Execution/{MLB,NBA,NCAAB}` | Empty directory stubs |
| No PBP / StatsAPI / Savant / MLB feed files anywhere | Confirmed by content search |

Default collector path is `Backtesting Suite/Data` (demo), not Data-Real. Validation runs explicitly set Data-Real.

---

## 6. Schemas and formats that already exist

`crates/research-data/src/schema.rs` (`SCHEMA_VERSION = "1.0.0"`):

- `RawMarketEvent` — `{ received_at, source, endpoint, ticker, payload }`
- `MarketMetadata` — game_id, market_id, ticker, event_ticker, series, side_label, status, open/close/settlement, result
- `OrderbookEvent` — mixed candles, REST snapshots, (unused) WS shapes
- `PublicTrade` — integer cents + hundredths qty
- `DailyManifest` — counts, completeness, file SHA-256, collector/schema versions

Lake layout:

```text
{root}/{MLB|WNBA}/2025-2026/
  raw/date=YYYY-MM-DD/events.jsonl.gz
  orderbook/date=YYYY-MM-DD/{metadata,orderbook}.parquet
  trades/date=YYYY-MM-DD/trades.parquet
  manifests/date=YYYY-MM-DD.json
```

Provenance is **partial**: collector receive time + endpoint + SHA-256 of published files. Missing: source_record_id, exchange timestamp on the raw envelope, raw_file pointer on each row, per-row checksum, observability enum stored in the lake (execution infers it later).

---

## 7. Identity as implemented

`crates/kalshi/src/identity.rs`:

- `GameId` = SHA-256(`"game" || event_ticker`) → u128
- `MarketId` = SHA-256(`"market" || ticker`) → u128

Tickers are aliases. There is **no** MLB official game id, no team registry, no postponement/doubleheader handler, no home/away canonicalization beyond Kalshi `subtitle`.

On 13 complete MLB days: **344 tickers, 172 event-tickers, all 2-contract pairs.** That pairing is Kalshi-side only.

---

## 8. MLB game / PBP ingestion

**None.** `crates/sports/src/mlb.rs` is a comment stub (“MLB domain types only. No 80/81/89”). `MarketEvent.game_state` is an opaque `Option<String>` and is not a model input. Live host typically leaves it `None`. PBP appears only in `docs/research/HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`.

---

## 9. Prediction / ML / theta

`crates/prediction` is a placeholder `Forecast` type. No XGBoost, Monte Carlo, event-theta, or market-theta implementation. Do not treat it as a research engine.

---

## 10. Tests that exist (research vs production)

Research:

- `crates/research-data/tests/infrastructure.rs`
- `crates/research-strategies/tests/{first01,trade_lifecycle}.rs`
- `crates/research-execution/tests/execution.rs`
- `crates/research-backtest/tests/control_plane.rs`

Production (must not be weakened for research):

- `strategies/mlb/tests/{strategy,yes_bid_observation,position_scoped_stop}.rs`
- `crates/risk/tests/{engine,invariants,open_position_cap}.rs`
- `crates/execution/tests/{engine,paper}.rs`
- `crates/positions/tests/*`, `crates/pnl/tests/ledger.rs`, `apps/trading-engine/tests/{live,paper}_host.rs`

---

## 11. Documentation already written (pre-this-package)

Reset + full waterfall plan (2026-08-26), FIRST01 audits, data-infrastructure, sheets-control-plane, desk loss review. Those docs correctly freeze FIRST01 and forbid candle-as-L2. They **do not** replace this reconnaissance: they did not inventory local files at this granularity, and they named `GameMarketEpisode` as the primary object without a dual-domain schema.

This package **completes Waterfall 0** with evidence. It does not implement Phase 1 Rust contracts.

---

## 12. Google Drive / Sheets (existing)

Hard-coded IDs in `crates/research-backtest/src/config.rs`. Local CSV mirrors under `Backtesting Suite/Google Sheets/`. Drive MCP is the write path; Sheets cell OAuth is optional. See [GOOGLE_REPORTING_ARCHITECTURE.md](GOOGLE_REPORTING_ARCHITECTURE.md).

---

## 13. What is missing relative to the north star

| Required | Present? |
|----------|----------|
| Dual EVENT / MARKET domains | MARKET only |
| Synchronized state + confidence | No |
| Starting prices for both contracts (lifetime, not close-day window) | Not guaranteed |
| Full path (not 80% snapshot) | Trades+candles on close-day only |
| First-touch engine (20–95%) | No (FIRST01 first_80 only, on candle bid) |
| StateTransition as research object | Docs only |
| Observability stored on every datum | Partial / inferred at execution |
| Immutable raw vs versioned normalize vs mutable research | Partial (raw gzip exists; normalize overwrite-on-republish; no transform version registry) |
| Multi-sport core interfaces | `ResearchSport::{Mlb,Wnba}` only; NBA/NHL/NCAAB are sports-crate stubs |
| MLB PBP | Absent |
| Historical L2 | Absent (and Kalshi does not sell it retrospectively) |
| Reporting of sync quality / theta / PBP cohorts | Absent |

---

## 14. Dangerous findings (summary)

1. Candles live in `orderbook.parquet` as `OrderbookEvent`.
2. REST `get_orderbook` at **collection time** is stored beside historical candles (not historical L2).
3. `RawMarketEvent.received_at` is collector clock (2026-08-25 for the June lake), not exchange time.
4. Day partitions are **close/settled PT date**, so market-open / starting price may lie **outside** the file.
5. `Backtesting Suite/Data` is demo, not real — easy to backtest the wrong lake.
6. FIRST01_live_entry_state_machine.md still says a completed trade “may allow new opportunity”; later audits and `can_attempt_entry` forbid it. Treat the later sources as canonical (see [FIRST01_BASELINE_SEMANTICS.md](FIRST01_BASELINE_SEMANTICS.md)).
