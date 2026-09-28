# ROLLER Terminal — API Surface Draft

**Status:** Phase 0 contract only — **no server implemented**  
**Not** `apps/research-api` (MLB research-engine).

```text
ROLLER Terminal API
  → Research Objects + PIT explorer
  ≠ FIRST80 strategy API
  ≠ live execution
```

---

## Design principles

1. Permanent body format = `research_spec_v0` (see schema).
2. Natural language endpoints return **spec + unresolved[]**, never silent math.
3. Explorer answers **What exists?** via ROLLER `as_of`.
4. Portfolio endpoints are Phase 7 consumers.
5. Freeze trilogy is first-class: saved / frozen / locked_population.

---

## Universes & definitions

### `GET /universes`

Returns configured universes (v0: `BBALL1` only).

### `GET /vocabulary?version=vocab_v0`

Returns vocabulary registry JSON.

### `GET /definitions`

Returns authority matrix summary + `definition_versions` catalog + non-equivalence list  
(`SURVIVE ≠ TERMINAL_YES`, `MEASUREMENT ≠ EDGE`, …).

---

## Language → spec (compiler; Phase 3 runtime ABSENT)

### `POST /query/compile`

Request:

```json
{
  "universe": "BBALL1",
  "language": "Show me Q3 first 80s that survived 40",
  "vocabulary_version": "vocab_v0"
}
```

Response:

```json
{
  "status": "COMPILED" | "UNRESOLVED" | "INVALID",
  "research_spec": { },
  "unresolved": [
    {
      "term": "favorite",
      "concept": "FAVORITE",
      "clarification_options": []
    }
  ],
  "interpretation_preview": { }
}
```

**Must not** invent thresholds for `BIG_MOVE` / `LATE_GAME` / `FAVORITE`.

### `POST /query/validate`

Validates `research_spec` against schema + run-gate (unresolved parameters).

---

## Explorer (“What exists?”)

### `POST /explorer/query`

```json
{
  "universe": "BBALL1",
  "as_of": "2026-02-01T00:00:00Z",
  "information_mode": "POINT_IN_TIME",
  "research_spec": { }
}
```

`information_mode`: `POINT_IN_TIME` | `FULL_HISTORY` | `FROZEN_ARTIFACT`

Binds to `Roller.as_of` / `dataset` / observation assembly — not warehouse backtest EV.

### `GET /objects/{id}`

Object Inspector payload: I(t)/O_t, state, path (if bound), terminal, measurements,  
NOT_CONSTRUCTIBLE statuses, caveats.

---

## Research objects & jobs

### `POST /research-objects`

Create/run an empirical Research Object from a validated `research_spec`.  
Async for heavy runs → job id.

### `POST /batches`

Parameter grid → N research_specs (matrix is a **view**; each cell has full spec).

### `GET /jobs/{id}`

```json
{ "status": "QUEUED|RUNNING|COMPLETED|FAILED", "progress": { "done": 29, "total": 36 } }
```

---

## Persistence (freeze trilogy)

### `POST /saved-research`

Mutable named spec.

### `POST /frozen-research`

Immutable: spec + dataset_versions + definition_versions + result_snapshot + cutoff + hash.

### `POST /populations/lock`

Lock empirical population → `population_hash` (e.g. FIRST80 NBA N=1230 freeze).

### `GET /saved-research` / `GET /frozen-research/{id}`

Library listing / fetch.

---

## Portfolio (Phase 7 — stub allowed)

### `POST /portfolio/simulate`

Requires:

- frozen or validated research_object_id  
- explicit economic + portfolio `definition_versions`  
- always returns caveats: `CANDLE PATH ≠ FILL`

Must not imply FILTER→BACKTEST→PROFIT as the core product.

---

## Non-goals

| Endpoint smell | Rejection |
|----------------|-----------|
| `/strategies/first80/run` as sole product surface | Wrong architecture |
| `/edge/score` | EDGE ABSENT |
| Silent compile of “big move” | UNRESOLVED required |
| Proxying MLB `research-api` | Wrong system |
