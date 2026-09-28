# Systimo startup coverage

Ports in this file are preferred defaults. The live binding is the runtime store.
`./bin/momento` discovers the controller from that record. `8791` is not the service id.

`up` does not set `VITAL_AWS_CONTROL`, does not call Vital start/stop/kill, and does not submit orders.
`up --scope all` includes `mlb-execution-desk`. `up --scope quad-1` does not.
Shared `roller-api` and `momento-shell` may be up for both scopes. A Quad 1 session still cannot read MLB endpoints.

## System types

Each `momento/registry/systems.yaml` id appears once.

| Type | Class | How it is served |
|---|---|---|
| database | shared | `roller-api`, `roller-terminal` |
| data_analysis | shared | `roller-terminal` |
| data_modeling | shared | `roller-terminal` |
| fair_odds_modeling | unimplemented | Quad 1 coming soon. Other quadrants blank |
| in_house_odds_modeling | unimplemented | Quad 1 coming soon. Other quadrants blank |
| game_modeling | unimplemented | Quad 1 coming soon. Other quadrants blank |
| signal_generation | unimplemented | Quad 1 coming soon. Other quadrants blank |
| momento_systems | shared | `momento-shell` |
| algorithmic_execution | split by instance | Quad 1 closed. Quad 3 desk on the shell, bot `UNAVAILABLE`. Quad 4 `mlb-execution-desk` observes `mlb-001` |
| dynamic_risk_engine | managed | `drevo` |
| trade_breakdown | managed | `choosin-texas` |
| position_stratification | shared | Austin on `choosin-texas` |
| position_management | managed | `positman` |
| hedging_analysis | managed | `ballhog` |
| relative_value_hedging | shared | TK Ultra on `momento-shell` |
| system_maintenance | shared | `systimo-ui`. Global and Quad 1 are sessions, not two processes |
| data_ingestion | shared | API on `roller-api`, page on `momento-shell`. Autojest is `UNAVAILABLE` |
| trade_reconciliation | shared | Observe-only page on `momento-shell`. Does not invent fills |
| system_orchestration | shared | Orchestra query on `roller-api` and `momento-shell`. No extra daemon |

## Processes

| Service | Ownership | Autostart | Preferred port |
|---|---|---|---|
| roller-api | shared | yes | 8791 |
| roller-terminal | shared | yes | 5179 |
| choosin-texas | managed | yes | 5182 |
| momento-shell | shared | yes | 5190 |
| drevo | managed | yes | 5191 |
| ballhog | managed | yes | 5192 |
| systimo-ui | shared | yes | 5193 |
| positman | managed | yes | 5194 |
| mlb-execution-desk | managed, quad-4 | yes | 5180 |
| momento-ls | unmanaged | no | 8792 |
| mlb-001 | external | no | not allocated |

## Bots

| Bot | Quadrant | Owner | Runtime | Started by up |
|---|---|---|---|---|
| mlb-001 | quad-4 | vital | momento-live.service | no |

`mlb-002` through `mlb-005` and `atp-001` stay unassigned. There is no `wnba-*` bot directory. `nba-first80-001` is a reserved contract id and does not open the Quad 1 execution node.

Drawn slots: 80. Reserved capacity: 10. Those ten are not drawn, launched, or named as products.
