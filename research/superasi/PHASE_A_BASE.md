# SuperASI Phase A — Base

Status: implemented. Research only. Not live trading. Not Debase.

```text
ROLLER CSV
     │
     ├───────────────┐
     ▼               ▼
OBSERVED         THEORETICAL
evidence         Mode A desk
     │               │
     │               ▼
     │          MONTE CARLO
     │          risk profile
     └──────────┬───────────┐
                ▼           ▼
           COMPARISON    VALIDATION
                │
                ▼
           BASE GRADING
```

Mode A (`p=0.70`, `+20%/−40%`, `$20,000`, `5%`, 10 trades/week) is the measuring instrument. It is not `BASE_GRADE`.

Monte Carlo is a 20-week desk risk profile (`$15,000` floor, `$30,000` target). It is not `BASE_GRADE`.

`LIVE_GRADE = UNAVAILABLE`. Candle-path W/L is not a fill. Fees, slippage, and fills stay `UNAVAILABLE`. `net_ev = NOT_COMPUTABLE`.

## Ingest

Source: `ROLLER/labs/<folder>/<lab_id>/Roller[Strategy Name].csv`

Required `record_type=row`. Empty-audit `strategy` records fail closed.

Observed facts come from row recount plus Roller header economics (`gross_ev`, `average_win`, `average_loss`, `risk_reward`). SuperASI does not invent a second EV.

Wilson interval: `z=1.96` via `roller.risk.formulas.wilson_interval` on decided trade rows.
This is the generic warehouse → Labs → SuperASI A ingest for every NBA (and other-desk) lab, not a named study.
Hold-YES / hold-NO (`HELD_TO_SETTLEMENT` + settlement) count as the same W/L as ROLLER only when the compiled win exit is HOLD.
Path-only REACH/CROSS exits do not treat HELD+YES as a win.
Path LOSS stays LOSS even when official settlement is YES. Hold-YES is 100¢ settlement, not a fill.

## grade_config_v1

`BASE_GRADE = min(research_evidence, coverage, robustness, theoretical_alignment, validation)`.

Composite score is ranking-only (`0.40 / 0.20 / 0.20 / 0.10 / 0.10`) and never raises the letter.

| Component | Inputs |
|---|---|
| research_evidence | Wilson lower vs `p_BE=2/3`, cap by header `gross_ev` sign |
| coverage | decided rate, MISSING/INVALID settlement rate, header N vs row count |
| robustness | `N_decided` bands; Wilson width caps `>0.20→C`, `>0.30→D` |
| theoretical_alignment | observed `p` vs desk `0.70` and `p_BE` |
| validation | header/row reconcile, hashes, risk record (missing risk is a warning) |

Same observed win rate at `N=20` and `N=500` must not share a `BASE_GRADE`.

## CSV

`SuperasiABase[Strategy_Name].csv` is long-format (`record_type`, `evidence_layer`, `program`, `metric`, `value`, …) plus repeated Roller metadata.

`evidence_layer` ∈ `{OBSERVED, THEORETICAL, MONTE_CARLO}`.

Trade rows stay in the sibling Roller CSV.

Disk:

```text
ROLLER/superasi_labs/phase_a/<Strategy_Name>/
  Roller[Strategy Name].csv
  SuperasiABase[Strategy_Name].csv
  metadata.json
```

Stored bytes = downloaded bytes.

## API

```text
GET  /superasi/base/sources
POST /superasi/base/run
GET  /superasi/base/results
GET  /superasi/base/results/{id}
GET  /superasi/base/results/{id}/csv?which=base|roller
```

v1 `/superasi/library/*` and asked-six remain for regression. Production SuperASI UI does not use them.

## Non-goals

Graph image files. Mode C invention. Fee/fill fabrication. Warehouse `execute` / `compiler` / `load_dataset`. W9. Live FIRST01.

Phase B Debase is specified in `research/superasi/PHASE_B_DEBASE.md`.
