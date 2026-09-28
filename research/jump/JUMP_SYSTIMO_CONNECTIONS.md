# Jump ↔ Systimo connections (data plane V0)

CSV SSOT: `research/systimo/registry/connections.csv`.
Jump does not copy these sources.

All Jump research tunnels are `QUERY` or `READ`. WRITE/CONTROL stay DENY.

| connection_id | source → Jump | capability | permission | lifecycle | lock |
|---|---|---|---|---|---|
| austin_to_jump | austin | AUSTIN_QUERY_AT | QUERY | IMPLEMENTED | N=604 |
| austin_replay_to_jump | austin | AUSTIN_REPLAY | QUERY | IMPLEMENTED | N=604 |
| austin_trade_to_jump | austin | AUSTIN_GET_TRADE | QUERY | IMPLEMENTED | N=604 |
| austin_universe_to_jump | austin | AUSTIN_UNIVERSE | QUERY | IMPLEMENTED | N=604 |
| choosin_to_jump | choosin_texas | CHOOSIN_TRADE_CONTEXT | QUERY | IMPLEMENTED | N=936 |
| ballhog_to_jump | ballhog | BALLHOG_INTENT | QUERY | IMPLEMENTED | N=604 |
| tk_ultra_to_jump | tk_ultra | TK_ULTRA_ASSESSMENT | QUERY | IMPLEMENTED | N=604 |
| roller_warehouse_to_jump | roller | WAREHOUSE_QUERY | QUERY | IMPLEMENTED | |
| roller_identity_to_jump | roller | ROLLER_GAME_IDENTITY | QUERY | IMPLEMENTED | |
| roller_observations_to_jump | roller | ROLLER_OBSERVATIONS | QUERY | IMPLEMENTED | |
| roller_pbp_to_jump | roller | ROLLER_PBP | QUERY | IMPLEMENTED | |
| roller_settlement_to_jump | roller | ROLLER_SETTLEMENT | QUERY | IMPLEMENTED | |
| vital_to_jump | vital | VITAL_BOT_STATUS | QUERY | IMPLEMENTED | |
| systimo_catalog_to_jump | systimo | SYSTIMO_CATALOG | QUERY | IMPLEMENTED | |
| superasi_iti_to_jump | superasi | SUPERASI_ITI | QUERY | IMPLEMENTED | |

`path_back` from `jump` walks these incoming edges. Health is refreshed
by Systimo; Jump displays it. Cache is not implemented (`CACHE ≠ SOURCE
OF TRUTH`).
