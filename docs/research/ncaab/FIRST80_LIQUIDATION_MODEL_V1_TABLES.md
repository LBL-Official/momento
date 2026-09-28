# FIRST80_LIQUIDATION_MODEL_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
40¢ = SIGNAL TO LIQUIDATE
40¢ ≠ GUARANTEED FILL PRICE
```

The 80→40 path exists on NBA and NCAAB candles. The remaining object is
not “can we sell at exactly 40?” It is:

```text
P(P_fill | market crosses 40)
```

and the EV question:

```text
How bad can average liquidation become before the path edge disappears?
```

## What this model is allowed to use

Observed / estimated from 1-minute TOB candles:

- `P_trigger` proxy: previous minute `yes_bid_close`
- `R_candle`: stop-minute bid high−low
- `ΔP` proxy: previous close → this close
- `S` proxy: stop-minute `ask_close − bid_close`

Unavailable (not invented):

- Historical L2 / `L` queue liquidity
- Intra-minute matching
- Detection / decision / RTT timestamps

Status labels: `ESTIMATED` (candle proxy), `SCENARIO` (defined rule),
`SIMULATED` (latency interpolation), `UNAVAILABLE` (L2).

## Detection vs matching

```text
cross 40 → detect → decide → transmit → MATCH / consume liquidity → fill
```

Fast ①–③ (as on the MLB desk) does not solve ④. If the book prints
42→41→40→38→35→30 inside one minute, an instant bot still cannot
guarantee 40.00.

## Book (unchanged path counts)

| | NCAAB | NBA |
|---|---:|---:|
| Settled FIRST-80 | 4,099 | 1,230 |
| Survivors | 2,998 | 910 |
| Close-40 stops | 1,099 | 320 |
| Survival | 73.14% | 73.98% |
| **EV = 0 at avg fill** | **25.4413¢** | **23.125¢** |

Wins still +20¢. Only stop legs are re-priced. Fees UNRESOLVED.

## NCAAB liquidation models (1,099 stops)

| Model | Status | E[P_fill] | E[L\|Stop] | EV ¢ |
|---|---|---:|---:|---:|
| A ideal 40 | SCENARIO | 40.0 | 40.0 | 3.9034 |
| B bid close | ESTIMATED | 33.1465 | 46.8535 | 2.0659 |
| C bid low | ESTIMATED | 28.6779 | 51.3221 | 0.8678 |
| D gap-aware | SCENARIO | 31.6988 | 48.3012 | 1.6777 |

Model B close-path distribution (NCAAB):

- P(fill ≥ 38) = 0.3722
- P(35–38) = 0.2284
- P(30–35) = 0.1929
- P(< 30) = 0.2066

## NBA liquidation models (320 stops)

| Model | Status | E[P_fill] | EV ¢ |
|---|---|---:|---:|
| B bid close | ESTIMATED | 34.125 | 2.8618 |
| C bid low | ESTIMATED | 30.6 | 1.9447 |

## Viability frontier

Hold the observed survival rates fixed. Vary only average stop fill.

| Avg stop fill | NCAAB EV ¢ | NBA EV ¢ |
|---:|---:|---:|
| 40.0 | 3.9034 | 4.3902 |
| 38.0 | 3.3672 | 3.8699 |
| 35.0 | 2.5628 | 3.0894 |
| 32.0 | 1.7585 | 2.3089 |
| 30.0 | 1.2222 | 1.7886 |
| 28.0 | 0.686 | 1.2683 |
| 25.5 | 0.0157 | 0.6179 |
| 25.0 | -0.1183 | 0.4878 |
| 23.0 | -0.6545 | -0.0325 |
| 20.0 | -1.4589 | -0.813 |

The strategy does not need perfect 40¢ fills. It needs average liquidation
**above ~25.4413¢ (NCAAB)** / **~23.125¢ (NBA)** before fees.

## Latency surface

Model E interpolates from first-touch 40 (or gap high) to bid_low over 60s.
That is a **SIMULATED** stress, not a reconstructed clock.

Live/paper next season should record T0…T5 and VWAP exit so
`P(P_fill | 80→40 liquidation)` becomes empirical.

## Non-goals

- Do not write 40.00 into live NBA/NCAAB execution as a fill.
- Do not invent L2 from candles.
- Do not change MLB FIRST01 50% VWAP stop semantics.
- Do not promote this model to Risk/Execution.

Code: `apps/ncaab-data/scripts/first80_liquidation_model_v1.py`  
Artifacts: `.../warehouse/derived/{ncaab,nba}/first80_liquidation_model_v1/`
