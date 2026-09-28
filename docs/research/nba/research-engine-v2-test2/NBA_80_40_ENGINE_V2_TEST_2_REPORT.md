# NBA_80_40_ENGINE_V2_TEST_2_REPORT

Identity: `NBA_RESEARCH_ENGINE_V2_TEST2`

This report is the spec deliverable for **Test 2: game-state × market-path clustering**.
It does **not** overwrite Path Engine V1 (Verdict C / NO FILTER) or Game Path Engine V2
(Verdict C / NO FILTER). It does not change live FIRST01, Risk, or Kalshi execution.

Frozen 80/40 definition is unchanged.

```text
ENTRY = first qualifying 80¢ candle close
Y_hit_40 = 1  ⇔  close-path 40 after ENTRY_DECISION_TIME
Y_survive_40 = 1 − Y_hit_40
EV_gross = 1 − 3q    where q = P(Y_hit_40 = 1)
breakeven q = 33.33%
unconditional q = 320/1230 = 26.02%   (survive 910/1230 = 73.98%)
EV_unconditional ≈ +0.219 R
```

Primary analysis set: GPE V2 alignment `HIGH ∪ MEDIUM` (n = 1,169). Full ledger n = 1,230.

---

## 1. Executive verdict

**VERDICT B**

Some descriptive structure exists, but not enough evidence for production filtering.

Under this spec’s A–D scale:

| Verdict | Meaning | This run |
| --- | --- | --- |
| A | Meaningful trade classes independently validated | no |
| **B** | **Descriptive structure, not production-ready** | **yes** |
| C | No structure beyond baseline demonstrated | too strong — weak structure exists |
| D | Data cannot answer the question | no: the question was answered honestly |

Production line (unchanged): **NO FILTER**.

Why not A: VAL Brier does not beat Model 0 (constant q̂ = 26.02%) by the 5% gate.
Full possession+market stacks overfit. Cluster q-gaps shrink OOS. Calibration of
the simple game-state logistic is worse than Model 0 (ECE 0.040 vs 0.007).

Why not C: K-Means K=2 on possession-primary features separates TRAIN close-path
40 rates 44.6% (n=56) vs 26.7% (n=424). PCA PC1 is dominated by how many
possessions were observed before entry (game progress), not a latent “trade type.”
KNN VAL AUC 0.58 is weak neighborhood structure, not an edge.

Why not D: Frozen labels, PBP sequence, and 1m TOB are sufficient to **reject**
production classes. L2 / true fills / pregame strength remain UNAVAILABLE and
are labeled as such; they are not invented.

---

## 2. Dataset description

| Quantity | Count |
| --- | ---: |
| Kalshi games scanned | 1,362 |
| First-80 | 1,230 |
| Survive close-path 40 | 910 (73.98%) |
| Hit close-path 40 | 320 (26.02%) |
| Primary HIGH+MEDIUM | 1,169 (q = 26.43%) |
| Excluded LOW/UNUSABLE/unmatched | 61 |
| TRAIN BUILD `game_date ≤ 2025-12-31` | 480 primary |
| VALIDATION CHOOSE through `2026-03-15` | 458 primary |
| OOS VERIFY after `2026-03-15` | 231 primary |

Seven first-80s have no PBP crosswalk match. They remain on the ledger.

PBP: PlayByPlayV3, 2025–26. Per-play `timeActual` unavailable.

---

## 3. Feature availability matrix

| Signal | Status |
| --- | --- |
| Possession sequence, period, official clock, score | OBSERVED |
| Modeled wall start/end (`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`) | DERIVED |
| Per-play `timeActual` | UNAVAILABLE |
| Kalshi 1m top-of-book OHLC | OBSERVED |
| Possession↔candle overlay | APPROXIMATED (`MULTI_POSSESSION_CANDLE` dominant) |
| L2 imbalance / queue / depth | UNAVAILABLE |
| Pregame win probability / team strength | UNAVAILABLE |
| Lineup state | UNAVAILABLE |
| Verified maker fill | UNAVAILABLE |
| Post-entry MAE / possessions-until-stop | OBSERVED, **TARGET_ONLY** |
| 1/5/15m candle windows | OBSERVED, **SECONDARY sampling artifact** |

No L2 was invented.

---

## 4. Leakage audit

`leakage_audit.json`: **PASS**.

- Predictors use possessions with modeled `wall_start ≤ ENTRY_DECISION_TIME` only.
- `Y_settle_yes`, `mae_after_entry_cents`, `possessions_until_stop`, wick, and
  time-to-40 are labels / TARGET_ONLY.
- Same-bar OHLC at the entry candle is observable under the frozen convention
  (end of first-80 candle), not a post-entry path.

---

## 5. Possession-normalization methodology

Canonical table: one row per possession from PBP event order (OBSERVED basketball
sequence, independent of Kalshi sampling).

Possession ends on: made FG (and-1 FTs stay open), defensive rebound, turnover,
period end. Continues on offensive rebound.

Primary clock = **possession index**. Official clock / elapsed / completion %
describe *where* the game is. Windows `{1,3,5,10,20,30}` possessions are all
computed; none is assumed optimal.

Validation (not silently dropped): duplicate ids = 0; unmapped `ejection` (66);
impossible score jumps flagged (50,751) not dropped; non-monotonic clocks = 0.

---

## 6. Game-to-market alignment methodology

Reuse GPE V2 `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`. Intra-period wall is MODELED.

Candle i covers `(end_period_ts−60, end_period_ts]`.

| Overlay code | Count (all possessions) |
| --- | ---: |
| EXACT_ALIGNMENT | 19,191 |
| MULTI_POSSESSION_CANDLE | 145,013 |
| MULTI_CANDLE_POSSESSION | 57,527 |
| PARTIAL_ALIGNMENT | 3,226 |

A 1-minute candle that covers many possessions is **not** attributed to one
possession.

---

## 7. Feature-store schema

Causal `T_i` at entry: families A–I (game state, possession path, game dynamics /
physics proxies, market state, possession-normalized market path, coupling) plus
secondary candle proxies labeled `CANDLE_DERIVED_MICROSTRUCTURE_PROXY`.

Keys: `observation_id`, `event_id`, `ticker`, `entry_decision_time`,
`possession_id`, `feature_version` implicit in `NBA_RESEARCH_ENGINE_V2_TEST2`.

Labels: `Y_survive_40`, `Y_hit_40`, `Y_settle_yes`, `Y_40_WICK`,
`mae_after_entry_cents` (TARGET_ONLY), `possessions_until_stop` (TARGET_ONLY).

Primary set n=1,169: survive 860, hit 309, settle YES 965.
Median post-entry MAE ≈ −13¢ (possession-overlay proxy). Median possessions
until stop among stoppers ≈ 69.

---

## 8. Correlation analysis

TRAIN only. 141 numeric possession-primary columns. 40 pairs with |Pearson| ≥ 0.9
(mostly nested windows 10p/20p/30p). Rolling windows are nested by construction;
they are not blindly deleted. Spearman and BH-FDR univariate tests are
exploratory (`DISCOVERED AFTER MULTIPLE SEARCHES`).

---

## 9. PCA analysis

Possession-primary TRAIN, robust-scaled:

| PC | Variance |
| --- | ---: |
| 1 | 57.3% |
| 2 | 11.7% |
| 1–2 | 69.0% |
| 1–12 | 88.4% |

PC1 loadings are dominated by `n_window_30p` / `n_window_20p` — **how many
possessions were observed before entry**, i.e. game progress / history length.
That is not an economic “trade class.” Do not interpret PC1 as path-risk.

UMAP was run for visualization only. A pretty embedding is **not** evidence.

---

## 10. Unsupervised clustering results

K-Means K=2 (highest silhouette 0.62 among 2–20; also highest CH among small K):

| Cluster | TRAIN n | TRAIN q (hit-40) | TRAIN survive | OOS n | OOS q |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 56 | 44.6% | 55.4% | 33 | 30.3% |
| 1 | 424 | 26.7% | 73.3% | 198 | 22.7% |

Cluster 0 is a small “early / short-history / high-q” bucket. OOS gap shrinks
(44.6% → 30.3% vs 26.7% → 22.7%). Wilson interval on TRAIN cluster 0 is wide
(32–58% hit-40).

HDBSCAN (min_cluster_size=30): 2 density clusters, 129 noise points. Not a
production taxonomy.

Hierarchical Ward / average / complete at K=4: diagnostic only.

---

## 11. Optimal cluster-number analysis

K was **not** chosen by silhouette peak. K=2–20 were all fit. Higher K inflate
TRAIN q-range by fragmenting n&lt;30 buckets (rejected economically).

Useful structure, if any, is binary: short-history vs the rest. That is mostly
**when** first-80 occurs, not a latent microstructure class.

---

## 12. Cluster stability analysis

- Bootstrap ARI (K=10 search from the first analyze pass) ≈ 0.67 — moderate,
  not a locked taxonomy.
- TRAIN early vs late halves: q 28.3% vs 29.2% (stable base rate).
- K=2 OOS assignment does not preserve TRAIN 18pp gap.
- Walk-forward (below) does not show a stable supervised edge.

---

## 13. Cluster economic comparison

`EV = 1 − 3q`. Unconditional EV ≈ +0.219 R.

K=2 TRAIN cluster 0: EV ≈ −0.34 R, n=56. Too small, too unstable OOS, and
economically it is the **worse** bucket (higher stop rate). Filtering it on TRAIN
would raise survive rate of the remainder only modestly and is not OOS-validated
as a production rule. Frequency: cluster 0 is ~12% of TRAIN — not a rare
curiosity, but still not a confirmed class.

---

## 14. KNN analysis

K=25, distance weights, possession-primary features, K not tuned on OOS.

| Split | Brier | AUC |
| --- | ---: | ---: |
| VAL | 0.191 | 0.584 |
| OOS | 0.192 | 0.563 |

Nearby states have **weakly** similar outcomes (AUC ~0.56–0.58). That is the
neighborhood hypothesis, not a trading filter. Brier is worse than Model 0 VAL
(0.189).

---

## 15. Supervised model comparison vs Model 0

Model 0: q̂ = 26.02%, VAL Brier **0.1892**.

| Model | Features | VAL Brier | VAL AUC | OOS Brier |
| --- | --- | ---: | ---: | ---: |
| Model 0 | none | **0.189** | 0.50 | 0.182 |
| L2 logistic | game state (7) | 0.189 | 0.56 | 0.182 |
| L2 logistic | market state | 0.189 | 0.56 | 0.184 |
| L2 logistic | possession dynamics | 0.201 | 0.52 | 0.191 |
| L2 logistic | candle price path (secondary) | 0.196 | 0.53 | 0.193 |
| L2 logistic | full possession-primary | 0.234 | 0.49 | 0.221 |
| Gradient boosting (depth 2) | full | 0.193 | 0.51 | 0.189 |
| KNN-25 | full | 0.191 | 0.58 | 0.192 |

Simple game-state ≈ Model 0. Complexity makes VAL **worse**.

---

## 16. Ensemble comparison

Equal blend of full L2 + random forest (weights not fit on OOS): OOS Brier 0.194,
worse than Model 0. No VAL-validated ensemble beat the constant.

---

## 17. Feature ablation analysis

Mandatory families (VAL Brier; lower is better):

| Family | VAL Brier vs Model 0 0.189 |
| --- | ---: |
| Game state only | 0.189 |
| Market state only | 0.189 |
| Possession dynamics only | 0.201 |
| Volatility only | 0.193 |
| Candle price path (secondary) | 0.196 |
| Game + market | 0.213 |
| Possession-primary full | 0.234 |
| Possession + candle | 0.240 |

**Where is the information?** Almost none beyond the first-80 rule. Adding
possession windows and coupling **hurts** logistic VAL. Possession-normalized
features did **not** beat arbitrary 1/5/15m candle windows; both fail vs Model 0.

---

## 18. Feature importance

Permutation importance on **VALIDATION** for L2 logistic game-state
(`neg_brier_score`):

| Feature | Mean Δ | Std |
| --- | ---: | ---: |
| estimated_possessions_remaining | +0.0042 | 0.0015 |
| official_time_remaining_s | +0.0019 | 0.0012 |
| score_differential | −0.0010 | 0.0004 |
| quarter | +0.0006 | 0.0005 |

Effects are tiny relative to Brier 0.189. Score differential permuting *improves*
Brier slightly (noise / correlation). SHAP was not required given the null.

---

## 19. Calibration analysis

Game-state logistic VAL ECE **0.040** vs Model 0 ECE **0.007**. Isotonic
calibration was TRAIN-CV only (`l2_logistic_isotonic_cv`); VAL Brier 0.195,
still no win. Platt/isotonic were **not** fit on VALIDATION or OOS.

---

## 20. OOS performance

Frozen OOS after 2026-03-15. No retune.

Game-state logistic OOS Brier 0.182 vs Model 0 0.182 (tie). Full logistic 0.221
(worse). GB 0.189 (worse). KNN 0.192 (worse).

An exploratory `P_survive ≥ 0.70` policy (same as q̂ &lt; 0.30) shows OOS
survive 80% at 58% acceptance. It is **not promoted**: VAL Brier/calibration
gates fail, so the OOS EV bump is treated as an unverified search result
(`DISCOVERED AFTER MULTIPLE SEARCHES`).

---

## 21. Portfolio simulation

Research parameters only (not live MLB):

- Bankroll snapshot $50, 12.5% → $6.25 entry budget
- Max 5 concurrent first-80s
- Observed max same-day first-80s (primary): 14
- Mean same-day: 5.5
- If cap=5: 853 taken / 316 skipped historically
- Weekly primary first-80 rate ≈ 33

No filter is applied. Fees are **not** the production FeeModel.

---

## 22. Trade-frequency analysis

Unfiltered primary first-80 ≈ 33/week. `P_survive ≥ 0.75` acceptance 25% → ~8/week
but fails the ≥50% production acceptance gate. `P_survive ≥ 0.80` is 5% VAL /
2.6% OOS — a handful of trades, not a strategy.

---

## 23. Representative trade replays

Dashboard trade explorer (`frontend/nba-research-engine-v2`, API `:8788`)
splits possession sequences at `ENTRY_DECISION_TIME`. After-entry path is labeled
**not a live feature**.

Example: `KXNBAGAME-25DEC01ATLDET|...-DET|first80` — 39 at-entry possessions,
148 after-entry. Alignment HIGH. Features at entry only.

---

## 24. What worked

- Frozen 1230/910/320 reproduced; Phase 1 gate passed.
- Possession table is an OBSERVED basketball sequence (224,957 rows).
- Honest overlay quality codes; MULTI_POSSESSION_CANDLE is the typical case.
- Leakage audit passed.
- Ablation answered “where is the information?”: nowhere useful beyond first-80.
- Simple models beating complex ones (complexity tax) is a real finding.

---

## 25. What failed

- Unsupervised classes that survive OOS with usable n and EV lift.
- Supervised Brier vs Model 0.
- Coupling / possession-path incremental value.
- Game-state logistic calibration.
- Using 1/5/15m as if they were the game’s clock (they remain sampling artifacts
  and still add no edge).

---

## 26. What is statistically interesting but not actionable

- K=2 “short history / early first-80” vs the rest (TRAIN q gap, OOS shrink).
- PCA PC1 = possession-history length.
- KNN AUC ~0.56–0.58 (weak neighborhood).
- Exploratory OOS EV at `P_survive ≥ 0.70` without confirmatory Brier.

A 74% vs 75% gap would be noise; we did not manufacture 82%/61% classes.

---

## 27. Recommended next experiment

Do **not** add more model families on the same Z. Prefer:

1. True event-time market data (trades/L2) if Kalshi ever provides it — current
   1m candles cannot attribute moves to one possession.
2. Pregame / strength only from information available before tip, if a clean
   source exists.
3. A **restricted** early-game first-80 study (the K=2 leftover) pre-registered
   on a new season, not a search on this OOS.
4. Leave live 80/40 unfiltered.

---

## Spec questions (explicit answers)

1. Meaningful structure in first-80? **Weak descriptive structure only.**
2. Possession-normalized better than clock windows? **Neither beats Model 0.**
3. Market incremental beyond game state? **No on VAL Brier.**
4. Game–market coupling predictive? **No; full stacks overfit.**
5. Unsupervised clusters materially different 80→40? **TRAIN yes (small n); OOS no.**
6. Supervised ML beat unconditional OOS? **No.**
7. Which families contain information? **Almost none; game state ≈ Model 0.**
8. Improve economics at sufficient weekly frequency? **No production candidate.**

---

## Final line

```text
VERDICT B
NO FILTER
```

Negative result is success. Live 80/40 is unchanged.
