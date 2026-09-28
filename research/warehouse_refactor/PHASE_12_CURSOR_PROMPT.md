# ROLLER Phase 12 — Conditional Backtest Engine

**Paste this entire file into a new Cursor agent chat.**

Phases 0–11 are COMPLETE and FROZEN. Do not clean them up. Do not restyle them.

NBA only.

Do not start Phase 13+ (no dual reference/optimized engines, no EV/CI Results, no frontend, no Parquet cutover).

Confirm & Run continues to read published CSV. Do not cut Confirm & Run over to Parquet.

Phase 12 is the first phase that **scans observation rows and evaluates conditions**.

It must consume the frozen contracts:

```text
ResearchQuestion
      ↓
Catalog.resolve
      ↓
ResearchContext
      ↓
ResearchPlan
      ↓
Phase 12 Conditional Backtest Engine
      ↓
BacktestResult
```

Do not invent a second strategy-specific execution path. Do not call FIRST80. Do not edit Confirm & Run `execute.py` / `compiler.py` / `load_dataset`.

---

# 0. FROZEN STATE

Treat these as frozen. Do not change their semantics, fingerprints, or public shapes unless a hard stop forces a report (then STOP; do not workaround).

```text
PHASE 0–8   Canonical NBA warehouse (Parquet)
PHASE 9     get_catalog / CoverageResolution
PHASE 10    get_research_context / ResearchContext
PHASE 11    compile_research / ResearchPlan
```

Measured warehouse (do not re-derive from CSV):

```text
ROLLER/data/nba/2025_2026/derived/warehouse/
  1,362 games
  2,724 markets / LINKED GameMarketLink rows
  6,165,183 TRADABLE_YES_BID 1-minute rows
  PIT field = available_at
  2,724 settlements  YES 1,359 / NO 1,359 / INVALID 6 / MISSING 0
  780,137 PBP events
  pbp_pit_aligned_to_candles = false
  orderbook SOURCE_UNAVAILABLE / 0 rows
```

Frozen planning-layer example (not FIRST80):

```text
NBA 2025-2026 · TRADABLE_YES_BID · 1-minute · PIT available_at
date 2025-10-10
Q2 CROSS 63¢ · WIN REACH 87¢ · LOSS REACH 41¢ · HOLD_TO_SETTLEMENT
```

Phase 10 measured slice for that question:

```text
READY
5 games / 10 markets / 5,125 observations / 3,176 PBP
NBA_20251010_BOS_TOR: 1,136 candles, 613 PBP, BOS=YES, TOR=NO
```

Phase 11 measured plan:

```text
status            READY
plan_hash         4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
terminal          HOLD_TO_SETTLEMENT
entries           CROSS 6300 e4 period=Q2
exits             win REACH 8700 ; loss REACH 4100
```

Governing plan: `research/warehouse_refactor/PLAN.md`.
Agent rule: `.cursor/rules/14-warehouse-refactor.mdc`.

---

# 1. OBJECTIVE

Build **one** NBA conditional backtest engine that executes a `READY` `ResearchPlan` against a `ResearchContext`.

```text
Universe
  → Game
  → Market          (via GameMarketLink only)
  → Observations    (TRADABLE_YES_BID, ordered by available_at)
  → PBP / PIT state where required
  → Entry detector  (operations.py authority)
  → Period / clock filters
  → AND intersection
  → WIN / LOSS path
  → Settlement
  → Classification
```

**NBA gate:** the selected NBA specification produces the correct population and event rows.

Phase 12 reports rows. It does **not** invent EV, CI, fills, slippage, or live P&L.

Phase 13 will add a second engine and row-level compare. Do not build two engines now.

---

# 2. WHAT PHASE 12 IS NOT

Do not:

* edit Phase 9–11 modules except to *call* them
* edit `ROLLER/roller/research_query/execute.py`
* edit `ROLLER/roller/research_query/compiler.py`
* edit `ROLLER/roller/admin.py` `load_dataset`
* edit `official_settlement.py`
* call FIRST80 / `execute_research_object` / `frozen_reference`
* start W9, Risk, live execution, SuperASI, STAX, frontend redesign
* upgrade candles to ticks / L2 / orderbook
* infer settlement from score, PBP, or last price
* treat `INVALID` as `NO`
* treat `ZERO_RESULTS` as `DATA_REQUIRED` or `OPERATION_REQUIRED`
* treat path WIN as terminal YES
* claim `pbp_pit_aligned_to_candles = true`
* persist a new aligned PIT dataset
* rewrite detector semantics
* optimize for speed (Phase 15)
* switch Confirm & Run to Parquet (Phase 16)

---

# 3. MODULE PLACEMENT

Inspect `ROLLER/roller/warehouse/` first.

Add a new isolated module, for example:

```text
ROLLER/roller/warehouse/conditional_backtest.py
```

Public entry (repository-equivalent name is fine if clearer):

```text
run_conditional_backtest(question, cfg=None) → BacktestResult
```

or, if you keep the steps explicit:

```text
run_conditional_backtest(plan, context) → BacktestResult
```

If you expose the two-argument form, also expose a one-call wrapper that:

1. `compile_research(question)`
2. if plan status is not READY → return that status, **do not scan**
3. `get_research_context(question)`
4. if context status is not READY → return that status, **do not scan**
5. execute against the typed context

Do not put Phase 12 inside Confirm & Run `execute.py`.

Update `test_live_execute_paths_do_not_import_entities` so Confirm & Run still must not import the new module.

---

# 4. REUSE — DO NOT DUPLICATE

**Reuse as contracts / inputs:**

| Object | Module |
| --- | --- |
| `ResearchQuestion` | `roller.research_query.models` |
| `ResearchStatus` | `roller.research_query.models` |
| `EntryOp` / `PathOp` / `ExitOutcome` | `roller.research_query.models` |
| `get_catalog` / `CoverageResolution` | `roller.warehouse.coverage` |
| `get_research_context` / `ResearchContext` | `roller.warehouse.query_context` |
| `compile_research` / `ResearchPlan` | `roller.warehouse.research_compiler` |
| Detector authority | `roller.research_query.operations` |
| Path crossing geometry | `roller.research_query.path_engine` (`first_later`, `reach_from_side`, `drop_to`, `rise_to`) |
| `TradableBar` | `roller.research_query.entry_engine` |
| Candle PIT visibility | `roller.base_terminal_efficiency.pit` (`available_at < t`; equality invisible) |

**Do not reuse as the execution driver:**

* `compile_question`
* `plan_query`
* `evaluate_ticker` / Confirm & Run `execute.py`
* FIRST80
* `official_settlement.py`
* CSV `catalog()` / `load_dataset`

Detectors stay in `operations.py`. Phase 12 **calls** them. It does not copy their inequalities into a new file and drift.

---

# 5. ADAPTER: MarketObservation → TradableBar

Phase 12 must not invent a generic `price`.

For this version:

```text
bar.bid     = MarketObservation.yes_bid_close    (e4 integer)
bar.ts      = parse(MarketObservation.available_at)   # PIT clock
bar.basis   = TRADABLE_YES_BID
bar.ticker  = observation.ticker
bar.game_id = link-resolved internal_game_id
```

Never use `event_timestamp`, `settlement_time`, or `yes_bid_close` as the PIT clock.

Never put `last_close_e4` on these bars.

Sort one market’s bars by `available_at` ascending. Absent minutes stay absent. Do not forward-fill.

Identity for every row:

```text
market_id → GameMarketLink → internal_game_id
```

Drop (do not guess) any observation whose ticker is not LINKED or whose stamped `internal_game_id` disagrees with the link.

---

# 6. EXECUTION PIPELINE

Implement this loop. Do not template it as FIRST80.

## 6.1 Fail closed before any scan

If `ResearchPlan.status` or `ContextResult.status` is:

* `DATA_REQUIRED` → return that status, empty rows
* `OPERATION_REQUIRED` → return that status, empty rows

Do not scan candles to “see if anything matches.”

L2 / tick / orderbook / trade-tape questions remain `DATA_REQUIRED`.
Questions that request `PBP_MARKET_PIT_ALIGNMENT` as a capability remain `OPERATION_REQUIRED`.

A Q2 period **chip** on a READY candle plan is a period filter (below). It is not a request to persist warehouse PIT alignment.

## 6.2 Universe → Game → Market

From `ResearchContext`:

* iterate games in deterministic `internal_game_id` order
* for each game, iterate LINKED markets in deterministic `ticker` order
* skip UNLINKED / AMBIGUOUS / INVALID links

## 6.3 Entry

Map each `ResearchPlan.entries[]` op onto `operations.py`:

| Plan op | Authority |
| --- | --- |
| CROSS | `first_cross` |
| FIRST_TOUCH / TOUCH | existing touch ordinal in `entry_engine.nth_touch` (do not redefine Cross as Touch) |
| BREAK | `first_break` |
| REVERSION | `first_reversion` |
| BOUNCE | `first_bounce` |
| RECOVERY | `first_recovery` (propagate `RecoveryInvalid` as fail-closed, not ZERO_RESULTS) |
| ABOVE | `first_above` |
| BELOW | `first_below` |
| MAXIMUM_TOUCH | `first_maximum_touch` |
| MINIMUM_TOUCH | `first_minimum_touch` |

Preserve price, range (`price_to_e4`), ordinal, direction, order.

**AND:** two compiled entries with `conjunction=AND` both must qualify on the same market. Do not collapse them into one detector. Intersection is on the market/game after each entry is identified — inspect existing AND semantics in `entry_engine` / Confirm & Run only as **reference**, then implement against `ResearchPlan` + `ResearchContext`. If AND timing is ambiguous, STOP and report rather than guess.

Cross ≠ First Touch. Break ≠ Cross. Do not substitute.

## 6.4 Period / clock

Interpretation already implemented for Confirm & Run and documented in `entry_engine`:

```text
Identify the game-level event first.
Then apply period/clock as a filter.
```

Reuse that interpretation. Reuse existing period-name mapping (`Q2` ↔ warehouse/PBP period vocabulary). Do not invent `Q2` from candle OHLC.

Candle PIT for visibility remains:

```text
I(t): available_at < observation_ts
equality is invisible
```

(`roller.base_terminal_efficiency.pit`)

This does **not** flip the warehouse flag `pbp_pit_aligned_to_candles` to true. Phase 5 storage is still identity-only. Phase 12 may *use* existing visibility + period-name filters at execution time. It must not write a new aligned join table and must not claim the warehouse now has PBP↔candle PIT alignment.

If a required period/clock snap cannot be formed from loaded PBP (missing PBP, unaligned snap, missing clock when clock was requested):

```text
unaligned / missing ≠ zero
```

Count it as a coverage exclusion, not as `ZERO_RESULTS`, and not as `DATA_REQUIRED`.

## 6.5 WIN / LOSS path

Independent predicates from `ResearchPlan.exits`.

Reuse `path_engine`:

* entry bar cannot satisfy an exit
* REACH is directional from the entry-close side (`reach_from_side`)
* DROP / RISE / RECOVER keep existing geometry
* HOLD means that side has no price barrier
* CLOCK uses compiled `horizon_kind` / `horizon_minutes` if present; if the required clock snap is missing, fail that predicate closed (unaligned), do not invent elapsed time

First exit that hits wins that market. If both WIN and LOSS would hit on the same later bar, fail closed and record the tie — do not pick a winner to make a test pass.

## 6.6 Terminal + settlement + classification

Keep these distinct:

```text
path WIN / path LOSS
  ≠
settlement YES / NO / INVALID / MISSING
  ≠
HOLD_TO_SETTLEMENT / NO_TERMINAL_RESULT
```

If a WIN or LOSS exit hits: classification is that path outcome. Attach settlement as a **separate** field. Do not rewrite WIN→YES.

If neither exit hits:

* `HOLD_TO_SETTLEMENT` → classification `HELD_TO_SETTLEMENT` (or repository-equivalent). Attach warehouse `Settlement.result`. `INVALID` stays `INVALID`. `MISSING` stays `MISSING`. Do not coerce to NO.
* `NO_TERMINAL_RESULT` → classification `NO_TERMINAL_RESULT`. Do not attach an inferred settlement winner.

Never derive settlement from final score, PBP, last candle, or price 0/100.

## 6.7 ZERO_RESULTS

New **execution** status only:

```text
Plan READY
Context READY
Engine ran
Qualifying population = 0
```

→ `ZERO_RESULTS`

Not a catalog status. Not a compiler status. Not missing data.

---

# 7. RESULT TYPE

Add a frozen `BacktestResult` (name may follow repo convention) with at least:

```text
status                  READY | ZERO_RESULTS | DATA_REQUIRED | OPERATION_REQUIRED
plan_hash               copy from ResearchPlan
warehouse_version
observation_basis       TRADABLE_YES_BID
pit_field               available_at
population_n            markets that qualified for entry
row_count
rows                    deterministic tuple
exclusions              counts by reason (unaligned, no_link, no_obs, …)
engine_version
```

Each event row must include:

```text
internal_game_id
ticker / market_id
entry_op
entry_available_at
entry_yes_bid_close_e4
path_outcome            WIN | LOSS | HELD_TO_SETTLEMENT | NO_TERMINAL_RESULT
exit_op                 if any
exit_available_at       if any
exit_yes_bid_close_e4   if any
settlement_result       YES | NO | INVALID | MISSING | (empty if not attached)
```

No generic `price`. No filesystem paths. No `current_time` in the semantic payload.

Same question + same warehouse/catalog/compiler version + same engine version → identical rows and identical `to_dict` / hash.

Do not compute EV, R:R, CI, win rate, or P&L in Phase 12.

---

# 8. REQUIRED LIVE SPEC (not FIRST80)

Execute this exact specification against the canonical warehouse:

```text
Universe:     NBA 2025-2026, date 2025-10-10
Observation:  TRADABLE_YES_BID, 1-minute, PIT available_at
Entry:        Q2 CROSS 63¢
WIN:          REACH 87¢
LOSS:         REACH 41¢
Terminal:     HOLD_TO_SETTLEMENT
```

Prove:

```text
Catalog:   READY
Context:   READY, canonical parquet (5 games / 10 markets on this date)
Plan:      READY, plan_hash
           4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
Engine:    ran
Backtest:  EXECUTED
```

Record **measured** population N and row hashes. Do not invent them. Do not force them to match FIRST80 290 or Increment-2 locks.

Also prove:

```text
L2 / tick request          → DATA_REQUIRED, 0 rows scanned
PBP_MARKET_PIT_ALIGNMENT   → OPERATION_REQUIRED, 0 rows scanned
READY + empty population   → ZERO_RESULTS, not DATA_REQUIRED
INVALID settlement         → INVALID, not NO
```

A useful empty/invalid fixture already exists: `NBA_20260108_MIA_CHI` (0 candles, 0 PBP, both markets INVALID).

---

# 9. TESTS

Create:

```text
ROLLER/tests/test_conditional_backtest.py
```

Minimum:

**Capability / fail-closed**

* L2 → DATA_REQUIRED, no rows
* tick → DATA_REQUIRED, no rows
* PBP↔candle PIT capability request → OPERATION_REQUIRED, no rows
* inverted date / non-NBA league → fail closed before scan

**Synthetic bag (no warehouse required)**

Construct a tiny `ResearchContext` in memory (the bag still works without the loader) and a matching `ResearchPlan`:

* CROSS then REACH WIN
* CROSS then REACH LOSS
* AND of two entries
* HOLD_TO_SETTLEMENT attaches YES / NO / INVALID correctly
* NO_TERMINAL_RESULT does not invent a winner
* same-bar WIN and LOSS tie fails closed
* missing minute is not forward-filled
* unaligned period request is exclusion, not zero-as-success

**Live NBA warehouse**

* 2025-10-10 Q2 CROSS 63 / REACH 87 / REACH 41 runs
* identity only via GameMarketLink
* BOS_TOR settlements remain YES / NO
* deterministic rerun (byte/structural)
* no CSV / FIRST80 / `official_settlement` import

**Isolation**

* `execute.py` / `compiler.py` / `load_dataset` do not import the new module
* `test_load_dataset_still_csv` stays green
* Phase 0–11 warehouse suite stays green

Do not delete failing tests to get a green gate.

---

# 10. REPORT

Create:

```text
research/warehouse_refactor/PHASE_12_CONDITIONAL_BACKTEST.md
```

Include:

* pipeline diagram
* which detectors were called (not copied)
* period/clock interpretation
* measured 2025-10-10 result (N, row counts, any exclusions)
* BOS_TOR row facts if that market qualified
* ZERO_RESULTS vs DATA_REQUIRED vs OPERATION_REQUIRED examples
* confirmation that Confirm & Run is still CSV
* confirmation that `pbp_pit_aligned_to_candles` is still false

Then STOP. Do not start Phase 13.

---

# 11. DOCS / GATE

After tests and report pass, update:

```text
research/warehouse_refactor/PLAN.md
.cursor/rules/14-warehouse-refactor.mdc
AGENTS.md
ROLLER/roller/warehouse/__init__.py
```

Set:

```text
next phase = 13
```

Do not edit `PHASE_12_CURSOR_PROMPT.md` except for typo fixes if you created notes elsewhere. Do not edit the Phase 9–11 implementation-plan file.

---

# 12. VALIDATION COMMAND

```text
pytest \
  tests/test_warehouse_contract.py \
  tests/test_warehouse_entities.py \
  tests/test_warehouse_identity.py \
  tests/test_warehouse_market_link.py \
  tests/test_warehouse_observations.py \
  tests/test_warehouse_pbp.py \
  tests/test_warehouse_settlement.py \
  tests/test_warehouse_orderbook.py \
  tests/test_warehouse_layout.py \
  tests/test_warehouse_catalog.py \
  tests/test_research_context.py \
  tests/test_research_compiler.py \
  tests/test_conditional_backtest.py
```

---

# 13. HARD STOPS

Stop and report if any of the following occurs:

```text
Phase 0–11 semantic change required
identity cannot be resolved without ticker parsing
settlement requires score / price / PBP inference
1-minute candle must be upgraded to tick / L2
available_at cannot remain the observation PIT field
PBP↔candle PIT alignment must be persisted to make Q2 work
AND timing must be guessed
same-minute WIN/LOSS tie must be arbitrarily broken
CSV becomes a hidden dependency of the new engine
Confirm & Run is modified
FIRST80 / T40 / W9 becomes an engine primitive
ZERO_RESULTS is used for missing data
detector inequalities are rewritten instead of called
NCAAB / MLB work is required to make NBA run
```

If a hard stop occurs, preserve the frozen warehouse and planning layer. Report the exact reason. Do not infer around the boundary.

---

# 14. FINAL RESPONSE SHAPE

Return exactly:

```text
PHASE 12: COMPLETE / BLOCKED

Tests:
  Phase 0–11 baseline: ...
  Phase 12: ...
  Total: ...
  Failures: ...

Report:
  research/warehouse_refactor/PHASE_12_CONDITIONAL_BACKTEST.md

Key measured facts:
  ...

Example (2025-10-10 Q2 CROSS 63 / REACH 87 / REACH 41):
  Catalog: ...
  Context: ...
  Plan hash: ...
  Population N: ...
  Rows: ...
  Backtest executed: YES

Capability:
  DATA_REQUIRED: ...
  OPERATION_REQUIRED: ...
  ZERO_RESULTS: ...

Validation:
  Confirm & Run remains CSV: PASS/FAIL
  Phase 0–11 semantics preserved: PASS/FAIL
  Detectors called from operations.py: PASS/FAIL
  pbp_pit_aligned_to_candles still false: PASS/FAIL

Then stop.
```
