# ROLLER V4C build report

**Date:** 2026-09-06  
**Extension of:** V1 / V2 / V3 / V4A / V4B  
**`state_schema_version`:** 2.0.0  
**`measurement_schema_version`:** 3.0.0  
**`fundamental_schema_version`:** 4.0.0-A  
**`greek_schema_version`:** 4.0.0-B  
**`greek_architecture_version`:** 4.0.0-C  
**`database.version` / `pipeline_version`:** 4.0.0-C

```text
A GREEK NAME DOES NOT AUTHORIZE A MEASUREMENT.
V4C CREATES ZERO NEW EMPIRICAL NUMBERS.
Δ/Γ/Θ/VEGA/Λ/Ω/Ψ/B/R ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
MEASUREMENT ≠ EDGE
CANDLE PATH ≠ EXECUTABLE PATH
LIVE EXECUTION = FALSE
```

## Executive result

V4C is a taxonomy, identity, capability, provenance, and constructibility overlay. It consumes the canonical V4B `db.greeks()` result. It does not rediscover candles, recalculate `F`, manufacture microstructure, or authorize trade.

```text
db.greeks(id)                         → V4B
db.greeks(id, schema_version=4.0.0-B) → V4B
db.greeks(id, schema_version=4.0.0-C) → V4B canonical result → lossless map
```

## Gate-by-gate results

| Gate | Result |
|------|--------|
| 1 Audit | PASS. [`ROLLER_V4C_PRE_IMPLEMENTATION_AUDIT.md`](ROLLER_V4C_PRE_IMPLEMENTATION_AUDIT.md) |
| 2 Registry + capability | Declarative [`greek_v4c_registry.json`](../config/greek_v4c_registry.json); regimes; capability taxonomy; `dataset()` rejects `v4c_*` with `use db.greeks()` |
| 3 Lossless map | `V4C_EMPIRICAL_COMPUTATION_COUNT = 0`; measurements vs catalog; provenance `V4B_CANONICAL_RESULT` / `LOSSLESS_METADATA_MAPPING` |
| 4–6 | Deferred. No new estimators. |

## Verification

| Check | Result |
|-------|--------|
| `.venv/bin/python -m pytest -q` | **182 passed** |
| `scripts/validate_roller.py` | **PASS** (integrity + V4B + V4C hooks) |
| `scripts/leakage_audit.py` | **PASS** (`n_errors`: 0) |

## Implemented

- Package [`roller/v4c/`](../roller/v4c/) — registry, regimes, capability, types, availability clocks, provenance, lossless mapper, taxonomy facades
- `schema_version` on `db.greeks()`; default remains V4B
- Payload split: `measurements` (copied V4B rationals) vs `catalog` (intentional nulls)
- Dataset firewall for `v4c_*`
- Validate hooks after `run_integrity` and `run_v4b_validate`

## Partial / recorded restraints

1. V4B measurement engines were not rewritten.
2. `pure_theta` remains PARTIAL. `PURE THETA ≠ NO-EVENT THETA`.
3. NBA `possessions=REAL` does not implement `possession_delta`.
4. Microstructure objects stay `NOT_CONSTRUCTIBLE`. No candle proxy.
5. `response_beta` is `NOT_YET_IMPLEMENTED`, not a candle regression.
6. V3 `basis.py` remains `NOT_YET_IMPLEMENTED`.
7. `db.research()` remains a stub.

## Docs

- [`V4C_GREEK_ARCHITECTURE.md`](../docs/V4C_GREEK_ARCHITECTURE.md)
- [`V4C_INFORMATION_REGIMES.md`](../docs/V4C_INFORMATION_REGIMES.md)
- [`V4C_CONSTRUCTIBILITY_MATRIX.md`](../docs/V4C_CONSTRUCTIBILITY_MATRIX.md)
- [`V4C_FUTURE_MICROSTRUCTURE.md`](../docs/V4C_FUTURE_MICROSTRUCTURE.md)
