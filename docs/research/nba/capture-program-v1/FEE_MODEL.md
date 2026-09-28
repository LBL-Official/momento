# Fee model

```text
FEE MODEL STATUS: UNRESOLVED
```

Production `KalshiFeeModel` is not wired and is not treated as truth.

Do not hard-code an assumed production fee schedule.

---

## Interface

`apps/nba-data/scripts/capture_program_v1/fee_models.py`

```text
FeeModelInterface
  calculate_entry_fee(...)
  calculate_exit_fee(...)
  calculate_settlement_fee(...)
  calculate_total_fee(...)
```

| Model | Status | Meaning |
| --- | --- | --- |
| `ZERO_FEE_MODEL` | SIMULATED | Placeholder zeros |
| `PUBLISHED_SCHEDULE_ESTIMATE` | ESTIMATED | `ceil_6dp(coef · C · P · (1−P))`, M=1 |
| `CUSTOM_STRESS_MODEL` | SIMULATED | 2× published coefficients |
| `OBSERVED_PRODUCTION_MODEL` | UNAVAILABLE | Until verified Kalshi execution |

Published coefficients copied from the frozen audit (not invented here):

- taker 0.07
- maker 0.0175
- settlement documented 0 for simple yes/no
- KXNBAGAME maker multiplier: UNKNOWN

Per-contract e6 at the frozen audit’s 80/40 points (1 contract):

| Leg | e6 | cents |
| --- | ---: | ---: |
| maker entry 80 | 2,800 | 0.28 |
| taker entry 80 | 11,200 | 1.12 |
| taker stop 40 | 16,801 | 1.6801 |

Every report must display **FEE MODEL STATUS** prominently.

`OBSERVED_PRODUCTION_MODEL` must remain unavailable until verified
against actual Kalshi execution. Do not silently fill it from the
published schedule.
