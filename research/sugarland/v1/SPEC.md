# Sugarland pregame favorite appreciation — SPEC v1

Universe: `SUGARLAND_PREGAME_V1`

Status: research only. Execution disabled. This file is the measurement contract. Outcome tables are emitted only after `SPEC.sha256` matches this file byte-for-byte.

This universe is not FIRST80 936, not asked-six 1182, not Austin 604, and not a sealed Austin confirmation cohort.

## Question answered first

Among contracts whose frozen 24-hour or 48-hour pregame quote is in the predefined around-80 band, how much did that same contract’s bid change by the 30-minute pregame mark, and did that bid change exceed the observed ask-to-bid spread?

Explanation is out of scope until that table exists.

## Price basis

Source: canonical Kalshi 1-minute candles, `market_data_type = CANDLESTICK_TOP_OF_BOOK`.

Columns used: `yes_bid_close`, `yes_ask_close`, `volume`, `available_at`. `available_at` is the candle end time. A candle is usable at target time `T` only when `available_at <= T`.

Prices are integer e4. `p = e4 / 10000` on `(0, 1)`. `10000` e4 = 100¢ = 1.00. Primary mark: `yes_bid_close`. Ask is used only in the quote-based benchmark.

`LAST_TRADE_PRINT` is not converted into this basis. Historical L2, depth, and latency are absent.

Official market listing time (`open_time`) is `UNAVAILABLE`. The first candle is **first observed**. It is not a market open.

### Valid quote

A candle is a valid two-sided quote when all of the following hold:

- bid and ask parse as integers
- `0 < bid <= ask < 10000`
- `ask - bid <= 1000` (10¢)

No `had_quality` carry-forward. Prices at 0 or 10000 are excluded, not clipped. They do not enter log-odds.

### History before the first valid quote

For each ticker, record:

- `history_before_first_raw = UNKNOWN` (left truncation; listing time is unavailable)
- timestamp of the first raw candle
- count of raw rows strictly before the first valid pregame quote
- count of those rows that are invalid
- missing minutes = max(0, whole minutes from the first raw candle to the first valid quote, minus the raw-row count before that quote)

## Clocks

`t_end = start − 30 minutes`. This is the 30-minute pregame mark, not an opening price.

Primary start for NBA, NCAAB, and WNBA is `actual_start`, labeled `RETROSPECTIVE_ACTUAL_START`.

`scheduled_start` is a **stored-schedule sensitivity** (`STORED_SCHEDULE_SENSITIVITY`). No entry-time schedule snapshot exists. An exact match between stored scheduled and actual timestamps is not evidence the clock was known beforehand.

Quarantine `SCHEDULE_EXCEPTION` when both timestamps parse and either:

- the absolute difference exceeds 6 hours, or
- the UTC dates differ by two or more calendar days

A UTC midnight crossing with absolute difference at most 6 hours is `UTC_DATE_ROLLOVER`. It stays in the primary set and is counted separately.

Empty `scheduled_start` makes the sensitivity `UNAVAILABLE` for that game. It is not treated as a match.

MLB `scheduled_start` and `actual_start` are blank in the canonical games table. `game_date` at midnight is not first pitch. If canonical PBP has an event timestamp, the MLB primary clock is the earliest PBP `event_timestamp`, labeled `FIRST_PBP_EVENT`. That clock is not a basketball `actual_start` and is not an entry-time schedule. If no PBP timestamp exists, MLB T−30 appreciation is `UNMEASURABLE`.

Ambiguous ticker-to-game maps and games that share one `event_ticker` are `AMBIGUOUS_MAP`.

Quarantined games are counted and excluded from eligible N.

## Endpoint

The mark at a target `T` is the latest valid quote with `available_at <= T` and `T - available_at <= age cap`.

Primary age cap: **30 minutes**. Sensitivities: 5, 15, and 60 minutes. Never a later quote. Never nearest-neighbor forward fill.

Entry must satisfy `available_at < t_end`. A quote at exactly `t_end` may be the endpoint and may not be the entry.

## Cohorts

Overlaps are counts. They are not a pooled N. The same ticker is kept for the whole path.

### A — First-observed above 70

Take the first valid quote with `available_at < t_end` and **no price filter**. Include the contract only when that quote’s bid satisfies `7000 < bid < 10000`.

Do not scan forward for a later print above 70¢. A contract first seen at or below 70¢ is out of A even if a later pregame print exceeds 70¢.

### B — Pregame FIRST80

Among valid quotes with `available_at < t_end`, the first bid `>= 8000` that follows an earlier valid bid `< 8000`. The recorded price is the actual crossing bid. An 82¢ print is not an 80¢ purchase.

If the first valid bid is already `>= 8000`, the contract is `ALREADY_ABOVE_80`. It is not a crossing.

Threshold sensitivity repeats this rule at 78¢ and 82¢ (`7800` and `8200`). It does not search for the threshold after skipping the first valid quote.

### C — WNBA account rows

Source: `research/vital/bots/mlb-001/execution/fills.jsonl`, tickers containing `KXWNBAGAME`.

Rows that share a `fill_id` are one fill. If two confirmed values of the same field disagree, the fill is `RECONCILIATION_CONFLICT` and is not resolved by dropping a row. Identical confirmed duplicates collapse.

Partial fills on one `order_id` sum confirmed contracts and confirmed costs. They are one position, not one trade per fill line.

Exact 80¢ is the primary price subgroup. 81¢ and the band 78–82¢ are labeled bands.

Actual realized P&L requires confirmed quantities, entry/exit linkage, and settlement or redemption evidence. Otherwise the report is confirmed acquisition cost plus a hypothetical endpoint or settlement valuation. Ledger fees are `UNAVAILABLE`. Any supported realized figure is gross.

The 2026-08-25 loss-review note is not a fill tape.

### D — Fixed horizons

Horizons: 48, 24, 12, 6, 2, and 1 hours before the primary start.

At horizon `H`, retrieve the latest valid quote with `available_at <= start − H` and age at most 30 minutes. Then apply rules to that quote:

- primary horizon cohort: `7000 < bid < 10000`
- around-80 subgroup: `7800 <= bid <= 8200`, label `AROUND_80_78_82`

A later price never decides eligibility. The around-80 flag is not a silent redefinition of the above-70 cohort.

### Dedicated 24–48h around-80 table

Built only from the frozen 48h snapshot and the frozen 24h snapshot, each restricted to `AROUND_80_78_82`.

Report 48h and 24h separately. The union keeps one row per ticker: the 48h quote when that snapshot is in the band, otherwise the 24h quote. The choice is by horizon, not by which return is larger.

This table is the first result. Cohort A does not substitute for it.

## Metrics

Let `p0` be the cohort anchor bid and `p30` the endpoint bid. `h` is elapsed hours from the anchor quote timestamp to the endpoint quote timestamp.

- `Δpp = 100 × (p30 − p0)` which equals `(bid30_e4 − bid0_e4) / 100`. Percentage points, also cents on a $1 contract.
- `R = (p30 − p0) / p0`
- `U = (p30 − p0) / (1 − p0)`. Headline `U` excludes anchors in `[0.90, 1)`. The `[90,100)` band reports `U` only inside that band.
- `L = log(p30 / (1 − p30)) − log(p0 / (1 − p0))`. Undefined at 0 or 1; those rows are counted and omitted, not clipped.
- `S_pp = Δpp / h`, plus `R / h` and `L / h`, when `h > 0`. Descriptive rates, not forecasts.

For every statistic report eligible N, endpoint N, and the statistic. An empty set is `UNAVAILABLE`, not zero.

Primary estimand: mean `Δpp`. Also median, sample standard deviation, quantiles 10/25/75/90, share rising (`Δpp > 0`), unchanged (`Δpp = 0`), and falling (`Δpp < 0`).

95% interval: date-block bootstrap, 1000 resamples, seed `20260923`. Resample game dates with replacement. Keep every contract on a drawn date. Percentile interval on the resampled means.

Discovery vs validation, inside each sport, using games that have a primary clock: sort distinct `game_date` values; the median date is the element at index `(n − 1) // 2`. Dates on or before that date are discovery. Later dates are validation. Both tickers from one game stay together. WNBA 2026 confirmation is retrospective. A prospective sample after this spec’s freeze date is empty.

### Quote-based benchmark

Gross dollars per contract = `(exit_bid_e4 − entry_ask_e4) / 10000`.

Return on entry ask = `(exit_bid_e4 − entry_ask_e4) / entry_ask_e4`.

This is whether bid appreciation exceeds the observed spread. It is not an executable return. Depth, latency, and fills are absent.

A separate fee column may show `ceil` to `1e-6` of `0.07 × P × (1 − P)` per leg for one contract, labeled `PUBLISHED_QUADRATIC_TAKER_ESTIMATE`. It is not a date-matched historical fee and is not subtracted from the headline return. A candle that touches 80¢ is not a maker fill.

Hold-to-settlement using Kalshi `result` minus entry ask is `HYPOTHETICAL_SETTLEMENT`. It is not ledger P&L.

### Path and slope

Grid step: 15 minutes, from the anchor timestamp through `t_end`. A grid time is kept when a valid quote has `available_at` at or before that time and age at most 60 minutes. Grid points more than 14 days before `t_end` are not retained. A path that needs that older grid fails the coverage gate and is `INSUFFICIENT_COVERAGE`. It is not interpolated.

Weight of a kept point = hours until the next kept point, and only when that gap is at most 60 minutes and the next grid time is still inside the 60-minute freshness window of that point’s quote. Otherwise the weight is zero. Stale gaps add no weight and are not bridged.

Report a slope only when all of the following hold:

- at least 8 positive-weight points
- positive-weight coverage spans at least 6 hours
- positive-weight hours are at least 50% of elapsed time from the anchor to `t_end`

Otherwise `INSUFFICIENT_COVERAGE`.

Fit `p = α + β t` by weighted least squares on positive-weight points. `t` is hours from the anchor. Report `100 × β` in percentage points per hour.

Time above, below, and unchanged uses covered hours (the sum of positive weights) as the denominator. Uncovered hours are reported separately and are not in that share.

Also record, on kept points: maximum appreciation from the anchor, maximum drawdown from the anchor, and the largest peak-to-trough decline.

Equal contract weights for population results. Capital weights only for reconciled WNBA positions with confirmed quantities.

### Association versus forecasting

Retrospective description may use lead time measured from the primary start. That variable is `DESCRIPTIVE_ACTUAL_START`.

The entry-time association model may use anchor bid, entry spread, entry volume, and sport. It must not use lead time from actual start, stored scheduled start, future volume, or settlement. It is an association, not a forecast. Stored `scheduled_start` is not an entry-time snapshot.

### Other checks

Price bands on the anchor bid: `(70,75)`, `[75,80)`, `[80,85)`, `[85,90)`, `[90,100)`.

Lead-time buckets on hours from the anchor to the primary start, labeled descriptive: `[0,1)`, `[1,2)`, `[2,6)`, `[6,12)`, `[12,24)`, `[24,48)`, `>=48`.

Threshold sensitivity for cohort A applies 68¢, 70¢, and 72¢ to the **first** valid bid, not to a later crossing.

Descriptive comparison cohorts: first valid bid in `(5000, 7000]` and in `(6000, 7000]`.

Report results with the largest positive `Δpp` removed. Subgroup searches are exploratory.

## Cohort universe for the numbers

Canonical candle CSV under `ROLLER/data/{sport}/{season}/canonical/kalshi_candles/`.

Seasons: WNBA `2025`, WNBA `2026`, NBA `2025_2026`, NCAAB `2025_2026`, MLB `2025_2026`.

Phase 8 parquet observation counts are inventory only. They are not added into cohort N. NCAAB canonical candles are the ESPN-mapped subset of the parquet desk.

Dashboard surface `#/sugarland` shows NBA and NCAAB only. WNBA and MLB stay in this directory’s findings.

## Headline columns

One row per sport, for cohort A and for the around-80 horizons:

- eligible N
- endpoint N
- mean and median `Δpp`
- 95% date-block interval
- share rising
- mean quote-based return on entry ask
- discovery mean `Δpp` and N
- validation mean `Δpp` and N

Empty cells are `UNAVAILABLE`.
