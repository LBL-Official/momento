# FIRST78→67 two-window findings

Live execution is off. The headline is an assumed 78¢ fill and an assumed 67¢ sale on a minute bid close.
The two accounts start over at $20,000. They are not pooled. A higher ending balance is not an out-of-sample pass.
The November 2026–April 2027 launch assessment stays NOT_YET_IDENTIFIABLE.

## OCT_2025

Coverage: `COMPLETE_FOR_NORMALIZED_WAREHOUSE`. Sport status: `{"NBA": "HAS_CANDIDATES", "NBA_events_in_window": 97, "NCAAB": "NO_ELIGIBLE_GAMES", "NCAAB_events_in_window": 0}`.
Ex-ante candidates 41. REF admitted 41. Rejections 0. Max open 3.
REF net 359311 cents. Gross 391138. Fees 31827. Identity holds: True.
NBA attribution 359311 cents. NCAAB attribution 0 cents.
Equal-weight mean net cents per admitted contract, REF: 5.412906501914133. JOINT_2_FEE_007: 1.0296095970435386 (portfolio net 60813 cents).
Cutoff marked equity 2359311 cents. Final realized equity 2359311 cents.
Complete batches 4. Partial batches 1.
Same-quantity stop minus hold: 35260 cents. Full hold replay net: 275789 cents. Those are different comparisons.
Sample-selection reading: supports_sign. Execution reading: supports_sign.
REF p-status ESTIMATED on 13 local days, one-sided p 0.0384807596201899. JOINT_2_FEE_007 p-status ESTIMATED, one-sided p 0.3538230884557721. Holm-adjusted values are 0.0769615192403798 and 0.3538230884557721.
supports_sign means the equal-weight mean stayed positive on this historical close proxy. A positive sign is not a 5% rejection after Holm.

## APR_2025

Coverage: `PARTIAL_RAW_TICKER_SUBSET`. Sport status: `{"NBA": "HAS_CANDIDATES", "NBA_events_in_window": 44, "NCAAB": "COVERAGE_UNKNOWN", "NCAAB_markets_in_window": 0}`.
Ex-ante candidates 6. REF admitted 6. Rejections 0. Max open 1.
REF net -5156 cents. Gross 0. Fees 5156. Identity holds: True.
NBA attribution -5156 cents. NCAAB attribution 0 cents.
Equal-weight mean net cents per admitted contract, REF: -0.5587342869527525. JOINT_2_FEE_007: -5.5151111111111115 (portfolio net -49636 cents).
Cutoff marked equity 1994844 cents. Final realized equity 1994844 cents.
Complete batches 0. Partial batches 1.
Same-quantity stop minus hold: 102200 cents. Full hold replay net: -107356 cents. Those are different comparisons.
Sample-selection reading: weakens. Execution reading: weakens.
REF p-status P_VALUE_NOT_ESTIMABLE on 4 local days. JOINT_2_FEE_007 p-status P_VALUE_NOT_ESTIMABLE.
weakens means the equal-weight mean on these six available contracts is at or below zero. It does not describe the games that have no candles. On four triggered stops, the 1% and 5% stop-fail quotas round to zero failures, so those paths match REF.

## What this changes

October was already scanned in the 936-game study, including signals and settlement labels, and then left out of that book's P&L. A positive October sign would be a retrospective check on an ex-ante rule, not a forward confirmation. April is a partial raw ticker list. It cannot stand in for the April slate. The NCAAB market file has no 25APR event dates; its APR-stamped rows are 26APR, outside this window, and candlesticks are absent. On four April stops, the 1% and 5% stop-fail quotas round to zero failures, so those paths match REF.
Measured fill selection is unavailable. The oracle bounds are pessimistic constructions, not a queue and not a probability. Maker fills remain unavailable. Nothing here authorizes trading.
