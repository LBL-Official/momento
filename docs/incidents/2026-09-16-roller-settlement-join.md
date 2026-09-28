# ROLLER Settlement Join Incident

Dated: 2026-09-16.

Research-correctness only. No Kalshi API. No ingest. No FIRST80.
No golden rewrite. Dated job `2f99745805d0462f8794f8e8b7fb823c` was
**not** re-executed.

Source inventory:
[`research/mlb_validation/PHASE_1_SETTLEMENT_SOURCE.md`](../../research/mlb_validation/PHASE_1_SETTLEMENT_SOURCE.md)

NBA warehouse incident (Q2∨Q3 / TE 6–20 / `WIN=0`):
[`ROLLER/tests/test_warehouse_incident_q2q3_te.py`](../../ROLLER/tests/test_warehouse_incident_q2q3_te.py)

---

## Tracker

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

RESEARCHCONTEXT JOIN
        MLB question → joins all 554 (435 YES / 119 NO)
        NBA question → loads KXNBAGAME only (0 of 554)

HOLD_TO_SETTLEMENT
        reads settlement.result as settlement_status
        YES/NO do not rewrite row class to WIN/LOSS
        results book HELD+YES → W only when win_hold
        MISSING → unresolved

NO API
NO INGEST
NO FIRST80
NO GOLDEN REWRITE
DATED JOB NOT RERUN
```

---

## What the inventory established

On today's disk, every golden ticker has a local binary Kalshi result:

| Settlement state | Count |
| --- | ---: |
| YES | 435 |
| NO | 119 |
| MISSING | 0 |
| INVALID | 0 |
| **Total** | **554** |

Provenance of that column: `kalshi_metadata` landing copied
`2026-09-13T12:41:10Z`, pipeline `4.0.0-C`. The same 435 / 119 is on
the MLB Phase 8 warehouse settlement parquet that ResearchContext reads
(`desk_sport=MLB`). Data-Real still covers only **84 / 554** (June 18–30).
Suite `metadata.parquet` is empty. `games.csv` box-score fields are empty.

The frozen dated job still records **65 YES / 19 NO / 470 MISSING**.
Those are two measurements. They must not be silently reconciled.

This does **not** mean the 2025-03-18 → 2026-09-01 research run had 554
settled tickers. That run is a different population.

---

## Next diagnostic (completed)

Question:

```text
554 settlement records now exist
             ↓
Does the canonical ResearchContext
             ↓
join the correct settlement to the
554 relevant market observations?
             ↓
Does HOLD_TO_SETTLEMENT
             ↓
read settlement.result
             ↓
YES → WIN
NO  → LOSS
MISSING → unresolved
```

And: how many of the **446** `HOLD_TO_SETTLEMENT` rows intersect the
**554**-record inventory?

### 446 ∩ 554 = 0

The 446 `HELD_TO_SETTLEMENT` count is from the NBA warehouse incident
(population 1607, LOSS 1161, WIN 0, dates 2025-03-18 → 2026-09-01).
NBA warehouse settlements are exclusively `KXNBAGAME` (2724 rows).

The 554 golden tickers are exclusively `KXMLBGAME`.

```text
554 ∩ NBA warehouse settlements = 0
554 ∩ MLB warehouse settlements = 554
```

A saved ticker list of the original 446 rows is not required for this
count. The two sets cannot intersect on ticker prefix / sport.

Therefore `WIN = 0` on that NBA result **cannot** be explained by
presence or absence of today's 554 MLB landing records. Those 554
records were never in that ResearchContext.

### ResearchContext join (code, not a job re-run)

`get_research_context` is sport-scoped
([`ROLLER/roller/warehouse/desk.py`](../../ROLLER/roller/warehouse/desk.py)
`desk_sport`,
[`query_context.py`](../../ROLLER/roller/warehouse/query_context.py)).
It loads
`data/{sport}/2025_2026/derived/warehouse/settlements/settlements.parquet`
and keeps `ticker ∈ GameMarketLink`.
[`run_plan`](../../ROLLER/roller/warehouse/conditional_backtest.py)
attaches `settle_index.get(ticker)`.

| Question sport | Parquet | 554 joined |
| --- | --- | ---: |
| MLB | MLB settlements (8920) | **554** (435 YES / 119 NO / 0 MISSING / 0 INVALID) |
| NBA (incident) | NBA settlements (2724) | **0** |

Landing CSV vs MLB warehouse parquet on the 554: **0 disagreements**.

### HOLD_TO_SETTLEMENT does not become WIN on the row

[`_classify_hold`](../../ROLLER/roller/warehouse/conditional_backtest.py):

```text
settlement is None / MISSING → MISSING_SETTLEMENT
INVALID                      → INVALID_SETTLEMENT
YES or NO                    → HELD_TO_SETTLEMENT + settlement_status
```

Row class stays `HELD_TO_SETTLEMENT`. The results contract
([`frontend_contract._settlement_books`](../../ROLLER/roller/warehouse/frontend_contract.py))
books `HELD + YES → terminal_win → W` only when `win_hold` is true.
`HELD + NO → L`. Missing stays unresolved.

So: the join **does** attach `settlement.result`. The engine **does not**
rewrite hold rows to `WIN`. Displayed `W` is a later booking step.

If the NBA incident booked `W` only from `classification == WIN`, then
`HELD_TO_SETTLEMENT = 446 / WIN = 0` is a **booking** defect on that
path, not a missing-554-MLB-settlement defect.

---

## What this is not

- Not a completed historical PIT settlement backfill.
- Not a re-run of the dated MLB job on today's landing.
- Not a claim that all 446 held NBA observations should become wins.
- Not FIRST80. Not an ingest. Not a golden rewrite.

---

## Dated job hold-like rows (separate object)

On the frozen MLB job, rows with empty `exit_outcome`: **336** (not 446).
All 336 have `terminal_yes=None` at job time. Today's landing would
classify those 336 as **335 YES / 1 NO**. That would be a new
information set. It was not attached and is not the dated result.
