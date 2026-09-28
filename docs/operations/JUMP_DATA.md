# Jump Canonical Data Plane

Jump queries the Momento research stack. Owners keep the data.
Systimo registers the tunnels.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
Austin 604 ≠ Choosin 936
WRITE / CONTROL = DENY
```

```text
browser :5179 ?app=jump#/nba/data
  → ROLLER research API :8791
  → /jump/data/sources|query|context|lineage|datasets|export
```

Package: `ROLLER/roller/jump/data/`.
Contract: `research/jump/JUMP_DATA_CONTRACT.md`.
Lineage: `research/jump/JUMP_LINEAGE_MODEL.md`.
Tunnels: `research/jump/JUMP_SYSTIMO_CONNECTIONS.md`.

## Surfaces

| Piece | Path |
|---|---|
| Explorer | `frontend/roller-terminal/src/jump/data/` `#/{sport}/data` |
| API | `/jump/data/*` on `:8791` |
| Registry | Systimo CSV + `/systimo/query` `path_back` |

## Operator flow

1. Open Jump Drive (`?app=jump`).
2. DATA / RESEARCH.
3. Enter `trade_id` (default FIRST80 `f84fd059fc0e1429`) and optional `as_of`.
4. Inspect Austin / Choosin / Ballhog / TK Ultra / ROLLER / Vital.
5. SHOW SOURCE for lineage.
6. Query upstream via the capability router.
7. EXPORT Austin 604 only when explicitly requested.

Missing siblings are `UNAVAILABLE`. They do not zero other systems.

## Do not

- Copy Austin / Choosin / ROLLER into a Jump database.
- Mix N=604 and N=936.
- Recalculate Austin alpha, Ballhog ρ*, TK residual, or Choosin prior.
- Write source datasets through this plane.
- Submit orders, start/stop `momento-live.service`, or set `VITAL_AWS_CONTROL`.
- Edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, W9, Phase 21.
