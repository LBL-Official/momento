# Positman — Position Management compositor

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
```

```text
browser :5194
  → ROLLER research API :8791
  → /positman
    → /positman/health|sources
    → /positman/state/{trade_id}
    → GET|POST /positman/plan
    → /positman/trace/{trace_id}
```

Does not submit. Systimo owns the hashed transition audit.
Drevo consumes the plan. Jump reads `POSITMAN_PLAN`.
