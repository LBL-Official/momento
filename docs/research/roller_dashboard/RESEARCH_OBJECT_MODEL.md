# ROLLER Terminal — Research Object Model

**Status:** Phase 0 contract (structural only — not a mathematical engine) — **LOCKED with schema**  
**Date:** 2026-09-07  
**Companion:** `research_spec.schema.json`, `RESEARCH_SPEC.md`, `AUTHORITY_MATRIX.md`,  
`ROLLER_DASHBOARD_CODEBASE_MAP.md`, `ROLLER_DASHBOARD_PHASE0_IMPLEMENTATION_PROMPT.md`

```text
THIS DOCUMENT DEFINES STRUCTURE
IT DOES NOT DEFINE NEW MATH
FIRST80 IS ONE RESEARCH OBJECT — NOT THE SYSTEM BOUNDARY
```

---

## 1. What ROLLER is

```text
ROLLER
  = self-maintaining rolling empirical database
  + point-in-time information space I(t)
  + empirical research objects
```

```text
ROLLER TERMINAL
  = interface into that database
  ≠ FIRST80 strategy dashboard
  ≠ consumer trading UI
  ≠ live execution
```

Architecture:

```text
                    ROLLER
          SELF-MAINTAINING EMPIRICAL DATABASE
                           │
                           ▼
                VERSIONED INFORMATION SPACE
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
        OBSERVATION                   RESEARCH
         EXPLORER                      ENGINE
             │                           │
             ▼                           ▼
       "What exists?"            "What happens after?"
             │                           │
             └─────────────┬─────────────┘
                           ▼
                    RESEARCH OBJECT
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
         PATH            TERMINAL       PORTFOLIO
       PHENOMENA         PHENOMENA      SIMULATION
```

Portfolio is a **consumer** of research objects, not the core engine.

---

## 2. Hierarchy (not FIRST80-centric)

```text
UNIVERSE
    ↓
DATASET
    ↓
POPULATION
    ↓
RESEARCH OBJECT
    ↓
MEASUREMENT
    ↓
RESULT
```

### Universe: BBALL1 Research (first)

| Field | Value |
|-------|-------|
| ID | `BBALL1` |
| Sports | NBA, WNBA, NCAAB |
| Default structural population | NBA: Q2∪Q3; WNBA: Q2∪Q3; NCAAB P5: H1_2∪H2_1 (`ASKED_SIX`) |
| Role | Organizational boundary for data + research objects |

Future universes (`MLB1`, etc.) must fit the same hierarchy without redesign.

**Wrong:**

```text
BBALL1 → FIRST80 dashboard
```

**Right:**

```text
BBALL1
├── Data Explorer          ("What exists?")
├── Research Objects       (FIRST80, FIRST75, FirstReach(q), custom, saved)
├── Path Studies
├── Terminal Studies
├── Conditional Phenomena
├── Backtests
├── Batch Lab
└── Portfolio              (last in chain)
```

---

## 3. Research Object (universal contract)

A **Research Object** is an empirical phenomenon definition — not a strategy, not a trade plan.

```text
RESEARCH OBJECT
  = POPULATION
  + ENTRY / ANCHOR
  + INFORMATION SET
  + STATE CONDITIONS
  + PATH MEASUREMENT
  + TERMINAL MEASUREMENT
  + SAMPLE BINDING
  + DEFINITION VERSIONS
```

### Canonical fields

| Field | Meaning |
|-------|---------|
| `identity` | Stable ID / name / tags |
| `universe` | e.g. `BBALL1` |
| `population_binding` | How members are selected (or locked population hash) |
| `anchor` | Entry / event that starts the object (price touch, move, observation time, …) |
| `information_regime` | e.g. `CANDLE_1M`, `POINT_IN_TIME`, `FROZEN_ARTIFACT` |
| `information_set` | e.g. `I(t_anchor)`, `O_t` |
| `state_filters` | AND/OR/NOT tree over game/market state |
| `path_conditions` | Forward path predicates / measurements |
| `terminal_conditions` | Settlement / terminal predicates |
| `measurement_requests` | Which metrics to compute (F_t, Greeks, EV bindings, …) |
| `sample_binding` | Train / validation / forward / as_of / data_cutoff |
| `definition_versions` | Explicit engine bindings |
| `dataset_versions` | Data identity at run/freeze time |
| `execution_interpretation` | e.g. `OBSERVABLE_PATH_ONLY` |
| `caveats` | Required disclosures (candle ≠ fill, etc.) |
| `economic_layer` | Optional; absent until Phase 7 bindings |
| `portfolio_layer` | Optional; consumer only |

### Acceptance criterion

> The same contract can represent FIRST80, a state-conditioned observation study, and a terminal-only study **without** inventing a new query format for each.

---

## 4. Worked examples (same contract)

### 4.1 FIRST80_Q3 (deeply implemented phenomenon)

```text
Object: FIRST80_Q3

Population:     NBA games (or BBALL1 asked-six subset)
Anchor:         FIRST_PRICE_TOUCH @ yes_bid_close ≥ 80¢ after seen_below
Information:    I(t_anchor)
State:          entry_slice = Q3
Path:           T60 / T50 / T40, MAE, time-to-barrier, subsequent min
Terminal:       kalshi_yes_settled
Binding:        warehouse_frozen_v1  OR  roller_4.1.0-R  (must be explicit)
Execution:      OBSERVABLE_PATH_ONLY
```

### 4.2 LARGE_DOWN_MOVE_Q4 (different phenomenon, same shape)

```text
Object: LARGE_DOWN_MOVE_Q4

Population:     NBA observations
Anchor:         observed price move exceeds threshold X (must be explicit; no silent "big")
Information:    O_t
State:          period = Q4
Path:           forward return distribution, reversal, time-to-recovery
Terminal:       optional Kalshi settlement
Binding:        roller observation / measurement versions
Execution:      OBSERVABLE_PATH_ONLY
```

### 4.3 Terminal-only study

```text
Object: FIRST80_TERMINAL_CALIBRATION

Population:     locked FIRST80 population hash
Anchor:         FIRST80
Path:           none required
Terminal:       P(W) vs 80¢; Wilson intervals
Binding:        alpha_decomposition / audit settlement rules
```

### 4.4 Greek / fundamental study

```text
Object: BASIS_EXTREME_AT_OBSERVATION

Population:     observations with constructible basis
Anchor:         observation timestamp
Information:    O_t + query-time Greeks (not inside O_t)
Measurements:   market_fundamental_basis, residual; NOT_CONSTRUCTIBLE stay null
Path/Terminal:  optional
```

FIRST80, FIRST75, FirstReach(q), ASKED_SIX slices, nested barriers, M1 responses, Greek trajectories, and portfolios of selected objects are all **instances** of this contract.

---

## 5. Two terminal modes (same `research_spec`)

### Mode A — Research Terminal (language)

```text
USER LANGUAGE
    ↓
VOCABULARY (versioned)
    ↓
STRUCTURED RESEARCH SPEC / RESEARCH OBJECT
    ↓
SHOW INTERPRETATION (editable)
    ↓
UNRESOLVED TERMS → user must choose
    ↓
AUTHORITATIVE ENGINE
```

Natural language is a **compiler assistant**, not the permanent format and not the math authority.

Ambiguous phrases (`big move`, `late game`) → `UNRESOLVED` with choices. No silent thresholds.

### Mode B — Structured Research Builder

Visual editing of the same fields (AND/OR/NOT, anchors, path, terminal).  
Changing language-compiled conditions updates the builder; editing the builder updates the spec.

```text
ONE research_spec
TWO views
ZERO divergent interpretations
```

---

## 6. Persistence: three distinct concepts

| Concept | Mutability | Holds |
|---------|------------|--------|
| **Saved Research** | Mutable | Named work-in-progress object + spec |
| **Frozen Research** | Immutable | `spec` + `dataset_version` + `definition_versions` + `result_snapshot` + cutoff + hash |
| **Locked Empirical Population** | Immutable population set | Explicit `population_hash` (e.g. `FIRST80_NBA_20260904_v1`, N=1230) |

Freeze is stronger than “save.”  
Locked population prevents mysterious N/rate drift when the rolling DB grows.

Live rerun ≠ frozen historical result. Always label which.

---

## 7. Analytical chain (order matters)

```text
POPULATION
  → ANCHOR
  → CONDITIONAL STATE
  → PATH PHENOMENON
  → TERMINAL PHENOMENON
  → EMPIRICAL DISTRIBUTION
  → ECONOMIC ASSUMPTION
  → TRADE MODEL
  → PORTFOLIO
```

Do not collapse to `FILTER → BACKTEST → PROFIT`.

Batch Lab generates many Research Objects from a parameter grid; the matrix is a **view** over objects, not a separate truth.

---

## 8. Information modes (Data Explorer)

Every explorer session must choose:

| Mode | Meaning |
|------|---------|
| Point-in-time | `I(t)` / `as_of` — what could have been known |
| Full historical | Explicit `full_history=True` — not default for “as of” questions |
| Frozen artifact | Bound to locked population / frozen research ID |

UI must distinguish **point-in-time information** vs **forward realization**.

---

## 9. Object Inspector (conceptual)

Clicking a row opens the empirical object:

```text
I(t) / O_t at anchor
STATE at anchor
PATH after anchor
TERMINAL
MEASUREMENTS (F_t, Greeks, …)
NOT_CONSTRUCTIBLE displayed as such — never coerced to 0
Caveats: CANDLE PATH ≠ FILL
```

---

## 10. Non-goals of this contract

- No new FIRST80 scanner
- No new EV / fee / portfolio mathematics
- No TypeScript reimplementation of ROLLER math
- No implication that every Research Object is executable or has edge
- No silent mapping of vocabulary to mathematics

Bindings to authoritative engines live in the authority matrix and `definition_versions`.

---

## 11. Phase 0 alignment (complete)

| Artifact | Role |
|----------|------|
| This file | Structural Research Object contract |
| `research_spec.schema.json` | Machine-readable encoding |
| `samples/*.json` | FIRST80 + unresolved observation + fundamental/basis (one format) |
| `research_vocabulary_v0.json` | Language → concepts (no silent math) |
| `AUTHORITY_MATRIX.md` | definition_versions bindings |
| `ROLLER/roller/dashboard_adapter/` | Validation + hash + PIT import only |

`research_object.py` validates schema and hashes identity.  
It must not compute barriers, EV, or fills.

Acceptance: FIRST80, a state-conditioned observation study, and a terminal/measurement-only study share **one** query format.
