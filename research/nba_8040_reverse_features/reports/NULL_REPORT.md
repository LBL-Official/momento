# KNN report

Euclidean distance on the standardized complete-column matrix.
Fixed k ∈ {5,10,20,30}. No k search.

| k | n | mean_agreement | mean_entropy | mean_neighbor_t40 | mean_cross_period_share | mean_distance |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 604 | 0.6202 | 0.6648 | 0.2599 | 0.2477 | 5.7498 |
| 10 | 604 | 0.6225 | 0.7507 | 0.2579 | 0.2820 | 6.1213 |
| 20 | 604 | 0.6188 | 0.7873 | 0.2572 | 0.3105 | 6.5571 |
| 30 | 604 | 0.6181 | 0.7982 | 0.2558 | 0.3330 | 6.8484 |


## Distance geometry

Support label: **partially_separated** (median cross/within = 1.1502)

| leg | p10 | p25 | p50 | p75 | p90 | mean |
| --- | --- | --- | --- | --- | --- | --- |
| Q2→Q3 nearest | 4.5701 | 4.9838 | 5.4762 | 6.0681 | 6.8508 | 5.7360 |
| Q3→Q2 nearest | 4.5590 | 5.0541 | 5.8424 | 7.0547 | 8.2457 | 6.2618 |
| within Q2 | 3.4248 | 3.9306 | 4.5251 | 5.3371 | 6.4015 | 4.8509 |
| within Q3 | 3.9952 | 4.6673 | 5.3386 | 6.3935 | 7.4955 | 5.6043 |


## Permutation null (T40 shuffled, distances fixed)

| k | observed_agreement | null_mean | null_p50 | null_p025 | null_p975 | percentile_of_observed |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.6202 | 0.6197 | 0.6200 | 0.5996 | 0.6365 | 0.5300 |
| 10 | 0.6225 | 0.6192 | 0.6188 | 0.6036 | 0.6349 | 0.6900 |
| 20 | 0.6188 | 0.6193 | 0.6185 | 0.6084 | 0.6335 | 0.5100 |
| 30 | 0.6181 | 0.6192 | 0.6184 | 0.6091 | 0.6315 | 0.4800 |

