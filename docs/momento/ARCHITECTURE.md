# Momento Systems — 19-System Architecture V0

**Status:** Architecture freeze V0. See [`ARCHITECTURE_FREEZE_V0.md`](ARCHITECTURE_FREEZE_V0.md).
**Registry SSOT:** [`momento/registry/systems.yaml`](../../momento/registry/systems.yaml)
**Loader:** [`ROLLER/roller/momento/registry.py`](../../ROLLER/roller/momento/registry.py)
**LIVE EXECUTION = FALSE**

This document is the ownership architecture.

It is **not** the sequential capability roadmap in
[`docs/architecture/MOMENTO_SYSTEMS_ROADMAP.md`](../architecture/MOMENTO_SYSTEMS_ROADMAP.md).
That file remains the 16-row program board (Oct 1 ingest, Terminito later).

```text
19 SYSTEMS ≠ 19 MICROSERVICES
15 TOURNAMENT + 4 INFRASTRUCTURE
ABSTRACTION WITHOUT DUPLICATION
ONE OWNER PER PROBLEM
NO FAKE PRODUCTION READINESS
```

## Who owns what

| System | Owner of | Implementation today | Research vs production |
|---|---|---|---|
| Database | What happened | ROLLER warehouse + research_query | Research measure. Not a trade decision. |
| Data Analysis | What the evidence says | SuperASI. STAX and Research Engine v1 are submodules. | Research only. |
| Fair Odds Modeling | External implied probability | None | Not implemented. |
| In House Odds Modeling | Momento P(win) | `apps/terminal-efficiency` XIB/MCD | Frozen research. Phase 7 not authorized. |
| Data Modeling | Path efficiency | Jump Drive + SuperASI path decomp + Choosin path/Dallas + nba_path_fe | Partial research. |
| Game Modeling | Terminal efficiency | SuperASI terminal decomp + XIB when authorized | Partial research. F_t vs K_t blocked. |
| Signal Generation | Why a trade opportunity exists | `first80.py` + Fort Worth policy + ITI catalog | Research FIRST80. Not live FIRST01. |
| Trade Breakdown | Trade economics | Choosin Texas | Research. 40-stop is legacy benchmark. |
| Position Stratification | What type of position this is | Austin PCA+KNN `#/austin` | Research. N=604. |
| Dynamic Risk Engine | Does the hold reason still exist | DRE `:5191` + Austin experiment artifacts | Research. Not `crates/risk`. Not policy. V1 aim: preserve αP&gt;0 then ΔP→ΔP*(Xt). |
| Hedging Analysis | When / how much to hedge | Ballhog `:5192` + Austin hedge + Family E; BDR `#/bdr` write-ups | Partial. Ballhog is the product Frontend. BDR is the library. YES+BUY-NO-taker not built. |
| Relative Value Hedging | Is the hedge rich/cheap | TK Ultra `#/tk-ultra` + `GENERIC_RV` / `BINARY_COMPLEMENT_V0` | Partial. Formula, not market truth. Missing = UNAVAILABLE. |
| Position Management | Current vs target exposure | None. Fort Worth is policy text. | Not implemented. |
| Algorithmic Execution | How NBA FIRST80 orders will be obtained | Contract / dry-run only (`nba-first80-001`) | NOT IMPLEMENTED. No NBA bot. MLB 001 is reference only. |
| Momento Systems | Trade-lifecycle architecture (champion) | Registry + `/momento` + `:5190` bracket | Partial. Not runtime orchestration. |
| System Maintenance | Observe / maintain | Systimo `:5193` Frontend + Momento LS observe adapter | Partial. UNKNOWN allowed. |
| Data Ingestion | Feed canonical data | ingest scripts + auto_roller + research-ingest | Partial. Autojest not built. |
| Trade Reconciliation | Intended vs observed fills / positions | `PositionReconciliation` contract only | NOT IMPLEMENTED. Observe-only. Not Vital. |
| System Orchestration | Runtime job / pipeline sequencing | None | NOT IMPLEMENTED. Distinct from champion Momento Systems. |

## Who calls whom

Canonical edges are in [`BRACKET.md`](BRACKET.md) and `roller.momento.bracket.OWNERSHIP_EDGES`.

```text
data_ingestion → database
database + data_analysis → data_modeling
fair_odds_modeling + in_house_odds_modeling → game_modeling
data_modeling + game_modeling → signal_generation
trade_breakdown + position_stratification → dynamic_risk_engine
hedging_analysis + relative_value_hedging → position_management
dynamic_risk_engine + position_management → algorithmic_execution
signal_generation + algorithmic_execution → momento_systems
system_maintenance observes; it is not a producer edge
trade_reconciliation observes; it is not a producer edge
system_orchestration observes; it is not a producer edge
```

SuperASI consumes ROLLER measurements. That is a research import, not a second
bracket edge. Do not add hidden hops.

## What object is passed

Named contracts only in V0. Typed models are Phase 4.
See [`API_CONTRACTS.md`](API_CONTRACTS.md).

Every future object needs `schema_version`, `generated_at`, `as_of`,
`source_system`, game/event identity, and provenance where applicable.
No downstream system may silently use future data.

## Where is the implementation / frontend / backend

| System | Frontend | Backend today | Phase 2 façade |
|---|---|---|---|
| Database | `:5179` ROLLER | `:8791` `/warehouse-research` | `/momento/systems/database` |
| Data Analysis | `:5179/?app=superasi` | `:8791` `/superasi` | `/momento/systems/data_analysis` |
| Data Modeling | `:5179/?app=jump` | `:8791` `/jump` | `/momento/systems/data_modeling` |
| Trade Breakdown | `:5182#/` | `:8791` `/choosin-texas` | `/momento/systems/trade_breakdown` |
| Position Stratification | `:5182#/austin` | `:8791` `/austin` | `/momento/systems/position_stratification` |
| Dynamic Risk Engine | `:5191` DRE (`#/objective`) | `:8791` `/dre` | `/momento/systems/dynamic_risk_engine` |
| Algorithmic Execution | `:5190` momento_page | registry / `/momento/systems/algorithmic_execution` | contract only |
| System Maintenance | `:5193` Systimo | `:8791` `/systimo` (LS observe `:8792`) | `/momento/systems/system_maintenance` |
| Hedging Analysis | `:5192` Ballhog | `/ballhog` | `/momento/systems/hedging_analysis` |
| Relative Value Hedging | `:5190/#/tk-ultra` TK Ultra | `/momento/tk-ultra` | `/momento/systems/relative_value_hedging` |
| All others | `:5190` momento_page | registry only | `/momento/systems/{id}` |

`/momento/*` is the Phase 2 façade on `:8791`. It delegates; it does not copy engines.

## Absolute

- Do not create a 20th top-level system.
- Do not treat System Orchestration as the champion Momento Systems box.
- Do not treat Trade Reconciliation as Vital or as an OMS.
- Do not move working engines to make the folder tree look cleaner.
- Do not edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, W9, warehouse Phase 21, or MLB 001.
- Do not call `crates/risk` the Dynamic Risk Engine.
- Do not remount Choosin Texas, Vital, Systimo, or Momento LS inside roller-terminal.
- Do not invent fair odds, RV residuals, fills, or L2.
- Do not mix N universes: 1182 / 936 / 905 / 604 / 1230 / 797 / 280.
