# State-space report

Unconditional PCA composition: **COMPOSITIONALLY PARTIAL**
Distance support: **partially_separated**

## Feature-class ablation (diagnostics, not a leaderboard)

| set | key | n | p | pc1_smd_q2_q3 | pc1_overlap | knn_k10_agreement | q2_to_q3_t40_diff | distance_support | median_cross_over_within |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A_PRICE | PRICE | 604 | 17 | -0.6110 | 0.7266 | 0.6119 | -0.0548 | largely_overlapping | 1.0559 |
| B_TIME | TIME | 604 | 4 | -1.0605 | 0.5778 | 0.6146 | -0.1379 | strongly_separated | 299.4057 |
| C_SCORE | SCORE | 604 | 5 | 0.0753 | 0.7723 | 0.6373 | -0.1217 | largely_overlapping | 0.0000 |
| D_OPEN | OPEN | 604 | 2 | -0.3704 | 0.8074 | 0.6189 | -0.0398 | largely_overlapping | 0.0000 |
| E_MARKET_PATH | MARKET_PATH | 604 | 28 | -0.5956 | 0.7394 | 0.6123 | -0.0710 | largely_overlapping | 1.0534 |
| F_VOLATILITY | VOLATILITY | 604 | 14 | 0.3911 | 0.7428 | 0.6045 | -0.0710 | largely_overlapping | 1.0911 |
| G_PERIOD | PERIOD | 604 | 2 | 0.0000 | 0.0000 | 0.7063 | -0.2611 | strongly_separated | 2830662643152.8525 |
| H_PRICE_TIME | PRICE_TIME | 604 | 21 | -0.8055 | 0.6790 | 0.6204 | -0.0548 | partially_separated | 1.6560 |
| I_PRICE_SCORE | PRICE_SCORE | 604 | 22 | -0.6003 | 0.7219 | 0.6199 | -0.0455 | largely_overlapping | 1.0531 |
| J_TIME_SCORE | TIME_SCORE | 604 | 9 | -0.3370 | 0.6899 | 0.6257 | -0.0395 | strongly_separated | 37.7801 |
| K_ALL_PRE80 | ALL_PRE80 | 604 | 77 | -0.6223 | 0.7248 | 0.6225 | -0.0854 | partially_separated | 1.1502 |

## Temporal variants

### all_pre80
support=partially_separated  k10_agreement=0.6225
| pc | q2_mean | q3_mean | smd | overlap |
| --- | --- | --- | --- | --- |
| 1 | -1.3575 | 1.4699 | -0.6223 | 0.7248 |
| 2 | -0.2785 | 0.3015 | -0.2074 | 0.8482 |
| 3 | 0.2288 | -0.2478 | 0.1905 | 0.8865 |

| source_period | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- |
| Q2 | 0.2389 | 0.3242 | -0.0854 |
| Q3 | 0.2724 | 0.2341 | 0.0383 |

### ex_time
support=largely_overlapping  k10_agreement=0.6149
| pc | q2_mean | q3_mean | smd | overlap |
| --- | --- | --- | --- | --- |
| 1 | -1.2273 | 1.3288 | -0.5655 | 0.7662 |
| 2 | -0.2682 | 0.2904 | -0.2008 | 0.8297 |
| 3 | 0.1794 | -0.1943 | 0.1492 | 0.8904 |

| source_period | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- |
| Q2 | 0.2389 | 0.3226 | -0.0838 |
| Q3 | 0.2724 | 0.2293 | 0.0431 |

### time_frac_plus_nontime
support=largely_overlapping  k10_agreement=0.6214
| pc | q2_mean | q3_mean | smd | overlap |
| --- | --- | --- | --- | --- |
| 1 | -1.2899 | 1.3966 | -0.5929 | 0.7424 |
| 2 | -0.2760 | 0.2988 | -0.2062 | 0.8329 |
| 3 | 0.2002 | -0.2168 | 0.1665 | 0.8893 |

| source_period | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- |
| Q2 | 0.2389 | 0.3236 | -0.0847 |
| Q3 | 0.2724 | 0.2307 | 0.0417 |

### time_raw_plus_nontime
support=largely_overlapping  k10_agreement=0.6214
| pc | q2_mean | q3_mean | smd | overlap |
| --- | --- | --- | --- | --- |
| 1 | -1.2899 | 1.3966 | -0.5929 | 0.7424 |
| 2 | -0.2760 | 0.2988 | -0.2062 | 0.8329 |
| 3 | 0.2002 | -0.2168 | 0.1665 | 0.8893 |

| source_period | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- |
| Q2 | 0.2389 | 0.3236 | -0.0847 |
| Q3 | 0.2724 | 0.2307 | 0.0417 |

## Predetermined tertile interactions

| left | right | left_bin | right_bin | period | n | t40_rate | t40_wilson_lo | t40_wilson_hi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frac_period_remaining | bought_margin | high | high | Q2 | 25 | 0.3600 | 0.2025 | 0.5548 |
| frac_period_remaining | bought_margin | high | high | Q3 | 26 | 0.2308 | 0.1103 | 0.4205 |
| frac_period_remaining | bought_margin | high | high | ALL | 51 | 0.2941 | 0.1871 | 0.4300 |
| frac_period_remaining | bought_margin | high | low | Q2 | 48 | 0.1667 | 0.0870 | 0.2958 |
| frac_period_remaining | bought_margin | high | low | Q3 | 47 | 0.2766 | 0.1694 | 0.4176 |
| frac_period_remaining | bought_margin | high | low | ALL | 95 | 0.2211 | 0.1494 | 0.3144 |
| frac_period_remaining | bought_margin | high | mid | Q2 | 23 | 0.2174 | 0.0966 | 0.4190 |
| frac_period_remaining | bought_margin | high | mid | Q3 | 33 | 0.3333 | 0.1975 | 0.5039 |
| frac_period_remaining | bought_margin | high | mid | ALL | 56 | 0.2857 | 0.1842 | 0.4148 |
| frac_period_remaining | bought_margin | low | high | Q2 | 42 | 0.0952 | 0.0377 | 0.2207 |
| frac_period_remaining | bought_margin | low | high | Q3 | 34 | 0.2353 | 0.1244 | 0.4000 |
| frac_period_remaining | bought_margin | low | high | ALL | 76 | 0.1579 | 0.0927 | 0.2560 |
| frac_period_remaining | bought_margin | low | low | Q2 | 46 | 0.2826 | 0.1732 | 0.4255 |
| frac_period_remaining | bought_margin | low | low | Q3 | 32 | 0.1562 | 0.0686 | 0.3175 |
| frac_period_remaining | bought_margin | low | low | ALL | 78 | 0.2308 | 0.1513 | 0.3356 |
| frac_period_remaining | bought_margin | low | mid | Q2 | 20 | 0.3000 | 0.1455 | 0.5190 |
| frac_period_remaining | bought_margin | low | mid | Q3 | 30 | 0.3000 | 0.1666 | 0.4788 |
| frac_period_remaining | bought_margin | low | mid | ALL | 50 | 0.3000 | 0.1910 | 0.4375 |
| frac_period_remaining | bought_margin | mid | high | Q2 | 34 | 0.2647 | 0.1460 | 0.4312 |
| frac_period_remaining | bought_margin | mid | high | Q3 | 29 | 0.2759 | 0.1470 | 0.4572 |
| frac_period_remaining | bought_margin | mid | high | ALL | 63 | 0.2698 | 0.1758 | 0.3903 |
| frac_period_remaining | bought_margin | mid | low | Q2 | 63 | 0.2857 | 0.1890 | 0.4070 |
| frac_period_remaining | bought_margin | mid | low | Q3 | 40 | 0.3500 | 0.2213 | 0.5049 |
| frac_period_remaining | bought_margin | mid | low | ALL | 103 | 0.3107 | 0.2295 | 0.4055 |
| frac_period_remaining | bought_margin | mid | mid | Q2 | 13 | 0.2308 | 0.0818 | 0.5026 |
| frac_period_remaining | bought_margin | mid | mid | Q3 | 19 | 0.2632 | 0.1181 | 0.4879 |
| frac_period_remaining | bought_margin | mid | mid | ALL | 32 | 0.2500 | 0.1325 | 0.4211 |
| frac_game_elapsed | velocity_5m | high | high | Q3 | 99 | 0.2424 | 0.1687 | 0.3354 |
| frac_game_elapsed | velocity_5m | high | high | ALL | 99 | 0.2424 | 0.1687 | 0.3354 |
| frac_game_elapsed | velocity_5m | high | low | Q3 | 48 | 0.3333 | 0.2168 | 0.4746 |
| frac_game_elapsed | velocity_5m | high | low | ALL | 48 | 0.3333 | 0.2168 | 0.4746 |
| frac_game_elapsed | velocity_5m | high | mid | Q3 | 55 | 0.2909 | 0.1877 | 0.4214 |
| frac_game_elapsed | velocity_5m | high | mid | ALL | 55 | 0.2909 | 0.1877 | 0.4214 |
| frac_game_elapsed | velocity_5m | low | high | Q2 | 33 | 0.3030 | 0.1738 | 0.4734 |
| frac_game_elapsed | velocity_5m | low | high | ALL | 33 | 0.3030 | 0.1738 | 0.4734 |
| frac_game_elapsed | velocity_5m | low | low | Q2 | 100 | 0.2800 | 0.2014 | 0.3749 |
| frac_game_elapsed | velocity_5m | low | low | ALL | 100 | 0.2800 | 0.2014 | 0.3749 |
| frac_game_elapsed | velocity_5m | low | mid | Q2 | 68 | 0.1912 | 0.1153 | 0.3001 |
| frac_game_elapsed | velocity_5m | low | mid | ALL | 68 | 0.1912 | 0.1153 | 0.3001 |
| frac_game_elapsed | velocity_5m | mid | high | Q2 | 34 | 0.2941 | 0.1683 | 0.4617 |
| frac_game_elapsed | velocity_5m | mid | high | Q3 | 25 | 0.2000 | 0.0886 | 0.3913 |
| frac_game_elapsed | velocity_5m | mid | high | ALL | 59 | 0.2542 | 0.1606 | 0.3780 |
| frac_game_elapsed | velocity_5m | mid | low | Q2 | 32 | 0.2188 | 0.1102 | 0.3876 |
| frac_game_elapsed | velocity_5m | mid | low | Q3 | 26 | 0.3846 | 0.2243 | 0.5747 |
| frac_game_elapsed | velocity_5m | mid | low | ALL | 58 | 0.2931 | 0.1918 | 0.4201 |
| frac_game_elapsed | velocity_5m | mid | mid | Q2 | 47 | 0.1489 | 0.0741 | 0.2769 |
| frac_game_elapsed | velocity_5m | mid | mid | Q3 | 37 | 0.2162 | 0.1139 | 0.3720 |
| frac_game_elapsed | velocity_5m | mid | mid | ALL | 84 | 0.1786 | 0.1113 | 0.2739 |
| bought_margin | delta_5m | high | high | Q2 | 20 | 0.2500 | 0.1119 | 0.4687 |
| bought_margin | delta_5m | high | high | Q3 | 44 | 0.2045 | 0.1115 | 0.3450 |
| bought_margin | delta_5m | high | high | ALL | 64 | 0.2188 | 0.1350 | 0.3343 |
| bought_margin | delta_5m | high | low | Q2 | 43 | 0.2791 | 0.1675 | 0.4269 |
| bought_margin | delta_5m | high | low | Q3 | 14 | 0.2857 | 0.1172 | 0.5465 |
| bought_margin | delta_5m | high | low | ALL | 57 | 0.2807 | 0.1808 | 0.4083 |
| bought_margin | delta_5m | high | mid | Q2 | 38 | 0.1316 | 0.0575 | 0.2733 |
| bought_margin | delta_5m | high | mid | Q3 | 31 | 0.2903 | 0.1610 | 0.4659 |
| bought_margin | delta_5m | high | mid | ALL | 69 | 0.2029 | 0.1249 | 0.3122 |
| bought_margin | delta_5m | low | high | Q2 | 35 | 0.3429 | 0.2083 | 0.5085 |
| bought_margin | delta_5m | low | high | Q3 | 51 | 0.2353 | 0.1400 | 0.3676 |
| bought_margin | delta_5m | low | high | ALL | 86 | 0.2791 | 0.1953 | 0.3817 |
| bought_margin | delta_5m | low | low | Q2 | 65 | 0.2615 | 0.1702 | 0.3795 |
| bought_margin | delta_5m | low | low | Q3 | 37 | 0.3784 | 0.2406 | 0.5390 |
| bought_margin | delta_5m | low | low | ALL | 102 | 0.3039 | 0.2231 | 0.3990 |
| bought_margin | delta_5m | low | mid | Q2 | 57 | 0.1754 | 0.0982 | 0.2937 |
| bought_margin | delta_5m | low | mid | Q3 | 31 | 0.1935 | 0.0919 | 0.3628 |
| bought_margin | delta_5m | low | mid | ALL | 88 | 0.1818 | 0.1151 | 0.2751 |
| bought_margin | delta_5m | mid | high | Q2 | 12 | 0.2500 | 0.0889 | 0.5323 |
| bought_margin | delta_5m | mid | high | Q3 | 29 | 0.2759 | 0.1470 | 0.4572 |
| bought_margin | delta_5m | mid | high | ALL | 41 | 0.2683 | 0.1569 | 0.4193 |
| bought_margin | delta_5m | mid | low | Q2 | 24 | 0.2500 | 0.1200 | 0.4490 |
| bought_margin | delta_5m | mid | low | Q3 | 23 | 0.3478 | 0.1881 | 0.5511 |
| bought_margin | delta_5m | mid | low | ALL | 47 | 0.2979 | 0.1865 | 0.4398 |
| bought_margin | delta_5m | mid | mid | Q2 | 20 | 0.2500 | 0.1119 | 0.4687 |
| bought_margin | delta_5m | mid | mid | Q3 | 30 | 0.3000 | 0.1666 | 0.4788 |
| bought_margin | delta_5m | mid | mid | ALL | 50 | 0.2800 | 0.1747 | 0.4167 |
| pregame_cents | entry_bid_cents | high | high | Q2 | 18 | 0.2222 | 0.0900 | 0.4522 |
| pregame_cents | entry_bid_cents | high | high | Q3 | 17 | 0.1765 | 0.0619 | 0.4103 |
| pregame_cents | entry_bid_cents | high | high | ALL | 35 | 0.2000 | 0.1004 | 0.3589 |
| pregame_cents | entry_bid_cents | high | low | Q2 | 65 | 0.2154 | 0.1329 | 0.3297 |
| pregame_cents | entry_bid_cents | high | low | Q3 | 29 | 0.3793 | 0.2269 | 0.5600 |
| pregame_cents | entry_bid_cents | high | low | ALL | 94 | 0.2660 | 0.1871 | 0.3632 |
| pregame_cents | entry_bid_cents | high | mid | Q2 | 38 | 0.2895 | 0.1700 | 0.4476 |
| pregame_cents | entry_bid_cents | high | mid | Q3 | 29 | 0.2759 | 0.1470 | 0.4572 |
| pregame_cents | entry_bid_cents | high | mid | ALL | 67 | 0.2836 | 0.1897 | 0.4009 |
| pregame_cents | entry_bid_cents | low | high | Q2 | 18 | 0.2778 | 0.1250 | 0.5087 |
| pregame_cents | entry_bid_cents | low | high | Q3 | 43 | 0.2326 | 0.1315 | 0.3774 |
| pregame_cents | entry_bid_cents | low | high | ALL | 61 | 0.2459 | 0.1551 | 0.3668 |
| pregame_cents | entry_bid_cents | low | low | Q2 | 33 | 0.3030 | 0.1738 | 0.4734 |
| pregame_cents | entry_bid_cents | low | low | Q3 | 39 | 0.2564 | 0.1457 | 0.4108 |
| pregame_cents | entry_bid_cents | low | low | ALL | 72 | 0.2778 | 0.1876 | 0.3905 |
| pregame_cents | entry_bid_cents | low | mid | Q2 | 34 | 0.2647 | 0.1460 | 0.4312 |
| pregame_cents | entry_bid_cents | low | mid | Q3 | 43 | 0.3023 | 0.1860 | 0.4511 |
| pregame_cents | entry_bid_cents | low | mid | ALL | 77 | 0.2857 | 0.1969 | 0.3949 |
| pregame_cents | entry_bid_cents | mid | high | Q2 | 14 | 0.2857 | 0.1172 | 0.5465 |
| pregame_cents | entry_bid_cents | mid | high | Q3 | 25 | 0.1600 | 0.0640 | 0.3465 |
| pregame_cents | entry_bid_cents | mid | high | ALL | 39 | 0.2051 | 0.1078 | 0.3553 |
| pregame_cents | entry_bid_cents | mid | low | Q2 | 55 | 0.2545 | 0.1581 | 0.3830 |
| pregame_cents | entry_bid_cents | mid | low | Q3 | 32 | 0.4062 | 0.2552 | 0.5774 |
| pregame_cents | entry_bid_cents | mid | low | ALL | 87 | 0.3103 | 0.2229 | 0.4138 |
| pregame_cents | entry_bid_cents | mid | mid | Q2 | 39 | 0.1026 | 0.0406 | 0.2358 |
| pregame_cents | entry_bid_cents | mid | mid | Q3 | 33 | 0.2121 | 0.1068 | 0.3775 |
| pregame_cents | entry_bid_cents | mid | mid | ALL | 72 | 0.1528 | 0.0875 | 0.2532 |
| range_5m | entry_bid_cents | high | high | Q2 | 9 | 0.7778 | 0.4526 | 0.9368 |
| range_5m | entry_bid_cents | high | high | Q3 | 36 | 0.2222 | 0.1172 | 0.3809 |
| range_5m | entry_bid_cents | high | high | ALL | 45 | 0.3333 | 0.2136 | 0.4793 |
| range_5m | entry_bid_cents | high | low | Q2 | 35 | 0.2286 | 0.1207 | 0.3902 |
| range_5m | entry_bid_cents | high | low | Q3 | 37 | 0.2703 | 0.1540 | 0.4298 |
| range_5m | entry_bid_cents | high | low | ALL | 72 | 0.2500 | 0.1644 | 0.3609 |
| range_5m | entry_bid_cents | high | mid | Q2 | 23 | 0.3478 | 0.1881 | 0.5511 |
| range_5m | entry_bid_cents | high | mid | Q3 | 36 | 0.2500 | 0.1375 | 0.4107 |
| range_5m | entry_bid_cents | high | mid | ALL | 59 | 0.2881 | 0.1884 | 0.4138 |
| range_5m | entry_bid_cents | low | high | Q2 | 23 | 0.2609 | 0.1255 | 0.4647 |
| range_5m | entry_bid_cents | low | high | Q3 | 22 | 0.2273 | 0.1012 | 0.4344 |
| range_5m | entry_bid_cents | low | high | ALL | 45 | 0.2444 | 0.1424 | 0.3867 |
| range_5m | entry_bid_cents | low | low | Q2 | 72 | 0.2778 | 0.1876 | 0.3905 |
| range_5m | entry_bid_cents | low | low | Q3 | 37 | 0.3514 | 0.2183 | 0.5124 |
| range_5m | entry_bid_cents | low | low | ALL | 109 | 0.3028 | 0.2244 | 0.3945 |
| range_5m | entry_bid_cents | low | mid | Q2 | 46 | 0.2174 | 0.1226 | 0.3557 |
| range_5m | entry_bid_cents | low | mid | Q3 | 33 | 0.3333 | 0.1975 | 0.5039 |
| range_5m | entry_bid_cents | low | mid | ALL | 79 | 0.2658 | 0.1809 | 0.3724 |
| range_5m | entry_bid_cents | mid | high | Q2 | 18 | 0.0000 | 0.0000 | 0.1759 |
| range_5m | entry_bid_cents | mid | high | Q3 | 27 | 0.1481 | 0.0592 | 0.3248 |
| range_5m | entry_bid_cents | mid | high | ALL | 45 | 0.0889 | 0.0351 | 0.2073 |
| range_5m | entry_bid_cents | mid | low | Q2 | 46 | 0.2174 | 0.1226 | 0.3557 |
| range_5m | entry_bid_cents | mid | low | Q3 | 26 | 0.4231 | 0.2554 | 0.6105 |
| range_5m | entry_bid_cents | mid | low | ALL | 72 | 0.2917 | 0.1994 | 0.4051 |
| range_5m | entry_bid_cents | mid | mid | Q2 | 42 | 0.1429 | 0.0672 | 0.2784 |
| range_5m | entry_bid_cents | mid | mid | Q3 | 36 | 0.2222 | 0.1172 | 0.3809 |
| range_5m | entry_bid_cents | mid | mid | ALL | 78 | 0.1795 | 0.1100 | 0.2790 |

## Unsupervised state regions (k-means on PC1–PC3, labels unused in fit)

| state_region | n | q2_share | t40_rate | s_rate |
| --- | --- | --- | --- | --- |
| STATE_REGION_1 | 91 | 0.3956 | 0.3077 | 0.6923 |
| STATE_REGION_2 | 215 | 0.5628 | 0.2372 | 0.7628 |
| STATE_REGION_3 | 88 | 0.2159 | 0.2841 | 0.7159 |
| STATE_REGION_4 | 210 | 0.6571 | 0.2381 | 0.7619 |


Period LPM AUC on full primary space: 1.0
LPM R²: 1.0
