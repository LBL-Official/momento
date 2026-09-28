# ROLLER V4B pre-implementation audit

**Date:** 2026-09-06  
**Purpose:** Gate 1. Confirm V1–V4A temporal and API contracts before any V4B measurement engine.  
**Invariant (locked):** `visible(row, t)` iff `available_at < t`. Equality hidden.

V1–V4A pytest, `scripts/validate_roller.py`, and `scripts/leakage_audit.py` were re-run as part of this gate.

| Check | Result |
|-------|--------|
| `.venv/bin/python -m pytest -q` | **105 passed** |
| `scripts/validate_roller.py` | **PASS** (`n_errors`: 0) |
| `scripts/leakage_audit.py` | **PASS** (`n_errors`: 0) |

Do not treat planned V4B objects as implemented. `db.greeks()` does not exist. `roller/v4b/` does not exist.

```text
Δ ≠ EDGE    Γ ≠ EDGE    Θ ≠ EDGE    BASIS ≠ EDGE    RESIDUAL ≠ EDGE
O_t ≠ F_t ≠ K_t ≠ V4B measurements
LIVE EXECUTION = FALSE
```

---

## Actual V4A interfaces V4B must consume (not invent)

### Observation identity

[`roller/state/observation_id.py`](../roller/state/observation_id.py):

```text
OBS_{internal_game_id}_{YYYYMMDDTHHMMSSmmmZ}_V{state_schema_version}
```

`parse_observation_id` right-splits twice so `internal_game_id` may contain underscores. Time for `db.fundamental()` comes from the parsed id, **not** `InformationSet.cutoff`.

`make_observation_id(gid, observation_time, state_schema_version)` is how V4B must reconstruct `F_{t-1}` at `C_{t-1}.available_at`.

`observation_time` on assembled `O_t` is `to_iso(cutoff)` ([`timeutil.to_iso`](../roller/timeutil.py) stores seconds + `Z`, no microseconds).

### `db.fundamental()` return shape (authoritative)

[`estimate_fundamental`](../roller/fundamental/estimator.py) returns, among other fields:

| Field | When implemented | When refused |
|-------|------------------|--------------|
| `value` | `{numerator: wins, denominator: n}` | `null` |
| `probability_wins` / `probability_n` | integers | `null` |
| `status` | `IMPLEMENTED` | `INSUFFICIENT_SUPPORT` / `NOT_SUPPORTED` / `MISSING_REQUIRED_INPUT` / `INVALID_CONDITION` |
| `available_at` | **observation cutoff ISO** (same as `information_cutoff`, `measurement_time`, `calculated_at`) | cutoff ISO still present |
| `observation_id` | target id | target id |
| `condition_id` | `core_v1` digest | may still be set |
| `contains_future_information` | `true` | `true` |

V4A timestamps `F_t.available_at` as the **observation cutoff**, not a candle close. V4B `measurement_available_at` for any measurement that requires `F_t` must be no earlier than that field.

NBA-only: non-NBA → `status=NOT_SUPPORTED`, `value=null`. Never 0.50 / K / global average.

### How `db.fundamental()` is invoked

[`Roller.fundamental`](../roller/point_in_time/query.py):

1. `gid, obs_time, ver = parse_observation_id(observation_id)`
2. `obs = assemble_observation(cfg, gid, as_of=obs_time)`
3. corpus = caller or `load_fundamental_corpus`
4. `estimate_fundamental(..., observation=obs, corpus=...)`

Therefore `F_{t-1}` **must** be a new `observation_id` at `C_{t-1}.available_at` so step 2 assembles a different `O_{t-1}` and step 4 uses a different prior-only cutoff. Forbidden: relabel `F_t` or look up history with the current cutoff.

### Score / clock / period on `O_t`

[`game_state_section`](../roller/state/game.py) + [`observation_state_fields`](../roller/fundamental/conditioning.py):

- `S` source: `GAME_STATE.data.score.score_differential_home` (unwrapped `{value, status, source}`), equivalently home − away
- `period`: `GAME_STATE.data.period`
- elapsed: `GAME_STATE.data.elapsed_game_seconds` (regulation 720s / OT 300s from remaining ISO `clock`)

`S_t = home_score − away_score` is already this warehouse convention. V4B must not reinterpret ΔS as total points.

### Visible K

[`MARKET_STATE`](../roller/state/market.py) carries `yes_bid_close` integer E4, open/ask, volume. **No high/low.** V4B must read candle OHLC itself (`yes_bid_high` / `yes_bid_low` on `kalshi_candles`).

[`visible_candles`](../roller/measurement/backward.py) already: `apply_as_of` then `team_side == "home"`. Half-open: candle `available_at == cutoff` is hidden. V3 `market_return_1m_backward` does **not** require 60s adjacency (`test_volatility.py` uses a 90s gap). V4B must not change `backward.py`.

[`latest_candle`](../roller/canonical/align.py) uses the same half-open filter.

### V3 APIs (do not mutate)

| API | Meaning |
|-----|---------|
| `db.observation` | `O_t` — no labels, no F_t, no Greeks |
| `db.response` | forward `Y_{t→t+h}` |
| `db.baseline` | `E[Y \| V3 condition]` on `observation_time_i < t` **and** `response_available_at_i < t` |
| `db.residual` | V3 market-response residual, not V4B `R^M` |
| `db.fundamental` | V4A `F_t` |

[`roller/greeks/basis.py`](../roller/greeks/basis.py) remains `NOT_YET_IMPLEMENTED` / `fundamental_probability_source=None`. Do not implement V4B by filling this file.

`db.research()` raises `ResearchNotImplementedError` (V4A wording). Keep stub.

### Observation firewall

[`FORBIDDEN_OBS_KEYS`](../roller/validation/greek_leakage.py): `labels`, `response`, `baseline`, `residual`, `Y`, `fundamental`, `F_t`, `FUNDAMENTAL`. V4B must not add Greeks onto `assemble_observation`.

### Dataset firewall today

[`dataset_contains_future_information`](../roller/point_in_time/filters.py) already rejects `greek_*`, `measurement_*`, `*_baseline`, `*_residual`, `_response`, and V4A `fundamental*`. Hint is `use db.fundamental()` for fundamental names else `use db.labels()`. V4B names (`v4b_*`, `greek_observations`, `greek_baselines`) need `use db.greeks()` **without** changing the V3/V4A hint strings.

### Versions (current)

| Field | Value |
|-------|-------|
| `database.version` / `pipeline_version` | `4.0.0-A` |
| `state_schema_version` | `2.0.0` |
| `measurement_schema_version` | `3.0.0` |
| `fundamental_schema_version` | `4.0.0-A` |
| `greek_schema_version` | **absent** |

V4B may bump only `version` / `pipeline_version` → `4.0.0-B` and add `greek_schema_version=4.0.0-B`. Do not mutate `core_v1` in [`config/fundamental_conditioning.json`](../config/fundamental_conditioning.json).

### `validate_roller.py`

Runs **only** `run_integrity`. V4B hook must be called **after** that function, not folded into the V1 integrity walker.

### `to_iso` vs observation-id milliseconds

`to_iso` drops sub-seconds. Observation ids keep milliseconds. Reconstructing an id from a candle `available_at` that is second-aligned is consistent with warehouse candle closes.

---

## Capability vs V4B intent

| Object | Current capability | V4B use |
|--------|--------------------|---------|
| Home `yes_bid_close` E4 | REAL | `K_t` |
| Candle OHLC high/low | REAL on candle rows; absent on `MARKET_STATE` | `candle_range`, `directional_efficiency` |
| Half-open visibility | REAL | `available_at < cutoff` |
| 60s interval | NOT enforced by V3 | V4B `market_delta_1m` requires configured 60s |
| `F_t` wins/n | REAL (NBA, support floors) | consume exactly |
| `F_{t-1}` at prior candle cutoff | possible via new `observation_id` | required |
| L2 / OFI / queue | UNAVAILABLE | do not invent |
| Event-level “no basketball events” | NOT in `core_v1` | `pure_theta` PARTIAL only |
| V3 `db.residual` | REAL (forward Y residual) | different object |

---

## Discrepancies V4B must record, not “fix”

1. V3 `basis.py` remains `NOT_YET_IMPLEMENTED`; V4B `market_fundamental_basis` is a different object.
2. Current candle at exact cutoff is hidden (`available_at < t`).
3. `MARKET_STATE` has no high/low; V4B reads candle OHLC itself.
4. `pure_theta` cannot prove “no events,” only unchanged period + score.
5. V3 `db.residual` is market-response residual, not V4B `R^M`.
6. `discrete_gamma` will be a temporal second difference, not score-surface curvature.
7. V3 `close_to_close_realized_volatility` is a different name/object from V4B `realized_market_volatility`.
8. V3 `market_return_1m_backward` accepts non-60s adjacency; V4B `market_delta_1m` must not.
9. After `result_available_at < cutoff`, `GAME_STATE.game` may carry unmasked `home_win` (V1). F_t still excludes current `game_id`. V4B inherits that; it must not treat current-game `home_win` as a Greek input.
10. F_t `available_at` is the observation cutoff, not the last PBP or candle time.

---

## Recommended Gate 1 actions (next)

1. Keep V1–V4A tests green.
2. Metadata only: `greek_schema_version=4.0.0-B`; definitions + registry; `dataset()` hint `use db.greeks()` for V4B names.
3. Do not start measurement engines until Gate 2 registry tests pass.
4. Then shared `X_t` → observed measurements → baselines → residuals → `db.greeks()`.
