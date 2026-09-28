# Momento Systems — Frontend Map

The bracket is a portal. Existing products stay themselves.
Do not remount Choosin Texas, Vital, Systimo, or Momento LS inside roller-terminal.

Routes come from [`momento/registry/systems.yaml`](../../momento/registry/systems.yaml).

## Product surfaces

| System | Kind | URL |
|---|---|---|
| Database | separate app | `http://127.0.0.1:5179` |
| Data Analysis | same-app mode | `http://127.0.0.1:5179/?app=superasi` |
| Data Modeling | same-app mode | `http://127.0.0.1:5179/?app=jump` |
| Trade Breakdown | separate app | `http://127.0.0.1:5182#/` |
| Position Stratification | hash route | `http://127.0.0.1:5182#/austin` |
| Dynamic Risk Engine | separate app | `http://127.0.0.1:5191/` (`#/objective`) |
| Algorithmic Execution | momento_page | `http://127.0.0.1:5190/#/systems/algorithmic_execution` |
| Hedging Analysis | separate app | `http://127.0.0.1:5192/` |
| Relative Value Hedging | momento_page | `http://127.0.0.1:5190/#/tk-ultra` |
| System Maintenance | separate app | `http://127.0.0.1:5193/` (Systimo). LS observe remains `:5181`. |
| Trade Reconciliation | momento_page | `http://127.0.0.1:5190/#/reconciliation` |
| System Orchestration | momento_page | `http://127.0.0.1:5190/#/orchestra` |
| Momento Systems | momento_page | `http://127.0.0.1:5190/` |
| All other systems | momento_page | `http://127.0.0.1:5190/#/systems/{id}` |

`:5190` is the Momento bracket app. Algorithmic Execution is a momento_page.
There is no NBA bot frontend. Vital `:5180` is MLB infrastructure, not this box.

## Not bracket boxes

Link from the owning system page, not as extra cards:

- `#/dallas` — path evidence (`data_modeling`)
- `#/book` — registered book (`trade_breakdown`)
- `#/fort-worth` — policy (`signal_generation` / `hedging_analysis` / `position_management`)
- `#/bdr` — BDR write-ups (`hedging_analysis` library). Not the product Frontend. Not a 20th system.
- `#/tk-ultra` — TK Ultra calculator + BINARY_COMPLEMENT_V0 (`relative_value_hedging` Frontend). Not a 20th system.

## Artifact UIs (research_paths only)

`frontend/dre-v2` … `dre-v7`, `frontend/pade-v1`, `frontend/first80-*`,
`frontend/a1-hybrid-hedge`, `frontend/nba-research-engine-v2`,
`frontend/execution-integrity`.

Several collide on 5179–5182. Product ports win.

## Click contract (Phase 3)

Box → modal → Backend | Frontend.
Backend opens the system inspector.
Frontend opens `frontend_target.url`.
No automatic navigation.
No fake frontends.
