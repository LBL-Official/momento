# CTO-W2 DEPENDENCIES

**Upstream:** CTO-W1 (types readable; catalog/coverage)  
**Downstream consumers (later, not this run):** CTO-W3 (market path), W4 (sync), W5 (canonical episode), W8 (event theta when valid)

## W1 consumption

W2 **reads** exported `foundation/w2_contract.rs`. W2 does **not** edit `foundation/**`. See [../W2_CTO_DECISIONS.md](../W2_CTO_DECISIONS.md).

## Blocking conditions

| Work | Blocker |
|------|---------|
| Official `mlb_game_pk` map | No authorized schedule/PBP source |
| Historical GameState from real games | Same + zero local PBP files |
| Event Theta values | Intentionally not computed in W2 |

Contract/engine work is not blocked. Historical coverage is incomplete by data, not by missing engine.

## Parallelism

W3 implementation is **not authorized**. This package must not start it.
