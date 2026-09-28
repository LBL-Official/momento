# ROLLER V4B build report

**Date:** 2026-09-06  
**Extension of:** V1 / V2 / V3 / V4A  
**`state_schema_version`:** 2.0.0  
**`measurement_schema_version`:** 3.0.0  
**`fundamental_schema_version`:** 4.0.0-A  
**`greek_schema_version`:** 4.0.0-B  
**`database.version` / `pipeline_version`:** 4.0.0-B

```text
Δ ≠ EDGE    Γ ≠ EDGE    Θ ≠ EDGE    BASIS ≠ EDGE    RESIDUAL ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
LIVE EXECUTION = FALSE
```

## Executive result

V4B is a query-time empirical measurement layer behind `db.greeks()`. It consumes V4A `F_t` and visible home candles. It does not extend `O_t`, does not invent L2, and does not authorize trade, signal, or alpha.

## Gate-by-gate results

| Gate | Result |
|------|--------|
| 1 Architecture audit | PASS. 105 pytest; validate PASS; leakage PASS before engines. [`ROLLER_V4B_PRE_IMPLEMENTATION_AUDIT.md`](ROLLER_V4B_PRE_IMPLEMENTATION_AUDIT.md) |
| 2 Metadata | `greek_schema_version=4.0.0-B`; definitions/registry; `dataset()` hint `use db.greeks()` |
| 3 Observed measurements | Shared `X_t`; exact rationals; 60s interval; provenance; runtime reconciliation |
| 4 Baselines | `E[M \| core_v1]` on `measurement_available_at_i < t` + current-game exclusion; exact MAD |
| 5 Residuals + API | `R = M − E`; null ≠ 0; `db.greeks()`; `v4b_leakage` + validate hook after `run_integrity` |
| 6 Docs + coverage | This report; [`V4B_EMPIRICAL_GREEKS.md`](../docs/V4B_EMPIRICAL_GREEKS.md); [`V4B_INFORMATION_BOUNDARIES.md`](../docs/V4B_INFORMATION_BOUNDARIES.md) |

## Implemented

- Package [`roller/v4b/`](../roller/v4b/) with one-way `candles` + `fundamentals` → `X_t` → measurements → baseline → residual
- `db.greeks(observation_id, ...)`
- Exact `Fraction` arithmetic; no floor-only `F_e4`
- `F_{t-1}` via a new observation id at the previous visible candle cutoff
- Firewall for `v4b_*` / `greek_observations` / `greek_baselines`

## Partial / recorded discrepancies

1. V3 `basis.py` remains `NOT_YET_IMPLEMENTED`.
2. Candle at exact cutoff is hidden.
3. `MARKET_STATE` has no high/low; V4B reads candle OHLC.
4. `pure_theta` is PARTIAL (period + score held), not no-event theta.
5. V3 `db.residual` ≠ V4B residual.
6. `discrete_gamma` is a temporal second difference, not score-surface curvature.
7. `realized_market_volatility` is absolute variation, not IV/stdev.
8. V3 `market_return_1m_backward` still accepts non-60s adjacency.

## Not implemented

Signals, PnL, fills, L2, neural nets, clustering, new Kalshi client, `db.research` train/OOS, `greek_everything.csv`, mutating `core_v1`.

## Verification

| Check | Result |
|-------|--------|
| `.venv/bin/python -m pytest -q` | **157 passed** |
| `scripts/validate_roller.py` | **PASS** (integrity + V4B hook) |
| `scripts/leakage_audit.py` | **PASS** |
| `scripts/audit_v4b_greeks.py` | **OBSERVED** (see coverage report) |

Coverage of warehouse candle intervals is in [`ROLLER_V4B_GREEK_COVERAGE.md`](ROLLER_V4B_GREEK_COVERAGE.md). Coverage ≠ edge.
