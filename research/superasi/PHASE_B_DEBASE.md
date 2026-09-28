# SuperASI Phase B — Debase

Status: implemented. Research only. Not live trading. Phase A stays locked.

```text
Phase A folder
  Roller[Strategy].csv
  SuperasiABase[Strategy].csv
        │
        ▼
   SuperASI B — Debase
        │
        ├─ OBSERVED     Roller header EV / R:R, IQR 1 as mean
        ├─ THEORETICAL  same grade report + desk at IQR 1
        └─ MONTE_CARLO  Bernoulli + Mode B at p_working = IQR 1
                │
                ▼
        SuperasiBDeBase[Strategy].csv
```

Landing is SuperASI Results Labs (phase a). Run SuperASI B — Debase writes one CSV with Base DeComposition, Base DeGrading, and Base DeValidation.

Disk:

```text
ROLLER/superasi_labs/phase_b/<Strategy_Name>/
  Roller[Strategy Name].csv
  SuperasiABase[Strategy_Name].csv
  SuperasiBDeBase[Strategy_Name].csv
  metadata.json
```

Stored bytes = downloaded bytes.

## Dynamic EV and R:R

Debase does not hard-code +20/−40, 1:2, or `p_BE=2/3` as this strategy.

Canonical economics come from the Roller header (`average_win`, `average_loss`, `risk_reward`, `gross_ev`). Recomputed `(W·reward − L·risk) / N` must match `gross_ev` or the run fails closed.

```text
IQR 1     = Wilson Q1 of decided W/L (z = Φ^{-1}(0.75))
p_working = IQR 1  (this is the degraded mean for any backtest)
ev_debase = p_working · average_win − (1 − p_working) · average_loss
p_BE      = average_loss / (average_win + average_loss)
R_w       = allocation × (average_win / entry)
R_l       = allocation × (−average_loss / entry)
```

IQR 1 is the lowest hinge of the strategy's IQR box. Debase treats that hinge as the mean, then runs the same grade_config_v1 report and Theoretical desk as Phase A on that worst-form p. Official YES does not rewrite path LOSS. Hold-YES counts only when the compiled win exit is HOLD.

`$20,000` / 5% / 10 trades/week / 20 weeks is bankroll sizing only. Phase A desk +20/−40 is copied as a labeled comparison.

Missing `average_win`, `average_loss`, or entry fails closed. No 20/40 fallback.

## DeGrading

`grade_config_v1` is unchanged. Inputs are conservative: `p = IQR 1`, EV = `min(header gross_ev, ev_debase)`. Theoretical desk `p_used` is that same IQR 1, not the observed mean.

`DEBASE_GRADE` cannot exceed Phase A `BASE_GRADE`. Both letters are stored.

`A_PLUS_INSTRUMENT_GATE` (`E[R_20] ≥ 67%` and `P_floor < 5.50%`) is a valuation pass/fail, not a letter.

## Honesty

`candle_path_not_fill`. Fees / slippage / fills = `UNAVAILABLE`. `net_ev = NOT_COMPUTABLE`. `LIVE_GRADE = UNAVAILABLE`.

Labs `question` is persisted in Phase B `metadata.json` when present. SuperASI does not reconstruct a `ResearchQuestion` from first-op columns and does not call warehouse compile/execute.

## API

```text
GET  /superasi/debase/sources
POST /superasi/debase/run
GET  /superasi/debase/results
GET  /superasi/debase/results/{id}
GET  /superasi/debase/results/{id}/csv?which=debase|abase|roller
```

## Non-goals

JUMP ITI may consume Final Results; it does not mutate them. Jump B is Bot Creation (control plane, not the engine). Jump C is the operating dashboard (confirmed state only). Phase 21. Warehouse Confirm & Run. Invented A–F from 67%/5.50%. Mode D. PNG graph files. Changing Phase A `BASE_GRADE` or `grade_config_v1`. Live / Risk Decision Engine / Kalshi submit.
