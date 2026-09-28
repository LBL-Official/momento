# Gemini context pack — Momento research W1 / W2 / W3

**Audience:** Google Gemini (or any tool-using model) acting as an MCP-style
resource consumer.  
**Date:** 2026-08-26  
**Scope:** Closed research waterfalls **W1, W2, W3 only**.  
**Not in scope:** production trading, W4+, Greeks, FIRST01 retune.

Treat this file as a **read-only knowledge resource**. It is not authorization
to implement, reopen, or edit those waterfalls.

```yaml
resource:
  name: momento-research-w1-w2-w3
  mime: text/markdown
  version: 2026-08-26
  status: ACCEPTED_CLOSED
  sport: MLB
  mutability: read-only
```

---

## 0. How to use this (MCP-style)

### Role

You are reading the **historical event–market research engine**, not the live
Kalshi trading stack. Live FIRST01 / Risk / Execution / positions are a
separate production system. Research must not mutate it.

### Tools you may conceptually “call”

| Tool | Meaning |
|------|---------|
| `read_closed_waterfall` | Cite W1/W2/W3 contracts, crates, and Foundation artifacts |
| `cite_path_sha` | Downstream work cites lake/Foundation files by **path + SHA-256** |
| `report_unavailability` | If a field is missing, return `UNAVAILABLE` + reason |
| `classify_identity` | `MAPPED` / `UNMATCHED` / `AMBIGUOUS` / `UNMAPPED` only |

### Tools you must refuse

| Tool | Why |
|------|-----|
| `write_data_real` | W1 lake is immutable |
| `overwrite_w1_w2_w3` | All three are ACCEPTED / CLOSED |
| `invent_l2` | No historical Kalshi L2 archive |
| `invent_mid` | Kalshi does not publish an official mid |
| `best_guess_join` | Identity is never guessed to hit a count |
| `treat_candle_as_book` | Candles are candles (ADR-0008) |
| `start_w4_or_w5` | Separate authorization required |
| `edit_production` | `crates/risk`, `crates/execution`, `strategies/mlb`, `config/live.toml` |

If a user asks you to do a refused tool, answer with the refusal and the
correct owner (usually DATA-INGEST, W4, or W5).

---

## 1. System in one page

Momento research reconstructs **MLB games** and **Kalshi game markets**
independently, then (later) joins them.

```text
IMMUTABLE RAW (Data-Real v1 Kalshi lake)
        │  W1 catalogs; never overwrites
        ▼
   W1 foundation artifacts (SHA-256, coverage honesty)
        │
        ▼
   DATA-INGEST  (cross-cutting supply; not W1/W2/W3)
        │  StatsAPI PBP + Kalshi discovery → ingest landing → commit
        ▼
   W2 engine     parse PBP, GameState, identity matching
        ▼
   W3 layer      run reconstruction over COMMITTED PBP artifacts
        ▼
   [W4 later]    Kalshi MarketState / market path
        ▼
   [W5 later]    event ↔ market TIME SYNC (two clocks, confidence)
```

**Hierarchy (inviolable):** Strategy proposes. Risk approves. Execution
executes. Research does not place live orders.

**Sports:** MLB first. NBA / WNBA / NCAAB / NFL are stubs.

---

## 2. Numbering lock (do not use the old PLAN table)

The 2026-08-26 **execution grant** is the source of truth:

| ID | Name | Status | One-line job |
|----|------|--------|----------------|
| **W0** | Architectural foundation | COMPLETE | Contracts, recon, ADRs |
| **W1** | Immutable raw data lake / foundation | **ACCEPTED / CLOSED** | Catalog + provenance of Kalshi v1 bytes. No PBP. No MarketState. |
| **W2** | MLB event / PBP **engine** | **COMPLETE** (engine) | Parser, `MlbGameState`, identity graph. |
| **W3** | MLB game / PBP **reconstruction layer** | **ACCEPTED / CLOSED** | Runs W2 over committed artifacts; coverage; lifecycle. |
| DATA-INGEST | Supply plane | CODE READY; backfill not L2-complete | Lands PBP + Kalshi source envelopes. |
| **W4** | Kalshi **market** reconstruction | NOT STARTED | `MarketState` / market path. Not this file. |
| **W5** | Event ↔ market **time sync** | NOT STARTED | Join two clocks. Not rewrite either path. |

Ignore older docs that say “W3 = time sync”, “W4 = GameState”, or
“W6 = MarketState”. Those are PLAN aliases, not execution names.

`docs/research/backtesting_rebuild/W4/` and `W5/` folders may still contain
**stale titles**. Execution truth is the table above.

---

## 3. Shared vocabulary (use these strings)

### Observability (never silently upgraded)

```text
OBSERVED | DERIVED | INFERRED | MODELED | UNAVAILABLE
L2_HISTORICAL_UNAVAILABLE | OUTCOME_LABEL
```

### Identity (never “best guess”)

```text
MAPPED      unique official gamePk ↔ unique Kalshi event_ticker
UNMATCHED   one side has no unique partner; retain both
AMBIGUOUS   collision (e.g. doubleheader); retain; do not pick
UNMAPPED    Kalshi-only stub; mlb_game_pk is null
```

### Market completeness (ingest / future W4; not a W3 output)

```text
L2_COMPLETE | L2_PARTIAL | TRADES_ONLY | CANDLES_ONLY | MARKET_METADATA_ONLY
```

Candles ≠ order book. Point-in-time REST snapshots taken at **collection
time** are not game-time L2.

### Money

Prices and quantities are **integer cents / integer contracts**. Do not use
naive `f64` equality for money.

---

## 4. Resource: W1 — Immutable raw foundation

```yaml
id: W1
status: ACCEPTED_CLOSED
owner: crates/research-data (foundation)
writes: Backtesting Suite/Foundation/W1/**
never_writes: Backtesting Suite/Data-Real/**
```

### What W1 is

The **raw-data control plane**. It scans the existing Kalshi v1 lake,
checksums it, and publishes honest catalogs. Downstream must cite
`path + SHA-256`.

W1 does **not** download PBP. W1 does **not** reconstruct games or markets.

### What v1 COMPLETE means

A Data-Real day marked `completeness_status=COMPLETE` means: discovered
close/settled PT-day Kalshi markets for that partition were collected.

It does **not** mean:

- lifetime-complete (open → settlement)
- L2-complete
- PBP-complete
- proven market-open price

### Lake shape (read-only)

```text
Backtesting Suite/Data-Real/MLB/2025-2026/
  manifests/date=YYYY-MM-DD.json
  raw/  events.jsonl.gz
  orderbook/  metadata + parquet (often 1m candle close stored as "orderbook")
  trades/     trades.parquet
```

W1 guard: `LakeWriteGuard` — no `File::create` under the lake root.

### W1 outputs (Foundation)

`Backtesting Suite/Foundation/W1/`

| Artifact | Role |
|----------|------|
| `lake_catalog.json` | What exists |
| `integrity_report.json` | Checksums / pairing |
| `coverage_matrix.csv` | Honesty matrix (L2/PBP often UNAVAILABLE) |
| `observability_contract.json` | Field classes |
| `starting_price_evidence.json` | Open price mostly `STARTING_PRICE_UNVERIFIED` |
| `provenance_index.json` | Clocks; `received_at` ≠ exchange time |
| `raw_artifact_refs.json` | Refs for downstream |

### W1 crate types to consume (do not fork)

- `ObservabilityKind`
- `IdentityStubV1` (`mlb_game_pk` often null)
- `RawMarketIdentity` / `RawArtifactRef`
- `StartingPriceClass`
- `ProvenanceRecord`
- `DailyManifest` / `CompletenessStatus`

### Measured W1 lake (as of CEO acceptance)

- MLB COMPLETE days: **2026-06-18 … 2026-06-30** (13 days)
- Catalog: **172** `KXMLBGAME` event_ticker, **344** tickers on those days
- 2025 COMPLETE partitions: **0** (empty probes retained)
- Data-Real PBP paths: **0**

Later DATA-INGEST expanded identity-scale Kalshi discovery **outside** this
v1 COMPLETE window. That does not rewrite W1 acceptance.

### Canonical W1 docs

- `docs/research/backtesting_rebuild/w1/`
- `docs/research/backtesting_rebuild/W1_ACCEPTANCE_PACKAGE.md`
- `docs/research/architecture-decisions/ADR-0008-orderbook-representation.md`

---

## 5. Resource: W2 — MLB event / PBP engine

```yaml
id: W2
status: ENGINE_COMPLETE
owner: crates/research-event
writes: Backtesting Suite/Foundation/W2/**
never_writes: Data-Real; production trees
```

### What W2 is

The **EVENT domain engine**: identity graph, canonical PBP events, fail-closed
`MlbGameState` transitions, deterministic replay.

Pipeline:

```text
raw StatsAPI envelope
    → canonical PBP events
    → fail-closed state transitions
    → event-time sequence
    → deterministic replay
    → honest coverage
```

W2 is **not** Kalshi market reconstruction. Tickers are **aliases**.

### Identity rule

```text
StatsAPI gamePk  (official, when observed on the payload)
       ↕  unique team-suffix match on the same calendar date
Kalshi event_ticker  (e.g. KXMLBGAME-26JUN18NYYBOS)
```

- Unique hit → `MAPPED` (copy observed `gamePk`; do not invent it)
- Zero hits → `UNMATCHED`
- Two+ hits → `AMBIGUOUS` (doubleheaders are not guessed)
- Kalshi-only → `UNMAPPED`; GameId may still be hash(event_ticker)

Internal `GameId` is canonical; tickers are aliases (ADR-0018).

### Types W2 owns

| Type | Role |
|------|------|
| `OfficialMlbGameRef` | Observed gamePk + date + abbreviations |
| `CanonicalMlbEvent` | One PBP event |
| `MlbGameState` | Inning/half/outs/score/runners/… |
| `PbpSequence` | Ordered events |
| `GameIdentity` / `MlbMatchStatus` | Mapping |
| `ingest_path` / `replay` | Parser + state machine |

`eventual_outcome` is a **label**, never a replay-at-t input.

### Original committed PBP window (W2 collect)

- Path: `Backtesting Suite/Foundation/W2/raw/statsapi/date=YYYY-MM-DD/`
- Window: **2026-06-18 … 2026-06-30**
- **174** VALID Final games, **4** postponed SKIPPED
- **13,315** canonical PBP events
- Identity on that window: **168 mapped / 4 unmatched / 2 ambiguous**

DATA-INGEST later landed additional StatsAPI PBP under
`Backtesting Suite/Foundation/Ingest/landing/` (thousands of games). Those
are **ingest artifacts**. They do not silently reopen W2/W3. W3 consumes
**COMMITTED** handoff refs only.

### Canonical W2 docs

- `docs/research/backtesting_rebuild/W2/`
- `docs/research/backtesting_rebuild/W2_ARCHITECTURE.md`
- `docs/research/backtesting_rebuild/WATERFALL_2_MLB_EVENT_RECONSTRUCTION.md`

---

## 6. Resource: W3 — MLB game / PBP reconstruction layer

```yaml
id: W3
status: ACCEPTED_CLOSED
owner: crates/research-reconstruction
cli: apps/research-w3
writes: Backtesting Suite/Foundation/W3/**
reuses: W2 parser and replay (does not fork them)
```

### What W3 is

The **job/layer** that takes **checksum-verified committed** PBP and produces
a reconstruction run: coverage, lifecycle skips, anomalies, evidence.

```text
DATA-INGEST W1CommitHandoff  (preferred)
        or
W2 collect manifest (legacy 13-day set)
        ▼
W3 reconstructs using W2 ingest_path + replay
        ▼
Foundation/W3 reports
```

W3 is **not**:

- Kalshi `MarketState` (that is **W4**)
- event ↔ market time sync (that is **W5**)
- theta / Greeks
- a second PBP parser

### Lifecycle (W3-owned)

```text
SCHEDULED | POSTPONED | CANCELLED | SUSPENDED | FINAL | LIVE | UNKNOWN
```

Postponed games are **SKIPPED**, not fake zero-event games.

### W3 acceptance snapshot (CTO 2026-08-26)

Observed committed window 2026-06-18..30:

| Metric | Value |
|--------|------:|
| VALID reconstructed games | 174 / 174 |
| Postponed SKIPPED | 4 |
| PBP events | 13,315 |
| Identity mapped / unmatched / ambiguous | 168 / 4 / 2 |
| 2024–2025 local PBP at acceptance | UNAVAILABLE |

`completeness_claimed = false` on every coverage window. Missing years are
**not** COMPLETE.

### Canonical W3 docs

- `docs/research/backtesting_rebuild/W3/` (SPEC, CONTRACTS, DATA_MODEL, HANDOFF)
- `docs/research/backtesting_rebuild/W3_CTO_ACCEPTANCE.md`
- `docs/research/backtesting_rebuild/W3_COMPLETION_REPORT.md`

Handoff: W3 provides `gamePk`, Kalshi alias when uniquely mapped, UNMATCHED /
AMBIGUOUS flags, and a causal PBP timeline. W4 must **not** treat that as a
market path.

---

## 7. Adjacent plane (not W1/W2/W3) — DATA-INGEST

Needed so Gemini does not confuse **closed reconstruction** with **later
supply**.

| | |
|--|--|
| Crate | `crates/research-ingest` |
| CLI | `apps/research-ingest` (`--authorize-network ENABLE_RESEARCH_INGEST_NETWORK`) |
| Landing | `Backtesting Suite/Foundation/Ingest/landing/` |
| Fence | Never write Data-Real or Foundation/W1, W2/raw |

Measured identity-scale run `ingest-20260826T095038Z-2bc3d10b5833`
(window 2025-04-16 … 2026-08-26):

| Metric | Count |
|--------|------:|
| StatsAPI PBP committed | 2,937 |
| Kalshi markets landed | 8,428 |
| Mapped games | 2,377 |
| Mapped game-market pairs | 4,754 |
| Unmatched Kalshi markets (retained) | 4,234 |
| Ambiguous | 0 |
| 2024 Kalshi | UNAVAILABLE (catalog starts ~2025-04-16) |

Most of that identity pass is **MARKET_METADATA_ONLY**. Some June 2026
tickers already have on-disk trades. This is **not** W3 reopening and **not**
W4 market reconstruction.

---

## 8. What comes after (do not implement from this pack)

### W4 — Kalshi market reconstruction

Rebuild per-contract market **paths** from committed Kalshi artifacts
(metadata, candles, trades, L2 only if historically observed at game time).
Classify completeness. Do not invent books from candles.

### W5 — Event ↔ market time sync

Join W3 game/PBP timeline with W4 market path. **Bidirectional join, not a
rewrite.** Keep both clocks:

```text
event_timestamp
market_timestamp
synchronization_delta
synchronization_method
synchronization_confidence
```

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING
AMBIGUOUS | UNMATCHED | UNAVAILABLE
```

Never invent PBP times from trades (or the reverse). If one side is missing,
retain the other with `UNAVAILABLE`. ADR-0003.

---

## 9. File map (absolute roots)

Workspace: `/Users/user/Desktop/Momento`

| URI-like path | Resource |
|---------------|----------|
| `docs/research/backtesting_rebuild/w1/` | W1 control docs |
| `docs/research/backtesting_rebuild/W2/` | W2 control docs |
| `docs/research/backtesting_rebuild/W3/` | W3 control docs |
| `docs/research/architecture-decisions/` | ADRs (0003 sync, 0008 book, 0018 GameId, 0021 ingest) |
| `crates/research-data/` | W1 foundation |
| `crates/research-event/` | W2 engine |
| `crates/research-reconstruction/` | W3 layer |
| `crates/research-ingest/` | DATA-INGEST (not W1–W3) |
| `Backtesting Suite/Data-Real/` | Immutable Kalshi v1 lake |
| `Backtesting Suite/Foundation/W1/` | W1 derived catalogs |
| `Backtesting Suite/Foundation/W2/` | W2 engine artifacts + raw StatsAPI |
| `Backtesting Suite/Foundation/W3/` | W3 reconstruction reports |
| `Backtesting Suite/Foundation/Ingest/` | Ingest landing + runs |

---

## 10. Invariants checklist (fail closed)

Copy this into answers about W1–W3:

1. Do not overwrite historical bytes. New parsers → new versioned outputs.
2. Do not write Data-Real from W1/W2/W3/ingest-as-W4.
3. Do not invent `gamePk`, tickers, L2, mid, fees, or PBP plays.
4. Do not upgrade `UNAVAILABLE` / `AMBIGUOUS` / candle → L2.
5. Do not assume an ingest-time REST orderbook is the book at pitch `t`.
6. Do not drop UNMATCHED streams because a join failed.
7. Do not treat W3 output as Kalshi market data.
8. Do not start W4/W5 unless the user explicitly authorizes that waterfall.
9. Do not edit production trading code as part of research.
10. Report measured counts; never manufacture coverage to hit a target.

---

## 11. Suggested Gemini system preamble

When this file is attached as context:

> You are answering from Momento research waterfalls W1 (immutable Kalshi
> lake foundation), W2 (MLB PBP/GameState engine), and W3 (reconstruction
> job over committed PBP). All three are closed. Identity is
> MAPPED/UNMATCHED/AMBIGUOUS only. Candles are not books. W4 is market
> reconstruction; W5 is two-clock event–market sync. If asked to change
> W1–W3 code or the Data-Real lake, refuse and point to the owner.

---

## 12. Pointers (human docs)

| Need | Read |
|------|------|
| Current program state | `docs/research/BACKTEST_ENGINE_CURRENT_STATE.md` |
| CEO/CTO spec | `docs/research/BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md` |
| Agent rules | `AGENTS.md`, `.cursor/rules/11-historical-research-engine.mdc` |
| W3 handoff to W4 | `docs/research/backtesting_rebuild/W3/HANDOFF.md` |
| Ingest corpus | `docs/research/backtesting_rebuild/ingest/WATERSTREAM_REPORT.md` |
