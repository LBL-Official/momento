# Terminal Efficiency — Point-in-Time Data Contract

**Status:** BINDING GATE (Phase 3)  
**Rule:** No information may cross forward through time.

```text
prediction_timestamp
feature_as_of_timestamp
game_event_timestamp
market_timestamp
```

These four clocks are never collapsed.

---

## Observation

| Field | Meaning |
|-------|---------|
| `prediction_timestamp` | Instant the model is asked to speak |
| `feature_as_of_timestamp` | Latest information timestamp used in features (`<= prediction`) |
| `game_event_timestamp` | Wall time of the basketball event that produced the state |
| `market_timestamp` | Kalshi candle `end_period_ts` (UTC period end), or null |
| `final_home_win` | Label only. Firewalled from the design matrix |
| `data_quality_flags` | `OBSERVED \| MODELED \| UNAVAILABLE \| AMBIGUOUS` |

`P(home) + P(away) = 1` for every scored row.

---

## Availability rules

**In-game:** `source_event_time <= prediction_timestamp`

**Pregame aggregates:** `source_game_end_time < target_game_start_time`  
Same-day: only games whose `result_available_at` is strictly before the target start. If end time is unknown, exclude the same calendar day.

**Rolling stats:** target game excluded by identity, not by date equality alone.

**Fitters:** `SimpleImputer` / encoders / selectors / GBM fit on **2024–25 TRAIN only**.  
Calibration (Platt) may use VAL after the model is fit. Do not then re-tune features.

**2025–26:** frozen. Never used to fit, select, or calibrate.

**Kalshi prices:** alignment/residual only. Forbidden as XIB/MCD features (`allowed_in_xib=false` in the registry).

**Player availability:** UNAVAILABLE (GAP-001). No hindsight inactive lists.

---

## Training vs apply grids

| Dataset | Unit | Role |
|---------|------|------|
| A | one row per game at scheduled start | pregame research |
| B | one row per valid possession close | **primary training grid** |
| C | one row per aligned candle | apply / coverage only |

Training must succeed when Dataset C is empty. Never synthesize candles.

---

## Leakage audit

`python -m terminal_efficiency audit-leakage --league NBA --season 2024-2025`

PASS → Phases 4–6. FAIL → stop fitting.

Machine-readable report: `derived/.../terminal_efficiency/reports/leakage_audit.json`
