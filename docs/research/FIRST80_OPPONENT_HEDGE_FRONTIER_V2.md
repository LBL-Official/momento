# FIRST80_OPPONENT_HEDGE_FRONTIER_V2

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL
ACTUAL FILL EXPERIMENT: NOT_RUN
Architecture C (portfolio margin): UNAVAILABLE
```

**Verdict: B — PROMISING BUT EXECUTION UNRESOLVED.**

Candle economics survive VAL→OOS with near-100% loss recall. Maker fills
are unobserved. Reserved-capital ranking vs 80/40 is **not uniform**
(NCAAB H=20 reserved beats 80/40; NBA H=28 reserved does not).

Locked P&L used throughout is the correct box:

```text
100 − 80 − H = 20 − H
```

(The prompt’s “= −H” is an algebra slip. H=40 must lock at **−20¢** to
reproduce V1. It does.)

Test 3. Does not modify V1, liquidation v1, Game Path V1–V4, FIRST01, Risk, or live execution.

## Question 1 — Does H=40 reproduce?

- NCAAB: True observed {'n': 4099, 'hedge': 1546, 'win': 2552, 'miss': 1, 'ev': 4.889, 'stop_ev': 3.9034}
- NBA: True observed {'n': 1230, 'hedge': 456, 'win': 774, 'miss': 0, 'ev': 5.1707, 'stop_ev': 4.3902}

Gate required 1,546 / 2,552 / 1 / +4.89¢ and 456 / 774 / 0 / +5.17¢.

## Question 2 — Is there a robust hedge-price frontier?

Yes, a **wide low-H plateau**, not a one-cent spike.

| H | NCAAB EV | NCAAB EV/res | NCAAB miss | NBA EV | NBA EV/res | NBA miss |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 5.51 | 0.0551 | 1 | 4.57 | 0.0457 | 0 |
| 28 | 5.16 | 0.0478 | 1 | 5.04 | 0.0467 | 0 |
| 35 | 5.08 | 0.0442 | 1 | 4.78 | 0.0415 | 0 |
| 40 | 4.89 | 0.0407 | 1 | 5.17 | 0.0431 | 0 |
| 50 | 4.69 | 0.0361 | 1 | 5.20 | 0.0400 | 0 |

NCAAB EV/reserved **falls as H rises**. VAL therefore picked the grid floor (20).
NBA VAL picked 28 (stable neighborhood 26–30). Loss recall stays ~100% on
the entire 20–60 close grid in both sports (NBA 0 misses; NCAAB 1 miss at
every H — the same single leak). Wick is weaker and is not the policy path.

Splits (same calendar cuts as the frozen 80/40 audit):

| | TRAIN ≤2025-12-31 | VAL through 2026-03-15 | OOS after |
|---|---:|---:|---:|
| NBA | 504 | 483 | 243 |
| NCAAB | 958 | 3,057 | **84** |

NCAAB OOS n=84 is too small to carry a production claim.

## Question 3 — False hedges vs catastrophic misses

Higher H → fewer opportunities, more misses, fewer false hedges, more negative lock (−H).
Lower H → more protection, more false locks, smaller per-lock loss.

## Question 4 — Cross-sport H*

- NCAAB selected H* = **20** (VALIDATION only). Stability: STABLE_PLATEAU
- NBA selected H* = **28** (VALIDATION only). Stability: STABLE_PLATEAU

## Question 5 — TRAIN → VAL → OOS

### NCAAB H*

| Split | n | Opp | False | Protected | Miss | EV ¢ | EV/reserved |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 958 | 659 | 514 | 145 | 0 | 6.2422 | 0.062422 |
| VALIDATION | 3057 | 2247 | 1698 | 549 | 1 | 5.2666 | 0.052666 |
| OOS | 84 | 58 | 48 | 10 | 0 | 6.1905 | 0.061905 |

### NBA H*

| Split | n | Opp | False | Protected | Miss | EV ¢ | EV/reserved |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 504 | 286 | 189 | 97 | 0 | 4.1111 | 0.038066 |
| VALIDATION | 483 | 245 | 165 | 80 | 0 | 5.7971 | 0.053677 |
| OOS | 243 | 126 | 92 | 34 | 0 | 5.4815 | 0.050754 |

## Question 6 — Capital

Architecture A reserves 80+H at entry ($6.25/game, $50 start, unlimited concurrent, historical path sim):

| Book | NBA terminal | NBA ROC | NCAAB terminal | NCAAB ROC |
|---|---:|---:|---:|---:|
| Hold | 29,500¢ | 4.90 | 84,940¢ | 15.99 |
| 80/40 stop | **42,800¢** | **7.56** | 116,020¢ | 22.20 |
| H=40 reserved | 36,800¢ | 6.36 | 104,700¢ | 19.94 |
| H* reserved | 36,020¢ (H=28) | 6.20 | **140,240¢ (H=20)** | **27.05** |

NBA: 5 contracts at 108¢ lose to 7 contracts at 80¢ on the stop book.
NCAAB H=20: lock is **0¢**, unit 100¢ → 6 contracts, and dollar path beats 80/40
in this simulation. That is still a candle proxy, not a fill.

Architecture B (fund H only when the opportunity prints): research only.
Live Risk cannot book a second market today.

Architecture C portfolio offset: **UNAVAILABLE**.

## Question 7 — Fill plausibility

Regimes are PROXY / NOT ACTUAL FILL: persistent-above, immediate reversal,
jump ≥10¢, gradual approach, high pre-cross vol. See `fill_plausibility_proxy.parquet`.

## Question 8 — Live telemetry required

T_submit, T_ack, first touch, first/last fill, VWAP, remaining qty, cancel,
bid/ask/depth if available. Object: P(ActualMakerFill | H, path, persist, vol).
Status: **NOT_RUN**.

## Selection protocol (a priori)

{
  "split": "TRAIN game_date<=2025-12-31; VAL 2025-12-31<d<=2026-03-15; OOS after 2026-03-15",
  "path": "close",
  "persist_min": 0,
  "objective": "max VALIDATION ev_per_reserved_capital (80+H)",
  "miss_ceiling": 0.01,
  "min_val_hedge_n": 30,
  "min_val_trades": 40,
  "stability": "5-point neighborhood rel range > 0.25 => THRESHOLD_OVERFIT_RISK, use smoothed plateau",
  "oos": "evaluate exactly once after freeze"
}

## Comparison (FULL close path)

| Strategy | Sport | H | Opp rate | False | Protected | Miss | Gross EV ¢ | Reserved | EV/cap |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hold to expiration | nba | — | — | — | — | — | 2.8455 | 80 | 0.03557 |
| 80/40 reactive stop proxy | nba | — | — | — | — | — | 4.3902 | 80 | 0.05488 |
| Opponent H=30 | nba | 30 | 0.5065 | 412 | 211 | 0 | 4.8049 | 110 | 0.04368 |
| Opponent H=35 | nba | 35 | 0.4350 | 324 | 211 | 0 | 4.7764 | 115 | 0.04153 |
| Opponent H=40 | nba | 40 | 0.3707 | 245 | 211 | 0 | 5.1707 | 120 | 0.04309 |
| Opponent H=45 | nba | 45 | 0.3317 | 197 | 211 | 0 | 5.0732 | 125 | 0.04059 |
| Selected H* | nba | 28 | 0.5341 | 446 | 211 | 0 | 5.0439 | 108 | 0.0467 |
| Hold to expiration | ncaab | — | — | — | — | — | 2.8007 | 80 | 0.03501 |
| 80/40 reactive stop proxy | ncaab | — | — | — | — | — | 3.9034 | 80 | 0.04879 |
| Opponent H=30 | ncaab | 30 | 0.4950 | 1325 | 704 | 1 | 5.1256 | 110 | 0.0466 |
| Opponent H=35 | ncaab | 35 | 0.4255 | 1040 | 704 | 1 | 5.0842 | 115 | 0.04421 |
| Opponent H=40 | ncaab | 40 | 0.3772 | 842 | 704 | 1 | 4.889 | 120 | 0.04074 |
| Opponent H=45 | ncaab | 45 | 0.3362 | 674 | 704 | 1 | 4.8475 | 125 | 0.03878 |
| Selected H* | ncaab | 20 | 0.7231 | 2260 | 704 | 1 | 5.5135 | 100 | 0.05514 |

Code: `apps/ncaab-data/scripts/first80_opponent_hedge_frontier_v2.py`
Dashboard: `frontend/first80-hedge-frontier-v2/`
Artifacts: `.../derived/{nba,ncaab}/first80_opponent_hedge_frontier_v2/`

