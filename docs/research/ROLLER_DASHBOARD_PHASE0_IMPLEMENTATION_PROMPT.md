# ROLLER Terminal — Phase 0 Implementation Prompt

**Use this as a standalone Cursor task.**  
**Prerequisite:**  
- `docs/research/ROLLER_DASHBOARD_CODEBASE_MAP.md`  
- `docs/research/roller_dashboard/RESEARCH_OBJECT_MODEL.md`

**Forbidden:** React/Next UI, new EV formulas, new FIRST80 scanners, live trading changes, MLB W9, inventing L2, designing a “FIRST80 strategy dashboard.”

```text
PHASE 0 = AUTHORITY + CONTRACTS ONLY
NO DASHBOARD CHROME
NO PARALLEL MATH
FIRST80 = ONE RESEARCH OBJECT, NOT THE SYSTEM BOUNDARY
```

---

## Architectural decision (locked)

ROLLER is a **self-maintaining rolling empirical database**.  
The product is a **research terminal** into that database.

```text
UNIVERSE → DATASET → POPULATION → RESEARCH OBJECT → MEASUREMENT → RESULT
```

BBALL1 is the first **universe**, not the dashboard itself.  
FIRST80 is the first deeply implemented **research object** inside BBALL1 — not the conceptual architecture of the terminal.

```text
                    ROLLER
          SELF-MAINTAINING EMPIRICAL DATABASE
                           │
                VERSIONED INFORMATION SPACE
             ┌─────────────┴─────────────┐
        OBSERVATION                   RESEARCH
         EXPLORER                      ENGINE
       "What exists?"            "What happens after?"
                           │
                    RESEARCH OBJECT
             path / terminal / (later) portfolio
```

Portfolio is last in the analytical chain. Do not design Phase 0 around bankroll P&L.

---

## Mission

Protect existing ROLLER and warehouse mathematics from accidental reimplementation, and establish the **universal Research Object contract** that the terminal will compile into.

Phase 0 delivers:

1. **Authority matrix** (metric → function → definition_version)
2. **Reconciliation tests** (ROLLER FIRST80 vs warehouse frozen audits) — as one object binding, not the whole product
3. **Research specification schema** encoding the Research Object Model
4. **Vocabulary registry v0** (words → concepts → engines; no silent math)
5. **Adapter stubs** (import-only)
6. **API surface draft** (ROLLER terminal API ≠ MLB `research-api`)
7. **Research Object contract** (structural; already seeded in `RESEARCH_OBJECT_MODEL.md` — complete/align schema + stub)

Do not implement Phase 1 UI in this task.

---

## Absolute rules

1. Inspect code before writing. Prefer importing existing functions.
2. If two implementations disagree, **flag the conflict** — do not pick a winner silently.
3. Candle path ≠ fill. Survive ≠ won. Measurement ≠ edge.
4. No floating-point money math in new code; preserve integer E4 / existing fee helpers.
5. Do not modify live FIRST01 / Risk / Execution.
6. Do not start W9 historical engine work.
7. Do not rewrite warehouse parquet; write Phase 0 artifacts under `docs/research/roller_dashboard/` and optionally `ROLLER/roller/dashboard_adapter/` / `ROLLER/meta/dashboard/`.
8. Do not collapse architecture around FIRST80. Schema and vocabulary must also express non-FIRST80 objects (e.g. observation studies, terminal-only, Greek/basis queries).
9. Ambiguous language → `UNRESOLVED` with choices — never invent thresholds.

---

## Deliverables (checklist)

### A. Authority matrix

Create: `docs/research/roller_dashboard/AUTHORITY_MATRIX.md`

| Research concept | Authoritative path | Symbol | definition_version | Also-ran / conflict | Dashboard may call? |
|------------------|--------------------|--------|--------------------|---------------------|---------------------|

Must cover at minimum:

- PIT `as_of` / `observation` / `clock_snap`
- F_t / V4B / V4C / NOT_CONSTRUCTIBLE
- FIRST80 trigger, quality gate, game window, T40, Kalshi W
- Asked-six clock slices
- Nested barriers 60/50/40
- Gross path EV, fee estimate (`quadratic_fee_e6`)
- Train / val / OOS splits
- Portfolio sims (Q23 + dual-sport) — marked as **economic layer / Phase 7 consumer**
- Explicit **ABSENT — must not invent** rows for generic path DSL, HTTP API, vocabulary compiler runtime

### B. Reconciliation tests

FIRST80 identity reconciliation only (one research-object binding):

1. Warehouse frozen audit sample vs ROLLER `first80` where both exist
2. Compare trigger ts, ticker, T40, W
3. Mismatch → fail with conflict report (no auto-heal)
4. CI may skip with documented fixture/marker if warehouse absent

### C. Research specification schema

Create:

- `docs/research/roller_dashboard/research_spec.schema.json`
- `docs/research/roller_dashboard/RESEARCH_SPEC.md`

Schema **must encode** the Research Object Model:

```text
identity
universe
population_binding
anchor
information_regime
information_set
state_filters          # AND/OR/NOT tree
path_conditions
terminal_conditions
measurement_requests
sample_binding         # as_of, train/val/forward, data_cutoff
definition_versions
dataset_versions
execution_interpretation
caveats
economic_layer         # optional
portfolio_layer        # optional
```

Validate **at least three** sample specs:

1. FIRST80 Q3 path/terminal (warehouse or ROLLER binding explicit)
2. Large-move / observation study with unresolved threshold **rejected** until filled
3. Terminal-only or F_t/basis measurement study (no FIRST80 required)

Permanent format = schema. Natural language is not.

### D. Vocabulary registry v0

Create: `docs/research/roller_dashboard/research_vocabulary_v0.json`

Bind synonyms → concept → `definition_version` / engine.  
Include FIRST80-related concepts **and** non-FIRST80 (observation, basis, residual, period, clock, margin, ASKED_SIX, CANDLE_1M, OBSERVABLE_PATH_ONLY).

`SURVIVE` must_not_equate `TERMINAL_YES`.  
`big move` / `late game` / `favorite` → `unresolved_if_ambiguous: true`.

### E. Adapter stubs (import-only)

`ROLLER/roller/dashboard_adapter/` (preferred):

- `research_object.py` — types + schema validation + `research_object_id` hash (**no math**)
- Thin wrappers that only import `Roller` / documented bindings
- Config paths to frozen artifacts

Forbidden: reimplement `quality`, `scan`, EV, fees, portfolio; TypeScript math.

### F. API surface draft

Create: `docs/research/roller_dashboard/API_SURFACE_DRAFT.md`

Sketch (no full server required):

```text
GET  /universes
GET  /vocabulary
GET  /definitions
POST /query/compile          # language → research_spec + unresolved[]
POST /query/validate
POST /explorer/query         # "What exists?" via ROLLER PIT
GET  /objects/{id}           # Object Inspector payload
POST /research-objects       # create/run empirical object
POST /batches
GET  /jobs/{id}
POST /saved-research
POST /frozen-research
POST /populations/lock
POST /portfolio/simulate     # Phase 7 consumer; stub OK
```

State explicitly: **not** `apps/research-api` (MLB).

### G. Research Object contract alignment

Ensure `RESEARCH_OBJECT_MODEL.md` and `research_spec.schema.json` agree.

Document the freeze trilogy in the API/spec docs:

| Concept | Role |
|---------|------|
| Saved Research | Mutable named spec |
| Frozen Research | Immutable spec + data + definitions + result snapshot |
| Locked Empirical Population | Immutable population hash (e.g. FIRST80 N=1230 freeze) |

Acceptance for G:

> FIRST80, a state-conditioned observation study, and a terminal-only study share one query format.

---

## Acceptance criteria

Phase 0 is done when:

1. Authority matrix covers PIT + FIRST80 bindings + ABSENT rows; portfolio marked as later consumer.
2. Reconciliation test exists with pass/fail/skip documented.
3. Schema validates three distinct Research Object samples (not only FIRST80).
4. Vocabulary distinguishes SURVIVE vs TERMINAL_YES; ambiguous terms unresolved.
5. Adapter stubs contain no duplicated scan/EV/fee/portfolio math.
6. Research Object Model and schema are aligned; freeze trilogy named.
7. Docs state BBALL1 = universe, FIRST80 = one object.
8. **No React app created.**

---

## Later phases (do not implement here)

| Phase | Content |
|-------|---------|
| **1 — Terminal foundation** | Shell, BBALL1 universe, Research Terminal input, Data Explorer, `as_of`, Object Inspector, definitions — **“What exists?”** only; no new backtest math |
| **2 — Structured Research Objects** | Visual builder, AND/OR/NOT, anchors, path/terminal, spec preview |
| **3 — NL compiler** | Language → vocabulary → spec → unresolved → confirm |
| **4 — Empirical research engine** | Wire ROLLER + FIRST80/barrier/PIT/F_t/V4 bindings for path & terminal phenomena |
| **5 — Research library** | Save / version / freeze / compare / locked populations |
| **6 — Batch Lab** | Grids, jobs, matrices as views over Research Objects |
| **7 — Economic & portfolio** | Fee/EV bindings, chronological portfolio, caveats always visible |

**Do not run Phase 1 until Phase 0 (including Research Object contract) is accepted.**

---

## Central invariant

```text
USER LANGUAGE
     ↓
VOCABULARY (versioned)
     ↓
RESEARCH OBJECT / research_spec (schema)
     ↓
AUTHORITATIVE ENGINE (ROLLER and/or warehouse binding)
     ↓
RESULT + CAVEATS
```

```text
BUILD THE INTERFACE TO ROLLER, THE ROLLING EMPIRICAL DATABASE.
FIRST80 IS THE FIRST DEEP RESEARCH OBJECT IN BBALL1 —
NOT THE CONCEPTUAL BOUNDARY OF THE SYSTEM.
```

If a concept has no authoritative engine → **UNRESOLVED / NOT AVAILABLE** — never a silent approximation.
