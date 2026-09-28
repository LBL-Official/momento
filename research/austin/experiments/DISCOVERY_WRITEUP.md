# Austin Discovery Write-Up

**Suite:** `AUSTIN_NCAAB_TRANSFER_V1`  
**Date of run:** 2026-09-18  
**Cohort:** DISCOVERY only  
**POLICY STATUS:** UNFROZEN  
**CONFIRMATION:** NOT RUN  
**LIVE FEED:** UNAVAILABLE  
**EXECUTION:** DISABLED  
**FILL:** FILL_UNAVAILABLE  
**FEE_MODEL:** UNAVAILABLE  

This is the human-readable discovery memo for the pre-registered NCAAB transfer test. It does not select a policy. It does not write `POLICY_FREEZE.json`. It does not combine Experiment A and Experiment B into one out-of-sample headline.

Machine artifacts remain the authority for exact floats: each member’s `discovery/statistics.json`, ledgers, `warning_time.csv`, `equity_curves.csv`, `REPORT.md`, and `STOP_REPORT.txt`.

---

## What was asked

Does a frozen NBA Austin model — Choosin 2Q/3Q N=604, K=25, EV = hold-80-to-settlement — contain forward-looking information about remaining hold-to-settlement economics when queried on locked NCAAB First-80 entries at every two game-clock minutes?

The test is cross-domain. NCAAB did not enter training, PCA, scaler, or kNN. Page 3 N=280 is display-only and was not queried. H2_2 is forbidden and contributed 0 rows.

Two members, never pooled:

| Member | Slice | Locked N | Discovery | Confirmation (unread) |
| --- | --- | ---: | --- | --- |
| A `NCAAB_H1_2_AUSTIN_TRANSFER_V1` | H1_2 | 193 | 96 trades / 96 games | 97 / 97 |
| B `NCAAB_H2_1_AUSTIN_TRANSFER_V1` | H2_1 | 139 | 69 trades / 69 games | 70 / 70 |

Split is temporal `floor(G/2)` unique games, sorted by `game_date`, `entry_timestamp`, `internal_game_id`. Written before any Austin query.

---

## Locks that held

**Model.** `austin_v2` / `choosin_nba_2q3q_604` / 48,752 snapshots / K=25 / Euclidean PCA. `ncaab_used_for_*=false`. Artifact hashes unchanged. `model_manifest_hash=4a47bf9ad3a2fcd4bb092a77cf93d534e308423deec29e33b6e6bad85c76431c`.

**Code pin.** `git_commit=UNAVAILABLE`, `git_commit_status=UNAVAILABLE`, `git_commit_reason=not_a_git_repo`. The working tree is not a git repository. The reason is persisted. The model lock is the five sha256 values, not the commit.

**Cohort hashes (game_id + trade_id only; settlement ISO rewrite did not change them).**

- A discovery `f7bc6280913c63a2a50cb5181b0c523c5492bbdb47da167d9639e2f867a87e36`
- A confirmation `4bc027bddba0f723b914b2d80e0ff49ae0eb0bff94711860e310737941e0f0e4`
- B discovery `699e6bb65fe4fa3dffc566b352f089c109ffadfb501b830e2c129f2e66450840`
- B confirmation `1ce8a0b2f3d3ee88d34cb0e4833cf3369aa776fc75bff912d7e2f3b2a4173c51`

**Date boundaries.**

- A discovery 2025-11-09 → 2026-01-27; confirmation 2026-01-28 → 2026-04-04
- B discovery 2025-11-07 → 2026-02-11; confirmation 2026-02-11 → 2026-04-02

**Entry source.** `ASKED_SIX_FIRST80`. Entry price is the asked-six yes bid, not a reconstructed First Touch.

**Settlement timestamps.** Asked-six stored unix seconds. Those were normalized to UTC ISO before grids. `AFTER_SETTLEMENT` now fires (18 A grid rows, 10 B).

**Grid before Austin.** `--stage grid` wrote full PRIMARY_GRID + PRE_ENTRY + AFTER_SETTLEMENT + DIAGNOSTIC_EVENT rows with zero `query_match` calls.

| Grid role | A rows | B rows |
| --- | ---: | ---: |
| PRIMARY_GRID | 1345 | 546 |
| PRE_ENTRY | 768 | 975 |
| DIAGNOSTIC_EVENT | 311 | 205 |
| AFTER_SETTLEMENT | 18 | 10 |
| NO_PBP | 2 | 2 |
| Total | 2444 | 1738 |

Diagnostics are never `primary`. They cannot arm a policy.

**Integrity.** Leakage audit: mutate bars/PBP after t, rebuild features at t — PASS, 5/5 trades, 0 failures. Self-neighbor: NCAAB `trade_id` overlap with the 604 snapshot matrix — PASS, empty overlap (96 and 69 vs 604). `submits=false`.

---

## How to read the economics

**BASELINE_HOLD** is primary: +20 if the contract won, −80 if it lost. This is settlement hold, not 80/40.

**BASELINE_8040** is secondary and is not the headline.

**Austin EV** is kNN conditional expected remaining hold-to-settlement PNL, cents, K=25, 95% weighted-bootstrap CI. `EV_entry` is the first valid PRIMARY_GRID EV on that trade and is immutable.

**Policy PNL** is Scenario B: if the policy says INTERVENE at the first armed primary checkpoint, replace remaining hold with a hypothetical next-1-minute close. That is a scenario. It is not an observed fill. Fees are UNAVAILABLE and were not subtracted.

**Clustered CI.** Cluster = `internal_game_id`. seed=80. B=1000. Checkpoints are not independent bets. A CI that includes 0 does not support a claim that the policy beat or lost to hold.

Classifications used below are only `SUPPORTED | MIXED | NOT_SUPPORTED | INSUFFICIENT_SAMPLE`.

---

## Experiment A — H1_2 discovery

Locked slice N=193. Discovery 96 games, 96 trades (one trade per game in this split). Hold reconstruction: 81 wins, 15 losses.

**BASELINE_HOLD.** EV +4.375¢. Median +20. Total +420¢. P10 −80. Max drawdown on chronological hold −280¢.

**Coverage.** Path complete 22 / partial 74 / unavailable 0. Primary grid rows 1,345. Valid Austin VALUE rows 1,453 (includes some diagnostic VALUE rows). Valid primary states used for ordering: 1,167. LOW_HISTORICAL_SUPPORT states: 44. Those rows stayed in the experiment. Distance is not confidence.

**Ordering / signal — SUPPORTED.**

| State class | n | Mean subsequent hold ¢ |
| --- | ---: | ---: |
| EV < 0 | 517 | +2.79 |
| EV ≥ 0 | 650 | +5.54 |
| EV − EV_entry ≤ −8¢ | 453 | +2.56 |
| Otherwise | 714 | +5.43 |
| First negative EV, subsequent hold | 67 | −0.90 (median still +20) |

Negative-EV states have worse mean remaining hold than non-negative. The gap is small relative to the +20/−80 payoff. Median realized hold in most EV bands is still +20: the signal is moving the mean, not flipping the typical trade.

**Calibration — MIXED.** Code flag `SEPARATED` because the leftmost band mean (−3.15) is below the rightmost (+6.27) among bands with n≥5. Interior bands are not monotone.

| Predicted EV band | n | Mean predicted | Mean realized hold | Median realized |
| --- | ---: | ---: | ---: | ---: |
| < −10¢ | 298 | −31.69 | −3.15 | +20 |
| −10 to 0¢ | 219 | −5.00 | +10.87 | +20 |
| 0 to +5¢ | 109 | +2.82 | +2.57 | +20 |
| +5 to +10¢ | 75 | +8.07 | +5.33 | +20 |
| > +10¢ | 466 | +16.26 | +6.27 | +20 |

Predicted magnitude is larger than realized magnitude on both tails. The < −10¢ band does not produce mean −30 hold. The > +10¢ band does not produce mean +16 hold.

**Warning time — NOT_SUPPORTED as an actionable lead-time tool.**

| Class | n |
| --- | ---: |
| WARNING_AVAILABLE | 5 |
| WARNING_TOO_LATE (price ≤42 or T40 already) | 62 |
| NO_WARNING | 29 |
| PATH_UNAVAILABLE | 0 |

Median minutes among AVAILABLE+TOO_LATE = 20 (P25=18, P75=20). Median among losers with AVAILABLE = UNAVAILABLE (not zero). Mean adverse cents remaining after first negative EV = 13.4. First negative EV is usually late. A 20-minute clock figure that is almost entirely TOO_LATE is not a usable early warning.

**42/41 diagnostic.** First ≤42: 28. First ≤41: 28. Same bar 42 and 41: 25. 42 without 41: 3. Trigger resolution remains 1-minute close. Most 42 prints are the same bar as 41.

**Policy table, Scenario B. No winner.** Every clustered 95% CI includes 0. Every mean Δ vs hold is negative. Intervention is frequent. Winners abandoned exceed losses avoided on every row.

| Policy | Rule | Rate | n INTERVENE | Hold EV | Policy B EV | Δ ¢ | Clustered 95% CI | Policy DD | P10 | Avoided | ¢ saved | Abandoned | ¢ sacrificed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | EV < 0¢ | 69.8% | 67 | +4.38 | +2.36 | −2.01 | [−8.30, +4.59] | −175 | −23.5 | 14 | 804 | 53 | 997 |
| B | EV < +2¢ | 72.9% | 70 | +4.38 | +1.88 | −2.50 | [−8.71, +4.11] | −200 | −23.5 | 14 | 804 | 56 | 1044 |
| C | EV < +5¢ | 78.1% | 75 | +4.38 | +2.01 | −2.36 | [−8.74, +4.54] | −201 | −23.5 | 14 | 827 | 61 | 1054 |
| D | EV − EV_entry ≤ −8¢ | 62.5% | 60 | +4.38 | +2.16 | −2.22 | [−7.12, +2.96] | −201 | −48.5 | 14 | 512 | 46 | 725 |
| E | EV < 0 and upper CI < 0 | 43.8% | 42 | +4.38 | +2.43 | −1.95 | [−7.29, +3.70] | −167 | −28.5 | 12 | 591 | 30 | 778 |
| F | EV < 0 and CI crosses 0 | 44.8% | 43 | +4.38 | +1.56 | −2.81 | [−7.44, +2.20] | −222 | −53.5 | 6 | 367 | 37 | 637 |

Hold chronological DD is −280¢. Several policies cut DD and P10. That is a path-shape observation, not a selected result. Cents sacrificed exceed cents saved on every policy.

**A claim set.**

- Ordering of Austin EV vs subsequent hold: **SUPPORTED**
- Useful early warning before T40 / late price: **NOT_SUPPORTED**
- Any POLICY_* beats hold on discovery ΔEV CI: **NOT_SUPPORTED**
- Confirmation generalization: **NOT RUN**

---

## Experiment B — H2_1 discovery

Locked slice N=139. Discovery 69 games, 69 trades. Hold reconstruction: 57 wins, 12 losses.

**BASELINE_HOLD.** EV +2.609¢. Median +20. Total +180¢. P10 −80. Max drawdown on chronological hold −340¢.

**Coverage — this is the binding constraint.** Path complete 0 / partial 63 / unavailable 6. Primary grid rows 546. Valid Austin VALUE rows 311. Valid primary states used for ordering: **117**. LOW_HISTORICAL_SUPPORT: 0. Six trades have no usable path. Zero trades have a complete VALUE path on every primary checkpoint. H2_1 starts later in the game; PRE_ENTRY consumes 975 of 1,738 grid rows. Do not read B as if it had A’s state density.

**Ordering / signal — SUPPORTED, small valid-n.**

| State class | n | Mean subsequent hold ¢ |
| --- | ---: | ---: |
| EV < 0 | 39 | −38.97 |
| EV ≥ 0 | 78 | +16.15 |
| EV − EV_entry ≤ −8¢ | 18 | −41.11 |
| Otherwise | 99 | +4.85 |
| First negative EV, subsequent hold | 22 | −34.55 (median −80) |

The negative-EV bucket is actually losing on average. That is a stronger state-level separation than A. It sits on 39 states, not 39 independent games, and on a cohort with 0 complete paths.

**Calibration — MIXED.** Code flag `SEPARATED` (leftmost −41.76 vs rightmost +20). The +5 to +10¢ band realizes −5¢ (n=8). The −10 to 0¢ band is n=5.

| Predicted EV band | n | Mean predicted | Mean realized hold | Median realized |
| --- | ---: | ---: | ---: | ---: |
| < −10¢ | 34 | −50.46 | −41.76 | −80 |
| −10 to 0¢ | 5 | −3.30 | −20.00 | +20 |
| 0 to +5¢ | 9 | +1.76 | +8.89 | +20 |
| +5 to +10¢ | 8 | +6.63 | −5.00 | +20 |
| > +10¢ | 61 | +18.72 | +20.00 | +20 |

The far-left and far-right bands line up better than A. The middle does not. Sample is thin.

**Warning time — NOT_SUPPORTED.**

| Class | n |
| --- | ---: |
| WARNING_AVAILABLE | 0 |
| WARNING_TOO_LATE | 22 |
| NO_WARNING | 47 |
| PATH_UNAVAILABLE | 0 |

There is no AVAILABLE warning. Median minutes among TOO_LATE = 3 (P25=0, P75=5.5). Losers AVAILABLE median = UNAVAILABLE. Mean adverse remaining = 5.2¢. First negative EV, when it exists, is already late in a second-half entry.

**42/41 diagnostic.** First ≤42: 18. First ≤41: 17. Same bar: 14. 42 without 41: 4.

**Policy table, Scenario B. No winner.** Every clustered 95% CI includes 0. Point Δ vs hold is positive. Intervention is less frequent than A. Losses avoided can exceed winners abandoned in count (A/B/C/E), and cents saved exceed cents sacrificed on those rows. That is a discovery point estimate on a partial-path cohort. It is not confirmation.

| Policy | Rule | Rate | n INTERVENE | Hold EV | Policy B EV | Δ ¢ | Clustered 95% CI | Policy DD | P10 | Avoided | ¢ saved | Abandoned | ¢ sacrificed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | EV < 0¢ | 31.9% | 22 | +2.61 | +4.36 | +1.75 | [−2.46, +6.57] | −290 | −66 | 12 | 308 | 10 | 187 |
| B | EV < +2¢ | 36.2% | 25 | +2.61 | +4.43 | +1.83 | [−2.49, +6.78] | −291 | −66 | 12 | 316 | 13 | 190 |
| C | EV < +5¢ | 37.7% | 26 | +2.61 | +4.06 | +1.45 | [−2.80, +6.62] | −291 | −66 | 12 | 316 | 14 | 216 |
| D | EV − EV_entry ≤ −8¢ | 13.0% | 9 | +2.61 | +3.54 | +0.93 | [−1.79, +4.54] | −299 | −80 | 4 | 144 | 5 | 80 |
| E | EV < 0 and upper CI < 0 | 24.6% | 17 | +2.61 | +4.59 | +1.99 | [−2.22, +6.78] | −290 | −66 | 12 | 304 | 5 | 167 |
| F | EV < 0 and CI crosses 0 | 10.1% | 7 | +2.61 | +3.88 | +1.28 | [−0.46, +3.70] | −340 | −80 | 3 | 107 | 4 | 19 |

**B claim set.**

- Ordering of Austin EV vs subsequent hold: **SUPPORTED**
- Useful early warning: **NOT_SUPPORTED**
- Any POLICY_* beats hold on discovery ΔEV CI: **NOT_SUPPORTED** (point Δ positive; interval includes 0)
- Coverage adequate for a confirmation-ready path product: **NOT_SUPPORTED** (0 complete paths)
- Confirmation generalization: **NOT RUN**

Do not combine B with A as a headline OOS result.

---

## What the two discoveries agree on

1. Frozen NBA-neighbor EV is not noise relative to subsequent hold. Ordering is SUPPORTED on both members.
2. Warning-as-early-exit-clock is not supported. A is mostly TOO_LATE. B has zero AVAILABLE.
3. No pre-registered policy has a clustered CI that excludes 0 versus BASELINE_HOLD.
4. Scenario B is not a fill. Fees are not in the EV.
5. Page 3 6.7143¢ / 218/280 / book 1880¢ remains a control display. It was not this test.

## Where they disagree (and must stay separate)

A is a first-half entry universe with dense post-entry grid (1,167 valid ordering states) and a small positive hold EV. Policies intervene often and, on Scenario B, give back more winner cents than they save.

B is a second-half entry universe with a thin valid grid (117 states, 0 complete paths). Negative EV states are actually bad. Policies intervene less. Point Δ vs hold is positive and still inside a CI that includes 0.

That is two different games, two different clocks, two different missingness patterns. Averaging them would invent a third experiment that was not pre-registered.

---

## What Austin adds

A frozen, already-fit NBA snapshot matrix and a predetermined 2-minute NCAAB clock grid. At each eligible checkpoint: reconstructible state, kNN EV, CI, support flag, remaining hold target, and a pre-registered INTERVENE/NONE decision that cannot be re-tuned on these numbers.

It does not add a live quote, a fill, a fee, an NCAAB-native model, or a 2026–27 NBA prospective result.

## What has not been proven

- That any POLICY_* should be frozen.
- That Scenario B would have been executable.
- That confirmation will repeat discovery sign or magnitude.
- That H2_1 coverage is sufficient for a path product.
- That warning time is early enough to matter.
- That Austin works on live NBA, live NCAAB, or Page 3’s 280-row book.

## Whether the evidence justifies the next validation stage

Discovery evidence alone cannot establish generalization. It can justify a human reading A and B as separate cards and selecting exactly one pre-registered policy — or selecting none and stopping.

If a policy is selected, freeze is suite-level and confirmation is read once per member. Confirmation capability exists in the CLI and was not invoked.

```text
DISCOVERY COMPLETE
POLICY STATUS = UNFROZEN
CONFIRMATION A = NOT RUN
CONFIRMATION B = NOT RUN
NEXT REQUIRED ACTION = HUMAN SELECTS EXACTLY ONE PRE-REGISTERED POLICY
```

After an explicit choice of POLICY_A…F:

```bash
python -m roller.austin.experiments.run --suite AUSTIN_NCAAB_TRANSFER_V1 --stage freeze --policy POLICY_X
python -m roller.austin.experiments.run --experiment NCAAB_H1_2_AUSTIN_TRANSFER_V1 --stage confirmation
python -m roller.austin.experiments.run --experiment NCAAB_H2_1_AUSTIN_TRANSFER_V1 --stage confirmation
```

`--stage all` remains forbidden. Experiment-local `POLICY_FREEZE.json` remains forbidden.

Discovery numbers above are unchanged. The follow-on discovery-only mechanism audit is:

`research/austin/experiments/AUSTIN_PERSISTENCE_MECHANISM_AUDIT_V1/REPORT.md`
