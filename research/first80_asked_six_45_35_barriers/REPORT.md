# Asked-six 45¢ / 35¢ barrier counts

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
DO NOT RETUNE FIRST80 FROM THIS TABLE
```

Generated: `2026-09-10T06:57:10.680272+00:00`

## Universe

- n = **1182** FIRST80 asked-six trades
- win_80_40 = **883** (never printed 40)
- STOP_40 = **299** (printed ≤40)
- T45 = first later tradable close ≤45. T40 ⇒ T45.
- T35 = first later tradable close ≤35. T35 ⇒ T40.

## 45¢ — early level above the stop

- Touched 45: **322** / 1182
- Of those, then lost (went to 40): **299** (92.9%, Wilson 89.5–95.2)
- Of those, survived (never printed 40): **23** (7.1%, Wilson 4.8–10.5)

Every one of the 299 losers touched 45, because ≤40 is ≤45.
The survivors at 45 are winners who dipped into 41–45 and came back.

### Did a 45 print exist before 40?

- First ≤45 close was still **41–45**: **169**. Then lost: **146** (86.4%). Then survived: **23** (13.6%).
- First ≤45 close was already **≤40**: **153**. No separate 45 print — 45 and 40 arrived on the same bar.

If you flatten at a *separate* 45 print, you exit some trades that
would have survived, and you also get out before some 40s. You do
not get a 45 print on the same-bar blow-throughs.

## 35¢ — continuation below the stop

- Touched 35: **277** (all of these already printed 40)
- Of the 299 losers, continued to 35: **277** (92.6%)
- Of the 299 losers, never printed 35: **22** (7.4%) — this is “survived 35”
- Of the 299, first 40-print was already ≤35: **128** (42.8%) — blew through 40 and 35 together

Among the 277 who printed 35:
- Later settled YES: **86** (31.0%) — recovered after 35; still a 40-stop on 80/40
- Settled NO: **191** (69.0%)

## By sport

| Sport | n | T45 | P(T40\|T45) | P(survive\|T45) | P(T35\|T40) | P(never 35\|T40) |
|---|---:|---:|---:|---:|---:|---:|
| NBA | 604 | 167 | 92.2% | 7.8% | 90.3% | 9.7% |
| WNBA | 246 | 66 | 95.5% | 4.5% | 98.4% | 1.6% |
| NCAAB | 332 | 89 | 92.1% | 7.9% | 92.7% | 7.3% |

## Exit reading (not a retune)

- **45** is a pre-stop warning. P(go to 40 | touch 45) is the cost of
  staying. P(survive | touch 45) is the winners you would sell early.
- **35** is a post-stop chase level. Most 40s that blow through get here.
  Never-35 is the group where a 40-area print was the path low-ish close.
- None of this is a fill. Do not change live FIRST01.

