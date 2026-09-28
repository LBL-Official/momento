# ROLLER V4A build report

**Date:** 2026-09-06  
**Extension of:** V1 / V2 / V3  
**`state_schema_version`:** 2.0.0  
**`measurement_schema_version`:** 3.0.0  
**`fundamental_schema_version`:** 4.0.0-A

```text
F_t ≠ TRUTH    K_t ≠ F_t    K_t - F_t ≠ EDGE
LIVE EXECUTION = FALSE
```

## Executive result

V4A implements a prior-only, information-bounded NBA empirical home-win estimator behind `db.fundamental()`. It does not implement Greeks, basis, signals, or train/OOS. The NBA 2025-2026 last-per-clock-bucket surface is classified **ROBUST** under the configured support floors.

## Gate-by-gate results

| Gate | Result |
|------|--------|
| 1 Architecture audit | PASS. pytest 81, validate PASS, leakage PASS before implementation. [`ROLLER_V4A_PRE_IMPLEMENTATION_AUDIT.md`](ROLLER_V4A_PRE_IMPLEMENTATION_AUDIT.md) |
| 2 Metadata | `4.0.0-A` versions; registry; `core_v1`; dataset reject |
| 3 Prior-only corpus | both clocks + current-game identity; support object |
| 4 Estimator | `fundamental_win_probability_empirical_v1` = wins/n; refusal |
| 4.5 Surface audit | **ROBUST** (see surface report) |
| 5 Public API | `db.fundamental`; leakage hook; no F_t cache |
| 6 Final validation | 105 pytest passed; validate PASS; leakage PASS |

## Implemented

- Registry / definitions / fundamental conditioning
- `db.fundamental(observation_id, ...)`
- Eligibility: `state_available_at < t` AND `result_available_at < t` AND `game_id != current`
- Exact `probability_wins` / `probability_n`
- Support floors from config; `effective_n` null
- Firewall + `fundamental_leakage`

## Partial

- Clock isolation is elapsed-from-remaining, not pure remaining-clock research
- One NBA season only
- Optional possession / pre-game strength exist as data and stay **off**
- Derived corpus is last-PBP-per-bucket, not every event

## Not supported

- WNBA / NCAAB F_t
- Smoothing, interpolation, nearest neighbor, shrinkage
- Basis, ΔK/ΔF, residual Greeks, L2
- `db.research` train/OOS
- Live trading / signals / PnL

## Explicit discrepancies

| Expected (spec) | Actual | Decision | Reason | Tests |
|-----------------|--------|----------|--------|-------|
| Generic subject − opponent | Home − away | Adopt home as subject | Existing PBP/Y columns | `test_fundamental_orientation.py` |
| Subject-agnostic Y | `Y=1` iff `home_win==1`; ties both 0 | Document | `canonical/games.py` | orientation + probability |
| Clock field as bucket source | Remaining ISO stored; elapsed bucketed | Document | V2/V3 `elapsed_game_seconds` | `test_fundamental_clock.py` |
| Observation never has terminal winner | V1 unmasks `GAME_STATE.game.home_win` after result | Preserve V1; exclude by game id | Do not mutate V1 | `test_v4a_leakage.py`, current-game exclusion |
| Multi-season floor | Warehouse has one NBA season | `minimum_unique_seasons=1` | Spec: only floors data can support | support tests |
| Reuse V3 conditioning | Separate `fundamental_conditioning.json` | Do not edit V3 file | Would rewrite V3 `condition_id` | `test_fundamental_conditioning.py` |

## Fundamental surface result

**ROBUST** for NBA 2025-2026 `core_v1` under the configured floors (352 cells, 4.5% null at end-of-sample; early-season median unique games 36). Rare extreme cells still refuse. This is not a trading endorsement.

## Recommended later V4 work (not started)

Provenance-preserving F_t use in basis research, temporal experiment construction, multi-season support if more seasons are ingested. Still not a trading system.
