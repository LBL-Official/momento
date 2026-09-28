# Current Architecture Map

**Date:** 2026-08-26  
**Purpose:** Map what is wired today versus the north-star historical engine. No code changes.

---

## 1. Production trading (untouched)

```text
Kalshi WS/REST book
        ↓
apps/trading-engine live.rs
        ↓
MarketEvent (core)  — bid/ask/last, optional opaque game_state
        ↓
strategies/mlb MlbStrategy::observe
        ↓  BuildPositionIntent
crates/risk RiskEngine::decide_entry
        ↓  ApprovedTradeIntent
crates/execution submit_entry
        ↓
crates/kalshi production venue  (only if triple live gate)
        ↓
fills → crates/positions → crates/pnl
        ↓
audit log (append-only)
```

Invariants (existing architecture docs, still binding):

- Strategy never submits to Kalshi.
- Risk never talks to the venue.
- Execution never approves exposure.
- Default mode is not LIVE.
- Integer money / price / qty.

Research rebuild **must not** enter this graph except later, via an explicit production-bridge waterfall, after CEO approval.

---

## 2. LEGACY_V1 research graph (what exists)

```text
Kalshi public REST (unsigned)
        ↓
apps/research-collector  /  crates/research-data::Collector
        ↓
raw/events.jsonl.gz     (immutable-ish gzip of REST payloads)
orderbook/*.parquet     (candles + PIT snapshots, typed as OrderbookEvent)
trades/*.parquet
manifests/*.json
        ↓
ReplayDataset / ReplayCursor  (Trade | Orderbook only)
        ↓
research-strategies EntryEngine / ExitEngine  (FIRST01 copy)
        ↓
research-execution CONSERVATIVE_MAKER
        ↓  (CANDLESTICK_ONLY → no maker fills)
research-backtest pipeline / validate-mlb / Sheets CSV
        ↓
Backtesting Suite/Runs/FIRST01/...
Google Sheets Input/Results (LEGACY_V1)
```

There is **no** event-domain pipeline.

---

## 3. Layer comparison

| Layer (north star) | Production today | Research today |
|--------------------|------------------|----------------|
| RAW DATA | Live WS/REST (not archived as research lake) | Kalshi REST gzip JSONL for collected days |
| NORMALIZATION | `MarketEvent` in core | Parquet metadata/trades/orderbook schema 1.0.0 |
| EVENT RECONSTRUCTION | None (`game_state: Option<String>`) | None |
| MARKET RECONSTRUCTION | Live L2 via WS (not historical) | 1-min candle close bid/ask + PIT REST book |
| SYNCHRONIZED STATE | None | None |
| STATE TRANSITIONS | Position/order SMs only | FIRST01 entry/exit phases only |
| STRATEGY REPLAY | Live FIRST01 | Parallel FIRST01 on candles |
| OUTCOME LABELING | Settlement on live positions | Metadata `result` when Kalshi provides it |
| FEATURE DATASET | None | Opportunity CSVs |
| STAT / ML | `crates/prediction` stub | None |
| RISK | Live Risk Engine | Not in research opportunity counts |
| EXECUTION | Live / paper | Modeled; unsupported on candles |

---

## 4. Crate dependency map (research isolation)

```text
research-strategies ──► momento-core
research-data       ──► momento-core, momento-kalshi (public client)
research-execution  ──► core, research-data, research-strategies
research-backtest   ──► core + three research crates
apps/research-collector, apps/backtest-runner ──► research crates
```

**Not imported by research:** `momento-risk`, `momento-execution`, `momento-strategy-mlb`, `apps/trading-engine`.

**Shared and sensitive:** `momento-core` (IDs, money, `Position::can_attempt_entry`, `MarketEvent`).

---

## 5. Identity map

```text
Kalshi event_ticker  ──hash──► GameId (u128)
Kalshi market ticker ──hash──► MarketId (u128)
Kalshi subtitle      ───────► side_label (team string, not canonical TeamId)
MLB official game pk ───────► MISSING
PBP event id         ───────► MISSING
```

Live and research share the hash function via `momento-kalshi` identity helpers. That is good for ticker-stable GameId. It is **not** a sport-identity engine.

---

## 6. Time map (today)

| Clock | Production | LEGACY research |
|-------|------------|-----------------|
| Exchange timestamp | `MarketEvent.exchange_ts` from venue | Trade `created_time`; candle `end_period_ts * 1000` |
| Receipt timestamp | `received_at` | Collector wall clock at backfill (not original observation) |
| Event time (outs/inning) | Absent | Absent |
| Market time (path since open) | Implicit in live WS | **Truncated** to close/settled PT day window |
| Partition clock | n/a | America/Los_Angeles calendar day of close **or** settlement |

---

## 7. Intended architecture (design only)

```text
IMMUTABLE RAW
  A. Kalshi raw (existing gzip + future captures)
  B. MLB/PBP raw (not present)
  C. Settlement/outcome raw
        ↓ versioned normalize (never overwrite raw)
EVENT DOMAIN reconstruction     MARKET DOMAIN reconstruction
        ↓                              ↓
        └──────── SYNCHRONIZED STATE ─┘
                      ↓
              STATE TRANSITIONS  (atomic research object)
                      ↓
         GameMarketEpisode (container: both contracts + full paths)
                      ↓
         derived: first-touch, starting state, theta inputs
                      ↓
         strategy plugins (FIRST01 first)  — read-only vs live
                      ↓
         labels / datasets / experiments (MUTABLE)
                      ↓
         Google Drive/Sheets (human archive, not source of truth)
```

Production Risk and Execution remain **downstream consumers** of a future prediction interface. They are not part of Waterfall 1.

---

## 8. Control-plane vs data plane

| Plane | Today | Target |
|-------|-------|--------|
| Machine source of truth | Parquet + gzip on disk | Versioned lake + (later) research DB |
| Human archive | Drive folder + two Sheets | Drive research archive (run reports, cohorts) |
| Experiment control | Backtesting Input sheet | Versioned Experiment objects; Sheets as view |
| Live control | `config/live.toml` + kill switch | Unchanged |

---

## 9. Apps

| App | Status |
|-----|--------|
| `trading-engine` | Production composition root — **untouched** |
| `research-collector` | LEGACY Kalshi daily collect — **wrap/extend**, do not delete |
| `backtest-runner` | LEGACY FIRST01 candle runner — **deprecate as platform**, keep for rule regression |
| `replay-engine` | Empty stub — candidate composition root for the **new** engine later |
| `prod-auth-validate` / `sandbox-validate` | Milestone auth — **untouched** |
