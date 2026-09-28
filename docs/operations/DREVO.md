# Drevo — Dynamic Risk Engine

Legacy alias: DRE. Same host `:5191`. `/dre/*` remains; `/drevo/*` is an alias.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
POLICY_UNRESOLVED ≠ ACCEPT
```

```text
browser :5191
  → ROLLER :8791
  → /dre and /drevo
    → /dre/health|positions*
    → /dre/decision/{trade_id}
```

Does not submit. Does not invent ACCEPT. Choosin 936 ≠ Austin 604.
How-to for the hold-reason observation surface remains `docs/operations/DRE.md`.
