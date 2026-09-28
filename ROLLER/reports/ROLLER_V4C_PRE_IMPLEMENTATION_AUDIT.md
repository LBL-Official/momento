# ROLLER V4C pre-implementation audit

**Date:** 2026-09-06  
**Purpose:** Gate 1. Confirm V1–V4B temporal and API contracts before any V4C taxonomy layer.  
**Invariant (locked):** `visible(row, t)` iff `available_at < t`. Equality hidden.

```text
V4B = measurement implementation
V4C = architecture, identity, regime, and constructibility
```

V1–V4B pytest, `scripts/validate_roller.py`, and `scripts/leakage_audit.py` were re-run as part of this gate. No `roller/v4c/` engines existed at audit time.

| Check | Result |
|-------|--------|
| `.venv/bin/python -m pytest -q` | **157 passed** |
| `scripts/validate_roller.py` | **PASS** (`n_errors`: 0; V4B hook PASS) |
| `scripts/leakage_audit.py` | **PASS** (`n_errors`: 0) |

```text
[PASS] V4B frozen
[PASS] default db.greeks() semantics identified
[PASS] no Greek fields on O_t
[PASS] V3 basis.py unchanged
[PASS] backward.py unchanged
[PASS] no historical L2
[PASS] db.research() remains stub
```

```text
A GREEK NAME DOES NOT AUTHORIZE A MEASUREMENT.
V4C MUST NEVER CREATE A NEW NUMBER when providing architecture.
Δ/Γ/Θ/VEGA/Λ/Ω/Ψ/B/R ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
MEASUREMENT ≠ EDGE
CANDLE PATH ≠ EXECUTABLE PATH
LIVE EXECUTION = FALSE
```

---

## Default `db.greeks()` semantics (must stay V4B)

[`Roller.greeks`](../roller/point_in_time/query.py) has **no** `schema_version` today. Every call runs:

```text
parse_observation_id
  → assemble_observation
  → assemble_shared_xt
  → compute_observed
  → build_greeks_payload
```

Public payload keys: `identity`, `versions` (`greek_schema_version=4.0.0-B`), `observed` (thirteen families), `availability`, `support`, `status`, `contains_future_information`, plus optional `fundamental` / `market` / `baseline` / `residual`.

Default and future `schema_version="4.0.0-B"` must keep **identical public semantics and field meanings**. V4C may only overlay after obtaining this canonical result.

V4C **must not independently calculate**:

```text
market_delta_1m
fundamental_delta
response_delta
market_fundamental_basis
basis_delta
score_delta
discrete_gamma
theta_observed
pure_theta
candle_range
absolute_return
realized_market_volatility
directional_efficiency
```

If V4C needs one of those values, it copies the already-produced V4B rational:

```text
numerator_V4C == numerator_V4B
denominator_V4C == denominator_V4B
```

Not float equality.

---

## Observation firewall

[`FORBIDDEN_OBS_KEYS`](../roller/validation/greek_leakage.py) already excludes labels, Y, F_t, and V4B `greeks` / `v4b`.

[`audit_observation_excludes_greeks`](../roller/validation/v4b_leakage.py) rejects `greeks`, `v4b`, `market_fundamental_basis`.

[`assemble_observation`](../roller/state/observation.py) does not attach F_t or Greeks. V4C catalog and measurements must not enter `O_t`. Add `v4c` to observation forbidden keys.

---

## Dataset firewall today

[`dataset_is_v4b`](../roller/point_in_time/filters.py) rejects `v4b_*`, `greek_observations`, `greek_baselines` with **`use db.greeks()`**.

V3/V4A hint strings remain:

- fundamental names → `use db.fundamental()`
- other future tables → `use db.labels()`

V4C must reject `v4c_*` with `use db.greeks()` without changing those strings.

---

## Frozen files (do not edit)

| File | Status |
|------|--------|
| [`roller/timeutil.py`](../roller/timeutil.py) | Constitutional half-open filter |
| [`roller/greeks/basis.py`](../roller/greeks/basis.py) | `NOT_YET_IMPLEMENTED`; `fundamental_probability_source=None` |
| [`roller/measurement/backward.py`](../roller/measurement/backward.py) | V3 backward measurements; not 60s-strict |
| [`config/fundamental_conditioning.json`](../config/fundamental_conditioning.json) | `core_v1` dimensions locked |
| V4B measurement engines under [`roller/v4b/`](../roller/v4b/) | Consume, do not reproduce |

`db.research()` still raises `ResearchNotImplementedError` mentioning `db.fundamental()` and `db.greeks()`. Keep stub.

---

## No historical L2

Warehouse market data remains 1-minute OHLC candles. `MARKET_STATE` has no high/low. There is no order-book, trade-tick, or second-snapshot store. V4C must register microstructure objects as `NOT_CONSTRUCTIBLE`, not invent them from candles.

```text
OHLC ≠ ORDER BOOK
CANDLE RETURN ≠ SIGNED FLOW
HIGH/LOW ≠ MICROPRICE
VOLUME ≠ QUEUE STATE
```

---

## Versions (current, pre-V4C)

| Field | Value |
|-------|-------|
| `database.version` / `pipeline_version` | `4.0.0-B` |
| `state_schema_version` | `2.0.0` |
| `measurement_schema_version` | `3.0.0` |
| `fundamental_schema_version` | `4.0.0-A` |
| `greek_schema_version` | `4.0.0-B` |
| `greek_architecture_version` | **absent** |

V4C may bump only `version` / `pipeline_version` → `4.0.0-C` and add `greek_architecture_version=4.0.0-C`. Keep `greek_schema_version=4.0.0-B`.

---

## Data capability ≠ measurement validity

NBA V2 [`capabilities.py`](../roller/state/capabilities.py) has `possessions=REAL`. That is **data** capability.

```text
POSSESSION_STATE = AVAILABLE
POSSESSION_CONDITIONED_F = NOT VALIDATED
possession_delta = NOT_YET_IMPLEMENTED
```

`DATA EXISTS ≠ MEASUREMENT IS VALID`. Do not infer possession from candles.

---

## `validate_roller.py`

Runs `run_integrity` then `run_v4b_validate`. V4C hook must be called **after** both, not folded into the V1 walker.

---

## Recommended Gate 2 actions (next)

1. Keep V1–V4B tests green.
2. Metadata only: `greek_architecture_version=4.0.0-C`; declarative `config/greek_v4c_registry.json`; information regimes; capability taxonomy; `dataset()` reject `v4c_*`.
3. `NEW EMPIRICAL MEASUREMENTS CREATED = 0`.
4. Do not start the lossless mapper until Gate 2 registry tests pass.
