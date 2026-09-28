# NBA Bot 001 — fees

Status: **verified for `quadratic_with_maker_fees` at multiplier 1** (the
KXNBAGAME configuration today) against 235 production account fills
(section 5). The worker reports `FEE_UNVERIFIED` for any other series fee
type or multiplier. Fees are a technical fact, not an owner choice.

## 1. Documented rule

Sources: Kalshi fee schedule (PDF, downloaded 2026-09-27), API docs
`get-series-fee-changes`, `get-fills`, `create-order-v2`, and the
OpenAPI `FeeType` enum.

| Fee type | Taker | Maker |
| --- | --- | --- |
| `quadratic` | `0.07 × M × C × P × (1 − P)` | 0 |
| `quadratic_with_maker_fees` | `0.07 × M × C × P × (1 − P)` | `0.0175 × M × C × P × (1 − P)` |
| `quadratic_with_combo_maker_fees`, `flat` | not modeled | not modeled (`FeeError::Unsupported` → `FEE_UNVERIFIED`) |

- `C` is the number of contracts, `P` is the price in dollars, and `M` is
  the series `fee_multiplier`.
- The trade fee is rounded **up** to $0.000001. A per-order rounding fee
  then aligns the account balance to $0.0001 (direct members) or $0.01.
  The rounding accumulates over **all fills of one order**, so the model is
  per order, not per fill.
- A maker is the resting side and a taker is the side that crosses. A
  post-only order is always a maker, or it is rejected.

## 2. Observed metadata (production, read-only)

| Series | `fee_type` | `fee_multiplier` | Read |
| --- | --- | --- | --- |
| KXNBAGAME | `quadratic_with_maker_fees` | 1 | 2026-09-27 03:54Z (worker) |
| KXMLBGAME | `quadratic_with_maker_fees` | 0.5 published (since 2026-08-07); **charged at 1** (section 5) | 2026-09-27 host |
| KXWNBAGAME | `quadratic_with_maker_fees` | 1 | 2026-09-27 host |
| demo NBA/WNBA | `quadratic` (no maker fee) | — | demo exercise |

A 0.5682 balance with four decimals indicates a direct member
(centicent precision). Reservations still round each fee up to whole cents,
which is the bound for either precision.

The research coefficient 0.0175 is the documented maker rate for this
series type. It is **not** assumed to hold for every account or series:
the worker reads `fee_type` every discovery pass, and an unknown type
blocks entries.

## 3. Implementation

`strategies/nba/src/fees.rs`

- `FeeModel{fee_type, multiplier_milli, precision}`
- `order_fee_centicents(liquidity, qty, price_cents)` computes
  `ceil(num × M_milli × C × p × (100 − p) / (den × 1000))` in centicents,
  with `num/den` = 7/100 (taker), 7/400 (maker, maker-fee type), or 0
  (maker, `quadratic`). `Cent` precision rounds up to a whole cent.
- `order_fee_bound_over(liquidity, qty, lo, hi)` uses the price in
  `[lo, hi]` closest to 50, because the fee peaks at 50¢.
- Tests: `fee_model_taker_maker_and_rounding` (strategy crate) and
  `full_fill_on_submit_then_fill_records` (worker fixtures; 1538 @ 40
  taker = 258,384cc).

Reference values for 1538 contracts (M = 1, centicents; 1¢ = 100cc):

| Leg | Fee |
| --- | ---: |
| entry @78 taker | 184,745 ($18.4745) |
| entry @78 maker | 46,187 ($4.6187) |
| hedge @33 taker | 238,037 |
| hedge @40 taker | 258,384 |
| hedge/emergency @45 or @55 taker | 266,459 |
| @50 taker (peak) | 269,150 |

## 4. Account evidence

`momento-nba-001 evidence` (GET-only; order ids hashed) groups
`GET /portfolio/fills` by order. It recomputes each order's fee under the
fee schedule in effect at each fill (the latest entry of
`GET /series/fee_changes?show_historical=true` at or before the fill's
`created_time`) and compares the result with the observed `fee_cost`.

- Counts are read in hundredths of a contract. An unreadable count is
  `UNMODELED`, never 0.
- A multiplier-1 diagnostic is computed alongside.

Tests: `maker_fee_is_modelled_under_the_schedule_at_fill_time`,
`fill_before_any_known_schedule_is_unmodeled_not_guessed`,
`fractional_fill_is_modelled_in_hundredths`, and
`unreadable_count_is_unmodeled_not_zero` (all in `account.rs`).

## 5. Host evidence run

Run on `i-0f0849d5829476c31`, 2026-09-27 (`read_at` 1790494416), by a
one-off copy of build `nba001-20260927T073047Z` (sha `97b038fc…6252`,
verified before running) started from a temporary directory and deleted
afterwards. The service binary (`9ef129e1…`) and MLB's binary
(`66ca5420…`) were unchanged before and after, and both services stayed
active. `non_get_sent=false`, 15 GETs, `funds_moved=false`. Output was
filtered on the host to drop any key containing `user`, `member`,
`email`, or `key`.

Scope: 235 fills, 194 orders, 2026-08-22 to 2026-09-25 (this credential is
shared with `momento-live.service`; there are no NBA fills yet).

| Group (series, liquidity) | Orders | Match under the schedule at fill | Match at multiplier 1 |
| --- | ---: | ---: | ---: |
| KXWNBAGAME maker | 25 | 24 | 24 |
| KXWNBAGAME taker | 4 | 4 | 4 |
| KXMLBGAME maker | 130 | 0 | 128 |
| KXMLBGAME taker | 35 | 0 | 35 |

What this establishes:

1. **The documented rule holds at multiplier 1.** KXWNBAGAME has the same
   `fee_type` and multiplier as KXNBAGAME today. 28 of 29 orders match
   exactly, maker and taker, including the per-order rounding to $0.0001.
   The one exception (100 contracts, 4 fills) is $0.0001 above the model:
   one rounding step. The demo taker round trip also matched to the
   centicent (buy 1 @39 = 167cc, sell 1 @37 = 164cc; demo `quadratic`).
2. **A published multiplier below 1 was not charged.** KXMLBGAME has
   published 0.5 since 2026-08-07, yet every MLB fill here (2026-08-23 to
   09-25) was charged at 1: 163 of 165 orders match at multiplier 1 and
   none at 0.5. Example: 7 maker contracts at 83¢ model to $0.0087 at 0.5
   and $0.0173 at 1; the observed fee was $0.0173. The worker therefore
   treats only multiplier 1 as verified (`engine::fees_verified_for`). This
   affects MLB's fee economics and is reported, not acted on: MLB's binary,
   service, and policy are untouched.
3. **Fractional fills exist on whole-contract orders.** 49 of 235 fills
   have fractional counts:
   - 19 MLB orders with whole totals (7 contracts) were filled in
     fractional pieces.
   - 3 WNBA orders had whole totals; 2 had fractional totals.

   The NBA order model counts whole contracts, so a fractional fill is a
   read error. It fails closed (no state change, lane holds; test
   `fractional_fill_count_fails_closed_without_changing_state`). Production
   carries the build-level blocker `FRACTIONAL_FILLS_UNSUPPORTED` until
   counts are hundredths end to end.

`FEE_UNVERIFIED` is therefore off for KXNBAGAME at multiplier 1 and on for
anything else. Reservations are unchanged: they round each leg's fee up to
whole cents.
