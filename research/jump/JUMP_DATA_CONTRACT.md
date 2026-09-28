# Jump data contract

```text
LIVE EXECUTION = FALSE
CACHE ≠ SOURCE OF TRUTH
Austin 604 ≠ Choosin 936
JUMP CONSUMES. OWNERS KEEP THE DATA.
WRITE / CONTROL = DENY
```

Jump is the operating consumer. It does not own Austin, Choosin Texas,
ROLLER warehouses, Ballhog, TK Ultra, or Vital.

## Envelope

Every `/jump/data/query` response includes:

| Field | Meaning |
|---|---|
| `schema` | `jump.data.v0` |
| `query_id` | this request |
| `source_system` | owner of the result |
| `source_resource` | registered interface |
| `as_of` | request as_of, if any |
| `data_mode` | HISTORICAL_QUERY / STATIC / POINTER / OBSERVE |
| `result` | source payload |
| `provenance` | owner, adapter, permission, `copy: false` |
| `lineage_id` | present when requested |
| `warnings` | UNAVAILABLE details |

Anonymous JSON blobs are not a data-plane response.

## Column provenance

Composite context keeps namespaced fields:

```text
austin.conditional_ev_cents
choosin.population_survival
ballhog.rho_star
tk_ultra.gross_route_edge
```

Do not flatten these into `ev` / `risk` / `price`.

## Universes

Displayed together. Never mixed as one population.

| Source | Universe | N |
|---|---|---|
| Austin | `choosin_nba_2q3q_604` | 604 |
| Choosin Texas | `derived_four_936` | 936 |

Choosin is STATIC. Austin is `query_at(persist=False)`.

## Dataset handles

Normal responses return handles and filtered subsets, not whole
warehouses. `EXPORT DATASET` is explicit. ROLLER large exports are
manifest + partition pointers. Jump does not become the owner.

## PIT

When `as_of` is set and the source exposes `source_timestamp`,
`source_timestamp <= as_of` is required. Future leakage is
`PIT_REJECTED` / `UNAVAILABLE`. Choosin remains labeled STATIC.
