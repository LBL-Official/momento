# Jump Canonical Data Plane V0 — recon

Facts from disk. Jump does not become the warehouse.

```text
LIVE EXECUTION = FALSE
CACHE ≠ SOURCE OF TRUTH
Austin 604 ≠ Choosin 936 ≠ asked-six 1182
JUMP CONSUMES. OWNERS KEEP THE DATA.
```

## Jump backend today

Package `ROLLER/roller/jump/`. HTTP `/jump/*` on `:8791`. Frontend
`frontend/roller-terminal` `?app=jump`.

Already consumes:

| Source | Path | Copy? |
|---|---|---|
| Vital | `vital_client.py` in-process | No |
| ROLLER warehouse | `jump/warehouse/` pointers + DuckDB read | No |
| SuperASI ITI | `jump/iti/` alias | No |
| Austin | `jump/adapters/austin.py` → DRE `query_at(persist=False)` | No |
| Choosin | `jump/adapters/choosin.py` → DRE `get_trade_context` STATIC | No |

Missing as a **canonical data plane**:

- No capability router (research-context handlers are one-off)
- No Ballhog / TK Ultra read adapters on Jump
- No composite `JumpResearchContext`
- No `JumpLineage` / SHOW SOURCE
- No dataset handles / EXPORT through Systimo artifacts
- Warehouse workbench exists (`/jump/warehouses/*`) but is not composed with Austin/Choosin/Ballhog/TK Ultra

## Ownership (do not move)

| Data | Owner | Jump role |
|---|---|---|
| Canonical warehouse parquet | ROLLER | QUERY pointer |
| Austin 604 book + query_at | Austin | QUERY persist=False |
| FIRST80 derived-four 936 | Choosin Texas | QUERY STATIC |
| Hedge intent q*/ρ*/Δ* | Ballhog | READ output |
| RV assessment | TK Ultra | READ output |
| MLB 001 observe | Vital | OBSERVE |
| Connection registry | Systimo | catalog + governance |

## Systimo tunnels already pointing at Jump

`austin_to_jump`, `choosin_to_jump`, `vital_to_jump`,
`roller_warehouse_to_jump`, `superasi_iti_to_jump`.

## Implemented (data plane V0)

Package `ROLLER/roller/jump/data/`. HTTP `/jump/data/*`. Explorer
`#/{sport}/data`. Systimo now registers Ballhog, TK Ultra, ROLLER
identity/observations/PBP/settlement, Austin replay/trade/universe, and
catalog tunnels. `path_back` is a Systimo query type.

Jump still does not copy source databases. Cache is not implemented.

## Frontend

Drive + warehouse workbench + DATA / RESEARCH at `#/{sport}/data`
using existing `ju-drive` chrome. Do not redesign Jump. Do not remount
Systimo, Choosin, or Vital.
