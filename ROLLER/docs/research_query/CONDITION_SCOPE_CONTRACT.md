# Condition Scope Contract

ROLLER research-query v1. Prevents **scope coercion** the same way the generic
engine prevented **template coercion**.

```text
GAME_FILTER
    ≠
MARKET_EVENT
    ≠
MODEL_STATE
    ≠
POST_ENTRY_PATH
    ≠
TERMINAL
```

AND on ticker identity is valid only when every conjunct shares the same
research subject. Mixing scopes is not an empty population.

---

## Required fields (future conditions)

Every condition that is not a v1 candle touch or path step must declare:

| Field | Meaning |
|---|---|
| `condition_id` | Stable id |
| `scope` | Where the predicate lives |
| `evaluation_time` | When the predicate is evaluated |
| `as_of_time` | Latest information the predicate may use |
| `subject_id` | Game / team / ticker / player |
| `join_key` | How it attaches to the research row |
| `predicate` | Approved, typed comparison |

v1 candle entry/path/terminal conditions have implicit fields (below). They are
not silently rewritten into another scope.

---

## Scopes

### Implemented in v1 (executable)

| Scope | Subject | Evaluation | AND |
|---|---|---|---|
| `UNIVERSE` | sport / league / season / market | compile time | N/A |
| `MARKET_TICKER` / `ENTRY_EVENT` | one Kalshi contract | game-level nth tradable close-cross, then PBP snap filter | ticker-set intersection |
| `POST_ENTRY_PATH` | same ticker, strictly later candles | after entry timestamp | sequential state machine, not AND |
| `TERMINAL` | same ticker | Kalshi settlement only | measurement filter, not entry rewrite |

v1 AND:

```text
A AND B == B AND A
on ticker identity
```

Display funnel order is UX only. Math is order-invariant.

Period and clock are **filters on an ENTRY_EVENT**, not a separate GAME scope
and not a new ordinal universe inside a quarter.

### Reserved — undefined (compiler → OPERATION_REQUIRED)

These names may appear in UI drafts or future AST slots. They have **no
approved definition** in v1. The compiler must return `OPERATION_REQUIRED`,
not `n=0`, not READY, not a Kalshi substitute.

| Scope | Examples that must not execute |
|---|---|
| `GAME` | home 80 AND away 60 as one game event |
| `GAME_PREGAME` | team win% at tip, spread, rest |
| `TEAM_GAME` | one side of the game, not the ticker |
| `PLAYER_GAME` | box / player filters |
| `POSSESSION` | possession-level basketball state |
| `STATE` | generic “game state” without a join contract |
| `MARKET_CANDLE` model fields | XIB/MCD/probability columns on a candle |

Reserved draft families (non-exhaustive): `xib`, `mcd`, `team_win_pct`,
`home`, `away`, `pregame`, `player`, `possession`, `state`.

`state_conditions` is a **future AST slot**. Increment 1 does not execute it.
The five-screen UI (Quick Start / Entry / Exit / Confirm / Results) is not
renamed.

---

## XIB / MCD as-of contract (document only — do not implement)

When Terminal Efficiency is later attached, ROLLER may only **filter frozen
predictions**. It must never train XIB, recalibrate MCD, or regenerate a
prediction during a query.

Join:

```text
CANDLE market_timestamp
    ↓
latest model-valid state
    feature_as_of_timestamp <= market_timestamp
    ↓
prediction_timestamp <= market_timestamp
    ↓
XIB / MCD predicate
```

Forbidden:

- nearest prediction **after** the candle
- possession that completed after the candle
- inventing clock or state from candle index
- dropping L2/tick and still saying READY

Every joined row must preserve:

```text
market_timestamp
state_as_of_timestamp
feature_as_of_timestamp
prediction_timestamp
model_version
dataset_version
alignment_status
```

Missing as-of alignment is `UNALIGNED` / `DATA_REQUIRED`, not a silent nearest-neighbor fill.

---

## Status rule (unchanged)

| Situation | Status |
|---|---|
| Defined + data present | READY |
| Defined + optional dim omitted after ack | READY_WITH_LIMITATIONS |
| Defined + warehouse missing | DATA_REQUIRED |
| Scope or op has no approved definition | OPERATION_REQUIRED |

```text
ZERO RESULTS ≠ UNSUPPORTED
MISSING DATA ≠ ZERO
UNDEFINED OPERATION ≠ EMPTY POPULATION
CANDLE ≠ FILL
```
