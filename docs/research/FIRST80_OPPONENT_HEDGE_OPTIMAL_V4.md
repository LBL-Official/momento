# FIRST80_OPPONENT_HEDGE_OPTIMAL_V4

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL
ORACLE BOOK              =  LOOKAHEAD (favorite close-40 already known)
```

**Verdict: B** — HYBRID candle EV beats 80→40 on VAL and OOS, but some trades are worse (false hedges). ORACLE weakly dominates every trade and is lookahead. Fills remain unobserved.

Does not modify V1–V3, FIRST01, Risk, or live execution.

## What “each trade better” can and cannot mean

For a single FIRST-80 trade, 80→40 Model A pays **+20** if the favorite
never prints close-40 and wins, and **−40** if it does.

A hedge fill at H locks **20−H** (H=40 → **−20**).

| This trade’s 80→40 path | Hedge fills | Hedge vs 80→40 |
|---|---|---|
| Survivor (+20) | yes (false hedge) | **worse** by H¢ |
| Survivor (+20) | no | equal |
| Stop (−40) | yes | **better** by (20−H)−(−40) = 60−H |
| Stop (−40) | no | equal if HYBRID; worse if REPLACE (falls to −80) |

So **no resting-opponent rule that can fire on a survivor is better on every trade.**
That is an identity, not a tuning failure.

This test therefore reports two books:

1. **HYBRID (executable candle proxy)** — rest opponent at H; if the
   opportunity never prints, keep 80→40. Selected on VALIDATION to
   maximize mean P&L subject to beating 80→40. Some trades are worse.
2. **ORACLE (lookahead upper bound)** — take the hedge **only** on trades
   that also printed favorite close-40. Then no trade is worse than
   80→40. This uses future information. It is **not** a live rule.

## Selection protocol (frozen before OOS)

- Universes: frozen FIRST-80 (NBA 1,230 / NCAAB 4,099)
- Path: opponent `yes_bid_close ≥ H` after entry (V1/V2 close proxy)
- Grid: H=20..60, persist ∈ {0,2,5}, skip CLASS-E jump yes/no,
  held favorite at touch ≤ {none, 60, 55}
- TRAIN / VAL / OOS: same calendar cuts as V2
- Choose HYBRID on **VALIDATION only**; score OOS once
- Per-trade P&L is the unit. Mean EV is the mean of those P&Ls.

## Reproduction

- NBA: {'n': 1230, 'hedge': 456, 'win': 774, 'miss': 0, 'ev': 5.1707, 'stop_ev': 4.3902} per_trade=True
- NCAAB: {'n': 4099, 'hedge': 1546, 'win': 2552, 'miss': 1, 'ev': 4.889, 'stop_ev': 3.9034} per_trade=True

## Selected HYBRID (executable proxy)

- NBA: `H=26, persist≥5, no_jump=False, held_max=None, lock=-6¢`
- NCAAB: `H=22, persist≥5, no_jump=False, held_max=None, lock=-2¢`

VAL picked **persist ≥ 5 minutes** on both sports. That is a candle
filter (opponent close stays ≥ H), not a fill. It raises mean EV by
skipping many one-bar touches, including some real stops. Treat it as
a VAL-fit gate, not a production parameter.

| Split | NBA HYBRID vs 80→40 | NCAAB HYBRID vs 80→40 |
|---|---|---|
| TRAIN | +5.55¢  (vs 80/40 +3.10, Δ +2.45; better 83 / worse 61 / equal 360) | +7.14¢  (vs 80/40 +5.16, Δ +1.98; better 120 / worse 121 / equal 717) |
| VAL | +8.03¢  (vs 80/40 +5.34, Δ +2.69; better 65 / worse 35 / equal 383) | +6.68¢  (vs 80/40 +3.40, Δ +3.27; better 513 / worse 432 / equal 2112) |
| OOS | +6.38¢  (vs 80/40 +5.19, Δ +1.19; better 33 / worse 32 / equal 178) | +8.71¢  (vs 80/40 +7.86, Δ +0.86; better 10 / worse 14 / equal 60) |
| FULL | +6.69¢  (vs 80/40 +4.39, Δ +2.30; better 181 / worse 128 / equal 921) | +6.83¢  (vs 80/40 +3.90, Δ +2.92; better 643 / worse 567 / equal 2889) |

FULL trades with HYBRID **worse** than 80→40: NBA **128**, NCAAB **567** (false hedges).

## H=40 REPLACE (V1 book) vs 80→40, per trade

| Sport | REPLACE H=40 EV | 80→40 EV | Δ | worse trades |
|---|---:|---:|---:|---:|
| NBA | +5.17 | +4.39 | +0.78 | 136 |
| NCAAB | +4.89 | +3.90 | +0.99 | 451 |

Mean EV is higher. Individual false-hedge trades are not.

## ORACLE (lookahead; every trade ≥ 80→40)

- NBA: `H=20, persist≥0, no_jump=False, held_max=None, lock=0¢` — FULL n_worse=0
- NCAAB: `H=20, persist≥0, no_jump=False, held_max=None, lock=0¢` — FULL n_worse=0

| Split | NBA ORACLE vs 80→40 | NCAAB ORACLE vs 80→40 |
|---|---|---|
| TRAIN | +14.37¢  (vs 80/40 +3.10, Δ +11.27; better 142 / worse 0 / equal 362) | +15.05¢  (vs 80/40 +5.16, Δ +9.90; better 237 / worse 0 / equal 721) |
| VAL | +15.11¢  (vs 80/40 +5.34, Δ +9.77; better 118 / worse 0 / equal 365) | +14.46¢  (vs 80/40 +3.40, Δ +11.06; better 845 / worse 0 / equal 2212) |
| OOS | +15.06¢  (vs 80/40 +5.19, Δ +9.88; better 60 / worse 0 / equal 183) | +15.95¢  (vs 80/40 +7.86, Δ +8.10; better 17 / worse 0 / equal 67) |
| FULL | +14.80¢  (vs 80/40 +4.39, Δ +10.41; better 320 / worse 0 / equal 910) | +14.63¢  (vs 80/40 +3.90, Δ +10.72; better 1099 / worse 0 / equal 3000) |

Oracle EV is the value of a **perfect** “only hedge the stops” gate.
Candles do not provide that gate at T+0, and a 40¢ bid still cannot rest
while the opponent ask is ~20¢.

## Unconditional H* (HYBRID, persist=0, no extra gate)

- NBA: {'h': 39, 'persist_min': 0, 'no_jump': False, 'held_max': None, 'book': 'hybrid', 'ev_cents': 6.354, 'stop_ev_cents': 5.3416, 'delta_vs_stop_cents': 1.0124, 'n_better': 118, 'n_worse': 51, 'n_equal': 314, 'hedge_opportunities': 169, 'false_hedges': 89, 'protected_losses': 80, 'lock_cents': -19, 'lookahead': False}
- NCAAB: {'h': 21, 'persist_min': 0, 'no_jump': False, 'held_max': None, 'book': 'hybrid', 'ev_cents': 5.334, 'stop_ev_cents': 3.402, 'delta_vs_stop_cents': 1.932, 'n_better': 845, 'n_worse': 1289, 'n_equal': 923, 'hedge_opportunities': 2134, 'false_hedges': 1585, 'protected_losses': 549, 'lock_cents': -1, 'lookahead': False}

## What this does not prove

- Maker fills at H
- That a post-only bid at H rests when opponent ask < H
- Fees, two-market risk booking, live FIRST01

Code: `apps/ncaab-data/scripts/first80_opponent_hedge_optimal_v4.py`
Artifacts: `.../derived/{nba,ncaab}/first80_opponent_hedge_optimal_v4/`

LIVE EXECUTION CHANGED: FALSE
