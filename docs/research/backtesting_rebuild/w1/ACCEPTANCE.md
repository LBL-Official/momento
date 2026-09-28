# CTO-W1 ACCEPTANCE

W1 is **not** closed because the implementation agent wrote COMPLETE or because tests are green.

**Binding bar:** [../W1_ACCEPTANCE_CRITERIA.md](../W1_ACCEPTANCE_CRITERIA.md)  
**Package the CTO will sign:** [../W1_ACCEPTANCE_PACKAGE.md](../W1_ACCEPTANCE_PACKAGE.md) (currently **NOT_AUDITED**)

Closing standard:

```text
code correctness
+ data integrity
+ provenance
+ observability
+ architectural compliance
+ reproducibility
```

## Ten criteria (summary)

1. Data-Real immutable; gzip byte-preserved; checksums valid  
2. Provenance: where / when / what / what can be observed  
3. Observability explicit — candles are not L2  
4. FLAG-003: CandleEnd keeps period-end timestamp; `received_at` ≠ exchange time  
5. Coverage honesty: 2026-06-18…30, 13 days, 172 games, 344 contracts; missing 2025, PBP, L2, proven open  
6. One unambiguous step ledger — no auto-complete  
7. fmt / check / test / clippy actually run + W1 integrity tests  
8. Reproducible documentation package  
9. Google: local artifacts real; `GOOGLE_PUBLISH_PENDING` OK; no fake publish  
10. No live / risk / execution / strategy / config / transport / Data-Real changes  

Any FAIL keeps W1 open. **CTO makes the final call.**

After ACCEPTED / CLOSED, CTO may authorize **CTO-W3 Kalshi market reconstruction**.
