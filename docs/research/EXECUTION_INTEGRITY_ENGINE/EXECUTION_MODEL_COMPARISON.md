# Execution model comparison

Same trades. Different claims.

| Model | NBA EV | P5 EV | Claim |
|---|---:|---:|---|
| E0 | — | — | no fill |
| E1 | 4.3252 | 4.1331 | modeled occupancy |
| E_THEO | 5.1707 | 4.3551 | illegal promotion |
| 80→40 | 4.3902 | 4.3551 | Model A fallback |
| E3 | NOT_AVAILABLE | NOT_AVAILABLE | no coefficients |
| E4 | NOT_AVAILABLE | NOT_AVAILABLE | no L2 |
| L4 | NOT_AVAILABLE | NOT_AVAILABLE | no tape |

## E2 q (partial=1)

| q | NBA | P5 |
|---|---:|---:|
| q=0.25,partial=1 | 4.373984 | 4.299584 |
| q=0.5,partial=1 | 4.357724 | 4.244105 |
| q=0.75,partial=1 | 4.341463 | 4.188627 |
| q=1.0,partial=1 | 4.325203 | 4.133148 |
