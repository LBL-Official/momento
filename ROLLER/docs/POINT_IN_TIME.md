# Point-in-time contract

ROLLER's public surface is an information set:

```text
I(t) = { x | available_at(x) < t }
```

## Constitutional rule (locked)

```text
For every public point-in-time query at cutoff t:

    visible(row, t)  iff  row.available_at < t

This applies independently of event_time.

A row may have event_time < t and still be invisible if available_at >= t.
A row with available_at == t is invisible.

No V2 implementation, merge_asof, state engine, observation assembler,
or convenience API may weaken this.
```

V2 draft wording that used `available_at <= as_of` is informal and rejected.

The warehouse records what files exist. ROLLER records when each observation could have been known.

## Three timestamps

Every meaningful observation carries:

| Field | Meaning |
|-------|---------|
| `event_timestamp` | When the event happened |
| `available_at` | When a researcher could theoretically know it. **as_of uses only this field.** |
| `ingested_at` | When ROLLER processed the row |

as_of never filters on `ingested_at`.

## Availability quality

`scheduled_start` is not automatically `available_at`.

Keep `identity_available_at` separate from `scheduled_start`.

If the true schedule publication time is observed, use it and label `availability_quality=OBSERVED`.

Otherwise:

```text
identity_available_at = scheduled_start   # or UTC start of game_date if start is missing
availability_quality  = CONSERVATIVE_PROXY
```

Never pretend the schedule became known at tipoff. V1 warehouse game catalogs do not carry a schedule-publication timestamp, so game identity rows are conservative proxies.

PBP wall clocks (`timeActual`, `wallclock`) are `OBSERVED` when present. Missing wall time is `CLOCK_ONLY` + `CONSERVATIVE_PROXY`. ROLLER never invents a wall clock from tip + game clock.

Candles: `available_at` is the candle **close**. The minute is not knowable before it ends.

## Half-open cutoff

```text
available_at < cutoff
```

| Call | Cutoff |
|------|--------|
| `as_of("2025-12-19")` | `2025-12-19T00:00:00Z` |
| `as_of("2025-12-19", end_of_day=True)` | `2025-12-20T00:00:00Z` |
| `as_of("2025-12-19T18:30:00Z")` | that instant, literal UTC |

A row with `available_at == cutoff` is excluded.

All stored timestamps are UTC. Naive vs aware comparison raises `TimestampError`.

## Public vs admin API

| API | Modules | Filter |
|-----|---------|--------|
| Public | `Roller.dataset`, `get_team_state`, `game_state`, `observation`, `as_of` | Requires `as_of` or explicit `full_history=True` |
| Labels | `Roller.labels` | Explicit future-information API; not `I(t)` |
| Response | `Roller.response` | Forward `Y_{t→t+h}` only; `contains_future_information=true` |
| Baseline | `Roller.baseline` | Eligible iff `observation_time_i < t` and `response_available_at_i < t` |
| Residual | `Roller.residual` | Undefined when support is insufficient (not 0) |
| Fundamental | `Roller.fundamental` | Prior-only empirical `F_t`; cutoff from `observation_id` |
| Greeks | `Roller.greeks` | Default / `schema_version="4.0.0-B"` is V4B. `schema_version="4.0.0-C"` is a lossless taxonomy overlay. Not part of `O_t`. |
| Stub | `Roller.research` | Train/OOS still unimplemented; use `db.fundamental()` / `db.greeks()` |
| Admin | `roller.admin`, ingest, canonicalize, feature rebuild | Unrestricted, scripts only |

ROLLER cannot stop someone from opening a CSV by hand. The official API never returns unfiltered data unless `full_history` is explicit.

`db.as_of(t)` returns `InformationSet` — a handle on `I(t)`. Downstream features are functions of `I(t)`, never `I(t+Δt)`.
