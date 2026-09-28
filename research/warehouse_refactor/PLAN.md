# ROLLER — Complete warehouse + conditional backtest refactor

**Status:** Phases 0–20 COMPLETE (measured 2026-09-13).  
**Execution order:** all phases, **NBA first**.  
**End-state:** a functioning NBA research desk (Phase 20). Confirm & Run remains CSV. Do not start Phase 21.

This is the governing waterfall. Do not skip phases. Do not start a later phase until the current phase’s NBA gate passes.

Prior reports (facts, not a substitute for this plan):

- Phase 0: [`PHASE_0_RECON.md`](PHASE_0_RECON.md)
- Phase 1: `ROLLER/roller/warehouse/entities.py` (no separate Phase 1 report)
- Phase 2: [`PHASE_2_IDENTITY.md`](PHASE_2_IDENTITY.md)
- Phase 3: [`PHASE_3_MARKET_LINK.md`](PHASE_3_MARKET_LINK.md)
- Phase 4: [`PHASE_4_MARKET_OBSERVATIONS.md`](PHASE_4_MARKET_OBSERVATIONS.md)
- Phase 5: [`PHASE_5_PBP.md`](PHASE_5_PBP.md)
- Phase 6: [`PHASE_6_SETTLEMENT.md`](PHASE_6_SETTLEMENT.md)
- Phase 7: [`PHASE_7_ORDERBOOK.md`](PHASE_7_ORDERBOOK.md)
- Phase 8: [`PHASE_8_PARQUET_LAYOUT.md`](PHASE_8_PARQUET_LAYOUT.md)
- Phase 9: [`PHASE_9_CATALOG.md`](PHASE_9_CATALOG.md)
- Phase 10: [`PHASE_10_RESEARCH_CONTEXT.md`](PHASE_10_RESEARCH_CONTEXT.md)
- Phase 11: [`PHASE_11_QUERY_COMPILER.md`](PHASE_11_QUERY_COMPILER.md)
- Phase 12: [`PHASE_12_CONDITIONAL_BACKTEST.md`](PHASE_12_CONDITIONAL_BACKTEST.md)
- Phase 13: [`PHASE_13_REFERENCE_OPTIMIZED.md`](PHASE_13_REFERENCE_OPTIMIZED.md)
- Phase 14: [`PHASE_14_EDGE_CASES.md`](PHASE_14_EDGE_CASES.md)
- Phase 15: [`PHASE_15_PERFORMANCE.md`](PHASE_15_PERFORMANCE.md)
- Phase 16: [`PHASE_16_PARQUET_EXECUTION.md`](PHASE_16_PARQUET_EXECUTION.md)
- Phase 17: [`PHASE_17_AUTO_ROLLER_INGEST.md`](PHASE_17_AUTO_ROLLER_INGEST.md)
- Phase 18: [`PHASE_18_AUTO_ROLLER_VERIFY.md`](PHASE_18_AUTO_ROLLER_VERIFY.md)
- Phase 19: [`PHASE_19_FRONTEND_STRATEGY_CREATION.md`](PHASE_19_FRONTEND_STRATEGY_CREATION.md)
- Phase 20: [`PHASE_20_FULL_NBA_RESEARCH_DESK.md`](PHASE_20_FULL_NBA_RESEARCH_DESK.md)

**Phases 0–20 are complete.** NBA identity, GameMarketLink, 1-minute TRADABLE_YES_BID observations, PBP (sequence-only; `pbp_pit_aligned_to_candles=false`), Kalshi settlement, orderbook SOURCE_UNAVAILABLE, physical Parquet layout, coverage catalog, ResearchContext, isolated query compiler, conditional backtest, reference ≡ optimized, edge/failure suite, performance, parquet-only warehouse-backed execution, source-driven warehouse ingest, Auto Roller verify, frontend ResearchQuestion construction, full NBA desk acceptance. Confirm & Run still reads CSV. Historical L2/tick remain `DATA_REQUIRED`. PBP↔candle PIT remains `OPERATION_REQUIRED`. Candle-path results are not fills. Do not start Phase 21.

---

## End-state objective

By the end of Phase 20 the four layers are **one connected system**:

```text
ROLLER DESKTOP
      → STRATEGY CREATION
      → ResearchQuestion
      → CAPABILITY RESOLUTION
      → QUERY COMPILER
      → CANONICAL NBA WAREHOUSE
            ├── Game
            ├── Market  → Observations
            ├── PBP
            └── Settlement
      → ResearchContext
      → CONDITIONAL EXECUTION
            ├── REFERENCE ENGINE
            └── OPTIMIZED ENGINE
      → ROW-LEVEL DIFF
      → RESULTS
            ├── W / L
            ├── R:R
            ├── EV (only when basis permits)
            ├── STATISTICAL SUPPORT
            └── COVERAGE / AUDIT
```

A user can construct a **previously unseen valid NBA strategy** in the existing ROLLER frontend, submit it, have the backend resolve it against the canonical warehouse, execute the exact conditional backtest, and receive trustworthy W/L, R:R, EV, statistical support, coverage, and row-level audit on Results.

The same architecture must support NCAAB/MLB **where the data actually permits it**. Those sports must not invent coverage, and they must not block the NBA desk.

---

## NBA-first rule

Finish **every phase for NBA** before treating that phase as a multi-sport completion.

| Sport | Role |
| --- | --- |
| **NBA** | End-to-end acceptance target. Every phase gates on NBA. Phase 20 is an NBA desk. |
| **NCAAB** | Same contracts. Apply when source data exists. Known gaps (no `kalshi_markets.csv`, 4 431 games without source id) are `DATA_REQUIRED` / identity-without-source — not an excuse to fake markets or block NBA. |
| **MLB** | Same contracts. `LAST_TRADE_PRINT` ≠ `TRADABLE_YES_BID`. Do not convert prints into yes-bid. Do not block NBA on MLB completeness. |
| Tennis / NHL / WNBA desk | Out of this program. Do not add tennis work. NHL stays `SOURCE_UNAVAILABLE`. |

Per-phase implication:

- Implement the NBA path first.
- Persist/measure NCAAB/MLB only when the phase’s work is identity-safe and data-true.
- A phase may **record** NCAAB/MLB gaps without closing them.
- Phase 20 does **not** wait for NCAAB settlement or MLB orderbook history.

---

## Locked architectural rules

These do not reopen.

```text
frontend spec → ResearchQuestion → capability resolution → warehouse plan
  → canonical linked data → exact ops → Results
```

A frozen lock is **evidence of historical correctness**. It is **never** the mechanism that makes a new strategy executable.

Hard no-fallbacks (STOP + report):

- unsupported ≠ substitute; Cross ≠ First Touch; Break ≠ Cross
- missing / unavailable / unaligned ≠ zero
- `ZERO RESULTS` ≠ `DATA_REQUIRED` ≠ `OPERATION_REQUIRED`
- last trade ≠ yes bid; candles ≠ fills
- path WIN ≠ terminal YES; GAME ≠ TICKER
- PBP identity ≠ PBP temporal alignment
- no implicit midpoint; no invented OHLC; no L2 synthesis
- no generic `price`
- no query-time ticker/date/team identity guess
- no `get_research_context` until Phase 10
- no execute/compiler cutover until the phase that names it
- no CSV → Parquet sole-read until Phase 16
- no performance work until Phase 15
- detectors stay in `operations.py`
- extend `ROLLER/roller/warehouse/` — do not create a second warehouse package

Historical locks remain regression fixtures only. Do not delete or rewrite:

- Increment 2: 1087 / 271 / 1552 / 288
- FIRST80 frozen: 290
- NCAAB P5: 721
- MLB FT75/TE: 554
- MLB 1661 verify-only

Ordinary generic research must not require `frozen_reference` / `execute_research_object`. FIRST80 stays on `execute_research_object` only.

Out of program: tennis warehouse/UI, NHL invention, W9, live trading, Risk, Kalshi submit, FIRST01 live, SuperASI, STAX, frontend redesign.

---

## Progress

| Phase | Name | NBA gate | Status |
| ---: | --- | --- | --- |
| 0 | Recon | Census complete, architecture stopped | **COMPLETE** |
| 1 | Canonical entities | Types exist; unused by Confirm & Run | **COMPLETE** |
| 2 | Game identity | Deterministic `internal_game_id` | **COMPLETE** |
| 3 | Market identity + GameMarketLink | Persistent NBA Game ↔ Market | **COMPLETE** |
| 4 | Market observations | Complete available NBA 1m history | **COMPLETE** |
| 5 | PBP | NBA events in warehouse; identity ≠ PIT | **COMPLETE** |
| 6 | Settlement | NBA Kalshi YES/NO/MISSING/INVALID | **COMPLETE** |
| 7 | Orderbook | Truthful NBA availability | **COMPLETE** |
| 8 | Physical Parquet layout | NBA layout documented + benchmarked | **COMPLETE** |

Phase 0–8 measured pytest baseline (Phase 8 closeout, re-collected after Phase 14): **85** = Phase 0–5 files **62** + Phase 6–8 files **23**. The Phase 9–11 closeout labeled this **87** while reporting Total **111**; that 87 is a mislabel (`87+8+8+10=113`). The collected 0–11 suite was always `85+8+8+10=111`. No Phase 0–8 test function was removed.
| 9 | Catalog + coverage | Cheap NBA READY / DATA_REQUIRED / OPERATION_REQUIRED | **COMPLETE** |
| 10 | ResearchContext | `get_research_context` for a valid NBA question | **COMPLETE** |
| 11 | Compiler / capability planner | Arbitrary valid NBA spec compiles without a lock | **COMPLETE** |
| 12 | Conditional backtest engine | Exact NBA spec → correct population and rows | **COMPLETE** |
| 13 | Reference + optimized | Zero unexplained NBA row diffs | **COMPLETE** |
| 14 | Edge / failure suite | Every NBA failure mode explicit | **COMPLETE** |
| 15 | Performance | Fast; Phase 13 still green | not started |
| 16 | Parquet sole execution source | One NBA Confirm & Run read path | not started |
| 17 | Auto Roller ingest | Warehouse-driven NBA ingest | not started |
| 18 | Auto Roller verify | Detects NBA warehouse/execution regression | not started |
| 19 | Frontend capability + strategy creation | Existing UI compiles a new NBA spec | not started |
| 20 | Full NBA research desk | Connected desk, not unit tests alone | not started |

---

## Phase 0 — Recon (COMPLETE)

Establish the factual current state from disk: NBA / NCAAB / MLB, CSV, Parquet, `rq_index`, Suite, PBP, settlements, identity, markets, orderbook, loaders, compiler, execution, frozen objects, frontend capability language.

Gate: recon complete and architecture stopped. Report: `PHASE_0_RECON.md`.

---

## Phase 1 — Canonical entities (COMPLETE)

Six logical types, unused by Confirm & Run:

`Game` · `Market` · `MarketObservation` · `PBPEvent` · `Settlement` · `GameMarketLink`

No generic `price`. Bases: `TRADABLE_YES_BID` → `yes_bid_close`; `LAST_TRADE_PRINT` → `last_close_e4`; `ORDERBOOK_SNAPSHOT` → TOB only.

Settlement: `YES` / `NO` / `MISSING` / `INVALID`.  
Link: `LINKED` / `UNLINKED` / `AMBIGUOUS` / `INVALID`.

---

## Phase 2 — Canonical Game identity (COMPLETE)

```text
source_game_id → deterministic identity → internal_game_id → Game
```

Preserve existing valid IDs (`NBA_{date}_{away}_{home}`, `MLB_…_{game_pk}`). No ticker guess. Report: `PHASE_2_IDENTITY.md`.

---

## Phase 3 — Market identity + GameMarketLink (NEXT)

Persistent, versioned:

```text
KXNBAGAME…
      ↓
Market
      ↓
GameMarketLink
      ↓
NBA_…
```

or an explicit `UNLINKED` / `AMBIGUOUS` / `INVALID`. No query-time guessing.

**NBA gate:** every NBA Kalshi market/game relationship is deterministic and auditable.  
NCAAB/MLB: link what evidence supports; do not invent NCAAB markets; do not start Phase 4.

---

## Phase 4 — Complete market observations

Every **available** Kalshi 1-minute observation for every available NBA game/market — not merely FIRST80.

Preserve `yes_bid_close`, `yes_ask_close`, `volume`, `available_at`, source OHLC, source timestamps, observation basis.

Never fabricate minutes, interpolate, forward-fill, invent OHLC, or convert last trade into YES bid.

**NBA gate:** coverage audit passes for available NBA observations. Absent minutes stay absent.

---

## Phase 5 — PBP

NBA event-level game state in the canonical warehouse: event ID, source ID, `internal_game_id`, period, game clock, event timestamp, score/state fields the source actually supplies, possession/state only where the source has it.

```text
PBP identity linkage  ≠  PIT temporal alignment
```

The warehouse records the event. Later planning decides whether it can legally support a point-in-time condition.

**NBA gate:** no interpolated or invented PBP timestamps.

---

## Phase 6 — Settlement

Authoritative Kalshi settlement on the Market:

`YES` / `NO` / `MISSING` / `INVALID`

Never `final score → inferred YES`.

**NBA gate:** settlement coverage and provenance are explicit.

---

## Phase 7 — Orderbook

Ingest actual historical snapshots where they exist. If unavailable: `SOURCE_UNAVAILABLE`, not fake L2.

**NBA gate:** orderbook availability is truthful and queryable (NBA orderbook is currently a stub / missing — say so).

---

## Phase 8 — Physical Parquet layout

Decide the physical warehouse (example):

```text
warehouse/
    games/
    markets/
    observations/
    pbp/
    settlements/
    game_market_links/
```

Partition grain, sort keys, compression, file sizes, scan patterns, predicate pushdown, game / market / time-range access.

Benchmark **before** changing execution.

**NBA gate:** physical design documented and validated. Execute still reads today’s published source.

---

## Phase 9 — Catalog + coverage

Answer “do I have enough data to run this question?” without loading the warehouse.

Catalog understands: sport, league, season, date range, game, market, observation basis, PBP, settlement, orderbook, coverage.

A query can be `READY` / `DATA_REQUIRED` / `OPERATION_REQUIRED` before execution.

**NBA gate:** coverage resolves cheaply and accurately for NBA questions.

---

## Phase 10 — ResearchContext

```text
ResearchQuestion → get_research_context() → ResearchContext
```

The frontend never sees filesystem paths. A game is loaded once into context; detectors do not rediscover it.

**NBA gate:** a valid NBA question receives a complete typed `ResearchContext`.

---

## Phase 11 — Query compiler / capability planner

Translate every valid frontend specification into an executable plan. Example:

```text
NBA / 2025–26 / Kalshi / Candles / CROSS 63¢ / Q2 / REACH 87¢ / LOSS REACH 41¢ / BOTH
```

Compiler must understand season, date range, market, observation basis, entry operation, price, period, clock, multiple entries, AND, exit, terminal, PIT requirements.

A frontend chip being **recognized** does not mean it is **supported**. Output is `READY` / `DATA_REQUIRED` / `OPERATION_REQUIRED`.

**NBA gate:** arbitrary valid NBA specifications compile without frozen locks.

---

## Phase 12 — Conditional backtest engine (COMPLETE)

Execute the selected specification against `ResearchContext`. Not a template. Not FIRST80. Not a special backtest.

```text
Universe → Game → Market → Observations → PBP/PIT → entry detector
  → period/clock → AND → WIN/LOSS path → Settlement → Classification
```

Preserve detector authority: Cross, Touch, Break, Reversion, Bounce, Recovery, Above, Below, Maximum Touch, Minimum Touch. No semantic substitutions.

**NBA gate:** the selected NBA specification produces the correct population and event rows.

---

## Phase 13 — Reference + optimized engines (COMPLETE)

Both consume the same `ResearchContext`.

- Reference: slow / obvious / semantic oracle
- Optimized: fast production implementation

Compare **rows**, not only `N = N`:

game, market, entry timestamp, entry price, entry operation, WIN/LOSS, exit timestamp, exit price, classification.

**NBA gate:** zero unexplained row-level differences.

---

## Phase 14 — Edge case / failure suite (COMPLETE)

Protect the desk from silent bad research. At minimum:

no market · no PBP · no settlement · missing minutes · missing `internal_game_id` · ambiguous link · same-minute ties · OT · period boundaries · multiple entry conditions · repeated touches · missing next bar · jump-through exits · game clock filters · DST · doubleheaders · duplicate observations · malformed records · empty populations

`ZERO RESULTS` remains different from `DATA_REQUIRED` and `OPERATION_REQUIRED`.

**NBA gate:** every failure mode is explicit.

---

## Phase 15 — Performance

Only now. Predicate pushdown, partition pruning, game-level caching, market-level indexing, observation scans, PBP joins, repeated queries, safe parallelism, memory.

Optimization cannot change semantics.

**NBA gate:** optimized engine still passes Phase 13 row-level equivalence.

---

## Phase 16 — Parquet as the sole execution source

```text
CANONICAL WAREHOUSE → PARQUET → NEW WAREHOUSE-BACKED RESEARCH EXECUTION
```

`compile_research` / `get_research_context` / `run_conditional_backtest` read Phase 8 parquet only. Confirm & Run remains an explicit CSV + `rq_index` + FIRST80 legacy boundary until a later authorized cutover.

**NBA gate:** new warehouse-backed NBA research execution is parquet-only. Confirm & Run is unchanged.

---

## Phase 17 — Auto Roller ingest

```text
AUTO ROLLER → INGEST → VERIFY → CANONICAL WAREHOUSE
```

Daily: discover missing data, acquire observations, update PBP / settlement / available orderbook, validate, write warehouse, update catalog. No strategy-specific ingestion.

**NBA gate:** Auto Roller updates the NBA warehouse without changing research semantics.

---

## Phase 18 — Auto Roller verify

Verify that existing ROLLER backtests remain accurate against the current warehouse.

Detect: changed source data, missing files, broken identity, coverage regression, changed observation fingerprints, execution regression, golden regression.

It must not redefine the warehouse.

**NBA gate:** automated integrity/accuracy verification works for the NBA desk path.

---

## Phase 19 — Frontend capability + strategy creation

**Do not redesign the existing ROLLER UI.** Connect the existing controls to the compiler.

The user can construct:

- Universe: sport, league, season, date from/to
- Observation: Kalshi, candles, last trade, tick, orderbook — with **actual** capability status
- Entry: Touch, Cross, Break, Reversion, Bounce, Recovery, Above, Below, Maximum Touch, Minimum Touch + price, from/to, ordinal, period, clock, second condition, AND
- Exit: independent WIN / LOSS (hold, reach, drop, rise, recover, clock-based where supported)

Before run, the UI shows `READY` or `DATA REQUIRED` or `OPERATION REQUIRED`.

That is the point ROLLER becomes a strategy-creation interface rather than a template selector.

**NBA gate:** a brand-new NBA spec can be built and honestly resolved in the existing UI.

---

## Phase 20 — Full NBA research desk (acceptance)

Phase 20 is **not** “the test suite is green.”

It is complete only when a researcher can use ROLLER as an NBA desk:

```text
CREATE NEW NBA STRATEGY
      → FRONTEND
      → ResearchQuestion
      → CAPABILITY CHECK
      → CANONICAL WAREHOUSE
      → ResearchContext
      → CONDITIONAL BACKTEST
      → REFERENCE ENGINE
      → OPTIMIZED ENGINE
      → ROW-LEVEL EQUIVALENCE
      → RESULTS
```

### Test 1 — Brand-new strategy

Construct an NBA question that has **never existed as a frozen research object**. Example:

```text
NBA
2025–26
Kalshi
Candles
Q2
CROSS 63¢
WIN:  REACH 87¢
LOSS: REACH 41¢
```

Submit it. It must not search for a FIRST80 lock. It must not require a frozen object. It must compile and execute if data/capabilities support it.

### Test 2 — Conditional population

Results must show exactly what was tested: universe games/markets, entry candidates, qualified rows, entry operation, period.

### Results page — required final contract

**Population:** games, markets, entry events, qualified trades.

**Trade outcome:** WIN, LOSS, W-L, win rate, loss rate.

**Risk / reward** from the actual entry and exits, e.g. entry 63¢ / WIN 87¢ / LOSS 41¢ → reward 24¢ / risk 22¢ → R:R 1.09 : 1.

**EV** only when the observation basis supports economic calculation:

- `TRADABLE_YES_BID` → EV permitted when exit semantics support it
- `LAST_TRADE_PRINT` → executable population EV unavailable — say so explicitly

Must show expected value, expected return, break-even win rate, observed win rate when permitted. Must **not** display executable EV where source semantics do not support it.

**Statistical reporting:** N, WIN, LOSS, win rate, loss rate, 95% CI, coverage. A 75% win rate without N is a failed desk.

**Data integrity:** observation basis, data coverage, settlement coverage, PBP coverage, ambiguous rows, missing rows. Distinguish `MISSING` / `UNAVAILABLE` / `UNCLASSIFIED` / `ZERO RESULTS`.

**Execution verification:** reference vs optimized, rows compared, exact matches, differences, `STATUS: VERIFIED` when appropriate.

**Reproducibility:** every result retains ResearchQuestion, compiler/version, warehouse version, identity version, observation basis, entry/exit spec, execution version, data fingerprint.

### What “complete” means

ROLLER is not complete because the warehouse exists. It is complete when all four layers work together:

1. **Data warehouse** — Game, Market, GameMarketLink, MarketObservation, PBPEvent, Settlement with truthful provenance and coverage.
2. **Conditional backtest engine** — new frontend combinations, not only historical locked objects.
3. **Strategy creation** — existing ROLLER UI expresses the question and receives honest capability resolution.
4. **Results** — population → W/L → R:R → EV → statistical support → coverage → execution verification for the strategy that was actually run.

---

## Stop conditions

- After locking this plan: **do not start Phase 3 until the next implementation turn is authorized.**
- After each phase: write `research/warehouse_refactor/PHASE_N_*.md`, run that phase’s tests, **STOP**.
- If a required NBA identity/link/coverage fact cannot be established: `UNCLEAR` + STOP. No guessing.
