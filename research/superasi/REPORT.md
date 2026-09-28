# SuperASI

Successor name for **Lebronner**. Alpha decomposition of +EV
strategies generated from ROLLER. First object: asked-six FIRST80
in-production 80/40 EV, split into terminal, path, and stop-path.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER 40 ≠ PROVEN FILL
SPEC_ONLY — IMPLEMENTATION NOT AUTHORIZED
```

Does not change live FIRST01 / 80/81/83/89. Does not retune
FIRST75, FIRST80, or T40. Reconstructs from locked integers.

Lebronner FIRST75 archive (named −0.37¢, p=73% held-path S):
`research/lebronner/REPORT.md`. That −35¢ stop is still not an
80→40 exit.

## 1. Rename

| | |
|---|---|
| Legacy | Lebronner |
| Current | SuperASI |
| Status | `SPEC_ONLY` |
| Live | FALSE |
| Consumes | ROLLER +EV strategy objects |
| First production-EV object | asked-six FIRST80 80/40 |

## 2. Asked-six FIRST80 four-cell

N = **1182**. One observation per FIRST80 event.

| | ¬T40 | T40 | Terminal |
|---|---:|---:|---:|
| W | **883** | 108 | 83.8409% |
| L | 0 | 191 | 16.1591% |
| | 74.7039% | 25.2961% | 100% |

p = **991/1182** = 83.84%. α₈₀ = **+3.84 pp**.
s_W = 883/991. s_L = 0. S = **883/1182** = 74.70%.

In-production 80/40 win rate is S = P(¬T40) = 883/1182, not terminal P(W) = 991/1182. The 108 W∩T40 settled YES after the stop and are 80/40 losers.

## 3. In-production EV vs research mixes

| Mix | Mean stop L | EV |
|---|---:|---:|
| Ledger 80/40 | 40¢ | **+4.82¢** |
| First T40 close | 45.49¢ | **+3.43¢** |
| Planning (user) | 49.18¢ | **+2.50¢** |
| 5m min after T40 | 55.53¢ | **+0.89¢** |

Planning +2.5¢ is the SuperASI research haircut on in-production
EV. It is not a live retune and not a proven fill.

## 4. Stop-path (299 T40 trades)

- Exact 40 first print: **54/299**.
- First print <40: **245/299**.
- First print ≤35: **128/299**.
- FAST_GAP: **181/299**.
- Mean T40 close: **34.51¢** (sum 10318).
- Mean bid at t−1: **49.0¢**.
- 38–40 close in the five minutes before T40: **1/299**.

CSV: `research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv`.

## 5. Layers

Identities: `research/superasi/EV_DECOMPOSITION.md`.
Program home: `research/superasi/README.md`.
FIRST75 named cases stay on `research/lebronner/`.

## 6. What this is not

- Not a live order, fill, or realized P&L.
- Not authorization to flatten at 45.
- Not a hedge. Opponent-at-60 at entry is not a lock.
- Not an independent FIRST80 path edge (v1 remains A).
- Not MLB FIRST01. Not W9.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
