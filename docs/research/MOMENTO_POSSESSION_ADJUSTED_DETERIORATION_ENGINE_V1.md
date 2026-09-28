# MOMENTO — Possession-Adjusted Deterioration Engine V1

**Program:** `MOMENTO_POSSESSION_ADJUSTED_DETERIORATION_ENGINE_V1`  
**Schema:** 1.0.0  
**Created:** 2026-09-03  
**Live execution changed:** FALSE  
**NCAAB:** not implemented (no joinable PBP)

This is a frozen offline state-layer experiment. It does not choose a stop, hedge, or fill rule. It does not modify FIRST01, Risk, live execution, hedge V1–V4, or existing FIRST-80 backtests.

```
CANDLE PATH ≠ ACTUAL FILL
AS-OF JOIN ≠ INTERPOLATION
POSSESSION TIME ≠ WALL CLOCK
GAME CLOCK ≠ timeActual
EXECUTION EVIDENCE: UNOBSERVED
```

Repository audit: `docs/research/PADE_V1_REPOSITORY_AUDIT.md`

---

## Verdict

| Item | Result |
|------|--------|
| TIME ALIGNMENT | **PASS** |
| POSSESSION ENGINE | **PASS** |
| DATA LEAKAGE AUDIT | **PASS** |
| POSSESSION PREDICTIVE VALUE | **INCONCLUSIVE** |
| REMAINING POSSESSIONS MODEL | **WARNING** |
| DRE STATE ARCHITECTURE | **READY FOR V2** |
| EXECUTION EVIDENCE | **UNOBSERVED** |
| LIVE DEPLOYMENT | **NOT AUTHORIZED BY THIS EXPERIMENT** |

**PRIMARY DISCOVERY:** Kalshi 1-minute candles can be defensibly aligned to observed NBA `timeActual` *during the live game*. A trade × possession panel with strict as-of market joins exists. Current price already dominates short-horizon “will it print ≤40 in the next 5 possessions.” Game clock and score add material information for 10¢ deterioration/recovery. Possession-time and velocity add only small OOS increments and do not clear a joint Brier+AUC bar versus game clock.

**PRIMARY LIMITATION:** Market observations are 1-minute candles. Many possessions share one stale print. Remaining-possession estimates are biased (R2 OOS MAE ≈ 31 possessions). Seven FIRST-80 events have no NBA game ID. Fills are unobserved.

**NEXT SCIENTIFIC EXPERIMENT (DRE V2):** State-conditional target deltas on horizons where price is *not* nearly sufficient (settlement, recovery, jump-through), using this panel — not a new stop optimizer.

---

## 1. Can Kalshi 1-minute candles be aligned to NBA PBP?

**Yes, during the game. Grade A for `timeActual`; Grade B for the as-of mapping.**

Primary wall clock is the live CDN field `timeActual` (downloaded 2026-09-03; 1,352 games; 780,137 / 780,137 actions). This is **not** Game Path’s `PERIOD_BOUNDED_LINEAR_GAME_CLOCK` proxy.

Method: last PBP event with `timeActual ≤ candle end_period_ts`, plus next event. No 48-min = 2.5-hour linear map. No interpolation of prices.

Scheduled boxscore `gameTimeUTC` is **not** used as observed tip. Observed tip = first period-start `timeActual`.

In-game candle-to-event gap: median **15.6s**, mean 74s, p90 171s (n=171,342).

The FIRST-80 scan window is `game_date+16h` … `+52h`. Most candles in that window are pre-tip or post-game and are stored as `UNRESOLVED` with `alignment_scope=PRE_TIP|POST_GAME`. They are excluded from GATE E. This is not a mapping failure; the basketball game is not happening then.

---

## 2. Alignment confidence mix

**In-game (GATE E denominator):**

| Confidence | n | % |
|------------|--:|--:|
| HIGH | 105,268 | 61.44 |
| MEDIUM | 42,447 | 24.77 |
| LOW | 22,835 | 13.33 |
| UNRESOLVED | 792 | 0.46 |

HIGH+MEDIUM = **86.21%** → GATE E **PASS**. One game had in-game HIGH+MEDIUM < 50%.

Full scan-window rows: 786,106, of which 615,556 are out-of-game UNRESOLVED (stored, not dropped).

Panel rows used for models: 139,966, all HIGH or MEDIUM, 0 unresolved panel rows, 0 as-of lookaheads.

---

## 3–5. Does possession time improve prediction?

Nested logistic regressions, complete-case, **game-level chronological splits** (TRAIN 503 games / 57,059 rows; VAL 481 / 55,192; OOS 237 / 27,715). Grade **C**.

OOS, selected targets:

| Target | B0 AUC | B2 AUC | M3 AUC | M5 AUC | B2 Brier | M3 Brier |
|--------|-------:|-------:|-------:|-------:|---------:|---------:|
| P(min≤40 within 5 poss) | 0.990 | 0.995 | 0.995 | 0.994 | 0.0289 | 0.0292 |
| P(min≤40 to end) | 0.892 | 0.885 | 0.890 | 0.892 | 0.1391 | 0.1351 |
| P(det≥10 within 5) | 0.796 | 0.849 | 0.852 | 0.856 | 0.1564 | 0.1591 |
| P(rec≥10 within 5) | 0.852 | 0.880 | 0.883 | 0.892 | 0.1336 | 0.1339 |
| P(jump-through 40 proxy) | 0.832 | 0.782 | 0.787 | 0.797 | 0.1937 | 0.1911 |
| P(settle YES) | 0.843 | 0.846 | 0.858 | 0.859 | 0.1611 | 0.1539 |

**Possession vs wall-clock (B1):** game clock (B2) is the first large lift on 5-possession deterioration/recovery. Wall age alone does not.

**Possession vs game clock (M3 vs B2):** no joint OOS Brier+AUC win on the pre-registered headline `P(min≤40 | 5 poss)`. Settlement is the clearest possession-layer gain (AUC 0.846 → 0.858, Brier 0.161 → 0.154).

**Which possession-adjusted variables add value?** Estimated remaining possessions (R2) and `possessions_since_entry` help **terminal settlement**. Velocity/acceleration/staleness (M5) help **5-possession recovery** (AUC 0.880 → 0.892). They do not improve the already-saturated 5-possession 40-cross.

Headline call remains **INCONCLUSIVE**: possession time is not useless, and it is not a dominant new clock for short-horizon 40-cross risk.

---

## 6–7. Velocity and acceleration

Grade **C**, and only when `unique_market_observations ≥ 2`. Identical repeated candles are flagged `velocity_valid=FALSE` and excluded from logistic complete-case (not imputed as zero).

M5 vs M3 OOS:

- Recovery ≥10¢ in 5 poss: AUC 0.883 → 0.892, Brier 0.134 → 0.127
- Jump-through 40 proxy: AUC 0.787 → 0.797
- 40-cross in 5 poss: no improvement

Velocity is a **weak incremental** signal for recovery/jumps, not a standalone deterioration engine.

---

## 8. Remaining possessions

Grade **B** estimates; actual remaining count is an evaluation label only.

| Split | R2 MAE | R2 bias | R1 MAE |
|-------|-------:|--------:|-------:|
| TRAIN | 30.3 | −29.2 | 46.4 |
| OOS | 30.8 | −30.2 | 47.8 |

R2 (current-game pace) beats R1/R3 but **under-counts** remaining possessions by ~30. GATE: **WARNING**. Still usable as a noisy feature (it is the M3 settlement increment). Do not treat R2 as a known clock.

---

## 9–11. Dangerous vs recoverable deterioration

Empirical HIGH+MEDIUM states, mixed splits for the severe bucket (descriptive, Grade A counts):

- States with deterioration ≥20¢ from the 80¢ entry: **16,501**
- Of those, later recover ≥10¢ before game end: **57.6%**
- Of those, settle YES: **37.0%**

So a 20¢ drawdown is **not** absorbing. Path risk and terminal risk are different objects (V1/V2 finding, now restated on possession rows).

Short-horizon 40-cross is almost a function of *current price* (AUC 0.99). The dangerous *states* for terminal loss are those that are already cheap **and** still settle NO (37% settle after ≥20¢ drawdown). That is not a stop recommendation.

---

## 12. Largest data limitations

1. One-minute candles; possessions often share one as-of print (`market_age_seconds` is first-class for a reason).
2. Seven unmatched FIRST-80 events (no invented NBA IDs). 1,221 / 1,230 trades produced a panel.
3. Live vs V3 action counts differ; possession engine is live-schema only.
4. Mean 206 possessions/game is slightly high vs textbook ~200 — FT trips and jump-ball edges remain ambiguous (5 ambiguous possessions, 0.002%).
5. R2 remaining-possessions bias.
6. NCAAB has no joinable PBP.
7. No L2, no IOC, no maker fill.

---

## 13. Evidence grades for conclusions

| Claim | Grade |
|-------|-------|
| `timeActual` present on live PBP actions | **A** |
| In-game as-of candle mapping + confidence mix | **B** |
| Possession sequence from live PBP | **A/B** (5 ambiguous) |
| As-of A1 bid at a possession | **A** (stale if age large) |
| Nested model AUC/Brier | **C** |
| Remaining possessions R1/R2/R3 | **B** (biased) |
| Jump-through | **B** observed candle proxy, **not** a fill |
| Hold PnL ±20/−80 | theoretical at 80¢ entry proxy |
| IOC / maker fill | **D / UNOBSERVED** |

---

## 14. Ready for DRE V2?

**PARTIAL-to-ready as a state layer. Not ready as a trading policy.**

The architecture required by the thesis exists:

1. Three clocks preserved (wall / game / possession)
2. Observed `timeActual` alignment with an explicit gate
3. Possession engine with ambiguity flags
4. Trade × possession panel, as-of only
5. Leakage audit + game-level OOS
6. Nested baselines

DRE V2 should estimate **state-conditional target deltas** (especially settlement and recovery), not retune 80/40. Consequence-weighted possession time is still forbidden until raw state value is clearer on non-saturated targets.

---

## Gates

| Gate | Status | Notes |
|------|--------|-------|
| A FIRST-80 | PASS | 1230 / 910 / 320 / 0 |
| B NBA IDs | PASS | 1223 / 1230 matched |
| C PBP live | PASS | 1223 / 1223 retrieved |
| D possessions | PASS | 252,138; 0.002% ambiguous |
| E alignment | PASS | 86.2% HIGH+MEDIUM in-game |
| F market leak | PASS | 0 future candles in state |
| G game leak | PASS | future poss count not a feature |
| H split isolation | PASS | no game in two splits |

---

## How to rerun

```
/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/pade_v1.py
```

Outputs: `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`

Dashboard: `frontend/pade-v1` on http://127.0.0.1:5183/
