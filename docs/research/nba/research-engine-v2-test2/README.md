# NBA Research Engine V2 — Test 2

Possession-normalized first-80 trade-state discovery.

```text
NBA_RESEARCH_ENGINE_V2_TEST2
```

Research only. Does **not** overwrite Path Engine V1 or Game Path Engine V2
verdicts. Does not change live FIRST01, Risk, or Kalshi execution.

## Question

Are all first-80 trades the same type of trade?

```text
T_i = { G_t, P_t, M_t, ΔG, ΔM, C_t }
q = P(Y_40 = 1 | T_i at ENTRY_DECISION_TIME)
EV_gross = 1 − 3q
```

Primary clock is **possession index**. Wall-clock and official game clock
describe *where* the game is. Kalshi 1-minute candles are sampling artifacts.

## Reuse (read-only)

- Frozen first-80: 1,230 / 910 / 320, q = 26.02%
- Alignment model: Game Path Engine V2 `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`
- Splits: TRAIN BUILD / VALIDATION CHOOSE / OOS VERIFY

## Layout

| Role | Path |
| --- | --- |
| Spec | `docs/research/nba/research-engine-v2-test2/` |
| Code | `apps/nba-data/scripts/research_engine_v2_test2/` |
| Derived | `.../derived/nba/momento_research_engine_v2_test2/` |
| Dashboard | `frontend/nba-research-engine-v2/` |

## Run

```text
cd apps/nba-data/scripts/research_engine_v2_test2
/tmp/momento-nba-venv/bin/python run_pipeline.py

/tmp/momento-nba-venv/bin/python api_server.py   # :8788
cd frontend/nba-research-engine-v2 && npm install && npm run dev
```

sklearn is authorized for this engine only (`requirements-research.txt`).
GPE V2 remains no-sklearn.

Spec deliverable: [`NBA_80_40_ENGINE_V2_TEST_2_REPORT.md`](NBA_80_40_ENGINE_V2_TEST_2_REPORT.md)
— **Verdict B / NO FILTER**. Frozen 80/40 unchanged.
