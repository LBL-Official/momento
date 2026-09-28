# ROLLER V3 pre-implementation audit

**Date:** 2026-09-06  
**Purpose:** Gate 1. Confirm V1/V2 temporal contracts before any measurement engines.  
**Invariant (locked):** `visible(row, t)` iff `available_at < t`. Equality hidden.

V1/V2 pytest, `scripts/validate_roller.py`, and `scripts/leakage_audit.py` were re-run as part of this gate. All passed. Do not treat planned V3 measurements as implemented.

## Required V3 conditions

| Component | Expected | Actual | Status | V3 Dependency | Recommended Action |
|-----------|----------|--------|--------|---------------|--------------------|
| PIT choke point | `available_at < cutoff` | [`timeutil.apply_as_of`](../roller/timeutil.py); [`filters.public_filter`](../roller/point_in_time/filters.py) | PASS | Required — do not switch to `<=` | Keep V1 half-open. Do not modify `timeutil.py`. |
| Equality | `available_at == cutoff` hidden | Two-clock tests + `test_half_open_equality_still_hidden` | PASS | Required | Keep. Add baseline two-clock test in V3. |
| V2 observation | Deterministic, versioned, no labels | [`assemble_observation`](../roller/state/observation.py); `state_schema_version` 2.0.0 | PASS | Consume via `db.observation()` | Add `BACKWARD_MEASUREMENTS` only; never Y/baseline/residual. |
| observation_id | Reproducible | [`make_observation_id`](../roller/state/observation_id.py) | PASS | Response/baseline keys | Keep codec. |
| state_schema_version | Available, unchanged | `roller.json` `2.0.0` | PASS | Do not bump | Keep `2.0.0`. Add `measurement_schema_version` 3.0.0 separately. |
| Labels | Explicit future-information boundary | `db.labels()`; `dataset()` rejects `game_state_features` / `*_labels` | PASS | Keep | Extend reject list for `*_response` / `*_baseline` / `*_residual`. |
| Possessions | NBA rule version documented | `possession_rule_version` 2.0.0; other sports `NOT_SUPPORTED` | PASS | Conditioning may use NBA status only | Do not invent WNBA/NCAAB possessions. |
| Market candles | Integer E4, `available_at` = close | [`CANDLE_COLUMNS`](../roller/canonical/candles.py); `yes_bid_close` | PASS | K field for M and Y | Document `yes_bid_close`. Path = `UNORDERED_SUMMARY`. |
| Player data | Capability honest | NBA REAL where `personId`; else NOT_SUPPORTED | PASS | Not required for V3 Greeks | Keep. |
| Lineup data | INCOMPLETE | `LINEUP_STATE` INCOMPLETE; no fabricated five | PASS | Do not condition on complete lineups | Keep. |
| Future-information registry | Operational | `contains_future_information` on schemas + `FUTURE_DATASET_NAMES` | PASS | Extend for responses | Gate 1 metadata. |
| Leakage tests | Passing | 60 pytest; validate PASS; leakage PASS | PASS | Expand with greek/baseline eligibility | Do not start engines if this regresses. |
| `db.research` | Stub; no train/OOS | Raises `ResearchNotImplementedError` | PASS | Retarget message to V4 | Do not implement research(). |

## Discrepancies V3 must record, not invent away

1. V2 `db.research` error text still says “V3 stub”. Retarget to V4 without implementing splits.
2. V2 `game_state_features.csv` remains on disk and is future information; keep `dataset()` reject.
3. NCAAB `scheduled_start` empty; V1 conservative proxy stays.
4. Current market data is 1-minute OHLC. Do not compute L2 from candles.
5. No validated F_t provider exists. Basis stays `NOT_YET_IMPLEMENTED`.
6. V2 labels use 60s/300s score horizons; V3 forward candle horizons are 1m/5m/10m. Different objects.

## Recommended Gate 1 actions

1. Keep V1/V2 tests green.
2. Bump database/pipeline to 3.0.0; keep `state_schema_version` 2.0.0; add `measurement_schema_version` 3.0.0.
3. Add measurement registry with `information_boundary` backward | forward | schema_only.
4. Add conditioning / horizons / greek definition configs.
5. Reject forward measurement dataset names from `dataset()`.
6. Do not start Gate 2 until Gate 1 tests pass.
