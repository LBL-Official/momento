# SuperASI — EV decomposition

In-production EV is not a single number. SuperASI splits it into
terminal efficiency, path efficiency, and stop-path realization.
Candle path, not fills. Does not change the live 80/40 rule.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER 40 ≠ PROVEN FILL
```

## 1. Locked identities

Trigger FIRST_q. K is the triggering quote, not a fill.

```
p   = P(W | FIRST_q)
α   = p − K
s_W = P(¬T40 | W, FIRST_q)
s_L = P(¬T40 | L, FIRST_q)
S   = P(¬T40 | FIRST_q) = p · s_W + (1 − p) · s_L
P(W ∩ ¬T40 | FIRST_q) = p · s_W
```

These terms are not independent edges. Documented in
`research/first75_terminal_path_decomp/TERMINAL_PATH_REPORT.md`
and `research/first80_alpha_decomposition_v1/METHODOLOGY.md`.

On asked-six FIRST80, s_L = 0, so S = p · s_W = 883/1182.

## 2. Two different “win rates”

| Object | Count | Rate | Role |
|---|---:|---:|---|
| Terminal P(W) | 991/1182 | 83.84% | settlement yes |
| Path S = P(¬T40) | 883/1182 | 74.70% | **80/40 rule wins** |
| W∩T40 | 108 | 9.14% | settled yes, 80/40 loser |

In-production EV uses **S**, not terminal p. Do not plug 83.84%
into +20/−40.

## 3. In-production EV (ledger)

```
EV_ledger = 20S − 40(1 − S) = 60S − 40
```

S = 883/1182 ⇒ **EV_ledger = 950/197 = 4.82¢**.
Breakeven S at L=40 is 40/60 = 66.67%.
Breakeven L at this S is 59.06¢ (exit ≈ 20.94¢).

This is the labeled 80/40 book. It assumes every T40 exits at 40.
That assumption is the research object SuperASI removes next.

## 4. Stop-path realization (enhancement)

```
L_x = E[80 − exit_x | T40]
EV_x = 20S − L_x (1 − S)
```

exit_x is a **candle** measurement, not a proven Kalshi fill.

| Mix x | n | Mean exit | Mean L | EV at S=883/1182 |
|---|---:|---:|---:|---:|
| Ledger 40 | 299 | 40 | 40 | **4.82¢** |
| First T40 close | 299 | 10318/299 = 34.51 | 45.49 | **3.43¢** |
| Planning +2.5¢ | 299 | 30.82 | 49.18 | **+2.50¢** |
| 5m min after T40 | 298 | 7291/298 = 24.47 | 55.53 | **0.89¢** |

Exact 40 on first tradable ≤40 close: **54/299**.
First close already <40: **245/299**.
First close ≤35: **128/299**.
FAST_GAP (prior >40, through 40, drop ≥10): **181/299**.

Keep the 40 **rule**. Do not move the stop to 45. Do not treat 40
as an executable resting sell while the bid is still 50–60.

## 5. Path to the stop (±5m)

Source: `research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv`.

| Offset | n | Sum bid | Mean close |
|---:|---:|---:|---:|
| -5 | 299 | 18262 | **61.1** |
| -1 | 299 | 14663 | **49.0** |
| +0 | 299 | 10318 | **34.5** |
| +5 | 297 | 9724 | **32.7** |

Trades with a 38–40 close in the five minutes **before** T40:
**1/299**. The stop arrives as a one-minute
gap from the high 40s. A 40/45 maker ask does not sit on that path.

## 6. What a SuperASI enhancement is allowed to change

Allowed in research:

- which EV mix is used for planning (ledger / T40-close / +2.5¢)
- how ROLLER +EV is reported after terminal × path × stop-path
- documentation of why the ledger overstates executable EV

Not allowed:

- live liquidation style
- FIRST80 / T40 / FIRST01 parameter retune
- treating any mix as a proven fill

**LIVE DEPLOYMENT: NOT AUTHORIZED**
