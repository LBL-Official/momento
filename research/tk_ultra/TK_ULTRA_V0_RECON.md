# TK Ultra V0 recon

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
formula ≠ truth
tk_ultra is not a 20th system
```

Facts from disk before V0. Not a redesign brief.

## Frontend

- App: `frontend/momento-systems/` Vite `:5190`
- Route: `#/tk-ultra` (`App.tsx` `parseHash`)
- Page: `frontend/momento-systems/src/TkUltra.tsx`
- CSS: `frontend/momento-systems/src/desk.css` (shared with bracket / BDR)
- Client: `frontend/momento-systems/src/api.ts`
  - `GET /api/momento/tk-ultra`
  - `GET /api/momento/tk-ultra/assess?...`
- Types: `TkUltraDesk`, `TkUltraAssess` in `src/types.ts`

Visual desk: letter, GENERIC_RV calculator, 80/45/35 corridor table, NQ/ES worked example. Manual fields. Empty wing/beta → `SOURCE_UNAVAILABLE` hero. No Austin picker. No Choosin stamp. No Ballhog panel. No order button. No client-side residual math (assess comes from API).

## Backend

- Desk engine: `ROLLER/roller/momento/tk_ultra.py`
  - `SCHEMA = tk_ultra_desk_v1`
  - `handle_desk`, `handle_assess`
- Formula: `ROLLER/roller/momento/relative_value.py`
  - `method = tk_relative_value_v1`
  - `(wing/base)*beta` futures ratio; Fraction exact
  - NQ/ES golden `rv_ticks = -247.92`
- Façade: `ROLLER/roller/momento/api.py` `handle_tk_ultra` / `handle_tk_ultra_assess`
- Mount: `ROLLER/scripts/terminal_api.py` `:8791`
  - `GET /momento/tk-ultra`
  - `GET /momento/tk-ultra/assess`
- Registry: `momento/registry/systems.yaml` `relative_value_hedging`
  - Frontend product TK Ultra `#/tk-ultra`
  - `api_namespace: /momento/tk-ultra`

## Domain models (pre-V0)

No `TKUltraState`. No `TKUltraRVAssessment`. Existing assess payload: `reading` `WING_CHEAP|WING_RICH|FAIR_LINE`, `residual`, `rv_ticks`, `relationship_multiplier`. `binary_formula_is_truth = false`. Missing inputs: `status=SOURCE_UNAVAILABLE`.

Anchors: user-typed `wing_anchor` / `base_anchor`. No timestamp. No `price_basis`. Default calculator `base_anchor=80`, `base_price=45`, empty wing.

Cheap/rich: sign of residual only. No ±1¢ deadband.

## Input sources (pre-V0)

```text
Austin     none
Choosin    none
Ballhog    none (Ballhog is forbidden from calling /assess)
Quotes     MANUAL_INPUT only
```

## Tests

`ROLLER/tests/test_momento_tk_ultra.py`: not an 18th system; NQ/ES ticks; desk; missing assess; invalid base=0 → 400; frontend routes `/tk-ultra`.

## Pre-V0 gaps required by establishment

- BINARY_COMPLEMENT_V0 (do not run futures ratio on A/B YES)
- Dual-leg lock / stop-equivalent B avg / partial hedge budget / runway
- Independent Austin + Choosin adapters
- Optional BallhogHedgeIntent sibling (in-process `handle_intent`)
- Relationship vs route as two estimands
- Provenance, universes 604 vs 936, `execution_enabled=false`
