# NBA Bot 001 selection protocol

Written 2026-09-22, before the ranking replay. This file fixes the portfolio, the fee, the confidence calculation, and the decision rule. The replay reads these rules. It does not revise them after seeing the bound.

`LIVE EXECUTION` stays false. The replay does not submit orders and does not write `VITAL_AWS_CONTROL`.

## Identity

One bot. Display name NBA Bot 001. Folder `research/vital/bots/nba-001/`. Canonical id `nba-001`. Alias `nba-first80-001` on the existing execution contract. Series `KXNBAGAME`. Research bankroll is the Austin mark of 2,000,000 cents. It is not a live account and not the MLB $50 book.

## Universe

Ranking tape: locked NBA 2Q∪3Q FIRST80, N=604, S=450/604. Slices inside that lock: 2Q N=314, 3Q N=290. Window 2025-10-10 through 2026-06-13, phases PRESEASON, REGULAR_SEASON, PLAYOFFS, FINALS.

The registered book pathname `nba_2q_regular_8040_1lot_2026_27` is not a 2026–27 observation sample. `tape_season` is `2025-26`. `measure_season` is `2026-27`. The `nba_2q_regular` window is 2025-10-22 through 2026-04-12, regular season only, N=280, S=218/280. Those 280 rows are not pooled into 604.

Out of the ranking pool: asked-six 1182, derived four 936, NBA FULL 1230, jump-filtered 1208, path-FE, DRE Phase 5 (`NO_POLICY_FROZEN`), Ballhog, and TK Ultra. Austin confirmation A (N=97) and B (N=70) stay `SEALED_UNSPENT`. Their outcome files are not opened.

Splits already used on this tape (IN_SAMPLE, VALIDATION, OOS) are not renamed into a fresh out-of-sample claim.

## Candidates

Four, already defined. No new time, lead, or price buckets.

1. `union` — unfiltered 80 entry / 40 stop on N=604. Canonical baseline.
2. `q2` — the same rule on the locked 2Q slice.
3. `q3` — the same rule on the locked 3Q slice.
4. `hedge` — the documented 41–42 trigger and opponent-YES maker near 40. Diagnostic only.

If the 2Q or 3Q lower bound is not strictly above the union lower bound, the candidate stays the union.

The hedge cannot win. `FILL_UNAVAILABLE` means a favorable theoretical opponent fill is not a selection input. The no-fill path exits the favorite reduce-only at the first later tradable YES bid close at or below 40, at that close, and pays the taker fee on that exit. If that close is not stored as its own print, the conservative proxy is `post_entry_min` when it is at or below 40, labeled `POST_ENTRY_MIN_NOT_FIRST_CLOSE`. If no such close appears, the position stays open until settlement on the same candle basis, and that path is reported separately. Hedge cash is not reserved at favorite entry.

## Portfolio

Integer cents. One chronological pass, then the bootstrap. No second pass that changes the rules.

- Starting cash: 2,000,000 cents.
- Equity at a decision: settled cash, plus hedge reserves still held as cash, plus open YES positions marked at the latest tradable YES bid at or before that timestamp.
- A missing bid is `MARK_UNAVAILABLE`. A bid older than 180 seconds before the decision is `STALE_MARK`. Either blocks that entry. Neither is stored as $0.
- Entry budget is 4% of that equity: `budget_cents = (equity_cents * 4) // 100`. This is an expenditure cap, not a loss budget, and it is not 4% per hedge leg.
- Contract count starts at `budget_cents // entry_price_cents`, then decreases until `contracts * entry_price_cents + entry_fee_cents` fits both the budget and free cash. Free cash excludes hedge reserves. If one contract does not fit, the signal is skipped.
- At most five lifecycles. Statuses `pending`, `partial`, `unknown`, `open`, and `working` occupy a slot until the exposure and working orders are terminal. A hedge on the same game is the same lifecycle.
- One entry per `game_id`. No re-entry. `game_id` is the warehouse `internal_game_id` on the locked row. Simultaneous signals sort by decision timestamp, then by `game_id` ascending UTF-8 bytes. The sort does not use the outcome.
- Hedge reserve, when a hedge is attempted: `hedge_contracts * 40 + hedge_fee_cents`, checked atomically at the hedge-trigger timestamp. If free cash cannot cover it, the hedge is not placed and the favorite uses the fallback exit. The 4% favorite cap is not increased to prefund the hedge. The reserve releases when the hedge order is terminal and any hedge position is closed or settled.
- Week boundary: America/New_York, Monday 00:00. A position open across that boundary contributes its mark-to-market change to each week it spans. Entry-week utilization still counts the decision week. Zero-trade weeks stay in the mean. Preseason, regular season, playoffs, and finals are reported as separate realized-cent totals. The selection mean is the full calendar.
- Settlement cash posts in the week of the settlement timestamp on the locked row, not the entry week.
- Where the one-minute tape does not contain the first close at or below 40, the replay does not invent an intra-minute print or an L2 fill.

The unit check (exact 80 entry, exact 40 exit, no fees: win about +1% of equity, stop about −2%) is a sanity check only. It is not the ranking metric.

## Fees

Source read 2026-09-22:

- https://docs.kalshi.com/getting_started/fee_rounding
- https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes

The venue rule used for the ranking bound:

- Taker model fee: `0.07 * contracts * P * (1−P)`, P in dollars.
- Maker model fee: `0.0175 * contracts * P * (1−P)` when maker fees apply.
- The model fee is rounded up to the next $0.000001.
- Non-direct member cash is then aligned up to the next cent. The fee in cents is that aligned debit minus the contract notional. The same cent alignment is subtracted from sale proceeds.
- Settlement is not a matched order. The ranking charges no settlement trading fee. A settlement fee is not invented to match a sentence that assumed one function for every cash event.

`KXNBAGAME` maker multiplier was not read from `GET /series/fee_changes` (no live fee call in this ranking). It is `UNAVAILABLE`. The selection bound uses maker multiplier 1, so entry pays the maker fee. Multiplier 0 is a sensitivity and is not the selection fee.

The research sentence “round half away from zero to the cent” is not the venue rule. Half-away is computed only as a labeled sensitivity.

## Two layers

Every table keeps them apart.

- Candle-path theoretical: entry at the observed YES bid close, exit at 40 cents when `t40` else YES settlement at 100. This is not a fill.
- Conservative executable scenario: a maker bid at 80 is `INFEASIBLE_MAKER` when the triggering close is already above 80. Eligible rows enter at 80. A `t40` exit uses `post_entry_min` when it is at or below 40. Otherwise the row settles on the candle basis. Fees use maker multiplier 1 and the taker schedule on the stop.
- Observed live fills: `UNAVAILABLE`.

The selection bound is the conservative layer. The theoretical layer is reported and cannot by itself become `SELECTED_FOR_PAPER_TEST`.

## Confidence

- Estimand: mean net weekly return on the full evaluation calendar, including zero-trade weeks. Return is `(equity_end − equity_start) / equity_start` in integer cents, as a ratio.
- The calendar is the set of America/New_York Monday weeks covering the union tape, and the same weeks are used for the 2Q and 3Q replays.
- After that single chronological replay: moving-block bootstrap of the weekly series. Block length 4 consecutive weeks. 2,000 resamples. Seed 604.
- Each resample draws start indexes uniformly from `0 .. n−4` with replacement until the sample has `n` weeks, then truncates to `n`.
- The 90% one-sided lower bound is the nearest-rank 10th percentile: ordered mean at rank `ceil(0.10 × 2000) = 200` (index 199).
- Block lengths 1 and 8 are sensitivity only. Selection uses length 4.
- A claim that the 1.5% mean is supported requires this lower bound to be at least 1.5%. If the point estimate is at least 1.5% and the bound is below, the claim is uncertain. If both are below, it is unsupported. The interval is not a snooping correction. Prior exploration of these same locks still limits the claim.
- If any week mark is `MARK_UNAVAILABLE` or `STALE_MARK`, that weekly return is missing, the bound is not computed, and the status is `NO_SELECTION`.

## Decision

Assigned only after the replay.

- `SELECTED_FOR_PAPER_TEST` only if the conservative length-4 lower bound is at least 1.5% and the fill basis is executable.
- Otherwise `PROVISIONAL` for the best-supported paper candidate when that bound exists.
- `NO_SELECTION` when no bound exists or no candidate is defensible.

The fill basis on this tape is `FILL_UNAVAILABLE`, so `SELECTED_FOR_PAPER_TEST` is not available from this replay.
