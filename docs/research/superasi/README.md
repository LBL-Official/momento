# SuperASI

Rename of **Lebronner**. Research-only alpha decomposition of
positive-EV strategies generated from ROLLER.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER 40 ≠ PROVEN FILL
TERMINAL ALPHA ≠ PATH ALPHA
PATH SURVIVAL ≠ INDEPENDENT EDGE
DO NOT CHANGE LIVE FIRST01 / 80/81/83/89
DO NOT START W9
```

Alpha decomposition of positive-EV strategies generated from ROLLER. Enhancements attach to in-production EV in research by decomposing EV and deconstructing terminal efficiency and path efficiency. SuperASI does not submit orders.

**Status:** `SPEC_ONLY`. Implementation authorized: False. Live authorized: False.

Lebronner remains the FIRST75 named-archive label
(`research/lebronner/`). SuperASI is the successor program that
consumes ROLLER +EV objects and attaches stop-path realization to
**in-production EV** without changing the live 80/40 rule.

## What SuperASI does

1. Take a ROLLER-generated +EV strategy (first object: asked-six
   FIRST80 80/40).
2. Decompose EV. Do not treat a single ledger number as alpha.
3. Deconstruct **terminal efficiency** — P(W | trigger) vs K.
4. Deconstruct **path efficiency** — s_W, s_L, four-cell, S.
5. Deconstruct **stop-path realization** — E[exit | T40], the
   ±5m window, printed-40 vs blow-through.
6. Publish a research planning EV that haircuts the ledger.

## What SuperASI does not do

- Submit, approve, or route orders. Strategy proposes; Risk
  approves; Execution executes.
- Change live FIRST01 / 80/81/83/89 or the 40 stop **rule**.
- Treat candle path as a Kalshi fill.
- Hunt a profitable subset. Do not start W9.
- Import Lebronner −35¢ as an 80→40 exit.
- Park a 40/45 sell at entry, or buy the opponent at 60 at entry.

## First object — asked-six FIRST80 80/40

- N = **1182**. Rule survivors S = **883/1182** (74.70%).
- Terminal P(W) = **991/1182**. The 108 W∩T40 are 80/40 losers.
- Ledger EV at −40¢ = **4.82¢**.
- T40-close EV (mean first close 10318/299¢) = **3.43¢**.
- Planning EV = **+2.50¢** ⇒ implied mean stop loss **49.2¢**.

Full identities: `research/superasi/EV_DECOMPOSITION.md`.
Named numbers: `research/superasi/REPORT.md`.

## Documented layers (do not re-derive)

| Layer | Object | Already documented |
|---|---|---|
| Terminal | P(W) − K | `research/first75_terminal_path_decomp/` |
| Path | four-cell, s_W, s_L | `research/first80_alpha_decomposition_v1/` |
| FIRST75 archive | named −0.37¢ | `research/lebronner/` |
| Stop-path | T40 close, ±5m | `research/first80_asked_six_*` |
| In-production EV | ledger vs haircut | this directory |

Alpha-decomp v1 classification on the NBA audit book remains
`A_TERMINAL_CALIBRATION_ONLY`. SuperASI does not reopen that as
an independent path edge.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
