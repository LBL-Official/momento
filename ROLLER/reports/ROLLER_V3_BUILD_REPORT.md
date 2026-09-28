# ROLLER V3 build report

**Date:** 2026-09-06  
**Extension of:** V1 and V2 (not a rewrite)  
**`state_schema_version`:** 2.0.0 (unchanged)  
**`measurement_schema_version`:** 3.0.0

```text
O_t ≠ Y_{t→t+h} ≠ E[Y|C] ≠ R_t
Δ ≠ EDGE    RESIDUAL ≠ EDGE
CANDLE PATH ≠ FILL
LIVE EXECUTION = FALSE
```

## 1. Executive summary

V3 is a measurement laboratory, not a strategy engine. Backward candle features live on `O_t`. Forward responses, PIT-safe baselines, and residuals are explicit APIs. Residual = observed Y minus a conditional expectation built only from responses already available before the cutoff.

## 2. Constitutional invariants

Half-open `available_at < cutoff` is unchanged in `timeutil.py`. Baseline eligibility uses both `observation_time_i < t` and `response_available_at_i < t`. Equality hidden. Insufficient support ≠ 0.

## 3. V1 dependencies

Canonical games, PBP, integer E4 candles, team `*_pre`, D2D, identity. Preserved.

## 4. V2 dependencies

`db.observation()`, deterministic `observation_id`, `state_schema_version` 2.0.0, labels boundary, NBA possessions, incomplete lineups. Preserved. `db.research` retargeted to V4 stub.

## 5. V3 architecture

```text
O_t (S_t + Γ_t + M_{≤t})
        → condition(O_t)
        → db.response Y_{t→t+h}
        → eligible historical Y
        → db.baseline E[Y|C]
        → db.residual
```

No `greek_everything.csv`. No `db.measure`.

## 6. Pre-implementation audit

[`ROLLER_V3_PRE_IMPLEMENTATION_AUDIT.md`](ROLLER_V3_PRE_IMPLEMENTATION_AUDIT.md). V1/V2 pytest, validate, and leakage passed before engines.

## 7. Measurement registry

[`meta/measurement_registry.json`](../meta/measurement_registry.json). Each family has `information_boundary` backward | forward | schema_only and an honest `contains_future_information` flag.

## 8. Observed measurement inventory

On `O_t` as `BACKWARD_MEASUREMENTS`: return, open-to-close, high-low, realized vol, directional efficiency, acceleration. All OHLC objects `path_information_status=UNORDERED_SUMMARY`.

## 9–13. Greek inventory

| Family | Status |
|--------|--------|
| Delta backward | REAL |
| Delta forward `market_response_{1,5,10}m` | REAL |
| Gamma `market_acceleration_1m` | REAL when 3 closes exist |
| Theta / clock_response | PARTIAL (no pure-clock claim) |
| Volatility proxies | REAL; zero range undefined |
| Basis | SCHEMA_ONLY / NOT_YET_IMPLEMENTED |
| Response beta | grouped means only |
| Residual | REAL when support sufficient |

## 14. Conditional baseline architecture

`conditioning_schema_v1`. Deterministic `condition_id`. Prior-eligible corpus only. `baseline_construction_version=prior_eligible_v1`.

## 15. Residual architecture

Integer `(Y*n - sum)/n` as numerator/denominator. `INSUFFICIENT_SUPPORT` omits value.

## 16. Support and dependence

Unique games tracked separately from observation count. `effective_n` is null.

## 17. Future-information boundary

`dataset()` rejects `*_response`, corpora, residuals, `greek_*`. `observation()` has no Y/baseline/residual/label.

## 18–19. Leakage and tests

`greek_leakage.py` plus `test_baseline_response_availability.py`. Full pytest run recorded below.

## 20. Dataset inventory

No new public PIT datasets. Optional `derived/v3_response_corpus.csv` is sampled first/mid/last candle observations per game.

## 21. Capability matrix

| Measurement | Current status |
|-------------|----------------|
| Candle backward M | REAL |
| Candle forward Y 1m/5m/10m | REAL |
| Score response | REAL where PBP exists |
| Clock response | PARTIAL |
| Possession-conditioned cells | NBA REAL status only |
| Basis / F_t | NOT_YET_IMPLEMENTED |
| L2 / 1s / queue / fills | NOT_SUPPORTED / SCHEMA_ONLY |

## 22–26. Status buckets

**IMPLEMENTED:** registry, backward section, `db.response` / `baseline` / `residual`, eligibility both clocks, support objects, grouped beta/surfaces, leakage hooks.

**PARTIAL:** theta / pure clock; sampled (not full-grid) response corpus.

**SCHEMA_ONLY:** basis, `market_delta_1s_l2`, L2 families.

**NOT_SUPPORTED:** order flow, queue, fill probability, book imbalance, true impact.

**NOT YET:** F_t, V4 train/OOS, effective_n.

## 27. Known limitations

1-minute OHLC cannot recover intraminute order. Corpus sampling is first/mid/last, not every timestamp. Residual means are exact rationals, not fills.

## 28. Recommended V4 work

Temporal experiment construction, training-window discipline, validation/OOS, optional F_t with provenance, surface stability. V4 is still not a trading system.
