# FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL
V4 persist≥5 + lock 20−H  =  LOOKAHEAD unless restated at T3
```

**Verdict: C** — After a causal T2 decision and lock at T2 bid, HYBRID no longer beats 80→40 on at least one sport FULL sample. V4’s persist≥5 mean was not a causal T3 result.

Does not retune H. Does not change FIRST01, Risk, or live execution.

## Question

Is V4 HYBRID (`persist ≥ 5`, lock `20−H`) a **causal post-entry trigger**,
or a full-path filter that peeks past the decision time?

## Timeline (required)

```text
T0  FIRST-80 candle on favorite          (fill still unobserved)
T1  opponent yes_bid_close first ≥ H
T2  K subsequent qualifying bars still ≥ H
T3  hedge decision  =  T2
```

Only bars with `t ≤ T3` may decide whether we hedge.
If favorite `close-40` prints at or before T3, HYBRID takes **80→40**,
not the hedge. That race is live-relevant and was invisible in V4.

K counts **subsequent qualifying 1-minute bars**, the same object as
V2 `persist_min`. That is not always 300 wall-clock seconds if bars
are missing or fail the tradable-quality filter.

## Three locks on the same T3 event

| Book | When we hedge | Lock | Status |
|---|---|---|---|
| V4 lookahead | full-path persist≥K, ignore 40-race | 20−H | LOOKAHEAD |
| Causal lock H | T3 reached, 40-race respected | 20−H | elapsed persist; optimistic price |
| Causal T2 bid | T3 reached, 40-race respected | 20 − bid_close(T2) | elapsed persist + then-price |
| Causal T2 ask | same | 20 − ask_close(T2) | worse if you take |

Frozen rule: NBA **H=26 K=5**. NCAAB **H=22 K=5**. Not reselected.

## Reproduction (V4 lookahead)

- NBA FULL 6.6878 vs expected 6.6878
- NCAAB FULL 6.8261 vs expected 6.8261

## FULL sample — V4 selected HYBRID

| Book | NBA EV | NBA vs 80→40 | NBA worse | NCAAB EV | NCAAB vs 80→40 | NCAAB worse |
|---|---:|---:|---:|---:|---:|---:|
| V4 lookahead | +6.69 | +2.30 | 128 | +6.83 | +2.92 | 567 |
| Causal lock H | +6.16 | +1.77 | 128 | +6.00 | +2.10 | 567 |
| Causal T2 bid | +4.12 | -0.27 | 129 | +3.56 | -0.34 | 568 |
| Causal T2 ask | +3.75 | -0.64 | 129 | +3.05 | -0.86 | 568 |

### What V4 was hiding

- NBA: V4 would hedge but causal aborts (mostly 40-race during wait): **19**. STOP_DURING_WAIT=19.
- NCAAB: **89** aborts. STOP_DURING_WAIT=88.

- NBA T2 bid vs H overshoot (hedged only): {'n': 290, 'mean': 8.6724, 'median': 7.0, 'p90': 20.0, 'max': 35.0}
- NCAAB T2 bid vs H overshoot: {'n': 1121, 'mean': 8.9313, 'median': 7.0, 'p90': 19.0, 'max': 53.0}
- NBA wait T1→T2 minutes: {'n': 290, 'mean': 5.0241, 'median': 5.0, 'p90': 5.0, 'max': 7.0}
- NCAAB wait T1→T2 minutes: {'n': 1121, 'mean': 5.0928, 'median': 5.0, 'p90': 5.0, 'max': 14.0}

## Splits (causal T2 bid — the honest HYBRID trigger)

| Split | NBA | NCAAB |
|---|---|---|
| TRAIN | +2.42¢ vs 80/40 +3.10 (Δ -0.67; hedge 134; worse 62) | +4.19¢ vs 80/40 +5.16 (Δ -0.97; hedge 222; worse 121) |
| VAL | +5.84¢ vs 80/40 +5.34 (Δ +0.50; hedge 93; worse 35) | +3.30¢ vs 80/40 +3.40 (Δ -0.10; hedge 876; worse 433) |
| OOS | +4.21¢ vs 80/40 +5.19 (Δ -0.98; hedge 63; worse 32) | +5.70¢ vs 80/40 +7.86 (Δ -2.15; hedge 23; worse 14) |
| FULL | +4.12¢ vs 80/40 +4.39 (Δ -0.27; hedge 290; worse 129) | +3.56¢ vs 80/40 +3.90 (Δ -0.34; hedge 1121; worse 568) |

## Decisions (FULL, V4 H/K)

- NBA: {'PERSIST_FAIL': 399, 'NO_T1': 522, 'HEDGE_AT_T3': 290, 'STOP_DURING_WAIT': 19}
- NCAAB: {'HEDGE_AT_T3': 1121, 'PERSIST_FAIL': 1484, 'NO_T1': 1394, 'STOP_DURING_WAIT': 88, 'STOP_AT_OR_BEFORE_T1': 12}

## Diagnostics (not selected)

- NBA H=40 K=5: EV +4.26 Δ -0.13 hedge 133 worse 31 beats_stop=False
- NCAAB H=40 K=5: EV +3.72 Δ -0.19 hedge 371 worse 91 beats_stop=False
- NBA H=40 K=0: EV +3.65 Δ -0.74 hedge 442 worse 136 beats_stop=False
- NCAAB H=40 K=0: EV +3.05 Δ -0.85 hedge 1450 worse 455 beats_stop=False

## What this does not prove

- 80¢ maker fill at T0
- Maker fill at H or at T2
- That a post-only bid rests while opponent ask < H
- Live/paper resting-order telemetry

Next object, if this causal book still has a portfolio edge: **paper
resting-order telemetry**, not another H search.

Code: `apps/ncaab-data/scripts/first80_hybrid_causal_timeline_audit_v5.py`
Artifacts: `.../derived/{nba,ncaab}/first80_hybrid_causal_timeline_audit_v5/`

LIVE EXECUTION CHANGED: FALSE
