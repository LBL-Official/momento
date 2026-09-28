# Evidence-level analysis

## Opportunity counts (H=40 exact, L2)

| class | NBA | P5 |
|---|---:|---:|
| AMBIGUOUS_SEQUENCE | 40 | 8 |
| EXACT_OBSERVATION | 92 | 49 |
| GAP_THROUGH | 364 | 233 |
| NO_OBSERVATION | 734 | 431 |

## Occupancy

| status | NBA | P5 |
|---|---:|---:|
| AMBIGUOUS | 40 | 8 |
| INFERRED_POSSIBLE | 364 | 233 |
| NOT_OBSERVED | 734 | 431 |
| OBSERVED_EXACT | 92 | 49 |

## L1 → L2

L1 records the close (e.g. 75). L2 may mark `THRESHOLD_CROSSING` and `GAP_THROUGH`. Occupancy of 40 is `INFERRED_POSSIBLE`, not `OBSERVED_EXACT`.

## L2 → L3

E1 refuses gap fills. Theoretical L3 accepts them. The difference is NBA 0.845528¢ and P5 0.221914¢.

## L3 → L4

L4 = NOT_AVAILABLE. No live fill tape. Modeled E1 must not be labeled actual.
