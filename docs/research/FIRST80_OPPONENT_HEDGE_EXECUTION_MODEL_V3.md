# FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE PRICE OPPORTUNITY  ≠  ACTUAL MAKER FILL
LAYER 3 ACTUAL FILL = UNOBSERVED HISTORICALLY
QUEUE = UNOBSERVED    DEPTH = UNOBSERVED
p_fill values are SCENARIOS, not estimates
PORTFOLIO MARGIN = UNAVAILABLE
```

**Verdict: A — Stable TRAIN→VAL→OOS opportunity clusters with large persist/overshoot gaps and practical p_fill requirements. ACTUAL_FILL still UNOBSERVED.**

Test 4. Does not modify V1, V2, liquidation v1, Game Path V1–V4, FIRST01, Risk, or live execution.
Locked P&L remains `100 − 80 − H = 20 − H`.

## Question 1 — Close-price opportunity frequency

- NBA H=40: 456 / 1230 = 37.0732%
- NCAAB H=40: 1546 / 4099 = 37.7165%
- NBA H=28: 657 / 1230
- NCAAB H=20: 2964 / 4099

## Question 2 — Wick-only opportunity

- NBA H=40 wick-only: 40
- NCAAB H=40 wick-only: 116

## Question 3 — Persistence after first close touch

- NBA H=40 subsequent minutes ≥ H: {'n': 456, 'mean': 12.932, 'p10': 0.0, 'p25': 1.0, 'median': 4.0, 'p75': 16.0, 'p90': 37.0, 'min': 0.0, 'max': 121.0}
- NCAAB H=40: {'n': 1546, 'mean': 12.8493, 'p10': 0.0, 'p25': 1.0, 'median': 4.0, 'p75': 15.0, 'p90': 35.0, 'min': 0.0, 'max': 1227.0}
- NBA H=40 P(persist≥5m | close opp): 0.4715
- NCAAB H=40 P(persist≥5m | close opp): 0.4787

## Question 4 — Path archetypes (deterministic classes at H=40 FULL)

- NBA classes: {'C_WEAK': 102, 'A_STRONG': 231, 'D_WICK_ONLY': 40, 'E_JUMP': 52, 'B_MODERATE': 71}
- NCAAB classes: {'A_STRONG': 719, 'B_MODERATE': 230, 'E_JUMP': 316, 'D_WICK_ONLY': 116, 'C_WEAK': 281}

CLASS E (jump ≥10¢ through H) is a gap: 1m candles cannot prove a print at H.

## Question 5 — Cluster stability (H=40 close opportunities, path features only)

- NBA: method=gmm k=3 VAL silhouette=0.24018242610692303 rank-stable=True
- NCAAB: method=kmeans k=3 VAL silhouette=0.2506258906498392 rank-stable=True

NBA observable: {'TRAIN': {'0': {'n': 132, 'median_persist': 1, 'median_overshoot': 3.0, 'reversal_rate': 0.5455, 'loss_rate': 0.3409}, '2': {'n': 37, 'median_persist': 6, 'median_overshoot': 13.0, 'reversal_rate': 0.1622, 'loss_rate': 0.6216}, '1': {'n': 35, 'median_persist': 50, 'median_overshoot': 4.0, 'reversal_rate': 0.0, 'loss_rate': 0.8286}}, 'VALIDATION': {'0': {'n': 109, 'median_persist': 2, 'median_overshoot': 4.0, 'reversal_rate': 0.4404, 'loss_rate': 0.367}, '2': {'n': 24, 'median_persist': 10, 'median_overshoot': 16.0, 'reversal_rate': 0.125, 'loss_rate': 0.625}, '1': {'n': 34, 'median_persist': 37, 'median_overshoot': 4.0, 'reversal_rate': 0.0, 'loss_rate': 0.7353}}, 'OOS': {'0': {'n': 64, 'median_persist': 2, 'median_overshoot': 3.0, 'reversal_rate': 0.4688, 'loss_rate': 0.2969}, '2': {'n': 7, 'median_persist': 9, 'median_overshoot': 13.0, 'reversal_rate': 0.4286, 'loss_rate': 0.8571}, '1': {'n': 14, 'median_persist': 35, 'median_overshoot': 2.0, 'reversal_rate': 0.0, 'loss_rate': 0.6429}}}
NCAAB observable: {'TRAIN': {'1': {'n': 108, 'median_persist': 25, 'median_overshoot': 5.0, 'reversal_rate': 0.0, 'loss_rate': 0.6296}, '0': {'n': 201, 'median_persist': 1, 'median_overshoot': 4.0, 'reversal_rate': 0.5174, 'loss_rate': 0.2687}, '2': {'n': 25, 'median_persist': 9, 'median_overshoot': 36.0, 'reversal_rate': 0.04, 'loss_rate': 0.92}}, 'VALIDATION': {'1': {'n': 413, 'median_persist': 22, 'median_overshoot': 5.0, 'reversal_rate': 0.0073, 'loss_rate': 0.6392}, '0': {'n': 721, 'median_persist': 1, 'median_overshoot': 3.0, 'reversal_rate': 0.5243, 'loss_rate': 0.3356}, '2': {'n': 50, 'median_persist': 8, 'median_overshoot': 34.0, 'reversal_rate': 0.04, 'loss_rate': 0.86}}, 'OOS': {'0': {'n': 17, 'median_persist': 2, 'median_overshoot': 4.0, 'reversal_rate': 0.4706, 'loss_rate': 0.2353}, '1': {'n': 9, 'median_persist': 18, 'median_overshoot': 8.0, 'reversal_rate': 0.0, 'loss_rate': 0.4444}, '2': {'n': 2, 'median_persist': 3, 'median_overshoot': 20.0, 'reversal_rate': 0.0, 'loss_rate': 1.0}}}

Clusters were selected on VALIDATION silhouette, then frozen. OOS labeled once. Target is not P&L.

## Question 6 — Minimum assumed p_fill for EV > 0

Hold-to-settlement EV is already positive, so universal p_min for EV>0 is **0** on both sports.
That does not mean the hedge is free. It means missing the hedge still leaves the +20/−80 book.

## Question 7 — Minimum assumed p_fill to beat frozen 80/40

- NBA H=40 universal: 0.6643
- NCAAB H=40 universal: 0.528
- NBA H=28 (V2 H*): 0.7027
- NCAAB H=20 (V2 H*): 0.4065

These are **scenario thresholds**, not estimated fill rates.

If only CLASS A (multi-minute persist) fills, the H=40 bar is **54.9% NBA / 55.5% NCAAB**. Weak/wick-only fills are not required for the hedge to beat 80/40 on the FULL sample.

OOS p_min = 0 on both sports is not a fill miracle: hold-to-settlement already beat the 80/40 proxy on those small windows (NCAAB OOS n=84). Do not read that as “fills are free out of sample.”

## Question 8 — Does the V2 low-H plateau survive imperfect fills?

Yes as a *shape*: lower H still has a smaller lock (`20−H`) and more close opportunities, so the p_fill needed to beat 80/40 is typically lower than at H=40. See tables. Capital reservation of 80+H still punishes high H.

## Question 9 — What to prioritize in a live/paper fill test

1. CLASS A (multi-minute close ≥ H) — strongest observed opportunity.
2. Pre-rested maker bid (T_rest ≪ T_touch). Median rest time is in the surface.
3. CLASS E jumps — measure whether price *traded* at H or gapped through.
4. CLASS D wick-only — expect the weakest fill rate; do not pool with A.

## Question 10 — Can historical candles answer actual fill?

**NO.** Layer 3 is unobserved. Candles can state a fill-quality taxonomy and a required p_fill. They cannot estimate P(ActualMakerFill | ·).

## Reproduction

- NBA: {'sport': 'nba', 'ok': True, 'observed': {'n': 1230, 'hedge': 456, 'win': 774, 'miss': 0, 'ev': 5.1707, 'stop_ev': 4.3902}, 'expected': {'n': 1230, 'hedge': 456, 'win': 774, 'miss': 0, 'ev': 5.1707, 'stop_ev': 4.3902}, 'label': 'CANDLE PRICE_OPPORTUNITY — NOT ACTUAL_FILL'}
- NCAAB: {'sport': 'ncaab', 'ok': True, 'observed': {'n': 4099, 'hedge': 1546, 'win': 2552, 'miss': 1, 'ev': 4.889, 'stop_ev': 3.9034}, 'expected': {'n': 4099, 'hedge': 1546, 'win': 2552, 'miss': 1, 'ev': 4.889, 'stop_ev': 3.9034}, 'label': 'CANDLE PRICE_OPPORTUNITY — NOT ACTUAL_FILL'}

## Passive hedge vs reactive liquidation

| Dimension | Passive hedge | Reactive 80/40 |
|---|---|---|
| Placement | After 80 fill, before H | After 40 trigger |
| Side | Resting buy opponent YES | Sell/liquidate favorite YES |
| Latency after trigger | Lower (already resting) | High |
| Queue | High (unobserved) | Lower if taking |
| Depth | High (unobserved) | High (unobserved) |
| Gap risk | Jump through H may skip the bid | Collapse can skip 40 |
| Historical fill | UNOBSERVED | UNOBSERVED |

Neither is declared superior. They are different unobserved execution problems.

## Required live/paper telemetry

ORDER_ID, GAME_ID, MARKET_ID, H, T_ENTRY, T_ORDER_SUBMIT, T_ORDER_ACK,
T_FIRST_PRICE_TOUCH_H, T_FIRST_POTENTIAL_MATCH, T_FIRST_FILL, T_LAST_FILL,
ORDER_PRICE, INITIAL_QTY, FILLED_QTY, REMAINING_QTY, VWAP_FILL,
CANCEL_TIME, CANCEL_REASON, BEST_BID/ASK at submit and touch, VISIBLE_DEPTH or DEPTH_UNAVAILABLE.

Target: `P(ActualMakerFill | H, path, persist, overshoot, vol, time_resting)` plus P(partial), E(fill fraction), E(VWAP), time-to-fill.

Status: **ACTUAL FILL EXPERIMENT NOT_RUN.**

## Selection protocol (a priori)

- Discover path clusters on TRAIN H=40 close opportunities.
- Features: overshoot, persist, range, velocities, vols, spread, reversal, complement residual.
- Drop |pearson|>0.92.
- Choose kmeans/gmm k∈{3,4,5} by VALIDATION silhouette, min VAL cluster n=20.
- Freeze. Label OOS once.
- Do not choose a new production H.

Code: `apps/ncaab-data/scripts/first80_opponent_hedge_execution_model_v3.py`
Dashboard: `frontend/first80-hedge-execution-v3/`
Tables: `docs/research/FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3_TABLES.md`

LIVE EXECUTION CHANGED: FALSE

