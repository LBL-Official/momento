# Systimo — System Maintenance data tunnel

Registers and operates tunnels. Does not become the source.
Not Vital. Not Momento LS product UI. Not a 20th system.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
SYSTIMO REGISTERS AND OPERATES THE TUNNEL
Austin 604 ≠ Choosin 936 ≠ asked-six 1182
```

```text
browser systimo-ui
  → owned controller (service id roller-api)
  → /systimo
    → /systimo/health|systems|connections|tree|graph|datasets|artifacts|actions|agents
    → /systimo/topology|plan|bots|runtime/endpoints
    → POST /systimo/scope/sessions
    → POST /systimo/refresh|query
    → GET  /systimo/traces[/{id}]
    → GET  /systimo/orchestra/context/{trade_id}
    → POST /systimo/query/{id}/artifact
    → POST /systimo/actions/{id}/dry-run|apply
```

Preferred ports are migration defaults, not service identities. Coverage:
`research/systimo/STARTUP_COVERAGE.md`. Live bindings are
`research/systimo/state/runtime.json`.

CSV SSOT: `research/systimo/`. Package: `ROLLER/roller/systimo/`.
Jump research-context tunnels: `GET /jump/research-context/austin|choosin`.
Jump data plane: `GET/POST /jump/data/*` (capability router, context,
lineage, dataset handles, explicit export). Systimo `path_back` walks
Jump → product → source. Jump does not copy warehouses.
Momento LS `:5181` `:8792` remains the live-host observe adapter.

HTTP 200 is not a fill. `execution_enabled` is false. Missing is
`UNAVAILABLE`, never `$0`.

## Surfaces

| Piece | Path |
|---|---|
| Dashboard | `frontend/systimo` (`systimo-ui`, preferred 5193) |
| API | `ROLLER/scripts/terminal_api.py` service `roller-api` `/systimo/*` |
| Inspect | `ROLLER/roller/systimo/` |
| Library | `research/systimo/` |
| LS observe | unmanaged, preferred 5181 / 8792, not autostart |

## Run

```text
./bin/momento plan --scope quad-1
./bin/momento doctor --scope all
./bin/momento open --scope quad-1
```

`./bin/momento` is the CLI because the `momento/` package directory already owns that name.
`up` prints the scoped plan and does not start `momento-live.service`.
`open` prints the shell URL from the runtime record once that process is owned.

## Do not

- Remount the shell inside `frontend/roller-terminal`, Choosin Texas, or `:5190`.
- Replace Momento LS live-service observe.
- Reclaim `ROLLER/roller/maintenance` (that is ingest).
- Invent a 20th system or treat this as System Orchestration.
- Mix N=604 / 936 / 1182. Lock drift is `INTEGRITY_DRIFT`.
- Edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, W9, Phase 21.
- Submit orders, start/stop `momento-live.service`, or set `VITAL_AWS_CONTROL`.
