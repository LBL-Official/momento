# B1 — Dissection of Price (feature engine)

**Status:** IMPLEMENTED (research infrastructure, schema 1.1.0)  
**Crate:** `momento-research-features`  
**CLI:** `momento-research-b1 --extract`  
**Not:** live trading, W9, L2 invention, strategy retune, fills.

B1 is observational research infrastructure.

Historical L2 is **unavailable**.

`TRADE != maker fill`.

No production trading behavior was changed.

---

## Purpose

When two Kalshi contracts both print 80–83¢, what baseball state, starting
TRADE belief, game/market path, and (when it exists) microstructure is already
known at that print — and how do subsequent TRADE prints and W6 settlement
differ under **A1 entry and exit targets**?

80¢ is a price, not a state. B1 stores the state around that price.

B1 does **not** answer whether a maker order would have filled.

---

## Pipeline

```text
W5 AS-OF  →  W6 state  →  W7 path  →  W8 FIRST01 sequencing  →  B1 features
                                                              → A1 buckets
```

B1 consumes those layers. It does not reconstruct PBP, resync W5, or replay W8.

---

## Entry definition

Primary cohort = W8 opportunities with an in-band TRADE (80–83) after first-80
and same-side 81. One primary snapshot per game (`UNIQUE (run_id, game_id)`).

```text
execution_status = OBSERVATIONAL_TRADE_ENTRY
```

Never `FILLED_ENTRY` unless actual historical execution evidence exists (it does not).

---

## Layers

| Layer | Contents | Availability |
|-------|----------|--------------|
| Baseball | W6 `state_at_or_before(entry)` | `NO_STATE` if none |
| Starting market | First TRADE ≤ entry; start bias; **start sentiment** | Bid/ask/mid/spread **UNAVAILABLE** |
| Current market | D80_trade = entry−80 | Mid/spread/D80_mid **UNAVAILABLE** |
| Market history | Start-to-entry move, path, reversals, TRADE vol, personality | TRADE dynamics only |
| Price dynamics | P_1m/5m/15m/30m, ΔP, velocity, acceleration | Actual lookback seconds recorded |
| Event response | Class aggregates + **event history** (last 32) | Not a causal claim |
| Microstructure | Full OBI/OFI/depth/microprice/absorption/residual schema | **UNAVAILABLE_SOURCE** |
| Fair value | Reserved | Not fit from settlement |
| **A1 targets** | Entry 80/81/82/83 × exits (hold, FIRST01/50%, hard 75–60, horizons) | TRADE-modeled exits |
| Outcomes | Future TRADE returns, MFE/MAE, W6 settlement | Label namespace only |

---

## Starting sentiment

Raw `P_start` is retained. Buckets (cents):

| Bucket | `P_start` |
|--------|-----------|
| STRONG_UNDERDOG | &lt; 40 |
| UNDERDOG | 40–46 |
| NEUTRAL | 47–53 |
| FAVORITE | 54–59 |
| STRONG_FAVORITE | ≥ 60 |

Price-band buckets (`LT_40`, `40_49`, …) are also kept.

---

## Baseball regimes

Inning: 1–3 EARLY, 4–6 MID, 7–8 LATE, 9 NINTH, ≥10 EXTRA.  
Score vs bound side: CLOSE `|lead|≤1`, LEAD `≥2`, TRAIL `≤-2`.  
`EXTRA_INNINGS` overrides score band.

Raw inning, lead, outs, bases are retained. Score buckets: TIED / ONE_RUN /
TWO_RUN / MULTI_RUN. Base class: EMPTY / RUNNER_ON / RISP / LOADED.

---

## A1 entry / exit targets

A1 here is the research-backtest target language (`entry_price_range` +
`exit_price_input`), **not** waterfall W0-A1.

**Entry targets:** `ENTRY_80` … `ENTRY_83` plus band `80-83`.

**Exit targets** (observational TRADE path, not fills):

| Target | Rule |
|--------|------|
| `HOLD_TO_SETTLEMENT` | W6 100/0 |
| `FIRST01` / `LIVE_50PCT_STOP` | First later TRADE ≤ entry/2, else settlement |
| `HARD_STOP_75` … `HARD_STOP_60` | First later TRADE ≤ N, else settlement |
| `HORIZON_1M` … `HORIZON_30M` | Last TRADE in window; else `INSUFFICIENT_HISTORY` |

`a1_bucket_report.json` crosses **entry × exit × coarse condition** and reports
`N_entries`, `N_unique_games`, win rate, lift vs baseline, EV, MFE/MAE.
The independence unit is **game**, not snapshot.

A positive cell is **not** a trading rule and does **not** change live
80/81/83/89 or the 50% stop.

---

## Personality

TRADE-path classes: TRENDING, MEAN_REVERTING, CHOPPY, ACCELERATING,
DECELERATING, REVERSING, STABLE, UNCLASSIFIED.

ACCELERATING / DECELERATING refine a recent-up path using 1m vs 5m velocity.

---

## State-conditioned z (TRADE only)

`volatility_5m_z` and `start_to_entry_move_z` use **TRAIN** μ/σ by baseball
regime (≥20 unique TRAIN games). TEST rows receive TRAIN moments.  
`OBI_z`, `OFI_z`, `MicroDeviation_z` stay **UNAVAILABLE** until L2 exists.

---

## Causality

Features: source timestamp ≤ entry.  
Outcomes / A1 exits: timestamp > entry (or settlement label).  
Settlement is an intentional future **label** from W6 finals, never a feature.
`FINAL_TIE` stays fail-closed. Fair value is reserved (fitting it from
settlement would leak the label).

---

## Conditional EV

`E[return | S]` and `P(win | S)` report `N_entries`, `N_unique_games`, and
sample-size flags (`VERY_SMALL` &lt;20 games, …, `RESEARCHABLE` ≥100).

Also:

- `Lift(S) = P(win|S) / P(win)`
- Settlement EV at the row's entry
- Theoretical 80¢ EV = `P(win)×20 − P(loss)×80` (fees ignored; comparable only
  for 80¢ entries)

Chronological split: official/entry date `&lt; 2026-01-01` = TRAIN, else TEST.

---

## What is still UNAVAILABLE (typed, not invented)

Bid, ask, mid, spread, D80_mid, OBI_1/3/5/10, ΔOBI, OBI_z, microprice,
depth 1/3/5/10, Δdepth, liquidity velocity, OFI, absorption, replenishment,
price/book and price/flow divergence, spread/liquidity state, cancellations,
queue, maker-fill probability, microstructure residual.

---

## Artifacts

`Backtesting Suite/Foundation/B1/`: `features.sqlite` (gitignored),
`schema.sql`, `manifest.json`, `validation_report.json`,
`feature_dictionary.json`, `coverage_report.json`,
`a1_bucket_report.json`, `representative_examples.json`.

Exhaustive A1 search (`momento-research-b1 --search`):
`b1_research_report.md`, `b1_search_summary.md`, ranking JSONs,
`b1_best_cohort.json`. TRADE-print modeled. Not a trading rule.
