# PHASE 1 — MLB Settlement Source Inspection

Status: **COMPLETE** (inspect only). Settlement ingest was **not** started.

Inspected: 2026-09-16. No Kalshi API call. No FIRST80. No golden rewrite.
The dated Confirm & Run job was **read**, not re-executed.

Frozen artifact: `ROLLER/data/.cache/research_query/mlb-dated-2026-04-01-2026-09-08-job.json`
(`job_id` `2f99745805d0462f8794f8e8b7fb823c`). `population.trades` length **554**.

---

## Incident tracker (this slice)

```text
SETTLEMENT SOURCE INVENTORY
        PASS — local source exists for 554 golden tickers

HISTORICAL PIT SETTLEMENT
        NOT ESTABLISHED

DATED JOB SETTLEMENT
        65 YES / 19 NO / 470 MISSING

CURRENT LANDING INVENTORY
        435 YES / 119 NO / 0 MISSING

446 ∩ 554
        0
        (see docs/incidents/2026-09-16-roller-settlement-join.md)

NO API
NO INGEST
NO FIRST80
NO GOLDEN REWRITE
DATED JOB NOT RERUN
```

Those two settlement columns are **different measurements**. They must not
be silently reconciled.

```text
Today's disk
554 golden tickers
435 YES / 119 NO
        │
        └── landing copied 2026-09-13T12:41:10Z
            source_dataset = kalshi_metadata
            pipeline 4.0.0-C

Frozen dated job
65 YES / 19 NO / 470 MISSING
        │
        └── original job's point-in-time settlement availability
```

This inventory does **not** establish that the 2025-03-18 → 2026-09-01
research run had 554 settled tickers.

---

## PHASE 1 STATUS

| Gate | Status |
| --- | --- |
| 554 tickers locked from dated artifact | **PASS** (no entry re-run) |
| Local `kalshi_markets.result` join | **PASS** — 554 / 554 binary |
| Warehouse ResearchContext settlement parquet | **PASS** — same 554 / 554, 0 disagreement |
| Historical PIT settlement | **NOT ESTABLISHED** |
| Settlement ingest / attach | **NOT STARTED** |
| Complete-settlement gate (dated measurement) | **BLOCKED** |
| FIRST80 / box score / path WIN / API | **EXCLUDED** / not called |

```text
PHASE 1 SOURCE INSPECTION = COMPLETE
SETTLEMENT INGEST        = NOT STARTED
COMPLETE-SETTLEMENT GATE = BLOCKED for the dated job
                           (PIT not established; attach not authorized)
NEXT WAIT                = explicit approval to attach today's local
                           results as a *new* information set,
                           or to perform a read-only Kalshi historical
                           probe. Do not treat either as the dated job.
```

---

## 1. Available authoritative source(s)

Preferred authority remains Kalshi `result` on the **exact ticker**.

| Source | Exists | Has Kalshi `result` | Usable for the dated 470 | Notes |
| --- | --- | --- | --- | --- |
| `ROLLER/data/mlb/2025_2026/canonical/kalshi_markets.csv` | yes | yes | **now** 554/554 on disk; **not** dated-job PIT | `source_dataset=kalshi_metadata`, `pipeline_version=4.0.0-C`, `ingested_at=2026-09-13T12:41:10Z` |
| Phase 8 `…/mlb/…/warehouse/settlements/settlements.parquet` | yes | `settlement_status` | same 554/554; 0 disagreement with landing | This is what `get_research_context` reads when `desk_sport=MLB` |
| `warehouse_v0/settlements.parquet` | yes | same tree | same 554/554 | 8920 rows warehouse-wide (YES 4426 / NO 4434 / MISSING 40 / INVALID 20) |
| Foundation `landing/kalshi_market_settlement` | yes (8880 JSON) | yes | 554/554 overlap | Same 435 / 119 as landing CSV |
| `rq_index_v1.0.0` MLB last-trade / tradable `settlement.parquet` | yes | yes | 554/554 (`yes` 435 / `no` 119) | Index of current warehouse facts, not dated-job PIT |
| Data-Real `orderbook/date=*/metadata.parquet` | yes | June 18–30 only | **84 / 554** | Unchanged hole outside that slice |
| Suite `Data/MLB/2025-2026/orderbook` `metadata.parquet` | 0 files | no | no | Empty |
| `games.csv` box-score columns | present, empty | no | **forbidden** | `home_win` / `away_win` / finals = 0 nonempty |
| FIRST80 W / `research/mlb_first80_80_40_v1` | exists | n/a | **forbidden** | Not inspected as a source |
| Kalshi `GET /trade-api/v2/markets/{ticker}` and `…/historical/markets/{ticker}` | client exists | `result` documented | **not called** | `OPERATION_REQUIRED` later; adapter fails closed on `scalar` |

Warehouse `dataset_version` on this disk is
`fdb5a3eff62234848fbb3f291eb03c6e28cd6abf101f7c4fff349911f40e3db3`
(`generated_at` `2026-09-14T23:30:01Z`, pipeline `4.0.0-C`).
Phase 0 recorded `cb7cff4f…` / `2026-09-11`. That is a later warehouse
stamp, not a re-run of job `2f997458…`.

---

## 2. Exact coverage by ticker / event

Join: **exact `ticker`**. No complement fill. No event-level vote.

```text
554 golden tickers
        └── all KXMLBGAME
        └── 554 unique
        └── 0 scalar / NON_BINARY_RESULT in this N
        └── 0 YES-vs-NO conflicts
        └── 0 duplicate warehouse settlement rows
```

| Classification (today's local `result`) | Count |
| --- | ---: |
| YES | 435 |
| NO | 119 |
| MISSING | 0 |
| INVALID | 0 |
| **Total** | **554** |

`YES + NO + MISSING + INVALID = 554`.

Warehouse Phase 8 settlements for the same 554:

| `settlement_status` | Count |
| --- | ---: |
| YES | 435 |
| NO | 119 |
| MISSING | 0 |
| INVALID | 0 |

Landing CSV vs warehouse parquet: **0 disagreements**.

The four warehouse-wide scalar / `INVALID` tickers (20 `INVALID` in the
full 8920-row MLB settlement table) are **not** in this 554.

---

## 3. Coverage dates

Ticker game-day parsed from `KXMLBGAME-YYMONDD…` (not a settlement
result):

| Month | N | YES | NO |
| --- | ---: | ---: | ---: |
| 2026-04 | 180 | 140 | 40 |
| 2026-05 | 190 | 153 | 37 |
| 2026-06 | 184 | 142 | 42 |
| **Total** | **554** | **435** | **119** |

Game-day span of the 554: **2026-04-01 → 2026-06-30** (90 distinct days).

Data-Real metadata with nonempty `result`: **2026-06-18 → 2026-06-30**
only (84 of the 554).

---

## 4. Can the dated 470 be resolved from this slice?

**On today's disk: those tickers now have a local binary `result`.**
That is landing / warehouse / index availability **after** 2026-09-13
copy-in. It is **not** a reconstruction of what the dated job could see.

| Question | Answer |
| --- | --- |
| Can Data-Real metadata resolve the 470? | **No.** 84/554 only (June 18–30). |
| Can Suite metadata resolve them? | **No.** Zero `metadata.parquet`. |
| Can box scores resolve them? | **No.** Empty. Forbidden. |
| Can FIRST80 resolve them? | **No.** Excluded. |
| Can today's landing/warehouse resolve them as a *new* attach? | **Yes, locally** (0 MISSING / 0 INVALID). **Not authorized. Not PIT.** |
| Was Kalshi called? | **No.** |

---

## 5. Proposed immutable join key (document only)

```text
primary   = Kalshi ticker exactly as stored on the golden observation
audit     = internal_game_id, event_ticker, source path,
            ingested_at / pipeline_version, settlement_time
forbidden = complementary side, box score, path WIN, last print,
            FIRST80 W, expiration price
```

---

## 6. Duplicate / conflict handling (document only)

- One ticker → one settlement. Identical YES/YES: keep one.
- Conflicting YES vs NO on the same ticker → `INVALID` +
  `CONFLICTING_RESULTS`. Not majority. Not drop-to-missing.
- Complementary event tickers are independent lookups.

Observed on this 554: **0 duplicates, 0 conflicts**.

---

## 7. Expected remaining MISSING / INVALID under local-only attach

If a later authorized attach used **today's** landing / warehouse
(and still did not call Kalshi):

```text
YES 435 + NO 119 + MISSING 0 + INVALID 0 = 554
```

That attach was **not** performed. Doing it and labeling the output as
job `2f997458…` would destroy the dated measurement.

The frozen job remains:

```text
YES 65 + NO 19 + MISSING 470 + INVALID 0 = 554
```

Dated-job rows with no path exit (`exit_outcome` empty): **336**.
All 336 have `terminal_yes=None` on the job. Today's landing would
classify those 336 as **335 YES / 1 NO**. That is a different
information set. Do not promote it.

---

## ResearchContext join (read-only)

`get_research_context` loads
`data/{sport}/2025_2026/derived/warehouse/settlements/settlements.parquet`
and keeps rows whose `ticker` is in the sport's `GameMarketLink` set.
`run_plan` attaches `settle_index.get(ticker)`.

- MLB question → MLB parquet → **all 554 join** (435 YES / 119 NO).
- NBA question → NBA parquet (`KXNBAGAME` only) → **0 of 554**.

Engine classification on hold:

```text
settlement missing / None → MISSING_SETTLEMENT
INVALID                   → INVALID_SETTLEMENT
YES or NO                 → HELD_TO_SETTLEMENT + settlement_status
```

`HELD_TO_SETTLEMENT` is **not** rewritten to `WIN` / `LOSS` on the row.
`frontend_contract._settlement_books` books `HELD + YES → W` only when
`win_hold` is true. Missing stays unresolved.

---

## Protected / unchanged

No edits to FIRST80, live FIRST01 / 80/81/83/89, Risk, generic
research-query semantics, golden expected counts, frontend, Data-Real,
or warehouse writes.

---

## End-of-phase report

| Item | Value |
| --- | --- |
| PHASE 1 STATUS | **COMPLETE** (inspect only) |
| CURRENT LANDING / WAREHOUSE (554) | YES 435 / NO 119 / MISSING 0 / INVALID 0 |
| DATED JOB (554) | YES 65 / NO 19 / MISSING 470 / INVALID 0 |
| HISTORICAL PIT | **NOT ESTABLISHED** |
| DATA-REAL | 84 / 554 (June 18–30) |
| FILES WRITTEN | this report; incident `docs/incidents/2026-09-16-roller-settlement-join.md` |
| NEXT | approval required before any attach / API probe |
