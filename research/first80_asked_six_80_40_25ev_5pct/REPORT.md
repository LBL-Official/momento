# 5% stake · +2.5¢ EV · 10 bets/week · 22 weeks

```
RESEARCH ONLY
PLANNING EV +2.5¢ — NOT A FILL
LIVE EXECUTION = FALSE
40 STOP UNCHANGED
DO NOT CHANGE LIVE FIRST01
```

Generated: `2026-09-10T07:06:29.261575+00:00`

## Setup

- Start **$20,000**
- Stake **5%** of bankroll at 80¢. `qty = floor(0.05 × B / 80)`
- A −49¢ stop then costs about **3.1%** of bankroll, not 5%
- 10 bets/week × 22 weeks = **220** trades (~5 months)
- Planning EV **+2.50¢**/contract (883 × +20 and a −49/−50 stop bag)
- p = 883/1182. Not a Kalshi fill.

Closed-form mean if every trade earns exactly 2.5¢: **$28,197** (41.0% on the fraction).

## Per-bet compound (resize every trade)

| | |
|---|---:|
| Median end | **$26,786** |
| Mean end | $28,245 |
| P5 / P95 | $17,214 / $43,121 |
| CAGR p50 | 99.5% |
| P(≥50% return) | 37.5% |
| P(lose money) | 14.45% |
| P(DD>20%) | 50.2% |
| P(DD>30%) | 13.0% |
| DD p50 / p95 / p99 | 20.1% / 36.0% / 44.0% |

## Week-start compound (same size for the 10 bets, then resize)

| | |
|---|---:|
| Median end | **$27,152** |
| Mean end | $28,163 |
| P5 / P95 | $17,072 / $42,652 |
| CAGR p50 | 106.0% |
| P(≥50% return) | 36.7% |
| P(lose money) | 14.16% |
| P(DD>20%) | 30.0% |
| DD p50 / p95 / p99 | 15.3% / 32.8% / 41.7% |

This is slower than the clean −40¢ 5% grid (~$36k median) because
the working EV is +2.5¢, not +4.82¢.

## Does not

- Change live FIRST01.
- Prove a 40¢ fill.
- Move the stop to 45.

