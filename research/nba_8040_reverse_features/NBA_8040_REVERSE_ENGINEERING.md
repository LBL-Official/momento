# NBA 80→40 reverse engineering

Research only. Candle path ≠ fill. Not a live FIRST80 retune. The Choosin Texas 2026–27 book is unchanged.

Generated: `2026-09-17T23:45:48.123602+00:00`

## Question

Why does NBA Q2 FIRST80 80→40 behave differently from Q3 and the broader 80→40 population?

Not: which filter raises EV.

## Structural label

**UNEXPLAINED**

Flags: none

Association on candle-path FIRST80 80→40. Not causation. Not a live filter. Not a fill.

| metric | value |
| --- | --- |
| mean |SMD| Q2 vs Q3 | 0.3612 |
| mean |SMD| Q2 vs Q3 excluding time | 0.2936 |
| max |SMD| Q2 vs Q3 | 3.1612 |
| time mean |SMD| | 1.6120 |
| score mean |SMD| | 0.0875 |
| open mean |SMD| | 0.3699 |
| price mean |SMD| | 0.4154 |
| raw T40 gap Q2−Q3 | -0.0336 |
| matching shrink | -1.5595 |
| temporal shrink | -0.9193 |

## How to read this

Q2 candle-path EV is +5.6688¢ / trade (N=314) against Q3 +3.6552¢ / trade (N=290). The T40 rate gap is small (75/314 vs 79/290). Q2 vs Q3 differ strongly on clock because Q3 is later in the game; that is not an explanation unless holding fraction-of-period / fraction-of-game fixed shrinks the EV gap. It does not (`temporal_shrink` is negative). Cross-period matching on the pre-80 matrix does not pull T40 rates together (`matching_shrink` is negative). Within-period survive-vs-T40 standardized differences stay small. Neighborhood outcome agreement is indistinguishable from a label permutation. So the current feature set does not explain why Q2 80→40 prints a higher candle-path EV than Q3. That is `UNEXPLAINED`, not a new trading filter.

## Locked population

Feature-store universe is the asked-six NBA Q2∪Q3 **N=604** after fail-closed reproduction. 314 / 290 / 280 are slices of that store.

| period | n | survivors | t40 | w_and_t40 | l_and_t40 | ev_per_trade_display | book_cents |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q2∪Q3 | 604 | 450 | 154 | 55 | 99 | +4.7020¢ / trade | 2840 |
| Q2 | 314 | 239 | 75 | 28 | 47 | +5.6688¢ / trade | 1780 |
| Q3 | 290 | 211 | 79 | 27 | 52 | +3.6552¢ / trade | 1060 |
| Q2 all-phase | 314 | 239 | 75 | 28 | 47 | +5.6688¢ / trade | 1780 |
| Q3 all-phase | 290 | 211 | 79 | 27 | 52 | +3.6552¢ / trade | 1060 |
| Q2 regular season | 280 | 218 | 62 | 22 | 40 | +6.7143¢ / trade | 1880 |
| Q3 regular season | 270 | 197 | 73 | 25 | 48 | +3.7778¢ / trade | 1020 |

EV uses `ev.py` only: `20S − 40(1−S)`. S = ¬T40.

## Feature store

Rows: **604**. Predictive columns after leakage assert: 82. PCA/KNN coverage set (≥90% observed): 78.

Missing stays missing. Possession / fouls / timeouts remain `SOURCE_UNAVAILABLE`. Time-windowed PBP remains `OPERATION_REQUIRED`. Historical L2 remains `SOURCE_UNAVAILABLE`.

### Availability

| feature_class | feature | available_n | missing_pct | source |
| --- | --- | --- | --- | --- |
| B | entry_bid_cents | 604 | 0.0000 | asked_six.market_yes_bid |
| L | entry_ask_cents | 604 | 0.0000 | asked_six.market_yes_ask |
| L | spread_cents | 604 | 0.0000 | asked_six bid/ask |
| B | entry_last_cents | 601 | 0.5000 | asked_six.market_last_price |
| B | entry_volume | 604 | 0.0000 | asked_six.market_volume |
| M | pregame_cents | 604 | 0.0000 | asked_six.pregame_*_win_prob |
| M | distance_from_open | 604 | 0.0000 | entry_bid − pregame |
| G | bought_margin | 604 | 0.0000 | asked_six.bought_team_margin |
| G | abs_margin | 604 | 0.0000 | abs(bought_margin) |
| G | leading | 604 | 0.0000 | bought_margin > 0 |
| G | tie | 604 | 0.0000 | bought_margin == 0 |
| G | favorite_leading | 604 | 0.0000 | pregame and margin |
| F | period_remaining_s | 604 | 0.0000 | asked_six.period_remaining_s |
| F | game_seconds_remaining | 604 | 0.0000 | asked_six.game_seconds_remaining |
| F | frac_period_remaining | 604 | 0.0000 | period_remaining_s / 720 |
| F | frac_game_elapsed | 604 | 0.0000 | 1 − remaining/2880 |
| A | regular_season | 604 | 0.0000 | asked_six.season_phase |
| D | jump_through_80 | 604 | 0.0000 | entry_bid > 80 |
| D | exact_80 | 604 | 0.0000 | entry_bid == 80 |
| D | prior_close_cents | 604 | 0.0000 | warehouse yes_bid_close |
| D | came_from_below | 604 | 0.0000 | prior_close < 80 |
| C | bars_before_n | 604 | 0.0000 | warehouse count |
| C | close_1m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_1m | 604 | 0.0000 | entry − close_wm |
| J | velocity_1m | 604 | 0.0000 | delta_1m / 1 |
| J | accel_1m | 0 | 100.0000 | second-half minus first-half velocity |
| C | min_1m | 604 | 0.0000 | min close in window |
| C | max_1m | 604 | 0.0000 | max close in window |
| K | range_1m | 604 | 0.0000 | max−min |
| K | std_1m | 0 | 100.0000 | std of closes |
| C | direction_changes_1m | 0 | 100.0000 | sign flips |
| C | n_bars_1m | 604 | 0.0000 | count |
| C | close_3m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_3m | 604 | 0.0000 | entry − close_wm |
| J | velocity_3m | 604 | 0.0000 | delta_3m / 3 |
| J | accel_3m | 0 | 100.0000 | second-half minus first-half velocity |
| C | min_3m | 604 | 0.0000 | min close in window |
| C | max_3m | 604 | 0.0000 | max close in window |
| K | range_3m | 604 | 0.0000 | max−min |
| K | std_3m | 604 | 0.0000 | std of closes |
| C | direction_changes_3m | 604 | 0.0000 | sign flips |
| C | n_bars_3m | 604 | 0.0000 | count |
| C | close_5m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_5m | 604 | 0.0000 | entry − close_wm |
| J | velocity_5m | 604 | 0.0000 | delta_5m / 5 |
| J | accel_5m | 604 | 0.0000 | second-half minus first-half velocity |
| C | min_5m | 604 | 0.0000 | min close in window |
| C | max_5m | 604 | 0.0000 | max close in window |
| K | range_5m | 604 | 0.0000 | max−min |
| K | std_5m | 604 | 0.0000 | std of closes |
| C | direction_changes_5m | 604 | 0.0000 | sign flips |
| C | n_bars_5m | 604 | 0.0000 | count |
| C | close_10m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_10m | 604 | 0.0000 | entry − close_wm |
| J | velocity_10m | 604 | 0.0000 | delta_10m / 10 |
| J | accel_10m | 604 | 0.0000 | second-half minus first-half velocity |
| C | min_10m | 604 | 0.0000 | min close in window |
| C | max_10m | 604 | 0.0000 | max close in window |
| K | range_10m | 604 | 0.0000 | max−min |
| K | std_10m | 604 | 0.0000 | std of closes |
| C | direction_changes_10m | 604 | 0.0000 | sign flips |
| C | n_bars_10m | 604 | 0.0000 | count |
| C | close_15m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_15m | 604 | 0.0000 | entry − close_wm |
| J | velocity_15m | 604 | 0.0000 | delta_15m / 15 |
| J | accel_15m | 604 | 0.0000 | second-half minus first-half velocity |
| C | min_15m | 604 | 0.0000 | min close in window |
| C | max_15m | 604 | 0.0000 | max close in window |
| K | range_15m | 604 | 0.0000 | max−min |
| K | std_15m | 604 | 0.0000 | std of closes |
| C | direction_changes_15m | 604 | 0.0000 | sign flips |
| C | n_bars_15m | 604 | 0.0000 | count |
| C | close_30m_before | 604 | 0.0000 | warehouse yes_bid_close |
| J | delta_30m | 604 | 0.0000 | entry − close_wm |
| J | velocity_30m | 604 | 0.0000 | delta_30m / 30 |
| J | accel_30m | 604 | 0.0000 | second-half minus first-half velocity |
| C | min_30m | 604 | 0.0000 | min close in window |
| C | max_30m | 604 | 0.0000 | max close in window |
| K | range_30m | 604 | 0.0000 | max−min |
| K | std_30m | 604 | 0.0000 | std of closes |
| C | direction_changes_30m | 604 | 0.0000 | sign flips |
| C | n_bars_30m | 604 | 0.0000 | count |

## Question A — unconditional Q2 vs Q3

Largest standardized mean differences first. Period one-hot is a grouping column and is not in the predictive matrix.

| feature | q2_mean | q3_mean | q2_median | q3_median | standardized_difference | q2_available_n | q3_available_n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frac_game_elapsed | 0.3751 | 0.6203 | 0.3769 | 0.6156 | -3.1612 | 314 | 290 |
| game_seconds_remaining | 1799.6051 | 1093.6231 | 1794.5000 | 1107.0000 | 3.1612 | 314 | 290 |
| delta_1m | 3.8312 | 5.5621 | 3.5000 | 5.0000 | -0.6251 | 314 | 290 |
| velocity_1m | 3.8312 | 5.5621 | 3.5000 | 5.0000 | -0.6251 | 314 | 290 |
| velocity_3m | 2.1401 | 3.1506 | 2.0000 | 3.0000 | -0.6134 | 314 | 290 |
| delta_3m | 6.4204 | 9.4517 | 6.0000 | 9.0000 | -0.6134 | 314 | 290 |
| min_3m | 74.0287 | 71.5931 | 75.0000 | 72.0000 | 0.5632 | 314 | 290 |
| velocity_5m | 1.6153 | 2.2821 | 1.5000 | 2.0000 | -0.5258 | 314 | 290 |
| delta_5m | 8.0764 | 11.4103 | 7.5000 | 10.0000 | -0.5258 | 314 | 290 |
| min_5m | 71.8376 | 68.9000 | 73.0000 | 70.0000 | 0.5171 | 314 | 290 |
| close_3m_before | 74.6338 | 72.3621 | 75.0000 | 73.0000 | 0.4909 | 314 | 290 |
| direction_changes_30m | 9.5000 | 8.0207 | 9.0000 | 8.0000 | 0.4740 | 314 | 290 |
| entry_volume | 21028.7045 | 39364.0488 | 13595.0000 | 25243.5000 | -0.4669 | 314 | 290 |
| entry_bid_cents | 81.0541 | 81.8138 | 81.0000 | 81.0000 | -0.4478 | 314 | 290 |
| min_10m | 66.9809 | 63.4759 | 68.0000 | 65.0000 | 0.4318 | 314 | 290 |
| std_5m | 2.2111 | 3.0266 | 1.9391 | 2.5768 | -0.4269 | 314 | 290 |
| close_5m_before | 72.9777 | 70.4034 | 74.0000 | 71.0000 | 0.4251 | 314 | 290 |
| range_3m | 3.5892 | 5.1586 | 3.0000 | 4.0000 | -0.4235 | 314 | 290 |
| std_3m | 1.5642 | 2.2326 | 1.2472 | 1.7926 | -0.4231 | 314 | 290 |
| range_5m | 5.9045 | 8.0655 | 5.0000 | 7.0000 | -0.4213 | 314 | 290 |

## Question B — survive vs T40 within period

| feature | q2_survive_mean | q2_t40_mean | q2_smd | q3_survive_mean | q3_t40_mean | q3_smd |
| --- | --- | --- | --- | --- | --- | --- |
| entry_bid_cents | 81.0711 | 81.0000 | 0.0530 | 81.9526 | 81.4430 | 0.2665 |
| entry_ask_cents | 82.3431 | 82.3200 | 0.0158 | 83.2180 | 82.7089 | 0.2588 |
| spread_cents | 1.2720 | 1.3200 | -0.0823 | 1.2654 | 1.2658 | -0.0008 |
| entry_last_cents | 81.8782 | 81.7838 | 0.0606 | 82.6810 | 82.1013 | 0.2934 |
| entry_volume | 20067.6588 | 24091.2367 | -0.1291 | 42641.6740 | 30609.8853 | 0.2806 |
| pregame_cents | 60.2092 | 59.8800 | 0.0223 | 54.6303 | 54.8987 | -0.0163 |
| distance_from_open | 20.8619 | 21.1200 | -0.0172 | 27.3223 | 26.5443 | 0.0462 |
| bought_margin | 5.5146 | 5.2400 | 0.0406 | 5.4028 | 5.2278 | 0.0303 |
| abs_margin | 5.6736 | 5.6133 | 0.0092 | 5.5545 | 5.6076 | -0.0096 |
| leading | 0.5063 | 0.4800 | 0.0526 | 0.5877 | 0.5949 | -0.0148 |
| tie | 0.4644 | 0.4667 | -0.0045 | 0.3839 | 0.3544 | 0.0611 |
| favorite_leading | 0.3724 | 0.3333 | 0.0818 | 0.3507 | 0.3165 | 0.0727 |
| period_remaining_s | 357.5477 | 366.1613 | -0.0400 | 365.8284 | 394.4418 | -0.1257 |
| game_seconds_remaining | 1797.5477 | 1806.1613 | -0.0400 | 1085.8284 | 1114.4418 | -0.1257 |
| frac_period_remaining | 0.4966 | 0.5086 | -0.0400 | 0.5081 | 0.5478 | -0.1257 |
| frac_game_elapsed | 0.3759 | 0.3729 | 0.0400 | 0.6230 | 0.6130 | 0.1257 |
| regular_season | 0.9121 | 0.8267 | 0.2557 | 0.9336 | 0.9241 | 0.0373 |
| jump_through_80 | 0.5188 | 0.4933 | 0.0510 | 0.6872 | 0.5696 | 0.2451 |
| exact_80 | 0.4812 | 0.5067 | -0.0510 | 0.3128 | 0.4304 | -0.2451 |
| prior_close_cents | 77.2594 | 77.1067 | 0.0823 | 76.3934 | 75.8734 | 0.1871 |
| came_from_below | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| bars_before_n | 2114.7741 | 2378.0667 | -0.2349 | 2325.4502 | 2320.5570 | 0.0057 |
| close_1m_before | 77.2594 | 77.1067 | 0.0823 | 76.3934 | 75.8734 | 0.1871 |
| delta_1m | 3.8117 | 3.8933 | -0.0371 | 5.5592 | 5.5696 | -0.0033 |
| velocity_1m | 3.8117 | 3.8933 | -0.0371 | 5.5592 | 5.5696 | -0.0033 |
| accel_1m | — | — | — | — | — | — |
| min_1m | 77.2594 | 77.1067 | 0.0823 | 76.3934 | 75.8734 | 0.1871 |
| max_1m | 77.2594 | 77.1067 | 0.0823 | 76.3934 | 75.8734 | 0.1871 |
| range_1m | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| std_1m | — | — | — | — | — | — |
| direction_changes_1m | — | — | — | — | — | — |
| n_bars_1m | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| close_3m_before | 74.9079 | 73.7600 | 0.2946 | 72.1848 | 72.8354 | -0.1218 |
| delta_3m | 6.1632 | 7.2400 | -0.2596 | 9.7678 | 8.6076 | 0.2033 |
| velocity_3m | 2.0544 | 2.4133 | -0.2596 | 3.2559 | 2.8692 | 0.2033 |
| accel_3m | — | — | — | — | — | — |
| min_3m | 74.2176 | 73.4267 | 0.2127 | 71.4882 | 71.8734 | -0.0773 |
| max_3m | 77.7238 | 77.2800 | 0.2356 | 76.8341 | 76.5316 | 0.1083 |
| range_3m | 3.5063 | 3.8533 | -0.1124 | 5.3460 | 4.6582 | 0.1643 |
| std_3m | 1.5317 | 1.6678 | -0.1031 | 2.3161 | 2.0098 | 0.1728 |
| direction_changes_3m | 0.2720 | 0.2000 | 0.1701 | 0.2749 | 0.3038 | -0.0638 |
| n_bars_3m | 3.0000 | 3.0000 | 0.0000 | 3.0000 | 3.0000 | 0.0000 |
| close_5m_before | 73.2050 | 72.2533 | 0.2013 | 70.2133 | 70.9114 | -0.0997 |
| delta_5m | 7.8661 | 8.7467 | -0.1777 | 11.7393 | 10.5316 | 0.1641 |
| velocity_5m | 1.5732 | 1.7493 | -0.1777 | 2.3479 | 2.1063 | 0.1641 |
| accel_5m | 0.4226 | 0.8200 | -0.1234 | 1.1706 | 0.6582 | 0.1311 |
| min_5m | 72.0167 | 71.2667 | 0.1602 | 68.7062 | 69.4177 | -0.1112 |
| max_5m | 77.8703 | 77.3333 | 0.2721 | 77.0284 | 76.7975 | 0.0761 |
| range_5m | 5.8536 | 6.0667 | -0.0512 | 8.3223 | 7.3797 | 0.1639 |
| std_5m | 2.1969 | 2.2566 | -0.0392 | 3.1185 | 2.7811 | 0.1573 |
| direction_changes_5m | 0.8619 | 0.6933 | 0.1927 | 0.8436 | 0.8987 | -0.0606 |
| n_bars_5m | 5.0000 | 5.0000 | 0.0000 | 5.0000 | 5.0000 | 0.0000 |
| close_10m_before | 69.6318 | 68.8267 | 0.1072 | 66.2938 | 66.1266 | 0.0166 |
| delta_10m | 11.4393 | 12.1733 | -0.0958 | 15.6588 | 15.3165 | 0.0320 |
| velocity_10m | 1.1439 | 1.2173 | -0.0958 | 1.5659 | 1.5316 | 0.0320 |
| accel_10m | 0.3138 | 0.5556 | -0.1281 | 0.8069 | 0.4146 | 0.1561 |
| min_10m | 67.0837 | 66.6533 | 0.0658 | 63.5403 | 63.3038 | 0.0251 |
| max_10m | 78.2510 | 77.6933 | 0.2402 | 77.5450 | 76.9873 | 0.1596 |
| range_10m | 11.1674 | 11.0400 | 0.0219 | 14.0047 | 13.6835 | 0.0378 |
| std_10m | 3.6377 | 3.5815 | 0.0300 | 4.5511 | 4.4882 | 0.0217 |
| direction_changes_10m | 2.4895 | 2.4400 | 0.0385 | 2.2370 | 2.4557 | -0.1389 |
| n_bars_10m | 10.0000 | 9.9733 | 0.1644 | 10.0000 | 10.0000 | 0.0000 |
| close_15m_before | 67.6485 | 65.7867 | 0.2096 | 63.9194 | 64.1772 | -0.0214 |
| delta_15m | 13.4226 | 15.2133 | -0.1976 | 18.0332 | 17.2658 | 0.0618 |
| velocity_15m | 0.8948 | 1.0142 | -0.1976 | 1.2022 | 1.1511 | 0.0618 |
| accel_15m | 0.4421 | 0.3687 | 0.0494 | 0.7030 | 0.7806 | -0.0461 |
| min_15m | 63.9833 | 62.7067 | 0.1657 | 60.4313 | 60.4304 | 0.0001 |
| max_15m | 78.5858 | 77.8133 | 0.2813 | 77.6635 | 77.0380 | 0.1716 |
| range_15m | 14.6025 | 15.1067 | -0.0738 | 17.2322 | 16.6076 | 0.0580 |
| std_15m | 4.5054 | 4.5919 | -0.0399 | 5.2997 | 5.2072 | 0.0261 |
| direction_changes_15m | 4.2594 | 4.2133 | 0.0267 | 3.4787 | 3.9747 | -0.2259 |
| n_bars_15m | 15.0000 | 14.9200 | 0.1644 | 14.9953 | 15.0000 | -0.0976 |
| close_30m_before | 63.9247 | 61.9200 | 0.1667 | 59.4502 | 61.1266 | -0.1224 |
| delta_30m | 17.1464 | 19.0800 | -0.1591 | 22.5024 | 20.3165 | 0.1570 |
| velocity_30m | 0.5715 | 0.6360 | -0.1591 | 0.7501 | 0.6772 | 0.1570 |
| accel_30m | 0.4357 | 0.5690 | -0.1375 | 0.5616 | 0.6365 | -0.0629 |
| min_30m | 58.1255 | 54.9733 | 0.3155 | 53.8057 | 54.5316 | -0.0599 |
| max_30m | 79.0795 | 78.3467 | 0.2098 | 78.0047 | 77.6329 | 0.0866 |
| range_30m | 20.9540 | 23.3733 | -0.2735 | 24.1991 | 23.1013 | 0.1037 |
| std_30m | 5.9936 | 6.6317 | -0.2271 | 6.7851 | 6.5305 | 0.0719 |
| direction_changes_30m | 9.5607 | 9.3067 | 0.0894 | 7.8863 | 8.3797 | -0.1542 |
| n_bars_30m | 30.0000 | 29.8533 | 0.1644 | 29.9953 | 30.0000 | -0.0976 |

## Temporal normalization (H1)

If the Q2/Q3 EV gap shrinks inside fraction-of-period / fraction-of-game bins, the period label is partly a clock alias.

| axis | bin | period | n | s | ev_cents |
| --- | --- | --- | --- | --- | --- |
| frac_period_remaining | (-0.001, 0.25] | Q2 | 79 | 60 | 5.5696 |
| frac_period_remaining | (-0.001, 0.25] | Q3 | 80 | 65 | 8.7500 |
| frac_period_remaining | (0.25, 0.5] | Q2 | 81 | 63 | 6.6667 |
| frac_period_remaining | (0.25, 0.5] | Q3 | 57 | 38 | 0.0000 |
| frac_period_remaining | (0.5, 0.75] | Q2 | 72 | 55 | 5.8333 |
| frac_period_remaining | (0.5, 0.75] | Q3 | 61 | 41 | 0.3279 |
| frac_period_remaining | (0.75, 1.01] | Q2 | 82 | 61 | 4.6341 |
| frac_period_remaining | (0.75, 1.01] | Q3 | 92 | 67 | 3.6957 |
| frac_game_elapsed | (0.249, 0.4] | Q2 | 186 | 140 | 5.1613 |
| frac_game_elapsed | (0.4, 0.55] | Q2 | 128 | 99 | 6.4062 |
| frac_game_elapsed | (0.4, 0.55] | Q3 | 83 | 60 | 3.3735 |
| frac_game_elapsed | (0.55, 0.7] | Q3 | 143 | 99 | 1.5385 |
| frac_game_elapsed | (0.7, 0.85] | Q3 | 64 | 52 | 8.7500 |

## Class ablation

Diagnostics, not a rank score. No k or EV tuning.

| feature_set | n_features | q2_q3_mean_abs_smd | q2_outcome_mean_abs_smd | q3_outcome_mean_abs_smd | knn_k10_agreement |
| --- | --- | --- | --- | --- | --- |
| PRICE | 6 | 0.4154 | 0.0988 | 0.2120 | 0.6439 |
| TIME | 4 | 1.6120 | 0.0400 | 0.1257 | 0.6127 |
| SCORE | 5 | 0.0875 | 0.0377 | 0.0377 | 0.5955 |
| OPEN | 2 | 0.3699 | 0.0197 | 0.0312 | 0.6268 |
| PRICE_TIME | 5 | 0.9447 | 0.0977 | 0.1692 | 0.6146 |
| PRICE_SCORE | 4 | 0.2508 | 0.0702 | 0.1176 | 0.6347 |
| ALL_PRE80 | 82 | 0.3612 | 0.1162 | 0.1006 | — |

## PCA

Complete-case n=601 on 78 features. Scaling: z-score. complete-case on OBSERVED matrix features; no mean-fill.

| component | explained | cumulative |
| --- | --- | --- |
| PC1 | 0.3085 | 0.3085 |
| PC2 | 0.1069 | 0.4154 |
| PC3 | 0.0850 | 0.5004 |
| PC4 | 0.0669 | 0.5673 |
| PC5 | 0.0549 | 0.6223 |
| PC6 | 0.0525 | 0.6748 |


Top |PC1| loadings:

| feature | pc1 | pc2 | pc3 |
| --- | --- | --- | --- |
| min_10m | -0.1907 | 0.0496 | -0.0165 |
| min_15m | -0.1875 | 0.0825 | 0.0622 |
| delta_10m | 0.1849 | -0.0465 | -0.0580 |
| velocity_10m | 0.1849 | -0.0465 | -0.0580 |
| close_10m_before | -0.1832 | 0.0457 | 0.0593 |
| delta_15m | 0.1801 | -0.0704 | -0.1238 |
| velocity_15m | 0.1801 | -0.0704 | -0.1238 |
| delta_5m | 0.1767 | 0.0152 | 0.1429 |
| velocity_5m | 0.1767 | 0.0152 | 0.1429 |
| close_15m_before | -0.1764 | 0.0700 | 0.1261 |
| close_5m_before | -0.1704 | -0.0208 | -0.1540 |
| min_30m | -0.1695 | 0.0788 | 0.1439 |
| min_5m | -0.1687 | -0.0262 | -0.1956 |
| velocity_3m | 0.1636 | 0.0783 | 0.1691 |
| delta_3m | 0.1636 | 0.0783 | 0.1691 |

## KNN / matching / null / stability

Fixed k ∈ {5,10,20,30}. Not a classifier.

### Neighborhood

| scope | period | k | n | outcome_agreement | mean_neighbor_ev |
| --- | --- | --- | --- | --- | --- |
| pooled | Q2 | 5 | 312 | 0.6391 | 5.8846 |
| pooled | Q2 | 10 | 312 | 0.6330 | 5.4038 |
| pooled | Q2 | 20 | 312 | 0.6314 | 5.0769 |
| pooled | Q2 | 30 | 312 | 0.6280 | 5.1282 |
| pooled | Q3 | 5 | 289 | 0.5931 | 2.0208 |
| pooled | Q3 | 10 | 289 | 0.6069 | 3.3910 |
| pooled | Q3 | 20 | 289 | 0.6057 | 4.0035 |
| pooled | Q3 | 30 | 289 | 0.6076 | 4.1799 |
| pooled | ALL | 5 | 601 | 0.6170 | 4.0266 |
| pooled | ALL | 10 | 601 | 0.6205 | 4.4359 |
| pooled | ALL | 20 | 601 | 0.6191 | 4.5607 |
| pooled | ALL | 30 | 601 | 0.6182 | 4.6722 |
| within-period | Q2 | 5 | 312 | 0.6423 | 6.6923 |
| within-period | Q2 | 10 | 312 | 0.6436 | 6.6923 |
| within-period | Q2 | 20 | 312 | 0.6439 | 6.6538 |
| within-period | Q2 | 30 | 312 | 0.6387 | 6.4615 |
| within-period | Q3 | 5 | 289 | 0.5938 | 1.5640 |
| within-period | Q3 | 10 | 289 | 0.5958 | 1.9377 |
| within-period | Q3 | 20 | 289 | 0.5927 | 1.8754 |
| within-period | Q3 | 30 | 289 | 0.5904 | 2.3460 |
| within-period | ALL | 5 | 601 | 0.6190 | 4.2263 |
| within-period | ALL | 10 | 601 | 0.6206 | 4.4060 |
| within-period | ALL | 20 | 601 | 0.6193 | 4.3561 |
| within-period | ALL | 30 | 601 | 0.6155 | 4.4825 |

### Cross-period matching (k=10)

| source_period | match_period | k | n | source_t40_rate | matched_t40_rate | difference | source_ev | matched_ev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q2 | Q3 | 10 | 312 | 0.2372 | 0.3231 | -0.0859 | 5.7692 | 0.6154 |
| Q3 | Q2 | 10 | 289 | 0.2734 | 0.2322 | 0.0412 | 3.5986 | 6.0692 |

### Label-permutation null (k=10, within-period)

| k | real_agreement | null_agreement |
| --- | --- | --- |
| 10.0000 | 0.6200 | 0.6231 |


### IN / VAL / OOS slices of the same 604

| split | n | q2_n | q3_n | q2_ev | q3_ev | q2_minus_q3 |
| --- | --- | --- | --- | --- | --- | --- |
| IN_SAMPLE | 236 | 125 | 111 | 5.6000 | 1.6216 | 3.9784 |
| VALIDATION | 248 | 119 | 129 | 4.8739 | 5.1163 | -0.2423 |
| OOS | 120 | 70 | 50 | 7.1429 | 4.4000 | 2.7429 |

## Hypotheses

- **H1 time** — composition only; does not explain outcomes. Clock composition is definitional for Q2 vs Q3. H1 survives only if temporal bins shrink the EV gap.
- **H2 score** — does not survive as primary. Bought-team margin and lead state at the CSV 80 snapshot.
- **H3 opening** — composition only; does not explain outcomes. KALSHI_LAST_PRE_TIP_YES_BID and distance 80-from-open.
- **H4 pre-80 path** — composition only; does not explain outcomes. Warehouse TRADABLE_YES_BID windows. Missing windows stay missing.
- **H5 game-state** — unavailable. Possession / fouls / timeouts are SOURCE_UNAVAILABLE.
- **H6 L2** — unavailable. Historical L2 is SOURCE_UNAVAILABLE. Quote-at-entry is not L2.
- **H7 joint state** — not selected. More than one pre-80 class is required to describe the gap.
- **H8 residual unexplained** — survives. Current pre-80 features do not absorb the Q2 vs Q3 candle-path EV gap.

## Figures

- `fig01_margin.svg`
- `fig02_clock.svg`
- `fig03_open.svg`
- `fig04_velocity.svg`
- `fig05_range.svg`
- `fig06_pca_period.svg`
- `fig07_pca_outcome.svg`
- `fig10_missingness.svg`

## What this will not do

- No skip-4–6 / only-56–60 / only-Q2 rule
- No Kelly, no live, no Risk, no FIRST80 retune
- No Choosin Texas book edit
- No treating PCA/KNN as a signal

## Artifacts

- `features/pre80.parquet`
- `labels/outcomes.parquet`
- `reports/event_path.parquet`
- `reports/analysis.json`

