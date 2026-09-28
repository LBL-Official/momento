# Lubbock spec v1

Exploratory specification for the Choosin Texas season-progression page.
This file is written before any outcome table. It is not a claim of untouched preregistration.
`LIVE EXECUTION` is false. The page does not submit. Findings are not an execution filter.
Candle path is not a fill. Net EV is `UNAVAILABLE`. No applicable fee model is treated as zero.
No hedge EV.

## Schedule denominator

Warehouse `*_games.json` is the Kalshi game catalog. A canonical `internal_game_id` does not prove that catalog is the league’s full schedule.

In-repo search, once, before ranking: files named like a schedule under `ROLLER/` are `roller/austin/experiments/schedule.py` (a 2-minute game-clock grid) and `roller/auto_roller/scheduler.py` (job timing). Neither is an official league schedule, and neither reconciles game-for-game with the warehouse. No new ingest is started.

Denominator label: `WAREHOUSE_COVERED_PROGRESS`.

Buckets are progression through warehouse-covered games. They are not labeled as the entire sports season. Unobserved official-season buckets stay `UNAVAILABLE`. This `G` is retrospective warehouse metadata.

Schedule completeness and FIRST80 coverage are separate lines on every table. A shared directory name is not evidence that four sports cover the same dates or are complete.

Registered FULL populations stay out of the denominator and are named as coverage limits: NBA 1230, NCAAB P5 721, WNBA 589.

## Season identifiers

Taken from each source’s own season field and from min/max `game_date`, not from the folder name alone.

- NBA: warehouse season `2025-2026`. One analysis season. Calendar year is not a split.
- NCAAB: warehouse season `2025-2026`. The denominator is P5-vs-P5 regular season (`p5_vs_p5 == 1` on canonical `games.csv`, produced from `ROLLER/config/conferences.json`). Other college games in that file are `EXCLUDED_NOT_P5` and are not ranked into these buckets.
- WNBA: calendar year of `game_date`. Canonical trees exist for `2025` and `2026`. Each year is its own `G`. They are not merged into “2025–26.” The warehouse file’s season field `2025-2026` is recorded as the source label only.
- MLB: calendar year of ledger and warehouse `game_date`. The ledger spans calendar 2025 and calendar 2026 even where a path says `2025-2026`. Each year is its own `G`. That span is not the NBA season.

One primary season per sport. Other seasons are sensitivity displays. There is no multi-season pool and no leave-one-season-out result. A single season cannot establish a persistent edge.

WNBA’s primary season is calendar `2025`, declared from membership dates, not from a contrast:

- 2025 regular-season warehouse games run `2025-05-22` through `2025-10-10`.
- 2026 regular-season warehouse games run `2026-04-29` through `2026-08-30` and have no September or October games.

`2026` is sensitivity only. Regular-season FIRST80 counts are 120 in 2025 and 126 in 2026. Those counts are not the selection rule, and the sign of either year’s contrast is not the selection rule.

MLB’s primary season remains calendar `2025` (2197 regular-season ledger rows; 2026 has 2106). That choice is the larger membership count, not an effect. `2026` is sensitivity.

## Universes

Membership is joined to season rank. Counts are asserted and not rewritten. No new warehouse FIRST80 scan.

- Asked-six FIRST80 **1182** (`research/first80_asked_six_chatgpt_export/first80_asked_six.csv`), reported by sport: NBA 604, NCAAB 332, WNBA 246.
- Derived four **936** (NBA 2Q/3Q 604 + NCAAB H1_2/H2_1 332).
- Austin/Dallas NBA 2Q∪3Q **604**. The NBA rows inside derived-four 936 and asked-six NBA are the same membership. One measurement, shown as an identity check. Not two Holm tests.
- MLB `mlb_first80_80_40_v1` (`ledger_baseline.json`) is a separate research ledger. Nominal entry 0.80. It is not a Choosin lock and it is not live 80/81/89.

Primary universe for the four Holm tests, chosen here:

| Sport | Universe | Role |
| --- | --- | --- |
| NBA | Austin/Dallas 604 | Holm |
| NCAAB | Derived-four H1_2∪H2_1, 332 | Holm |
| WNBA | Asked-six 2Q∪3Q, 246 | Holm |
| MLB | `mlb_first80_80_40_v1` regular-season ledger rows | Holm |

Every other slice is a sensitivity or identity display.

## Rank, then FIRST80

Within one sport × analysis season × phase, rank warehouse-covered games before any FIRST80 filter.

Fields: `season_phase`, `event_ticker`, `game_date`, `scheduled_start`, `event_status`, joined to canonical `games.csv` on `event_ticker` for `internal_game_id`, and for NCAAB `p5_vs_p5`.

One row per `internal_game_id` when that id exists; otherwise one row per `event_ticker`. Sort by actual start when present, else `scheduled_start`, else `game_date` at `T00:00:00Z`, then `internal_game_id` bytes (else `event_ticker` bytes). NBA has many missing starts. NCAAB starts are absent in the current canonical snapshot. The fallback is stored on the assignment and shown on the page.

League-local date is `America/New_York` when a timestamp exists; otherwise the stored `game_date`.

A timestamp at `T00:00:00Z` on the stored `game_date` is the date fallback, not a tip time. NCAAB canonical `actual_start` is that sentinel on every row, so NCAAB rank uses `game_date`. Other clocks, including warehouse `scheduled_start`, are real start times.

`event_status` is Kalshi lifecycle, not a postponement flag. There is no postponed or canceled column. Duplicates collapse on `internal_game_id` or `event_ticker`.

Regular season is primary. Playoffs, play-in, finals, and NCAAB `NCAA_TOURNAMENT` are phase `POSTSEASON` and are not folded into the last regular-season decile. Preseason is phase `PRESEASON`. If a phase has too few ranked games to form the predeclared contrast, that phase is `INSUFFICIENT_DATA`.

`season_progress = (game_rank − 0.5) / G`, with `G` the warehouse-covered count for that sport, season, and phase.

Disjoint deciles (10) and quintiles (5) are equal-count buckets. Sizes differ by at most one. Extra games go to the earliest buckets. Each bucket stores id, numeric progress bounds, rank bounds, and actual date range.

Final 10% is the last decile. Preceding 90% is every earlier decile. Final 20% is the last quintile. Preceding 80% is every earlier quintile.

Cumulative checkpoints (first 10%, 20%, …, 100%) overlap. They are not independent samples. The whole-season row is the 100% checkpoint.

If the warehouse-covered list is not a finished league season, the latest games are not renamed as unobserved 90–100% of an official season. The page states that this `G` is retrospective warehouse metadata.

For incomplete or completeness-unknown seasons, warehouse-relative deciles remain descriptive. Official-season final-10% and final-20% contrasts are `UNAVAILABLE` unless a full-season schedule denominator establishes those boundaries.

This run’s denominator is `WAREHOUSE_COVERED_PROGRESS`, so every sport’s official-season final-10% and final-20% contrast is `UNAVAILABLE`. Holm uses the four warehouse-relative last-10% versus preceding-90% legacy gross-EV contrasts, one per declared primary season. Those labels refer to legacy flags. They are not the league’s final decile.

Date-preserving sensitivity: reassign every game on a shared league-local date into the bucket of that date’s first game, and recompute the primary contrast. Same-date splits are not hidden when start times are missing. This sensitivity does not replace the primary label.

Observations whose event is absent from the ranked catalog are `SCHEDULE_UNJOINED`. They stay in the exclusion count. They are not forced into a bucket and they are not deleted from the lock display.

## Path status

Legacy T40 stays the locked rule.

- Basketball asked-six CSV: `T40` is true when `post_entry_min_yes_bid_cents ≤ 40` after entry. The stored boolean is checked against that column when the column is present.
- MLB ledger: `stop_triggered`.

A stored `T40=False` does not prove the post-entry path was fully observed. Each row has `evaluation_status` separate from the legacy flag. These artifacts store a legacy flag and a post-entry minimum. They do not show a contiguous path through settlement or through the first T40 print. Every row in this run is `PATH_COMPLETENESS_UNVERIFIED`. Legacy cells are still reported. The run does not claim the incomplete-path check passed. A missing exit timestamp does not separate “stop never printed” from “the rest of the path is absent.”

No warehouse bar scan is used to pass that check.

Four terminal/path cells require both a valid settlement and a valid T40 flag. A flag without settlement is not a path cell. Terminal-only measurements, including the YES rate, may use the larger settlement denominator. Loss without T40 is kept even when a lock has `s_L = 0`. The four cells are legacy classifications because path status is `PATH_COMPLETENESS_UNVERIFIED`.

Time-to-T40 is not a survival curve. Post-entry min and exit timestamp stay descriptive when present.

## Measurements

Per sport × universe × phase × bucket:

- Warehouse-covered `G`, schedule completeness on its own line, market-linked games, FIRST80 rows, legacy-evaluable rows, `PATH_COMPLETENESS_UNVERIFIED` rows, `SCHEDULE_UNJOINED`, missing settlement.
- Observed entry bid distribution and entry period from the CSV. MLB entry is nominal 0.80, so observed-price calibration for MLB is `UNAVAILABLE`.
- Terminal: YES settlement rate, gap versus 0.80, mean observed entry, calibration residual `mean(outcome − entry_price_dollars)`, Brier score on the observed entry. Nominal 80¢ economics stay in a separate column from overshoot prices.
- Gross EV from the explicit payoff, recomputed from row outcomes, in cents per contract:
  - stop: −40¢
  - YES and no stop: +20¢
  - NO and no stop: −80¢
  - `EV = 20·P(win∧¬T40) − 40·P(T40) − 80·P(loss∧¬T40)`
- The shorthand `60·P(¬T40) − 40` is stored only as a legacy identity check, and only interpreted where loss-without-T40 is zero. It does not overwrite explicit EV.
- Hold-to-settlement gross EV on the nominal 80¢ book is `+20` if YES else `−80`, labeled separately from the stop rule. Stop-versus-hold and late-versus-earlier differences are both shown.
- Net EV: `UNAVAILABLE`.

## Contrasts

Fixed before the tables. The breakpoint is not chosen from the outcomes.

- Warehouse-relative primary: last 10% of warehouse-covered games minus the preceding 90%, 80→40 gross EV (cents per contract). Hypothesized side: positive. This is descriptive progress through the covered catalog.
- Official-season final 10% and final 20%: `UNAVAILABLE` under `WAREHOUSE_COVERED_PROGRESS`.
- Warehouse-relative secondary: last 20% minus the preceding 80%, same EV. Exploratory relative to Holm.
- Supporting: warehouse-relative last 10% minus preceding 90%, P(T40), on the path-cell denominator. Not used to pick a breakpoint. Not in Holm.
- Terminal YES rate, same warehouse-relative cut, uses the settlement denominator. Not used to pick a breakpoint. Not in Holm.

**Supported in this sample** requires a positive primary contrast, its 95% interval entirely above zero, and Holm-adjusted p ≤ 0.05. **Contradicted in this sample** requires the corresponding negative result and Holm-adjusted p ≤ 0.05. Otherwise, **inconclusive**. Findings using unverified paths explicitly refer to legacy classifications. Holm is only the four warehouse-relative primary EV contrasts. Other cuts stay exploratory and are not called supported or contradicted.

## Uncertainty

- Wilson 95% intervals on rates. `n = 0` is `UNAVAILABLE`, not zero.
- Blocks are consecutive **active game dates** (a league-local date with at least one ranked game in that comparison group). They are not calendar dates that include off days.
- Primary block length is 1 active date. Sensitivity uses blocks of 3 and of 7 consecutive active dates inside each group. If a group has fewer active dates than the block length, that sensitivity is `UNAVAILABLE`.
- Within each comparison, resample chronological blocks inside the late group and inside the earlier group. Every observation on a sampled date stays in that replicate, with multiplicity if a date is drawn more than once. The contrast is computed inside the replicate.
- `B = 2000`. The 95% percentile interval uses the ordered replicates at 1-based ranks 50 and 1950.
- Holm uses a separate p-value, not the percentile interval. For an observed contrast `c`, recenter each replicate as `c* − c` and set `p = (1 + count(|c* − c| ≥ |c|)) / (B + 1)`, two-sided.
- Holm is applied only to the four warehouse-relative primary EV contrasts (regular season, declared primary season, primary universe, block length 1). Other cuts are exploratory.
- Report distinct active dates in the late group and in the earlier group. Distinct is a count. Independence is not assumed. The block lengths 3 and 7 examine dependence. Two thousand draws do not add information beyond that date count.
- Bootstrap seed is `604`. Each named stream uses `Random(604 xor crc32(stream_name))` so the draw does not depend on call order.
- Contrasts of integer-cent payoffs are stored at a scale of one-millionth of a cent per contract, from integer sums, then rendered as decimal strings.

## Entry bands and adjustment

Defined here, before any outcome table.

Bands are the observed bid relative to 80: `80`, `81–83`, `84+`. A bid below 80 is `BELOW_80` and is outside the three bands. MLB nominal 0.80 has one band, `80`.

The estimator is a common-support standardization. Cells are band × entry period from the CSV (`UNSPECIFIED` when the file has no period). Cells with no earlier rows or no late rows are `UNSUPPORTED_STRATUM` and are not filled by extrapolation. After those cells are removed, late-group weights are renormalized over the retained strata. Both the late mean and the earlier mean are computed with those same weights. Report the retained share of the late group and the retained share of the earlier group. Cells with fewer than 5 rows on either side are `SPARSE_STRATUM`; they stay in the retained set when both sides are nonempty, and they are flagged. Show the raw difference and the standardized difference, each with the percentile interval at block length 1. No post-entry or settlement covariates.

The standardized contrast is recomputed inside each bootstrap replicate on the original sample’s retained strata. A replicate is invalid when any retained stratum has no late rows or no earlier rows. Invalid replicates are not renormalized onto a smaller support. They are counted and excluded from the percentile interval and from the p-value. If 2000 valid replicates are not obtained, the standardized interval is `UNAVAILABLE` and the invalid-replicate count is still reported.

> **Interpretation and adjusted sensitivity:** Terminal calibration, terminal win rate, and path survival are separate outcomes. A higher late-season win rate does not necessarily indicate better calibration. Define entry-price bands and the adjustment estimator before inspecting outcomes. Compare late and earlier observations over common entry-price/period support, report unsupported or sparse strata, and show both raw and standardized differences with uncertainty. Do not extrapolate across empty strata. Classify results from effect estimates and intervals—not the sign of a point estimate alone. A positive but imprecise estimate is inconclusive; “contradicted in this sample” requires evidence of an effect in the opposite direction.

## What this run does not do

- Does not edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, warehouse Phase 21, or W9.
- Does not start or stop `momento-live.service` and does not set `VITAL_AWS_CONTROL`.
- Does not open sealed Austin confirmation cohorts and does not hash those files. Non-access is the code path. `book.json` is hashed only to show it was not edited.
- Does not invent N, fills, L2, or fees.
