# Frozen 80/40 baseline (do not rebuild)

V3 **imports** `nba_80_40_execution_audit.py`. It does not fork first-80.

If counts do not match, the pipeline exits 1.

| Quantity | Count |
| ---: | ---: |
| Games | 1,362 |
| First-80 (settled) | 1,230 |
| Survive close-path 40 | 910 |
| Hit close-path 40 | 320 |

```text
q_unconditional = 26.0163%
EV_gross        = 1 − 3q ≈ +0.2195 R
breakeven q     = 33.3333%
```

Primary event `Y_40_CLOSE`: first subsequent completed candle after
`ENTRY_DECISION_TIME` with tradable `yes_bid_close ≤ 4000`.

Secondary `Y_40_WICK` stored separately. V3 risk-set exit uses close-path only.

Survival object: time from entry to close-path 40, or censoring at last
alive candle / contract close.
