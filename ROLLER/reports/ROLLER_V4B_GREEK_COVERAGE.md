# ROLLER V4B Greek coverage

Constructibility of query-time measurements. **Not a trading report.**

```text
Δ ≠ EDGE    Γ ≠ EDGE    Θ ≠ EDGE    BASIS ≠ EDGE    RESIDUAL ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
```

- Sport/season: `NBA` / `2025-2026`
- Status: `OBSERVED`
- Games scanned: `8`
- Visible adjacent pairs: `4035`
- Configured 60s pairs: `2804`
- Non-60s pairs (`TIME_GAP`): `1231`
- Interval-ok rate: `0.6949194547707559`

Warehouse pair scan does not estimate edge, fill probability, or PnL.
Baselines remain `E[M | core_v1]` with `measurement_available_at_i < t` and current-game exclusion.

## Families

| family | layer |
| --- | --- |
| market_delta_1m | observed |
| fundamental_delta | observed |
| response_delta | observed |
| market_fundamental_basis | observed |
| basis_delta | observed |
| score_delta | observed |
| discrete_gamma | observed |
| theta_observed | observed |
| pure_theta | observed |
| candle_range | observed |
| absolute_return | observed |
| realized_market_volatility | observed |
| directional_efficiency | observed |
| v4b_baseline | baseline |
| v4b_residual | residual |

## Machine summary

```json
{
  "sport": "NBA",
  "season": "2025-2026",
  "expected_interval_seconds": 60,
  "note": "Coverage of constructibility only. \u0394/\u0393/\u0398/B/R \u2260 EDGE. Not a trading recommendation.",
  "status": "OBSERVED",
  "games_scanned": 8,
  "visible_pairs": 4035,
  "interval_ok_pairs": 2804,
  "interval_gap_pairs": 1231,
  "status_counts": {
    "TIME_GAP": 1231,
    "INTERVAL_OK": 2804
  },
  "identity_rows": 7254,
  "interval_ok_rate": 0.6949194547707559
}
```
