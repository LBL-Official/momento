# Systimo V0 recon

Facts from disk. No behavior change in this document.

```text
LIVE EXECUTION = FALSE
19 SYSTEMS ≠ 20
system_maintenance TODAY = Momento LS :5181 / :8792
ROLLER/roller/maintenance = data_ingestion, not System Maintenance
```

## Existing System Maintenance slot

[`momento/registry/systems.yaml`](../../momento/registry/systems.yaml) `system_maintenance`:

- status `PARTIAL`, version `momento_ls_v1`
- Frontend: Momento LS `http://127.0.0.1:5181`
- Backend: `127.0.0.1:8792` `/health` `/observe`
- Implementation: `ROLLER/roller/ls/`, `ROLLER/scripts/ls_api.py`, `frontend/momento-ls/`
- Notes: adapter. Not `ROLLER/roller/maintenance`.

Momento LS observes `momento-live.service`. Read-only SSM. Does not submit. Does not set `VITAL_AWS_CONTROL`.

## Absent

- No `systimo` package, frontend, or `systemmaintenance/` root
- No `research/systimo/` before this V0
- Port `5193` unused (5190 Momento/TK Ultra, 5191 DRE, 5192 Ballhog)

## Jump today

Package `ROLLER/roller/jump/`. Frontend `frontend/roller-terminal` `:5179/?app=jump`. HTTP `/jump/*` on `:8791`.

Reads:

- Vital in-process (`vital_client.py`)
- Warehouses as pointers (`roller.warehouse`, no copy)
- SuperASI ITI
- Choosin asked-six **lock integers** only (`locks_asked_six`)

Does **not** call `roller.dre.adapters.austin.query_at` or Choosin `get_trade_context`. Austin/Choosin research-context tunnels do not exist yet.

## Austin / Choosin (canonical sources)

| Product | Package | N | Consumer adapter |
|---|---|---|---|
| Austin | `ROLLER/roller/austin/` `/austin/*` | 604 | `roller.dre.adapters.austin.query_at` persist=False |
| Choosin Texas | `ROLLER/roller/choosin_texas/` `/choosin-texas/*` | 936 STATIC | `roller.dre.adapters.choosin.get_trade_context` |

## Independent consumers already in code

- Ballhog `:5192` `/ballhog/*` — own adapters → DRE Austin/Choosin
- TK Ultra `:5190/#/tk-ultra` `/momento/tk-ultra/*` — own adapters → DRE Austin/Choosin; optional `handle_intent` sibling
- DRE `:5191` `/dre` — wraps Choosin + Austin only

There is no Austin → Ballhog → TK Ultra edge.

## Other products

| Product | Port / API |
|---|---|
| Vital | `:5180` `/vital` on `:8791` |
| Choosin Texas UI | `:5182` |
| ROLLER / Jump Drive | `:5179` |
| Momento LS | `:5181` `:8792` |

Position Management: `NOT_IMPLEMENTED`. Fort Worth is policy text, not an engine.

## Store conventions

Atomic JSON: temp + `os.replace` (STAX, Vital, Jump). `fcntl.flock` in `ROLLER/roller/auto_roller/locking.py`. No app `filelock` package. CSV writers elsewhere are mostly non-atomic; Systimo must be stricter.

## Mount

Single FastAPI `ROLLER/scripts/terminal_api.py` `:8791`. CORS lists 5179–5192. Add 5193. LS stays a separate process on 8792.

## Ownership decision for V0

Systimo becomes System Maintenance **Frontend**. Momento LS remains the live-host observe adapter. `ROLLER/roller/maintenance` stays ingest.
