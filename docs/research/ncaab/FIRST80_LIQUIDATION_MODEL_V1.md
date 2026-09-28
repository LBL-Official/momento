# FIRST80_LIQUIDATION_MODEL_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
40¢ = SIGNAL TO LIQUIDATE
40¢ ≠ GUARANTEED FILL PRICE
```

The 80→40 path exists and replicates on NBA and NCAAB candles. The
remaining research object is not a fake stop price:

```text
ExitPrice = 40     ← do not model this as execution
```

It is an execution-slippage distribution:

```text
P(P_fill | P_trigger, V_market, R_candle, ΔP, S, L)
```

and the EV question:

```text
How bad can average liquidation become before the path edge disappears?
```

## Conceptual rule

| | Meaning |
|---|---|
| 40¢ | Risk-trigger threshold. The market has crossed the stop. |
| Fill | Whatever the book actually pays after detection, decision, transmission, and matching. |
| Model A | Impossible ideal. Upper bound only. |
| Models B–D | Candle-structure proxies. ESTIMATED / SCENARIO. |
| Model E | Latency stress. SIMULATED, not observed. |

Wins stay **+20¢**. Only the stop leg is re-priced. Fees remain UNRESOLVED.
Do not change live FIRST01, Risk, or Execution. Do not invent L2.

## Detection versus matching

```text
MARKET EVENT
     │
     ▼
Price crosses 40
     │
     ▼
① Detection latency      bot / API notices
     │
     ▼
② Decision latency       stop logic fires
     │
     ▼
③ Order transmission     order reaches exchange
     │
     ▼
④ Matching latency       available liquidity is consumed
     │
     ▼
ACTUAL FILL
```

MLB paper/live execution can make ①+②+③ fast. That is valuable. It does
not solve ④. If the book prints `42 → 41 → 40 → 38 → 35 → 30` inside a
short window, an instant bot still cannot guarantee 40.00.

Candle data cannot reconstruct ①–④. Historical L2 (`L`) is UNAVAILABLE.

Conditioning variables that *can* be proxied from 1-minute TOB:

| Symbol | Proxy | Status |
|---|---|---|
| `P_trigger` | previous minute `yes_bid_close` | ESTIMATED |
| `R_candle` | stop-minute bid high − low | ESTIMATED |
| `ΔP` | previous close → this close | ESTIMATED |
| `S` | stop-minute `ask_close − bid_close` | ESTIMATED |
| `V_market` | not separately estimated in v1 (range / gap flags used) | PARTIAL |
| `L` | queue / depth | UNAVAILABLE |

## Book (path counts unchanged)

| | NCAAB | NBA |
|---|---:|---:|
| Settled FIRST-80 | 4,099 | 1,230 |
| Survivors (no close-40, won) | 2,998 | 910 |
| Close-40 stops | 1,099 | 320 |
| Leak (`LOSS_NO_STOP`) | 2 | 0 |
| Survival | 73.14% | 73.98% |

EV identity (leak P&L = 0):

```text
EV = (N_win × 20 − N_stop × (80 − E[P_fill])) / N
```

Gross EV is zero when:

```text
E[P_fill]* = 80 − (N_win × 20) / N_stop
           = 25.4413¢  NCAAB
           = 23.1250¢  NBA
```

The strategy does not need perfect 40¢ fills. It needs average
liquidation **above that threshold** before fees.

## Models

### A — Impossible ideal (SCENARIO)

`P_fill = 40` on every stop. Not executable. Upper bound.

### B — Close model (ESTIMATED)

`P_fill =` stop-minute `yes_bid_close`, clamped to `[0, 40]`.
Candle *end*, not a match.

### C — Conservative low (ESTIMATED)

`P_fill =` stop-minute `yes_bid_low`, clamped to `[0, 40]`.
Worst print visible in that minute. Still not a fill.

### D — Gap-aware (SCENARIO)

If previous bid close `> 50¢` and this close `≤ 40¢`, use Model C
(crash minute). Otherwise Model B.

### E — Latency stress surface (SIMULATED)

Delays: 0, 100, 250, 500, 1000, 2000, 5000 ms.

Two collapse horizons, both labeled SIMULATED:

- **E60** — linear from first-touch 40 (or gap `bid_high`) to `bid_low`
  over 60 seconds. Optimistic if the crash is faster than the candle.
- **E5** — same interpolation over 5 seconds. Stresses “the wick happens
  in five seconds.” At 5,000 ms this coincides with Model C.

0 ms on a straddling minute is a first-touch-at-40 scenario. 0 ms on a
minute already entirely below 40 uses `bid_high` (the best print still
visible). Neither is an observed millisecond path.

## NCAAB results (1,099 reconstructed stop minutes)

| Model | Status | E[P_fill] | E[L \| Stop] | P(≥38) | P(35–38) | P(30–35) | P(<30) | EV ¢ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A ideal 40 | SCENARIO | 40.00 | 40.00 | 1.000 | 0 | 0 | 0 | **+3.90** |
| B bid close | ESTIMATED | 33.15 | 46.85 | 0.372 | 0.228 | 0.193 | 0.207 | **+2.07** |
| C bid low | ESTIMATED | 28.68 | 51.32 | 0.158 | 0.207 | 0.238 | 0.398 | **+0.87** |
| D gap-aware | SCENARIO | 31.70 | 48.30 | 0.312 | 0.221 | 0.197 | 0.270 | **+1.68** |

Model B is the closest analogue to “what the candle said after the
minute finished.” Average exit **33.15¢**, not 40. Loss widens from
40¢ to 46.85¢. EV falls from +3.90¢ to +2.07¢ and remains positive.

Model C is the pessimistic candle print. Average exit **28.68¢**. EV
is still positive (+0.87¢) but thin, and fees are not in the number.

Conditional structure (not a fill model):

- Gap minutes (prior close > 50, this close ≤ 40): **326 / 1,099**
- Model B given gap: E[P_fill] = 32.85¢ (vs 33.27¢ non-gap)
- Model C given gap: 27.97¢
- Model C given bid range > 10¢ (861 minutes): **26.77¢**

Wide minutes, not prior-close gaps, are the worse candle state.

## NBA results (320 reconstructed stop minutes)

| Model | Status | E[P_fill] | E[L \| Stop] | P(≥38) | P(35–38) | P(30–35) | P(<30) | EV ¢ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A ideal 40 | SCENARIO | 40.00 | 40.00 | 1.000 | 0 | 0 | 0 | **+4.39** |
| B bid close | ESTIMATED | 34.13 | 45.88 | 0.422 | 0.216 | 0.191 | 0.172 | **+2.86** |
| C bid low | ESTIMATED | 30.60 | 49.40 | 0.244 | 0.200 | 0.225 | 0.331 | **+1.94** |
| D gap-aware | SCENARIO | 32.60 | 47.40 | 0.347 | 0.209 | 0.222 | 0.222 | **+2.46** |

NBA stop minutes are slightly cleaner than NCAAB on the same proxies
(higher close, higher low, fewer crash buckets). Combined with the
higher 73.98% survival, NBA’s zero-crossing fill is lower (23.13¢).

Gap minutes: **105 / 320**. Model C given range > 10¢ (244 minutes): 28.42¢.

## Viability frontier

Hold observed survival fixed. Vary only average stop fill.

| Avg stop fill | NCAAB EV ¢ | NBA EV ¢ | Reading |
|---:|---:|---:|---|
| 40¢ | +3.90 | +4.39 | Ideal / Model A |
| 38¢ | +3.37 | +3.87 | Strong |
| 35¢ | +2.56 | +3.09 | Positive |
| 33¢ | ~+2.03 | ~+2.57 | Near Model B |
| 32¢ | +1.76 | +2.31 | Positive |
| 30¢ | +1.22 | +1.79 | Small–moderate |
| 28.7¢ | +0.87 | +1.45 | NCAAB Model C |
| 25.5¢ | +0.02 | +0.62 | NCAAB ≈ breakeven |
| 25.0¢ | −0.12 | +0.49 | NCAAB negative |
| 23.1¢ | −0.63 | 0.00 | NBA breakeven |
| 20¢ | −1.46 | −0.81 | Negative |

Exact NCAAB zero: **25.4413¢**. Exact NBA zero: **23.1250¢**. Before fees.

## Latency surface (SIMULATED)

E60 barely moves in a few seconds because 5 s is 8% of a 60 s candle.
That is why a 5-second crash horizon (E5) is the useful stress.

| Delay | NCAAB E60 fill / EV | NCAAB E5 fill / EV | NBA E5 fill / EV |
|---:|---:|---:|---:|
| 0 ms | 39.38 / +3.74 | 39.38 / +3.74 | 39.93 / +4.37 |
| 100 ms | 39.36 / +3.73 | 39.17 / +3.68 | 39.74 / +4.32 |
| 250 ms | 39.34 / +3.73 | 38.85 / +3.59 | 39.46 / +4.25 |
| 500 ms | 39.29 / +3.71 | 38.31 / +3.45 | 38.99 / +4.13 |
| 1 s | 39.20 / +3.69 | 37.24 / +3.16 | 38.06 / +3.89 |
| 2 s | 39.03 / +3.64 | 35.10 / +2.59 | 36.20 / +3.40 |
| 5 s | 38.49 / +3.50 | 28.68 / +0.87 | 30.60 / +1.94 |

Read this as a **scenario**, not a clock. If ①+②+③ stay well under a
second *and* the book has not already gapped through 40, these surfaces
stay far above the 25.4¢ / 23.1¢ viability line. If the crash realizes
the full minute-low in ~5 s and the bot is late, NCAAB EV compresses to
Model C (+0.87¢). Matching quality, not RTT, is the binding risk.

E60 0 ms is already 39.38¢ on NCAAB, not 40.00, because 63 minutes
(5.7%) gapped entirely below 40. Instant reaction still cannot buy a
40 print that is not there.

## What this does *not* say

- It does not say a live NBA/NCAAB bot will fill at 33¢ or 28¢.
- It does not reconstruct queue position or IOC slippage.
- It does not include fees, maker rebates, or partial fills.
- It does not authorize live NBA or NCAAB trading.
- It does not change MLB FIRST01 50% VWAP stop semantics.

Entry at 80¢ maker remains a separate fill question. It is not the
primary weakness isolated here. Liquidation at the 40 trigger is.

## Next season: empirical liquidation distribution

Candles cannot produce `P(P_fill | 80→40)`. Live or paper trades can.

Record, for every stop:

| Field | Meaning |
|---|---|
| T0 | market crosses trigger |
| T1 | bot detects |
| T2 | order submitted |
| T3 | exchange acknowledges |
| T4 | first partial fill |
| T5 | final fill |
| P0 | trigger price |
| P_fill | volume-weighted average exit |

That becomes the real object:

```text
P(P_fill | 80→40 liquidation)
```

Status of that experiment: **NOT_RUN**. Do not invent a live pipeline
in this model. Do not arm NBA/NCAAB execution from these tables.

## Non-goals

- Do not write 40.00 into live NBA/NCAAB execution as a fill.
- Do not invent L2 from candles.
- Do not start W9 or retune FIRST01.
- Do not promote this model into the Risk Decision Engine.

## Artifacts

- Code: `apps/ncaab-data/scripts/first80_liquidation_model_v1.py`
- NCAAB: `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/derived/ncaab/first80_liquidation_model_v1/`
- NBA: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_liquidation_model_v1/`
- Generated tables: `docs/research/ncaab/FIRST80_LIQUIDATION_MODEL_V1_TABLES.md`

NCAAB stop candles reused from `first80_execution_audit/stop_candle_inspect/stop_candles.json`.
NBA stop candles reconstructed from the frozen FIRST-80 candidates (320/320 found).
