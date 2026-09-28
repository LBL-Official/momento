# STAX Phase 0 — repository recon

```
LIVE EXECUTION = FALSE
RESEARCH AUTOMATION ≠ EXECUTION
AGGREGATION_METHOD = NONE
CANDLE PATH ≠ ACTUAL FILL
DO NOT CHANGE LIVE FIRST01 / 80/81/83/89
DO NOT START W9
DO NOT MODIFY FROZEN RESEARCH-QUERY SEMANTICS
```

Audit and contract lock only. Phase 0 does not invent rolling timeframes
or a second research engine.

## 1. What STAX consumes

ROLLER is the measurement terminal (`frontend/roller-terminal` on :5179,
API `ROLLER/scripts/terminal_api.py` on :8791).

```
ONE ROLLER RUN  =  ONE RESEARCH OBJECT
MULTIPLE ROLLER RUNS  =  ONE STAX
```

STAX sits above ROLLER execution, parallel to SuperASI, not inside
`/research-query/*`.

| Path | Function | Full trades? |
|---|---|---|
| Frozen FIRST80 | `execute_research_object` | Full in memory; HTTP `rows` capped at 200 |
| Generic query | `execute_question` | `population.trades` is the full list |

STAX calls those functions directly (SuperASI import pattern). It must
not fan out through the single-worker `jobs.py` pool and must not
duplicate the compiler, candle scanner, path engine, or terminal engine.

Candidates: research-library saves, compiled questions/drafts, current
session envelopes. SuperASI packages are **not** STAX members.

## 2. Isolation (do not touch)

| Path | Status |
|---|---|
| `ROLLER/roller/research/first80.py` | Frozen. Do not modify. |
| `ROLLER/roller/research_query/` | Compiler / execute / hashes. Do not modify. |
| Frozen bindings in `research_executor.py` | Do not change. |
| `ROLLER/roller/superasi/` | Downstream consumer. Do not change behavior. |
| FIRST01 / Risk / Execution / W9 | Out of STAX scope. |

Allowed homes: `ROLLER/roller/stax/` (new), `research/stax/library/`
(new), `/stax/*` mounts on `terminal_api.py`, `frontend/roller-terminal/src/stax/`
(new), mode strip in existing ROLLER shell.

## 3. V1 locks

### Fixed timeframe

```
STAX UNIVERSE =
  sport
+ league_set
+ seasons
+ date_from
+ date_to
```

All immutable. Daily automation is:

```
DAILY RE-EXECUTION OF THE SAVED RESEARCH SPECIFICATION
```

not daily expansion of the observation period. No `TO CURRENT DATA`,
`LAST 365 DAYS`, or `TIMEFRAME MODE = ROLLING` in V1.

If the saved window is `2025-10-10 → 2026-06-13`, a midnight run on
2026-09-12 still queries that exact window.

### Persistent member identity

```
member_id  = STXM-0007   # durable
position   = 1           # order only
display_id = STX01-S01   # version-local presentation
```

Reorder changes `position`, not `member_id`. Compare keys on `member_id`.

## 4. Compatibility

Compare compiled `ResearchQuestion.universe` values, never UI labels.

- Same sport family + canonical league set + seasons + dates → pass
- NBA vs NCAAB → `STAX_CONSTRAINT_VIOLATION`
- NBA vs NBA+WNBA → reject
- Different seasons or compiled date windows → reject
- Do not expand a narrower window to match a wider one
- Do not drop a member to make the stack valid
- Markets / observation basis are per-strategy, not stack identity

## 5. Versioning

```
DEFINITION HASH UNCHANGED + DATASET FINGERPRINT CHANGED = PATCH
DEFINITION HASH CHANGED = MINOR
STAX SCHEMA INCOMPATIBLE = MAJOR
```

`aggregation_method = NONE`. No STAX EV. No combined independent N.

## 6. Automation

No existing ROLLER research scheduler. STAX introduces the first one
(stdlib tick + optional in-process loop). Research re-execution only.
`LIVE EXECUTION = FALSE`.

## 7. SuperASI boundary

V1 exposes `GET /stax/:id/export` only. No SuperASI stack import,
decomposition, ranking, or trading.
